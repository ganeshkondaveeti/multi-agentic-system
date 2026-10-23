"""Deployment Phase 2 exit: the routes, through FastAPI's TestClient with models off."""

import json

import pytest

from support_reply.api.limits import RateLimiter
from support_reply.api.store import SessionNotFound, SessionStore, StoreFull
from support_reply.contracts import Session
from support_reply.fixtures import ADVICE_THREAD, BRANCHES, CLEAN_HIT, LARGE_CAP_URL
from support_reply.gate import EMAIL_DRAFTS_DIR, RECORDS_FILE
from support_reply.llm import CUES_ONLY

GOLD_URL = "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth"
ALL_CUES = {"facts": "cues", "pattern": "cues", "compliance": "cues", "reviewer": "cues"}


class FlagsTheSource:
    def classify(self, **_):
        return {"failures": [{"check": "advice", "span": "Source"}]}


def _start(client, complaint=CLEAN_HIT):
    response = client.post("/api/sessions", json={"complaint": complaint})
    assert response.status_code == 200, response.text
    return response.json()


def _refine(client, session_id, pushback):
    return client.post(f"/api/sessions/{session_id}/refine", json={"pushback": pushback})


# --- meta -------------------------------------------------------------------------------


def test_health_reports_models_corpus_and_window(api):
    body = api().get("/api/health").json()

    assert body == {
        "status": "ok",
        "environment": "local",
        "models": {
            "mode": "off",
            "agents": "cues",
            "reviewer": "code",
            "agent_model": None,
            "reviewer_model": None,
        },
        "corpus": {"last_checked": "25-Jun-2026", "schemes": 5},
        "review_window": {"start": "2026-04-12", "end": "2026-07-04"},
        "access_code_required": False,
        "mcp": {"enabled": False, "doc_configured": False},
    }


def test_health_names_the_models_when_keys_are_set(api, monkeypatch):
    client = api()
    monkeypatch.setenv("REPLY_DESK_MODELS", "auto")
    monkeypatch.setenv("GROQ_API_KEY", "set")
    monkeypatch.setenv("GEMINI_API_KEY", "set")

    models = client.get("/api/health").json()["models"]

    assert models["mode"] == "auto"
    assert (models["agents"], models["reviewer"]) == ("groq", "gemini")
    assert models["agent_model"] and models["reviewer_model"]


def test_docs_and_openapi_are_served(api):
    client = api()
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/api/health",
        "/api/sessions",
        "/api/sessions/{session_id}",
        "/api/sessions/{session_id}/refine",
        "/api/sessions/{session_id}/replace",
        "/api/sessions/{session_id}/messages",
        "/api/sessions/{session_id}/approve",
        "/api/records",
        "/api/records/{session_id}/email",
        "/api/acceptance",
        "/api/acceptance/run",
    } <= set(paths)
    assert not any("send" in path for path in paths)


# --- the four branches ------------------------------------------------------------------


def test_clean_hit(api):
    view = _start(api(), BRANCHES["clean_hit"])
    session = view["session"]

    assert session["facts"]["status"] == "covered" and session["facts"]["scheme_id"] == "large_cap"
    assert session["draft"]["citation"] == LARGE_CAP_URL and LARGE_CAP_URL in session["draft"]["reply"]
    assert session["draft"]["disposition"] == "escalate"
    assert session["review"]["status"] == "pass"
    assert view["approvable"] is True and view["approved"] is None
    assert view["refinements_left"] == 5
    assert view["provenance"] == ALL_CUES
    assert view["turn"] == {
        "kind": "complaint",
        "ran": ["facts", "pattern", "compliance", "orchestrator"],
        "provenance": ALL_CUES,
    }
    kinds = [(event["kind"], event["node"]) for event in view["trace"]]
    starts = [i for i, (kind, node) in enumerate(kinds) if kind == "start" and node in ALL_CUES]
    returns = [i for i, (kind, node) in enumerate(kinds) if kind == "return" and node in ("facts", "pattern", "compliance")]
    assert max(starts[:3]) < min(returns)


def test_corpus_miss(api):
    session = _start(api(), BRANCHES["corpus_miss"])["session"]

    assert session["facts"]["status"] == "not_covered" and session["facts"]["searched"]
    assert session["draft"]["disposition"] == "handoff"
    assert "http" not in session["draft"]["reply"]


def test_recurring_theme(api):
    session = _start(api(), BRANCHES["recurring_theme"])["session"]

    assert session["pattern"]["theme_id"] == "fees_brokerage"
    assert session["pattern"]["count"] == 136
    assert session["pattern"]["signal"] in ("recurring", "rising")
    assert "stays open" in session["draft"]["routing_note"]["why"]


def test_pii_branch_returns_tokens_only(api):
    view = _start(api(), BRANCHES["pii"])

    assert "[PAN]" in view["session"]["redacted_text"]
    assert "[PHONE]" in view["session"]["redacted_text"]
    assert view["session"]["pii_types"] == ["PAN", "PHONE"]
    assert "pii" in view["session"]["compliance"]["flags"]
    assert view["session"]["review"]["status"] == "pass"


