"""Configuration of the responder, from environment variables only."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    webhook_token: str
    mcp_url: str
    mcp_token: str
    github_token: str
    github_repository: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_reasoning_effort: str
    allow_push: bool
    target_branch: str
    repo_root: Path
    # github (default) or local: the local demo (#69) writes incidents, fixes
    # and the draft prod PR as files, and never calls GitHub.
    mode: str = "github"
    # Alert names to handle; empty = all. The local demo follows SaveItemFailing
    # only (one cause also fires HighServerErrors, #62).
    only_alerts: frozenset = frozenset()
    demo_output: Path = Path("/demo-output")
    max_steps: int = 20
    max_seconds: int = 600
    max_fix_attempts: int = 2


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def load_config() -> Config:
    config = Config(
        webhook_token=os.environ.get("ALERT_WEBHOOK_TOKEN", "").strip(),
        mcp_url=os.environ.get("MCP_URL", "http://mcp-server:8090/mcp").strip(),
        mcp_token=os.environ.get("MCP_TOKEN", "").strip(),
        github_token=os.environ.get("GITHUB_TOKEN", "").strip(),
        github_repository=os.environ.get(
            "GITHUB_REPOSITORY", "davbaster/ai-dev-tools-project"
        ).strip(),
        llm_base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        .strip()
        .rstrip("/"),
        llm_api_key=os.environ.get("LLM_API_KEY", "").strip(),
        llm_model=os.environ.get("LLM_MODEL", "gpt-6-luna").strip(),
        llm_reasoning_effort=os.environ.get("LLM_REASONING_EFFORT", "").strip(),
        allow_push=_flag("RESPONDER_ALLOW_PUSH"),
        target_branch=os.environ.get("RESPONDER_TARGET_BRANCH", "main").strip()
        or "main",
        repo_root=Path(os.environ.get("REPO_ROOT", "/repo")),
        mode=os.environ.get("RESPONDER_MODE", "github").strip() or "github",
        only_alerts=frozenset(
            a.strip()
            for a in os.environ.get("RESPONDER_ONLY_ALERTS", "").split(",")
            if a.strip()
        ),
        demo_output=Path(os.environ.get("DEMO_OUTPUT", "/demo-output")),
    )
    if config.mode not in ("github", "local"):
        raise SystemExit(f"RESPONDER_MODE must be github or local, not {config.mode!r}")
    missing = [
        name
        for name, value in (
            ("ALERT_WEBHOOK_TOKEN", config.webhook_token),
            ("MCP_TOKEN", config.mcp_token),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            f"{', '.join(missing)} not set: the responder refuses to start."
        )
    return config
