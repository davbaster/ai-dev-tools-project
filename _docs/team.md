# Team

The project is built by a small team of agents coordinated by an orchestrator. Any LLM tool can play these roles; if it has no subagents, one session plays them in order.

| Role | Instructions | Does | Does not |
|---|---|---|---|
| Orchestrator | this file + `_docs/process.md` | Picks the next issue, starts each role, merges on QA PASS + green CI, updates `HANDOFF.md` and the log | Write feature code |
| Product Manager | `_docs/agents/pm.md` | Grooms issues into the template with checkable acceptance criteria | Write code |
| Software Engineer | `_docs/agents/software-engineer.md` | Implements one groomed issue, writes tests, opens the PR | Change acceptance criteria, close issues |
| QA Engineer | `_docs/agents/qa-engineer.md` | Verifies each acceptance criterion, posts PASS/FAIL | Change code |
| On-call Responder | `_docs/agents/oncall-responder.md` | Runtime agent: investigates alerts, pushes fixes to `main` (dev), opens the PR to `prod`, or escalates | Merge to `prod`, deploy, restart, touch production data |
| Human (David) | - | Owner. Answers questions, approves dependencies, merges the PR from `main` to `prod` (production deploy) | - |

## How they work together

```
issue (backlog) → PM grooms → (groomed) → Engineer implements + PR
      → QA verifies → FAIL: back to Engineer │ PASS: Orchestrator merges
      → CD to dev → Orchestrator updates HANDOFF.md + log
```

- The **issue** is the shared workspace: every role comments there, so the tracker is the evidence of the process.
- Hand-offs happen through labels (`groomed`, `in-progress`, `qa-pass`, `qa-fail`) and comments.
- The orchestrator escalates to David after two QA FAILs on the same criterion, for any new dependency, and for anything the plan doesn't cover.

## Models

See `AGENTS.md` → Models.
