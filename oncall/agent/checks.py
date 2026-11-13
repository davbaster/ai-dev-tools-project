"""Checks a proposed fix before it is pushed (#17): on a temporary copy of the
repository, never on the repo or the running app. ruff and the suites that need
no Docker (unit, frontend, contract); integration runs in CI.
"""

import asyncio
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

IGNORE = shutil.ignore_patterns(
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mcp-audit*",
    ".env",
)
COMMANDS = (
    ("ruff check", [sys.executable, "-m", "ruff", "check", "."]),
    ("ruff format --check", [sys.executable, "-m", "ruff", "format", "--check", "."]),
    (
        "pytest unit/frontend/contract",
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/unit",
            "tests/frontend",
            "tests/contract",
        ],
    ),
)
TIMEOUT_SECONDS = 300
OUTPUT_TAIL = 3000


@dataclass
class CheckResult:
    ok: bool
    report: str


async def _run(name: str, command: list[str], cwd: Path) -> tuple[bool, str]:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), TIMEOUT_SECONDS)
    except TimeoutError:
        process.kill()
        return False, f"{name}: timed out after {TIMEOUT_SECONDS} s"
    text = output.decode("utf-8", errors="replace")
    return (
        process.returncode == 0,
        f"{name}: exit {process.returncode}\n{text[-OUTPUT_TAIL:]}",
    )


async def check_fix(repo_root: Path, files: dict[str, str]) -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="oncall-fix-") as tmp:
        work = Path(tmp) / "repo"
        # Solo el contenido, sin permisos: montado desde Windows, todo parece
        # ejecutable y ruff fallaría con EXE002.
        await asyncio.to_thread(
            shutil.copytree,
            repo_root,
            work,
            ignore=IGNORE,
            copy_function=shutil.copyfile,
        )
        for path, content in files.items():
            target = work / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        reports = []
        for name, command in COMMANDS:
            ok, report = await _run(name, command, work)
            reports.append(report)
            if not ok:
                return CheckResult(False, "\n\n".join(reports))
        return CheckResult(True, "\n\n".join(r.splitlines()[0] for r in reports))
