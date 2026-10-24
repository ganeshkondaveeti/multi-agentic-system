"""The approval-gated MCP step: Doc append and Gmail draft after a human approve."""

import asyncio
import shutil

import pytest

from support_reply import workspace
from support_reply.fixtures import CLEAN_HIT, RAW_PAN
from support_reply.workspace import OFF, Step, deliver

RECORD = {
    "session_id": "c786b480b6d04784acb61582d94bee82",
    "approved_at": "2026-10-24T08:00:00+00:00",
    "redacted_text": "Why was I charged an exit load? My PAN is [PAN].",
    "disposition": "escalate",
    "reply": "Exit load of 1% if redeemed within 1 year. Last checked 25-Jun-2026.",
    "citation": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
    "routing_note": {"team": "Fees and mutual fund ops", "priority": "P2", "why": "recurring"},
    "pattern_signal": "recurring",
}
EMAIL = RECORD["reply"] + "\n"


class FakeRunner:
    """Records the tool calls; answers each with the next scripted Step."""

    def __init__(self, *answers, fail_after=None, delay=0.0):
        self.answers = list(answers)
        self.fail_after = fail_after
        self.delay = delay
        self.calls = []

    async def __call__(self, calls, steps):
        for name, arguments in calls:
            if self.fail_after is not None and len(steps) == self.fail_after:
                raise ConnectionError("server went away")
            await asyncio.sleep(self.delay)
            self.calls.append((name, arguments))
            steps.append(self.answers.pop(0) if self.answers else Step("done"))


@pytest.fixture
def mcp_on(monkeypatch):
    monkeypatch.setenv("REPLY_DESK_MCP", "on")
    monkeypatch.setenv("REPLY_DESK_DOC_ID", "doc-123")
    monkeypatch.delenv("REPLY_DESK_DRAFT_TO", raising=False)


def test_off_by_default_and_nothing_runs(monkeypatch):
    monkeypatch.delenv("REPLY_DESK_MCP", raising=False)
    runner = FakeRunner()

    assert deliver(RECORD, EMAIL, runner=runner) == OFF
    assert runner.calls == []


def test_appends_the_record_and_drafts_without_a_recipient(mcp_on):
    runner = FakeRunner()

    delivery = deliver(RECORD, EMAIL, runner=runner)

    assert delivery.to_dict() == {"doc": {"status": "done", "error": None}, "email": {"status": "done", "error": None}}
    (doc_tool, doc_args), (mail_tool, mail_args) = runner.calls
    assert doc_tool == "google_docs_append"
    assert doc_args["document_id"] == "doc-123"
    assert "escalate" in doc_args["content"] and "[PAN]" in doc_args["content"]
    assert "\n" not in doc_args["content"]
    assert mail_tool == "gmail_draft"
    assert mail_args == {"subject": "Support reply draft c786b480 (escalate)", "body": EMAIL}
    assert "to" not in mail_args


def test_the_draft_is_addressed_to_the_configured_inbox(mcp_on, monkeypatch):
    monkeypatch.setenv("REPLY_DESK_DRAFT_TO", "support@example.com, lead@example.com ")
    runner = FakeRunner()

    delivery = deliver(RECORD, EMAIL, runner=runner)

    assert delivery.email == Step("done")
    _, (mail_tool, mail_args) = runner.calls
    assert mail_tool == "gmail_draft"
    assert mail_args["to"] == ["support@example.com", "lead@example.com"]


def test_a_malformed_recipient_skips_only_the_draft(mcp_on, monkeypatch):
    monkeypatch.setenv("REPLY_DESK_DRAFT_TO", "not-an-address")
    runner = FakeRunner()

    delivery = deliver(RECORD, EMAIL, runner=runner)

    assert delivery.doc == Step("done")
    assert delivery.email == Step("failed", "draft_to_invalid")
    assert [name for name, _ in runner.calls] == ["google_docs_append"]


def test_never_calls_a_send_tool(mcp_on):
    runner = FakeRunner()
    deliver(RECORD, EMAIL, runner=runner)
    assert all("send" not in name for name, _ in runner.calls)


def test_without_a_doc_id_the_draft_is_still_made(mcp_on, monkeypatch):
    monkeypatch.delenv("REPLY_DESK_DOC_ID")
    runner = FakeRunner()

    delivery = deliver(RECORD, EMAIL, runner=runner)

    assert delivery.doc == Step("failed", "doc_id_missing")
    assert delivery.email == Step("done")
    assert [name for name, _ in runner.calls] == ["gmail_draft"]


def test_a_tool_error_is_reported_by_its_code(mcp_on):
    delivery = deliver(RECORD, EMAIL, runner=FakeRunner(Step("done"), Step("failed", "AUTHENTICATION_REQUIRED")))
    assert delivery.doc == Step("done")
    assert delivery.email == Step("failed", "AUTHENTICATION_REQUIRED")


