"""The backend implements exactly the operations in api/openapi.yaml."""

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.main import app


def backend_operations() -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/")
        for method in route.methods
        if method != "HEAD"
    }


def test_contract_is_openapi_3_1(contract):
    assert contract["openapi"].startswith("3.1")


def test_backend_routes_match_contract(contract_operations):
    implemented = backend_operations()
    defined = set(contract_operations)
    assert implemented - defined == set(), "backend routes missing from the contract"
    assert defined - implemented == set(), "contract operations the backend lacks"


def test_health_response_matches_contract_schema(contract):
    schema = contract["components"]["schemas"]["Health"]
    body = TestClient(app).get("/api/health").json()
    for field in schema["required"]:
        assert field in body
        allowed = schema["properties"][field].get("enum")
        if allowed:
            assert body[field] in allowed
