"""Small hand-written client for the backend API (api/openapi.yaml)."""

import logging
import time
from collections.abc import Callable
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
    "getDaily": ("GET", "/api/daily"),
}

DEFAULT_TIMEOUT_SECONDS = 2.0
WAKE_RETRY_PAUSE_SECONDS = 2.0

# Solo operationId, código o tipo de error e intentos: nunca datos del usuario.
log = logging.getLogger("frontend.backend")


class BackendUnavailable(Exception):
    """The backend is down, timed out, or didn't answer with the API's JSON."""


@dataclass
class ApiResult:
    status: int
    body: Any

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class BackendClient:
    def __init__(
        self,
        base_url: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        wake_seconds: float = 0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._client = httpx.Client(
            base_url=base_url, timeout=timeout, transport=transport
        )
        # Render despierta un backend gratis dormido en ~30-60 s y mientras tanto
        # su proxy responde errores al instante. Durante wake_seconds se reintenta.
        self._wake_seconds = wake_seconds
        self._sleep = sleep
        self._clock = clock

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
        deadline = self._clock() + self._wake_seconds
        attempts = 0
        while True:
            attempts += 1
            try:
                return self._send(method, path, json, headers, params)
            except BackendUnavailable as error:
                # Solo se reintenta lo que es seguro repetir: cualquier GET, y otros
                # métodos solo si la conexión falló antes de enviar el pedido.
                retry_safe = method == "GET" or isinstance(
                    error.__cause__, httpx.ConnectError
                )
                if not retry_safe or self._clock() >= deadline:
                    log.warning(
                        "backend unavailable: operation=%s reason=%s attempts=%d",
                        operation_id,
                        error.args[0],
                        attempts,
                    )
                    raise BackendUnavailable(operation_id) from error.__cause__
                self._sleep(WAKE_RETRY_PAUSE_SECONDS)

    def _send(self, method, path, json, headers, params) -> ApiResult:
        try:
            response = self._client.request(
                method, path, json=json, headers=headers, params=params
            )
        except httpx.HTTPError as error:
            raise BackendUnavailable(type(error).__name__) from error
        # 5xx, redirecciones o HTML (página de Render mientras despierta) no son la API.
        if response.status_code >= 500 or 300 <= response.status_code < 400:
            raise BackendUnavailable(f"status {response.status_code}")
        if not response.content:
            return ApiResult(response.status_code, None)
        try:
            body = response.json()
        except ValueError as error:
            kind = response.headers.get("content-type", "unknown")
            raise BackendUnavailable(
                f"status {response.status_code} non-JSON {kind}"
            ) from error
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

    def get_daily(self, token: str) -> ApiResult:
        return self._call("getDaily", token=token)
