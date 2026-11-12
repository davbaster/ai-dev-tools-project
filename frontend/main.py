"""Para Luego frontend: HTML pages that get their data from the backend API."""

from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

import telemetry
from frontend.api_client import BackendClient, BackendUnavailable
from frontend.config import (
    get_backend_public_url,
    get_backend_timeout,
    get_backend_url,
    get_backend_wake_seconds,
    get_deployment,
    get_version,
)
from frontend.share import share_text, whatsapp_url

# Validated at import time so the frontend refuses to start with a bad value.
DEPLOYMENT = get_deployment()
BACKEND_URL = get_backend_url()
BACKEND_TIMEOUT = get_backend_timeout()
BACKEND_WAKE_SECONDS = get_backend_wake_seconds()
BACKEND_PUBLIC_URL = get_backend_public_url()
VERSION = get_version()

SESSION_COOKIE = "pl_session"
SESSION_MAX_AGE = 7 * 24 * 60 * 60  # igual que el token del backend
SECURE_COOKIE = DEPLOYMENT in ("dev", "prod")

UNAVAILABLE = "El servicio no está disponible, probá de nuevo en un momento."
WRONG_CREDENTIALS = "Usuario o contraseña incorrectos"

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals.update(share_text=share_text, whatsapp_url=whatsapp_url)

app = FastAPI(title="Para Luego", docs_url=None, redoc_url=None, openapi_url=None)
# JSON logs, spans and request metrics (#13), before the routes are used.
telemetry.setup(app, "para-luego-frontend", DEPLOYMENT, VERSION)


def get_backend_client() -> BackendClient:
    # Los tests lo reemplazan con app.dependency_overrides para simular el backend.
    return BackendClient(
        BACKEND_URL, timeout=BACKEND_TIMEOUT, wake_seconds=BACKEND_WAKE_SECONDS
    )


Backend = Annotated[BackendClient, Depends(get_backend_client)]


async def read_form(request: Request) -> dict[str, str]:
    """Parse an application/x-www-form-urlencoded body (no python-multipart)."""
    fields = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    return {key: values[0] for key, values in fields.items()}


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def set_session(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=SECURE_COOKIE,
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True, samesite="lax", secure=SECURE_COOKIE
    )


def render(request: Request, template: str, status_code: int = 200, **context):
    return templates.TemplateResponse(
        request, template, context, status_code=status_code
    )


def unavailable_page(request: Request) -> HTMLResponse:
    # En Render, el navegador despierta al backend y recarga (_wake.html).
    response = render(
        request, "error.html", 503, message=UNAVAILABLE, wake_url=BACKEND_PUBLIC_URL
    )
    response.headers["Retry-After"] = "10"
    return response


def backend_status(backend: BackendClient) -> str:
    health = backend.get_health()
    if health is None:
        return "unavailable"
    return f"{health['status']} ({health['deployment']})"


def error_messages(body) -> list[str]:
    """Messages from a backend Error (409) or ValidationError (422) body."""
    detail = (body or {}).get("detail")
    if isinstance(detail, str):
        return [detail]
    if isinstance(detail, list):
        return list(dict.fromkeys(item.get("message", "") for item in detail))
    return ["Dato inválido."]


@app.get("/", response_class=HTMLResponse)
def index(request: Request, backend: Backend):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return redirect("/login")
    try:
        me = backend.get_me(token)
        daily = backend.get_daily(token) if me.ok else None
    except BackendUnavailable:
        return unavailable_page(request)
    if not me.ok or not daily.ok:
        return session_expired()
    return render(request, "index.html", user=me.body, daily=daily.body["items"])


def session_expired() -> RedirectResponse:
    # Token vencido o revocado: borrar la cookie y pedir login.
    response = redirect("/login")
    clear_session(response)
    return response


def categories_page(
    request: Request,
    backend: BackendClient,
    token: str,
    status_code: int = 200,
    errors: list[str] | None = None,
    name: str = "",
):
    listed = backend.list_categories(token)
    if listed.status == 401:
        return session_expired()
    return render(
        request,
        "categories.html",
        status_code,
        categories=listed.body,
        errors=errors,
        name=name,
    )


@app.get("/categories", response_class=HTMLResponse)
def list_categories(request: Request, backend: Backend):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return redirect("/login")
    try:
        return categories_page(request, backend, token)
    except BackendUnavailable:
        return unavailable_page(request)


@app.post("/categories", response_class=HTMLResponse)
async def create_category(request: Request, backend: Backend):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return redirect("/login")
    name = (await read_form(request)).get("name", "")
    try:
        created = backend.create_category(token, name)
        if created.status == 401:
            return session_expired()
        if created.status != 201:
            return categories_page(
                request,
                backend,
                token,
                created.status,
                errors=error_messages(created.body),
                name=name,
            )
    except BackendUnavailable:
        return unavailable_page(request)
    return redirect("/categories")


