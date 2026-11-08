"""Daily section on the dashboard with a fake backend (shapes from api/openapi.yaml)."""

import httpx

USER = {"id": 1, "username": "ana", "is_admin": False}
DAILY_ITEMS = [
    {
        "id": 10,
        "url": "https://example.com/a",
        "title": "<img src=x onerror=alert(1)>",
        "note": "Para Luis",
        "category_id": 1,
        "category_name": "Leer",
        "created_at": "2026-11-08T12:00:00+00:00",
    },
    {
        "id": 11,
        "url": "https://example.com/v",
        "title": "Un video",
        "note": None,
        "category_id": 2,
        "category_name": "<b>Ver</b>",
        "created_at": "2026-11-08T12:00:00+00:00",
    },
]


def backend(items=DAILY_ITEMS, daily_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/me":
            return httpx.Response(200, json=USER)
        if request.url.path == "/api/daily":
            if daily_status == 401:
                return httpx.Response(
                    401, json={"detail": "Sesión inválida o vencida."}
                )
            return httpx.Response(200, json={"date": "2026-11-08", "items": items})
        return httpx.Response(404, json={"detail": "Not Found"})

    return handler


def logged_in(client):
    client.cookies.set("pl_session", "fake-token")


def test_daily_cards_show_category_link_and_note(client, fake_backend):
    fake_backend(backend())
    logged_in(client)
    page = client.get("/").text
    assert "Tu Daily" in page
    assert (
        '<a href="https://example.com/a" target="_blank" rel="noopener noreferrer">'
        in page
    )
    assert "Leer" in page and "Para Luis" in page and "Un video" in page
    assert page.count('class="note"') == 1


def test_daily_text_is_escaped(client, fake_backend):
    fake_backend(backend())
    logged_in(client)
    page = client.get("/").text
    assert "<img src=x" not in page and "&lt;img src=x onerror=alert(1)&gt;" in page
    assert "<b>Ver</b>" not in page and "&lt;b&gt;Ver&lt;/b&gt;" in page


def test_empty_daily_links_to_items(client, fake_backend):
    fake_backend(backend(items=[]))
    logged_in(client)
    page = client.get("/").text
    assert "Todavía no guardaste nada." in page
    assert 'href="/items">Guardá tu primer item' in page


def test_expired_session_on_daily_clears_cookie(client, fake_backend):
    fake_backend(backend(daily_status=401))
    logged_in(client)
    response = client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert 'pl_session=""' in response.headers["set-cookie"]


def test_backend_down_gives_503(client, fake_backend):
    def down(request):
        raise httpx.ConnectError("down")

    fake_backend(down)
    logged_in(client)
    assert client.get("/").status_code == 503
