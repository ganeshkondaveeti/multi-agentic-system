# Local full stack. `make dev` runs the API and the web app together; Ctrl-C stops both.

API_PORT ?= 8000
IMAGE ?= reply-desk-api
# Origins the Docker API accepts: `make preview-direct` (4173) and `make dev-web` (5173).
DOCKER_ORIGINS ?= http://localhost:4173,http://127.0.0.1:4173,http://localhost:5173,http://127.0.0.1:5173
# The Render deploy that `make e2e-prod` drives.
PROD_WEB ?= https://reply-desk-web.onrender.com
PROD_API ?= https://reply-desk-api.onrender.com

.PHONY: help install dev dev-api dev-web test e2e e2e-prod google-auth render-env stack-check docker-build docker-run preview-direct

help:
	@echo "install         uv sync, npm ci, and build the MCP server"
	@echo "dev             API on :$(API_PORT) with reload, web on :5173"
	@echo "dev-api         API only"
	@echo "dev-web         web only (proxies /api to :$(API_PORT))"
	@echo "test            pytest, Vitest, and the MCP server tests"
	@echo "e2e             Playwright against its own API (models off) and a preview build"
	@echo "e2e-prod        Playwright against the Render deploy (live models; E2E_ACCESS_CODE or ~/.reply-desk-access-code)"
	@echo "google-auth     sign in to Google for the MCP server; saves mcp-server/data/google-token.json"
	@echo "render-env      send the MCP settings and Google token to Render and redeploy (~/.render-api-key)"
	@echo "stack-check     Playwright against the production server command, cross-origin, then a PII grep"
	@echo "docker-run      build and run the production image on :$(API_PORT)"
	@echo "preview-direct  build the web app to call the API on :$(API_PORT) directly, and preview it on :4173"

install:
	uv sync
	cd web && npm ci
	cd mcp-server && npm ci && npm run build

dev:
	$(MAKE) -j2 dev-api dev-web

dev-api:
	uv run uvicorn support_reply.api.app:app --reload --reload-dir src --host 127.0.0.1 --port $(API_PORT)

dev-web:
	cd web && npm run dev

test:
	uv run pytest
	cd web && npm test
	cd mcp-server && npm test

# The Playwright config starts the API with REPLY_DESK_MODELS=off, builds and previews
# the web app, and stops both when the run ends.
e2e:
	cd web && npm run e2e

# The same suite against the deployed site. It makes live model calls and approves
# real (redacted) records. The access code comes from E2E_ACCESS_CODE or
# ~/.reply-desk-access-code (`make render-env` can save it), never from the repo.
e2e-prod:
	@code="$${E2E_ACCESS_CODE:-$$(cat ~/.reply-desk-access-code 2>/dev/null)}"; \
	test -n "$$code" || { echo "Set E2E_ACCESS_CODE, or run make render-env SAVE_ACCESS_CODE=1"; exit 1; }; \
	cd web && E2E_ACCESS_CODE="$$code" E2E_BASE_URL=$(PROD_WEB) E2E_API_URL=$(PROD_API) npm run e2e

# While the Google app is in Testing mode the token lasts 7 days: run both again then.
google-auth:
	uv run python scripts/google_auth.py

render-env:
	uv run python scripts/render_env.py $(if $(SAVE_ACCESS_CODE),--save-access-code)

stack-check:
	scripts/stack_check.sh

docker-build:
	docker build -t $(IMAGE) .

# Keys and settings come from .env when it exists. Records persist in the named volume,
# as they do on Render's disk.
docker-run: docker-build
	docker run --rm -p $(API_PORT):8000 $(if $(wildcard .env),--env-file .env) \
		-e REPLY_DESK_OUT_DIR=/data/out \
		-e ALLOWED_ORIGINS=$(DOCKER_ORIGINS) \
		-v reply-desk-out:/data/out \
		$(IMAGE)

preview-direct:
	cd web && VITE_API_BASE_URL=http://localhost:$(API_PORT) npm run build
	cd web && npx vite preview --host localhost --port 4173 --strictPort
