# Deploy

How Para Luego reaches **dev** (issue #11) and **prod** (issue #12) on Render, and how to roll back.

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
| `para-luego-dev-frontend` | web, image, free | uvicorn on port 8000. `BACKEND_URL` = the backend's public URL; `BACKEND_TIMEOUT_SECONDS=60`; `BACKEND_WAKE_SECONDS=5` (short retries for blips); `BACKEND_PUBLIC_URL` = the backend's public URL, used by the wake-up page (below). |
| `para-luego-dev-db` | Postgres 16, free | One free Postgres per workspace. **Expires 30 days after creation** (then 14 days of grace before deletion). Created 2026-11-08: **expires 2026-12-08**. |

Free plan limits that shape this (checked 2026-11-08): free web services can't receive private-network traffic (so the frontend uses the backend's public URL), have no pre-deploy command (so migrations run at start), and sleep after 15 minutes without traffic (about a minute to wake up). Prod's database is on Neon's free tier (below), because Render allows only one free Postgres.

## One-time setup (David)

These are account changes, so a person does them once:

1. **GHCR image:** (done 2026-11-08: the package inherited the public repo's visibility; only check it) after the first CD run, open the package `ai-dev-tools-project` under your GitHub profile → *Package settings* → *Change visibility* → **Public**, so Render can pull it without a credential. Check with `docker logout ghcr.io && docker pull ghcr.io/davbaster/ai-dev-tools-project:dev`.
2. **Render:** sign in to Render, *New* → *Blueprint*, pick this repository and apply `render.yaml`. It creates the database and the two services. If Render changes a service name (because it's taken), update `BACKEND_URL` in `render.yaml` and `DEV_BACKEND_URL` / `DEV_FRONTEND_URL` in the `Makefile`.
3. **Deploy hooks:** in each service → *Settings* → *Deploy Hook*, copy the URL and save it as a **repository** secret (not an environment secret: `cd-dev.yml` declares no environment) (GitHub → *Settings* → *Secrets and variables* → *Actions*): `RENDER_DEV_BACKEND_DEPLOY_HOOK` and `RENDER_DEV_FRONTEND_DEPLOY_HOOK`. Or `gh secret set RENDER_DEV_BACKEND_DEPLOY_HOOK` and paste it. Never commit them.
4. **Database expiry:** write down the creation date; the free database stops working 30 days later. Recreating it means a new empty database (re-run the Blueprint or create one with the same name).

## How a release reaches prod

1. `make promote-prod` opens the PR `main` → `prod` (title `Release: main to prod`, body with the commits). If one is open it prints its URL; if `prod` already has everything it says "Nothing to promote". It never merges.
2. CI runs on the PR. David reviews it and merges it with **Create a merge commit** (not squash or rebase).
3. CI runs on the push to `prod`. Only if it is green, **Deploy prod** (`.github/workflows/deploy-prod.yml`, which runs from `main`'s copy of the file):
   - `make promoted-sha`: the merge commit's second parent, the `main` commit that was promoted (or the head itself after a fast-forward). Anything else fails, asking for a merge commit;
   - `make wait-image`: waits (up to 15 minutes) until `…:<sha>` is on GHCR, since CD dev pushes it after CI on `main`. If it never appears (CI on `main` failed for that commit), the run fails and prod is untouched;
   - `make retag ENV=prod`: moves `:prod` to that image, without rebuilding;
   - `make deploy-prod` and `make wait-deploy ENV=prod`: calls the prod hooks with `imgURL=…:<sha>` and waits until both prod health checks report that version and `"deployment":"prod"`.
4. Without the prod hook secrets (a fork, or before step 5 below) it still moves `:prod` and skips the deploy with a notice.

Prod runs exactly the image dev ran, so its `version` is the `main` commit's SHA, not the merge commit's. `prod` never gets commits of its own.

Why `:prod` moves too: a deploy hook's `imgURL` applies only to that deploy; Render's later deploys (manual, or after a Blueprint config change) use the tag in the service's settings, which is `:prod` (`:dev` for dev).

Check what prod runs: `curl https://para-luego-prod-backend.onrender.com/api/health`.

## Rollback

**Rollback** workflow (*Actions* → *Rollback* → *Run workflow*, inputs `env` = `dev`/`prod` and `tag` = a full commit SHA), or `make rollback ENV=<dev|prod> TAG=<sha>` locally (needs `docker login ghcr.io` and the hook variables).

- Before touching anything it refuses an `ENV` other than `dev`/`prod`, a `TAG` that isn't a 40-character SHA, a tag with no image on GHCR, and missing hook secrets.
- Then it moves `:<env>` to that image, calls that environment's hooks and waits for the version, like a deploy.
- It changes no branch: the next CD (dev) or promotion (prod) deploys `main` again. To stay on the old version, revert the bad commit on `main`.
- It doesn't undo database migrations: an older image runs against the newer schema. Today every migration is additive; #42 is about making this safe.
- Previous versions: the `version` reported by the health checks, *Actions* → *Deploy prod* / *CD dev* runs, or the image tags on GHCR. Record every rollback in the log.

## What runs on Render for prod (`render.prod.yaml`)

A **second Blueprint**, linked to the **`prod` branch**, so prod's services and settings change only when a release PR is merged, never on a merge to `main`.

| Resource | What | Notes |
|---|---|---|
| `para-luego-prod-backend` | web, image `:prod`, free | Same command and health check as dev. `DEPLOYMENT=prod`. `DATABASE_URL` is `sync: false`: Render asks for it when the Blueprint is created (later syncs ignore it, so change it in the service's *Environment*). |
| `para-luego-prod-frontend` | web, image `:prod`, free | `DEPLOYMENT=prod`; `BACKEND_URL` and `BACKEND_PUBLIC_URL` = `https://para-luego-prod-backend.onrender.com`; `BACKEND_TIMEOUT_SECONDS=60`; `BACKEND_WAKE_SECONDS=5` (same wake-up setup as dev). |
| Database | **Neon** free | Not on Render. Doesn't expire. Use the direct connection string (host without `-pooler`), with `sslmode=require`. |

The four free services share the workspace's free instance hours; sleeping services don't use them.

## One-time setup for prod (David)

In this order:

1. **Neon:** create a project (region AWS us-east, near Render's Virginia), database `para_luego`. Copy the **direct** connection string (*Connection details*, pooling off; it starts with `postgresql://` and ends with `?sslmode=require`). Don't paste it anywhere but Render.
2. **`prod` branch:** create it from a commit **before** #12's merge, so the first release goes through a PR: `git push origin 68de85a8f9349755733eec7ca3e1fb9ee23b765d:refs/heads/prod`. (That push runs CI on `prod` and then *Deploy prod*, which only moves `:prod` to that commit's image and skips the deploy, since there are no prod hooks yet.)
3. **Protect `prod`:** GitHub → *Settings* → *Branches* (or *Rules*) → rule for `prod`: require a pull request, require the status check **lint, security, tests, build**, block force pushes and deletion. Leave `main` unprotected (the on-call responder pushes there).
4. **First release:** `make promote-prod`, review and merge the PR with **Create a merge commit**. *Deploy prod* moves `:prod` to `main`'s image and skips the deploy (still no hooks).
5. **Render:** *New* → *Blueprint*, this repository, branch **`prod`**, Blueprint path **`render.prod.yaml`**. Paste the Neon string as `DATABASE_URL` when asked. It creates the two prod services from `:prod`. If Render changes a name, update the URLs in `render.prod.yaml` and `PROD_BACKEND_URL` / `PROD_FRONTEND_URL` in the `Makefile`.
6. **Deploy hooks:** in each prod service → *Settings* → *Deploy Hook*, save them as repository secrets `RENDER_PROD_BACKEND_DEPLOY_HOOK` and `RENDER_PROD_FRONTEND_DEPLOY_HOOK` (`gh secret set …`). Never commit them.
7. **Re-run** the last *Deploy prod* run (*Actions* → *Deploy prod* → *Re-run jobs*): it deploys and waits until prod reports the version.

## Troubleshooting

- **CD times out waiting for the version:** open the service's *Events* and *Logs* in Render. A failed migration shows up in the backend log; the previous version keeps serving.
- **400 from a deploy hook:** the `imgURL` must match the service's image (`ghcr.io/davbaster/ai-dev-tools-project`) except for the tag.
- **First page after a while is slow:** the free services were asleep; Render shows its own "waking up" page while the frontend starts, then the frontend's wake-up page wakes the backend (about a minute in total).
- **"Despertando el servicio…" page:** expected after a while without traffic. Found in QA of #11 and confirmed with Render's logs: calls from the frontend service to a sleeping free backend, even to its public URL, never reach it and never wake it; only internet traffic does. So when the frontend can't reach the backend, the 503 page and the login page include `_wake.html`: the user's browser calls `BACKEND_PUBLIC_URL/api/health` (that wakes the backend), waits 5 s and reloads with GET. It gives up after 3 minutes with a message. If it never wakes, check `BACKEND_PUBLIC_URL` on the frontend service.
- **Deploy prod fails with "merge the PR main -> prod with 'Create a merge commit'":** the PR was squashed or rebased, so the commit on `prod` has no image. Run the *Rollback* workflow with `env=prod` and the `main` SHA you meant to release, then make sure later release PRs use a merge commit.
- **Deploy prod times out waiting for the image:** CI or CD dev failed on `main` for that commit. Fix `main` first; prod keeps running the previous version.
- **Prod backend fails at start with "DATABASE_URL is not set" or a connection error:** set or fix `DATABASE_URL` in the prod backend's *Environment* (the Neon direct string with `sslmode=require`).
