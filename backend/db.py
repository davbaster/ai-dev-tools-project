"""Database engine and sessions. The engine is created on first use, not at import."""

from collections.abc import Iterator
from functools import lru_cache

from opentelemetry import trace
from opentelemetry.instrumentation.sqlalchemy.engine import EngineTracer
from opentelemetry.metrics import NoOpMeterProvider
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import get_database_url

# Segundos para conectar antes de fallar (evita colgarse si Postgres no responde).
# Con "localhost", psycopg prueba IPv6 e IPv4: el peor caso es el doble.
CONNECT_TIMEOUT_SECONDS = 3

# Spans de base de datos (#13). EngineTracer solo engancha los eventos del
# engine: SQLAlchemyInstrumentor().instrument() además parchea el módulo asyncio
# (pide greenlet) y declara soporte solo hasta SQLAlchemy < 2.1.
_DB_TRACER = trace.get_tracer("opentelemetry.instrumentation.sqlalchemy")
_DB_CONNECTIONS = NoOpMeterProvider().get_meter("db").create_up_down_counter("db")


def create_db_engine(url: str) -> Engine:
    engine = create_engine(
        url,
        pool_pre_ping=True,
        # No loguear SQL ni la URL: puede contener la contraseña.
        echo=False,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )
    # La sentencia con sus marcadores, nunca los valores; sin comentarios SQL.
    EngineTracer(_DB_TRACER, engine, _DB_CONNECTIONS, enable_commenter=False)
    return engine


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
