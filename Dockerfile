# Imagen única para frontend y backend: Compose y Render eligen el servicio con el comando.
# Python 3.12, dependencias de runtime desde uv.lock, usuario no root.
FROM ghcr.io/astral-sh/uv:0.11 AS uv

FROM python:3.12-slim

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias primero para aprovechar la caché; --locked falla si uv.lock está desactualizado.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev

COPY backend ./backend
COPY frontend ./frontend
COPY alembic.ini ./
COPY migrations ./migrations

RUN useradd --system --uid 10001 --no-create-home appuser
USER appuser

EXPOSE 8000 8001

# Versión que reportan los health checks: el SHA del commit en CD, "local" si falta.
# Va al final para no invalidar la caché de las capas anteriores.
ARG APP_VERSION=local
ENV APP_VERSION=$APP_VERSION
LABEL org.opencontainers.image.source="https://github.com/davbaster/ai-dev-tools-project"

# Por defecto el backend; el frontend se arranca con su propio comando.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
