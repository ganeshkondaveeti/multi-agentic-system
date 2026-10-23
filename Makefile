# Local full stack. `make dev` runs the API and the web app together; Ctrl-C stops both.

API_PORT ?= 8000
IMAGE ?= reply-desk-api
# Origins the Docker API accepts: `make preview-direct` (4173) and `make dev-web` (5173).
DOCKER_ORIGINS ?= http://localhost:4173,http://127.0.0.1:4173,http://localhost:5173,http://127.0.0.1:5173

.PHONY: help install dev dev-api dev-web test e2e stack-check docker-build docker-run preview-direct

help:
	@echo "install         uv sync and npm ci"
	@echo "dev             API on :$(API_PORT) with reload, web on :5173"
	@echo "dev-api         API only"
	@echo "dev-web         web only (proxies /api to :$(API_PORT))"
	@echo "test            pytest and Vitest"
	@echo "e2e             Playwright against its own API (models off) and a preview build"
	@echo "stack-check     Playwright against the production server command, cross-origin, then a PII grep"
	@echo "docker-run      build and run the production image on :$(API_PORT)"
	@echo "preview-direct  build the web app to call the API on :$(API_PORT) directly, and preview it on :4173"

install:
	uv sync
	cd web && npm ci

dev:
	$(MAKE) -j2 dev-api dev-web

dev-api:
	uv run uvicorn support_reply.api.app:app --reload --reload-dir src --host 127.0.0.1 --port $(API_PORT)

dev-web:
	cd web && npm run dev

test:
	uv run pytest
	cd web && npm test

# The Playwright config starts the API with REPLY_DESK_MODELS=off, builds and previews
# the web app, and stops both when the run ends.
e2e:
	cd web && npm run e2e

stack-check:
	scripts/stack_check.sh

docker-build:
	docker build -t $(IMAGE) .

# Keys and settings come from .env when it exists. Records persist in the named volume,
# as they do on Railway's.
docker-run: docker-build
	docker run --rm -p $(API_PORT):8000 $(if $(wildcard .env),--env-file .env) \
		-e REPLY_DESK_OUT_DIR=/data/out \
		-e ALLOWED_ORIGINS=$(DOCKER_ORIGINS) \
		-v reply-desk-out:/data/out \
		$(IMAGE)

preview-direct:
	cd web && VITE_API_BASE_URL=http://localhost:$(API_PORT) npm run build
	cd web && npx vite preview --host localhost --port 4173 --strictPort
