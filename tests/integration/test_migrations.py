from sqlalchemy import inspect

from tests.integration.conftest import run_alembic

APP_TABLES = {"users", "categories", "items", "incidents", "auth_tokens"}


def app_tables(engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_migrations_go_from_empty_to_head_and_back(engine, database_url):
    run_alembic(database_url, "downgrade", "base")
    assert app_tables(engine) == set()

    run_alembic(database_url, "upgrade", "head")
    assert app_tables(engine) == APP_TABLES

    # Una segunda vez no cambia nada ni falla.
    run_alembic(database_url, "upgrade", "head")
    assert app_tables(engine) == APP_TABLES


def test_models_match_migrations(engine, database_url):
    # `alembic check` falla si los modelos y las migraciones difieren.
    run_alembic(database_url, "check")
