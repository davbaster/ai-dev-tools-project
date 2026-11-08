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
