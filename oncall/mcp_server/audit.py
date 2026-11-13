"""Audit log: one JSON line per call (allowed, failed or denied) (#16).

Written to MCP_AUDIT_LOG (a Compose volume) and to stdout through the JSON
logger. Arguments are redacted; the token and the raw result never appear.
"""

import json
import logging
import threading
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from oncall.mcp_server.redact import redact_value

log = logging.getLogger("mcp.audit")
_lock = threading.Lock()
# Quién llama (User-Agent del request HTTP); lo pone el middleware de auth.
client_id: ContextVar[str] = ContextVar("client_id", default="unknown")


class AuditLog:
    def __init__(self, path: str | None):
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        tool: str,
        arguments: dict,
        outcome: str,
        result_bytes: int = 0,
        duration_ms: float = 0.0,
        error: str | None = None,
    ) -> dict:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "tool": tool,
            "arguments": redact_value(arguments),
            "outcome": outcome,
            "result_bytes": result_bytes,
            "duration_ms": round(duration_ms, 1),
            "client": client_id.get(),
        }
        if error:
            entry["error"] = redact_value(error)
        line = json.dumps(entry, ensure_ascii=False)
        with _lock:
            if self.path:
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
        log.info("tool call", extra={"fields": {"audit": entry}})
        return entry
