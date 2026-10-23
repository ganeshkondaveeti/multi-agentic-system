"""Phase 10 acceptance run. `python -m support_reply.accept` exits non-zero on the first miss.

Checks, in order:

1. 20 real complaints from `normalized_reviews.json` (non-empty text, file order).
   Every one returns all three agent results, keeps the parallel trace rule, and
   either cites its scheme's `source_url` or states no fact at all.
2. The four branches from `fixtures.BRANCHES`: clean hit, corpus miss, recurring
   theme, and PII. Each records its trace and which agents fired. The clean hit and
   the PII branch are approved.
3. The advice thread: one session, every turn `refuse`, `advice_refusal` stays true.
4. The caps: two reviewer failures end `blocked` and approve writes nothing; the
   sixth pushback is refused and leaves the draft as it was.

`report()` runs the checks and returns a JSON-ready dict; `render()` turns it into
the text this script prints. The report holds review ids and outcomes, never review
text. Approvals go to a temporary directory unless `out_dir` is given, so a run never
adds test records to the real `out/`. With `--offline` (or `report(offline=True)`)
every node is passed `CUES_ONLY` and the run needs no network; the API keys are left
alone. Without it, whatever `GROQ_API_KEY` and `GEMINI_API_KEY` configure is used.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from support_reply.contracts import COVERED_DISPOSITIONS, Session
from support_reply.corpus import data_dir
from support_reply.fixtures import (
    ADVICE_THREAD,
    BRANCHES,
    CLEAN_HIT,
    LARGE_CAP_URL,
    RAW_PAN,
    RAW_PHONE,
    REAL_COMPLAINT_COUNT,
)
from support_reply.gate import (
    EMAIL_DRAFTS_DIR,
    RECORDS_FILE,
    ApprovalRefused,
    approvable,
    approve,
)
from support_reply.graph import Turn, complaint_turn
from support_reply.llm import CUES_ONLY, Classifier, models_mode
from support_reply.reviewer import factual_claims, urls
from support_reply.session import MAX_REFINEMENTS, RefinementRefused, refine
from support_reply.trace import AGENT_NODES, Trace

Models = dict[str, Classifier | None]
Report = dict[str, Any]


class AcceptanceFailure(AssertionError):
    """One acceptance check missed. The message names the check and the input."""


class _FlagsTheSource:
    """A review model that always quotes the `Source:` label as advice.

    Every covered template ends with that label, so the rewrite cannot drop it and
    round 2 fails as well. This is how the cap check forces `blocked`.
    """

    def classify(self, **_: Any) -> dict[str, Any]:
        return {"failures": [{"check": "advice", "span": "Source"}]}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m support_reply.accept")
    parser.add_argument(
        "--out", type=Path, default=None, help="keep approvals here (default: a temporary directory)"
    )
    parser.add_argument(
        "--offline", action="store_true", help="skip the models and use the cue tables"
    )
    args = parser.parse_args(argv)
    result = report(out_dir=args.out, offline=args.offline)
    print(render(result))
    return 0 if result["status"] == "pass" else 1


def report(
    *,
    out_dir: Path | None = None,
    offline: bool = False,
    classifier: Classifier | None = None,
    review_classifier: Classifier | None = None,
) -> Report:
    """Run every check and return the report. Stops at the first miss.

    `status` is `pass` or `fail`; on a miss, `failure` names it and the sections
    hold what ran up to that point.
    """
    models: Models = (
        {"classifier": CUES_ONLY, "review_classifier": CUES_ONLY}
        if offline
        else {"classifier": classifier, "review_classifier": review_classifier}
    )
    result: Report = {
        "status": "fail",
        "failure": None,
        "mode": "cues" if offline else models_mode(),
        "real_complaints": [],
        "branches": [],
        "advice_thread": [],
        "caps": {},
    }
    with ExitStack() as stack:
        out = Path(out_dir) if out_dir is not None else Path(
            stack.enter_context(tempfile.TemporaryDirectory(prefix="reply-desk-accept-"))
        )
        try:
            check_real_complaints(result, models)
            check_branches(result, out, models)
            check_advice_thread(result, models)
            check_caps(result, out, models)
        except AcceptanceFailure as exc:
            result["failure"] = str(exc)
            return result
    result["status"] = "pass"
    return result


# --- 1. Twenty real complaints ----------------------------------------------------------


def real_complaints(count: int = REAL_COMPLAINT_COUNT) -> list[tuple[str, str]]:
    """`(id, text)` for the first `count` reviews with non-empty text, in file order."""
    with (data_dir() / "normalized_reviews.json").open(encoding="utf-8") as handle:
        reviews = json.load(handle)
    picked: list[tuple[str, str]] = []
    for review in reviews:
        text = review.get("text")
        if isinstance(text, str) and text.strip():
            picked.append((review["id"], text))
        if len(picked) == count:
            break
    return picked


def check_real_complaints(result: Report, models: Models) -> None:
    complaints = real_complaints()
    _require(
        len(complaints) == REAL_COMPLAINT_COUNT,
        f"expected {REAL_COMPLAINT_COUNT} reviews with text, found {len(complaints)}",
    )
    for review_id, text in complaints:
        trace = Trace()
        turn = _handle(Session(), text, trace=trace, label=f"review {review_id}", **models)
        del text
        session = turn.session
        result["real_complaints"].append(
            {"review_id": review_id, **_outcome(session), "provenance": dict(turn.provenance)}
        )
        _require_parallel(trace, f"review {review_id}")
        _require_cited_or_factless(session, f"review {review_id}")


# --- 2. The four branches ---------------------------------------------------------------


def check_branches(result: Report, out_dir: Path, models: Models) -> None:
    for name, text in BRANCHES.items():
        trace = Trace()
        turn = _handle(Session(), text, trace=trace, label=name, **models)
        session = turn.session
        entry: dict[str, Any] = {
            "name": name,
            "redacted_text": session.redacted_text,
            **_outcome(session),
            "routing_note": session.draft.routing_note.to_dict(),
            "agents_fired_this_turn": [node for node in AGENT_NODES if trace.starts(node)]
            + ["orchestrator"],
            "agents_fired": [item.to_dict() for item in session.agents_fired],
            "trace": trace.to_list(),
            "provenance": dict(turn.provenance),
            "approved": None,
        }
        result["branches"].append(entry)
        _require_parallel(trace, name)
        _require_cited_or_factless(session, name)
        _BRANCH_CHECKS[name](session, out_dir, entry)


def _check_clean_hit(session: Session, out_dir: Path, entry: dict[str, Any]) -> None:
    label = "clean_hit"
    facts = session.facts
    _require(facts is not None and facts.status == "covered", f"{label}: Facts not covered")
    _require(facts.scheme_id == "large_cap", f"{label}: scheme {facts.scheme_id!r}")
    _require(session.draft.citation == LARGE_CAP_URL, f"{label}: citation {session.draft.citation!r}")
    _require(LARGE_CAP_URL in session.draft.reply, f"{label}: reply lacks the large-cap URL")
    _require(session.review.status == "pass", f"{label}: review {session.review.status!r}")
    try:
        approve(session, human_approved=False, out_dir=out_dir)
    except ApprovalRefused:
        pass
    else:
        raise AcceptanceFailure(f"{label}: approve ran without the human-approve flag")
    _approve_and_check(session, out_dir, label, entry)


def _check_corpus_miss(session: Session, out_dir: Path, entry: dict[str, Any]) -> None:
    label = "corpus_miss"
    facts = session.facts
    _require(facts.status == "not_covered", f"{label}: Facts {facts.status!r}")
    _require(bool(facts.searched), f"{label}: searched is empty")
    _require(session.draft.disposition == "handoff", f"{label}: {session.draft.disposition!r}")
    _require(not urls(session.draft.reply), f"{label}: reply carries a URL")
    claims = factual_claims(session.draft.reply)
    _require(not claims, f"{label}: reply states a fact: {claims}")


def _check_recurring_theme(session: Session, out_dir: Path, entry: dict[str, Any]) -> None:
    label = "recurring_theme"
    pattern = session.pattern
    _require(pattern.theme_id == "fees_brokerage", f"{label}: theme {pattern.theme_id!r}")
    _require(pattern.count == 136, f"{label}: count {pattern.count}")
    _require(pattern.signal in ("recurring", "rising"), f"{label}: signal {pattern.signal!r}")
    _require(
        session.draft.disposition in ("escalate", "disagree"),
        f"{label}: disposition {session.draft.disposition!r} closes the ticket",
    )
    note = session.draft.routing_note
    _require("stays open" in note.why, f"{label}: routing note does not keep the ticket open")


def _check_pii(session: Session, out_dir: Path, entry: dict[str, Any]) -> None:
    label = "pii"
    stored = json.dumps(session.to_dict(), ensure_ascii=False)
    for raw in (RAW_PAN, RAW_PHONE):
        _require(raw not in stored, f"{label}: a raw value is in session state")
    _require(
        "[PAN]" in session.redacted_text and "[PHONE]" in session.redacted_text,
        f"{label}: ingress tokens missing from {session.redacted_text!r}",
    )
    _require("pii" in session.compliance.flags, f"{label}: Compliance did not flag pii")
    pii_failures = [f for f in session.review.failures if f.check == "pii"]
    _require(
        session.review.status == "pass" and not pii_failures,
        f"{label}: reviewer PII check did not pass",
    )
    approval = _approve_and_check(session, out_dir, label, entry)
    written = approval.records_path.read_text(encoding="utf-8").splitlines()[-1]
    email = approval.email_path.read_text(encoding="utf-8")
    _require("[PAN]" in written, f"{label}: the record lost the [PAN] token")
    for raw in (RAW_PAN, RAW_PHONE):
        _require(raw not in written and raw not in email, f"{label}: a raw value reached out/")


_BRANCH_CHECKS = {
    "clean_hit": _check_clean_hit,
    "corpus_miss": _check_corpus_miss,
    "recurring_theme": _check_recurring_theme,
    "pii": _check_pii,
}
assert set(_BRANCH_CHECKS) == set(BRANCHES)


# --- 3. Advice resistance ---------------------------------------------------------------


def check_advice_thread(result: Report, models: Models) -> None:
    session = Session()
    for turn_number, ask in enumerate(ADVICE_THREAD, start=1):
        session = _handle(session, ask, label=f"advice turn {turn_number}", **models).session
        result["advice_thread"].append(
            {
                "turn": turn_number,
                "ask": ask,
                "disposition": session.draft.disposition,
                "flags": list(session.compliance.flags),
                "advice_refusal": session.advice_refusal,
            }
        )
        _require(
            session.draft.disposition == "refuse",
            f"advice turn {turn_number}: {session.draft.disposition!r}, not refuse",
        )
        _require(session.advice_refusal, f"advice turn {turn_number}: advice_refusal is not set")
        _require(not urls(session.draft.reply), f"advice turn {turn_number}: refusal carries a URL")


# --- 4. Caps ----------------------------------------------------------------------------


def check_caps(result: Report, out_dir: Path, models: Models) -> None:
    before = _out_snapshot(out_dir)
    session = _handle(
        Session(),
        CLEAN_HIT,
        label="blocked",
        classifier=models["classifier"],
        review_classifier=_FlagsTheSource(),
    ).session
    _require(
        session.review.status == "blocked" and session.review.round == 2,
        f"blocked: review {session.review.status!r} round {session.review.round}",
    )
    _require(not approvable(session), "blocked: the session is approvable")
    try:
        approve(session, human_approved=True, out_dir=out_dir)
    except ApprovalRefused:
        pass
    else:
        raise AcceptanceFailure("blocked: approve accepted a blocked draft")
    _require(_out_snapshot(out_dir) == before, "blocked: approve wrote to out/")
    result["caps"]["blocked"] = {
        "review_status": session.review.status,
        "review_round": session.review.round,
        "failed_checks": sorted({failure.check for failure in session.review.failures}),
        "approve_refused": True,
        "files_written": 0,
    }

    session = _handle(Session(), CLEAN_HIT, label="refinement cap", **models).session
    for _ in range(MAX_REFINEMENTS):
        refine(session, "Shorter", **models)
    last = session.draft
    try:
        refine(session, "Shorter", **models)
    except RefinementRefused:
        pass
    else:
        raise AcceptanceFailure("refinement cap: the sixth pushback was accepted")
    _require(session.refinement_count == MAX_REFINEMENTS, "refinement cap: count moved")
    _require(session.draft == last, "refinement cap: the draft changed")
    result["caps"]["refinement_cap"] = {
        "applied": session.refinement_count,
        "sixth_refused": True,
        "draft_kept": True,
    }


# --- text output ------------------------------------------------------------------------


def render(result: Report) -> str:
    """The text the script prints, built only from the report."""
    lines = [f"== {REAL_COMPLAINT_COUNT} real complaints (mode: {result['mode']})"]
    for item in result["real_complaints"]:
        lines.append(f"  {item['review_id']}  {_outcome_line(item)}")

    if result["branches"]:
        lines.append("\n== four branches")
    for branch in result["branches"]:
        lines.append(f"\n-- {branch['name']}: {_outcome_line(branch)}")
        lines.append(f"   agents fired: {branch['agents_fired_this_turn']}")
        lines.append(f"   agents_fired log: {branch['agents_fired']}")
        lines.append(f"   provenance: {branch['provenance']}")
        lines.append("   trace:")
        for event in branch["trace"]:
            lines.append(
                f"     {event['seq']:03d} {event['elapsed_ms']:9.3f}ms "
                f"{event['kind']:<6} {event['node']}"
            )
        if branch["name"] == "recurring_theme":
            note = branch["routing_note"]
            lines.append(f"   routing: {note['team']}, {note['priority']}: {note['why']}")
        if branch["name"] == "pii":
            lines.append(f"   redacted: {branch['redacted_text']}")
            lines.append("   reviewer pii check: pass (no raw value in the reply, routing note, or record)")
        if branch["approved"]:
            lines.append(f"   approved: record appended, email draft {branch['approved']['email_file']}")
    if len(result["branches"]) == len(BRANCHES):
        lines.append("\n   parallel: facts, pattern, and compliance started before any returned, on every branch")

    if result["advice_thread"]:
        lines.append("\n== advice thread (one session)")
    for turn in result["advice_thread"]:
        lines.append(f"  {turn['turn']}. {turn['disposition']}  flags={turn['flags']}  {turn['ask']}")

    caps = result["caps"]
    if caps:
        lines.append("\n== caps")
    if "blocked" in caps:
        lines.append("  two reviewer failures: blocked at round 2, approve refused, nothing written")
    if "refinement_cap" in caps:
        lines.append(f"  {MAX_REFINEMENTS} pushbacks applied, the sixth refused, last draft kept")

    if result["status"] == "pass":
        lines.append("\nPASS: every acceptance check held")
    else:
        lines.append(f"\nFAIL: {result['failure']}")
    return "\n".join(lines)


# --- helpers ----------------------------------------------------------------------------


def _require(condition: object, message: str) -> None:
    if not condition:
        raise AcceptanceFailure(message)


def _handle(
    session: Session,
    text: str,
    *,
    label: str,
    trace: Trace | None = None,
    classifier: Classifier | None = None,
    review_classifier: Classifier | None = None,
) -> Turn:
    """`complaint_turn`, with a missing agent result reported as an acceptance miss."""
    try:
        turn = complaint_turn(
            session,
            text,
            classifier=classifier,
            review_classifier=review_classifier,
            trace=trace,
        )
    except RuntimeError as exc:
        raise AcceptanceFailure(f"{label}: {exc}") from exc
    for node in AGENT_NODES:
        _require(getattr(turn.session, node) is not None, f"{label}: {node} returned no result")
    return turn


def _require_parallel(trace: Trace, label: str) -> None:
    problems = trace.violations()
    _require(not problems, f"{label}: parallel rule broken: {problems}")


def _require_cited_or_factless(session: Session, label: str) -> None:
    """A covered reply cites its scheme. Any other reply states no fact and no link."""
    draft = session.draft
    if draft.disposition in COVERED_DISPOSITIONS:
        _require(
            draft.citation is not None and draft.citation == session.facts.citation,
            f"{label}: covered reply without its source_url",
        )
        _require(draft.citation in draft.reply, f"{label}: reply text lacks the source_url")
        return
    if draft.disposition == "handoff":
        _require(session.facts.status == "not_covered", f"{label}: handoff on a covered fact")
    _require(not urls(draft.reply), f"{label}: uncovered reply carries a URL")
    claims = factual_claims(draft.reply)
    _require(not claims, f"{label}: uncited fact in reply: {claims}")


def _approve_and_check(session: Session, out_dir: Path, label: str, entry: dict[str, Any]):
    records = out_dir / RECORDS_FILE
    lines_before = _line_count(records)
    approval = approve(session, human_approved=True, out_dir=out_dir)
    _require(_line_count(records) == lines_before + 1, f"{label}: approve did not append one record")
    _require(approval.email_path.is_file(), f"{label}: no email draft was written")
    _require(
        approval.email_path.read_text(encoding="utf-8").strip() == session.draft.reply,
        f"{label}: the email draft is not the reply text",
    )
    entry["approved"] = {"session_id": approval.session_id, "email_file": approval.email_path.name}
    return approval


def _line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return len(path.read_text(encoding="utf-8").splitlines())


def _out_snapshot(out_dir: Path) -> tuple[int, tuple[str, ...]]:
    drafts = out_dir / EMAIL_DRAFTS_DIR
    names = tuple(sorted(p.name for p in drafts.iterdir())) if drafts.is_dir() else ()
    return _line_count(out_dir / RECORDS_FILE), names


def _outcome(session: Session) -> dict[str, Any]:
    facts, pattern = session.facts, session.pattern
    return {
        "facts_status": facts.status,
        "scheme_id": facts.scheme_id,
        "section_title": facts.section_title,
        "theme_id": pattern.theme_id,
        "signal": pattern.signal,
        "count": pattern.count,
        "compliance_flags": list(session.compliance.flags),
        "disposition": session.draft.disposition,
        "review_status": session.review.status,
    }


def _outcome_line(item: dict[str, Any]) -> str:
    facts = f"facts={item['facts_status']}"
    if item["facts_status"] == "covered":
        facts += f"/{item['scheme_id']}/{item['section_title']}"
    return (
        f"{facts}  pattern={item['theme_id']}/{item['signal']}/{item['count']}"
        f"  compliance={item['compliance_flags']}"
        f"  disposition={item['disposition']}  review={item['review_status']}"
    )


if __name__ == "__main__":
    sys.exit(main())
