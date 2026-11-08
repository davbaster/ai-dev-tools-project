"""Items page with a fake backend (shapes from api/openapi.yaml)."""

import json
import re
from urllib.parse import urlencode

import httpx

CATEGORIES = [
    {"id": 1, "name": "Leer", "item_count": 1},
    {"id": 2, "name": "Ver", "item_count": 0},
]
ITEM = {
    "id": 10,
    "url": "https://example.com/a",
    "title": "<img src=x onerror=alert(1)>",
    "note": "Para Luis",
    "category_id": 1,
    "category_name": "Leer",
    "created_at": "2026-11-08T12:00:00+00:00",
}


class FakeBackend:
    def __init__(self, items=None, create_status=201, list_status=200):
        self.items = [ITEM] if items is None else items
        self.create_status = create_status
        self.list_status = list_status
        self.calls = []
        self.created = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        self.calls.append((method, path, str(request.url.query, "ascii")))
        if path == "/api/categories":
            return httpx.Response(200, json=CATEGORIES)
        if path == "/api/items" and method == "GET":
            if self.list_status == 404:
                return httpx.Response(404, json={"detail": "No existe esa categoría."})
            return httpx.Response(200, json=self.items)
        if path == "/api/items" and method == "POST":
            self.created = json.loads(request.content)
            if self.create_status == 201:
                return httpx.Response(201, json=ITEM)
            return httpx.Response(
                422,
                json={
                    "detail": [
                        {
                            "field": "url",
                            "message": "La URL debe empezar con http:// o https:// (máximo 2048 caracteres).",
                        }
                    ]
                },
            )
        if path.startswith("/api/items/") and method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404, json={"detail": "Not Found"})


def form(**fields):
    return {
        "content": urlencode(fields),
        "headers": {"Content-Type": "application/x-www-form-urlencoded"},
    }


def logged_in(client):
    client.cookies.set("pl_session", "fake-token")


def test_page_has_form_with_my_categories_and_the_list(client, fake_backend):
    fake_backend(FakeBackend())
    logged_in(client)
    page = client.get("/items").text
    assert 'name="url"' in page and 'name="title"' in page and 'name="note"' in page
    assert '<option value="1"' in page and '<option value="2"' in page
    assert 'href="/items?category_id=2"' in page
    assert "Para Luis" in page


def test_item_link_opens_in_new_tab_safely(client, fake_backend):
    fake_backend(FakeBackend())
    logged_in(client)
    page = client.get("/items").text
    assert (
        'href="https://example.com/a" target="_blank" rel="noopener noreferrer"' in page
    )


def test_titles_are_escaped(client, fake_backend):
    fake_backend(FakeBackend())
    logged_in(client)
    page = client.get("/items").text
    assert "<img src=x" not in page
    assert "&lt;img src=x onerror=alert(1)&gt;" in page


def test_save_redirects_and_keeps_the_filter(client, fake_backend):
    backend = FakeBackend()
    fake_backend(backend)
    logged_in(client)
    response = client.post(
        "/items",
        **form(url="https://a.b", title="", category_id="2", note="", filter="2"),
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/items?category_id=2"
    assert backend.created["category_id"] == 2


def test_save_without_filter_redirects_to_items(client, fake_backend):
    fake_backend(FakeBackend())
    logged_in(client)
    response = client.post(
        "/items", **form(url="https://a.b", category_id="1", filter="")
    )
    assert response.headers["location"] == "/items"


def test_save_error_shows_message_and_keeps_values(client, fake_backend):
    fake_backend(FakeBackend(create_status=422))
    logged_in(client)
    response = client.post(
        "/items",
        **form(
            url="javascript:alert(1)", title="Mi título", category_id="2", note="Nota"
        ),
    )
    assert response.status_code == 422
    assert "La URL debe empezar con http://" in response.text
    assert 'value="Mi título"' in response.text
    assert ">Nota</textarea>" in response.text
    assert 'value="javascript:alert(1)"' in response.text
    # La categoría elegida sigue seleccionada (y solo esa).
    assert re.search(r'<option value="2"\s+selected>', response.text)
    assert not re.search(r'<option value="1"\s+selected>', response.text)


def test_filter_is_sent_to_the_backend(client, fake_backend):
    backend = FakeBackend()
    fake_backend(backend)
    logged_in(client)
    client.get("/items?category_id=2")
    assert ("GET", "/api/items", "category_id=2") in backend.calls


def test_garbage_filter_is_ignored(client, fake_backend):
    backend = FakeBackend()
    fake_backend(backend)
    logged_in(client)
    assert client.get("/items?category_id=abc").status_code == 200
    assert ("GET", "/api/items", "") in backend.calls


def test_foreign_filter_shows_message(client, fake_backend):
    fake_backend(FakeBackend(list_status=404))
    logged_in(client)
    response = client.get("/items?category_id=99")
    assert response.status_code == 404
    assert "No existe esa categoría." in response.text


def test_empty_states(client, fake_backend):
    fake_backend(FakeBackend(items=[]))
    logged_in(client)
    assert "Todavía no guardaste nada." in client.get("/items").text
    assert "No hay items en esta categoría." in client.get("/items?category_id=1").text


def test_delete_redirects_and_keeps_the_filter(client, fake_backend):
    backend = FakeBackend()
    fake_backend(backend)
    logged_in(client)
    response = client.post("/items/10/delete", **form(filter="1"))
    assert response.status_code == 303
    assert response.headers["location"] == "/items?category_id=1"
    assert ("DELETE", "/api/items/10", "") in backend.calls


def test_without_session_redirects_to_login(client, fake_backend):
    fake_backend(FakeBackend())
    assert client.get("/items").headers["location"] == "/login"


def test_backend_down_gives_503(client, fake_backend):
    def down(request):
        raise httpx.ConnectError("refused", request=request)

    fake_backend(down)
    logged_in(client)
    assert client.get("/items").status_code == 503
