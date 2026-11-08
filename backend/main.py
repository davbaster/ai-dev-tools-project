"""Para Luego backend: JSON API under /api, defined by api/openapi.yaml."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend import auth, categories, daily, items
from backend.config import get_deployment

# Validated at import time so the backend refuses to start with a bad value.
DEPLOYMENT = get_deployment()

# Mensajes por campo para los 422 (en español, se muestran en el frontend).
FIELD_MESSAGES = {
    "username": (
        "El usuario debe tener entre 3 y 50 caracteres: letras, números, "
        "punto, guion o guion bajo."
    ),
    "password": "La contraseña debe tener entre 8 y 128 caracteres.",
    "name": "El nombre debe tener entre 1 y 50 caracteres.",
    "url": "La URL debe empezar con http:// o https:// (máximo 2048 caracteres).",
    "title": "El título puede tener hasta 300 caracteres.",
    "note": "La nota puede tener hasta 1000 caracteres.",
    "category_id": "Elegí una de tus categorías.",
}
DEFAULT_FIELD_MESSAGE = "Dato inválido."

# api/openapi.yaml is the contract, so FastAPI's generated docs are turned off.
app = FastAPI(title="Para Luego API", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(items.router)
app.include_router(daily.router)


@app.exception_handler(RequestValidationError)
def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # El 422 por defecto de FastAPI repite el valor enviado (por ejemplo la
    # contraseña). Este solo devuelve el campo y un mensaje fijo.
    detail = []
    for error in exc.errors():
        field = str(error["loc"][-1]) if error.get("loc") else "body"
        detail.append(
            {
                "field": field,
                "message": FIELD_MESSAGES.get(field, DEFAULT_FIELD_MESSAGE),
            }
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detail}
    )


@app.get("/api/health")
def get_health() -> dict[str, str]:
    return {"status": "ok", "deployment": DEPLOYMENT}
