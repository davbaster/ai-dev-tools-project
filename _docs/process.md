# Process

How work moves from an idea to production. The GitHub issue is the record: every role leaves its trace there as a comment, so the tracker shows how the agents worked.

## Labels

| Label | Meaning |
|---|---|
| `backlog` | A task exists. Not ready to implement. |
| `groomed` | The PM rewrote it with the template. Ready to implement. |
| `in-progress` | An engineer is working on it. |
| `qa-pass` / `qa-fail` | The QA verdict on the latest attempt. |
| `incident` | Opened by the on-call responder or a human from an alert. |
| `needs-human` | The responder could not find the cause. |

Create these labels once in the repo.

## Lifecycle of a task

1. **File** - anyone opens an issue labeled `backlog`. One line is enough.
2. **Groom** - the **PM** rewrites it with `_docs/task-template.md` (Goal, Acceptance criteria, Out of scope, Constraints), files follow-up issues for anything moved out, swaps `backlog` for `groomed`, and comments "Groomed".
3. **Pick** - the orchestrator takes the lowest-numbered `groomed` issue whose dependencies are closed, labels it `in-progress`, and updates `HANDOFF.md`.
4. **Implement** - the **Software Engineer** works on branch `<issue>-<slug>`, implements against the acceptance criteria, writes tests, runs `make lint` and `make test`, commits, opens a PR with `Closes #<issue>`, and comments on the issue what was done.
5. **Verify** - the **QA Engineer** checks each acceptance criterion against the running code and the tests, and posts `## QA: PASS` or `## QA: FAIL` on the issue. It changes no code.
6. **Fix loop** - on FAIL, the engineer fixes on the same branch and QA verifies again. After two FAILs on the same criterion, the orchestrator stops and asks David.
7. **Merge** - only on QA PASS **and** a green CI check on the PR (`.github/workflows/ci.yml`: `make install`, `lint`, `security`, `test`, `build`), the orchestrator merges the PR with David's OK. A red or still-running CI blocks the merge. The issue closes. CD deploys `main` to **dev**. To reproduce CI on your machine before pushing, run `make ci-local` (`act` + Docker).
8. **Record** - the orchestrator appends to `_docs/log/YYYY-MM-DD.md` and overwrites `HANDOFF.md`.

Production is never automatic: to release, open a PR from `main` to `prod` (`make promote-prod`). David reviews and merges it; merging deploys to **prod**.

## Incidents

1. An alert fires (Grafana locally, or the admin panel's threshold in the cloud demo).
2. The **On-call Responder** opens an issue labeled `incident` with the alert, investigates with the MCP tools, and comments its findings.
3. If it finds the cause, it pushes the fix (with a test) directly to `main`, referencing the incident in the commit. CI runs; if green, CD deploys to **dev**. If CI fails, nothing deploys and the responder labels the incident `needs-human`.
4. It then opens (or updates) the PR from `main` to `prod` with the incident linked. David merges it to deploy to prod.
5. If it cannot, it labels the issue `needs-human`, writes what it checked, and shows the incident in the admin panel.
6. After the fix reaches dev, the alert resolves. The responder comments the resolution and closes the incident.

## Rollback

If a deploy makes things worse, redeploy the previous image tag: `make rollback ENV=<dev|prod> TAG=<tag>` or the **Rollback** workflow. Record it in the log.

## Rules of the road

- One issue at a time, one branch per issue.
- Acceptance criteria change only through the PM, with a comment explaining why.
- Every decision goes in `HANDOFF.md` and the log the moment it is made.
