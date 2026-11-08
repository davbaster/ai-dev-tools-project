from pathlib import Path

import pytest
import yaml

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "api" / "openapi.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture(scope="session")
def contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def contract_operations(contract) -> dict[tuple[str, str], dict]:
    """(METHOD, path) -> operation, for every operation in the contract."""
    return {
        (method.upper(), path): operation
        for path, item in contract["paths"].items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    }
