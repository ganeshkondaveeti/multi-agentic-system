"""Server-sent events for one turn: trace events live, then the result.

The turn runs in its own thread with a `QueueTrace`, whose `record()` also puts each
event on a queue. The response generator drains that queue:

    event: trace    {seq, node, kind, elapsed_ms}   per node start and return
    event: result   the same body as the JSON route
    event: error    {error, message}                a generic message, never user text

A comment line is sent every `heartbeat` seconds while nothing else is, so proxies
do not buffer or drop the stream. If the client goes away, the generator stops but
the turn thread finishes; the session changes only when the graph completes.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from collections.abc import Callable, Iterator
from typing import Any

from support_reply.trace import Trace, TraceEvent

from .service import ApiError

logger = logging.getLogger(__name__)

SSE_MEDIA_TYPE = "text/event-stream"
SSE_HEADERS = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
HEARTBEAT_SECONDS = 10.0

Work = Callable[[Trace], dict[str, Any]]


class QueueTrace(Trace):
    """A `Trace` that also publishes each event as it is recorded."""

    def __init__(self, events: queue.Queue[tuple[str, Any]]) -> None:
        super().__init__()
        self._outbox = events

    def record(self, node: str, kind: str) -> TraceEvent:
        event = super().record(node, kind)
        self._outbox.put(("trace", event.to_dict()))
        return event


def wants_stream(accept_header: str | None) -> bool:
    return SSE_MEDIA_TYPE in (accept_header or "").lower()


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_turn(work: Work, *, heartbeat: float = HEARTBEAT_SECONDS) -> Iterator[str]:
    """Run `work` in a thread and yield its trace events, then its result or error."""
    events: queue.Queue[tuple[str, Any]] = queue.Queue()
    trace = QueueTrace(events)

    def target() -> None:
        try:
            events.put(("result", work(trace)))
        except ApiError as exc:
            events.put(("error", {"error": exc.error, "message": exc.message}))
        except Exception as exc:  # noqa: BLE001 - the stream must always end with an event
            logger.error("streamed turn failed: %s", type(exc).__name__)
            events.put(("error", {"error": "internal_error", "message": "The turn failed."}))

    threading.Thread(target=target, name="reply-desk-turn", daemon=True).start()
    while True:
        try:
            kind, data = events.get(timeout=heartbeat)
        except queue.Empty:
            yield ": heartbeat\n\n"
            continue
        yield sse(kind, data)
        if kind in ("result", "error"):
            return
