"""HTTP entry point of the responder (#17): Grafana's webhook and a health check.

Run: the `oncall-agent` Compose service (`python -m oncall.agent.app`).
"""

import asyncio
import hmac
import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import telemetry
from oncall.agent.config import load_config
from oncall.agent.github import GitHub
from oncall.agent.llm import LLM, RecordingLLM, ReplayLLM
from oncall.agent.local import LocalTracker
from oncall.agent.mcp_tools import MCPTools
from oncall.agent.responder import Responder

SERVICE_NAME = "para-luego-oncall"
log = logging.getLogger("oncall.app")
# Dentro del contenedor escucha en todas las interfaces; Compose publica el puerto
# solo en 127.0.0.1.
BIND_ALL = "0.0.0.0"  # nosec B104


def create_app(responder: Responder, webhook_token: str) -> FastAPI:
    app = FastAPI(title="Para Luego on-call responder", docs_url=None, redoc_url=None)
    expected = f"Bearer {webhook_token}".encode()
    tasks: set[asyncio.Task] = set()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/alerts")
    async def alerts(request: Request):
        given = request.headers.get("authorization", "").encode()
        if not hmac.compare_digest(given, expected):
            log.warning("alert webhook denied")
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            payload = await request.json()
        except ValueError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        if not isinstance(payload, dict):
            return JSONResponse(
                {"error": "body must be a JSON object"}, status_code=400
            )
        log.info(
            "alert received",
            extra={
                "fields": {
                    "status": payload.get("status"),
                    "alertname": (payload.get("groupLabels") or {}).get("alertname"),
                }
            },
        )
        # Se responde enseguida; la investigación sigue en segundo plano.
        task = asyncio.create_task(responder.handle_alert(payload))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return JSONResponse({"status": "accepted"}, status_code=202)

    return app


def build_responder(config, replay: str = "", record: str = "") -> Responder:
    """The responder for this config: where incidents go and which LLM decides."""
    if config.mode == "local":
        # Demo local (#69): incidentes y arreglo como archivos; nunca GitHub.
        tracker = LocalTracker(config.demo_output, config.repo_root)
    elif config.github_token:
        tracker = GitHub(config.github_token, config.github_repository)
    else:
        tracker = None
        log.warning(
            "GITHUB_TOKEN not set: alerts are logged but no incidents are opened"
        )
    llm = LLM(
        config.llm_base_url,
        config.llm_api_key,
        config.llm_model,
        config.llm_reasoning_effort,
    )
    if config.llm_api_key and record:
        llm = RecordingLLM(llm, Path(record))
    elif not config.llm_api_key and replay:
        llm = ReplayLLM(Path(replay))
        log.warning("LLM_API_KEY not set: investigations replay a recorded run")
    elif not config.llm_api_key:
        log.warning(
            "LLM_API_KEY not set: incidents will be escalated without investigation"
        )
    return Responder(config, tracker, llm, MCPTools(config.mcp_url, config.mcp_token))


def main() -> None:
    config = load_config()
    telemetry.setup_logging(
        SERVICE_NAME,
        os.environ.get("DEPLOYMENT", "local"),
        os.environ.get("APP_VERSION", "").strip() or "local",
    )
    responder = build_responder(
        config,
        replay=os.environ.get("RESPONDER_REPLAY", "").strip(),
        record=os.environ.get("RESPONDER_RECORD", "").strip(),
    )
    llm = responder.llm
    log.info(
        "responder ready",
        extra={
            "fields": {
                "allow_push": config.allow_push,
                "target_branch": config.target_branch,
                "model": config.llm_model,
                "mode": config.mode,
                "llm": type(llm).__name__,
            }
        },
    )
    uvicorn.run(
        create_app(responder, config.webhook_token),
        host=os.environ.get("RESPONDER_HOST", BIND_ALL),
        port=int(os.environ.get("RESPONDER_PORT", "8080")),
        log_config=None,
    )


if __name__ == "__main__":
    main()
