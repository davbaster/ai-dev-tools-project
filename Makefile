# Single entry point for every command. Plain `make` lists the targets.
# Compatible with GNU Make 3.81 (no .ONESHELL or newer features).

.DEFAULT_GOAL := help
.PHONY: help install dev-backend dev-frontend lint format security ci-local mcp mcp-audit responder-logs demo-on demo-off demo-local demo-local-clean test test-unit test-frontend test-contract test-integration migrate build up down logs image push-image wait-image retag promoted-sha deploy-hooks deploy-dev deploy-prod wait-deploy rollback promote-prod

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
	uv run bandit -r backend frontend telemetry oncall -ll -q
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

# Servidor MCP fuera de Docker: lee Loki, Prometheus y la app publicados en el host.
MCP_LOCAL_ENV = LOKI_URL=http://127.0.0.1:3100 PROMETHEUS_URL=http://127.0.0.1:9090 REPO_ROOT=. \
	HEALTH_URLS=local:frontend=http://127.0.0.1:8000/health,local:backend=http://127.0.0.1:8001/api/health

mcp: ## Run the MCP server locally on 127.0.0.1:8090 (needs MCP_TOKEN; `make up` runs it in Docker)
	$(MCP_LOCAL_ENV) MCP_HOST=127.0.0.1 MCP_AUDIT_LOG=$${MCP_AUDIT_LOG:-.mcp-audit.jsonl} uv run python -m oncall.mcp_server.server

demo-local: ## One-command local demo for reviewers: bug, alert, responder fix, draft prod PR; no GitHub (#69)
	uv run python demo/demo_local.py run

demo-local-clean: ## Stop the local demo and remove .demo/ and demo-output/
	uv run python demo/demo_local.py clean

demo-on: ## Restart the backend with the demo bug on (BUG_SAVE_ITEM=1, #19; see _docs/demo.md)
	BUG_SAVE_ITEM=1 docker compose up -d --no-deps --wait backend
	@echo "Demo bug ON: save a title longer than 40 characters at http://localhost:8000 and watch Grafana and the incident issues (_docs/demo.md)."

demo-off: ## Restart the backend with the demo bug off (BUG_SAVE_ITEM=0)
	BUG_SAVE_ITEM=0 docker compose up -d --no-deps --wait backend
	@echo "Demo bug OFF. If the responder enabled pushing for the demo, set RESPONDER_ALLOW_PUSH=false in .env and run make up."

responder-logs: ## Follow the on-call responder's logs (Ctrl+C to stop)
	docker compose logs -f oncall-agent

mcp-audit: ## Print the last 50 entries of the MCP server's audit log (Docker)
	docker compose exec -T mcp-server tail -n 50 /var/log/mcp/audit.jsonl

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

# --- Deploy a dev y prod (Render) --------------------------------------------
# CD dev (cd-dev.yml), Deploy prod (deploy-prod.yml) y Rollback (rollback.yml)
# llaman a estos targets con TAG=<commit SHA completo>.
# Los deploy hooks son secretos: vienen del entorno y nunca se imprimen.
IMAGE ?= ghcr.io/davbaster/ai-dev-tools-project
TAG ?=
ENV ?= dev
REF ?= HEAD
DEV_BACKEND_URL ?= https://para-luego-dev-backend.onrender.com
DEV_FRONTEND_URL ?= https://para-luego-dev-frontend.onrender.com
PROD_BACKEND_URL ?= https://para-luego-prod-backend.onrender.com
PROD_FRONTEND_URL ?= https://para-luego-prod-frontend.onrender.com
DEPLOY_WAIT_SECONDS ?= 600
IMAGE_WAIT_SECONDS ?= 900
IMAGE_REF_ENCODED = $(subst /,%2F,$(subst :,%3A,$(IMAGE):$(TAG)))

