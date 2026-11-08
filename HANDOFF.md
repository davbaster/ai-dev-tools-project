# HANDOFF

Snapshot of where the work stands, so any session or any LLM can continue. **Overwrite this file** after every decision and every finished piece of work. History goes in `_docs/log/`.

**Last updated:** 2026-11-08, by the orchestrator session (#10 groomed, waiting for David's review)

## Current state

- **Architecture change (2026-11-08):** the app is split into `backend/` (JSON API under `/api/...`, owns Postgres) and `frontend/` (FastAPI + Jinja2 pages), talking only through `api/openapi.yaml` (contract-first). `_docs/plan.md` (sections 4, 5, 6, 9, 11), `AGENTS.md` (layout, commands, a new rules block) and `_docs/testing-guidelines.md` (contract layer) are updated. The code split is merged (PR #24).
- Planning done. Agent docs written (`AGENTS.md`, `_docs/`).
- Docs committed and pushed to `davbaster/ai-dev-tools-project`.
- Labels from `_docs/process.md` created: `backlog`, `groomed`, `in-progress`, `qa-pass`, `qa-fail`, `incident`, `needs-human`.
- Issues #1-#20 created from the backlog seed (`_docs/plan.md` section 11), numbered in the same order. #2-#20 are labeled `backlog`.
- #1 (repo scaffold): groomed, approved by David (with `httpx`), implemented on `1-repo-scaffold`, **QA: PASS**, PR #21 merged into `main` by the orchestrator with David's OK (no CI yet). #1 is closed, branch deleted.
- #2 (Docker Compose with app + Postgres): groomed, approved by David, implemented on `2-docker-compose`, **QA: PASS**, PR #22 merged into `main` with David's OK (no CI yet). #2 is closed, branch deleted.
- #23 (split into frontend and backend with `api/openapi.yaml`): groomed, approved by David (with `httpx` runtime and `pyyaml` dev), implemented on `23-frontend-backend-split`, **QA: PASS**, PR #24 merged into `main` with David's OK (no CI yet). #23 is closed, branch deleted. Comments about the split posted on #3-#8, #11, #13, #18.
- #3 (database models and Alembic migrations): groomed, approved by David (with `sqlalchemy`, `alembic`, `psycopg[binary]`), implemented on `3-db-models-migrations`, **QA: PASS**, PR #25 merged into `main` with David's OK (no CI yet). #3 is closed, branch deleted.
- Code on `main`: `api/openapi.yaml` (health, auth, category, item and daily operations), `backend/` (JSON API, `models.py`, `db.py`, `security.py`, `auth.py`, `defaults.py`, `categories.py`, `items.py`, `daily.py`), `migrations/` (`0001` users/categories/items/incidents, `0002` auth_tokens, `0003` default-categories backfill), `frontend/` (Spanish login/register/home (with "Tu Daily")/categories/items pages, `pl_session` cookie, `httpx` client with an `OPERATIONS` table, `share.py` + WhatsApp/Copiar buttons), 107 tests (unit 46, frontend 57, contract 4) + 51 integration tests (throwaway Postgres on 5433), Compose with `frontend` (8000) + `backend` (8001, runs migrations before serving) + `db`. Makefile targets: `help`, `install`, `dev-backend`, `dev-frontend`, `lint`, `format`, `test`, `test-unit`, `test-frontend`, `test-contract`, `test-integration`, `migrate`, `build`, `up`, `down`, `logs`.
- #4 (registration, login, logout): groomed, approved by David, implemented on `4-auth`, **QA: PASS**, PR #27 merged into `main` with David's OK (no CI yet). #4 is closed, branch deleted. It added contract operations `register`/`login`/`logout`/`getMe`, `backend/security.py` + `backend/auth.py`, migration `0002` (`auth_tokens`), Spanish login/register/home pages with the `pl_session` cookie, 60 tests + 21 integration tests. No new dependencies. Follow-up #26 (login rate limiting) filed as `backlog`; admin creation noted on #18.
- Since #4, `/` requires a session; the backend status line from #23 is on the login page.
- #6 (default + user-created categories): approved by David, implemented on `6-categories`, **QA: PASS**, PR #31 merged into `main` with David's OK (no CI yet). #6 is closed, branch deleted. It added contract operations `listCategories`/`createCategory`/`deleteCategory`, `backend/defaults.py` + `backend/categories.py`, migration `0003` (backfill), the `/categories` page; 71 tests + 32 integration tests.
- #5 (items): approved by David, implemented on `5-items`, **QA: PASS**, PR #32 merged into `main` with David's OK (no CI yet). #5 is closed, branch deleted. It added contract operations `createItem`/`listItems`/`deleteItem`, `backend/items.py`, the `/items` page (save form, category filter, list, delete); 84 tests + 47 integration tests. Follow-ups filed as `backlog`: #28 (rename a category), #29 (edit/move an item), #30 (fetch the title automatically).
- #7 (Daily dashboard): groomed, approved by David, implemented on `7-daily`, **QA: PASS**, PR #34 merged into `main` with David's OK (no CI yet). #7 is closed, branch deleted. It adds contract operation `getDaily` (`GET /api/daily` → `Daily {date, items}`), `backend/daily.py` (pure `pick_daily` seeded with `user_id:date`, Costa Rica day at fixed UTC-6), the "Tu Daily" section on `/`; 93 tests + 51 integration tests. Follow-up #33 (reshuffle on demand) filed as `backlog`.
- #8 (Share via WhatsApp and Copy): groomed, approved by David, implemented on `8-share`, **QA: PASS**, PR #35 merged into `main` with David's OK (no CI yet). #8 is closed, branch deleted. 106 tests + 51 integration tests. Frontend only, no backend or contract change: `frontend/share.py` builds the text (title, note if any, URL; URL once if the title is the URL) and the `wa.me` link; a shared partial puts both buttons on `/items` and on the Daily cards; one small vanilla script copies from an escaped attribute and shows "Copiado". No follow-ups filed. QA finding: WhatsApp's web page shows 4-byte emoji (🎵) as �; our link is valid UTF-8, nothing to fix on our side.
- #9 (test suites): groomed, approved by David, implemented on `9-test-suites`, **QA: PASS**, PR #36 merged into `main` with David's OK (no CI yet). #9 is closed, branch deleted. Targets: `test-unit`, `test-frontend`, `test-contract`, and `test-integration` with a throwaway Postgres (own Compose project, port 5433 / `TEST_DB_PORT`, removed even on failure, `TEST_DATABASE_URL` override); `make test` runs all four (so it now needs Docker); one missing frontend flow test (login → save → list); `AGENTS.md` and testing-guidelines updated. `make test`: unit 46, frontend 57, contract 4, integration 51.
- #10 (CI workflow): **groomed** by the PM (label `groomed`). `make security` (bandit on backend/frontend, medium+; pip-audit), `.github/workflows/ci.yml` (one job: `make install`, `lint`, `security`, `test`, `build`; on every PR and pushes to `main`/`prod`; no secrets; pinned actions; concurrency cancel), `make ci-local` with `act` (maybe a `TEST_DB_HOST` override), docs say PRs merge only with green CI + QA PASS. New dev dependencies `bandit`, `pip-audit` pending David's approval. Waiting for David's review.
- `/` now calls `getMe` and then `getDaily`; frontend test fakes that serve `/` must answer `/api/daily`.
- Deadline: **Friday 2026-11-13** (Costa Rica time). Peer reviews of three other projects are also required to pass.

## In progress

- Nothing.

## Next up

1. David reviews the groomed #10 (approving it approves `bandit` and `pip-audit` as dev dependencies).
2. On approval: implement #10 on branch `10-ci`, run `make lint`, `make security`, `make test`, `make ci-local`, open the PR (CI runs on it), QA, post `## QA: PASS`/`FAIL`. Merge only with David's OK.

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
| 2026-11-08 | #3 schema: categories unique per `(user_id, name)`; deleting a user cascades; deleting a category with items is refused; incident `status` limited to `open`/`resolved`/`needs_human`; timestamps `timestamptz` | Rules the later tasks rely on, enforced by the database |
| 2026-11-08 | Backend runs migrations before serving in Compose; plain `postgresql://` URLs are switched to psycopg by the backend | `make up` stays one command; Compose and Render give plain URLs |
| 2026-11-08 | Integration tests use a separate `para_luego_test` database; since #9 on a throwaway Postgres (port 5433), `TEST_DATABASE_URL` overrides | Tests must never wipe dev data |
| 2026-11-08 | `sqlalchemy`, `alembic`, `psycopg[binary]` approved | David approved for #3 |
| 2026-11-08 | `items.category_id` FK uses `NO ACTION`, not `RESTRICT` (criterion reworded by the PM) | `RESTRICT` is checked immediately and could break the user-delete cascade; `NO ACTION` still refuses deleting a category with items |
| 2026-11-08 | Database connect timeout 3 s | psycopg tries IPv6 and IPv4 for `localhost`; 5 s made an unreachable db take ~12 s |
| 2026-11-08 | #4 auth: passwords with stdlib `hashlib.scrypt`; opaque tokens (`secrets`) stored hashed in `auth_tokens`, 7-day expiry, revoked on logout | No new dependency; revocable sessions |
| 2026-11-08 | Frontend cookie `pl_session` holds the opaque token: `HttpOnly`, `SameSite=Lax`, `Secure` outside local; no signing | Opaque token needs no signing; avoids a signing library. Plan section 5 updated |
| 2026-11-08 | Usernames trimmed and lowercased, 3-50 chars `[a-z0-9._-]`; passwords 8-128 chars; same 401 for unknown user and wrong password | Case-insensitive uniqueness; don't reveal which usernames exist |
| 2026-11-08 | UI text in Spanish | Default categories are Spanish; David is in Costa Rica |
| 2026-11-08 | Backend contract test lists routes with FastAPI's `get_openapi` | FastAPI 0.162 nests included routers, so scanning `app.routes` missed them; the YAML stays the contract |
| 2026-11-08 | Frontend parses form bodies with `urllib.parse` | FastAPI `Form` needs `python-multipart`, a new dependency |
| 2026-11-08 | Backend 422 handler returns only `{field, message}` in Spanish | FastAPI's default echoes the input, including passwords |
| 2026-11-08 | Implement #6 (categories) before #5 (items) | Every item needs a category; new users have none until #6 |
| 2026-11-08 | #5: only `http(s)://` URLs (max 2048); empty title becomes the URL; another user's category gets the same 422 as a missing one | Blocks `javascript:` links; saving stays fast; no id probing |
| 2026-11-08 | #6: defaults created in the registration transaction; migration `0003` backfills existing users; names unique per user ignoring case; deleting a category with items is 409 | Matches the schema from #3; no half-created users |
| 2026-11-08 | #7 Daily (approved by David): stable for the whole day, seeded with user id + local date; day changes at midnight Costa Rica (fixed UTC-6, no `zoneinfo`); computed per request, nothing stored | A Daily that changes on every refresh isn't a "Daily"; fixed offset avoids needing `tzdata` on Windows; no migration |
| 2026-11-08 | #8 (approved by David): share text built in the frontend from the `Item` it already gets; format title / note / URL one per line; buttons on `/items` and the Daily; text in an escaped HTML attribute, read by one vanilla script | No API change needed; avoids user data inside `<script>`; plan section 3 and testing guidelines ask for both pages |
| 2026-11-08 | #9 (approved by David): `make test` runs every suite including integration on a throwaway Postgres (port 5433); per-suite targets need no Docker | AGENTS.md and plan section 9 already promise it; CI (#10) calls the same targets; tests never touch dev data |
| 2026-11-08 | #10 (proposed, pending David's review): CI is one job calling the make targets; runs on every PR and on pushes to `main`/`prod`; no branch protection on `main` (the responder pushes there) | Same commands locally and in CI; no duplicate runs; matches the on-call design |
| 2026-11-08 | Merge PRs without CI until #10 adds it, on local `make lint` + `make test` and David's OK | No CI exists yet; David approved for #21 |

## Open questions

- Starlette warns that `httpx` with `TestClient` is deprecated in favor of `httpx2`. Switching would be a new dependency; decide later if it becomes an error.

- If Render's free tier allows only one free Postgres, use Neon for the second database? Decide with David when reaching issue 11 (Render blueprint).

## How to resume

Read `AGENTS.md`, this file and the newest `_docs/log/` file, then continue with "Next up".
