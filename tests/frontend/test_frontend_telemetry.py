"""The frontend's half of the save-item trace, its access log and metrics (#13)."""

import json
from urllib.parse import urlencode

import httpx
from opentelemetry.trace import SpanKind

TOKEN = "telemetry-token"
USER = {"id": 7, "username": "ana", "is_admin": False}
ITEM = {
    "id": 42,
    "url": "https://example.com/secreto",
    "title": "Título secreto",
    "note": "Nota secreta",
    "category_id": 1,
    "category_name": "Leer",
    "created_at": "2026-11-12T12:00:00+00:00",
}


def backend(seen: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        seen[(request.method, request.url.path)] = request.headers.get("traceparent")
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, json={"token": TOKEN, "user": USER})
        if request.method == "POST" and request.url.path == "/api/items":
            json.loads(request.content)
            return httpx.Response(201, json=ITEM)
        return httpx.Response(200, json=[])

    return handler


def post_form(client, path, **fields):
    return client.post(
        path,
        content=urlencode(fields),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def hex_trace(span) -> str:
    return format(span.context.trace_id, "032x")


def test_save_sends_traceparent_in_the_same_trace(
    client, fake_backend, spans, json_logs
):
    seen = {}
    fake_backend(backend(seen))
    post_form(client, "/login", username="ana", password="a long password")
    spans.clear()
    json_logs.clear()

    saved = post_form(
        client,
        "/items",
        url=ITEM["url"],
        title=ITEM["title"],
        category_id="1",
        note=ITEM["note"],
        filter="",
    )
    assert saved.status_code == 303

    traceparent = seen[("POST", "/api/items")]
    assert traceparent and traceparent.startswith("00-")
    trace_id = traceparent.split("-")[1]

    finished = spans.get_finished_spans()
    server = [s for s in finished if s.name == "POST /items"]
    assert server and hex_trace(server[0]) == trace_id
    assert server[0].attributes.get("http.route") == "/items"
    clients = [s for s in finished if s.kind == SpanKind.CLIENT]
    assert clients and all(hex_trace(s) == trace_id for s in clients)

    access = [line for line in json_logs if line["logger"].endswith(".access")]
    assert access[-1]["route"] == "/items" and access[-1]["method"] == "POST"
    assert access[-1]["status"] == 303 and access[-1]["trace_id"] == trace_id
    assert not [line for line in json_logs if line["logger"] == "httpx"]

    # Nada del usuario ni del item en spans o logs.
    dumped = json.dumps(json_logs) + "".join(
        json.dumps(dict(s.attributes or {})) for s in finished
    )
    for secret in (TOKEN, "a long password", "secreto", "Nota secreta"):
        assert secret not in dumped


def test_unknown_path_is_counted_as_unmatched(client, metric_points):
    assert client.get("/no-such-page/12345").status_code == 404
    routes = {dict(key)["route"] for key in metric_points("http.requests")}
    assert "unmatched" in routes
    assert not any("no-such-page" in route for route in routes)


def test_health_makes_no_span_and_no_access_line(client, spans, json_logs):
    assert client.get("/health").status_code == 200
    assert not [s for s in spans.get_finished_spans() if "health" in s.name]
    assert not [line for line in json_logs if line.get("route") == "/health"]


def test_duration_histogram_uses_second_buckets(client, histogram_bounds):
    # Los límites por defecto de OTel son para ms; con segundos el p95 era falso.
    client.get("/login")
    bounds = histogram_bounds("http.server.request.duration")
    assert bounds[:3] == [0.005, 0.01, 0.025] and bounds[-1] == 60
