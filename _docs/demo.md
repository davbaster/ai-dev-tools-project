# Demo script (#19, #69)

## Local demo for reviewers (#69)

`make demo-local` runs the incident story on any machine with Docker, uv, git and make, without GitHub, without the owner's keys and without changing anything real. `make demo-local-clean` undoes it.

What happens (the script prints each step):

1. **Workspace:** a git worktree `.demo/workspace` (branch `demo/<time>`) from `HEAD`, with the demo bug from `demo/bug.json` (the `display_title` off-by-one). Your checkout and `main` don't change.
2. **Stack:** `docker-compose.yml` + `docker-compose.demo.yml`. The backend builds from the workspace with `BUG_SAVE_ITEM=1`; the MCP server and the responder read the workspace. The responder runs with `RESPONDER_MODE=local` and follows SaveItemFailing only (#62).
3. **Traffic:** a demo user saves long titles every few seconds; the backend answers 500.
4. **Incident** (~2-3 min): `demo-output/incident-1.md`.
5. **Fix** (~1 min): the responder writes the fix into the workspace after ruff and the unit, frontend and contract tests pass; `demo-output/fix-1.diff`.
6. **Draft release:** `demo-output/prod-pr-1.md`, the PR `main` → `prod` a human would review and merge.
7. **Resolution** (~4-6 min): the backend is rebuilt from the fixed workspace (flag still on), long titles save, the alert resolves and the incident file says closed.

**LLM:** with `LLM_API_KEY` in `.env` the investigation is live. Without it, the responder replays `oncall/agent/replays/demo_bug.json`, a recorded real run: only the model's choices are recorded; the MCP queries, the checks and the fix run for real. The incident says "replayed investigation", and its evidence (trace ids, timestamps) comes from the recording. If the code changed and a recorded step no longer applies, the responder escalates with "replay out of date" instead of guessing. To record again (with a key): `RESPONDER_RECORD=/demo-output/recording.json make demo-local` (in Git Bash prefix `MSYS_NO_PATHCONV=1`, or the path gets rewritten), then copy `demo-output/recording.json` to `oncall/agent/replays/demo_bug.json` and check it with `make test`.

**If it stops:** the script says which step timed out. `make responder-logs` and Grafana (http://localhost:3000) show why. Common causes: Docker not running, ports 8000/3000 taken, or the first build taking long.

---

## Full demo (project owner)

The rest of this page is the demo with GitHub, dev and prod (#19).

The end-to-end demo from `_docs/plan.md` section 12: the app in the cloud, its telemetry locally, and an incident that the on-call responder fixes on its own. About 15 minutes.

## Before you start

- `make up` is running (app, Postgres, observability, MCP server, responder) and your local `.env` has the responder's keys (`GITHUB_TOKEN`, `LLM_API_KEY`; see `oncall/agent/README.md`).
- For the incident part, the responder must be allowed to push to `main`. In `.env`:
  ```
  RESPONDER_ALLOW_PUSH=true
  RESPONDER_TARGET_BRANCH=main
  ```
  then `make up` again so the responder picks it up. **Set it back to `false` after the demo.**
- The demo bug must still be in `main` (`backend/items.py`, `display_title`). After a successful demo the responder has removed it: see "Re-arm the demo" below.
- Open these tabs:
  - the app: https://para-luego-dev-frontend.onrender.com (dev; the first load can take a minute while Render wakes it);
  - http://localhost:8000 (local app);
  - Grafana: http://localhost:3000 (dashboard "Para Luego");
  - GitHub issues filtered by label `incident`;
  - GitHub Actions.

## 1. The app (dev, public)

Register, save three items in different categories, show **Tu Daily**, share one with **WhatsApp** and **Copiar** another (paste it somewhere).

## 2. Telemetry (local)

1. In the local app (http://localhost:8000), log in and save an item.
2. Grafana → dashboard **Para Luego**: requests by route and status, p95 latency, items saved, the app's JSON logs. The **Alerts** panel shows SaveItemFailing and HighServerErrors as Normal.
3. Explore → Loki `{service_name="para-luego-backend"} |= "item saved"` → open the line → **Tempo** link on `trace_id`: one trace from the frontend through the backend to the database. From a span, **Related logs** goes back to the logs. No usernames, URLs or titles anywhere, only ids.

## 3. The incident

1. `make demo-on`: restarts the backend with `BUG_SAVE_ITEM=1`.
2. In the local app, save an item with a **title longer than 40 characters**, e.g. "Un artículo muy largo sobre cómo guardar cosas". The page says the service isn't available (backend 500). Short titles still work. Keep saving long titles every few seconds (or refresh a few times).
3. Grafana: the save-item error panel goes up; after ~2-3 minutes **SaveItemFailing** goes Pending, then Firing.
4. GitHub: an issue `[incident] SaveItemFailing: …` appears, labeled `incident`. **HighServerErrors** usually opens a second incident for the same cause (#62); follow SaveItemFailing.
5. `make responder-logs`: the responder's steps (logs, metrics, health, source files), then `propose_fix`. In about a minute:
   - a commit on `main`: "<fix summary>" with `Refs #<incident>` (not `Fixes`: the incident stays open until the alert resolves);
   - a comment on the incident with the cause, the evidence (the `trace_id`, the `IndexError` at `backend/items.py`), the diff and the checks that passed;
   - the PR **Release: main to prod** opened or updated, linking the incident.

## 4. From the fix to production

1. GitHub Actions: **CI** runs on the responder's commit (~1 min); when it's green, **CD dev** deploys it (~1.5 min). `curl https://para-luego-dev-backend.onrender.com/api/health` reports the new SHA.
2. Locally, the alerts watch your machine, so run the fixed code:
   ```bash
   git pull
   BUG_SAVE_ITEM=1 docker compose up -d --build --no-deps --wait backend
   ```
   Only the backend is rebuilt (`make up` would also rebuild and restart the responder; it would still close the incident, because it finds its fix marker on the issue, but there's no need). With the flag still on, long titles now save. Within ~4-6 minutes (the alert's 5-minute window) the alert resolves; the responder comments "Alert resolved … after the fix" and **closes the incident**.
3. Release: review the prod PR and merge it with **Create a merge commit** (a human decides). **Deploy prod** deploys the same image dev ran.
4. `make demo-off`, and set `RESPONDER_ALLOW_PUSH=false` in `.env` again (then `make up`).

## If the responder escalates instead

It labels the incident `needs-human` and comments what it checked, ruled out and would look at next. That is the other designed outcome: show the comment. Common causes: the LLM key or model (`make responder-logs` names the error), or a fix that failed its checks twice (the comment includes the check output). Fix by hand and push through a PR as usual.

## Re-arm the demo

The responder's fix removes the bug from `main`, so the demo works once per bug. To run it again, revert the fix commit through a PR:

```bash
git switch -c rearm-demo-bug origin/main
git revert --no-edit <fix commit sha>
```

Then push the branch, open the PR, and merge it with green CI. Close any leftover incidents by hand.
