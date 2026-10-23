"""API settings, read once from the environment when the app is created.

The model switches (`REPLY_DESK_MODELS`, the keys) and `REPLY_DESK_OUT_DIR` are not
here: the package reads those at call time, so they behave the same in the CLI.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    access_code: str | None = None
    allowed_origins: tuple[str, ...] = ()
    allowed_origin_regex: str | None = None
    # Turns per minute per client IP on the routes that run the graph.
    rate_per_minute: int = 12
    # Graph runs at once. Each run makes three Groq calls together.
    max_concurrent_runs: int = 2
    run_wait_seconds: float = 30.0
    max_body_bytes: int = 8 * 1024
    session_ttl_seconds: float = 2 * 60 * 60
    max_sessions: int = 200
    environment: str = "local"
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        for name in ("rate_per_minute", "max_concurrent_runs", "max_body_bytes", "max_sessions"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive int")
        if self.access_code is not None and not self.access_code.strip():
            raise ValueError("access_code must be non-empty when set")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        source = os.environ if env is None else env
        defaults = cls()

        def text(name: str) -> str | None:
            value = source.get(name, "").strip()
            return value or None

        def number(name: str, default: int) -> int:
            value = text(name)
            if value is None:
                return default
            try:
                return int(value)
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc

        origins = tuple(
            origin.strip().rstrip("/")
            for origin in (text("ALLOWED_ORIGINS") or "").split(",")
            if origin.strip()
        )
        return cls(
            access_code=text("ACCESS_CODE"),
            allowed_origins=origins,
            allowed_origin_regex=text("ALLOWED_ORIGIN_REGEX"),
            rate_per_minute=number("REPLY_DESK_RATE_PER_MINUTE", defaults.rate_per_minute),
            max_concurrent_runs=number("REPLY_DESK_MAX_CONCURRENT_RUNS", defaults.max_concurrent_runs),
            environment=text("REPLY_DESK_ENV") or defaults.environment,
            log_level=(text("LOG_LEVEL") or defaults.log_level).upper(),
        )
