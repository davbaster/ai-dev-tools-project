import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from backend.models import Category, Incident, Item, User


def add_user(session, username="ana") -> User:
    user = User(username=username, password_hash="not-a-real-hash")
    session.add(user)
    session.flush()
    return user


def add_category(session, user, name="Leer") -> Category:
    category = Category(user_id=user.id, name=name)
    session.add(category)
    session.flush()
    return category


def add_item(session, user, category) -> Item:
    item = Item(
        user_id=user.id,
        category_id=category.id,
        url="https://example.com/article",
        title="An article",
        note="For Luis",
    )
    session.add(item)
    session.flush()
    return item


def test_save_and_read_back_an_item(session):
    user = add_user(session)
    category = add_category(session, user)
    add_item(session, user, category)
    session.commit()

    saved = session.scalars(select(Item).where(Item.user_id == user.id)).one()
    assert saved.title == "An article"
    assert saved.note == "For Luis"
    assert saved.category_id == category.id
    assert saved.created_at.tzinfo is not None
    assert session.get(User, user.id).is_admin is False


def test_category_names_are_unique_per_user(session):
    ana = add_user(session, "ana")
    luis = add_user(session, "luis")
    add_category(session, ana, "Leer")
    add_category(session, luis, "Leer")  # otro usuario: permitido
    session.commit()

    with pytest.raises(IntegrityError):
        add_category(session, ana, "Leer")


def test_usernames_are_unique(session):
    add_user(session, "ana")
    with pytest.raises(IntegrityError):
        add_user(session, "ana")


def test_deleting_a_user_deletes_their_categories_and_items(session):
    user = add_user(session)
    category = add_category(session, user)
    add_item(session, user, category)
    session.commit()

    session.execute(delete(User).where(User.id == user.id))
    session.commit()

    assert session.scalars(select(Item)).all() == []
    assert session.scalars(select(Category)).all() == []


def test_deleting_a_category_with_items_is_refused(session):
    user = add_user(session)
    category = add_category(session, user)
    add_item(session, user, category)
    session.commit()

    with pytest.raises(IntegrityError):
        session.execute(delete(Category).where(Category.id == category.id))
        session.flush()


def test_incident_status_defaults_to_open_and_rejects_unknown_values(session):
    incident = Incident(alert_name="SaveItemFailing")
    session.add(incident)
    session.commit()
    session.refresh(incident)
    assert incident.status == "open"

    session.add(Incident(alert_name="HighServerErrors", status="closed"))
    with pytest.raises(IntegrityError):
        session.flush()
