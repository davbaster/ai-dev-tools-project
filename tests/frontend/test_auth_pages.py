"""Register, login, logout pages with a fake backend (shapes from api/openapi.yaml)."""

from urllib.parse import urlencode

import httpx
import pytest

TOKEN = "fake-token-123"
USER = {"id": 1, "username": "ana", "is_admin": False}


class FakeBackend:
    """Answers like the backend would; records the calls it got."""

    def __init__(self, me_status=200, login_ok=True, register_status=201):
        self.me_status = me_status
        self.login_ok = login_ok
        self.register_status = register_status
        self.calls = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path))
        if path == "/api/health":
            return httpx.Response(200, json={"status": "ok", "deployment": "local"})
        if path == "/api/auth/login":
            if self.login_ok:
                return httpx.Response(200, json={"token": TOKEN, "user": USER})
            return httpx.Response(
                401, json={"detail": "Usuario o contraseña incorrectos."}
            )
        if path == "/api/auth/register":
            if self.register_status == 201:
                return httpx.Response(201, json=USER)
            if self.register_status == 409:
                return httpx.Response(
                    409, json={"detail": "Ese nombre de usuario ya está en uso."}
                )
            return httpx.Response(
                422,
                json={
                    "detail": [
                        {
                            "field": "password",
                            "message": "La contraseña debe tener entre 8 y 128 caracteres.",
                        }
                    ]
                },
            )
        if path == "/api/me":
            if self.me_status == 200:
                return httpx.Response(200, json=USER)
            return httpx.Response(401, json={"detail": "Sesión inválida o vencida."})
        if path == "/api/auth/logout":
            return httpx.Response(204)
        return httpx.Response(404, json={"detail": "Not Found"})


def form(**fields):
    return {
        "content": urlencode(fields),
        "headers": {"Content-Type": "application/x-www-form-urlencoded"},
    }


def session_cookie_header(response) -> str:
    return next(
        value
        for key, value in response.headers.multi_items()
        if key == "set-cookie" and value.startswith("pl_session=")
    )


def test_login_and_register_forms_render(client, fake_backend):
    fake_backend(FakeBackend())
    login = client.get("/login")
    assert 'name="username"' in login.text
    assert 'type="password"' in login.text
    assert 'href="/register"' in login.text
    register = client.get("/register")
    assert register.status_code == 200
    assert 'type="password"' in register.text
    assert 'href="/login"' in register.text


def test_successful_login_sets_httponly_cookie_and_redirects(client, fake_backend):
    fake_backend(FakeBackend())
    response = client.post("/login", **form(username="Ana", password="secret123"))
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookie = session_cookie_header(response)
    assert cookie.startswith(f"pl_session={TOKEN}")
    lowered = cookie.lower()
    assert "httponly" in lowered
    assert "samesite=lax" in lowered
    assert "path=/" in lowered
    assert "max-age=604800" in lowered
    assert "secure" not in lowered  # DEPLOYMENT=local


def test_wrong_login_shows_error_with_401_and_no_cookie(client, fake_backend):
    fake_backend(FakeBackend(login_ok=False))
    response = client.post("/login", **form(username="ana", password="nope"))
    assert response.status_code == 401
    assert "Usuario o contraseña incorrectos" in response.text
    assert "pl_session" not in response.headers.get("set-cookie", "")
    assert "nope" not in response.text


def test_register_logs_in_and_redirects(client, fake_backend):
    backend = FakeBackend()
    fake_backend(backend)
    response = client.post("/register", **form(username="ana", password="secret123"))
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert session_cookie_header(response).startswith(f"pl_session={TOKEN}")
    assert ("POST", "/api/auth/register") in backend.calls
    assert ("POST", "/api/auth/login") in backend.calls


@pytest.mark.parametrize(
    ("status", "message"),
    [(409, "ya está en uso"), (422, "entre 8 y 128 caracteres")],
)
def test_register_errors_keep_username_and_drop_password(
    client, fake_backend, status, message
):
    fake_backend(FakeBackend(register_status=status))
    response = client.post("/register", **form(username="ana", password="secretpw1"))
    assert response.status_code == status
    assert message in response.text
    assert 'value="ana"' in response.text
    assert "secretpw1" not in response.text


def test_home_without_session_redirects_to_login(client, fake_backend):
    fake_backend(FakeBackend())
    response = client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_home_with_session_greets_the_user(client, fake_backend):
    fake_backend(FakeBackend())
    client.cookies.set("pl_session", TOKEN)
    response = client.get("/")
    assert response.status_code == 200
    assert "Hola, ana" in response.text
    assert "Cerrar sesión" in response.text


def test_invalid_token_clears_cookie_and_redirects(client, fake_backend):
    fake_backend(FakeBackend(me_status=401))
    client.cookies.set("pl_session", "expired")
    response = client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert session_cookie_header(response).startswith('pl_session=""')


def test_logout_calls_backend_and_clears_cookie(client, fake_backend):
    backend = FakeBackend()
    fake_backend(backend)
    client.cookies.set("pl_session", TOKEN)
    response = client.post("/logout")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert session_cookie_header(response).startswith('pl_session=""')
    assert ("POST", "/api/auth/logout") in backend.calls


def down(request):
    raise httpx.ConnectError("connection refused", request=request)


def test_logout_works_when_backend_is_down(client, fake_backend):
    fake_backend(down)
    client.cookies.set("pl_session", TOKEN)
    response = client.post("/logout")
    assert response.status_code == 303
    assert session_cookie_header(response).startswith('pl_session=""')


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_backend_down_on_submit_gives_503(client, fake_backend, path):
    fake_backend(down)
    response = client.post(path, **form(username="ana", password="secret123"))
    assert response.status_code == 503
    assert "El servicio no está disponible" in response.text
    assert "Traceback" not in response.text


def test_usernames_are_escaped(client, fake_backend):
    fake_backend(FakeBackend(login_ok=False))
    response = client.post("/login", **form(username="<b>x</b>", password="nope"))
    assert "<b>x</b>" not in response.text
    assert "&lt;b&gt;x&lt;/b&gt;" in response.text
