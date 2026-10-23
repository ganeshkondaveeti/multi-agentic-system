# Reply Desk: multi-agent support replies for Groww

Reply Desk drafts a support reply to a Groww user's mutual-fund complaint. Three specialist agents run in parallel on a LangGraph:

- **Facts** copies the answer from one of five HDFC scheme pages and cites its `source_url`.
- **Pattern** matches the complaint to a Play Store review theme and says whether it is recurring, rising, or a one-off.
- **Compliance** flags requests for advice or returns, and any PII.

An orchestrator merges them into a reply of at most three sentences plus an internal routing note. A reviewer blocks uncited facts, advice, return figures, and surviving PII; it allows one rework. A human can push back up to five times. Nothing is saved until a human approves, and nothing is ever sent.

Each agent's model call only classifies, returning an id or a flag from a closed list. Code copies the fact, counts the reviews, and writes the reply. With no API keys, every node falls back to regex cue tables, so everything below runs offline.

## Requirements

- [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 from `.python-version`)
- Optional: a Groq key for the three agents and a Gemini key for the reviewer

## Setup

```bash
uv sync
cp .env.example .env   # then fill in GROQ_API_KEY and GEMINI_API_KEY, or leave them blank
```

`.env` is gitignored. Keys already set in your shell take precedence over `.env`.

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY`, `GROQ_MODEL` | Agent classifier (default model `openai/gpt-oss-120b`) |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Reviewer second opinion (default `gemini-3.5-flash`) |
| `REPLY_DESK_MODELS` | `auto` (default) uses models when keys are set; `off` forces the cue tables |
| `REPLY_DESK_OUT_DIR` | Where approved records and email drafts go (default `out/`) |

## Run

```bash
uv run pytest                                   # full test suite, offline
uv run python -m support_reply.cli --offline    # interactive session: complaint, pushbacks, /approve
uv run python -m support_reply.accept --offline # acceptance run: 20 reviews, 4 branches, advice thread, caps
uv run python scripts/verify_flow.py            # one complaint against the live models (needs both keys)
```

Drop `--offline` to use the models configured in `.env`.

In the CLI, plain text is a pushback that re-runs only the agents it names. `/message`, `/replace`, `/approve`, `/show`, `/quit`, and `/help` are listed by `/help`. `/approve` is offered only when the reviewer passed. It appends a redacted record to `out/records.jsonl` and writes `out/email_drafts/<session>.txt`; with `REPLY_DESK_MCP=on` it then appends the record to the Google Doc and creates the Gmail draft (see below).

### HTTP API

```bash
uv run uvicorn support_reply.api.app:app --reload --port 8000   # OpenAPI docs at http://localhost:8000/docs
```

Routes live under `/api`: `health`, `sessions` (create, list, get), `sessions/{id}/refine`, `/replace`, `/messages`, `/approve`, `records`, `records/{id}/email`, and `acceptance` (`POST acceptance/run` runs the cues-only acceptance check). The four turn routes stream the trace as server-sent events when the request sends `Accept: text/event-stream`; otherwise they return JSON.

| Variable | Purpose |
|---|---|
| `ACCESS_CODE` | When set, every route except `/api/health` needs an `X-Access-Code` header |
| `ALLOWED_ORIGINS`, `ALLOWED_ORIGIN_REGEX` | CORS origins for the web frontend (none by default) |
| `REPLY_DESK_RATE_PER_MINUTE` | Turns per minute per client IP (default 12) |
| `REPLY_DESK_MAX_CONCURRENT_RUNS` | Graph runs at once (default 2) |
| `REPLY_DESK_CLIENT_IP_HEADER` | Header that carries the caller's IP for the rate limit (Render: `CF-Connecting-IP`). Unset, the last `X-Forwarded-For` hop is used. Set it only behind a proxy that overwrites the header. |
| `REPLY_DESK_ENV`, `LOG_LEVEL` | Environment label shown by `/api/health` (default `local`), log level (default `INFO`) |

Sessions live in memory for 2 idle hours; approved records persist in `REPLY_DESK_OUT_DIR`. Approving closes a session.

### Approval-gated MCP (`mcp-server/`)

After a human approve, and only with `REPLY_DESK_MCP=on`, the API starts Reply Desk's MCP server as a stdio subprocess. It appends the redacted record as one line to the Google Doc in `REPLY_DESK_DOC_ID` and creates a Gmail draft of the reply with no recipient. The server has no send tool, so nothing is ever sent. The local record and email file are written first, and a failed Google call never undoes the approval: the approve response and the approved note report each step as done or failed, with the server's error code. `mcp-server/README.md` covers the one-time Google OAuth setup.

### Web app (`web/`)

React + Vite + TypeScript + Tailwind, built from the Stitch designs in `design/stitch/`. Node 22 or newer.

```bash
cd web && npm ci
npm run dev          # http://localhost:5173, proxies /api to the API on :8000 (start it first)
npm test             # Vitest: components, client, and helpers against captured API responses
npm run e2e          # Playwright: starts its own API (models off) and a preview build, then drives the browser
npm run typecheck && npm run lint && npm run build
```

Pages: **Workspace** (queue, new complaint, the three agent cards, live trace, draft, reviewer, routing, refine, approve), **Records** (approved records and their email drafts), and **Acceptance** (the cues-only acceptance run). After an API change, regenerate the types with `npm run gen:api` (API running on :8000) and the test fixtures with `uv run python scripts/capture_web_fixtures.py`. Set `VITE_API_BASE_URL` for a build that calls a deployed API directly.

## Full stack

From a fresh clone:

```bash
make install                  # uv sync, then npm ci in web/
cp .env.example .env          # keys optional; blank keys or REPLY_DESK_MODELS=off use the cue tables
cp web/.env.example web/.env.local
make dev                      # API on :8000 with reload, web on http://localhost:5173; Ctrl-C stops both
```

| Target | What it does |
|---|---|
| `make dev-api`, `make dev-web` | One side only |
| `make test` | pytest, then Vitest. Offline. |
| `make e2e` | Playwright. Its config starts the API with `REPLY_DESK_MODELS=off` and a preview build, so it is offline and leaves `out/` alone. |
| `make stack-check` | Starts the API with the production server command and a web build that calls it directly, so every request crosses origins through CORS. Runs the Playwright suite against them, then greps the API log (at `DEBUG`) and the records directory for the fixture PAN and phone. Offline. |
| `make docker-run` | Builds the production image (`Dockerfile`, the one Render builds) and runs it on :8000. It reads keys from `.env` and keeps records in the `reply-desk-out` Docker volume. |
| `make preview-direct` | Builds the web app with `VITE_API_BASE_URL=http://localhost:8000` and previews it on http://localhost:4173. Use it with `make docker-run` to drive the image from the browser. `docker-run` already allows that origin. |

