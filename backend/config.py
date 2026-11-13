"""Configuration read from environment variables only."""

import os

ALLOWED_DEPLOYMENTS = ("local", "dev", "prod")
PLAIN_SCHEMES = ("postgresql://", "postgres://")
PSYCOPG_SCHEME = "postgresql+psycopg://"


def get_deployment() -> str:
    """Return DEPLOYMENT, defaulting to "local"; fail on any other value."""
    value = os.environ.get("DEPLOYMENT", "local")
    if value not in ALLOWED_DEPLOYMENTS:
        allowed = ", ".join(ALLOWED_DEPLOYMENTS)
        raise ValueError(f"Invalid DEPLOYMENT={value!r}. Allowed values: {allowed}.")
    return value


def to_psycopg_url(url: str) -> str:
    """Switch a plain postgresql:// URL (Compose, Render) to the psycopg 3 driver."""
    for scheme in PLAIN_SCHEMES:
        if url.startswith(scheme):
            return PSYCOPG_SCHEME + url[len(scheme) :]
    return url


def get_database_url() -> str:
    """Return DATABASE_URL for SQLAlchemy; fail with a clear message if unset."""
    value = os.environ.get("DATABASE_URL", "").strip()
    if not value:
        raise ValueError(
            "DATABASE_URL is not set. Example: "
            "postgresql://user:password@localhost:5432/para_luego"
        )
    return to_psycopg_url(value)


def get_version() -> str:
    """Return APP_VERSION (the commit SHA baked into the image), or "local"."""
    return os.environ.get("APP_VERSION", "").strip() or "local"


def short_titles_enabled() -> bool:
    """BUG_SAVE_ITEM=1 turns on the demo's long-title feature (#19); read per request."""
    return os.environ.get("BUG_SAVE_ITEM", "").strip() == "1"
