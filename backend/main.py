"""Para Luego backend: JSON API under /api, defined by api/openapi.yaml."""

from fastapi import FastAPI

from backend.config import get_deployment

# Validated at import time so the backend refuses to start with a bad value.
DEPLOYMENT = get_deployment()

# api/openapi.yaml is the contract, so FastAPI's generated docs are turned off.
app = FastAPI(title="Para Luego API", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/api/health")
def get_health() -> dict[str, str]:
    return {"status": "ok", "deployment": DEPLOYMENT}
