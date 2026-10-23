"""The session CLI: a human drives one thread, and the trace prints as a log."""

import json
from pathlib import Path

from support_reply.cli import HELP, main, run_session
from support_reply.fixtures import ADVICE_THREAD, CLEAN_HIT, PII_COMPLAINT, RAW_PAN, RAW_PHONE
from support_reply.gate import EMAIL_DRAFTS_DIR, RECORDS_FILE


class FlagsTheSource:
    def classify(self, **_):
        return {"failures": [{"check": "advice", "span": "Source"}]}


def _drive(tmp_path, lines, **kwargs):
    """Run the CLI on scripted input. Returns the printed output and the prompts shown."""
    feed = iter(lines)
    prompts, printed = [], []

    def read(prompt):
        prompts.append(prompt)
        try:
            return next(feed)
        except StopIteration:
            raise EOFError from None

    code = run_session(out_dir=tmp_path, read=read, emit=printed.append, **kwargs)
    assert code == 0
    return "\n".join(printed), prompts


def _files(out):
    return sorted(str(p.relative_to(out)) for p in Path(out).rglob("*") if p.is_file())


def test_a_complaint_a_pushback_and_approve_write_one_record(tmp_path):
    output, prompts = _drive(tmp_path, [CLEAN_HIT, "Shorter", "/approve"])

    assert "parallel rule: pass" in output
    assert "agents fired: facts, pattern, compliance, orchestrator" in output
    assert "=== Refinement 1" in output and "agents fired: orchestrator" in output
    assert "round 1 refinement: ran orchestrator; skipped facts, pattern, compliance" in output
    assert "Approved." in output and "Nothing was sent." in output
    assert len(_files(tmp_path / EMAIL_DRAFTS_DIR)) == 1
    [record] = [json.loads(l) for l in (tmp_path / RECORDS_FILE).read_text().splitlines()]
    assert record["agents_fired"][0]["ran"] == ["orchestrator"]
    assert all("/approve" in prompt for prompt in prompts[1:])


def test_a_different_scheme_reruns_facts_only(tmp_path):
    output, _ = _drive(tmp_path, [CLEAN_HIT, "They're asking about HDFC Gold ETF Fund of Fund"])

    assert "agents fired: facts, orchestrator" in output
    assert "covered: gold_fof / Exit load" in output


def test_the_raw_complaint_is_never_printed(tmp_path):
    output, _ = _drive(tmp_path, [PII_COMPLAINT, "/show", "/approve"])

    assert "[PAN]" in output and "[PHONE]" in output
    assert RAW_PAN not in output and RAW_PHONE not in output
    assert RAW_PAN not in (tmp_path / RECORDS_FILE).read_text()


def test_a_blocked_draft_hides_approve_and_refuses_it(tmp_path):
    output, prompts = _drive(
        tmp_path, [CLEAN_HIT, "/approve"], review_classifier=FlagsTheSource()
    )

    assert "Review: blocked (round 2)" in output
    assert "approve is not available" in output
    assert "/approve" not in prompts[1]
    assert "Approve refused" in output
    assert _files(tmp_path) == []


def test_the_sixth_pushback_is_refused(tmp_path):
    output, prompts = _drive(tmp_path, [CLEAN_HIT, *["Shorter"] * 6])

    assert "=== Refinement 5" in output and "=== Refinement 6" not in output
    assert "Refinement refused: refinement limit reached" in output
    assert "pushback" not in prompts[-1]


def test_messages_in_one_thread_stay_refused(tmp_path):
    first, *later = ADVICE_THREAD
    output, _ = _drive(tmp_path, [first, *(f"/message {ask}" for ask in later)])

    assert output.count("Draft (refuse)") == len(ADVICE_THREAD)
    assert "advice refusal is sticky for this thread" in output


def test_replace_reruns_every_agent_as_a_refinement(tmp_path):
    output, _ = _drive(tmp_path, [CLEAN_HIT, "/replace What is the benchmark of HDFC Mid Cap Fund?"])

    assert "=== Refinement 1" in output
    assert "agents fired: facts, pattern, compliance, orchestrator" in output
    assert "covered: mid_cap / Benchmark" in output


def test_quit_end_of_input_and_unknown_commands_write_nothing(tmp_path):
    output, _ = _drive(tmp_path, [CLEAN_HIT, "/help", "/nope", "/message", "/quit"])
    assert HELP in output
    assert "Unknown command /nope" in output
    assert "Usage: /message" in output
    assert "Not approved; nothing was written." in output

    output, _ = _drive(tmp_path, [])
    assert "No complaint" in output
    assert _files(tmp_path) == []


def test_main_offline_runs_on_stdin(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GROQ_API_KEY", "set")
    inputs = iter([CLEAN_HIT, "/quit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    assert main(["--offline", "--out", str(tmp_path)]) == 0
    assert "parallel rule: pass" in capsys.readouterr().out
