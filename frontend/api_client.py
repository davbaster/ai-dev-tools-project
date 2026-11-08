"""Small hand-written client for the backend API (api/openapi.yaml)."""

import httpx

# Every operation the frontend calls, by operationId. The contract tests check
# that each one exists in api/openapi.yaml with the same method and path.
OPERATIONS: dict[str, tuple[str, str]] = {
    "getHealth": ("GET", "/api/health"),
}

TIMEOUT_SECONDS = 2.0


class BackendClient:
    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url=base_url, timeout=TIMEOUT_SECONDS, transport=transport
        )

    def _call(self, operation_id: str) -> httpx.Response:
        method, path = OPERATIONS[operation_id]
        return self._client.request(method, path)

    def get_health(self) -> dict | None:
        """Return the backend health, or None if the backend is unavailable."""
        try:
            response = self._call("getHealth")
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        return response.json()