# Por entorno: URLs y nombre de las variables de los hooks
# (RENDER_DEV_BACKEND_DEPLOY_HOOK, RENDER_PROD_FRONTEND_DEPLOY_HOOK, ...).
BACKEND_URL_dev = $(DEV_BACKEND_URL)
FRONTEND_URL_dev = $(DEV_FRONTEND_URL)
HOOKS_dev = RENDER_DEV
BACKEND_URL_prod = $(PROD_BACKEND_URL)
FRONTEND_URL_prod = $(PROD_FRONTEND_URL)
HOOKS_prod = RENDER_PROD
BACKEND_HOOK = $$$(HOOKS_$(ENV))_BACKEND_DEPLOY_HOOK
FRONTEND_HOOK = $$$(HOOKS_$(ENV))_FRONTEND_DEPLOY_HOOK

CHECK_TAG = test -n "$(TAG)" || { echo "TAG is required, e.g. TAG=<commit sha>"; exit 1; }
CHECK_ENV = case "$(ENV)" in dev|prod) ;; *) echo "ENV must be dev or prod, not '$(ENV)'"; exit 1;; esac
CHECK_SHA = echo "$(TAG)" | grep -Eq '^[0-9a-f]{40}$$' || { echo "TAG must be a full 40-character commit SHA, not '$(TAG)'"; exit 1; }
CHECK_HOOKS = test -n "$(BACKEND_HOOK)" -a -n "$(FRONTEND_HOOK)" || { echo "Deploy hook variables for $(ENV) are not set"; exit 1; }
CHECK_IMAGE = docker manifest inspect $(IMAGE):$(TAG) >/dev/null 2>&1 || { echo "No image $(IMAGE):$(TAG) on the registry"; exit 1; }

image: ## Build the app image as IMAGE:TAG and IMAGE:dev with APP_VERSION=TAG (TAG=<sha> required)
	@$(CHECK_TAG)
	docker build --target app --build-arg APP_VERSION=$(TAG) -t $(IMAGE):$(TAG) -t $(IMAGE):dev .

push-image: ## Push IMAGE:TAG and IMAGE:dev (needs docker login to the registry)
	@$(CHECK_TAG)
	docker push $(IMAGE):$(TAG)
	docker push $(IMAGE):dev

wait-image: ## Wait until IMAGE:TAG is on the registry (IMAGE_WAIT_SECONDS, default 900)
	@$(CHECK_TAG)
	@echo "Waiting for $(IMAGE):$(TAG) on the registry"; \
	end=$$(( $$(date +%s) + $(IMAGE_WAIT_SECONDS) )); \
	until docker manifest inspect $(IMAGE):$(TAG) >/dev/null 2>&1; do \
		if [ $$(date +%s) -ge $$end ]; then echo "Timed out: no image $(IMAGE):$(TAG). Did CI and CD dev pass on main for that commit?"; exit 1; fi; \
		sleep 30; \
	done; \
	echo "OK: $(IMAGE):$(TAG)"

retag: ## Point IMAGE:ENV (dev or prod) at the existing IMAGE:TAG without rebuilding (needs docker login)
	@$(CHECK_ENV)
	@$(CHECK_TAG)
	docker buildx imagetools create -t $(IMAGE):$(ENV) $(IMAGE):$(TAG)

