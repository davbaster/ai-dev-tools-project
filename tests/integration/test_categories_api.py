"""Categories API against a real Postgres."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.main import app
from backend.models import Category, Item

DEFAULTS = ["Leer", "Ver", "Comprar", "Compartir", "Proyectos"]


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
    """Register and log in; return auth headers."""
    password = "a long enough password"
    assert (
        api.post(
            "/api/auth/register", json={"username": username, "password": password}
        ).status_code
        == 201
    )
    token = api.post(
        "/api/auth/login", json={"username": username, "password": password}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def names(api, headers) -> list[str]:
    return [c["name"] for c in api.get("/api/categories", headers=headers).json()]


def test_registration_creates_the_defaults_in_order(api):
    ana = signup(api, "ana")
    categories = api.get("/api/categories", headers=ana).json()
    assert [c["name"] for c in categories] == DEFAULTS
    assert all(c["item_count"] == 0 for c in categories)


def test_user_categories_come_after_the_defaults(api):
    ana = signup(api, "ana")
    created = api.post("/api/categories", json={"name": "  Música "}, headers=ana)
    assert created.status_code == 201
    assert created.json()["name"] == "Música"
    assert names(api, ana) == [*DEFAULTS, "Música"]


def test_duplicate_name_in_any_case_is_409_but_other_users_can_reuse_it(api):
    ana = signup(api, "ana")
    luis = signup(api, "luis")
    duplicate = api.post("/api/categories", json={"name": "leer"}, headers=ana)
    assert duplicate.status_code == 409
    assert "Ya tenés una categoría" in duplicate.json()["detail"]
    assert (
        api.post("/api/categories", json={"name": "Música"}, headers=ana).status_code
        == 201
    )
    assert (
        api.post("/api/categories", json={"name": "Música"}, headers=luis).status_code
        == 201
    )


@pytest.mark.parametrize("name", ["", "   ", "x" * 51])
def test_invalid_names_are_422(api, name):
    ana = signup(api, "ana")
    response = api.post("/api/categories", json={"name": name}, headers=ana)
    assert response.status_code == 422
    assert response.json()["detail"][0]["field"] == "name"


def test_delete_an_empty_category_including_a_default(api):
    ana = signup(api, "ana")
    leer = api.get("/api/categories", headers=ana).json()[0]
    assert api.delete(f"/api/categories/{leer['id']}", headers=ana).status_code == 204
    assert "Leer" not in names(api, ana)


def test_delete_with_items_is_409_and_deletes_nothing(api, session):
    ana = signup(api, "ana")
    leer = api.get("/api/categories", headers=ana).json()[0]
    category = session.get(Category, leer["id"])
    session.add(
        Item(
            user_id=category.user_id,
            category_id=category.id,
            url="https://a.b",
            title="t",
        )
    )
    session.commit()

    response = api.delete(f"/api/categories/{leer['id']}", headers=ana)
    assert response.status_code == 409
    assert "tiene items" in response.json()["detail"]
    counts = {
        c["name"]: c["item_count"]
        for c in api.get("/api/categories", headers=ana).json()
    }
    assert counts["Leer"] == 1
    assert session.scalars(select(Item)).one()


def test_other_users_categories_are_invisible(api):
    ana = signup(api, "ana")
    luis = signup(api, "luis")
    luis_category = api.get("/api/categories", headers=luis).json()[0]
    assert (
        api.delete(f"/api/categories/{luis_category['id']}", headers=ana).status_code
        == 404
    )
    assert api.delete("/api/categories/999999", headers=ana).status_code == 404
    ana_ids = {c["id"] for c in api.get("/api/categories", headers=ana).json()}
    assert luis_category["id"] not in ana_ids


def test_categories_need_a_token(api):
    assert api.get("/api/categories").status_code == 401
    assert api.post("/api/categories", json={"name": "x"}).status_code == 401
    assert api.delete("/api/categories/1").status_code == 401
