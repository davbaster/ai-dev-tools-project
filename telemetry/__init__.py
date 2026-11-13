"""OpenTelemetry and JSON logging shared by the backend and the frontend (#13).

Imports nothing from either service. Each service calls `setup()` once when it
creates its app; calling it again (tests) changes nothing.

- Traces and metrics go over OTLP/HTTP only when OTEL_EXPORTER_OTLP_ENDPOINT is
  set (the local collector, #14). Unset (Render, tests), nothing leaves the
  process, but spans still exist so log lines carry trace_id / span_id.
- Every log line is one JSON object on stdout, uvicorn's included. Uvicorn's
  access log (raw paths, client IPs) is replaced by one line per request with
  the route template.
- No customer data: only ids and route templates in spans, metrics and logs.
"""

import json
import logging
import os
import sys
import time
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Las rutas de health no generan spans ni líneas de acceso: Render las consulta
# todo el tiempo. Sí se cuentan en las métricas.
HEALTH_PATHS = ("/health", "/api/health")
EXCLUDED_URLS = "health$"
UNMATCHED_ROUTE = "unmatched"
ACCESS_LOGGER = "access"
# Límites del histograma de duración, en segundos. Los de OpenTelemetry por
# defecto (0, 5, 10, 25, ...) son para milisegundos: con segundos, todo caía en
# el primer tramo y el p95 daba ~4,8 s (encontrado en #14).
DURATION_BUCKETS_SECONDS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1,
    2.5,
    5,
    10,
    30,
    60,
)

# Campos fijos de cada línea de log; los completa setup_logging.
_fields: dict[str, str] = {
    "service": "unknown",
    "deployment": "local",
    "version": "local",
}
_instruments: dict = {}
# Uno nada más: setup_logging lo reemplaza si se llama de nuevo.
_handler: logging.Handler | None = None
_NO_METRICS = NoOpMeterProvider()


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with the active trace and span ids."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **_fields,
        }
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            data["trace_id"] = format(context.trace_id, "032x")
            data["span_id"] = format(context.span_id, "016x")
        # Campos extra: logger.info("...", extra={"fields": {"item_id": 3}}).
        data.update(getattr(record, "fields", None) or {})
        if record.exc_info and record.exc_info[0] is not None:
            data["exc_type"] = record.exc_info[0].__name__
            data["stack"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str, ensure_ascii=False)


def setup_logging(service: str, deployment: str, version: str) -> None:
    """Send every log line (root, uvicorn, alembic) to stdout as JSON."""
    global _handler
    _fields.update(service=service, deployment=deployment, version=version)
    root = logging.getLogger()
    if _handler is not None:
        root.removeHandler(_handler)
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(JsonFormatter())
    root.addHandler(_handler)
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    # Uvicorn y Alembic traen sus propios handlers: que pasen por el root.
    for name in ("uvicorn", "uvicorn.error", "alembic", "sqlalchemy"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    # Su access log imprime rutas crudas e IPs; el nuestro va en track_requests.
    logging.getLogger("uvicorn.access").disabled = True
    # httpx anota cada llamada con la URL completa en INFO: solo advertencias.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def resource() -> Resource:
    return Resource.create(
        {
            "service.name": _fields["service"],
            "service.version": _fields["version"],
            "deployment.environment": _fields["deployment"],
        }
    )


def setup_providers() -> None:
    """Global tracer and meter providers, once. Tests install their own first."""
    exporting = bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip())
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        tracer_provider = TracerProvider(resource=resource())
        if exporting:
            tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(tracer_provider)
    if not isinstance(metrics.get_meter_provider(), MeterProvider):
        readers = (
            [PeriodicExportingMetricReader(OTLPMetricExporter())] if exporting else []
        )
        metrics.set_meter_provider(
            MeterProvider(resource=resource(), metric_readers=readers)
        )


def request_instruments():
    if not _instruments:
        meter = metrics.get_meter("para_luego.http")
        _instruments["requests"] = meter.create_counter(
            "http.requests", unit="{request}", description="HTTP requests served"
        )
        _instruments["duration"] = meter.create_histogram(
            "http.server.request.duration",
            unit="s",
            description="Time to answer an HTTP request",
            explicit_bucket_boundaries_advisory=DURATION_BUCKETS_SECONDS,
        )
    return _instruments["requests"], _instruments["duration"]


def route_template(request: Request) -> str:
    """The matched route's template (/items/{item_id}); never the raw path."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or UNMATCHED_ROUTE


def track_requests(app: FastAPI, service: str) -> None:
    """Count, time and log every request by route template."""
    access = logging.getLogger(f"{service}.{ACCESS_LOGGER}")
    errors = logging.getLogger(f"{service}.errors")

    @app.middleware("http")
    async def record(request: Request, call_next):
        requests_total, duration = request_instruments()
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        except Exception:
            errors.exception(
                "unhandled error",
                extra={"fields": {"route": route_template(request)}},
            )
            raise
        finally:
            elapsed = time.perf_counter() - start
            labels = {
                "route": route_template(request),
                "method": request.method,
                "status": status,
            }
            requests_total.add(1, labels)
            duration.record(elapsed, labels)
            if request.url.path not in HEALTH_PATHS:
                access.info(
                    "request",
                    extra={
                        "fields": {**labels, "duration_ms": round(elapsed * 1000, 1)}
                    },
                )


def setup(app: FastAPI, service: str, deployment: str, version: str) -> None:
    """Logging, providers, server spans and request metrics for one service."""
    setup_logging(service, deployment, version)
    setup_providers()
    if getattr(app.state, "telemetry", False):
        return
    app.state.telemetry = True
    track_requests(app, service)
    # Las métricas HTTP son las nuestras (con la plantilla de ruta), no las de la
    # instrumentación; tampoco spans por cada receive/send.
    FastAPIInstrumentor.instrument_app(
        app,
        meter_provider=_NO_METRICS,
        excluded_urls=EXCLUDED_URLS,
        exclude_spans=["receive", "send"],
    )


def no_metrics() -> NoOpMeterProvider:
    """For instrumentations whose own metrics we don't want (httpx client)."""
    return _NO_METRICS
