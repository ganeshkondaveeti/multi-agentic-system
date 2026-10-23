"""Deployment Phase 3 exit: the trace streams as server-sent events, then the result."""

import json
import threading
import time

from support_reply.api.service import ApiError
from support_reply.api.stream import stream_turn
from support_reply.fixtures import CLEAN_HIT, PII_COMPLAINT, RAW_PAN, RAW_PHONE
from support_reply.llm import CUES_ONLY

SSE = {"Accept": "text/event-stream"}
AGENTS = ("facts", "pattern", "compliance")
GOLD = "They're asking about HDFC Gold ETF Fund of Fund"
GOLD_URL = "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth"


def parse(text):
    """`(event, data)` pairs from an SSE body. Comment lines (heartbeats) are skipped."""
    found = []
    for block in text.split("\n\n"):
        lines = [line for line in block.splitlines() if line and not line.startswith(":")]
        if not lines:
            continue
        name = next(line[7:] for line in lines if line.startswith("event: "))
        data = json.loads(next(line[6:] for line in lines if line.startswith("data: ")))
        found.append((name, data))
    return found


class Slow:
    """Sleeps on every call, then fails, so the node falls back to its cue table."""

    def __init__(self, seconds):
        self.seconds = seconds

    def classify(self, **_):
        time.sleep(self.seconds)
        raise RuntimeError("slow and down")


def slow_models(seconds=0.2):
    return lambda: {"classifier": Slow(seconds), "review_classifier": CUES_ONLY}


def test_a_streamed_clean_hit_sends_three_starts_then_returns_draft_reviewer_and_result(api):
    client = api()

    response = client.post("/api/sessions", json={"complaint": CLEAN_HIT}, headers=SSE)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-accel-buffering"] == "no"

    events = parse(response.text)
    names = [name for name, _ in events]
    assert names[-1] == "result" and set(names[:-1]) == {"trace"}
    trace = [data for name, data in events if name == "trace"]
    order = [(event["kind"], event["node"]) for event in trace]

    agent_starts = [i for i, (kind, node) in enumerate(order) if kind == "start" and node in AGENTS]
    agent_returns = [i for i, (kind, node) in enumerate(order) if kind == "return" and node in AGENTS]
    assert len(agent_starts) == 3 and len(agent_returns) == 3
    assert max(agent_starts) < min(agent_returns)
    assert order.index(("start", "draft")) > max(agent_returns)
    assert order.index(("start", "reviewer")) > order.index(("return", "draft"))
    assert order[-1] == ("return", "reviewer")

    result = events[-1][1]
    # The streamed events are the result's trace, and the result is the JSON body.
    assert trace == result["trace"]
    assert result == client.get(f"/api/sessions/{result['session_id']}").json()
    assert result["session"]["draft"]["disposition"] == "escalate"


def test_a_streamed_refine_that_reruns_facts_emits_no_pattern_or_compliance_events(api):
    client = api()
    session_id = client.post("/api/sessions", json={"complaint": CLEAN_HIT}).json()["session_id"]

    events = parse(
        client.post(f"/api/sessions/{session_id}/refine", json={"pushback": GOLD}, headers=SSE).text
    )

    nodes = {data["node"] for name, data in events if name == "trace"}
    assert "facts" in nodes
    assert not nodes & {"pattern", "compliance"}
    result = events[-1][1]
    assert result["turn"]["ran"] == ["facts", "orchestrator"]
    assert result["session"]["draft"]["citation"] == GOLD_URL


def test_streamed_shorter_runs_no_agent(api):
    client = api()
    session_id = client.post("/api/sessions", json={"complaint": CLEAN_HIT}).json()["session_id"]

    events = parse(
        client.post(f"/api/sessions/{session_id}/refine", json={"pushback": "Shorter"}, headers=SSE).text
    )

    nodes = [data["node"] for name, data in events if name == "trace"]
    assert not set(nodes) & set(AGENTS)
    assert "reviewer" in nodes


