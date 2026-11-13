"""The MCP server's tools, guards, auth and audit log, with fake upstreams (#16)."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from mcp import Client
from starlette.testclient import TestClient

from oncall.mcp_server.audit import AuditLog
from oncall.mcp_server.guards import ToolInputError, logql_string, safe_repo_path
from oncall.mcp_server.server import TOOL_NAMES, build_server, create_app
from oncall.mcp_server.tools import Settings, Tools

ROOT = Path(__file__).resolve().parents[2]


def settings(**kwargs) -> Settings:
    base = {
        "loki_url": "http://loki.test",
        "prometheus_url": "http://prom.test",
        "repo_root": ROOT,
        "health": [("local", "backend", "http://backend.test/api/health")],
    }
    return Settings(**{**base, **kwargs})


def run(coro):
    return asyncio.run(coro)


# --- path guard ---------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "../.env",
        "/etc/passwd",
        ".env",
        ".git/config",
        "backend/../../x",
        "C:/Windows",
        ".venv/x",
    ],
)
def test_path_guard_refuses(path):
    with pytest.raises(ToolInputError):
        safe_repo_path(ROOT, path)


def test_path_guard_allows_code_and_lists_directories():
    assert safe_repo_path(ROOT, "backend/items.py").name == "items.py"
    listing = run(Tools(settings()).read_source_file("backend"))
    assert "items.py" in listing["entries"] and "__pycache__/" not in listing["entries"]
    root = run(Tools(settings()).read_source_file("."))
    assert ".git/" not in root["entries"] and ".venv/" not in root["entries"]


def test_read_source_file_numbers_lines():
    out = run(Tools(settings()).read_source_file("backend/items.py", 3, 2))
    assert out["from_line"] == 3 and out["to_line"] == 4
    assert out["content"].splitlines()[0].lstrip().startswith("3")


# --- LogQL ----------------------------------------------------------------------


def test_logql_string_cannot_break_out():
    assert logql_string('a"} |= "x') == '"a\\"} |= \\"x"'
    with pytest.raises(ToolInputError):
        logql_string("line\nbreak")


def test_get_recent_logs_builds_an_escaped_query():
    seen = {}

    def loki(request: httpx.Request) -> httpx.Response:
        seen["query"] = request.url.params["query"]
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "result": [{"stream": {}, "values": [["2", "b"], ["1", "a"]]}]
                },
            },
        )

    tools = Tools(settings(), transport=httpx.MockTransport(loki))
    out = run(tools.get_recent_logs("backend", 5, "ERROR", None, '"} |= "x', 10))
    assert seen["query"].startswith(
        '{service_name="para-luego-backend"} | level="ERROR"'
    )
    assert seen["query"].endswith('|= "\\"} |= \\"x"')
    assert out["lines"] == ["b", "a"]


def test_out_of_range_arguments_are_refused():
    tools = Tools(settings())
    with pytest.raises(ToolInputError):
        run(tools.get_recent_logs("backend", minutes=61))
    with pytest.raises(ToolInputError):
        run(tools.get_recent_logs("backend", trace_id="not-hex"))


# --- metrics and health ---------------------------------------------------------


def test_query_metrics_caps_series_and_reports_upstream_errors():
    many = [{"metric": {"i": str(i)}, "value": [0, "1"]} for i in range(60)]

    def prom(request):
        if request.url.params["query"] == "bad(":
            return httpx.Response(400, json={"status": "error", "error": "parse error"})
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "vector", "result": many},
            },
        )

    tools = Tools(settings(), transport=httpx.MockTransport(prom))
    out = run(tools.query_metrics("up"))
    assert len(out["series"]) == 50 and "60 series" in out["note"]
    with pytest.raises(Exception, match="Prometheus error 400: parse error"):
        run(tools.query_metrics("bad("))


def test_check_health_reports_each_service():
    def health(request):
        return httpx.Response(
            200, json={"status": "ok", "deployment": "local", "version": "abc"}
        )

    out = run(
        Tools(settings(), transport=httpx.MockTransport(health)).check_health("local")
    )
    assert (
        out["results"][0]["version"] == "abc"
        and out["results"][0]["http_status"] == 200
    )


# --- server: tool list, audit, auth --------------------------------------------


def test_server_exposes_exactly_four_tools_and_audits_calls(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    server = build_server(Tools(settings()), AuditLog(str(audit_file)))

    async def calls():
        async with Client(server) as client:
            names = [t.name for t in (await client.list_tools()).tools]
            ok = await client.call_tool(
                "read_source_file", {"path": "Makefile", "max_lines": 1}
            )
            bad = await client.call_tool("read_source_file", {"path": "../.env"})
            return names, ok, bad

    names, ok, bad = run(calls())
    assert sorted(names) == sorted(TOOL_NAMES)
    assert not ok.is_error and bad.is_error
    entries = [json.loads(line) for line in audit_file.read_text().splitlines()]
    assert [e["outcome"] for e in entries] == ["ok", "error"]
    assert entries[0]["tool"] == "read_source_file" and entries[0]["result_bytes"] > 0


def test_http_requests_need_the_token(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    app = create_app("right-token", settings(), AuditLog(str(audit_file)))
    with TestClient(app, base_url="http://127.0.0.1:8090") as client:
        assert client.get("/health").status_code == 200
        denied = client.post("/mcp", json={}, headers={"Authorization": "Bearer wrong"})
        assert denied.status_code == 401
    entry = json.loads(audit_file.read_text().splitlines()[-1])
    assert entry["outcome"] == "denied" and "right-token" not in audit_file.read_text()


def test_server_refuses_to_start_without_a_token():
    with pytest.raises(SystemExit):
        create_app("")
