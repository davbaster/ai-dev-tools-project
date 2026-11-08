"""Daily API against a real Postgres."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.main import app


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


def signup(api, username) -> dict:
    password = "a long enough password"
    api.post("/api/auth/register", json={"username": username, "password": password})
    token = api.post(
        "/api/auth/login", json={"username": username, "password": password}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def category_ids(api, headers) -> dict[str, int]:
    return {
        c["name"]: c["id"] for c in api.get("/api/categories", headers=headers).json()
    }


def save(api, headers, category_id, url) -> int:
    response = api.post(
        "/api/items", json={"url": url, "category_id": category_id}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


def daily(api, headers) -> dict:
    response = api.get("/api/daily", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_one_item_per_non_empty_category_and_stable(api):
    ana = signup(api, "ana")
    cats = category_ids(api, ana)
    leer = {save(api, ana, cats["Leer"], f"https://example.com/l{n}") for n in range(3)}
    ver = {save(api, ana, cats["Ver"], "https://example.com/v")}

    first = daily(api, ana)
    assert first["date"]
    assert [i["category_id"] for i in first["items"]] == [cats["Leer"], cats["Ver"]]
    assert first["items"][0]["id"] in leer and first["items"][1]["id"] in ver
    assert first["items"][1]["category_name"] == "Ver"
    assert daily(api, ana) == first


def test_deleted_pick_is_replaced_or_dropped(api):
    ana = signup(api, "ana")
    cats = category_ids(api, ana)
    save(api, ana, cats["Leer"], "https://example.com/a")
    save(api, ana, cats["Leer"], "https://example.com/b")
    only_ver = save(api, ana, cats["Ver"], "https://example.com/v")

    picked = daily(api, ana)["items"][0]["id"]
    assert api.delete(f"/api/items/{picked}", headers=ana).status_code == 204
    assert api.delete(f"/api/items/{only_ver}", headers=ana).status_code == 204

    items = daily(api, ana)["items"]
    assert len(items) == 1
    assert items[0]["category_id"] == cats["Leer"] and items[0]["id"] != picked


def test_only_the_callers_items_and_empty_when_none(api):
    ana = signup(api, "ana")
    beto = signup(api, "beto")
    save(api, ana, category_ids(api, ana)["Leer"], "https://example.com/a")
    assert daily(api, beto)["items"] == []
    assert len(daily(api, ana)["items"]) == 1


def test_requires_a_token(api):
    assert api.get("/api/daily").status_code == 401
