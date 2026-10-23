"""Phase 9 exit: approve appends one redacted record and writes one email draft. No send."""

import ast
import json
from pathlib import Path

import pytest

import support_reply.gate as gate_module
from support_reply.contracts import Session
from support_reply.fixtures import CLEAN_HIT, LARGE_CAP_URL, PII_COMPLAINT, RAW_PAN, RAW_PHONE
from support_reply.gate import (
    EMAIL_DRAFTS_DIR,
    RECORDS_FILE,
    Approval,
    ApprovalRefused,
    approve,
    new_session_id,
)
from support_reply.graph import handle_complaint
from support_reply.ingress import scan
from support_reply.session import refine


class FlagsTheSource:
    """Review model that quotes `Source` as advice on every round, so the draft ends blocked."""

    def classify(self, **_):
        return {"failures": [{"check": "advice", "span": "Source"}]}


def _files(out):
    return sorted(str(path.relative_to(out)) for path in Path(out).rglob("*") if path.is_file())


def _records(out):
    return [json.loads(line) for line in (out / RECORDS_FILE).read_text().splitlines()]


def test_a_passed_large_cap_draft_appends_one_record_and_one_email_file(tmp_path):
    session = handle_complaint(Session(), CLEAN_HIT)

    approval = approve(session, human_approved=True, session_id="s1", out_dir=tmp_path)

    assert approval == Approval(
        session_id="s1",
        records_path=tmp_path / RECORDS_FILE,
        email_path=tmp_path / EMAIL_DRAFTS_DIR / "s1.txt",
    )
    assert _files(tmp_path) == [f"{EMAIL_DRAFTS_DIR}/s1.txt", RECORDS_FILE]
    [record] = _records(tmp_path)
    assert set(record) == {
        "session_id",
        "approved_at",
        "redacted_text",
        "pii_types",
        "disposition",
        "reply",
        "citation",
        "last_checked",
        "routing_note",
        "pattern_signal",
        "agents_fired",
    }
    assert record["session_id"] == "s1"
    assert record["redacted_text"] == CLEAN_HIT
    assert record["disposition"] == session.draft.disposition
    assert record["reply"] == session.draft.reply
    assert record["citation"] == LARGE_CAP_URL
    assert record["last_checked"] == "25-Jun-2026"
    assert record["routing_note"] == session.draft.routing_note.to_dict()
    assert record["pattern_signal"] == session.pattern.signal


def test_the_email_file_is_the_reply_text(tmp_path):
    session = handle_complaint(Session(), CLEAN_HIT)

    approval = approve(session, human_approved=True, out_dir=tmp_path)

    assert approval.email_path.read_text(encoding="utf-8") == session.draft.reply + "\n"
    assert LARGE_CAP_URL in approval.email_path.read_text(encoding="utf-8")


def test_a_second_approve_appends_a_second_record(tmp_path):
    approve(handle_complaint(Session(), CLEAN_HIT), human_approved=True, out_dir=tmp_path)
    approve(handle_complaint(Session(), CLEAN_HIT), human_approved=True, out_dir=tmp_path)

    assert len(_records(tmp_path)) == 2
    assert len(list((tmp_path / EMAIL_DRAFTS_DIR).iterdir())) == 2


def test_the_record_keeps_the_pan_token_and_never_the_pan(tmp_path):
    session = handle_complaint(Session(), PII_COMPLAINT)

    approval = approve(session, human_approved=True, out_dir=tmp_path)

    written = (tmp_path / RECORDS_FILE).read_text(encoding="utf-8")
    assert "[PAN]" in written and "[PHONE]" in written
    assert RAW_PAN not in written and RAW_PHONE not in written
    assert RAW_PAN not in approval.email_path.read_text(encoding="utf-8")
    assert _records(tmp_path)[0]["pii_types"] == ["PAN", "PHONE"]


def test_the_record_carries_agents_fired(tmp_path):
    session = handle_complaint(Session(), CLEAN_HIT)
    refine(session, "Shorter")

    approve(session, human_approved=True, out_dir=tmp_path)

    [record] = _records(tmp_path)
    assert record["agents_fired"] == [
        {
            "round": 1,
            "kind": "refinement",
            "ran": ["orchestrator"],
            "skipped": ["facts", "pattern", "compliance"],
        }
    ]


def test_a_blocked_session_creates_neither_file(tmp_path):
    session = handle_complaint(Session(), CLEAN_HIT, review_classifier=FlagsTheSource())
    assert session.review.status == "blocked"

    with pytest.raises(ApprovalRefused, match="blocked"):
        approve(session, human_approved=True, out_dir=tmp_path)

    assert _files(tmp_path) == []


def test_approve_without_the_human_flag_writes_nothing(tmp_path):
    session = handle_complaint(Session(), CLEAN_HIT)

    with pytest.raises(ApprovalRefused, match="human-approve"):
        approve(session, human_approved=False, out_dir=tmp_path)
    with pytest.raises(TypeError):
        approve(session, human_approved="yes", out_dir=tmp_path)

    assert _files(tmp_path) == []


def test_an_unreviewed_session_is_refused(tmp_path):
    with pytest.raises(ApprovalRefused, match="no reviewed draft"):
        approve(Session(), human_approved=True, out_dir=tmp_path)
    assert _files(tmp_path) == []


def test_the_record_writer_refuses_a_raw_value_and_writes_nothing(tmp_path):
    session = handle_complaint(Session(), CLEAN_HIT)
    # Something upstream stored a raw value. The writer is the last line.
    session.redacted_text = f"{CLEAN_HIT} PAN {RAW_PAN}"

    with pytest.raises(ApprovalRefused, match="raw PAN"):
        approve(session, human_approved=True, out_dir=tmp_path)

    assert _files(tmp_path) == []


@pytest.mark.parametrize("bad", ["", "../escape", "a/b", "a.txt", "x" * 65, 7])
def test_a_session_id_must_be_a_plain_token(tmp_path, bad):
    session = handle_complaint(Session(), CLEAN_HIT)

    with pytest.raises(ValueError, match="session_id"):
        approve(session, human_approved=True, session_id=bad, out_dir=tmp_path)

    assert _files(tmp_path) == []


def test_an_existing_email_draft_is_never_overwritten(tmp_path):
    session = handle_complaint(Session(), CLEAN_HIT)
    approve(session, human_approved=True, session_id="same", out_dir=tmp_path)

    with pytest.raises(ApprovalRefused, match="already"):
        approve(session, human_approved=True, session_id="same", out_dir=tmp_path)

    assert len(_records(tmp_path)) == 1


def test_generated_session_ids_never_read_as_pii():
    for _ in range(500):
        assert scan(new_session_id()).pii_types == ()


def test_the_gate_has_no_way_to_send():
    tree = ast.parse(Path(gate_module.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"smtplib", "email", "requests", "httpx", "urllib", "socket"}
    assert not [name for name in dir(gate_module) if "send" in name.lower()]
