"""Categories page with a fake backend (shapes from api/openapi.yaml)."""

from urllib.parse import urlencode

import httpx

CATEGORIES = [
    {"id": 1, "name": "Leer", "item_count": 2},
    {"id": 2, "name": "<script>alert(1)</script>", "item_count": 0},
]


class FakeBackend:
    def __init__(self, create_status=201, delete_status=204, list_status=200):
        self.create_status = create_status
        self.delete_status = delete_status
        self.list_status = list_status
        self.calls = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        if request.url.path == "/api/categories" and request.method == "GET":
            if self.list_status == 401:
                return httpx.Response(
                    401, json={"detail": "Sesión inválida o vencida."}
                )
            return httpx.Response(200, json=CATEGORIES)
        if request.url.path == "/api/categories" and request.method == "POST":
            if self.create_status == 201:
                return httpx.Response(
                    201, json={"id": 3, "name": "Música", "item_count": 0}
                )
            if self.create_status == 409:
                return httpx.Response(
                    409, json={"detail": "Ya tenés una categoría con ese nombre."}
                )
            return httpx.Response(
                422,
                json={
                    "detail": [
                        {
                            "field": "name",
                            "message": "El nombre debe tener entre 1 y 50 caracteres.",
                        }
                    ]
                },
            )
        if (
            request.url.path.startswith("/api/categories/")
            and request.method == "DELETE"
        ):
            if self.delete_status == 204:
                return httpx.Response(204)
            return httpx.Response(
                409,
                json={
                    "detail": "Esta categoría tiene items. Borralos o movelos antes."
                },
            )
        return httpx.Response(404, json={"detail": "Not Found"})


def form(**fields):
    return {
        "content": urlencode(fields),
        "headers": {"Content-Type": "application/x-www-form-urlencoded"},
    }


def logged_in(client):
    client.cookies.set("pl_session", "fake-token")


def test_list_shows_names_counts_form_and_delete_buttons(client, fake_backend):
    fake_backend(FakeBackend())
    logged_in(client)
    response = client.get("/categories")
    assert response.status_code == 200
    assert "Leer" in response.text
    assert "(2 items)" in response.text
    assert 'action="/categories"' in response.text
    assert 'action="/categories/1/delete"' in response.text


def test_names_are_escaped(client, fake_backend):
    fake_backend(FakeBackend())
    logged_in(client)
    text = client.get("/categories").text
    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;" in text


def test_add_success_redirects_back(client, fake_backend):
    backend = FakeBackend()
    fake_backend(backend)
    logged_in(client)
    response = client.post("/categories", **form(name="Música"))
    assert response.status_code == 303
    assert response.headers["location"] == "/categories"
    assert ("POST", "/api/categories") in backend.calls


def test_add_duplicate_shows_message_and_keeps_name(client, fake_backend):
    fake_backend(FakeBackend(create_status=409))
    logged_in(client)
    response = client.post("/categories", **form(name="leer"))
    assert response.status_code == 409
    assert "Ya tenés una categoría con ese nombre." in response.text
    assert 'value="leer"' in response.text


def test_add_invalid_shows_message(client, fake_backend):
    fake_backend(FakeBackend(create_status=422))
    logged_in(client)
    response = client.post("/categories", **form(name=""))
    assert response.status_code == 422
    assert "entre 1 y 50 caracteres" in response.text


def test_delete_with_items_shows_message(client, fake_backend):
    fake_backend(FakeBackend(delete_status=409))
    logged_in(client)
    response = client.post("/categories/1/delete")
    assert response.status_code == 409
    assert "Esta categoría tiene items" in response.text
    assert "Leer" in response.text


def test_delete_success_redirects_back(client, fake_backend):
    backend = FakeBackend()
    fake_backend(backend)
    logged_in(client)
    response = client.post("/categories/2/delete")
    assert response.status_code == 303
    assert ("DELETE", "/api/categories/2") in backend.calls


def test_without_session_redirects_to_login(client, fake_backend):
    fake_backend(FakeBackend())
    assert client.get("/categories").headers["location"] == "/login"
    assert client.post("/categories", **form(name="x")).headers["location"] == "/login"


def test_expired_session_clears_cookie(client, fake_backend):
    fake_backend(FakeBackend(list_status=401))
    logged_in(client)
    response = client.get("/categories")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_backend_down_gives_503(client, fake_backend):
    def down(request):
        raise httpx.ConnectError("refused", request=request)

    fake_backend(down)
    logged_in(client)
    assert client.get("/categories").status_code == 503


def test_home_links_to_categories(client, fake_backend):
    def me(request):
        if request.url.path == "/api/daily":
            return httpx.Response(200, json={"date": "2026-11-08", "items": []})
        return httpx.Response(200, json={"id": 1, "username": "ana", "is_admin": False})

    fake_backend(me)
    logged_in(client)
    assert 'href="/categories"' in client.get("/").text
