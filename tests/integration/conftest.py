"""Integration tests run against a real Postgres, in a database they may wipe."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.config import to_psycopg_url
from backend.db import create_db_engine

ROOT = Path(__file__).resolve().parents[2]
DEV_DATABASE_NAME = "para_luego"
# La base descartable de `make test-integration` (docker-compose.test.yml).
DEFAULT_TEST_DATABASE_URL = (
    "postgresql://para_luego:para_luego_local@localhost:5433/para_luego_test"
)


def run_alembic(database_url: str, *args: str) -> None:
    """Run an alembic command; env.py reads DATABASE_URL from the environment."""
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        config = Config(str(ROOT / "alembic.ini"))
        getattr(command, args[0])(config, *args[1:])
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


@pytest.fixture(scope="session")
def database_url() -> str:
    raw = os.environ.get("TEST_DATABASE_URL") or DEFAULT_TEST_DATABASE_URL
    url = make_url(to_psycopg_url(raw))
    if not url.database or url.database == DEV_DATABASE_NAME:
        pytest.exit(
            "TEST_DATABASE_URL must name a separate test database "
            f"(not {DEV_DATABASE_NAME!r}).",
            returncode=2,
        )

    # Crear la base de test si falta, conectándose a la base de mantenimiento.
    admin = create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 5},
    )
    try:
        with admin.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError:
        pytest.exit(
            f"Postgres is not reachable at {url.host}:{url.port}. "
            "Run `make test-integration` (it starts a throwaway Postgres) "
            "or set TEST_DATABASE_URL.",
            returncode=1,
        )
    finally:
        admin.dispose()
    return url.render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def engine(database_url):
    # Esquema limpio en cada corrida: base → head.
    run_alembic(database_url, "downgrade", "base")
    run_alembic(database_url, "upgrade", "head")
    engine = create_db_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    session = Session(engine)
    yield session
    session.rollback()
    session.close()
    # Cada test deja la base vacía.
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, incidents RESTART IDENTITY CASCADE"))
