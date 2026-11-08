# Para Luego - Plan

Source of truth for scope, architecture and rules. Proof of concept: simple, but working end to end.

**Deadline:** Friday 2026-11-13 (Costa Rica time).

## 1. Problem

Interesting things (links, YouTube or social videos, photos, books, movies, products, GitHub repos) end up in a WhatsApp chat to self and get forgotten. Para Luego is a "save it for later" inbox: save an item in seconds, organize it by category, get a random **Daily** of things to revisit, and share an item later with specific people, with a note on why it made you think of them.

## 2. Users and behavior

- **User:** registers, logs in, saves items, sees the Daily, shares items.
- **Admin:** sees request status codes, simulates errors (cloud demo), reads incidents.
- **Recipients** do not use the app; they receive a WhatsApp message or whatever the user pastes.

## 3. Scope (v1)

- Registration and login (username + hashed password, session cookie). Basic security only.
- Item: URL, title, category, optional note, created date. Create, list, filter by category, delete.
- Default categories: **Leer, Ver, Comprar, Compartir, Proyectos**. Users can create their own.
- **Daily:** on the dashboard, one random item per category that has items. Purely random, no ranking.
- **Share via WhatsApp:** a button opens `https://wa.me/?text=<title, note, URL>`; the user picks the contact and sends.
- **Copy:** a button copies the same text (title, note, URL) to the clipboard, to paste into an email or anywhere else. Shows a short "Copied" confirmation.
- **Admin panel:** counts of 2xx/4xx/5xx by status code (404, 500, 503, 504), a "Simulate error" button, and the incident list.
- **Error routes:** backend `/api/simulate/500`, `/api/simulate/503`, `/api/simulate/504` (admin only) to demo alerts; the admin panel calls them through the frontend.

**Out of scope:** native/mobile app, browser extension, recipient accounts, sending messages through an API, email digests, recommendations by relevance, password reset.

## 4. Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI JSON API, SQLAlchemy 2, Alembic. The only service that talks to Postgres |
| Frontend | Python 3.12, its own FastAPI service rendering Jinja2 templates, plain CSS, a little vanilla JS (copy button). Talks to the backend only through the API, with `httpx` |
| API contract | `api/openapi.yaml` (OpenAPI 3.1), written by hand, **contract-first**: source of truth for every backend endpoint |
| Database | PostgreSQL 16 |
| Packaging | uv |
| Containers | Docker, Docker Compose |
| Telemetry | OpenTelemetry SDK (traces, metrics, logs) → OTel Collector |
| Storage/UI | Prometheus (metrics), Tempo (traces), Loki (logs), Grafana (dashboards + alerts) |
| On-call | Responder agent (Python) + MCP server (`mcp` SDK); LLM via any OpenAI-compatible API (default model `gpt-6-luna`) |
| CI/CD | GitHub Actions; `act` for local runs |
| Hosting | Render (dev + prod web services, Postgres); Neon as fallback database |

## 5. Architecture

```
Browser ──HTML──> Frontend (FastAPI + Jinja2) ──JSON API (api/openapi.yaml)──> Backend (FastAPI) ──SQL──> Postgres
                     │                                                            │
                     └──────────── OTLP (traces, metrics, logs, shared trace_id) ─┘
                     v
              OTel Collector ──> Prometheus / Tempo / Loki ──> Grafana
                                                                  │ alert webhook
                                                                  v
                                     On-call responder ──MCP──> tools (logs, metrics, health, code)
                                           │
                                           ├─ finds cause → push to main (CI → CD to dev) → PR main→prod (human merges)
                                           └─ no cause    → incident `needs-human`
```

### Frontend and backend

- **Two services.** The **backend** (`backend/`) is a JSON API under `/api/...` and owns the database. The **frontend** (`frontend/`) serves the HTML pages the user sees and gets all data from the backend API. The frontend never imports backend code and never touches the database.
- **Contract-first.** `api/openapi.yaml` is written before the code. A backend endpoint is added or changed by editing `api/openapi.yaml` first. A contract test fails if the backend's routes (paths, methods, status codes) don't match the file, and another fails if the frontend's API client calls anything the file doesn't define.
- **Auth across the split.** The backend issues a token on login and checks it on every protected endpoint (`Authorization: Bearer`). The token is a random opaque value; the backend stores only its hash (`auth_tokens`, 7-day expiry) and logout revokes it. The frontend keeps the token in an `HttpOnly`, `SameSite=Lax` cookie (`pl_session`, `Secure` outside local), so page scripts can't read it; it needs no signing because it is opaque. Passwords are hashed with the standard library's `hashlib.scrypt`. Details in #4.
- **Ports (local):** frontend `8000` (what users open), backend `8001`.
- **Packaging:** one root `pyproject.toml` and `uv.lock` (AGENTS.md rule), one `Dockerfile`; Compose and Render run two services from it with different commands.

### Cloud demo mode (Render)

