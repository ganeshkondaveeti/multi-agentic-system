"""Per-IP rate limit and the global cap on concurrent graph runs."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from starlette.requests import Request

_IDLE_PRUNE_SECONDS = 600.0
_PRUNE_AT = 10_000


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """Token bucket per key: `per_minute` tokens, refilled continuously over a minute."""

    def __init__(self, per_minute: int, *, clock: Callable[[], float] = time.monotonic) -> None:
        if per_minute < 1:
            raise ValueError("per_minute must be positive")
        self.capacity = float(per_minute)
        self.refill_per_second = per_minute / 60.0
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = self._buckets[key] = _Bucket(tokens=self.capacity, updated=now)
            else:
                elapsed = now - bucket.updated
                bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.refill_per_second)
                bucket.updated = now
            if len(self._buckets) > _PRUNE_AT:
                self._prune(now)
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True
            return False

    def _prune(self, now: float) -> None:
        stale = [k for k, b in self._buckets.items() if now - b.updated > _IDLE_PRUNE_SECONDS]
        for key in stale:
            del self._buckets[key]


class RunsBusy(RuntimeError):
    """Every graph-run slot stayed taken for the whole wait."""


class RunSlots:
    """At most `size` graph runs at once; callers wait up to `wait_seconds` for a slot."""

    def __init__(self, size: int, *, wait_seconds: float) -> None:
        self._slots = threading.BoundedSemaphore(size)
        self._wait = wait_seconds

    @contextmanager
    def slot(self) -> Iterator[None]:
        if not self._slots.acquire(timeout=self._wait):
            raise RunsBusy("every run slot is busy")
        try:
            yield
        finally:
            self._slots.release()


def client_ip(request: Request, header: str | None = None) -> str:
    """The caller's IP: `header` when set and present, else the last `X-Forwarded-For` hop.

    On Render, `header` is `CF-Connecting-IP`: Cloudflare overwrites it on every request,
    while the last `X-Forwarded-For` hop is Render's own proxy. Set `header` only behind
    a proxy that overwrites it, or a client can pick its own rate-limit key.

    Without `header`, the last `X-Forwarded-For` entry is the one a single proxy appended,
    so a forged left-most entry does not change the key.
    """
    if header:
        value = request.headers.get(header, "").strip()
        if value:
            return value
    forwarded = request.headers.get("x-forwarded-for", "")
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    if hops:
        return hops[-1]
    return request.client.host if request.client else "unknown"
