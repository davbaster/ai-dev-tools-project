"""Alembic environment. Reads DATABASE_URL from the environment, never from alembic.ini."""

from logging.config import fileConfig

from alembic import context

from backend.config import get_database_url
from backend.db import create_db_engine
from backend.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    try:
        return get_database_url()
    except ValueError as error:
        # Mensaje claro en vez de un traceback; nunca imprime la URL.
        raise SystemExit(f"alembic: {error}") from None


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_db_engine(database_url())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
