"""Items: save, list (optionally by category) and delete (api/openapi.yaml).

`POST /api/items` is the key user journey. Never log an item's URL, title or note.
"""

import logging
from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Response, status
from opentelemetry import metrics, trace
from pydantic import BaseModel, StringConstraints, field_validator
from sqlalchemy import select

from backend.auth import DB, CurrentToken
from backend.models import Category, Item

URL_MAX_LENGTH = 2048
NOT_YOUR_CATEGORY = "Elegí una de tus categorías."
CATEGORY_NOT_FOUND = "No existe esa categoría."
ITEM_NOT_FOUND = "No existe ese item."

router = APIRouter(prefix="/api")

# Solo ids en spans, métricas y logs (#13).
log = logging.getLogger("backend.items")
items_saved = metrics.get_meter("para_luego.backend").create_counter(
    "items.saved", unit="{item}", description="Items saved"
)

Title = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class ItemCreate(BaseModel):
    url: str
    title: Title | None = None
    category_id: int
    note: Note | None = None

    @field_validator("url")
    @classmethod
    def http_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        # Solo http(s) con host: bloquea javascript:, data:, ftp: y URLs sin esquema.
        if (
            len(value) > URL_MAX_LENGTH
            or parsed.scheme.lower() not in ("http", "https")
            or not parsed.netloc
        ):
            raise ValueError("invalid url")
        return value


class ItemOut(BaseModel):
    id: int
    url: str
    title: str
    note: str | None
    category_id: int
    category_name: str
    created_at: datetime


def own_category(db, user_id: int, category_id: int) -> Category | None:
    category = db.get(Category, category_id)
    if category is None or category.user_id != user_id:
        return None
    return category


def item_out(item: Item, category_name: str) -> ItemOut:
    return ItemOut(
        id=item.id,
        url=item.url,
        title=item.title,
        note=item.note,
        category_id=item.category_id,
        category_name=category_name,
        created_at=item.created_at,
    )


@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(body: ItemCreate, token: CurrentToken, db: DB) -> ItemOut:
    span = trace.get_current_span()
    span.set_attributes({"user_id": token.user_id, "category_id": body.category_id})
    category = own_category(db, token.user_id, body.category_id)
    if category is None:
        # Misma respuesta para una categoría inexistente o ajena.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[{"field": "category_id", "message": NOT_YOUR_CATEGORY}],
        )
    item = Item(
        user_id=token.user_id,
        category_id=category.id,
        url=body.url,
        title=body.title or body.url,
        note=body.note or None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    span.set_attribute("item_id", item.id)
    items_saved.add(1)
    log.info(
        "item saved",
        extra={
            "fields": {
                "user_id": token.user_id,
                "item_id": item.id,
                "category_id": item.category_id,
            }
        },
    )
    return item_out(item, category.name)


@router.get("/items")
def list_items(
    token: CurrentToken, db: DB, category_id: int | None = None
) -> list[ItemOut]:
    query = (
        select(Item, Category.name)
        .join(Category, Category.id == Item.category_id)
        .where(Item.user_id == token.user_id)
        .order_by(Item.created_at.desc(), Item.id.desc())
    )
    if category_id is not None:
        if own_category(db, token.user_id, category_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=CATEGORY_NOT_FOUND)
        query = query.where(Item.category_id == category_id)
    return [item_out(item, name) for item, name in db.execute(query).all()]


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, token: CurrentToken, db: DB) -> Response:
    item = db.get(Item, item_id)
    if item is None or item.user_id != token.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=ITEM_NOT_FOUND)
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