Env files: the root `.env` holds the keys and the serving variables above. `web/.env.local` holds `VITE_API_BASE_URL`, which is empty locally so the Vite proxy is used. Both are gitignored; `.env.example` and `web/.env.example` document them.

## Deploying on Render

`render.yaml` is a Render Blueprint with two services: `reply-desk-api`, a free-plan web service built from the `Dockerfile` (approved records in `/data/out` are lost whenever it restarts, redeploys, or spins down after 15 idle minutes), and `reply-desk-web`, a static site built from `web/`. The static site rewrites every path to `index.html` and sets the security headers. Its CSP `connect-src` names `https://reply-desk-api.onrender.com`; change it if Render gives the API a different URL. Both services deploy from `main` after CI passes. The steps are Phases 10–12 of `docs/deployment-plan.md`.

## Layout

```
src/support_reply/   the package: ingress, facts, pattern, compliance, draft, reviewer, graph, session, gate, cli, accept
data/                read-only corpus: five parsed scheme pages, 1,650 reviews, analyzed themes
tests/               pytest suite
docs/                problem statement, architecture, implementation plan, deployment plan
web/                 React frontend (Vite, Tailwind, Vitest, Playwright)
mcp-server/          MCP server for the approve step: Google Doc append, Gmail draft, no send (TypeScript)
design/stitch/       Stitch UI designs for the web frontend (reference only, not built)
scripts/             live-model verification, web fixture capture, the local stack check
Dockerfile           the API image Render builds
render.yaml          Render Blueprint: the API service and the static site
Makefile             local full-stack targets
```

## Status

The package is complete against `docs/implementation-plan.md`. The web app runs locally as a full stack, and CI runs on GitHub (Phases 0–8 of `docs/deployment-plan.md`). Both services are deployed on Render; the production checks are Phases 10–12. Approve also appends to a Google Doc and creates a Gmail draft over MCP once `REPLY_DESK_MCP=on` and the Google settings are in place.
