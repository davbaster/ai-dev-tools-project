# Deploy

How Para Luego reaches **dev** on Render (issue #11). Prod is #12.

## How a change reaches dev

1. A commit lands on `main` (a merged PR or an on-call fix).
2. **CI** (`.github/workflows/ci.yml`) runs lint, security, all test suites and the Docker build.
3. Only if CI is green, **CD dev** (`.github/workflows/cd-dev.yml`) runs:
   - `make image TAG=<sha>`: builds the image once, with `APP_VERSION=<sha>`;
   - `make push-image`: pushes `ghcr.io/davbaster/ai-dev-tools-project:<sha>` and `:dev`;
   - `make deploy-dev`: calls the backend deploy hook, then the frontend one, each with `imgURL=…:<sha>`;
   - `make wait-deploy`: waits (up to 10 minutes) until `GET /api/health` on the backend and `GET /health` on the frontend report `"version": "<sha>"`.
4. A red CI never deploys. In a fork, or without the Render secrets, CD pushes the image and skips the deploy with a notice.

Check what dev runs: `curl https://para-luego-dev-backend.onrender.com/api/health`.

## What runs on Render (`render.yaml`)

| Resource | What | Notes |
|---|---|---|
| `para-luego-dev-backend` | web, image, free | `sh /app/backend/start.sh`: migrations, then uvicorn on port 8001. `DATABASE_URL` from the database. |
| `para-luego-dev-frontend` | web, image, free | uvicorn on port 8000. `BACKEND_URL` = the backend's public URL; `BACKEND_TIMEOUT_SECONDS=60`; `BACKEND_WAKE_SECONDS=60` (while the backend wakes, Render answers the frontend's calls with quick errors, so the frontend retries GETs, and calls whose connection failed, for up to 60 s). |
| `para-luego-dev-db` | Postgres 16, free | One free Postgres per workspace. **Expires 30 days after creation** (then 14 days of grace before deletion). Created 2026-11-08: **expires 2026-12-08**. |

Free plan limits that shape this (checked 2026-11-08): free web services can't receive private-network traffic (so the frontend uses the backend's public URL), have no pre-deploy command (so migrations run at start), and sleep after 15 minutes without traffic (about a minute to wake up). Prod's database goes to Neon's free tier in #12, because Render allows only one free Postgres.

## One-time setup (David)

These are account changes, so a person does them once:

1. **GHCR image:** (done 2026-11-08: the package inherited the public repo's visibility; only check it) after the first CD run, open the package `ai-dev-tools-project` under your GitHub profile → *Package settings* → *Change visibility* → **Public**, so Render can pull it without a credential. Check with `docker logout ghcr.io && docker pull ghcr.io/davbaster/ai-dev-tools-project:dev`.
2. **Render:** sign in to Render, *New* → *Blueprint*, pick this repository and apply `render.yaml`. It creates the database and the two services. If Render changes a service name (because it's taken), update `BACKEND_URL` in `render.yaml` and `DEV_BACKEND_URL` / `DEV_FRONTEND_URL` in the `Makefile`.
3. **Deploy hooks:** in each service → *Settings* → *Deploy Hook*, copy the URL and save it as a **repository** secret (not an environment secret: `cd-dev.yml` declares no environment) (GitHub → *Settings* → *Secrets and variables* → *Actions*): `RENDER_DEV_BACKEND_DEPLOY_HOOK` and `RENDER_DEV_FRONTEND_DEPLOY_HOOK`. Or `gh secret set RENDER_DEV_BACKEND_DEPLOY_HOOK` and paste it. Never commit them.
4. **Database expiry:** write down the creation date; the free database stops working 30 days later. Recreating it means a new empty database (re-run the Blueprint or create one with the same name).

## Troubleshooting

- **CD times out waiting for the version:** open the service's *Events* and *Logs* in Render. A failed migration shows up in the backend log; the previous version keeps serving.
- **400 from a deploy hook:** the `imgURL` must match the service's image (`ghcr.io/davbaster/ai-dev-tools-project`) except for the tag.
- **First page after a while is slow:** the free services were asleep; the frontend retries the backend for up to 60 seconds while it wakes.
- **"Backend: unavailable" right after waking:** found in QA of #11: with only `BACKEND_TIMEOUT_SECONDS` the frontend got an immediate error from Render while the backend woke (0.9 s), so `BACKEND_WAKE_SECONDS` was added. If it shows again, check that both variables are set on the frontend service.
