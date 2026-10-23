# Reply Desk API, as Railway runs it. Build: `docker build -t reply-desk-api .`
#
# The package finds `data/` by walking up from its own source file, so it is installed
# editable (uv's default) with `src/` and `data/` side by side under /app.
FROM python:3.12-slim

# Pinned to the uv used locally, so `uv.lock` resolves the same way.
COPY --from=ghcr.io/astral-sh/uv:0.12.12 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    REPLY_DESK_OUT_DIR=/data/out

WORKDIR /app

# Dependencies first, so a source change does not reinstall them.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
COPY data/ data/
RUN uv sync --frozen --no-dev

# Approved records and email drafts go to /data/out. Railway mounts its volume there;
# Railway volumes are owned by root, so set RAILWAY_RUN_UID=0 if writes are refused.
RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir -p /data/out \
    && chown app /data/out
USER app

EXPOSE 8000

# Railway sets PORT. `exec` hands signals straight to uvicorn.
CMD ["sh", "-c", "exec uvicorn support_reply.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
