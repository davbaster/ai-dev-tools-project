"""Frontend client while a sleeping Render backend wakes up (#11), no network."""

import httpx
import pytest

from frontend import config as frontend_config
from frontend.api_client import BackendClient, BackendUnavailable

HEALTH = {"status": "ok", "deployment": "dev", "version": "abc"}
WAKING_PAGE = httpx.Response(
    200, text="<html>Service waking up</html>", headers={"content-type": "text/html"}
)


class FakeTime:
    """A clock that only moves when the client sleeps."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def client_with(responses, wake_seconds=60):
    calls = []
    queue = list(responses)

    def handler(request):
        calls.append(request.method)
        answer = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    fake = FakeTime()
    client = BackendClient(
        "http://backend.test",
        transport=httpx.MockTransport(handler),
        wake_seconds=wake_seconds,
        sleep=fake.sleep,
        clock=fake.clock,
    )
    return client, calls, fake


def test_get_waits_through_render_wake_up_answers():
    client, calls, fake = client_with(
        [
            httpx.Response(503, text="waking"),
            WAKING_PAGE,
            httpx.Response(307, headers={"location": "/"}),
            httpx.ConnectError("refused"),
            httpx.Response(200, json=HEALTH),
        ]
    )
    assert client.get_health() == HEALTH
    assert len(calls) == 5
    assert fake.sleeps == [2.0, 2.0, 2.0, 2.0]


def test_get_gives_up_after_the_wake_budget():
    client, calls, fake = client_with([httpx.Response(503, text="down")], 10)
    assert client.get_health() is None
    assert fake.now >= 10 and len(calls) == 6


def test_without_wake_budget_there_are_no_retries():
    client, calls, _ = client_with([httpx.Response(503, text="down")], 0)
    assert client.get_health() is None
    assert calls == ["GET"]


def test_post_is_not_retried_after_a_response():
    client, calls, _ = client_with([httpx.Response(503, text="down")])
    with pytest.raises(BackendUnavailable):
        client.login("ana", "a long password")
    assert calls == ["POST"]


def test_post_is_retried_when_the_connection_failed():
    token = {"token": "t", "user": {"id": 1, "username": "ana", "is_admin": False}}
    client, calls, _ = client_with(
        [httpx.ConnectError("refused"), httpx.Response(200, json=token)]
    )
    assert client.login("ana", "a long password").body == token
    assert calls == ["POST", "POST"]


def test_html_instead_of_json_is_unavailable_not_a_crash():
    client, _, _ = client_with([WAKING_PAGE], 0)
    with pytest.raises(BackendUnavailable):
        client.get_me("token")


def test_wake_seconds_defaults_to_zero(monkeypatch):
    monkeypatch.delenv("BACKEND_WAKE_SECONDS", raising=False)
    assert frontend_config.get_backend_wake_seconds() == 0


def test_wake_seconds_reads_seconds(monkeypatch):
    monkeypatch.setenv("BACKEND_WAKE_SECONDS", "60")
    assert frontend_config.get_backend_wake_seconds() == 60


@pytest.mark.parametrize("value", ["-1", "abc"])
def test_bad_wake_seconds_stops_startup(monkeypatch, value):
    monkeypatch.setenv("BACKEND_WAKE_SECONDS", value)
    with pytest.raises(ValueError, match="BACKEND_WAKE_SECONDS"):
        frontend_config.get_backend_wake_seconds()


def test_giving_up_logs_the_reason_without_user_data(caplog):
    client, _, _ = client_with([httpx.Response(503, text="down")], 4)
    with caplog.at_level("WARNING", logger="frontend.backend"):
        assert client.get_health() is None
    message = caplog.records[-1].getMessage()
    assert "operation=getHealth" in message and "status 503" in message
    assert "attempts=3" in message
