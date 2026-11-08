"""Frontend pages, with the backend faked by responses shaped like the contract."""

import httpx
import pytest
from fastapi.testclient import TestClient

from frontend.api_client import BackendClient
from frontend.main import DEPLOYMENT, app, get_backend_client


def fake_backend(handler):
    """Make the frontend use a fake backend instead of the network."""
    client = BackendClient(
        "http://backend.test", transport=httpx.MockTransport(handler)
    )
    app.dependency_overrides[get_backend_client] = lambda: client


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_index_shows_app_name_and_backend_status(client):
    fake_backend(
        lambda request: httpx.Response(
            200, json={"status": "ok", "deployment": "local"}
        )
    )
    response = client.get("/")
    assert response.status_code == 200
    assert "Para Luego" in response.text
    assert "Backend: ok (local)" in response.text


def test_index_when_backend_is_down(client):
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    fake_backend(refuse)
    response = client.get("/")
    assert response.status_code == 200
    assert "Backend: unavailable" in response.text


def test_index_when_backend_times_out(client):
    def too_slow(request):
        raise httpx.ReadTimeout("timed out", request=request)

    fake_backend(too_slow)
    response = client.get("/")
    assert response.status_code == 200
    assert "Backend: unavailable" in response.text


def test_index_when_backend_returns_error(client):
    fake_backend(lambda request: httpx.Response(500, json={"detail": "boom"}))
    assert "Backend: unavailable" in client.get("/").text


def test_frontend_health_does_not_call_backend(client):
    def fail(request):
        raise AssertionError("frontend /health must not call the backend")

    fake_backend(fail)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "deployment": DEPLOYMENT}


def test_unknown_route_returns_404(client):
    assert client.get("/nope").status_code == 404
