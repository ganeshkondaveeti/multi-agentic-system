"""In-memory session store for one backend replica.

`session_id -> Entry`. Each entry has its own lock, so two turns on one thread run
one after the other instead of interleaving. Sessions idle past the TTL expire; when
the store is full, the oldest idle unlocked session is evicted. An entry holds the
`Session` (redacted text only), the last turn's trace and provenance, and the
approval, never the raw complaint.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from support_reply.contracts import Session
from support_reply.gate import new_session_id
from support_reply.llm import Source


class SessionNotFound(KeyError):
    """No live session has this id (never created, expired, or evicted)."""


class SessionBusy(RuntimeError):
    """Another turn on this session held its lock for the whole wait."""


class StoreFull(RuntimeError):
    """Every slot holds a session that is in use right now."""


@dataclass(slots=True)
class Entry:
    session_id: str
    session: Session
    created_at: float
    updated_at: float
    trace: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Source] = field(default_factory=dict)
    turn: dict[str, Any] = field(default_factory=dict)
    approved: dict[str, str] | None = None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class SessionStore:
    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_sessions: int,
        lock_wait_seconds: float = 30.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._lock_wait = lock_wait_seconds
        self._clock = clock
        self._entries: dict[str, Entry] = {}
        self._lock = threading.Lock()

    def has_room(self) -> bool:
        """True when a new session fits now, after expiring and evicting what can go."""
        with self._lock:
            self._expire()
            return len(self._entries) < self.max_sessions or self._evictable() is not None

    def add(self, session: Session) -> Entry:
        """Store a session that has finished its first turn. Raises `StoreFull`."""
        now = self._clock()
        with self._lock:
            self._expire()
            if len(self._entries) >= self.max_sessions:
                victim = self._evictable()
                if victim is None:
                    raise StoreFull("every session slot is in use")
                del self._entries[victim]
            session_id = new_session_id()
            while session_id in self._entries:
                session_id = new_session_id()
            entry = Entry(session_id=session_id, session=session, created_at=now, updated_at=now)
            self._entries[session_id] = entry
            return entry

    @contextmanager
    def locked(self, session_id: str) -> Iterator[Entry]:
        """Hold one session's lock. Raises `SessionNotFound` or `SessionBusy`."""
        entry = self._live(session_id)
        if not entry.lock.acquire(timeout=self._lock_wait):
            raise SessionBusy(session_id)
        try:
            # It may have been evicted while this caller waited.
            if self._entries.get(session_id) is not entry:
                raise SessionNotFound(session_id)
            yield entry
        finally:
            entry.lock.release()

    def entries(self) -> list[Entry]:
        """Live entries, most recently updated first."""
        with self._lock:
            self._expire()
            return sorted(self._entries.values(), key=lambda e: e.updated_at, reverse=True)

    def now(self) -> float:
        return self._clock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def _live(self, session_id: str) -> Entry:
        with self._lock:
            self._expire()
            entry = self._entries.get(session_id)
        if entry is None:
            raise SessionNotFound(session_id)
        return entry

    def _expire(self) -> None:
        cutoff = self._clock() - self.ttl_seconds
        stale = [
            key
            for key, entry in self._entries.items()
            if entry.updated_at < cutoff and not entry.lock.locked()
        ]
        for key in stale:
            del self._entries[key]

    def _evictable(self) -> str | None:
        idle = [entry for entry in self._entries.values() if not entry.lock.locked()]
        if not idle:
            return None
        return min(idle, key=lambda e: e.updated_at).session_id
