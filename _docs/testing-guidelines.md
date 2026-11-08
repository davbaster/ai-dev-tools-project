# Testing guidelines

Proof-of-concept level: a few meaningful tests per layer, not full coverage. All layers (unit, frontend, integration, contract) must exist and pass with `make test`.

| Layer | Folder | Target | Uses | Example |
|---|---|---|---|---|
| Unit | `tests/unit/` | `make test-unit` | plain pytest, no DB or network | Daily picks one item per non-empty category; share text includes title, note and URL; redaction hides secrets |
| Frontend | `tests/frontend/` | `make test-frontend` | FastAPI `TestClient` on the frontend app, backend faked with responses shaped by `api/openapi.yaml` (no real network) | Login page renders; after login the dashboard shows the Daily, WhatsApp and Copy buttons; login → save → list flow (`test_flow.py`) |
| Contract | `tests/contract/` | `make test-contract` | plain pytest, reads `api/openapi.yaml` | Every backend route matches the contract; the frontend client calls only operations the contract defines |
| Integration | `tests/integration/` | `make test-integration` | real Postgres in Docker, backend API | Save an item and read it back; one user cannot see another's items |

`make test` runs the four targets in that order and stops at the first failing one. Only the integration suite needs Docker: `make test-integration` starts a throwaway Postgres 16 (`docker-compose.test.yml`, its own Compose project, port 5433 or `TEST_DB_PORT`), runs the tests, and removes the database even when they fail, so it never touches the `make up` data. To use another database, pass `TEST_DATABASE_URL=<url>` (it must not be the dev `para_luego` database).

## Rules

- Test behavior against the acceptance criteria, not implementation details.
- One test per acceptance criterion that matters; edge cases only when the issue names them.
- No real network calls: fake the LLM and GitHub clients in tests.
- Tests never need secrets. Use dummy values from `.env.example`.
- Never skip or delete an existing test. If one is wrong, comment on the issue.
