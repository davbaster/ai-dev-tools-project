"""The four read-only on-call tools (#16). Each returns plain data (dicts);
server.py redacts, audits and serializes it.

Nothing here writes, deploys, restarts or runs commands: Loki and Prometheus
read APIs, GETs to health URLs, and files from a read-only repo.
"""

import asyncio
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from oncall.mcp_server import guards
from oncall.mcp_server.guards import ToolInputError

SERVICES = ("frontend", "backend")
ENVIRONMENTS = ("local", "dev", "prod")
LEVELS = ("ERROR", "WARNING", "INFO")
MAX_SERIES = 50
HEALTH_TIMEOUT_SECONDS = 70  # un servicio gratis de Render tarda ~60 s en despertar
QUERY_TIMEOUT_SECONDS = 15

# Formato de HEALTH_URLS: "env:service=url,..."; por defecto Compose, dev y prod.
DEFAULT_HEALTH_URLS = (
    "local:frontend=http://frontend:8000/health,"
    "local:backend=http://backend:8001/api/health,"
    "dev:frontend=https://para-luego-dev-frontend.onrender.com/health,"
    "dev:backend=https://para-luego-dev-backend.onrender.com/api/health,"
    "prod:frontend=https://para-luego-prod-frontend.onrender.com/health,"
    "prod:backend=https://para-luego-prod-backend.onrender.com/api/health"
)


class UpstreamError(RuntimeError):
    """Loki, Prometheus or a health URL failed; the message names which."""


@dataclass
class Settings:
    loki_url: str = "http://loki:3100"
    prometheus_url: str = "http://prometheus:9090"
    repo_root: Path = Path("/repo")
    # [(environment, service, url)]
    health: list[tuple[str, str, str]] = field(default_factory=list)


def parse_health_urls(value: str) -> list[tuple[str, str, str]]:
    """'env:service=url,...' -> [(env, service, url)]."""
    targets = []
    for item in filter(None, (part.strip() for part in value.split(","))):
        key, _, url = item.partition("=")
        environment, _, service = key.partition(":")
        if environment not in ENVIRONMENTS or service not in SERVICES or not url:
            raise ValueError(f"bad HEALTH_URLS entry: {item!r}")
        targets.append((environment, service, url))
    return targets


def load_settings() -> Settings:
    return Settings(
        loki_url=os.environ.get("LOKI_URL", "http://loki:3100").rstrip("/"),
        prometheus_url=os.environ.get(
            "PROMETHEUS_URL", "http://prometheus:9090"
        ).rstrip("/"),
        repo_root=Path(os.environ.get("REPO_ROOT", "/repo")),
        health=parse_health_urls(os.environ.get("HEALTH_URLS", DEFAULT_HEALTH_URLS)),
    )


