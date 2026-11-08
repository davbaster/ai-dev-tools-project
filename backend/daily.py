"""Daily: one random item per category that has items (api/openapi.yaml).

The pick is seeded with the user id and the Costa Rica date, so it stays the
same all day and changes the next day. Nothing is stored.
"""

import random
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from typing import Protocol

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from backend.auth import DB, CurrentToken
from backend.items import ItemOut, item_out
from backend.models import Category, Item

# Costa Rica no tiene horario de verano: un offset fijo evita depender de tzdata.
DAILY_TIMEZONE = timezone(timedelta(hours=-6))

router = APIRouter(prefix="/api")


class Pickable(Protocol):
    id: int
    category_id: int


def today() -> date:
    return datetime.now(DAILY_TIMEZONE).date()


def pick_daily[T: Pickable](items: Iterable[T], user_id: int, day: date) -> list[T]:
    """One item per category, ordered by category id; same inputs, same pick."""
    by_category: dict[int, list[T]] = defaultdict(list)
    for item in items:
        by_category[item.category_id].append(item)
    # El azar no es de seguridad: solo elige qué mostrar.
    rng = random.Random(f"{user_id}:{day.isoformat()}")  # nosec B311
    return [
        rng.choice(sorted(by_category[category_id], key=lambda item: item.id))
        for category_id in sorted(by_category)
    ]


class DailyOut(BaseModel):
    date: date
    items: list[ItemOut]


@router.get("/daily")
def get_daily(token: CurrentToken, db: DB) -> DailyOut:
    day = today()
    rows = db.execute(
        select(Item, Category.name)
        .join(Category, Category.id == Item.category_id)
        .where(Item.user_id == token.user_id)
    ).all()
    names = {item.id: name for item, name in rows}
    picked = pick_daily((item for item, _ in rows), token.user_id, day)
    return DailyOut(date=day, items=[item_out(item, names[item.id]) for item in picked])
