"""Registration, login, logout and the current user (api/openapi.yaml)."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.defaults import add_default_categories
from backend.models import AuthToken, User
from backend.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    hash_token,
    new_token,
    normalize_username,
    verify_password,
)

TOKEN_LIFETIME = timedelta(days=7)

USERNAME_TAKEN = "Ese nombre de usuario ya está en uso."
WRONG_CREDENTIALS = "Usuario o contraseña incorrectos."
NOT_AUTHENTICATED = "Sesión inválida o vencida."

router = APIRouter(prefix="/api")

Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=3,
        max_length=50,
        # Pydantic revisa el patrón antes de pasar a minúsculas.
        pattern=r"^[A-Za-z0-9._-]+$",
    ),
]
NewPassword = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    username: Username
    password: NewPassword


class LoginRequest(BaseModel):
    username: Annotated[str, StringConstraints(max_length=200)]
    password: Annotated[str, StringConstraints(max_length=1024)]


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool


class LoginResponse(BaseModel):
    token: str
    user: UserOut


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, is_admin=user.is_admin)


def unauthorized(detail: str = NOT_AUTHENTICATED) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


DB = Annotated[Session, Depends(get_db)]


def current_token(
    db: DB, authorization: Annotated[str | None, Header()] = None
) -> AuthToken:
    """The valid (not expired) token from `Authorization: Bearer <token>`."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise unauthorized()
    row = db.scalars(
        select(AuthToken).where(
            AuthToken.token_hash == hash_token(token.strip()),
            AuthToken.expires_at > datetime.now(UTC),
        )
    ).first()
    if row is None:
        raise unauthorized()
    return row


CurrentToken = Annotated[AuthToken, Depends(current_token)]


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: DB) -> UserOut:
    if db.scalars(select(User.id).where(User.username == body.username)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail=USERNAME_TAKEN)
    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    try:
        # Usuario y categorías por defecto en la misma transacción.
        db.flush()
        add_default_categories(db, user.id)
        db.commit()
    except IntegrityError:
        # Dos registros simultáneos con el mismo nombre.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=USERNAME_TAKEN) from None
    return user_out(user)


@router.post("/auth/login")
def login(body: LoginRequest, db: DB) -> LoginResponse:
    username = normalize_username(body.username)
    user = db.scalars(select(User).where(User.username == username)).first()
    # Verificar siempre, para que un usuario inexistente tarde lo mismo.
    password_ok = verify_password(
        body.password, user.password_hash if user else DUMMY_PASSWORD_HASH
    )
    if user is None or not password_ok:
        raise unauthorized(WRONG_CREDENTIALS)

    token = new_token()
    db.add(
        AuthToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + TOKEN_LIFETIME,
        )
    )
    db.commit()
    return LoginResponse(token=token, user=user_out(user))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: CurrentToken, db: DB) -> Response:
    db.execute(delete(AuthToken).where(AuthToken.id == token.id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def get_me(token: CurrentToken, db: DB) -> UserOut:
    user = db.get(User, token.user_id)
    if user is None:
        raise unauthorized()
    return user_out(user)
