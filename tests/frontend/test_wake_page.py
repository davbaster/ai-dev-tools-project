"""Wake-up page: the browser wakes a sleeping Render backend (#11)."""

import httpx
import pytest

from frontend import config as frontend_config
from frontend import main as frontend_main

PUBLIC = "https://para-luego-dev-backend.onrender.com"
SCRIPT = f'data-health-url="{PUBLIC}/api/health"'


def down(request):
    raise httpx.ConnectError("asleep")


def health_ok(request):
    return httpx.Response(
        200, json={"status": "ok", "deployment": "dev", "version": "abc"}
    )


@pytest.fixture
def on_render(monkeypatch):
    monkeypatch.setattr(frontend_main, "BACKEND_PUBLIC_URL", PUBLIC)


@pytest.mark.parametrize("path", ["/", "/items", "/categories"])
def test_unavailable_page_wakes_the_backend_from_the_browser(
    client, fake_backend, on_render, path
):
    fake_backend(down)
    client.cookies.set("pl_session", "fake-token")
    response = client.get(path)
    assert response.status_code == 503
    assert response.headers["retry-after"] == "10"
    assert SCRIPT in response.text
    assert "Despertando el servicio" in response.text


def test_failed_login_submit_also_wakes(client, fake_backend, on_render):
    fake_backend(down)
    response = client.post(
        "/login",
        content="username=ana&password=a+long+password",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 503
    assert SCRIPT in response.text
    assert "a long password" not in response.text


def test_login_page_wakes_only_when_backend_is_unavailable(
    client, fake_backend, on_render
):
    fake_backend(down)
    assert SCRIPT in client.get("/login").text
    fake_backend(health_ok)
    page = client.get("/login").text
    assert "Backend: ok (dev)" in page and "data-health-url" not in page


def test_without_public_url_the_plain_503_page_stays(client, fake_backend):
    fake_backend(down)
    client.cookies.set("pl_session", "fake-token")
    response = client.get("/")
    assert response.status_code == 503
    assert "data-health-url" not in response.text


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("", None), (f"{PUBLIC}/", PUBLIC), (PUBLIC, PUBLIC)],
)
def test_public_url_config(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("BACKEND_PUBLIC_URL", raising=False)
    else:
        monkeypatch.setenv("BACKEND_PUBLIC_URL", value)
    assert frontend_config.get_backend_public_url() == expected
