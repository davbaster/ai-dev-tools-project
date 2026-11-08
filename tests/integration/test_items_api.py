"""Items API against a real Postgres."""

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


def save(api, headers, **fields):
    return api.post("/api/items", json=fields, headers=headers)


def test_create_and_read_back(api):
    ana = signup(api, "ana")
    leer = category_ids(api, ana)["Leer"]
    created = save(
        api,
        ana,
        url=" https://example.com/a ",
        title=" Un artículo ",
        category_id=leer,
        note="Para Luis",
    )
    assert created.status_code == 201
    item = created.json()
    assert item["url"] == "https://example.com/a"
    assert item["title"] == "Un artículo"
    assert item["note"] == "Para Luis"
    assert item["category_name"] == "Leer"
    listed = api.get("/api/items", headers=ana).json()
    assert [i["id"] for i in listed] == [item["id"]]


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "ftp://example.com/x",
        "example.com",
        "",
        "https://",
        "https://" + "a" * 2048,
    ],
)
def test_bad_urls_are_422(api, url):
    ana = signup(api, "ana")
    response = save(api, ana, url=url, category_id=category_ids(api, ana)["Leer"])
    assert response.status_code == 422
    assert response.json()["detail"][0]["field"] == "url"


def test_empty_title_becomes_the_url_and_empty_note_is_null(api):
    ana = signup(api, "ana")
    item = save(
        api,
        ana,
        url="https://example.com/b",
        title="   ",
        note="",
        category_id=category_ids(api, ana)["Ver"],
    ).json()
    assert item["title"] == "https://example.com/b"
    assert item["note"] is None


def test_title_and_note_limits(api):
    ana = signup(api, "ana")
    leer = category_ids(api, ana)["Leer"]
    assert (
        save(api, ana, url="https://a.b", title="x" * 300, category_id=leer).status_code
        == 201
    )
    long_title = save(api, ana, url="https://a.b", title="x" * 301, category_id=leer)
    assert long_title.status_code == 422
    assert long_title.json()["detail"][0]["field"] == "title"
    long_note = save(api, ana, url="https://a.b", note="x" * 1001, category_id=leer)
    assert long_note.json()["detail"][0]["field"] == "note"


def test_foreign_and_missing_categories_get_the_same_422(api):
    ana = signup(api, "ana")
    luis = signup(api, "luis")
    foreign = save(
        api, ana, url="https://a.b", category_id=category_ids(api, luis)["Leer"]
    )
    missing = save(api, ana, url="https://a.b", category_id=999999)
    assert foreign.status_code == missing.status_code == 422
    assert foreign.json() == missing.json()
    assert foreign.json()["detail"][0]["field"] == "category_id"


def test_same_url_twice_makes_two_items(api):
    ana = signup(api, "ana")
    leer = category_ids(api, ana)["Leer"]
    save(api, ana, url="https://a.b", category_id=leer)
    save(api, ana, url="https://a.b", category_id=leer)
    assert len(api.get("/api/items", headers=ana).json()) == 2


def test_list_is_newest_first_and_only_mine(api):
    ana = signup(api, "ana")
    luis = signup(api, "luis")
    leer = category_ids(api, ana)["Leer"]
    first = save(api, ana, url="https://a.b/1", category_id=leer).json()
    second = save(api, ana, url="https://a.b/2", category_id=leer).json()
    save(api, luis, url="https://a.b/luis", category_id=category_ids(api, luis)["Leer"])
    listed = api.get("/api/items", headers=ana).json()
    assert [i["id"] for i in listed] == [second["id"], first["id"]]


def test_filter_by_category_and_foreign_filter_is_404(api):
    ana = signup(api, "ana")
    luis = signup(api, "luis")
    ids = category_ids(api, ana)
    save(api, ana, url="https://a.b/leer", category_id=ids["Leer"])
    save(api, ana, url="https://a.b/ver", category_id=ids["Ver"])
    only_ver = api.get(f"/api/items?category_id={ids['Ver']}", headers=ana).json()
    assert [i["url"] for i in only_ver] == ["https://a.b/ver"]
    foreign = category_ids(api, luis)["Leer"]
    assert api.get(f"/api/items?category_id={foreign}", headers=ana).status_code == 404


def test_delete_twice_and_foreign_delete_are_404(api):
    ana = signup(api, "ana")
    luis = signup(api, "luis")
    item = save(
        api, ana, url="https://a.b", category_id=category_ids(api, ana)["Leer"]
    ).json()
    assert api.delete(f"/api/items/{item['id']}", headers=luis).status_code == 404
    assert api.delete(f"/api/items/{item['id']}", headers=ana).status_code == 204
    assert api.delete(f"/api/items/{item['id']}", headers=ana).status_code == 404


def test_items_need_a_token(api):
    assert api.get("/api/items").status_code == 401
    assert (
        api.post(
            "/api/items", json={"url": "https://a.b", "category_id": 1}
        ).status_code
        == 401
    )
    assert api.delete("/api/items/1").status_code == 401
