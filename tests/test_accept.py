"""Phase 10 exit: the acceptance script passes offline and writes only approved records."""

import json
import os

import pytest

from support_reply import accept, llm
from support_reply.accept import AcceptanceFailure, main, real_complaints
from support_reply.fixtures import RAW_PAN, RAW_PHONE, REAL_COMPLAINT_COUNT
from support_reply.gate import EMAIL_DRAFTS_DIR, RECORDS_FILE


def test_the_acceptance_run_passes_offline_and_writes_only_approved_records(tmp_path, capsys):
    assert main(["--offline", "--out", str(tmp_path)]) == 0

    output = capsys.readouterr().out
    assert "PASS" in output
    records = [
        json.loads(line) for line in (tmp_path / RECORDS_FILE).read_text().splitlines()
    ]
    # The clean hit and the PII branch are the two approved sessions.
    assert len(records) == 2
    assert len(list((tmp_path / EMAIL_DRAFTS_DIR).iterdir())) == 2
    written = (tmp_path / RECORDS_FILE).read_text()
    assert RAW_PAN not in written and RAW_PHONE not in written


def test_the_run_prints_review_ids_and_never_review_text(tmp_path, capsys):
    main(["--offline", "--out", str(tmp_path)])

    output = capsys.readouterr().out
    for review_id, text in real_complaints():
        assert review_id in output
        assert text not in output


def test_real_complaints_are_the_first_twenty_with_text_in_file_order():
    picked = real_complaints()

    assert len(picked) == REAL_COMPLAINT_COUNT
    assert all(text.strip() for _, text in picked)
    assert len({review_id for review_id, _ in picked}) == REAL_COMPLAINT_COUNT


def test_a_miss_exits_non_zero_and_names_the_check(tmp_path, monkeypatch, capsys):
    def broken(result, out_dir, models):
        raise AcceptanceFailure("clean_hit: citation None")

    monkeypatch.setattr(accept, "check_branches", broken)

    assert main(["--offline", "--out", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "FAIL: clean_hit: citation None" in output
    # The section that ran before the miss is still reported.
    assert real_complaints()[0][0] in output


def test_offline_makes_no_model_call_and_leaves_the_keys_alone(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "set")
    monkeypatch.setenv("GEMINI_API_KEY", "set")
    calls = []

    def counting():
        class Counting:
            def classify(self, **kwargs):
                calls.append(kwargs["task"])
                raise RuntimeError("must not be called")

        return Counting()

    monkeypatch.setattr(llm, "default_classifier", counting)
    monkeypatch.setattr(llm, "default_review_classifier", counting)

    assert main(["--offline", "--out", str(tmp_path)]) == 0

    assert calls == []
    assert os.environ["GROQ_API_KEY"] == "set" and os.environ["GEMINI_API_KEY"] == "set"


def test_without_out_the_run_writes_to_a_temporary_directory(monkeypatch, tmp_path):
    real = tmp_path / "real-out"
    monkeypatch.setenv("REPLY_DESK_OUT_DIR", str(real))

    result = accept.report(offline=True)

    assert result["status"] == "pass"
    assert not real.exists()
    assert [branch["name"] for branch in result["branches"] if branch["approved"]] == [
        "clean_hit",
        "pii",
    ]


def test_an_uncited_covered_reply_is_a_miss():
    from dataclasses import replace

    from support_reply.contracts import Session
    from support_reply.fixtures import CLEAN_HIT
    from support_reply.graph import handle_complaint

    session = handle_complaint(Session(), CLEAN_HIT)
    session.draft = replace(session.draft, reply="Exit load of 1% if redeemed within 1 year.")

    with pytest.raises(AcceptanceFailure, match="lacks the source_url"):
        accept._require_cited_or_factless(session, "probe")
