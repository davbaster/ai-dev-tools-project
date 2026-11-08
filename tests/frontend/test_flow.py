"""Login → save an item → see it on /items, through the frontend.

The fake backend keeps state like the real one would, with shapes from
api/openapi.yaml, so the frontend's own redirects and cookie drive the flow.
"""

import json
from urllib.parse import urlencode

import httpx

TOKEN = "flow-token"
USER = {"id": 1, "username": "ana", "is_admin": False}
CATEGORIES = [{"id": 1, "name": "Leer", "item_count": 0}]


class StatefulBackend:
    def __init__(self):
        self.items = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        if path == "/api/auth/login":
            return httpx.Response(200, json={"token": TOKEN, "user": USER})
        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            return httpx.Response(401, json={"detail": "Sesión inválida o vencida."})
        if path == "/api/me":
            return httpx.Response(200, json=USER)
        if path == "/api/daily":
            return httpx.Response(200, json={"date": "2026-11-08", "items": []})
        if path == "/api/categories":
            return httpx.Response(200, json=CATEGORIES)
        if path == "/api/items" and method == "POST":
            body = json.loads(request.content)
            item = {
                "id": len(self.items) + 1,
                "url": body["url"],
                "title": body.get("title") or body["url"],
                "note": body.get("note") or None,
                "category_id": body["category_id"],
                "category_name": "Leer",
                "created_at": "2026-11-08T12:00:00+00:00",
            }
            self.items.insert(0, item)
            return httpx.Response(201, json=item)
        if path == "/api/items" and method == "GET":
            return httpx.Response(200, json=self.items)
        return httpx.Response(404, json={"detail": "Not Found"})


def post_form(client, path, **fields):
    return client.post(
        path,
        content=urlencode(fields),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def test_login_save_and_list(client, fake_backend):
    fake_backend(StatefulBackend())

    login = post_form(client, "/login", username="ana", password="a long password")
    assert login.status_code == 303 and login.headers["location"] == "/"
    assert client.get("/").status_code == 200  # la cookie de sesión quedó puesta

    assert "Todavía no guardaste nada." in client.get("/items").text
    saved = post_form(
        client,
        "/items",
        url="https://example.com/flujo",
        title="Artículo del flujo",
        category_id="1",
        note="Para después",
        filter="",
    )
    assert saved.status_code == 303 and saved.headers["location"] == "/items"

    page = client.get("/items").text
    assert "Artículo del flujo" in page and "Para después" in page
    assert 'href="https://example.com/flujo"' in page
