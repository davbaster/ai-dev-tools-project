"""Backend auth API against a real Postgres."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.main import app
from backend.models import AuthToken, User
from backend.security import hash_token

PASSWORD = "correct horse battery"


@pytest.fixture
def api(engine, session):
    # `session` (conftest) deja la base vacía al terminar cada test.
    def test_db():
        db = Session(engine, expire_on_commit=False)
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(api, username="ana", password=PASSWORD):
    return api.post(
        "/api/auth/register", json={"username": username, "password": password}
    )


def login(api, username="ana", password=PASSWORD):
    return api.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_full_flow_register_login_me_logout(api):
    created = register(api, "  Ana ")
    assert created.status_code == 201
    assert created.json()["username"] == "ana"
    assert created.json()["is_admin"] is False

    logged_in = login(api, "ANA")
    assert logged_in.status_code == 200
    token = logged_in.json()["token"]
    assert logged_in.json()["user"]["username"] == "ana"

    assert api.get("/api/me", headers=bearer(token)).json()["username"] == "ana"
    assert api.post("/api/auth/logout", headers=bearer(token)).status_code == 204
    assert api.get("/api/me", headers=bearer(token)).status_code == 401
    assert api.post("/api/auth/logout", headers=bearer(token)).status_code == 401


def test_duplicate_username_in_other_case_is_409(api):
    assert register(api, "ana").status_code == 201
    response = register(api, "ANA")
    assert response.status_code == 409
    assert "en uso" in response.json()["detail"]


def test_wrong_password_and_unknown_user_look_the_same(api):
    register(api)
    wrong_password = login(api, "ana", "not the password")
    unknown_user = login(api, "nobody", PASSWORD)
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


def test_me_without_or_with_bad_token_is_401(api):
    assert api.get("/api/me").status_code == 401
    assert api.get("/api/me", headers=bearer("made-up")).status_code == 401
    assert api.get("/api/me", headers={"Authorization": "Basic abc"}).status_code == 401


def test_expired_token_is_401(api, session):
    register(api)
    token = login(api).json()["token"]
    session.execute(
        update(AuthToken)
        .where(AuthToken.token_hash == hash_token(token))
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    session.commit()
    assert api.get("/api/me", headers=bearer(token)).status_code == 401


def test_token_expires_in_seven_days(api, session):
    register(api)
    token = login(api).json()["token"]
    row = session.scalars(
        select(AuthToken).where(AuthToken.token_hash == hash_token(token))
    ).one()
    lifetime = row.expires_at - datetime.now(UTC)
    assert timedelta(days=6, hours=23) < lifetime <= timedelta(days=7)


def test_two_sessions_are_independent(api):
    register(api)
    first = login(api).json()["token"]
    second = login(api).json()["token"]
    assert first != second
    api.post("/api/auth/logout", headers=bearer(first))
    assert api.get("/api/me", headers=bearer(second)).status_code == 200


def test_database_has_no_plain_password_or_token(api, session):
    register(api)
    token = login(api).json()["token"]
    user = session.scalars(select(User)).one()
    assert PASSWORD not in user.password_hash
    dump = session.execute(
        text("SELECT string_agg(t::text, ' ') FROM auth_tokens t")
    ).scalar()
    assert token not in dump


def test_same_password_gives_different_hashes_in_db(api, session):
    register(api, "ana")
    register(api, "luis")
    hashes = session.scalars(select(User.password_hash)).all()
    assert len(set(hashes)) == 2


def test_deleting_a_user_deletes_their_tokens(api, session):
    register(api)
    login(api)
    session.execute(text("DELETE FROM users"))
    session.commit()
    assert session.scalars(select(AuthToken)).all() == []


@pytest.mark.parametrize(
    ("username", "password", "field"),
    [
        ("ana", "short", "password"),
        ("a", "a perfectly fine password", "username"),
        ("ana maria", "a perfectly fine password", "username"),
    ],
)
def test_validation_errors_never_echo_the_password(api, username, password, field):
    response = register(api, username, password)
    assert response.status_code == 422
    assert password not in response.text
    assert field in {item["field"] for item in response.json()["detail"]}
