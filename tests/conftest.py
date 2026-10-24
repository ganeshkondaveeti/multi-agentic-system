"""Unit tests stay on the cue path. Groq and Gemini calls are opt-in and use fake clients."""

import pytest


@pytest.fixture(autouse=True)
def _offline_llm(monkeypatch):
    for name in (
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "REPLY_DESK_MODELS",
        "REPLY_DESK_OUT_DIR",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def api(monkeypatch, tmp_path):
    """Build a TestClient for a fresh app: models off, approvals into `client.out_dir`.

    Call it with `Settings` fields as keyword arguments, plus `models=` to override
    the classifiers a turn uses and `raise_server_exceptions=` for 500 tests.
    """
    from fastapi.testclient import TestClient

    from support_reply.api.app import create_app
    from support_reply.api.settings import Settings

    out_dir = tmp_path / "out"
    monkeypatch.setenv("REPLY_DESK_MODELS", "off")
    monkeypatch.setenv("REPLY_DESK_OUT_DIR", str(out_dir))
    # MCP delivery stays off unless a test turns it on.
    monkeypatch.delenv("REPLY_DESK_MCP", raising=False)
    monkeypatch.delenv("REPLY_DESK_DOC_ID", raising=False)
    monkeypatch.delenv("REPLY_DESK_DRAFT_TO", raising=False)

    def make(*, models=None, raise_server_exceptions=True, **settings):
        client = TestClient(
            create_app(Settings(**settings), models=models),
            raise_server_exceptions=raise_server_exceptions,
        )
        client.out_dir = out_dir
        return client

    return make
