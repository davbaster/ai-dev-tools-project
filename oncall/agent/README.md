# On-call responder (#17)

Wakes on Grafana's alert webhook (#15), opens a GitHub issue labeled `incident`, investigates with the MCP server's read-only tools (#16) through an LLM, and either pushes a minimal fix with a test or labels the incident `needs-human`. Role and rules: `_docs/agents/oncall-responder.md` (also its system prompt).

## Flow

1. `POST /alerts` (Compose `oncall-agent`, `http://oncall-agent:8080/alerts`; host `127.0.0.1:8080`) needs `Authorization: Bearer $ALERT_WEBHOOK_TOKEN`; answers 202 at once and works in the background.
2. **Firing:** one incident per `alertname` while it's open. A new alert opens `[incident] <alertname>: <summary>` (labels, start time, Grafana link); repeats only comment on it.
3. **Investigation:** an LLM loop (OpenAI-compatible Chat Completions with tool calling, over `httpx`) with the four MCP tools plus:
   - `propose_fix(files, summary, cause, evidence)`: whole-file contents for at most 3 files under `backend/`, `frontend/`, `telemetry/` or `tests/`, at least one test. The responder copies the repo to a temp folder, writes the files and runs `ruff check`, `ruff format --check` and the unit, frontend and contract tests (integration runs in CI). A failure goes back to the LLM; after 2 failed attempts it escalates.
   - `escalate(checked, ruled_out, next_steps)`.

   Limits: 20 steps, 10 minutes. Hitting one, or the LLM/MCP failing, escalates with the reason.
4. **Fix, push allowed:** one commit on `RESPONDER_TARGET_BRANCH` through the GitHub Git Data API, message `<summary>\n\nRefs #<incident>` (`Refs`, not `Fixes`, so GitHub doesn't close the incident on push). On `main` it also opens (or comments on) the PR `main` → `prod`. The incident gets cause, evidence, diff, commit and PR.
5. **Fix, push disabled** (default): the diff and explanation go on the incident, labeled `needs-human`.
6. **Escalation:** label `needs-human`, comment with what was checked, ruled out and next steps.
7. **Resolved:** comment on the open incident; close it only if a fix was pushed. "Fix pushed" is remembered in memory and, after a restart, read from a hidden marker in the fix comment (`<!-- oncall:fix-pushed -->`; local mode: `fix-<n>.diff` exists).

Everything posted to GitHub (titles, comments, commit messages, diffs) goes through the MCP server's `redact`. The responder never merges, deploys, restarts, runs commands from the LLM, or writes outside those four folders.

## Configuration (local `.env`, never committed)

| Variable | Meaning |
|---|---|
| `ALERT_WEBHOOK_TOKEN` | Shared with Grafana's contact point (#15). Required. |
| `MCP_TOKEN`, `MCP_URL` | The MCP server (#16). Token required. |
| `GITHUB_TOKEN` | Fine-grained token for this repository only: **Contents**, **Issues**, **Pull requests** read/write (no Workflows, no Administration). Without it, alerts are logged but no incident is opened. |
| `GITHUB_REPOSITORY` | `davbaster/ai-dev-tools-project` |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | OpenAI-compatible API (default `https://api.openai.com/v1`, `gpt-6-luna`). Without a key, incidents are opened and escalated (`LLM_API_KEY is not set`). |
| `LLM_REASONING_EFFORT` | Sent as `reasoning_effort` when not empty. OpenAI's reasoning models (e.g. `gpt-6-luna`) need `none` to use tools on Chat Completions (Compose's default). Empty for other providers. |
| `RESPONDER_ALLOW_PUSH` | `false` (default): propose only. `true`: commit the fix. |
| `RESPONDER_TARGET_BRANCH` | `main` (default). Any other branch gets the commit but no prod PR: use a throwaway branch to try the fix path. |

The container is the Dockerfile's `agent` target (runtime plus ruff and pytest), with the repo mounted read-only at `/repo`.

## Local mode, replay and recording (#69)

`make demo-local` runs the responder with these settings (from `docker-compose.demo.yml`):

| Variable | Meaning |
|---|---|
| `RESPONDER_MODE` | `github` (default) or `local`. Local: incidents, comments and labels go to `DEMO_OUTPUT/incident-<n>.md` (+ `incidents.json`); the fix is written into the workspace (`REPO_ROOT`) with its diff in `fix-<n>.diff`; the "prod PR" is the draft `prod-pr-<n>.md`. No GitHub call, even with a `GITHUB_TOKEN`. |
| `RESPONDER_ONLY_ALERTS` | Comma-separated alert names to handle; empty = all. The demo uses `SaveItemFailing` (#62). |
| `RESPONDER_REPLAY` | Without `LLM_API_KEY`, replay the assistant messages of this recorded run (`replays/demo_bug.json`); the incident says so, and a recorded step that no longer applies escalates as "replay out of date". |
| `RESPONDER_RECORD` | With `LLM_API_KEY`, save the run's assistant messages (redacted) to this file. |
| `DEMO_OUTPUT` | Where local mode writes (`/demo-output`). |

## Try it

- Logs: `make responder-logs` (JSON, with `incident` and `alertname`; never tokens).
- Escalation: log in to the app, `docker compose stop db`, keep saving items: the alert fires (~3 min), an incident opens and the responder escalates (the cause is the database, not the code). `docker compose start db`: resolved comment, the incident stays open for a human.
- Fix path without touching `main`: create a throwaway branch from `main`, set `RESPONDER_ALLOW_PUSH=true` and `RESPONDER_TARGET_BRANCH=<that branch>`, plant a bug locally (not committed) and `make up`.
