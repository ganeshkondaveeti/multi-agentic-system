"""Approval gate. Nothing is appended or drafted until a human clicks approve.

The human click is the only trigger, and the reviewer status must be `pass`.
`fail` and `blocked` sessions are not approvable: the UI hides Approve and Send,
and a programmatic call lands here and raises.

`approve` calls `require_approvable` first and writes nothing when it raises.
On approve it appends one redacted record to `out/records.jsonl` and writes the
reply to `out/email_drafts/{session_id}.txt`. There is no SMTP client and no send
function: the email file is a draft a human sends by hand.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from support_reply.contracts import Session
from support_reply.corpus import data_dir
from support_reply.ingress import scan

logger = logging.getLogger(__name__)

OUT_DIR_ENV = "REPLY_DESK_OUT_DIR"
RECORDS_FILE = "records.jsonl"
EMAIL_DRAFTS_DIR = "email_drafts"
# A session id names a file, so it is a plain token: no separators, no dots.
_SESSION_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class ApprovalRefused(RuntimeError):
    """Raised when something tries to approve a session the gate does not accept."""


@dataclass(frozen=True, slots=True)
class Approval:
    """Where one approve wrote. Paths and the id only, never the record body."""

    session_id: str
    records_path: Path
    email_path: Path


def default_out_dir() -> Path:
    """`REPLY_DESK_OUT_DIR` when set (a Railway volume), else the repo `out/`. Gitignored."""
    configured = os.environ.get(OUT_DIR_ENV, "").strip()
    if configured:
        return Path(configured)
    return data_dir().parent / "out"


def approvable(session: Session) -> bool:
    """True only when a draft exists and its last review is `pass`."""
    if not isinstance(session, Session):
        raise TypeError("gate expects a Session")
    return (
        session.draft is not None
        and session.review is not None
        and session.review.status == "pass"
    )


def require_approvable(session: Session, *, human_approved: bool) -> None:
    """Raise `ApprovalRefused` unless a human approved a reviewer-passed draft."""
    if type(human_approved) is not bool:
        raise TypeError("human_approved must be a bool")
    if not human_approved:
        raise ApprovalRefused("approve requires the human-approve flag")
    if session.draft is None or session.review is None:
        raise ApprovalRefused("nothing to approve: the session has no reviewed draft")
    if session.review.status != "pass":
        checks = [failure.check for failure in session.review.failures]
        raise ApprovalRefused(
            f"review status is {session.review.status!r} (round {session.review.round}, "
            f"checks {checks}); approve is not available"
        )


def approve(
    session: Session,
    *,
    human_approved: bool,
    session_id: str | None = None,
    out_dir: Path | str | None = None,
) -> Approval:
    """Append one redacted record and write one email draft. Never sends.

    Both payloads are built and scanned for raw PII before either file is touched,
    so a refused approve leaves `out/` as it was. `session_id` names the email file;
    a random one is used when it is not given.
    """
    if not isinstance(session, Session):
        raise TypeError("gate expects a Session")
    require_approvable(session, human_approved=human_approved)
    if session_id is None:
        session_id = new_session_id()
    if not valid_session_id(session_id):
        raise ValueError("session_id must be 1-64 letters, digits, underscores, or hyphens")

    out = Path(out_dir) if out_dir is not None else default_out_dir()
    records_path = out / RECORDS_FILE
    email_path = out / EMAIL_DRAFTS_DIR / f"{session_id}.txt"
    if email_path.exists():
        raise ApprovalRefused(f"session {session_id} already has an email draft")

    record = record_for(session, session_id=session_id)
    line = json.dumps(record, ensure_ascii=False)
    email = email_for(session)
    _refuse_raw_pii(line, "record")
    _refuse_raw_pii(email, "email draft")

    email_path.parent.mkdir(parents=True, exist_ok=True)
    with email_path.open("x", encoding="utf-8") as handle:
        handle.write(email)
    with records_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    logger.info("approved session %s: record appended, email draft written", session_id)
    return Approval(session_id=session_id, records_path=records_path, email_path=email_path)


def valid_session_id(value: object) -> bool:
    """True for a plain token that can name an email draft file."""
    return isinstance(value, str) and _SESSION_ID.fullmatch(value) is not None


def new_session_id() -> str:
    """A random hex id. One whose digits read as a phone or Aadhaar is drawn again,
    so the record's own PII scan never trips on the id."""
    while True:
        candidate = uuid.uuid4().hex
        if not scan(candidate).pii_types:
            return candidate


def record_for(session: Session, *, session_id: str) -> dict[str, Any]:
    """The stored record: redacted complaint, outcome, routing, and who fired."""
    draft = session.draft
    if draft is None or session.pattern is None:
        raise ApprovalRefused("nothing to approve: the session has no reviewed draft")
    return {
        "session_id": session_id,
        "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "redacted_text": session.redacted_text,
        "pii_types": list(session.pii_types),
        "disposition": draft.disposition,
        "reply": draft.reply,
        "citation": draft.citation,
        "last_checked": draft.last_checked,
        "routing_note": draft.routing_note.to_dict(),
        "pattern_signal": session.pattern.signal,
        "agents_fired": [entry.to_dict() for entry in session.agents_fired],
    }


def email_for(session: Session) -> str:
    """The email draft is the reply text. A covered reply already ends with its source."""
    if session.draft is None:
        raise ApprovalRefused("nothing to approve: the session has no reviewed draft")
    return session.draft.reply + "\n"


def _refuse_raw_pii(text: str, place: str) -> None:
    found = scan(text).pii_types
    if found:
        raise ApprovalRefused(f"{place} holds raw {', '.join(found)}; nothing was written")
