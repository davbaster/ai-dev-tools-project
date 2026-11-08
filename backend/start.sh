#!/bin/sh
# Arranque del backend en Compose y Render: migraciones y luego la API.
# Render free no tiene pre-deploy, por eso las migraciones van acá.
# PORT lo define Render (o Compose); 8001 si no está.
set -e
alembic upgrade head
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8001}"
