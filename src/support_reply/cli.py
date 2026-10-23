"""Interactive session CLI. `python -m support_reply.cli` drives one complaint thread.

The human types a complaint, reads the three agent results, the parallel trace, the
draft, the routing note, and the review, then pushes back or approves. Every turn
prints which agents fired, so the demo trace is a log, not a screenshot.

    plain text        a pushback; only the agents it names re-run (five at most)
    /message TEXT     a new message from the user in the same thread; all agents run
    /replace TEXT     the human corrects the complaint text; a refinement, all agents run
    /approve          the gate: append a redacted record and write an email draft
    /show             print the current state again
    /quit             end the session without approving; nothing is written
    /help             list the commands

`/approve` is offered only while the last review is `pass`. Nothing is sent. The raw
complaint is handed to the graph and dropped; the CLI prints the redacted text only.
With `--offline` every node is passed `CUES_ONLY` and uses its cue table; the keys are left alone.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from support_reply.contracts import Session
from support_reply.gate import ApprovalRefused, approvable, approve, default_out_dir
from support_reply.graph import handle_complaint
from support_reply.llm import CUES_ONLY, Classifier
from support_reply.session import MAX_REFINEMENTS, RefinementRefused, refine
from support_reply.trace import AGENT_NODES, Trace
from support_reply.workspace import Step, deliver

Emit = Callable[[str], None]
Read = Callable[[str], str]

# A /replace is a refinement whose pushback is the text change itself.
REPLACE_PUSHBACK = "The complaint text changed."

HELP = """Commands:
  <text>            push back on the draft; only the agents it names re-run
  /message <text>   a new message from the user in this thread; all agents run
  /replace <text>   correct the complaint text; a refinement, all agents run
  /approve          append a redacted record and write an email draft (no send)
  /show             print the current state again
  /quit             end without approving; nothing is written
  /help             this list"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m support_reply.cli")
    parser.add_argument("--out", type=Path, default=None, help="output directory (default: out/)")
    parser.add_argument(
        "--offline", action="store_true", help="skip the models and use the cue tables"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="also log each node's redacted result to stderr"
    )
    args = parser.parse_args(argv)
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    out_dir = args.out if args.out is not None else default_out_dir()
    if args.offline:
        return run_session(out_dir=out_dir, classifier=CUES_ONLY, review_classifier=CUES_ONLY)
    return run_session(out_dir=out_dir)


def run_session(
    *,
    out_dir: Path,
    read: Read | None = None,
    emit: Emit = print,
    classifier: Classifier | None = None,
    review_classifier: Classifier | None = None,
) -> int:
    """Drive one thread until approve, /quit, or end of input. Returns the exit code.

    `read` defaults to `input`, looked up at call time.
    """
    if read is None:
        read = input
    models: dict[str, Any] = {"classifier": classifier, "review_classifier": review_classifier}
    emit("Reply Desk: one complaint thread. Type /help for commands.")

    complaint = _read(read, "\nComplaint> ")
    while complaint is not None and not complaint.strip():
        complaint = _read(read, "Complaint> ")
    if complaint is None:
        emit("No complaint. Nothing was written.")
        return 0

    trace = Trace()
    session = handle_complaint(Session(), complaint, trace=trace, **models)
    del complaint
    emit(render_turn(session, trace, heading="Complaint"))

    while True:
        line = _read(read, f"\n{_prompt(session)}> ")
        if line is None:
            emit("\nEnd of input. Not approved; nothing was written.")
            return 0
        command, _, text = line.strip().partition(" ")
        text = text.strip()

        if not command:
            continue
        if command == "/help":
            emit(HELP)
        elif command == "/show":
            emit(render_state(session))
        elif command == "/quit":
            emit("Not approved; nothing was written.")
            return 0
        elif command == "/approve":
            try:
                approval = approve(session, human_approved=True, out_dir=out_dir)
            except ApprovalRefused as exc:
                emit(f"Approve refused: {exc}")
                continue
            emit(
                f"Approved. Record appended to {approval.records_path}; "
                f"email draft saved to {approval.email_path}. Nothing was sent."
            )
            # The gate just appended this session's record as the last line.
            record = json.loads(approval.records_path.read_text(encoding="utf-8").splitlines()[-1])
            delivery = deliver(record, approval.email_path.read_text(encoding="utf-8"))
            if delivery.doc.status != "off":
                emit(f"Google Doc: {_step_text(delivery.doc)}. Gmail draft: {_step_text(delivery.email)}.")
            return 0
        elif command == "/message":
            if not text:
                emit("Usage: /message <the user's new message>")
                continue
            trace = Trace()
            session = handle_complaint(session, text, trace=trace, **models)
            emit(render_turn(session, trace, heading="New message in this thread"))
        elif command == "/replace":
            if not text:
                emit("Usage: /replace <the corrected complaint text>")
                continue
            _refine(session, REPLACE_PUSHBACK, emit, complaint=text, **models)
        elif command.startswith("/"):
            emit(f"Unknown command {command}. Type /help.")
        else:
            _refine(session, line.strip(), emit, **models)
        del line, text


