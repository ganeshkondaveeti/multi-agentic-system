"""Turn logic shared by the JSON and the streamed routes.

`Desk` runs one turn under the session's lock and a graph-run slot, then records
the trace, the provenance, and what ran on the store entry. Errors come out as
`ApiError` with a status, a stable code, and a message that never quotes user text.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from support_reply import accept
from support_reply.contracts import Session
from support_reply.gate import (
    EMAIL_DRAFTS_DIR,
    RECORDS_FILE,
    ApprovalRefused,
    approvable,
    approve,
    default_out_dir,
    valid_session_id,
)
from support_reply.graph import Turn, complaint_turn
from support_reply.llm import CUES_ONLY, Classifier, models_mode
from support_reply.session import MAX_REFINEMENTS, RefinementRefused, refine_turn
from support_reply.trace import AGENT_NODES, Trace
from support_reply.workspace import deliver

from .limits import RunsBusy, RunSlots
from .store import Entry, SessionBusy, SessionNotFound, SessionStore, StoreFull

logger = logging.getLogger(__name__)

Models = dict[str, Classifier | None]
ModelsFactory = Callable[[], Models]

# A /replace is a refinement whose pushback is the text change itself.
REPLACE_PUSHBACK = "The complaint text changed."
EXCERPT_CHARS = 140


class ApiError(Exception):
    """An error the API returns as `{"error": code, "message": message}`."""

    def __init__(self, status: int, error: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.error = error
        self.message = message


def configured_models() -> Models:
    """`REPLY_DESK_MODELS=off` passes `CUES_ONLY`; `auto` lets each node use its default."""
    if models_mode() == "off":
        return {"classifier": CUES_ONLY, "review_classifier": CUES_ONLY}
    return {"classifier": None, "review_classifier": None}


def iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="seconds")


class Desk:
    def __init__(
        self, store: SessionStore, slots: RunSlots, models: ModelsFactory = configured_models
    ) -> None:
        self.store = store
        self.slots = slots
        self._models = models

    # --- prechecks, before a stream starts ---------------------------------------------

    def check_room(self) -> None:
        if not self.store.has_room():
            raise ApiError(503, "store_full", "Every session slot is in use. Try again shortly.")

    def check_open(self, session_id: str, *, refining: bool) -> None:
        with self._locked(session_id) as entry:
            self._require_open(entry)
            if refining:
                self._require_refinable(entry)

    # --- turns ------------------------------------------------------------------------

    def new_complaint(self, complaint: str, trace: Trace) -> dict[str, Any]:
        self.check_room()
        models = self._models()
        with self._slot():
            turn = complaint_turn(Session(), complaint, trace=trace, **models)
        del complaint
        try:
            entry = self.store.add(turn.session)
        except StoreFull as exc:
            raise ApiError(503, "store_full", "Every session slot is in use. Try again shortly.") from exc
        with self._locked(entry.session_id) as entry:
            self._record(entry, "complaint", trace, turn)
            return self._view(entry)

    def message(self, session_id: str, message: str, trace: Trace) -> dict[str, Any]:
        models = self._models()
        with self._locked(session_id) as entry:
            self._require_open(entry)
            with self._slot():
                turn = complaint_turn(entry.session, message, trace=trace, **models)
            del message
            self._record(entry, "message", trace, turn)
            return self._view(entry)

    def refine(
        self, session_id: str, pushback: str, trace: Trace, *, complaint: str | None = None
    ) -> dict[str, Any]:
        kind = "refinement" if complaint is None else "replace"
        models = self._models()
        with self._locked(session_id) as entry:
            self._require_open(entry)
            self._require_refinable(entry)
            with self._slot():
                try:
                    turn = refine_turn(
                        entry.session, pushback, complaint=complaint, trace=trace, **models
                    )
                except RefinementRefused as exc:
                    raise ApiError(409, "refinement_refused", str(exc)) from exc
            del pushback, complaint
            self._record(entry, kind, trace, turn)
            return self._view(entry)

    def replace(self, session_id: str, complaint: str, trace: Trace) -> dict[str, Any]:
        """The human corrected the complaint text: a refinement in which every agent re-runs."""
        return self.refine(session_id, REPLACE_PUSHBACK, trace, complaint=complaint)

    def approve(self, session_id: str) -> dict[str, Any]:
        with self._locked(session_id) as entry:
            if entry.approved is not None:
                raise ApiError(409, "already_approved", "This session is already approved.")
            try:
                approval = approve(
                    entry.session, human_approved=True, session_id=session_id, out_dir=default_out_dir()
                )
            except ApprovalRefused as exc:
                raise ApiError(409, "not_approvable", str(exc)) from exc
            record = find_record(approval.records_path, session_id)
            if record is None:
                raise ApiError(500, "record_missing", "The record was written but could not be read back.")
            # The approval stands from here on; the Doc append and Gmail draft report
            # their own outcome.
            delivery = deliver(record, approval.email_path.read_text(encoding="utf-8")).to_dict()
            entry.approved = {
                "approved_at": record["approved_at"],
                "email_file": approval.email_path.name,
                "delivery": delivery,
            }
            return {
                "session_id": session_id,
                "email_file": approval.email_path.name,
                "record": record,
                "delivery": delivery,
            }

    # --- reads ------------------------------------------------------------------------

    def view(self, session_id: str) -> dict[str, Any]:
        with self._locked(session_id) as entry:
            return self._view(entry)

    def summaries(self) -> list[dict[str, Any]]:
        return [self._summary(entry) for entry in self.store.entries()]

    # --- helpers ----------------------------------------------------------------------

    @contextmanager
    def _locked(self, session_id: str) -> Iterator[Entry]:
        if not valid_session_id(session_id):
            raise ApiError(404, "session_not_found", "No live session has this id.")
        try:
            with self.store.locked(session_id) as entry:
                yield entry
        except SessionNotFound as exc:
            raise ApiError(404, "session_not_found", "No live session has this id.") from exc
        except SessionBusy as exc:
            raise ApiError(409, "session_busy", "Another turn on this session is still running.") from exc

    @contextmanager
    def _slot(self) -> Iterator[None]:
        try:
            with self.slots.slot():
                yield
        except RunsBusy as exc:
            raise ApiError(503, "busy", "The desk is busy. Try again in a few seconds.") from exc

    @staticmethod
    def _require_open(entry: Entry) -> None:
        if entry.approved is not None:
            raise ApiError(409, "already_approved", "This session is approved; start a new one.")

    @staticmethod
    def _require_refinable(entry: Entry) -> None:
        if entry.session.refinement_count >= MAX_REFINEMENTS:
            raise ApiError(
                409,
                "refinement_refused",
                f"Refinement limit reached: {MAX_REFINEMENTS} pushbacks already applied; "
                "the last reviewed draft stands.",
            )

    def _record(self, entry: Entry, kind: str, trace: Trace, turn: Turn) -> None:
        entry.trace = trace.to_list()
        entry.provenance.update(turn.provenance)
        entry.turn = {
            "kind": kind,
            "ran": [node for node in AGENT_NODES if trace.starts(node)] + ["orchestrator"],
            "provenance": dict(turn.provenance),
        }
        entry.updated_at = self.store.now()

    def _view(self, entry: Entry) -> dict[str, Any]:
        session = entry.session
        return {
            "session_id": entry.session_id,
            "session": session.to_dict(),
            "trace": list(entry.trace),
            "provenance": dict(entry.provenance),
            "turn": dict(entry.turn),
            "approvable": approvable(session) and entry.approved is None,
            "approved": dict(entry.approved) if entry.approved else None,
            "refinements_left": MAX_REFINEMENTS - session.refinement_count,
            "created_at": iso(entry.created_at),
            "updated_at": iso(entry.updated_at),
        }

    @staticmethod
    def _summary(entry: Entry) -> dict[str, Any]:
        session = entry.session
        draft, review = session.draft, session.review
        text = session.redacted_text
        excerpt = text if len(text) <= EXCERPT_CHARS else text[: EXCERPT_CHARS - 1].rstrip() + "…"
        return {
            "session_id": entry.session_id,
            "excerpt": excerpt,
            "disposition": None if draft is None else draft.disposition,
            "priority": None if draft is None else draft.routing_note.priority,
            "review_status": None if review is None else review.status,
            "refinement_count": session.refinement_count,
            "advice_refusal": session.advice_refusal,
            "approved": entry.approved is not None,
            "updated_at": iso(entry.updated_at),
        }


# --- records ------------------------------------------------------------------------------


def load_records(out_dir: Path | None = None) -> list[dict[str, Any]]:
    """Every approved record, in file order. A malformed line is skipped and logged by number."""
    path = (out_dir or default_out_dir()) / RECORDS_FILE
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("records line %d is not JSON; skipped", number)
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def find_record(records_path: Path, session_id: str) -> dict[str, Any] | None:
    for record in reversed(load_records(records_path.parent)):
        if record.get("session_id") == session_id:
            return record
    return None


def email_text(session_id: str, out_dir: Path | None = None) -> str:
    if not valid_session_id(session_id):
        raise ApiError(404, "email_not_found", "No email draft has this id.")
    path = (out_dir or default_out_dir()) / EMAIL_DRAFTS_DIR / f"{session_id}.txt"
    if not path.is_file():
        raise ApiError(404, "email_not_found", "No email draft has this id.")
    return path.read_text(encoding="utf-8")


# --- acceptance ---------------------------------------------------------------------------


class AcceptanceRunner:
    """One cues-only acceptance run at a time; keeps the last report."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.last: dict[str, Any] | None = None

    def run(self, clock: Callable[[], float]) -> dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            raise ApiError(429, "acceptance_running", "An acceptance run is already in progress.")
        try:
            report = accept.report(offline=True)
            report["ran_at"] = iso(clock())
            self.last = report
            return report
        finally:
            self._lock.release()
