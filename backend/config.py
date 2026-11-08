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

import os
