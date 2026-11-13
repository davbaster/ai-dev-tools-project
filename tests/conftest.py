"""Telemetry for every suite: in-memory providers, installed before any app is
imported, so telemetry.setup() keeps them and nothing goes over the network."""

import json
import logging

import pytest
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import telemetry

SPANS = InMemorySpanExporter()
METRICS = InMemoryMetricReader()

_tracer_provider = TracerProvider()
_tracer_provider.add_span_processor(SimpleSpanProcessor(SPANS))
trace.set_tracer_provider(_tracer_provider)
metrics.set_meter_provider(MeterProvider(metric_readers=[METRICS]))


@pytest.fixture
def spans() -> InMemorySpanExporter:
    """Finished spans of this test only."""
    SPANS.clear()
    return SPANS


@pytest.fixture
def metric_points():
    """Call metric_points(name) for {attributes: value} of a counter, cumulative."""

    def read(name: str) -> dict[tuple, float]:
        data = METRICS.get_metrics_data()
        points = {}
        for resource_metrics in data.resource_metrics if data else []:
            for scope in resource_metrics.scope_metrics:
                for metric in scope.metrics:
                    if metric.name == name:
                        for point in metric.data.data_points:
                            key = tuple(sorted(point.attributes.items()))
                            points[key] = getattr(point, "value", None) or getattr(
                                point, "count", 0
                            )
        return points

    return read


class _JsonLines(logging.Handler):
    """Formats each record when it is emitted, inside its span, like stdout does."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.setFormatter(telemetry.JsonFormatter())
        self.lines: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(json.loads(self.format(record)))


@pytest.fixture
def json_logs():
    """The JSON log lines (as dicts) every service logger emits during the test."""
    handler = _JsonLines()
    root = logging.getLogger()
    root.addHandler(handler)
    yield handler.lines
    root.removeHandler(handler)


@pytest.fixture
def histogram_bounds():
    """Call histogram_bounds(name) for the bucket limits of a recorded histogram."""

    def read(name: str) -> list[float]:
        data = METRICS.get_metrics_data()
        for resource_metrics in data.resource_metrics if data else []:
            for scope in resource_metrics.scope_metrics:
                for metric in scope.metrics:
                    if metric.name == name and metric.data.data_points:
                        return list(metric.data.data_points[0].explicit_bounds)
        return []

    return read
