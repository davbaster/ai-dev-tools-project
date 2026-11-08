"""Frontend configuration, read from environment variables only."""

import os

ALLOWED_DEPLOYMENTS = ("local", "dev", "prod")
DEFAULT_BACKEND_URL = "http://localhost:8001"
DEFAULT_BACKEND_TIMEOUT = 2.0


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


def get_version() -> str:
    """Return APP_VERSION (the commit SHA baked into the image), or "local"."""
    return os.environ.get("APP_VERSION", "").strip() or "local"


def get_backend_timeout() -> float:
    """Seconds to wait for the backend (BACKEND_TIMEOUT_SECONDS, default 2).

    On Render a sleeping backend takes about a minute to wake up, so it is set
    higher there; a bad value stops startup.
    """
    raw = os.environ.get("BACKEND_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return DEFAULT_BACKEND_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        value = 0
    if value <= 0:
        raise ValueError(
            f"Invalid BACKEND_TIMEOUT_SECONDS={raw!r}. Use a number of seconds above 0."
        )
    return value
