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
- **Error routes:** `/simulate/500`, `/simulate/503`, `/simulate/504` (admin only) to demo alerts.

**Out of scope:** native/mobile app, browser extension, recipient accounts, sending messages through an API, email digests, recommendations by relevance, password reset.

## 4. Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic |
| Frontend | Jinja2 templates, plain CSS, a little vanilla JS (copy button) |
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
Browser ──HTTP──> FastAPI app ──SQL──> Postgres
                     │ OTLP (traces, metrics, logs, shared trace_id)
                     v
              OTel Collector ──> Prometheus / Tempo / Loki ──> Grafana
                                                                  │ alert webhook
                                                                  v
                                     On-call responder ──MCP──> tools (logs, metrics, health, code)
                                           │
                                           ├─ finds cause → push to main (CI → CD to dev) → PR main→prod (human merges)
                                           └─ no cause    → incident `needs-human`
```

### Cloud demo mode (Render)

Render runs only the app and Postgres. The admin panel acts as a mini-Grafana with status-code counts kept by the app. "Simulate error" calls an error route; when 5xx count crosses a threshold in a short window, the app starts the responder in a background task. The incident and its diagnosis appear in the admin panel.

## 6. Observability

- **Key user journey:** *save an item* (`POST /items`) - instrumented end to end: HTTP span, DB span, a `items_saved_total` counter, a request-duration histogram, and structured JSON logs that carry the same `trace_id`.
- Every request: `http_requests_total{route, method, status}` with the **route template**, never the raw path.
- **No customer data in telemetry:** no usernames, URLs, titles or notes; only ids.
- Logs are JSON to stdout; the collector ships them to Loki. Grafana links a log line to its trace in Tempo by `trace_id`.

## 7. Alerting on user impact

Alerts measure what users feel, not CPU:

- **SaveItemFailing:** error rate of `POST /items` > 5% over 5 minutes.
- **HighServerErrors:** 5xx rate on any route > 5% over 5 minutes.

Each alert's webhook goes to the responder.

## 8. On-call responder

1. Wakes on an alert webhook (or the cloud threshold).
2. Opens a GitHub issue labeled `incident`.
3. Investigates with the MCP tools: `get_recent_logs`, `query_metrics`, `check_health`, `read_source_file`.
4. If the cause is found in code, writes a minimal fix plus a test and **pushes it directly to `main`**. CI runs; if green, CD deploys to **dev** and the alert resolves. It then opens a PR from `main` to `prod`; a human merges it to deploy to production.
5. If not, labels the incident `needs-human`, writes what it checked, and shows it in the admin panel.

Demo bug: a feature-flagged defect (for example `BUG_SAVE_ITEM=1` makes `POST /items` raise on long titles) that the responder can find and fix.

## 9. Testing (proof-of-concept level)

- **Unit:** Daily selection, WhatsApp/copy text building, password hashing, redaction.
- **Frontend:** rendered pages contain the expected elements; the login → save → list flow with FastAPI's test client.
- **Integration:** real Postgres in Docker; save and read back an item; categories per user.
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

## 12. Demo script

1. Open the public dev URL, register, save three items, see the Daily, share one via WhatsApp and copy another.
2. Locally: `make up`, open Grafana, show the save-item trace with its logs and metrics.
3. Turn on the demo bug, save a long title, watch the alert fire, the incident open, and the responder push a fix to `main`.
4. CI passes, CD deploys to dev, the alert resolves. Merge the responder's PR from `main` to `prod` to release.
