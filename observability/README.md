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

## Alerts (#15)

Grafana alerting, provisioned from `grafana/provisioning/alerting/` (folder "Para Luego", group `user-impact`). Both rules use the same expressions as the dashboard's error panels, are evaluated every 30 s and fire after 1 minute above the threshold. With no traffic they stay Normal (no data = OK); a query error shows as Error.

| Rule | Fires when | Labels |
|---|---|---|
| **SaveItemFailing** | over 5% of backend `POST /api/items` answer 5xx (5-minute window) | `severity=page`, `team=para-luego` |
| **HighServerErrors** | over 5% of a service's requests answer 5xx (5-minute window), one alert per `job` | same + `job` |

There is no minimum-traffic guard: one 500 among a few requests is already over 5%. Fine for a demo.

### Webhook to the on-call responder

Contact point "on-call responder" posts Grafana's webhook JSON to `ALERT_WEBHOOK_URL` (default `http://oncall-agent:8080/alerts`, the responder from #17) with `Authorization: Bearer $ALERT_WEBHOOK_TOKEN`; the responder must reject anything else. Grouped by `alertname`: a notification when a group starts firing, when it changes (at most every minute), every 4 hours while firing, and when it resolves. If the URL is unreachable, Grafana logs `Notify for alerts failed` and tries again at the next group interval.

Example (trimmed; only metric labels, never customer data):

```json
{
  "receiver": "on-call responder",
  "status": "firing",
  "groupLabels": {"alertname": "HighServerErrors"},
  "alerts": [
    {
      "status": "firing",
      "labels": {"alertname": "HighServerErrors", "job": "para-luego-backend", "severity": "page", "team": "para-luego", "grafana_folder": "Para Luego"},
      "annotations": {
        "summary": "Server errors on para-luego-backend: over 5% of requests answer 5xx",
        "description": "Users get errors. Share of 5xx answers on para-luego-backend (any route) over the last 5 minutes is above 5%.",
        "runbook": "_docs/agents/oncall-responder.md"
      },
      "startsAt": "2026-11-13T03:34:30Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "fingerprint": "b16d3f9f861d8534",
      "generatorURL": "http://localhost:3000/alerting/grafana/high-server-errors/view"
    }
  ]
}
```

When it resolves, the same shape arrives with `"status": "resolved"` and a real `endsAt`. `fingerprint` identifies one alert instance (rule + labels) across firing and resolved.

### Make them fire locally

1. Log in and save an item (so the browser has a session).
2. `docker compose stop db`, then keep saving items: the backend answers 500, the frontend 503. Both rules go Pending, then Firing within ~2-3 minutes.
3. `docker compose start db` and use the app normally: they resolve within ~4-6 minutes (the 5-minute window).

To watch the webhook without the responder, point `ALERT_WEBHOOK_URL` at any HTTP receiver on your machine, e.g. `ALERT_WEBHOOK_URL=http://host.docker.internal:9999/alerts make up`.
