# Local observability (#14)

`make up` starts these next to the app. Local only: Render exports nothing (no
`OTEL_EXPORTER_OTLP_ENDPOINT` there). No volumes, so `make down` clears the data.

| Service | URL (127.0.0.1 only) | What it does | Config |
|---|---|---|---|
| Grafana | http://localhost:3000 | Dashboard "Para Luego" (home page), Explore. Opens without login (local anonymous Editor). | `grafana/` |
| Prometheus | http://localhost:9090 | Metrics, scraped from the collector every 10 s | `prometheus.yaml` |
| Tempo | http://localhost:3200 | Traces | `tempo.yaml` |
| Loki | http://localhost:3100 | Logs | `loki.yaml` |
| OTel Collector | not published | Receives OTLP from the apps; reads their JSON logs | `otel-collector.yaml` |

## How data gets there

- **Traces and metrics:** frontend and backend send OTLP/HTTP to `otel-collector:4318` (`OTEL_EXPORTER_OTLP_ENDPOINT` in `docker-compose.yml`; metrics every 10 s with `OTEL_METRIC_EXPORT_INTERVAL`). Traces go to Tempo; metrics to the collector's `prometheus` exporter, which Prometheus scrapes (`job` = service name).
- **Logs:** the apps print JSON to stdout. The collector's `file_log` receiver reads Docker's json-file logs (`/var/lib/docker/containers`, mounted read-only; the collector runs as root because those files are root-only), keeps only lines with `"service": "para-luego-…"` and sends them to Loki. Loki indexes `service_name`; `trace_id`, `span_id`, `level` and `logger` are structured metadata.
- The app doesn't depend on any of this: with the collector stopped, saving an item still works.

## Metrics (Prometheus names)

| Metric | Labels | From |
|---|---|---|
| `http_requests_total` | `job`, `route` (template, `unmatched` for 404s), `method`, `status` | both services |
| `http_server_request_duration_seconds_bucket` | same | both services (buckets 5 ms … 60 s) |
| `items_saved_total` | `job` | backend, one per item saved |

The dashboard's two error panels use the same expressions as the alerts in #15:
save-item 5xx share (backend `POST /api/items`) and 5xx share by service.

## From a log line to its trace, and back

1. Grafana → Explore → Loki: `{service_name="para-luego-backend"} |= "item saved"`.
2. Open a line: the `trace_id` field has a **Tempo** link that opens the whole trace (frontend server and client spans, backend server span, DB spans).
3. In the trace, a span's **Related logs** opens Loki filtered by that `trace_id`: the frontend and backend lines of the same request.

Logs and spans carry only ids and route templates, never usernames, URLs, titles or notes (#13).