@app.post("/categories/{category_id}/delete", response_class=HTMLResponse)
def delete_category(category_id: int, request: Request, backend: Backend):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return redirect("/login")
    try:
        deleted = backend.delete_category(token, category_id)
        if deleted.status == 401:
            return session_expired()
        if deleted.status != 204:
            return categories_page(
                request,
                backend,
                token,
                deleted.status,
                errors=error_messages(deleted.body),
            )
    except BackendUnavailable:
        return unavailable_page(request)
    return redirect("/categories")


def parse_id(value: str | None) -> int | None:
    """A positive integer id from a form or query value, else None."""
    value = (value or "").strip()
    return int(value) if value.isdigit() else None


def items_url(category_filter: int | None) -> str:
    # Solo ids numéricos en la URL de redirección (nada del usuario sin validar).
    if category_filter is None:
        return "/items"
    return f"/items?category_id={category_filter}"


def items_page(
    request: Request,
    backend: BackendClient,
    token: str,
    category_filter: int | None,
    status_code: int = 200,
    errors: list[str] | None = None,
    values: dict | None = None,
):
    categories = backend.list_categories(token)
    if categories.status == 401:
        return session_expired()
    listed = backend.list_items(token, category_filter)
    if listed.status == 401:
        return session_expired()
    items = listed.body if listed.ok else []
    if not listed.ok:
        # Filtro por una categoría que no existe o no es del usuario.
        status_code = listed.status
        errors = (errors or []) + error_messages(listed.body)
    return render(
        request,
        "items.html",
        status_code,
        categories=categories.body,
        items=items,
        category_filter=category_filter,
        errors=errors,
        values=values or {},
    )


@app.get("/items", response_class=HTMLResponse)
def list_items(request: Request, backend: Backend, category_id: str | None = None):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return redirect("/login")
    try:
        return items_page(request, backend, token, parse_id(category_id))
    except BackendUnavailable:
        return unavailable_page(request)


@app.post("/items", response_class=HTMLResponse)
async def create_item(request: Request, backend: Backend):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return redirect("/login")
    form = await read_form(request)
    category_filter = parse_id(form.get("filter"))
    item = {
        "url": form.get("url", ""),
        "title": form.get("title", ""),
        "category_id": parse_id(form.get("category_id")),
        "note": form.get("note", ""),
    }
    try:
        created = backend.create_item(token, item)
        if created.status == 401:
            return session_expired()
        if created.status != 201:
            return items_page(
                request,
                backend,
                token,
                category_filter,
                created.status,
                errors=error_messages(created.body),
                values=item,
            )
    except BackendUnavailable:
        return unavailable_page(request)
    return redirect(items_url(category_filter))


@app.post("/items/{item_id}/delete", response_class=HTMLResponse)
async def delete_item(item_id: int, request: Request, backend: Backend):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return redirect("/login")
    category_filter = parse_id((await read_form(request)).get("filter"))
    try:
        deleted = backend.delete_item(token, item_id)
        if deleted.status == 401:
            return session_expired()
        if deleted.status != 204:
            return items_page(
                request,
                backend,
                token,
                category_filter,
                deleted.status,
                errors=error_messages(deleted.body),
            )
    except BackendUnavailable:
        return unavailable_page(request)
    return redirect(items_url(category_filter))


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, backend: Backend):
    status = backend_status(backend)
    wake_url = BACKEND_PUBLIC_URL if status == "unavailable" else None
    return render(request, "login.html", backend_status=status, wake_url=wake_url)


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, backend: Backend):
    form = await read_form(request)
    username = form.get("username", "")
    try:
        result = backend.login(username, form.get("password", ""))
    except BackendUnavailable:
        return unavailable_page(request)
    if result.status != 200:
        return render(
            request,
            "login.html",
            401,
            errors=[WRONG_CREDENTIALS],
            username=username,
            backend_status=backend_status(backend),
        )
    response = redirect("/")
    set_session(response, result.body["token"])
    return response


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return render(request, "register.html")


@app.post("/register", response_class=HTMLResponse)
async def register(request: Request, backend: Backend):
    form = await read_form(request)
    username = form.get("username", "")
    password = form.get("password", "")
    try:
        created = backend.register(username, password)
        if created.status != 201:
            return render(
                request,
                "register.html",
                created.status,
                errors=error_messages(created.body),
                username=username,
            )
        # Registro exitoso: iniciar sesión de una vez.
        logged_in = backend.login(username, password)
    except BackendUnavailable:
        return unavailable_page(request)
    if logged_in.status != 200:
        return redirect("/login")
    response = redirect("/")
    set_session(response, logged_in.body["token"])
    return response


@app.post("/logout")
def logout(request: Request, backend: Backend):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        try:
            backend.logout(token)
        except BackendUnavailable:
            pass  # La cookie se borra igual; el token vence solo.
    response = redirect("/login")
    clear_session(response)
    return response


@app.get("/health")
def health() -> JSONResponse:
    # Salud propia del frontend: no llama al backend.
    return JSONResponse({"status": "ok", "deployment": DEPLOYMENT, "version": VERSION})
