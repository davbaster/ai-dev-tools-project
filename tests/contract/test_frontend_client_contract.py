"""The frontend client only calls operations defined in api/openapi.yaml."""

from frontend.api_client import OPERATIONS


def test_every_client_call_is_in_contract(contract_operations):
    for operation_id, (method, path) in OPERATIONS.items():
        operation = contract_operations.get((method, path))
        assert operation is not None, f"{method} {path} is not in the contract"
        assert operation["operationId"] == operation_id
