"""Frontend basics. Since #4 the backend status is shown on the login page."""

import httpx

from frontend.main import DEPLOYMENT, VERSION


def health_ok(request):
    return httpx.Response(
        200, json={"status": "ok", "deployment": "local", "version": "local"}
    )


def test_login_page_shows_app_name_and_backend_status(client, fake_backend):
    fake_backend(health_ok)
    response = client.get("/login")
    assert response.status_code == 200
    assert "Para Luego" in response.text
    assert "Backend: ok (local)" in response.text


def test_login_page_when_backend_is_down(client, fake_backend):
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    fake_backend(refuse)
    response = client.get("/login")
    assert response.status_code == 200
    assert "Backend: unavailable" in response.text


def test_login_page_when_backend_times_out(client, fake_backend):
    def too_slow(request):
        raise httpx.ReadTimeout("timed out", request=request)

    fake_backend(too_slow)
    response = client.get("/login")
    assert response.status_code == 200
    assert "Backend: unavailable" in response.text


def test_login_page_when_backend_returns_error(client, fake_backend):
    fake_backend(lambda request: httpx.Response(500, json={"detail": "boom"}))
    assert "Backend: unavailable" in client.get("/login").text


def test_frontend_health_does_not_call_backend(client, fake_backend):
    def fail(request):
        raise AssertionError("frontend /health must not call the backend")

    fake_backend(fail)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "deployment": DEPLOYMENT,
        "version": VERSION,
    }


def test_unknown_route_returns_404(client):
    assert client.get("/nope").status_code == 404
