# Reply Desk API, as Render runs it. Build: `docker build -t reply-desk-api .`
#
# The package finds `data/` by walking up from its own source file, so it is installed
# editable (uv's default) with `src/` and `data/` side by side under /app.

# Reply Desk's MCP server (mcp-server/). The API starts it as a stdio subprocess after a
# human approve, to append the record to the Google Doc and create the Gmail draft.
FROM node:22-slim AS mcp
WORKDIR /mcp
COPY mcp-server/package.json mcp-server/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY mcp-server/tsconfig.json ./
COPY mcp-server/src/ src/
RUN npm run build && npm prune --omit=dev --no-audit --no-fund

FROM python:3.12-slim

# Node runs the MCP server; it is the binary from the image that built it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=mcp /usr/local/bin/node /usr/local/bin/node
RUN node --version

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

# package.json carries "type": "module", which the built server needs to load.
COPY --from=mcp /mcp/package.json mcp-server/package.json
COPY --from=mcp /mcp/node_modules/ mcp-server/node_modules/
COPY --from=mcp /mcp/dist/ mcp-server/dist/

# Approved records and email drafts go to /data/out. On Render's free plan that is the
# container's own filesystem, wiped on every restart. On a paid plan a disk mounts here;
# if writes are then refused, see Phase 9 step 5 of docs/deployment-plan.md.
RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir -p /data/out \
    && chown app /data/out
USER app

EXPOSE 8000

# Render sets PORT. `exec` hands signals straight to uvicorn.
CMD ["sh", "-c", "exec uvicorn support_reply.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