# --- refinements ------------------------------------------------------------------------


def test_shorter_different_scheme_and_fee_issue_rerun_only_their_agents(api):
    client = api()
    session_id = _start(client)["session_id"]

    shorter = _refine(client, session_id, "Shorter").json()
    assert shorter["turn"]["kind"] == "refinement"
    assert shorter["turn"]["ran"] == ["orchestrator"]
    assert shorter["session"]["agents_fired"][-1] == {
        "round": 1,
        "kind": "refinement",
        "ran": ["orchestrator"],
        "skipped": ["facts", "pattern", "compliance"],
    }

    gold = _refine(client, session_id, "They're asking about HDFC Gold ETF Fund of Fund").json()
    assert gold["turn"]["ran"] == ["facts", "orchestrator"]
    assert gold["session"]["draft"]["citation"] == GOLD_URL
    assert gold["session"]["agents_fired"][-1]["skipped"] == ["pattern", "compliance"]

    fee = _refine(client, session_id, "Check if this is the fee issue from last week").json()
    assert fee["turn"]["ran"] == ["pattern", "orchestrator"]
    assert fee["session"]["agents_fired"][-1]["ran"] == ["pattern", "orchestrator"]
    assert fee["refinements_left"] == 2
    # Provenance keeps the last known source for every node.
    assert fee["provenance"] == ALL_CUES


def test_the_sixth_refine_is_409_and_the_draft_stands(api):
    client = api()
    session_id = _start(client)["session_id"]
    for _ in range(5):
        assert _refine(client, session_id, "Shorter").status_code == 200
    before = client.get(f"/api/sessions/{session_id}").json()

    sixth = _refine(client, session_id, "Shorter")

    assert sixth.status_code == 409
    assert sixth.json()["error"] == "refinement_refused"
    after = client.get(f"/api/sessions/{session_id}").json()
    assert after["session"] == before["session"]
    assert after["refinements_left"] == 0
    # A replace is a refinement too.
    replace = client.post(f"/api/sessions/{session_id}/replace", json={"complaint": CLEAN_HIT})
    assert replace.status_code == 409


def test_replace_reruns_every_agent_and_counts_as_a_refinement(api):
    client = api()
    session_id = _start(client)["session_id"]

    view = client.post(
        f"/api/sessions/{session_id}/replace",
        json={"complaint": "What is the benchmark of HDFC Mid Cap Fund?"},
    ).json()

    assert view["turn"]["kind"] == "replace"
    assert view["turn"]["ran"] == ["facts", "pattern", "compliance", "orchestrator"]
    assert view["session"]["facts"]["scheme_id"] == "mid_cap"
    assert view["session"]["refinement_count"] == 1


def test_the_advice_thread_stays_refused_through_messages(api):
    client = api()
    first, *later = ADVICE_THREAD
    view = _start(client, first)
    assert view["session"]["draft"]["disposition"] == "refuse"

    for ask in later:
        response = client.post(f"/api/sessions/{view['session_id']}/messages", json={"message": ask})
        assert response.status_code == 200
        view = response.json()
        assert view["turn"]["kind"] == "message"
        assert view["session"]["draft"]["disposition"] == "refuse"
        assert view["session"]["advice_refusal"] is True
        assert view["session"]["draft"]["citation"] is None


# --- approve and records ----------------------------------------------------------------


def test_approve_writes_to_the_out_dir_and_the_records_list_it(api):
    client = api()
    view = _start(client)
    session_id = view["session_id"]

    approved = client.post(f"/api/sessions/{session_id}/approve")

    assert approved.status_code == 200
    body = approved.json()
    assert body["session_id"] == session_id
    assert body["email_file"] == f"{session_id}.txt"
    assert body["record"]["reply"] == view["session"]["draft"]["reply"]
    assert (client.out_dir / RECORDS_FILE).is_file()
    assert (client.out_dir / EMAIL_DRAFTS_DIR / f"{session_id}.txt").is_file()

    records = client.get("/api/records").json()
    assert [record["session_id"] for record in records] == [session_id]
    email = client.get(f"/api/records/{session_id}/email").json()
    assert email == {"session_id": session_id, "text": view["session"]["draft"]["reply"] + "\n"}

    after = client.get(f"/api/sessions/{session_id}").json()
    assert after["approvable"] is False
    assert after["approved"]["email_file"] == f"{session_id}.txt"


def test_an_approved_session_is_closed(api):
    client = api()
    session_id = _start(client)["session_id"]
    client.post(f"/api/sessions/{session_id}/approve")

    again = client.post(f"/api/sessions/{session_id}/approve")
    refine = _refine(client, session_id, "Shorter")
    message = client.post(f"/api/sessions/{session_id}/messages", json={"message": "hello"})

    assert again.status_code == refine.status_code == message.status_code == 409
    assert {again.json()["error"], refine.json()["error"], message.json()["error"]} == {"already_approved"}
    assert len(client.get("/api/records").json()) == 1


