"""The FastAPI app. Run with `uvicorn support_reply.api.app:app`.

Every `/api` route except `/api/health` sits behind the access code when
`ACCESS_CODE` is set. The four routes that run the graph are rate limited per IP,
share a small pool of run slots, and stream their trace as server-sent events when
the request sends `Accept: text/event-stream`; otherwise they answer with JSON.

PII rules for this layer: complaint text arrives only in POST bodies; validation
and server errors never echo the request; nothing logs a request body. The
package's own loggers print redacted text only.
"""

from __future__ import annotations

import hmac
import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from support_reply import __version__
from support_reply.contracts import FULL_WINDOW, Disposition, Priority
from support_reply.corpus import load as load_corpus
from support_reply.llm import default_classifier, default_review_classifier, models_mode
from support_reply.trace import Trace

from .limits import RateLimiter, RunSlots, client_ip
from .schemas import (
    AcceptanceOut,
    ApproveOut,
    ComplaintIn,
    EmailOut,
    ErrorOut,
    HealthOut,
    MessageIn,
    PushbackIn,
    RecordOut,
    SessionSummary,
    SessionView,
)
from .service import (
    AcceptanceRunner,
    ApiError,
    Desk,
    ModelsFactory,
    configured_models,
    email_text,
    load_records,
)
from .settings import Settings
from .store import SessionStore
from .stream import SSE_HEADERS, SSE_MEDIA_TYPE, stream_turn, wants_stream

logger = logging.getLogger(__name__)

ACCESS_HEADER = "X-Access-Code"
REQUEST_ID_HEADER = "X-Request-ID"

_ERRORS: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorOut} for status in (400, 401, 404, 409, 413, 429, 503)
}
_STREAM_DOC = (
    "Send `Accept: text/event-stream` to receive `trace` events as the graph runs, "
    "then one `result` event with this same body (or an `error` event)."
)


