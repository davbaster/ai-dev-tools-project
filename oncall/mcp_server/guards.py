"""Argument checks for the tools: repo paths, LogQL strings, ranges."""

import re
from pathlib import Path

# Lo que read_source_file puede leer, relativo a la raíz del repo.
ALLOWED_TOP = {
    "backend",
    "frontend",
    "telemetry",
    "migrations",
    "api",
    "tests",
    "oncall",
    "observability",
    "_docs",
    ".github",
    "Makefile",
    "docker-compose.yml",
    "docker-compose.test.yml",
    "Dockerfile",
    "pyproject.toml",
    "render.yaml",
    "render.prod.yaml",
    ".env.example",
    "README.md",
    "AGENTS.md",
    "HANDOFF.md",
    "alembic.ini",
}
MAX_FILE_BYTES = 200 * 1024
SKIP_IN_LISTINGS = {"__pycache__", ".git", ".pytest_cache", ".ruff_cache"}
HEX32 = re.compile(r"^[0-9a-f]{32}$")


class ToolInputError(ValueError):
    """An argument the tool refuses; the message goes back to the caller."""


def check_range(name: str, value: int, low: int, high: int) -> int:
    if not isinstance(value, int) or not low <= value <= high:
        raise ToolInputError(f"{name} must be an integer from {low} to {high}")
    return value


def _forbidden_name(part: str) -> bool:
    return part == ".git" or (part.startswith(".env") and part != ".env.example")


def safe_repo_path(root: Path, path: str) -> Path:
    """Resolve path inside root, or raise ToolInputError."""
    if not path or "\x00" in path:
        raise ToolInputError("path is empty or invalid")
    raw = Path(path)
    if raw.is_absolute() or path.startswith(("/", "\\")) or ":" in path:
        raise ToolInputError("path must be relative to the repository root")
    root = root.resolve()
    target = (root / raw).resolve()
    try:
        relative = target.relative_to(root)
    except ValueError:
        raise ToolInputError("path leaves the repository") from None
    parts = relative.parts
    if not parts:
        return target
    if parts[0] not in ALLOWED_TOP:
        raise ToolInputError(f"{parts[0]!r} is not readable through this tool")
    if any(_forbidden_name(part) for part in parts):
        raise ToolInputError("secrets and .git are not readable")
    if not target.exists():
        raise ToolInputError(f"{relative.as_posix()} does not exist")
    return target


def read_text_file(target: Path) -> str:
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ToolInputError(f"file is over {MAX_FILE_BYTES // 1024} KB")
    data = target.read_bytes()
    if b"\x00" in data[:8192]:
        raise ToolInputError("binary file")
    return data.decode("utf-8", errors="replace")


def list_directory(root: Path, target: Path) -> list[str]:
    at_root = target.resolve() == root.resolve()
    entries = []
    for child in sorted(target.iterdir()):
        name = child.name
        if name in SKIP_IN_LISTINGS or _forbidden_name(name):
            continue
        if at_root and name not in ALLOWED_TOP:
            continue
        entries.append(name + "/" if child.is_dir() else name)
    return entries


def logql_string(value: str) -> str:
    """A LogQL double-quoted string literal; the value can't end it early."""
    if any(ord(ch) < 32 for ch in value):
        raise ToolInputError("text can't contain control characters")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
