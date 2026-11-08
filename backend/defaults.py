"""Default categories every user gets at registration."""

from sqlalchemy.orm import Session

from backend.models import Category

# Orden fijo: así aparecen al registrarse. La migración 0003 tiene una copia.
DEFAULT_CATEGORIES = ("Leer", "Ver", "Comprar", "Compartir", "Proyectos")


def add_default_categories(db: Session, user_id: int) -> None:
    """Add the defaults to the session; the caller commits (same transaction)."""
    for name in DEFAULT_CATEGORIES:
        db.add(Category(user_id=user_id, name=name))
