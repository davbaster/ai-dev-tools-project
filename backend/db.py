"""Database engine and sessions. The engine is created on first use, not at import."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import get_database_url

# Segundos para conectar antes de fallar (evita colgarse si Postgres no responde).
# Con "localhost", psycopg prueba IPv6 e IPv4: el peor caso es el doble.
CONNECT_TIMEOUT_SECONDS = 3


def create_db_engine(url: str) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        # No loguear SQL ni la URL: puede contener la contraseña.
        echo=False,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_db_engine(get_database_url())


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request. Tests override it."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