def test_messages_and_replace_stream_too(api):
    client = api()
    session_id = client.post("/api/sessions", json={"complaint": CLEAN_HIT}).json()["session_id"]

    message = parse(
        client.post(
            f"/api/sessions/{session_id}/messages", json={"message": "Is it a good fund?"}, headers=SSE
        ).text
    )
    replace = parse(
        client.post(
            f"/api/sessions/{session_id}/replace", json={"complaint": CLEAN_HIT}, headers=SSE
        ).text
    )

    assert message[-1][1]["turn"]["kind"] == "message"
    assert message[-1][1]["session"]["draft"]["disposition"] == "refuse"
    assert replace[-1][1]["turn"]["kind"] == "replace"


def test_prechecks_answer_with_status_codes_not_a_stream(api):
    client = api()
    missing = client.post("/api/sessions/nope/refine", json={"pushback": "Shorter"}, headers=SSE)
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/json")

    session_id = client.post("/api/sessions", json={"complaint": CLEAN_HIT}).json()["session_id"]
    for _ in range(5):
        client.post(f"/api/sessions/{session_id}/refine", json={"pushback": "Shorter"})
    sixth = client.post(f"/api/sessions/{session_id}/refine", json={"pushback": "Shorter"}, headers=SSE)
    assert sixth.status_code == 409
    assert sixth.json()["error"] == "refinement_refused"


def test_a_failed_streamed_turn_ends_with_a_generic_error_event(api):
    def broken_models():
        raise RuntimeError(f"boom {RAW_PAN}")

    client = api(models=broken_models)

    response = client.post("/api/sessions", json={"complaint": PII_COMPLAINT}, headers=SSE)

    events = parse(response.text)
    assert events[-1] == ("error", {"error": "internal_error", "message": "The turn failed."})
    assert RAW_PAN not in response.text and RAW_PHONE not in response.text


def test_an_api_error_inside_the_turn_keeps_its_code():
    def refused(trace):
        raise ApiError(409, "refinement_refused", "Refinement limit reached.")

    events = parse("".join(stream_turn(refused)))

    assert events == [("error", {"error": "refinement_refused", "message": "Refinement limit reached."})]


def test_a_heartbeat_comment_is_sent_while_nothing_else_is():
    def slow(trace):
        time.sleep(0.25)
        return {"ok": True}

    chunks = list(stream_turn(slow, heartbeat=0.05))

    assert chunks[0] == ": heartbeat\n\n"
    assert chunks[-1].startswith("event: result")


def test_trace_events_arrive_while_the_graph_is_still_running(api):
    desk = api(models=slow_models(0.3)).app.state.desk
    stream = stream_turn(lambda trace: desk.new_complaint(CLEAN_HIT, trace), heartbeat=5)

    started = time.monotonic()
    first = next(stream)
    first_at = time.monotonic() - started
    rest = list(stream)
    done_at = time.monotonic() - started

    assert first.startswith("event: trace")
    assert '"node": "ingress"' in first
    assert done_at - first_at >= 0.25  # the agents were still sleeping when it arrived
    assert rest[-1].startswith("event: result")


def test_a_client_that_disconnects_mid_stream_never_sees_a_half_updated_session(api):
    client = api(models=slow_models(0.2))
    session_id = client.post("/api/sessions", json={"complaint": CLEAN_HIT}).json()["session_id"]
    desk = client.app.state.desk
    before = client.get(f"/api/sessions/{session_id}").json()
    assert before["session"]["refinement_count"] == 0

    stream = stream_turn(lambda trace: desk.refine(session_id, GOLD, trace), heartbeat=5)
    assert next(stream).startswith("event: trace")
    stream.close()  # the browser went away

    # The turn thread still holds the session's lock; a read waits for it to finish.
    reader = {}
    thread = threading.Thread(
        target=lambda: reader.update(view=client.get(f"/api/sessions/{session_id}").json())
    )
    thread.start()
    thread.join(timeout=10)

    after = reader["view"]
    assert after["session"]["refinement_count"] == 1
    assert after["session"]["draft"]["citation"] == GOLD_URL
    assert after["session"]["agents_fired"] == [
        {"round": 1, "kind": "refinement", "ran": ["facts", "orchestrator"], "skipped": ["pattern", "compliance"]}
    ]
    assert after["turn"]["ran"] == ["facts", "orchestrator"]
