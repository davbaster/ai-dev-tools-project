# Single entry point for every command. Plain `make` lists the targets.
# Compatible with GNU Make 3.81 (no .ONESHELL or newer features).

.DEFAULT_GOAL := help
.PHONY: help install dev-backend dev-frontend lint format security ci-local test test-unit test-frontend test-contract test-integration migrate build up down logs image push-image deploy-dev wait-deploy

help: ## List every target
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-17s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies from uv.lock (fails if the lock is out of date)
	uv sync --locked

dev-backend: ## Run the backend API with reload on http://localhost:8001
	uv run uvicorn backend.main:app --reload --port 8001

dev-frontend: ## Run the frontend with reload on http://localhost:8000 (needs the backend)
	uv run uvicorn frontend.main:app --reload --port 8000

lint: ## Lint and check formatting with ruff
	uv run ruff check .
	uv run ruff format --check .

format: ## Format and auto-fix with ruff
	uv run ruff format .
	uv run ruff check --fix .

# Ignorar un hallazgo solo con su ID y el motivo, por ejemplo:
#   PIP_AUDIT_IGNORE = --ignore-vuln GHSA-xxxx  # sin arreglo publicado, no usamos la parte afectada
PIP_AUDIT_IGNORE =

security: ## Scan the code with bandit (medium+) and the installed dependencies with pip-audit
	uv run bandit -r backend frontend -ll -q
	uv run pip-audit --skip-editable --progress-spinner off $(PIP_AUDIT_IGNORE)

test: test-unit test-frontend test-contract test-integration ## Run every suite, in order; stops at the first failing one (needs Docker)

test-unit: ## Run the unit tests (no Docker needed)
	uv run pytest tests/unit

test-frontend: ## Run the frontend tests with a fake backend (no Docker needed)
	uv run pytest tests/frontend

test-contract: ## Check the backend and the frontend client against api/openapi.yaml (no Docker needed)
	uv run pytest tests/contract

# Postgres descartable: proyecto Compose propio, puerto TEST_DB_PORT, se borra
# siempre (también si fallan los tests). Con TEST_DATABASE_URL usa esa base.
# TEST_DB_HOST: dónde se ve el puerto publicado (dentro de `act` no es localhost).
TEST_DB_PORT ?= 5433
TEST_DB_HOST ?= localhost
TEST_DB = TEST_DB_PORT=$(TEST_DB_PORT) docker compose -f docker-compose.test.yml
TEST_DB_URL = postgresql://para_luego:para_luego_local@$(TEST_DB_HOST):$(TEST_DB_PORT)/para_luego_test

test-integration: ## Run the integration tests on a throwaway Postgres (TEST_DB_PORT, default 5433; or TEST_DATABASE_URL=<url>)
	@if [ -n "$(TEST_DATABASE_URL)" ]; then \
		TEST_DATABASE_URL="$(TEST_DATABASE_URL)" uv run pytest tests/integration; \
	else \
		$(TEST_DB) down -v --remove-orphans >/dev/null 2>&1; \
		$(TEST_DB) up -d --wait || { $(TEST_DB) down -v >/dev/null 2>&1; exit 1; }; \
		TEST_DATABASE_URL="$(TEST_DB_URL)" uv run pytest tests/integration; status=$$?; \
		$(TEST_DB) down -v; \
		exit $$status; \
	fi

migrate: ## Apply database migrations to DATABASE_URL
	uv run alembic upgrade head

build: ## Build the Docker images
	docker compose build

up: ## Start the local system in Docker and wait until it is healthy
	docker compose up -d --build --wait

down: ## Stop and remove the containers (the database volume is kept)
	docker compose down

logs: ## Follow the frontend and backend logs (Ctrl+C to stop)
	docker compose logs -f frontend backend

# act corre ci.yml en un contenedor con Docker; la base de test publica su
# puerto en el host, que desde ese contenedor es host.docker.internal.
ACT_IMAGE = catthehacker/ubuntu:act-latest

ci-local: ## Run .github/workflows/ci.yml locally with act (needs Docker and act)
	act pull_request -W .github/workflows/ci.yml -P ubuntu-latest=$(ACT_IMAGE) --pull=false --env TEST_DB_HOST=host.docker.internal

# --- Deploy a dev (Render) ---------------------------------------------------
# CD (.github/workflows/cd-dev.yml) llama a estos targets con TAG=<commit SHA>.
# Los deploy hooks son secretos: vienen del entorno y nunca se imprimen.
IMAGE ?= ghcr.io/davbaster/ai-dev-tools-project
TAG ?=
DEV_BACKEND_URL ?= https://para-luego-dev-backend.onrender.com
DEV_FRONTEND_URL ?= https://para-luego-dev-frontend.onrender.com
DEPLOY_WAIT_SECONDS ?= 600
IMAGE_REF_ENCODED = $(subst /,%2F,$(subst :,%3A,$(IMAGE):$(TAG)))

image: ## Build the app image as IMAGE:TAG and IMAGE:dev with APP_VERSION=TAG (TAG=<sha> required)
	@test -n "$(TAG)" || { echo "TAG is required, e.g. make image TAG=<commit sha>"; exit 1; }
	docker build --build-arg APP_VERSION=$(TAG) -t $(IMAGE):$(TAG) -t $(IMAGE):dev .

push-image: ## Push IMAGE:TAG and IMAGE:dev (needs docker login to the registry)
	@test -n "$(TAG)" || { echo "TAG is required"; exit 1; }
	docker push $(IMAGE):$(TAG)
	docker push $(IMAGE):dev

deploy-dev: ## Deploy IMAGE:TAG to Render dev with the deploy hooks (RENDER_DEV_BACKEND_DEPLOY_HOOK, RENDER_DEV_FRONTEND_DEPLOY_HOOK)
	@test -n "$(TAG)" || { echo "TAG is required"; exit 1; }
	@test -n "$$RENDER_DEV_BACKEND_DEPLOY_HOOK" -a -n "$$RENDER_DEV_FRONTEND_DEPLOY_HOOK" || { echo "Deploy hook variables are not set"; exit 1; }
	@echo "Deploying $(IMAGE):$(TAG) to the dev backend"
	@curl -fsS -X POST -o /dev/null "$$RENDER_DEV_BACKEND_DEPLOY_HOOK&imgURL=$(IMAGE_REF_ENCODED)"
	@echo "Deploying $(IMAGE):$(TAG) to the dev frontend"
	@curl -fsS -X POST -o /dev/null "$$RENDER_DEV_FRONTEND_DEPLOY_HOOK&imgURL=$(IMAGE_REF_ENCODED)"

wait-deploy: ## Wait until the dev backend and frontend health checks report version TAG (DEPLOY_WAIT_SECONDS, default 600)
	@test -n "$(TAG)" || { echo "TAG is required"; exit 1; }
	@for url in $(DEV_BACKEND_URL)/api/health $(DEV_FRONTEND_URL)/health; do \
		echo "Waiting for $$url to report $(TAG)"; \
		end=$$(( $$(date +%s) + $(DEPLOY_WAIT_SECONDS) )); \
		until curl -fsS --max-time 90 "$$url" 2>/dev/null | grep -q '"version":"$(TAG)"'; do \
			if [ $$(date +%s) -ge $$end ]; then echo "Timed out: $$url does not report $(TAG)"; exit 1; fi; \
			sleep 15; \
		done; \
		echo "OK: $$url"; \
	done
