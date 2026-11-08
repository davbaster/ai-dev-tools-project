# Testing guidelines

Proof-of-concept level: a few meaningful tests per layer, not full coverage. All layers (unit, frontend, integration, contract) must exist and pass with `make test`.

| Layer | Folder | Uses | Example |
|---|---|---|---|
| Unit | `tests/unit/` | plain pytest, no DB or network | Daily picks one item per non-empty category; share text includes title, note and URL; redaction hides secrets |
| Frontend | `tests/frontend/` | FastAPI `TestClient` on the frontend app, backend faked with responses shaped by `api/openapi.yaml` (no real network) | Login page renders; after login the dashboard shows the Daily, WhatsApp and Copy buttons |
| Integration | `tests/integration/` | real Postgres in Docker (`make test-integration`), backend API | Save an item and read it back; one user cannot see another's items |
| Contract | `tests/contract/` | plain pytest, reads `api/openapi.yaml` | Every backend route matches the contract; the frontend client calls only operations the contract defines |

## Rules

- Test behavior against the acceptance criteria, not implementation details.
- One test per acceptance criterion that matters; edge cases only when the issue names them.
- No real network calls: fake the LLM and GitHub clients in tests.
- Tests never need secrets. Use dummy values from `.env.example`.
- Never skip or delete an existing test. If one is wrong, comment on the issue.