Render runs the frontend, the backend and Postgres. The admin panel acts as a mini-Grafana with status-code counts kept by the backend (and served to the frontend through the API). "Simulate error" calls a backend error route; when the 5xx count crosses a threshold in a short window, the backend starts the responder in a background task. The incident and its diagnosis appear in the admin panel.

## 6. Observability

- **Key user journey:** *save an item* (frontend form → backend `POST /api/items`) - instrumented end to end across both services, one trace: frontend HTTP span, frontend → backend client span, backend HTTP span, DB span, a `items_saved_total` counter, a request-duration histogram, and structured JSON logs that carry the same `trace_id`.
- Every request: `http_requests_total{route, method, status}` with the **route template**, never the raw path.
- **No customer data in telemetry:** no usernames, URLs, titles or notes; only ids.
- Logs are JSON to stdout; the collector ships them to Loki. Grafana links a log line to its trace in Tempo by `trace_id`.

## 7. Alerting on user impact

Alerts measure what users feel, not CPU:

- **SaveItemFailing:** error rate of backend `POST /api/items` > 5% over 5 minutes.
- **HighServerErrors:** 5xx rate on any route > 5% over 5 minutes.

Each alert's webhook goes to the responder.

## 8. On-call responder

1. Wakes on an alert webhook (or the cloud threshold).
2. Opens a GitHub issue labeled `incident`.
3. Investigates with the MCP tools: `get_recent_logs`, `query_metrics`, `check_health`, `read_source_file`.
4. If the cause is found in code, writes a minimal fix plus a test and **pushes it directly to `main`**. CI runs; if green, CD deploys to **dev** and the alert resolves. It then opens a PR from `main` to `prod`; a human merges it to deploy to production.
5. If not, labels the incident `needs-human`, writes what it checked, and shows it in the admin panel.

Demo bug: a feature-flagged defect (for example `BUG_SAVE_ITEM=1` makes backend `POST /api/items` raise on long titles) that the responder can find and fix.

## 9. Testing (proof-of-concept level)

- **Unit:** Daily selection, WhatsApp/copy text building, password hashing, redaction.
- **Frontend:** rendered pages contain the expected elements; the login → save → list flow with FastAPI's test client.
- **Integration:** real Postgres in Docker; save and read back an item; categories per user.
- **Contract:** backend routes match `api/openapi.yaml`; the frontend API client only calls operations defined there. Frontend tests fake the backend from the contract, with no real network.
- `make test` runs all three.

## 10. CI/CD

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | every PR and push | lint, security (bandit, pip-audit), unit + frontend + integration tests, Docker build |
| `cd-dev.yml` | push to `main` after CI | build and push image tagged with the commit SHA, deploy to Render **dev** via deploy hook |
| `deploy-prod.yml` | push to `prod` (a human merged the PR from `main`) | deploy to Render **prod** |
| `rollback.yml` | manual (inputs `env`, `tag`) | redeploy a previous tag |

All workflows run locally with `make ci-local` (act), and in anyone's fork with their own secrets.

## 11. Backlog seed

Create one issue per line, labeled `backlog`. The PM grooms each before work starts.

1. Repo scaffold: uv project, FastAPI hello, Makefile, ruff, `.env.example`
2. Docker Compose with app + Postgres; `make up` / `make down`
3. Database models and Alembic migrations (users, categories, items, incidents)
4. Registration, login, logout
5. Items: create, list, filter by category, delete
6. Default categories + user-created categories
7. Daily dashboard (one random item per category)
8. Share via WhatsApp and Copy buttons
9. Test suites: unit, frontend, integration; `make test`
10. CI workflow (lint, security, tests, Docker build)
11. Render blueprint and CD to dev
12. Prod deploy via PR `main` → `prod`, and rollback workflow
13. OpenTelemetry instrumentation of the save-item journey + structured logs with trace_id
14. Observability stack in Compose (Collector, Prometheus, Tempo, Loki, Grafana) + dashboard
15. Alert rules on user impact + webhook to responder
16. MCP server with the on-call tools, redaction and audit log
17. On-call responder: incident issue, investigation, fix pushed to `main` + PR to `prod`, or `needs-human`
18. Admin panel: status-code counts, Simulate error, incidents (cloud demo mode)
19. Demo bug behind a flag + end-to-end incident demo
20. README: problem, usage, local run, deploy, demo script

Added after the seed (issue numbers 21 and 22 are PRs):

23. Split into frontend and backend services with the `api/openapi.yaml` contract. Do it before #3; #3-#8, #11, #13 and #18 build on the split.

## 12. Demo script

1. Open the public dev URL, register, save three items, see the Daily, share one via WhatsApp and copy another.
2. Locally: `make up`, open Grafana, show the save-item trace with its logs and metrics.
3. Turn on the demo bug, save a long title, watch the alert fire, the incident open, and the responder push a fix to `main`.
4. CI passes, CD deploys to dev, the alert resolves. Merge the responder's PR from `main` to `prod` to release.