def test_a_blocked_session_cannot_be_approved_and_writes_nothing(api):
    client = api(models=lambda: {"classifier": CUES_ONLY, "review_classifier": FlagsTheSource()})
    view = _start(client)
    assert view["session"]["review"]["status"] == "blocked"
    assert view["approvable"] is False

    response = client.post(f"/api/sessions/{view['session_id']}/approve")

    assert response.status_code == 409
    assert response.json()["error"] == "not_approvable"
    assert "blocked" in response.json()["message"]
    assert not client.out_dir.exists()


def test_records_filter_by_disposition_priority_and_team(api):
    client = api()
    escalated = _start(client, BRANCHES["clean_hit"])["session_id"]
    handed_off = _start(client, BRANCHES["corpus_miss"])["session_id"]
    for session_id in (escalated, handed_off):
        assert client.post(f"/api/sessions/{session_id}/approve").status_code == 200

    def ids(**params):
        return [r["session_id"] for r in client.get("/api/records", params=params).json()]

    assert set(ids()) == {escalated, handed_off}
    assert ids(disposition="handoff") == [handed_off]
    assert ids(priority="P2") == [escalated]
    assert ids(team="Fees and mutual fund ops") == [escalated]
    assert len(ids(limit=1)) == 1
    assert client.get("/api/records", params={"disposition": "send"}).status_code == 400


def test_unknown_or_unsafe_ids_are_404(api):
    client = api()
    for session_id in ("nope", "a" * 32):
        assert client.get(f"/api/sessions/{session_id}").status_code == 404
        assert _refine(client, session_id, "Shorter").status_code == 404
        assert client.post(f"/api/sessions/{session_id}/approve").status_code == 404
        assert client.get(f"/api/records/{session_id}/email").status_code == 404
    assert client.get("/api/records/..%2Fsecrets/email").status_code == 404


def test_sessions_list_newest_first_with_redacted_excerpts(api):
    client = api()
    first = _start(client, BRANCHES["pii"])["session_id"]
    second = _start(client, BRANCHES["corpus_miss"])["session_id"]
    _refine(client, first, "Shorter")

    summaries = client.get("/api/sessions").json()

    assert [s["session_id"] for s in summaries] == [first, second]
    assert "[PAN]" in summaries[0]["excerpt"]
    assert summaries[0]["refinement_count"] == 1
    assert summaries[1]["disposition"] == "handoff" and summaries[1]["priority"] == "P1"


def test_empty_and_too_long_text_is_400(api):
    client = api()
    for body in ({"complaint": ""}, {"complaint": "   "}, {"complaint": "x" * 2001}, {}):
        response = client.post("/api/sessions", json=body)
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_request"


# --- acceptance -------------------------------------------------------------------------


def test_acceptance_runs_cues_only_and_keeps_the_last_report(api):
    client = api()
    assert client.get("/api/acceptance").status_code == 404

    report = client.post("/api/acceptance/run").json()

    assert report["status"] == "pass" and report["mode"] == "cues"
    assert report["ran_at"]
    assert len(report["real_complaints"]) == 20 and len(report["branches"]) == 4
    assert client.get("/api/acceptance").json() == report
    # Its approvals went to a temporary directory, not the configured out dir.
    assert not client.out_dir.exists()


def test_a_second_acceptance_run_while_one_runs_is_429(api):
    client = api()
    runner = client.app.state.acceptance
    runner._lock.acquire()
    try:
        response = client.post("/api/acceptance/run")
    finally:
        runner._lock.release()
    assert response.status_code == 429
    assert response.json()["error"] == "acceptance_running"


# --- store and limiter units ------------------------------------------------------------


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_store_expires_idle_sessions_and_evicts_the_oldest_when_full():
    clock = Clock()
    store = SessionStore(ttl_seconds=60, max_sessions=2, clock=clock)
    first = store.add(Session())
    clock.now += 10
    second = store.add(Session())
    clock.now += 10

    third = store.add(Session())

    ids = {entry.session_id for entry in store.entries()}
    assert ids == {second.session_id, third.session_id}
    with pytest.raises(SessionNotFound):
        with store.locked(first.session_id):
            pass

    clock.now += 61
    assert store.entries() == []


def test_store_never_evicts_a_session_in_use():
    store = SessionStore(ttl_seconds=60, max_sessions=1)
    entry = store.add(Session())
    with store.locked(entry.session_id):
        assert store.has_room() is False
        with pytest.raises(StoreFull):
            store.add(Session())
    assert store.has_room() is True


def test_rate_limiter_refills_over_a_minute():
    clock = Clock()
    limiter = RateLimiter(12, clock=clock)

    assert all(limiter.allow("a") for _ in range(12))
    assert limiter.allow("a") is False
    assert limiter.allow("b") is True
    clock.now += 5  # one token per five seconds
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False


def test_session_views_are_json_round_trippable(api):
    view = _start(api())
    assert json.loads(json.dumps(view)) == view
