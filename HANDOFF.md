# HANDOFF

Snapshot of where the work stands, so any session or any LLM can continue. **Overwrite this file** after every decision and every finished piece of work. History goes in `_docs/log/`.

**Last updated:** 2026-11-12, by the orchestrator session (#16: PR #50 green CI + QA PASS, waiting for David's OK)

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
- Code on `main`: `api/openapi.yaml` (health, auth, category, item and daily operations), `backend/` (JSON API, `models.py`, `db.py`, `security.py`, `auth.py`, `defaults.py`, `categories.py`, `items.py`, `daily.py`), `migrations/` (`0001` users/categories/items/incidents, `0002` auth_tokens, `0003` default-categories backfill), `frontend/` (Spanish login/register/home (with "Tu Daily")/categories/items pages, `pl_session` cookie, `httpx` client with an `OPERATIONS` table, `share.py` + WhatsApp/Copiar buttons), 142 tests (unit 71, frontend 67, contract 4) + 51 integration tests (throwaway Postgres on 5433), CI in `.github/workflows/ci.yml`, CD to Render dev in `cd-dev.yml` + `render.yaml`, Compose with `frontend` (8000) + `backend` (8001, runs migrations before serving) + `db`. Makefile targets: `help`, `install`, `dev-backend`, `dev-frontend`, `lint`, `format`, `security`, `ci-local`, `image`, `push-image`, `deploy-dev`, `wait-deploy`, `test`, `test-unit`, `test-frontend`, `test-contract`, `test-integration`, `migrate`, `build`, `up`, `down`, `logs`.
- #4 (registration, login, logout): groomed, approved by David, implemented on `4-auth`, **QA: PASS**, PR #27 merged into `main` with David's OK (no CI yet). #4 is closed, branch deleted. It added contract operations `register`/`login`/`logout`/`getMe`, `backend/security.py` + `backend/auth.py`, migration `0002` (`auth_tokens`), Spanish login/register/home pages with the `pl_session` cookie, 60 tests + 21 integration tests. No new dependencies. Follow-up #26 (login rate limiting) filed as `backlog`; admin creation noted on #18.
- Since #4, `/` requires a session; the backend status line from #23 is on the login page.
- #6 (default + user-created categories): approved by David, implemented on `6-categories`, **QA: PASS**, PR #31 merged into `main` with David's OK (no CI yet). #6 is closed, branch deleted. It added contract operations `listCategories`/`createCategory`/`deleteCategory`, `backend/defaults.py` + `backend/categories.py`, migration `0003` (backfill), the `/categories` page; 71 tests + 32 integration tests.
- #5 (items): approved by David, implemented on `5-items`, **QA: PASS**, PR #32 merged into `main` with David's OK (no CI yet). #5 is closed, branch deleted. It added contract operations `createItem`/`listItems`/`deleteItem`, `backend/items.py`, the `/items` page (save form, category filter, list, delete); 84 tests + 47 integration tests. Follow-ups filed as `backlog`: #28 (rename a category), #29 (edit/move an item), #30 (fetch the title automatically).
- #7 (Daily dashboard): groomed, approved by David, implemented on `7-daily`, **QA: PASS**, PR #34 merged into `main` with David's OK (no CI yet). #7 is closed, branch deleted. It adds contract operation `getDaily` (`GET /api/daily` → `Daily {date, items}`), `backend/daily.py` (pure `pick_daily` seeded with `user_id:date`, Costa Rica day at fixed UTC-6), the "Tu Daily" section on `/`; 93 tests + 51 integration tests. Follow-up #33 (reshuffle on demand) filed as `backlog`.
- #8 (Share via WhatsApp and Copy): groomed, approved by David, implemented on `8-share`, **QA: PASS**, PR #35 merged into `main` with David's OK (no CI yet). #8 is closed, branch deleted. 106 tests + 51 integration tests. Frontend only, no backend or contract change: `frontend/share.py` builds the text (title, note if any, URL; URL once if the title is the URL) and the `wa.me` link; a shared partial puts both buttons on `/items` and on the Daily cards; one small vanilla script copies from an escaped attribute and shows "Copiado". No follow-ups filed. QA finding: WhatsApp's web page shows 4-byte emoji (🎵) as �; our link is valid UTF-8, nothing to fix on our side.
- #9 (test suites): groomed, approved by David, implemented on `9-test-suites`, **QA: PASS**, PR #36 merged into `main` with David's OK (no CI yet). #9 is closed, branch deleted. Targets: `test-unit`, `test-frontend`, `test-contract`, and `test-integration` with a throwaway Postgres (own Compose project, port 5433 / `TEST_DB_PORT`, removed even on failure, `TEST_DATABASE_URL` override); `make test` runs all four (so it now needs Docker); one missing frontend flow test (login → save → list); `AGENTS.md` and testing-guidelines updated. `make test`: unit 46, frontend 57, contract 4, integration 51.
- #10 (CI workflow): groomed, approved by David (with `bandit` and `pip-audit`), implemented on `10-ci`, **QA: PASS**, PR #37 merged into `main` with David's OK and green CI. #10 is closed, branch deleted. CI on the push to `main` green (run 42515414360). `make security` (bandit on backend/frontend, medium+; pip-audit), `.github/workflows/ci.yml` (one job: `make install`, `lint`, `security`, `test`, `build`; on every PR and pushes to `main`/`prod`; no secrets; pinned actions; concurrency cancel), `make ci-local` with `act` (`TEST_DB_HOST=host.docker.internal`), docs say PRs merge only with green CI + QA PASS. Red-path check: throwaway PR #38 failed at Lint, later steps skipped; closed and branch deleted.
- #11 (Render + CD to dev): approved by David (dev on Render's free Postgres, prod on Neon in #12), PRs #39 (blueprint + CD), #40 (frontend retries) and #41 (the browser wakes the backend) merged with green CI and David's OK. **QA: PASS**, #11 closed. Dev: frontend https://para-luego-dev-frontend.onrender.com, backend https://para-luego-dev-backend.onrender.com; every green push to `main` deploys there (`cd-dev.yml`). Free-plan lesson: calls from one Render service never wake a sleeping free service, so the browser wakes the backend (`BACKEND_PUBLIC_URL`, `_wake.html`). See `_docs/deploy.md`. **Dev database expires 2026-12-08.**
- #12 (prod deploy, rollback, promote-prod): approved by David, PRs #44 and #45 merged with green CI and David's OK; first release PR #46 merged by David. **QA: PASS**, #12 closed. **Prod:** frontend https://para-luego-prod-frontend.onrender.com, backend https://para-luego-prod-backend.onrender.com, database on Neon free; Blueprint `render.prod.yaml` on branch `prod`. Release: `make promote-prod` → David merges with **Create a merge commit** → Deploy prod deploys the image dev ran. Rollback: the Rollback workflow or `make rollback ENV TAG`. `prod` is protected (PR + CI check); `main` isn't. QA test users: `qa12proda2d876` (prod), `qa12deva2d876` (dev). Follow-ups #42 (rollback across migrations), #43 (dev database expiry).
- #13 (OpenTelemetry + JSON logs): approved by David with six OpenTelemetry dependencies, PR #47 merged with green CI and David's OK. **QA: PASS**, #13 closed. Shared `telemetry/` package; one trace frontend → backend → DB; JSON logs with trace ids on dev (checked in Render's logs: frontend `POST /items` and backend `item saved` share the trace id). No export on Render (no `OTEL_EXPORTER_OTLP_ENDPOINT`). Test user `qa13devac633c` on dev.
- #14 (local observability): approved by David, PR #48 merged with green CI and David's OK. **QA: PASS**, #14 closed. `make up` also runs the OTel Collector, Prometheus, Tempo, Loki and Grafana (http://localhost:3000, dashboard "Para Luego"); see `observability/README.md`. Dev on Render unchanged (reports `b426e20`).
- #15 (alerts + webhook): approved by David, PR #49 merged with green CI and David's OK. **QA: PASS**, #15 closed. Grafana rules SaveItemFailing and HighServerErrors; webhook to `ALERT_WEBHOOK_URL` (default `http://oncall-agent:8080/alerts`) with a bearer token; payload and how to trigger them in `observability/README.md`. Dev reports `2a880c1`.
- `/` now calls `getMe` and then `getDaily`; frontend test fakes that serve `/` must answer `/api/daily`.
- Deadline: **Friday 2026-11-13** (Costa Rica time). Peer reviews of three other projects are also required to pass.

## In progress

- #16 (MCP server): approved by David with `mcp`. Implemented on `16-mcp-server`, **PR #50** (`Closes #16`), CI green, **`## QA: PASS`** on #16 (local live QA over HTTP with the SDK client). **Waiting for David's OK to merge.**
- Adds `oncall/mcp_server/` (server, tools, redact, guards, audit, README), Compose `mcp-server` at 127.0.0.1:8090 with bearer `MCP_TOKEN`, `make mcp`, `make mcp-audit`; Dockerfile copies `oncall/` and creates `/var/log/mcp` for `appuser`.

## Next up

1. David's OK → merge PR #50.
2. Groom #17 (responder): receives the #15 webhook at `http://oncall-agent:8080/alerts` (bearer `ALERT_WEBHOOK_TOKEN`), opens the `incident` issue, investigates through the MCP server (`http://mcp-server:8090/mcp`, bearer `MCP_TOKEN`), pushes a fix to `main` + PR to `prod` or labels `needs-human`. Needs an LLM (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`) and GitHub access: dependency and secrets decisions for David.
3. Then #18 (admin panel), #19 (demo bug), #20 (README). #43 before 2026-12-08.
- Deadline Friday 2026-11-13 (Costa Rica). Don't push to `main` while waiting for services to sleep.

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
| 2026-11-08 | #10 (approved by David, with `bandit` and `pip-audit`): CI is one job calling the make targets; runs on every PR and on pushes to `main`/`prod`; no branch protection on `main` (the responder pushes there) | Same commands locally and in CI; no duplicate runs; matches the on-call design |
| 2026-11-12 | OpenTelemetry api, sdk, exporter-otlp-proto-http, instrumentation fastapi/httpx/sqlalchemy approved | David approved for #13 |
| 2026-11-12 | Telemetry setup in a shared top-level `telemetry/` package (copied by the Dockerfile) | Same code for both services without the frontend importing `backend/` |
| 2026-11-12 | DB spans with the SQLAlchemy package's `EngineTracer` per engine, not `SQLAlchemyInstrumentor().instrument()` | The instrumentor declares support only below SQLAlchemy 2.1 and its global patch imports asyncio, which needs `greenlet` |
| 2026-11-12 | Own request metrics and access log (route template, `unmatched` for 404s); the instrumentations' HTTP metrics and uvicorn's access log off; `httpx` logger at WARNING | Raw paths, client IPs and full URLs must never reach telemetry |
| 2026-11-12 | #14: logs reach Loki through the collector's `file_log` receiver on Docker's json-file logs (read-only mount, collector as root); Loki label is `service_name` | David's choice over Alloy + Docker socket; Loki's OTLP ingestion names it `service_name` |
| 2026-11-12 | Observability UIs on 127.0.0.1, Grafana anonymous Editor locally, no volumes; `OTEL_METRIC_EXPORT_INTERVAL=10000` in Compose | Local demo only; dashboards update within seconds |
| 2026-11-12 | #15: Grafana alerting from files (no Alertmanager); webhook to `ALERT_WEBHOOK_URL` with a bearer token; 30 s / 1 min / no data = OK | David approved; one tool already running; the responder can reject anything not from Grafana |
| 2026-11-12 | `mcp` 2.3.0 approved (MCPServer, Streamable HTTP, stateless) | David approved for #16; plan names the SDK |
| 2026-11-12 | MCP audit through the SDK's request middleware + an ASGI auth middleware; client = User-Agent | Audits every tools/call, even those rejected by argument validation, and denied requests; stateless HTTP has no session client info |
| 2026-11-11 | `main` stays unprotected; `prod` requires a PR (0 approvals) and the CI check | The responder pushes fixes straight to `main`; David merges his own release PRs |
| 2026-11-08 | #12 (approved by David): prod in its own Blueprint `render.prod.yaml` on branch `prod`; deploy-prod deploys the promoted `main` image (no rebuild) and moves `:prod` | Render's `imgURL` affects only one deploy and later deploys use the stored tag; a Blueprint on `main` would change prod on every merge to `main` and syncs ignore `sync: false` |
| 2026-11-08 | #11: the browser wakes the sleeping Render backend (`BACKEND_PUBLIC_URL`); server-side retries only 5 s | Render's logs showed calls from the frontend service never wake a free backend; only internet traffic does |
| 2026-11-08 | ~~Merge PRs without CI until #10~~ Closed: since #10 (merged), PRs merge only with green CI + QA PASS + David's OK | CI exists now (`.github/workflows/ci.yml`) |

## Open questions

- Starlette warns that `httpx` with `TestClient` is deprecated in favor of `httpx2`. Switching would be a new dependency; decide later if it becomes an error.

- Database for prod: decided — dev on Render's free Postgres, prod on Neon free (#12). David approved with #11.

## How to resume

Read `AGENTS.md`, this file and the newest `_docs/log/` file, then continue with "Next up".
