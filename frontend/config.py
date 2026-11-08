"""Frontend configuration, read from environment variables only."""

import os

ALLOWED_DEPLOYMENTS = ("local", "dev", "prod")
DEFAULT_BACKEND_URL = "http://localhost:8001"


def get_deployment() -> str:
    """Return DEPLOYMENT, defaulting to "local"; fail on any other value."""
    value = os.environ.get("DEPLOYMENT", "local")
    if value not in ALLOWED_DEPLOYMENTS:
        allowed = ", ".join(ALLOWED_DEPLOYMENTS)
        raise ValueError(f"Invalid DEPLOYMENT={value!r}. Allowed values: {allowed}.")
    return value


def get_backend_url() -> str:
    """Return the backend base URL, without a trailing slash."""
    return os.environ.get("BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")
