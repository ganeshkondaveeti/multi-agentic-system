"""After a human approve: append the record to the Google Doc and create the Gmail draft.

This is the approval-gated MCP step from the problem statement. It runs only after
`gate.approve` has written the local record and email file, and only when
`REPLY_DESK_MCP=on`. Reply Desk's own MCP server (`mcp-server/`) is started as a stdio
subprocess for each approve. It has two tools, `google_docs_append` and `gmail_draft`,
and no send tool. The draft is addressed to `REPLY_DESK_DRAFT_TO` when that is set (an
operator inbox, never the customer: the app does not store the customer's address),
and has no recipient otherwise. Either way a person sends it from Gmail.

A failure here never undoes an approval. Each step reports `done`, `failed` (with the
server's error code, never a message body), or `off`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from support_reply.corpus import data_dir
from support_reply.ingress import scan

logger = logging.getLogger(__name__)

MCP_ENV = "REPLY_DESK_MCP"
DOC_ID_ENV = "REPLY_DESK_DOC_ID"
DRAFT_TO_ENV = "REPLY_DESK_DRAFT_TO"
SERVER_ENV = "REPLY_DESK_MCP_SERVER"
TIMEOUT_SECONDS = 45.0
# Only these reach the Node process, on top of the SDK's base HOME/PATH/USER set.
_GOOGLE_ENV = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI", "GOOGLE_TOKEN_JSON", "GOOGLE_TOKEN_PATH")
_EMAIL = re.compile(r"[^@\s,]+@[^@\s,]+\.[^@\s,]+")
_NODE_LOG_LEVELS = {"DEBUG": "debug", "INFO": "info", "WARNING": "warn", "ERROR": "error", "CRITICAL": "error"}

Status = Literal["done", "failed", "off"]
ToolCall = tuple[str, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class Step:
    status: Status
    error: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {"status": self.status, "error": self.error}


@dataclass(frozen=True, slots=True)
class Delivery:
    """What happened to the Doc append and the Gmail draft after one approve."""

    doc: Step
    email: Step

    def to_dict(self) -> dict[str, dict[str, str | None]]:
        return {"doc": self.doc.to_dict(), "email": self.email.to_dict()}


OFF = Delivery(doc=Step("off"), email=Step("off"))

# Runs the tool calls in order, appending one Step per call as it finishes, so the
# steps that finished survive a later failure.
Runner = Callable[[Sequence[ToolCall], list[Step]], Awaitable[None]]


def enabled() -> bool:
    return os.environ.get(MCP_ENV, "").strip().lower() == "on"


def deliver(record: dict[str, Any], email: str, *, runner: Runner | None = None) -> Delivery:
    """Append `record` to the Doc and draft `email` in Gmail. Off unless `REPLY_DESK_MCP=on`."""
    if not enabled():
        return OFF
    doc_id = os.environ.get(DOC_ID_ENV, "").strip()
    doc_text = doc_line(record)
    subject = draft_subject(record)
    # The gate already refused raw PII; check again before anything leaves the process.
    if scan(doc_text).pii_types or scan(email).pii_types or scan(subject).pii_types:
        logger.error("delivery refused for %s: raw PII in the outgoing text", record.get("session_id"))
        return Delivery(doc=Step("failed", "raw_pii"), email=Step("failed", "raw_pii"))

    recipients = draft_recipients()
    draft: dict[str, Any] = {"subject": subject, "body": email}
    if recipients:
        draft["to"] = recipients

    calls: list[ToolCall] = []
    if doc_id:
        calls.append(("google_docs_append", {"document_id": doc_id, "content": doc_text}))
    if recipients is not None:
        calls.append(("gmail_draft", draft))

    steps = _run(calls, runner or _run_stdio) if calls else []
    doc = steps.pop(0) if doc_id else Step("failed", "doc_id_missing")
    email_step = steps[0] if recipients is not None else Step("failed", "draft_to_invalid")
    delivery = Delivery(doc=doc, email=email_step)
    logger.info(
        "delivery for %s: doc %s, email %s",
        record.get("session_id"),
        delivery.doc.status,
        delivery.email.status,
    )
    return delivery


def draft_recipients() -> list[str] | None:
    """`REPLY_DESK_DRAFT_TO` as a list: empty when unset, None when an address is malformed."""
    raw = os.environ.get(DRAFT_TO_ENV, "")
    addresses = [part.strip() for part in raw.split(",") if part.strip()]
    if any(_EMAIL.fullmatch(address) is None for address in addresses):
        logger.error("%s holds a malformed address; the Gmail draft is skipped", DRAFT_TO_ENV)
        return None
    return addresses


def doc_line(record: dict[str, Any]) -> str:
    """One line per approved record. Redacted text only, as in records.jsonl."""
    routing = record.get("routing_note") or {}
    fields = [
        record.get("approved_at", ""),
        f"session {record.get('session_id', '')}",
        record.get("disposition", ""),
        routing.get("priority", ""),
        routing.get("team", ""),
        f"pattern {record.get('pattern_signal', '')}",
        f"citation {record.get('citation') or 'none'}",
        f"complaint: {record.get('redacted_text', '')}",
        f"reply: {record.get('reply', '')}",
    ]
    return " | ".join(str(field).replace("\n", " ") for field in fields)


def draft_subject(record: dict[str, Any]) -> str:
    return f"Support reply draft {str(record.get('session_id', ''))[:8]} ({record.get('disposition', '')})"


def _run(calls: Sequence[ToolCall], runner: Runner) -> list[Step]:
    """Every call gets a Step: one the runner did not reach is `failed`."""
    steps: list[Step] = []
    error = "incomplete"
    try:
        asyncio.run(asyncio.wait_for(runner(calls, steps), TIMEOUT_SECONDS))
    except TimeoutError:
        error = "timeout"
    except Exception as exc:  # the subprocess or the protocol failed; the approval stands
        logger.error("MCP server unavailable: %s", type(exc).__name__)
        error = "mcp_unavailable"
    return [*steps, *[Step("failed", error)] * (len(calls) - len(steps))][: len(calls)]


async def _run_stdio(calls: Sequence[ToolCall], steps: list[Step]) -> None:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    server = server_path()
    node = shutil.which("node")
    if node is None or not server.is_file():
        raise FileNotFoundError("node or the built MCP server is missing")
    params = StdioServerParameters(command=node, args=[str(server)], env=_child_env(server), cwd=str(server.parents[1]))
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        for name, arguments in calls:
            steps.append(_step(await session.call_tool(name, arguments)))


def server_path() -> Path:
    configured = os.environ.get(SERVER_ENV, "").strip()
    if configured:
        return Path(configured)
    return data_dir().parent / "mcp-server" / "dist" / "index.js"


def _child_env(server: Path) -> dict[str, str]:
    env = {key: os.environ[key] for key in _GOOGLE_ENV if os.environ.get(key)}
    env.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:3000/oauth/callback")
    if "GOOGLE_TOKEN_JSON" in env:
        # The token comes from the environment; a refreshed copy goes somewhere writable.
        env.setdefault("GOOGLE_TOKEN_PATH", "/tmp/reply-desk-google-token.json")
    else:
        # Where `npm run auth` in mcp-server/ saves it.
        env.setdefault("GOOGLE_TOKEN_PATH", str(server.parents[1] / "data" / "google-token.json"))
    env["NODE_ENV"] = "production"
    env["LOG_LEVEL"] = _NODE_LOG_LEVELS.get(os.environ.get("LOG_LEVEL", "INFO").strip().upper(), "info")
    return env


def _step(result: Any) -> Step:
    if not getattr(result, "is_error", False):
        return Step("done")
    code = "tool_error"
    for item in getattr(result, "content", None) or []:
        try:
            code = str(json.loads(item.text)["error"]["code"])
            break
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    return Step("failed", code)
