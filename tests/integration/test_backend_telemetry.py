"""The backend's half of the save-item trace, against a real Postgres (#13)."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.main import app

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
TRACEPARENT = f"00-{TRACE_ID}-00f067aa0ba902b7-01"
PASSWORD = "una contraseña larga y secreta"
SECRETS = (
    "telemetria_ana",
    PASSWORD,
    "https://example.com/privado",
    "Mi título",
    "Mi nota",
)


@pytest.fixture
def api(engine, session):
    def test_db():
        db = Session(engine, expire_on_commit=False)
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def saved_count(metric_points) -> float:
    return sum(metric_points("items.saved").values())


def test_save_continues_the_frontend_trace(api, spans, json_logs, metric_points):
    api.post("/api/auth/register", json={"username": SECRETS[0], "password": PASSWORD})
    token = api.post(
        "/api/auth/login", json={"username": SECRETS[0], "password": PASSWORD}
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    category = api.get("/api/categories", headers=headers).json()[0]["id"]
    before = saved_count(metric_points)

    created = api.post(
        "/api/items",
        json={
            "url": SECRETS[2],
            "title": SECRETS[3],
            "note": SECRETS[4],
            "category_id": category,
        },
        headers={**headers, "traceparent": TRACEPARENT},
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    finished = spans.get_finished_spans()
    server = [s for s in finished if s.name == "POST /api/items"]
    assert server and format(server[0].context.trace_id, "032x") == TRACE_ID
    assert server[0].attributes["http.route"] == "/api/items"
    assert server[0].attributes["item_id"] == item_id
    assert server[0].attributes["category_id"] == category
    db_spans = [
        s
        for s in finished
        if s.attributes.get("db.system") or "db.statement" in (s.attributes or {})
    ]
    # La consulta y el INSERT del guardado van dentro de la misma traza.
    assert [s for s in db_spans if format(s.context.trace_id, "032x") == TRACE_ID]

    assert saved_count(metric_points) == before + 1
    saved = [line for line in json_logs if line["message"] == "item saved"]
    assert saved and saved[-1]["trace_id"] == TRACE_ID
    assert saved[-1]["item_id"] == item_id and saved[-1]["category_id"] == category

    # Ni el usuario, la contraseña, el token ni los datos del item.
    dumped = json.dumps(json_logs) + "".join(
        json.dumps(dict(s.attributes or {}), default=str) for s in finished
    )
    for secret in (*SECRETS, token):
        assert secret not in dumped


def test_rejected_save_is_not_counted(api, metric_points):
    before = saved_count(metric_points)
    assert (
        api.post(
            "/api/items", json={"url": "https://x.y", "category_id": 1}
        ).status_code
        == 401
    )
    assert saved_count(metric_points) == before
