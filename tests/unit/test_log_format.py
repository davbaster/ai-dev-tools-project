"""JSON log lines and route labels (#13)."""

import json
import logging

from opentelemetry import trace
from starlette.requests import Request

import telemetry


def record(message="hello", exc_info=None, **fields) -> logging.LogRecord:
    rec = logging.LogRecord(
        "backend.items", logging.INFO, __file__, 1, message, None, exc_info
    )
    if fields:
        rec.fields = fields
    return rec


def formatted(rec: logging.LogRecord) -> dict:
    return json.loads(telemetry.JsonFormatter().format(rec))


def test_line_has_the_fixed_fields_and_no_trace_outside_a_request():
    line = formatted(record(item_id=3))
    for key in ("timestamp", "level", "logger", "message", "service", "deployment"):
        assert key in line
    assert line["timestamp"].endswith("Z") and line["level"] == "INFO"
    assert line["message"] == "hello" and line["item_id"] == 3
    assert "trace_id" not in line and "span_id" not in line


def test_line_carries_the_active_trace_and_span_ids():
    with trace.get_tracer("test").start_as_current_span("work") as span:
        line = formatted(record())
        context = span.get_span_context()
    assert line["trace_id"] == format(context.trace_id, "032x")
    assert line["span_id"] == format(context.span_id, "016x")
    assert len(line["trace_id"]) == 32 and len(line["span_id"]) == 16


def test_exception_goes_in_one_line_with_its_type():
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        import sys

        line = formatted(record("failed", exc_info=sys.exc_info()))
    assert line["exc_type"] == "RuntimeError"
    assert "Traceback" in line["stack"] and "boom" in line["stack"]


def test_route_label_is_the_template_or_unmatched():
    class Route:
        path = "/items/{item_id}/delete"

    matched = Request({"type": "http", "route": Route()})
    unmatched = Request({"type": "http"})
    assert telemetry.route_template(matched) == "/items/{item_id}/delete"
    assert telemetry.route_template(unmatched) == "unmatched"
