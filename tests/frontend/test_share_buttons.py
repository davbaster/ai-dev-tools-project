"""WhatsApp and Copiar buttons on /items and on the Daily, with a fake backend."""

import html
import re

import httpx
import pytest

from frontend.share import share_text, whatsapp_url

USER = {"id": 1, "username": "ana", "is_admin": False}
CATEGORIES = [{"id": 1, "name": "Leer", "item_count": 2}]
EVIL = {
    "id": 10,
    "url": "https://example.com/a?x=1&y=2",
    "title": '"><img src=x onerror=alert(1)>',
    "note": "Para Luis",
    "category_id": 1,
    "category_name": "Leer",
    "created_at": "2026-11-08T12:00:00+00:00",
}
PLAIN = {**EVIL, "id": 11, "title": "Un video", "note": None}


def backend(items):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/me":
            return httpx.Response(200, json=USER)
        if path == "/api/daily":
            return httpx.Response(200, json={"date": "2026-11-08", "items": items})
        if path == "/api/categories":
            return httpx.Response(200, json=CATEGORIES)
        if path == "/api/items":
            return httpx.Response(200, json=items)
        return httpx.Response(404, json={"detail": "Not Found"})

    return handler


def page(client, fake_backend, path, items):
    fake_backend(backend(items))
    client.cookies.set("pl_session", "fake-token")
    return client.get(path).text


def copy_values(text):
    return [html.unescape(v) for v in re.findall(r'data-copy="([^"]*)"', text)]


@pytest.mark.parametrize("path", ["/items", "/"])
def test_every_item_has_whatsapp_link_and_copy_button(client, fake_backend, path):
    text = page(client, fake_backend, path, [EVIL, PLAIN])
    for item in (EVIL, PLAIN):
        link = html.escape(whatsapp_url(item))
        assert f'<a href="{link}" target="_blank" rel="noopener noreferrer"' in text
    assert copy_values(text) == [share_text(EVIL), share_text(PLAIN)]
    assert text.count(">Copiar</button>") == 2


@pytest.mark.parametrize("path", ["/items", "/"])
def test_malicious_title_stays_escaped(client, fake_backend, path):
    text = page(client, fake_backend, path, [EVIL])
    assert "<img src=x" not in text
    assert "&#34;&gt;&lt;img src=x onerror=alert(1)&gt;" in text


@pytest.mark.parametrize("path", ["/items", "/"])
def test_no_buttons_without_items(client, fake_backend, path):
    text = page(client, fake_backend, path, [])
    assert "wa.me" not in text and 'data-copy="' not in text


def test_script_has_no_user_data(client, fake_backend):
    text = page(client, fake_backend, "/", [EVIL])
    script = text[text.index("<script>") : text.index("</script>")]
    assert "example.com" not in script and "Para Luis" not in script
