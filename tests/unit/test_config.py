import pytest

from app.config import get_deployment


def test_deployment_defaults_to_local(monkeypatch):
    monkeypatch.delenv("DEPLOYMENT", raising=False)
    assert get_deployment() == "local"


@pytest.mark.parametrize("value", ["local", "dev", "prod"])
def test_deployment_accepts_allowed_values(monkeypatch, value):
    monkeypatch.setenv("DEPLOYMENT", value)
    assert get_deployment() == value


def test_invalid_deployment_names_variable_and_allowed_values(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT", "staging")
    with pytest.raises(ValueError) as excinfo:
        get_deployment()
    message = str(excinfo.value)
    assert "DEPLOYMENT" in message
    assert "local, dev, prod" in message
