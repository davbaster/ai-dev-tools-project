from fastapi.testclient import TestClient

from backend.main import DEPLOYMENT, app

client = TestClient(app)


def test_health_reports_status_and_deployment():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "deployment": DEPLOYMENT}


def test_unknown_api_path_returns_json_404():
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_generated_docs_are_off():
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