def render_turn(session: Session, trace: Trace, *, heading: str) -> str:
    """The trace for this turn, then the session state."""
    started = [node for node in AGENT_NODES if trace.starts(node)]
    lines = [f"\n=== {heading}", "", "Trace"]
    lines.extend(f"  {line}" for line in trace.render().splitlines())
    if len(started) == len(AGENT_NODES):
        problems = trace.violations()
        verdict = "pass" if not problems else "FAIL: " + "; ".join(problems)
        lines.append(f"  parallel rule: {verdict}")
    lines.append(f"  agents fired: {', '.join([*started, 'orchestrator'])}")
    lines.append(render_state(session))
    return "\n".join(lines)


def render_state(session: Session) -> str:
    """Redacted complaint, three agent results, draft, routing, review, and the log."""
    facts, pattern, compliance = session.facts, session.pattern, session.compliance
    draft, review = session.draft, session.review
    if facts is None or pattern is None or compliance is None or draft is None or review is None:
        return "\n(no reviewed draft yet)"

    lines = ["", f"Complaint (redacted): {session.redacted_text}"]
    if session.pii_types:
        lines.append(f"  PII redacted at ingress: {', '.join(session.pii_types)}")

    lines += ["", "Agents"]
    if facts.status == "covered":
        lines.append(
            f"  facts       covered: {facts.scheme_id} / {facts.section_title}, "
            f"last checked {facts.last_checked}"
        )
    else:
        lines.append(f"  facts       not covered ({len(facts.searched)} schemes and sections searched)")
    lines.append(
        f"  pattern     {pattern.theme_id} is {pattern.signal}: {pattern.count} reviews "
        f"{pattern.window.start} to {pattern.window.end}, {pattern.recent_count} in the last 7 days"
    )
    flags = ", ".join(compliance.flags) if compliance.flags else "none"
    lines.append(f"  compliance  flags: {flags}")
    if session.advice_refusal:
        lines.append("  advice refusal is sticky for this thread")

    lines += ["", f"Draft ({draft.disposition})", f"  {draft.reply}"]
    if draft.disagreement:
        lines.append("  agents disagree: Facts has an answer, but Pattern shows the issue rising")

    note = draft.routing_note
    lines += ["", "Routing note (internal)", f"  {note.team}, {note.priority}: {note.why}"]

    lines += ["", f"Review: {review.status} (round {review.round})"]
    for failure in review.failures:
        lines.append(f"  {failure.check}: {failure.detail}")

    lines += ["", f"Refinements: {session.refinement_count} / {MAX_REFINEMENTS}"]
    for entry in session.agents_fired:
        lines.append(
            f"  round {entry.round} {entry.kind}: ran {', '.join(entry.ran)}; "
            f"skipped {', '.join(entry.skipped) or 'none'}"
        )
    lines.append("")
    lines.append(_next_steps(session))
    return "\n".join(lines)


def _refine(
    session: Session,
    pushback: str,
    emit: Emit,
    *,
    complaint: str | None = None,
    **models: Any,
) -> None:
    trace = Trace()
    try:
        refine(session, pushback, complaint=complaint, trace=trace, **models)
    except RefinementRefused as exc:
        emit(f"Refinement refused: {exc}")
        return
    del pushback, complaint
    emit(render_turn(session, trace, heading=f"Refinement {session.refinement_count}"))


def _next_steps(session: Session) -> str:
    if session.review is not None and session.review.status == "blocked":
        return "Blocked after the one rework: approve is not available. Push back to redraft."
    if not approvable(session):
        return "Not approvable yet."
    return "Approve writes a redacted record and an email draft. Nothing is sent."


def _prompt(session: Session) -> str:
    options = []
    if session.refinement_count < MAX_REFINEMENTS:
        options.append("pushback")
    if approvable(session):
        options.append("/approve")
    options += ["/message", "/help", "/quit"]
    return " | ".join(options)


def _step_text(step: Step) -> str:
    if step.status == "done":
        return "done"
    return f"failed ({step.error})"


def _read(read: Read, prompt: str) -> str | None:
    try:
        return read(prompt)
    except EOFError:
        return None


if __name__ == "__main__":
    sys.exit(main())
