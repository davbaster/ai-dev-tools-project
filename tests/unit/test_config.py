import pytest

from backend import config as backend_config
from frontend import config as frontend_config

# Both services apply the same DEPLOYMENT rule (each has its own config.py).
GET_DEPLOYMENT = [backend_config.get_deployment, frontend_config.get_deployment]


@pytest.mark.parametrize("get_deployment", GET_DEPLOYMENT)
def test_deployment_defaults_to_local(monkeypatch, get_deployment):
    monkeypatch.delenv("DEPLOYMENT", raising=False)
    assert get_deployment() == "local"


@pytest.mark.parametrize("get_deployment", GET_DEPLOYMENT)
@pytest.mark.parametrize("value", ["local", "dev", "prod"])
def test_deployment_accepts_allowed_values(monkeypatch, get_deployment, value):
    monkeypatch.setenv("DEPLOYMENT", value)
    assert get_deployment() == value


@pytest.mark.parametrize("get_deployment", GET_DEPLOYMENT)
def test_invalid_deployment_names_variable_and_allowed_values(
    monkeypatch, get_deployment
):
    monkeypatch.setenv("DEPLOYMENT", "staging")
    with pytest.raises(ValueError) as excinfo:
        get_deployment()
    message = str(excinfo.value)
    assert "DEPLOYMENT" in message
    assert "local, dev, prod" in message


def test_backend_url_defaults_to_local_backend(monkeypatch):
    monkeypatch.delenv("BACKEND_URL", raising=False)
    assert frontend_config.get_backend_url() == "http://localhost:8001"


def test_backend_url_drops_trailing_slash(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "http://backend:8001/")
    assert frontend_config.get_backend_url() == "http://backend:8001"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgresql://u:p@db:5432/x", "postgresql+psycopg://u:p@db:5432/x"),
        ("postgres://u:p@db:5432/x", "postgresql+psycopg://u:p@db:5432/x"),
        ("postgresql+psycopg://u:p@db/x", "postgresql+psycopg://u:p@db/x"),
    ],
)
def test_database_url_uses_psycopg(monkeypatch, raw, expected):
    monkeypatch.setenv("DATABASE_URL", raw)
    assert backend_config.get_database_url() == expected


def test_missing_database_url_names_the_variable(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        backend_config.get_database_url()


def test_backend_imports_without_database_url(monkeypatch):
    # El engine se crea al primer uso, no al importar.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import backend.db
    import backend.main

    assert backend.db.get_engine.cache_info().currsize == 0
    assert backend.main.app is not None
