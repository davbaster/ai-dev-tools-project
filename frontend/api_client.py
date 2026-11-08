"""Small hand-written client for the backend API (api/openapi.yaml)."""

from dataclasses import dataclass
from typing import Any

import httpx

# Every operation the frontend calls, by operationId. The contract tests check
# that each one exists in api/openapi.yaml with the same method and path.
OPERATIONS: dict[str, tuple[str, str]] = {
    "getHealth": ("GET", "/api/health"),
    "register": ("POST", "/api/auth/register"),
    "login": ("POST", "/api/auth/login"),
    "logout": ("POST", "/api/auth/logout"),
    "getMe": ("GET", "/api/me"),
    "listCategories": ("GET", "/api/categories"),
    "createCategory": ("POST", "/api/categories"),
    "deleteCategory": ("DELETE", "/api/categories/{category_id}"),
    "listItems": ("GET", "/api/items"),
    "createItem": ("POST", "/api/items"),
    "deleteItem": ("DELETE", "/api/items/{item_id}"),
}

TIMEOUT_SECONDS = 2.0


class BackendUnavailable(Exception):
    """The backend is down, timed out or answered with a 5xx."""


@dataclass
class ApiResult:
    status: int
    body: Any

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class BackendClient:
    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url=base_url, timeout=TIMEOUT_SECONDS, transport=transport
        )

    def _call(
        self,
        operation_id: str,
        json: dict | None = None,
        token: str | None = None,
        path_params: dict | None = None,
        params: dict | None = None,
    ) -> ApiResult:
        method, template = OPERATIONS[operation_id]
        path = template.format(**(path_params or {}))
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            response = self._client.request(
                method, path, json=json, headers=headers, params=params
            )
        except httpx.HTTPError as error:
            raise BackendUnavailable(operation_id) from error
        if response.status_code >= 500:
            raise BackendUnavailable(operation_id)
        body = response.json() if response.content else None
        return ApiResult(response.status_code, body)

    def get_health(self) -> dict | None:
        """Return the backend health, or None if the backend is unavailable."""
        try:
            result = self._call("getHealth")
        except BackendUnavailable:
            return None
        return result.body if result.status == 200 else None

    def register(self, username: str, password: str) -> ApiResult:
        return self._call("register", json={"username": username, "password": password})

    def login(self, username: str, password: str) -> ApiResult:
        return self._call("login", json={"username": username, "password": password})

    def logout(self, token: str) -> ApiResult:
        return self._call("logout", token=token)

    def get_me(self, token: str) -> ApiResult:
        return self._call("getMe", token=token)

    def list_categories(self, token: str) -> ApiResult:
        return self._call("listCategories", token=token)

    def create_category(self, token: str, name: str) -> ApiResult:
        return self._call("createCategory", json={"name": name}, token=token)

    def delete_category(self, token: str, category_id: int) -> ApiResult:
        return self._call(
            "deleteCategory", token=token, path_params={"category_id": category_id}
        )

    def list_items(self, token: str, category_id: int | None = None) -> ApiResult:
        params = {"category_id": category_id} if category_id is not None else None
        return self._call("listItems", token=token, params=params)

    def create_item(self, token: str, item: dict) -> ApiResult:
        return self._call("createItem", json=item, token=token)

    def delete_item(self, token: str, item_id: int) -> ApiResult:
        return self._call("deleteItem", token=token, path_params={"item_id": item_id})