promoted-sha: ## Print the main commit that REF (default HEAD) on prod promotes: a merge commit's second parent, or REF after a fast-forward
	@set -- $$(git rev-list --parents -n 1 $(REF)); \
	if [ $$# -eq 3 ] && git merge-base --is-ancestor $$3 origin/main; then echo $$3; \
	elif [ $$# -eq 2 ] && git merge-base --is-ancestor $$1 origin/main; then echo $$1; \
	else echo "$(REF) is neither a merge commit of main nor a commit of main: merge the PR main -> prod with 'Create a merge commit'" >&2; exit 1; fi

# Llama a los dos hooks de ENV con imgURL=IMAGE:TAG (backend primero).
deploy-hooks:
	@$(CHECK_ENV)
	@$(CHECK_TAG)
	@$(CHECK_HOOKS)
	@echo "Deploying $(IMAGE):$(TAG) to the $(ENV) backend"
	@curl -fsS -X POST -o /dev/null "$(BACKEND_HOOK)&imgURL=$(IMAGE_REF_ENCODED)"
	@echo "Deploying $(IMAGE):$(TAG) to the $(ENV) frontend"
	@curl -fsS -X POST -o /dev/null "$(FRONTEND_HOOK)&imgURL=$(IMAGE_REF_ENCODED)"

deploy-dev: ## Deploy IMAGE:TAG to Render dev with the deploy hooks (RENDER_DEV_BACKEND_DEPLOY_HOOK, RENDER_DEV_FRONTEND_DEPLOY_HOOK)
	@"$(MAKE)" --no-print-directory deploy-hooks ENV=dev TAG=$(TAG) IMAGE=$(IMAGE)

deploy-prod: ## Deploy IMAGE:TAG to Render prod with the deploy hooks (RENDER_PROD_BACKEND_DEPLOY_HOOK, RENDER_PROD_FRONTEND_DEPLOY_HOOK)
	@"$(MAKE)" --no-print-directory deploy-hooks ENV=prod TAG=$(TAG) IMAGE=$(IMAGE)

wait-deploy: ## Wait until ENV's (dev or prod, default dev) health checks report version TAG (DEPLOY_WAIT_SECONDS, default 600)
	@$(CHECK_ENV)
	@$(CHECK_TAG)
	@for url in $(BACKEND_URL_$(ENV))/api/health $(FRONTEND_URL_$(ENV))/health; do \
		echo "Waiting for $$url to report $(TAG) ($(ENV))"; \
		end=$$(( $$(date +%s) + $(DEPLOY_WAIT_SECONDS) )); \
		until body=$$(curl -fsS --max-time 90 "$$url" 2>/dev/null) && \
			echo "$$body" | grep -q '"version":"$(TAG)"' && \
			echo "$$body" | grep -q '"deployment":"$(ENV)"'; do \
			if [ $$(date +%s) -ge $$end ]; then echo "Timed out: $$url does not report $(TAG) ($(ENV))"; exit 1; fi; \
			sleep 15; \
		done; \
		echo "OK: $$url"; \
	done

rollback: ## Redeploy an earlier image: make rollback ENV=<dev|prod> TAG=<full sha> (moves IMAGE:ENV, calls the hooks, waits)
	@$(CHECK_ENV)
	@$(CHECK_TAG)
	@$(CHECK_SHA)
	@$(CHECK_IMAGE)
	@$(CHECK_HOOKS)
	@echo "Rolling $(ENV) back to $(IMAGE):$(TAG)"
	@"$(MAKE)" --no-print-directory retag ENV=$(ENV) TAG=$(TAG) IMAGE=$(IMAGE)
	@"$(MAKE)" --no-print-directory deploy-hooks ENV=$(ENV) TAG=$(TAG) IMAGE=$(IMAGE)
	@"$(MAKE)" --no-print-directory wait-deploy ENV=$(ENV) TAG=$(TAG)

# Abre el PR de release main -> prod; David lo mergea con "Create a merge commit".
# Nunca mergea ni pushea a prod.
promote-prod: ## Open the release PR from main to prod with gh (prints the open one if it exists)
	@command -v gh >/dev/null 2>&1 || { echo "gh is not installed: https://cli.github.com"; exit 1; }
	@gh auth status >/dev/null 2>&1 || { echo "gh is not logged in: run gh auth login"; exit 1; }
	@git fetch -q origin main prod 2>/dev/null || { echo "Could not fetch origin/main and origin/prod: does the prod branch exist? (_docs/deploy.md, one-time setup)"; exit 1; }
	@open=$$(gh pr list --base prod --head main --state open --json url --jq '.[0].url'); \
	if [ -n "$$open" ]; then echo "A release PR is already open: $$open"; exit 0; fi; \
	if [ -z "$$(git rev-list origin/prod..origin/main)" ]; then echo "Nothing to promote: prod already has every commit of main"; exit 0; fi; \
	{ echo "Release to prod. Merge with **Create a merge commit**: Deploy prod then deploys the image dev ran for the head of main."; \
	  echo; echo "Commits:"; git log --no-merges --format='- %h %s' origin/prod..origin/main; } | \
	gh pr create --base prod --head main --title "Release: main to prod" --body-file -
