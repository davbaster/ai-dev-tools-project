from fastapi.testclient import TestClient

from app.main import DEPLOYMENT, app

client = TestClient(app)


def test_index_shows_app_name():
    response = client.get("/")
    assert response.status_code == 200
    assert "Para Luego" in response.text


def test_health_reports_status_and_deployment():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "deployment": DEPLOYMENT}


def test_unknown_route_returns_404():
    assert client.get("/nope").status_code == 404
