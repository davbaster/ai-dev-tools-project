"""Categories: the five defaults plus the user's own (api/openapi.yaml)."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth import DB, CurrentToken
from backend.models import Category, Item

DUPLICATE_NAME = "Ya tenés una categoría con ese nombre."
HAS_ITEMS = "Esta categoría tiene items. Borralos o movelos antes."
NOT_FOUND = "No existe esa categoría."

router = APIRouter(prefix="/api")


class CategoryCreate(BaseModel):
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
    ]


class CategoryOut(BaseModel):
    id: int
    name: str
    item_count: int


def item_count(db: Session, category_id: int) -> int:
    return db.scalar(select(func.count(Item.id)).where(Item.category_id == category_id))


@router.get("/categories")
def list_categories(token: CurrentToken, db: DB) -> list[CategoryOut]:
    rows = db.execute(
        select(Category.id, Category.name, func.count(Item.id))
        .outerjoin(Item, Item.category_id == Category.id)
        .where(Category.user_id == token.user_id)
        .group_by(Category.id)
        .order_by(Category.id)
    ).all()
    return [CategoryOut(id=id_, name=name, item_count=n) for id_, name, n in rows]


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryCreate, token: CurrentToken, db: DB) -> CategoryOut:
    duplicate = db.scalars(
        select(Category.id).where(
            Category.user_id == token.user_id,
            func.lower(Category.name) == body.name.lower(),
        )
    ).first()
    if duplicate:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=DUPLICATE_NAME)
    category = Category(user_id=token.user_id, name=body.name)
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=DUPLICATE_NAME) from None
    return CategoryOut(id=category.id, name=category.name, item_count=0)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, token: CurrentToken, db: DB) -> Response:
    category = db.get(Category, category_id)
    # Misma respuesta si no existe o es de otro usuario: no revela ids ajenos.
    if category is None or category.user_id != token.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    if item_count(db, category_id) > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=HAS_ITEMS)
    db.delete(category)
    try:
        db.commit()
    except IntegrityError:
        # Alguien agregó un item justo ahora; la base lo rechaza (FK de #3).
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=HAS_ITEMS) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
