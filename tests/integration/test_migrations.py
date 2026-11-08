from sqlalchemy import inspect, text

from backend.defaults import DEFAULT_CATEGORIES
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


def category_names(connection, username) -> list[str]:
    return (
        connection.execute(
            text(
                "SELECT c.name FROM categories c JOIN users u ON u.id = c.user_id "
                "WHERE u.username = :username ORDER BY c.id"
            ),
            {"username": username},
        )
        .scalars()
        .all()
    )


def test_0003_backfills_defaults_only_for_users_without_categories(
    engine, database_url, session
):
    run_alembic(database_url, "downgrade", "0002")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (username, password_hash) "
                "VALUES ('old', 'x'), ('has_one', 'x')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO categories (user_id, name) "
                "SELECT id, 'Mía' FROM users WHERE username = 'has_one'"
            )
        )

    run_alembic(database_url, "upgrade", "head")
    # Correrla de nuevo (bajar a 0002 y subir) no agrega duplicados.
    run_alembic(database_url, "downgrade", "0002")
    run_alembic(database_url, "upgrade", "head")

    with engine.connect() as connection:
        assert category_names(connection, "old") == list(DEFAULT_CATEGORIES)
        assert category_names(connection, "has_one") == ["Mía"]


def test_models_match_migrations(engine, database_url):
    # `alembic check` falla si los modelos y las migraciones difieren.
    run_alembic(database_url, "check")
