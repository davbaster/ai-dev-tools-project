"""Frontend tests fake the backend with responses shaped like api/openapi.yaml."""

import httpx
import pytest
from fastapi.testclient import TestClient

from frontend.api_client import BackendClient
from frontend.main import app, get_backend_client


@pytest.fixture
def fake_backend():
    """Call fake_backend(handler) to answer the frontend's backend calls."""

    def install(handler):
        client = BackendClient(
            "http://backend.test", transport=httpx.MockTransport(handler)
        )
        app.dependency_overrides[get_backend_client] = lambda: client

    yield install
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    # Sin seguir redirects, para poder revisar el 303 y la cookie.
    return TestClient(app, follow_redirects=False)
