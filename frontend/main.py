"""Para Luego frontend: HTML pages that get their data from the backend API."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from frontend.api_client import BackendClient
from frontend.config import get_backend_url, get_deployment

# Validated at import time so the frontend refuses to start with a bad value.
DEPLOYMENT = get_deployment()
BACKEND_URL = get_backend_url()

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

app = FastAPI(title="Para Luego", docs_url=None, redoc_url=None, openapi_url=None)


def get_backend_client() -> BackendClient:
    # Los tests lo reemplazan con app.dependency_overrides para simular el backend.
    return BackendClient(BACKEND_URL)


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request, backend: Annotated[BackendClient, Depends(get_backend_client)]
):
    health = backend.get_health()
    if health is None:
        backend_status = "unavailable"
    else:
        backend_status = f"{health['status']} ({health['deployment']})"
    return templates.TemplateResponse(
        request, "index.html", {"backend_status": backend_status}
    )


@app.get("/health")
def health() -> dict[str, str]:
    # Salud propia del frontend: no llama al backend.
    return {"status": "ok", "deployment": DEPLOYMENT}
