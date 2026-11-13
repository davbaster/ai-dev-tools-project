"""The local observability files (#14) parse and query only metrics #13 emits."""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OBS = ROOT / "observability"
# Nombres en Prometheus de las métricas de telemetry/ y backend/items.py.
EMITTED = {
    "http_requests_total",
    "http_server_request_duration_seconds_bucket",
    "items_saved_total",
}
UI_SERVICES = ("grafana", "prometheus", "tempo", "loki")


def test_every_yaml_file_parses():
    files = list(OBS.rglob("*.yaml"))
    assert len(files) >= 6
    for path in files:
        assert yaml.safe_load(path.read_text(encoding="utf-8")), path


def test_dashboard_queries_only_emitted_metrics():
    dashboard = json.loads(
        (OBS / "grafana" / "dashboards" / "para-luego.json").read_text(encoding="utf-8")
    )
    exprs = [
        target["expr"]
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
        if panel["datasource"]["type"] == "prometheus"
    ]
    used = {
        name
        for expr in exprs
        for name in re.findall(r"\b([a-z_]+_(?:total|bucket|sum|count))\b", expr)
    }
    assert used and used <= EMITTED, used - EMITTED


def test_ui_ports_listen_on_localhost_only():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    for name in UI_SERVICES:
        ports = compose["services"][name]["ports"]
        assert ports and all(port.startswith("127.0.0.1:") for port in ports), name
    assert "ports" not in compose["services"]["otel-collector"]


ALERTING = OBS / "grafana" / "provisioning" / "alerting"


def dashboard_exprs() -> dict[str, str]:
    dashboard = json.loads(
        (OBS / "grafana" / "dashboards" / "para-luego.json").read_text(encoding="utf-8")
    )
    return {
        panel["title"]: panel["targets"][0]["expr"]
        for panel in dashboard["panels"]
        if panel.get("targets")
    }


def test_alert_rules_match_the_dashboard_panels():
    rules = yaml.safe_load((ALERTING / "rules.yaml").read_text(encoding="utf-8"))
    by_title = {rule["title"]: rule for rule in rules["groups"][0]["rules"]}
    assert set(by_title) == {"SaveItemFailing", "HighServerErrors"}
    panels = dashboard_exprs()
    expected = {
        "SaveItemFailing": "Save-item error rate (backend POST /api/items, 5xx share)",
        "HighServerErrors": "5xx share by service (any route)",
    }
    for title, panel in expected.items():
        rule = by_title[title]
        query = next(d for d in rule["data"] if d["refId"] == "A")["model"]["expr"]
        threshold = next(d for d in rule["data"] if d["refId"] == "C")["model"]
        assert query == panels[panel], title
        assert threshold["conditions"][0]["evaluator"]["params"] == [0.05]
        assert rule["for"] == "1m" and rule["noDataState"] == "OK"
        assert rule["labels"]["severity"] == "page"
    assert rules["groups"][0]["interval"] == "30s"


def test_webhook_comes_from_the_environment():
    text = (ALERTING / "notifications.yaml").read_text(encoding="utf-8")
    settings = yaml.safe_load(text)["contactPoints"][0]["receivers"][0]["settings"]
    assert settings["url"] == "$ALERT_WEBHOOK_URL"
    assert settings["authorization_scheme"] == "Bearer"
    assert settings["authorization_credentials"] == "$ALERT_WEBHOOK_TOKEN"
