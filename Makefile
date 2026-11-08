# Single entry point for every command. Plain `make` lists the targets.
# Compatible with GNU Make 3.81 (no .ONESHELL or newer features).

.DEFAULT_GOAL := help
.PHONY: help install dev-backend dev-frontend lint format test test-integration migrate build up down logs

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

test: ## Run the unit, frontend and contract tests (no Docker needed)
	uv run pytest --ignore=tests/integration

test-integration: ## Run the integration tests on Postgres (TEST_DATABASE_URL, default: the Compose db)
	uv run pytest tests/integration

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
