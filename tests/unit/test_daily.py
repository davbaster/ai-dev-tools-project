"""Daily selection without a database."""

from dataclasses import dataclass
from datetime import date, timedelta

from backend.daily import pick_daily


@dataclass
class FakeItem:
    id: int
    category_id: int


ITEMS = [FakeItem(1, 10), FakeItem(2, 10), FakeItem(3, 10), FakeItem(4, 5)]
DAY = date(2026, 11, 8)


def test_one_item_per_category_ordered_by_category_id():
    picked = pick_daily(ITEMS, user_id=1, day=DAY)
    assert [item.category_id for item in picked] == [5, 10]
    assert picked[0].id == 4


def test_same_inputs_same_pick_whatever_the_order():
    assert pick_daily(ITEMS, 1, DAY) == pick_daily(list(reversed(ITEMS)), 1, DAY)


def test_every_item_gets_picked_over_many_days():
    seen = {
        pick_daily(ITEMS, 1, DAY + timedelta(days=offset))[1].id for offset in range(60)
    }
    assert seen == {1, 2, 3}


def test_no_items_no_daily():
    assert pick_daily([], 1, DAY) == []
