"""Deployment Phase 1 exit: model switches, output directory, provenance, and the acceptance report."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from support_reply import accept, llm
from support_reply.contracts import Session
from support_reply.fixtures import CLEAN_HIT, PII_COMPLAINT, RAW_PAN, RAW_PHONE
from support_reply.gate import RECORDS_FILE, approve, default_out_dir
from support_reply.graph import complaint_turn, handle_complaint
from support_reply.llm import CUES, CUES_ONLY, MODEL, classify_or_none, models_mode
from support_reply.session import refine_turn

ALL_NODES = ("facts", "pattern", "compliance", "reviewer")
ANSWERS = {
    "facts": {"scheme_id": "large_cap", "section_title": "Exit load"},
    "pattern": {"theme_id": "fees_brokerage"},
    "compliance": {"flags": []},
    "review": {"failures": []},
}


class Counting:
    """Answers each task with a fixed JSON object and counts the calls. Thread-safe."""

    def __init__(self, fail_after=None):
        self.calls = []
        self.fail_after = fail_after
        self._lock = threading.Lock()

    def classify(self, **kwargs):
        with self._lock:
            self.calls.append(kwargs["task"])
            count = len(self.calls)
        if self.fail_after is not None and count > self.fail_after:
            raise RuntimeError("quota")
        return ANSWERS[kwargs["task"]]


@pytest.fixture
def defaults(monkeypatch):
    """Point the env-configured defaults at counting fakes, with keys "set"."""
    monkeypatch.setenv("GROQ_API_KEY", "set")
    monkeypatch.setenv("GEMINI_API_KEY", "set")
    agents, reviewer = Counting(), Counting()
    monkeypatch.setattr(llm, "default_classifier", lambda: agents)
    monkeypatch.setattr(llm, "default_review_classifier", lambda: reviewer)
    return agents, reviewer


# --- 1. Model switches --------------------------------------------------------------------


def test_models_off_makes_zero_model_calls_with_keys_set(defaults, monkeypatch):
    agents, reviewer = defaults
    monkeypatch.setenv("REPLY_DESK_MODELS", "off")

    turn = complaint_turn(Session(), CLEAN_HIT)

    assert agents.calls == [] and reviewer.calls == []
    assert turn.provenance == dict.fromkeys(ALL_NODES, CUES)


def test_models_auto_uses_the_configured_models(defaults, monkeypatch):
    agents, reviewer = defaults
    monkeypatch.setenv("REPLY_DESK_MODELS", "auto")

    turn = complaint_turn(Session(), CLEAN_HIT)

    assert sorted(agents.calls) == ["compliance", "facts", "pattern"]
    assert reviewer.calls == ["review"]
    assert turn.provenance == dict.fromkeys(ALL_NODES, MODEL)


def test_an_unknown_models_mode_fails_loudly(monkeypatch):
    monkeypatch.setenv("REPLY_DESK_MODELS", "of")
    with pytest.raises(ValueError, match="REPLY_DESK_MODELS"):
        models_mode()
    monkeypatch.setenv("REPLY_DESK_MODELS", " OFF ")
    assert models_mode() == "off"
    monkeypatch.delenv("REPLY_DESK_MODELS")
    assert models_mode() == "auto"


def test_cues_only_skips_the_call_without_a_warning(caplog):
    caplog.set_level("WARNING")
    assert classify_or_none(
        task="facts", redacted_text="x", allowed={"scheme_id": ()}, classifier=CUES_ONLY
    ) is None
    assert caplog.records == []
    with pytest.raises(RuntimeError, match="sentinel"):
        CUES_ONLY.classify(task="facts", redacted_text="x", allowed={})


def test_a_cues_only_turn_and_a_model_turn_in_parallel_do_not_affect_each_other():
    agents, reviewer = Counting(), Counting()
    barrier = threading.Barrier(2)

    def offline():
        barrier.wait()
        return complaint_turn(
            Session(), CLEAN_HIT, classifier=CUES_ONLY, review_classifier=CUES_ONLY
        )

    def online():
        barrier.wait()
        return complaint_turn(Session(), CLEAN_HIT, classifier=agents, review_classifier=reviewer)

    for _ in range(5):
        agents.calls.clear()
        reviewer.calls.clear()
        with ThreadPoolExecutor(max_workers=2) as pool:
            off_turn, on_turn = pool.submit(offline), pool.submit(online)
            off_turn, on_turn = off_turn.result(), on_turn.result()
        assert off_turn.provenance == dict.fromkeys(ALL_NODES, CUES)
        assert on_turn.provenance == dict.fromkeys(ALL_NODES, MODEL)
        assert sorted(agents.calls) == ["compliance", "facts", "pattern"]
        assert reviewer.calls == ["review"]


# --- 2. Output directory ------------------------------------------------------------------


def test_the_out_dir_env_redirects_approve(monkeypatch, tmp_path):
    target = tmp_path / "volume"
    monkeypatch.setenv("REPLY_DESK_OUT_DIR", str(target))
    assert default_out_dir() == target

    approve(handle_complaint(Session(), CLEAN_HIT), human_approved=True)

    assert len((target / RECORDS_FILE).read_text().splitlines()) == 1


def test_a_blank_out_dir_env_falls_back_to_the_repo_out(monkeypatch):
    monkeypatch.setenv("REPLY_DESK_OUT_DIR", "  ")
    assert default_out_dir().name == "out"
    assert (default_out_dir().parent / "data").is_dir()


# --- 3. Provenance ------------------------------------------------------------------------


def test_provenance_is_cues_for_every_node_offline():
    turn = complaint_turn(Session(), CLEAN_HIT)
    assert turn.provenance == dict.fromkeys(ALL_NODES, CUES)
    # The contracts are unchanged: the session dict carries no provenance.
    assert "provenance" not in turn.session.to_dict()


def test_provenance_is_model_when_fakes_answer():
    agents, reviewer = Counting(), Counting()
    turn = complaint_turn(Session(), CLEAN_HIT, classifier=agents, review_classifier=reviewer)
    assert turn.provenance == dict.fromkeys(ALL_NODES, MODEL)
    assert list(turn.provenance) == list(ALL_NODES)


def test_a_model_that_fails_mid_turn_shows_up_as_cues_for_that_node():
    # The first two agent calls answer; the third falls back to its cue table.
    agents = Counting(fail_after=2)
    turn = complaint_turn(Session(), CLEAN_HIT, classifier=agents, review_classifier=CUES_ONLY)
    agent_sources = [turn.provenance[node] for node in ("facts", "pattern", "compliance")]
    assert sorted(agent_sources) == [CUES, MODEL, MODEL]
    assert turn.provenance["reviewer"] == CUES


def test_a_refinement_reports_only_the_nodes_that_ran():
    session = handle_complaint(Session(), CLEAN_HIT)

    shorter = refine_turn(session, "Shorter")
    assert shorter.provenance == {"reviewer": CUES}

    gold = refine_turn(session, "They're asking about HDFC Gold ETF Fund of Fund")
    assert gold.provenance == {"facts": CUES, "reviewer": CUES}
    assert gold.session is session and session.refinement_count == 2


def test_a_reviewer_round_without_the_model_marks_the_whole_review_cues():
    class FlagsThenFails:
        """Round 1: a grounded advice finding, so the draft goes to a rewrite. Round 2: down."""

        def __init__(self):
            self.rounds = 0

        def classify(self, **_):
            self.rounds += 1
            if self.rounds == 1:
                return {"failures": [{"check": "advice", "span": "Exit load"}]}
            raise RuntimeError("quota")

    reviewer = FlagsThenFails()
    turn = complaint_turn(Session(), CLEAN_HIT, review_classifier=reviewer)

    assert reviewer.rounds == 2
    assert turn.provenance["reviewer"] == CUES


# --- 4. Acceptance as data ----------------------------------------------------------------


def test_the_report_is_complete_json_and_holds_no_review_text_or_raw_pii():
    result = accept.report(offline=True)

    assert result["status"] == "pass" and result["failure"] is None
    assert result["mode"] == "cues"
    assert len(result["real_complaints"]) == 20
    assert [b["name"] for b in result["branches"]] == [
        "clean_hit",
        "corpus_miss",
        "recurring_theme",
        "pii",
    ]
    assert len(result["advice_thread"]) == 6
    assert all(turn["disposition"] == "refuse" for turn in result["advice_thread"])
    assert set(result["caps"]) == {"blocked", "refinement_cap"}
    for branch in result["branches"]:
        assert branch["provenance"] == dict.fromkeys(ALL_NODES, CUES)
        assert [e["kind"] for e in branch["trace"]].count("start") >= 6

    dumped = json.dumps(result)
    assert RAW_PAN not in dumped and RAW_PHONE not in dumped
    for _, text in accept.real_complaints():
        assert text not in dumped


def test_the_printed_run_is_the_rendered_report(tmp_path, capsys):
    assert accept.main(["--offline", "--out", str(tmp_path)]) == 0
    printed = capsys.readouterr().out

    rendered = accept.render(accept.report(offline=True))

    # Timings and generated ids differ between runs; everything else is the same text.
    def stable(text):
        return [
            line
            for line in text.splitlines()
            if "ms " not in line and "email draft" not in line
        ]

    assert stable(printed.rstrip("\n")) == stable(rendered)
    assert "PASS: every acceptance check held" in printed


def test_the_pii_branch_in_the_report_keeps_tokens_only():
    result = accept.report(offline=True)
    [pii] = [b for b in result["branches"] if b["name"] == "pii"]
    assert "[PAN]" in pii["redacted_text"] and "[PHONE]" in pii["redacted_text"]
    assert PII_COMPLAINT not in json.dumps(pii)