def create_app(settings: Settings | None = None, *, models: ModelsFactory | None = None) -> FastAPI:
    """Build the app. `models` overrides how each turn picks its classifiers (tests)."""
    settings = settings or Settings.from_env()
    _configure_logging(settings.log_level)

    store = SessionStore(
        ttl_seconds=settings.session_ttl_seconds,
        max_sessions=settings.max_sessions,
        lock_wait_seconds=settings.run_wait_seconds,
    )
    desk = Desk(
        store,
        RunSlots(settings.max_concurrent_runs, wait_seconds=settings.run_wait_seconds),
        models or configured_models,
    )
    limiter = RateLimiter(settings.rate_per_minute)
    acceptance = AcceptanceRunner()

    app = FastAPI(
        title="Reply Desk API",
        version=__version__,
        description="Multi-agent support reply drafts. Approve writes a draft; nothing is sent.",
    )
    app.state.settings = settings
    app.state.desk = desk
    app.state.acceptance = acceptance

    def require_access_code(
        x_access_code: str | None = Header(default=None, alias=ACCESS_HEADER),
    ) -> None:
        expected = settings.access_code
        if expected is None:
            return
        given = (x_access_code or "").encode("utf-8")
        if not hmac.compare_digest(given, expected.encode("utf-8")):
            raise ApiError(401, "access_code_required", f"Send a valid {ACCESS_HEADER} header.")

    def rate_limited(request: Request) -> None:
        if not limiter.allow(client_ip(request, settings.client_ip_header)):
            raise ApiError(429, "rate_limited", "Too many turns from this address. Wait a minute.")

    def respond(request: Request, work: Callable[[Trace], dict[str, Any]]) -> Any:
        """JSON by default; a server-sent event stream when the client asks for one."""
        if wants_stream(request.headers.get("accept")):
            return StreamingResponse(
                stream_turn(lambda trace: _session_body(work(trace))),
                media_type=SSE_MEDIA_TYPE,
                headers=SSE_HEADERS,
            )
        return work(Trace())

    api = APIRouter(prefix="/api")

    @api.get("/health", response_model=HealthOut, tags=["meta"])
    def health() -> dict[str, Any]:
        mode = models_mode()
        agents = default_classifier() if mode == "auto" else None
        reviewer = default_review_classifier() if mode == "auto" else None
        corpus = load_corpus()
        return {
            "status": "ok",
            "environment": settings.environment,
            "models": {
                "mode": mode,
                "agents": "groq" if agents is not None else "cues",
                "reviewer": "gemini" if reviewer is not None else "code",
                "agent_model": getattr(agents, "model", None),
                "reviewer_model": getattr(reviewer, "model", None),
            },
            "corpus": {"last_checked": corpus.schemes[0].nav_date, "schemes": len(corpus.schemes)},
            "review_window": FULL_WINDOW.to_dict(),
            "access_code_required": settings.access_code is not None,
        }

    protected = APIRouter(dependencies=[Depends(require_access_code)], responses=_ERRORS)

    @protected.post(
        "/sessions",
        response_model=SessionView,
        dependencies=[Depends(rate_limited)],
        tags=["sessions"],
        description="Start a thread with one complaint. " + _STREAM_DOC,
    )
    def create_session(body: ComplaintIn, request: Request) -> Any:
        complaint = body.complaint
        desk.check_room()
        return respond(request, lambda trace: desk.new_complaint(complaint, trace))

    @protected.get("/sessions", response_model=list[SessionSummary], tags=["sessions"])
    def list_sessions() -> list[dict[str, Any]]:
        return desk.summaries()

    @protected.get("/sessions/{session_id}", response_model=SessionView, tags=["sessions"])
    def get_session(session_id: str) -> dict[str, Any]:
        return desk.view(session_id)

    @protected.post(
        "/sessions/{session_id}/refine",
        response_model=SessionView,
        dependencies=[Depends(rate_limited)],
        tags=["sessions"],
        description="Push back on the draft; only the agents it names re-run. " + _STREAM_DOC,
    )
    def refine_session(session_id: str, body: PushbackIn, request: Request) -> Any:
        pushback = body.pushback
        desk.check_open(session_id, refining=True)
        return respond(request, lambda trace: desk.refine(session_id, pushback, trace))

    @protected.post(
        "/sessions/{session_id}/replace",
        response_model=SessionView,
        dependencies=[Depends(rate_limited)],
        tags=["sessions"],
        description="Correct the complaint text; a refinement in which every agent re-runs. "
        + _STREAM_DOC,
    )
    def replace_complaint(session_id: str, body: ComplaintIn, request: Request) -> Any:
        complaint = body.complaint
        desk.check_open(session_id, refining=True)
        return respond(request, lambda trace: desk.replace(session_id, complaint, trace))

    @protected.post(
        "/sessions/{session_id}/messages",
        response_model=SessionView,
        dependencies=[Depends(rate_limited)],
        tags=["sessions"],
        description="A new message from the user in this thread; every agent runs. " + _STREAM_DOC,
    )
    def add_message(session_id: str, body: MessageIn, request: Request) -> Any:
        message = body.message
        desk.check_open(session_id, refining=False)
        return respond(request, lambda trace: desk.message(session_id, message, trace))

    @protected.post(
        "/sessions/{session_id}/approve",
        response_model=ApproveOut,
        tags=["sessions"],
        description="The human approve click. Appends a redacted record and writes an email "
        "draft. Nothing is sent.",
    )
    def approve_session(session_id: str) -> dict[str, Any]:
        return desk.approve(session_id)

    @protected.get("/records", response_model=list[RecordOut], tags=["records"])
    def list_records(
        disposition: Disposition | None = None,
        priority: Priority | None = None,
        team: str | None = None,
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> list[dict[str, Any]]:
        records = sorted(load_records(), key=lambda r: r.get("approved_at", ""), reverse=True)
        picked = [
            record
            for record in records
            if (disposition is None or record.get("disposition") == disposition)
            and (priority is None or record.get("routing_note", {}).get("priority") == priority)
            and (team is None or record.get("routing_note", {}).get("team") == team)
        ]
        return picked[:limit]

    @protected.get("/records/{session_id}/email", response_model=EmailOut, tags=["records"])
    def get_email(session_id: str) -> dict[str, str]:
        return {"session_id": session_id, "text": email_text(session_id)}

    @protected.post("/acceptance/run", response_model=AcceptanceOut, tags=["acceptance"])
    def run_acceptance() -> dict[str, Any]:
        return acceptance.run(desk.store.now)

    @protected.get("/acceptance", response_model=AcceptanceOut, tags=["acceptance"])
    def last_acceptance() -> dict[str, Any]:
        if acceptance.last is None:
            raise ApiError(404, "no_acceptance_run", "No acceptance run yet. POST /api/acceptance/run.")
        return acceptance.last

    api.include_router(protected)
    app.include_router(api)

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse({"error": exc.error, "message": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Field names and error types only. Pydantic's `input`, `msg`, and `ctx` can
        # quote the request body, so none of them is returned or logged.
        fields = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())[1:]) or "body",
                "type": str(error.get("type", "invalid")),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            {"error": "invalid_request", "message": "The request body is not valid.", "fields": fields},
            status_code=400,
        )

    # Unhandled exceptions become a generic 500 in `RequestId`, inside the CORS layer.
    # Outermost last: CORS wraps everything, so error responses carry its headers too.
    app.add_middleware(BodyLimit, max_bytes=settings.max_body_bytes)
    app.add_middleware(RequestId)
    if settings.allowed_origins or settings.allowed_origin_regex:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_origin_regex=settings.allowed_origin_regex,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", ACCESS_HEADER],
            expose_headers=[REQUEST_ID_HEADER],
            max_age=600,
        )
    return app


def _session_body(view: dict[str, Any]) -> dict[str, Any]:
    """The streamed `result` is the JSON route's body, validated the same way."""
    return SessionView.model_validate(view).model_dump(mode="json")


def _configure_logging(level: str) -> None:
    logging.getLogger("support_reply").setLevel(level)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


class RequestId:
    """Tags each request with an id, kept on `request.state` and sent back as a header.

    It also turns an unhandled exception into a generic 500 here, inside the CORS
    layer, so the browser can read it. Only the exception's type is logged: its
    message or traceback could quote a value.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        started = False

        async def tagged(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message.setdefault("headers", []).append(
                    (REQUEST_ID_HEADER.lower().encode("latin-1"), request_id.encode("latin-1"))
                )
            await send(message)

        try:
            await self.app(scope, receive, tagged)
        except Exception as exc:  # noqa: BLE001 - last line before the server
            logger.error("unhandled %s request_id=%s", type(exc).__name__, request_id)
            if started:
                return
            payload = json.dumps(
                {"error": "internal_error", "message": "Something went wrong.", "request_id": request_id}
            ).encode("utf-8")
            await tagged(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(payload)).encode("latin-1")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": payload})


class BodyLimit:
    """Rejects request bodies over `max_bytes` with 413 before anything parses them."""

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return
        declared = dict(scope.get("headers", [])).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            await self._too_large(send)
            return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.max_bytes:
                await self._too_large(send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    async def _too_large(self, send: Send) -> None:
        payload = json.dumps(
            {"error": "payload_too_large", "message": f"Request bodies are limited to {self.max_bytes} bytes."}
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})


app = create_app()
