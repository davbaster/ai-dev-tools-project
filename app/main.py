"""Para Luego FastAPI application."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.config import get_deployment

# Validated at import time so the app refuses to start with a bad value.
DEPLOYMENT = get_deployment()

app = FastAPI(title="Para Luego")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return "<h1>Para Luego</h1><p>Save it for later.</p>"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "deployment": DEPLOYMENT}
