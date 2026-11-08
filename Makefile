# Single entry point for every command. Plain `make` lists the targets.
# Compatible with GNU Make 3.81 (no .ONESHELL or newer features).

.DEFAULT_GOAL := help
.PHONY: help install dev lint format test

help: ## List every target
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies from uv.lock (fails if the lock is out of date)
	uv sync --locked

dev: ## Run the app with reload on http://localhost:8000
	uv run uvicorn app.main:app --reload --port 8000

lint: ## Lint and check formatting with ruff
	uv run ruff check .
	uv run ruff format --check .

format: ## Format and auto-fix with ruff
	uv run ruff format .
	uv run ruff check --fix .

test: ## Run the test suite
	uv run pytest