def test_a_step_that_finished_survives_a_later_crash(mcp_on):
    delivery = deliver(RECORD, EMAIL, runner=FakeRunner(fail_after=1))
    assert delivery.doc == Step("done")
    assert delivery.email == Step("failed", "mcp_unavailable")


def test_a_slow_server_times_out(mcp_on, monkeypatch):
    monkeypatch.setattr(workspace, "TIMEOUT_SECONDS", 0.05)
    delivery = deliver(RECORD, EMAIL, runner=FakeRunner(delay=1.0))
    assert delivery.doc == Step("failed", "timeout")
    assert delivery.email == Step("failed", "timeout")


def test_raw_pii_never_leaves_the_process(mcp_on):
    runner = FakeRunner()

    delivery = deliver(RECORD, f"My PAN is {RAW_PAN}", runner=runner)

    assert delivery.doc == Step("failed", "raw_pii")
    assert delivery.email == Step("failed", "raw_pii")
    assert runner.calls == []


def test_the_child_gets_google_settings_only(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    monkeypatch.setenv("ACCESS_CODE", "door")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("GOOGLE_TOKEN_JSON", '{"refresh_token": "r"}')
    monkeypatch.delenv("GOOGLE_TOKEN_PATH", raising=False)
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    env = workspace._child_env(tmp_path / "mcp-server" / "dist" / "index.js")

    assert set(env) == {
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI",
        "GOOGLE_TOKEN_JSON",
        "GOOGLE_TOKEN_PATH",
        "NODE_ENV",
        "LOG_LEVEL",
    }
    assert env["GOOGLE_TOKEN_PATH"] == "/tmp/reply-desk-google-token.json"
    assert env["LOG_LEVEL"] == "warn"
    assert env["NODE_ENV"] == "production"


def test_locally_the_token_is_where_npm_run_auth_saves_it(monkeypatch, tmp_path):
    for key in ("GOOGLE_TOKEN_JSON", "GOOGLE_TOKEN_PATH"):
        monkeypatch.delenv(key, raising=False)
    env = workspace._child_env(tmp_path / "mcp-server" / "dist" / "index.js")
    assert env["GOOGLE_TOKEN_PATH"] == str(tmp_path / "mcp-server" / "data" / "google-token.json")


# --- through the API ----------------------------------------------------------------------


def test_approve_reports_delivery_and_the_session_keeps_it(api, monkeypatch):
    monkeypatch.setenv("REPLY_DESK_MCP", "on")
    monkeypatch.setenv("REPLY_DESK_DOC_ID", "doc-123")
    runner = FakeRunner(Step("done"), Step("failed", "RATE_LIMITED"))
    monkeypatch.setattr(workspace, "_run_stdio", runner)
    client = api()
    session_id = client.post("/api/sessions", json={"complaint": CLEAN_HIT}).json()["session_id"]

    approved = client.post(f"/api/sessions/{session_id}/approve").json()

    expected = {"doc": {"status": "done", "error": None}, "email": {"status": "failed", "error": "RATE_LIMITED"}}
    assert approved["delivery"] == expected
    assert client.get(f"/api/sessions/{session_id}").json()["approved"]["delivery"] == expected
    # The approval stands: the record is listed even though the draft failed.
    assert [record["session_id"] for record in client.get("/api/records").json()] == [session_id]
    assert client.get("/api/health").json()["mcp"] == {"enabled": True, "doc_configured": True}


def test_approve_with_mcp_off_reports_off(api):
    client = api()
    session_id = client.post("/api/sessions", json={"complaint": CLEAN_HIT}).json()["session_id"]

    approved = client.post(f"/api/sessions/{session_id}/approve").json()

    assert approved["delivery"] == OFF.to_dict()


# --- the real server, when it is built -----------------------------------------------------


@pytest.mark.skipif(
    shutil.which("node") is None or not workspace.server_path().is_file(),
    reason="needs node and a built mcp-server (cd mcp-server && npm ci && npm run build)",
)
def test_the_real_server_answers_over_stdio_without_reaching_google(mcp_on, monkeypatch, tmp_path):
    # Placeholder OAuth settings and no token: each tool fails at its auth check,
    # before any request to Google, and says so with its code.
    monkeypatch.delenv("GOOGLE_TOKEN_JSON", raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "placeholder")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "placeholder")
    monkeypatch.setenv("GOOGLE_TOKEN_PATH", str(tmp_path / "missing-token.json"))

    delivery = deliver(RECORD, EMAIL)

    assert delivery.doc == Step("failed", "AUTHENTICATION_REQUIRED")
    assert delivery.email == Step("failed", "AUTHENTICATION_REQUIRED")
