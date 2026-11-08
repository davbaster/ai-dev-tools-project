# Testing guidelines

Proof-of-concept level: a few meaningful tests per layer, not full coverage. All three layers must exist and pass with `make test`.

| Layer | Folder | Uses | Example |
|---|---|---|---|
| Unit | `tests/unit/` | plain pytest, no DB or network | Daily picks one item per non-empty category; share text includes title, note and URL; redaction hides secrets |
| Frontend | `tests/frontend/` | FastAPI `TestClient`, SQLite or the test DB | Login page renders; after login the dashboard shows the Daily, WhatsApp and Copy buttons |
| Integration | `tests/integration/` | real Postgres in Docker (`make test-integration`) | Save an item and read it back; one user cannot see another's items |

## Rules

- Test behavior against the acceptance criteria, not implementation details.
- One test per acceptance criterion that matters; edge cases only when the issue names them.
- No real network calls: fake the LLM and GitHub clients in tests.
- Tests never need secrets. Use dummy values from `.env.example`.
- Never skip or delete an existing test. If one is wrong, comment on the issue.
