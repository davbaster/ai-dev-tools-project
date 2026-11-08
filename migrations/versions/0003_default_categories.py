"""Backfill the default categories for users that have none.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-08

Data-only migration. New users get the defaults at registration (#6); this
covers users created before that. Running it again adds nothing.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Copia de backend/defaults.py: una migración no importa código de la app.
DEFAULT_CATEGORIES = ("Leer", "Ver", "Comprar", "Compartir", "Proyectos")


def upgrade() -> None:
    values = ", ".join(
        f"({position}, '{name}')" for position, name in enumerate(DEFAULT_CATEGORIES)
    )
    op.execute(
        sa.text(
            "INSERT INTO categories (user_id, name) "
            "SELECT u.id, d.name "
            f"FROM users u CROSS JOIN (VALUES {values}) AS d(position, name) "
            "WHERE NOT EXISTS (SELECT 1 FROM categories c WHERE c.user_id = u.id) "
            "ORDER BY u.id, d.position"
        )
    )


def downgrade() -> None:
    # No se puede saber qué categorías vinieron de este backfill: no se borra nada.
    pass