class Tools:
    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ):
        self.settings = settings
        self._transport = transport

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=self._transport)

    async def _get_json(self, name: str, url: str, params: dict) -> dict:
        try:
            async with self._client(QUERY_TIMEOUT_SECONDS) as client:
                response = await client.get(url, params=params)
        except httpx.HTTPError as error:
            raise UpstreamError(
                f"{name} is unreachable ({type(error).__name__})"
            ) from error
        try:
            body = response.json()
        except ValueError:
            raise UpstreamError(
                f"{name} answered {response.status_code} without JSON"
            ) from None
        if response.status_code >= 400 or body.get("status") == "error":
            message = body.get("error") or body.get("message") or response.text[:300]
            raise UpstreamError(f"{name} error {response.status_code}: {message}")
        return body

    async def get_recent_logs(
        self,
        service: str,
        minutes: int = 15,
        level: str | None = None,
        trace_id: str | None = None,
        contains: str | None = None,
        limit: int = 50,
    ) -> dict:
        if service not in SERVICES:
            raise ToolInputError(f"service must be one of {', '.join(SERVICES)}")
        guards.check_range("minutes", minutes, 1, 60)
        guards.check_range("limit", limit, 1, 200)
        query = f'{{service_name="para-luego-{service}"}}'
        if level is not None:
            if level not in LEVELS:
                raise ToolInputError(f"level must be one of {', '.join(LEVELS)}")
            query += f" | level={guards.logql_string(level)}"
        if trace_id is not None:
            if not guards.HEX32.match(trace_id):
                raise ToolInputError("trace_id must be 32 lowercase hex characters")
            query += f" | trace_id={guards.logql_string(trace_id)}"
        if contains:
            query += f" |= {guards.logql_string(contains)}"
        end = time.time_ns()
        body = await self._get_json(
            "Loki",
            f"{self.settings.loki_url}/loki/api/v1/query_range",
            {
                "query": query,
                "start": end - minutes * 60 * 10**9,
                "end": end,
                "limit": limit,
                "direction": "backward",
            },
        )
        lines = [
            (int(ts), line)
            for stream in body["data"]["result"]
            for ts, line, *_ in stream["values"]
        ]
        lines.sort(reverse=True)
        return {
            "query": query,
            "count": len(lines[:limit]),
            "lines": [line for _, line in lines[:limit]],
        }

    async def query_metrics(self, query: str, minutes: int = 0) -> dict:
        if not query or not query.strip():
            raise ToolInputError("query is empty")
        guards.check_range("minutes", minutes, 0, 60)
        base = self.settings.prometheus_url
        if minutes == 0:
            body = await self._get_json(
                "Prometheus", f"{base}/api/v1/query", {"query": query}
            )
        else:
            end = time.time()
            body = await self._get_json(
                "Prometheus",
                f"{base}/api/v1/query_range",
                {
                    "query": query,
                    "start": end - minutes * 60,
                    "end": end,
                    "step": max(15, minutes),  # a lo sumo ~60 puntos por serie
                },
            )
        data = body["data"]
        result = data["result"]
        series = []
        if data["resultType"] in ("vector", "matrix"):
            for item in result[:MAX_SERIES]:
                entry = {"labels": item["metric"]}
                if "value" in item:
                    entry["value"] = item["value"][1]
                else:
                    entry["values"] = [[t, v] for t, v in item["values"]]
                series.append(entry)
        else:  # scalar o string
            series.append({"value": result[1]})
        answer = {"query": query, "type": data["resultType"], "series": series}
        if isinstance(result, list) and len(result) > MAX_SERIES:
            answer["note"] = f"{len(result)} series, showing the first {MAX_SERIES}"
        return answer

    async def check_health(self, environment: str = "all") -> dict:
        if environment != "all" and environment not in ENVIRONMENTS:
            raise ToolInputError(
                f"environment must be all or one of {', '.join(ENVIRONMENTS)}"
            )
        targets = [t for t in self.settings.health if environment in ("all", t[0])]

        async def one(client, env, service, url):
            start = time.perf_counter()
            entry = {"environment": env, "service": service, "url": url}
            try:
                response = await client.get(url)
                entry["http_status"] = response.status_code
                try:
                    entry.update(
                        {
                            k: v
                            for k, v in response.json().items()
                            if k in ("status", "deployment", "version")
                        }
                    )
                except ValueError:
                    entry["error"] = "answer is not JSON"
            except httpx.HTTPError as error:
                entry["error"] = type(error).__name__
            entry["latency_ms"] = round((time.perf_counter() - start) * 1000)
            return entry

        async with self._client(HEALTH_TIMEOUT_SECONDS) as client:
            results = await asyncio.gather(*(one(client, *t) for t in targets))
        return {"environment": environment, "results": list(results)}

    async def read_source_file(
        self, path: str, start_line: int = 1, max_lines: int = 200
    ) -> dict:
        guards.check_range("max_lines", max_lines, 1, 400)
        guards.check_range("start_line", start_line, 1, 10**6)
        root = self.settings.repo_root
        target = guards.safe_repo_path(root, path)
        if target.is_dir():
            return {"path": path, "entries": guards.list_directory(root, target)}
        lines = guards.read_text_file(target).splitlines()
        chunk = lines[start_line - 1 : start_line - 1 + max_lines]
        numbered = "\n".join(
            f"{number:>5}  {text}"
            for number, text in enumerate(chunk, start=start_line)
        )
        return {
            "path": path,
            "total_lines": len(lines),
            "from_line": start_line,
            "to_line": start_line + len(chunk) - 1,
            "content": numbered,
        }
