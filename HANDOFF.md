# HANDOFF

Snapshot of where the work stands, so any session or any LLM can continue. **Overwrite this file** after every decision and every finished piece of work. History goes in `_docs/log/`.

**Last updated:** 2026-11-08, by the orchestrator session (#23 implemented, QA PASS, PR #24 open)

## Current state

- **Architecture change (2026-11-08):** the app is split into `backend/` (JSON API under `/api/...`, owns Postgres) and `frontend/` (FastAPI + Jinja2 pages), talking only through `api/openapi.yaml` (contract-first). `_docs/plan.md` (sections 4, 5, 6, 9, 11), `AGENTS.md` (layout, commands, a new rules block) and `_docs/testing-guidelines.md` (contract layer) are updated. The code split is on PR #24 (not merged yet).
- Planning done. Agent docs written (`AGENTS.md`, `_docs/`).
- Docs committed and pushed to `davbaster/ai-dev-tools-project`.
- Labels from `_docs/process.md` created: `backlog`, `groomed`, `in-progress`, `qa-pass`, `qa-fail`, `incident`, `needs-human`.
- Issues #1-#20 created from the backlog seed (`_docs/plan.md` section 11), numbered in the same order. #2-#20 are labeled `backlog`.
- #1 (repo scaffold): groomed, approved by David (with `httpx`), implemented on `1-repo-scaffold`, **QA: PASS**, PR #21 merged into `main` by the orchestrator with David's OK (no CI yet). #1 is closed, branch deleted.
- #2 (Docker Compose with app + Postgres): groomed, approved by David, implemented on `2-docker-compose`, **QA: PASS**, PR #22 merged into `main` with David's OK (no CI yet). #2 is closed, branch deleted.
- #23 (split into frontend and backend with `api/openapi.yaml`): groomed, approved by David (with `httpx` runtime and `pyyaml` dev), implemented on `23-frontend-backend-split`, **QA: PASS** (labels `groomed`, `qa-pass`). PR #24 is open, not merged. Comments about the split posted on #3-#8, #11, #13, #18.
- Code on `main`: single `app/` (until PR #24 merges). On the #23 branch: `api/openapi.yaml` (`GET /api/health`), `backend/` (JSON API), `frontend/` (Jinja2 page + `httpx` client with an `OPERATIONS` table), 27 tests (unit, frontend, contract), Compose with `frontend` (8000) + `backend` (8001) + `db`. Makefile targets: `help`, `install`, `dev-backend`, `dev-frontend`, `lint`, `format`, `test`, `build`, `up`, `down`, `logs`.
- Deadline: **Friday 2026-11-13** (Costa Rica time). Peer reviews of three other projects are also required to pass.

## In progress

- PR #24 waits for David's OK to merge (no CI yet).

## Next up

1. David approves merging PR #24; the orchestrator merges it (closes #23).
2. PM grooms #3 (database models and Alembic migrations, in `backend/`). It will need new dependencies (SQLAlchemy, Alembic, a Postgres driver), which David must approve.

Order note: #23 goes before #3 even though its number is higher. #3-#8, #11, #13 and #18 depend on it.

## Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-11-08 | FastAPI + Jinja2 templates, Postgres, SQLAlchemy/Alembic, uv | Simple full stack in one language |
| 2026-11-08 | Docker Compose for the full local system, started with `make up` | Rubric: single command |
| 2026-11-08 | Render for dev and prod (web app + Postgres); full observability stack runs locally | Free tier cannot run Grafana/Tempo/Loki |
| 2026-11-08 | Cloud demo mode: admin panel shows status-code counts, has "Simulate error", and wakes the responder in-process | Demo the on-call flow without Grafana in the cloud |
| 2026-11-08 | WhatsApp share = `wa.me` link with text prefilled; user sends manually | No API needed |
| 2026-11-08 | Copy button next to WhatsApp copies title, note and URL to the clipboard | David wants to paste into email or anywhere |
| 2026-11-08 | Default categories Leer, Ver, Comprar, Compartir, Proyectos + user-created ones | User request |
| 2026-11-08 | LLM via any OpenAI-compatible API (default OpenAI) | Provider-agnostic |
| 2026-11-08 | Default `LLM_MODEL=gpt-6-luna` (OpenAI); overridable by env var | David's choice |
| 2026-11-08 | Build models: Opus 5.5 medium orchestrator, Sonnet 5.5 high engineer, Haiku 5.5 high PM and QA | Many integration-heavy tasks; strong orchestrator and engineer avoid rework before Friday |
| 2026-11-08 | Repo is `davbaster/ai-dev-tools-project` (already cloned) | Existing course repo |
| 2026-11-08 | Responder escalates with an incident marked `Needs human on-call` when it can't find the cause | User request |
| 2026-11-08 | Responder pushes fixes directly to `main` (CD deploys to dev); prod changes only via PR `main` → `prod` merged by David | David's decision: fast fixes in dev, human gate for prod |
| 2026-11-08 | Proof-of-concept testing: few tests, but unit + frontend + integration all exist | Course requires all three |
| 2026-11-08 | `AGENTS.md` is the only instruction file; `CLAUDE.md` points to it | Must work with any LLM tool |
| 2026-11-08 | #1 includes `GET /health` (`status` + `deployment`) and a minimal `make test` | Render and the MCP `check_health` tool need a health check later; AGENTS.md requires `make test` before done. #9 expands the test targets |
| 2026-11-08 | `DEPLOYMENT` allowed values `local`/`dev`/`prod`, default `local`; an invalid value stops startup | Fail fast on bad config instead of running in an unknown mode |
| 2026-11-08 | Makefile must work with GNU Make 3.81 | That is the `make` on David's Windows machine |
| 2026-11-08 | `httpx` approved as a dev dependency | David approved; FastAPI's `TestClient` needs it |
| 2026-11-08 | Roles played in this one session (no subagents) for #1 | Small task; QA comment says so |
| 2026-11-08 | #2: `make up` uses `docker compose up -d --build --wait`; works without `.env` (local-only defaults); Postgres data in a named volume that survives `make down`; host ports overridable with `APP_PORT`/`DB_PORT` | One command from a fresh clone; keep dev data between restarts |
| 2026-11-08 | #2 busy-port criterion reworded by the PM: Docker's bind error, not the exact Linux text | Docker Desktop on Windows prints "ports are not available ... bind" |
| 2026-11-08 | `DATABASE_URL` in compose uses the plain `postgresql://` scheme | The driver is chosen in #3, which can adjust the scheme |
| 2026-11-08 | Split the app into `frontend/` and `backend/` services that talk only through the API | David's requirement (he thought it was already in the plan) |
| 2026-11-08 | Frontend in Python: its own FastAPI + Jinja2 service calling the backend with `httpx` | David's choice; keeps "Python only", one toolchain, least delay before Friday |
| 2026-11-08 | `api/openapi.yaml` contract-first, hand-written; contract tests check backend routes and the frontend client against it | David's choice; the contract is the source of truth |
| 2026-11-08 | Backend issues a bearer token at login; the frontend keeps it in its own signed `HttpOnly` session cookie | The browser never sees the API token; details settled when grooming #4 |
| 2026-11-08 | One `pyproject.toml`, one `Dockerfile`, two services (frontend 8000, backend 8001) | AGENTS.md: single root `pyproject.toml`; simplest packaging |
| 2026-11-08 | PR #22 merged as is; #23 turns the single Compose `app` into `frontend` + `backend` | David's choice; #2 had already passed QA |
| 2026-11-08 | `httpx` runtime, `pyyaml` dev approved | David approved for #23 |
| 2026-11-08 | Frontend Compose service sets `dns_opt: timeout:1, attempts:1` | Docker DNS took ~4 s to fail for a stopped backend and `httpx`'s timeout doesn't cover DNS |
| 2026-11-08 | Frontend client lists its calls in an `OPERATIONS` table (operationId → method, path) | Lets the contract test check every call without generating code |
| 2026-11-08 | Merge PRs without CI until #10 adds it, on local `make lint` + `make test` and David's OK | No CI exists yet; David approved for #21 |

## Open questions

- Starlette warns that `httpx` with `TestClient` is deprecated in favor of `httpx2`. Switching would be a new dependency; decide later if it becomes an error.

- If Render's free tier allows only one free Postgres, use Neon for the second database? Decide with David when reaching issue 11 (Render blueprint).

## How to resume

Read `AGENTS.md`, this file and the newest `_docs/log/` file, then continue with "Next up".
