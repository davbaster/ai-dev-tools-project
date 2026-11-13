"""One-command local demo for reviewers (#69).

    make demo-local         # run it (~6-8 minutes)
    make demo-local-clean   # remove everything it created

What it does, step by step, printing where to look:
 1. creates a throwaway git worktree (.demo/workspace) from HEAD and puts the demo
    bug in it (demo/bug.json): your working tree and main never change;
 2. starts the full stack with docker-compose.demo.yml (backend, MCP server and
    responder run the workspace; the responder in local mode);
 3. saves long titles until the SaveItemFailing alert fires and the responder
    opens an incident (demo-output/incident-1.md), investigates and writes a fix;
 4. rebuilds the backend from the fixed workspace and keeps saving until the
    alert resolves and the responder closes the incident;
 5. prints a summary. The draft release PR is demo-output/prod-pr-1.md: nothing is
    pushed or deployed; in the real flow a human merges it.

Without LLM_API_KEY in .env the responder replays a recorded real investigation
(the tools, checks and fix still run here). Standard library + httpx only.
"""

import json
import secrets
import shutil
import subprocess  # nosec B404 - only fixed git/docker commands, no shell
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / ".demo" / "workspace"
OUTPUT = ROOT / "demo-output"
COMPOSE = [
    "docker",
    "compose",
    "-f",
    "docker-compose.yml",
    "-f",
    "docker-compose.demo.yml",
]
APP = "http://localhost:8000"
LONG_TITLE = "Un artículo muy largo sobre cómo guardar cosas para leer más tarde"
TIMEOUTS = {"incident": 8 * 60, "fix": 6 * 60, "closed": 12 * 60}


def say(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def fail(message: str) -> None:
    print(f"\nDemo stopped: {message}", file=sys.stderr)
    print("Logs: make responder-logs · Grafana: http://localhost:3000", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603
        cmd, cwd=ROOT, text=True, capture_output=True, check=False, **kwargs
    )


def check_prerequisites() -> None:
    for tool in ("git", "docker"):
        if shutil.which(tool) is None:
            fail(f"{tool} is not installed or not on the PATH")
    if run(["docker", "info"]).returncode != 0:
        fail("Docker isn't running: start Docker Desktop (or the Docker service)")


def git_branches() -> list[str]:
    out = run(["git", "branch", "--list", "demo/*", "--format=%(refname:short)"]).stdout
    return [b.strip() for b in out.splitlines() if b.strip()]


def remove_workspace() -> None:
    if WORKSPACE.exists() or (ROOT / ".git" / "worktrees").exists():
        run(["git", "worktree", "remove", "--force", str(WORKSPACE)])
        run(["git", "worktree", "prune"])
    shutil.rmtree(ROOT / ".demo", ignore_errors=True)
    for branch in git_branches():
        run(["git", "branch", "-D", branch])


def create_workspace() -> str:
    remove_workspace()
    branch = f"demo/{datetime.now():%Y%m%d-%H%M%S}"
    result = run(["git", "worktree", "add", "-b", branch, str(WORKSPACE), "HEAD"])
    if result.returncode != 0:
        fail(f"git worktree add failed: {result.stderr.strip()}")
    bug = json.loads((ROOT / "demo" / "bug.json").read_text(encoding="utf-8"))
    target = WORKSPACE / bug["path"]
    text = target.read_text(encoding="utf-8")
    if text.count(bug["old"]) != 1:
        fail(f"can't place the demo bug: {bug['path']} changed (update demo/bug.json)")
    target.write_text(text.replace(bug["old"], bug["new"], 1), encoding="utf-8")
    return branch


def compose(*args: str, timeout: int = 1800) -> None:
    result = run([*COMPOSE, *args], timeout=timeout)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout).strip().splitlines()[-8:]
        fail("docker compose " + " ".join(args) + " failed:\n" + "\n".join(tail))


def index() -> list[dict]:
    path = OUTPUT / "incidents.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


class User:
    def __init__(self):
        self.client = httpx.Client(base_url=APP, timeout=30)
        name = "demo" + secrets.token_hex(3)
        self.client.post(
            "/register", data={"username": name, "password": secrets.token_urlsafe(12)}
        )
        page = self.client.get("/items").text
        marker = '<option value="'
        start = page.find(marker)
        if start < 0:
            fail("couldn't register a demo user at http://localhost:8000")
        self.category = page[start + len(marker) : page.find('"', start + len(marker))]

    def save(self, title: str) -> int:
        try:
            response = self.client.post(
                "/items",
                data={
                    "url": "https://example.org/demo",
                    "title": title,
                    "category_id": self.category,
                    "note": "",
                    "filter": "",
                },
            )
            return response.status_code
        except httpx.HTTPError:
            return 0


def wait_for(what: str, condition, user: User, title: str, seconds: int) -> None:
    end = time.time() + seconds
    while time.time() < end:
        user.save(title)
        if condition():
            return
        time.sleep(3)
    fail(f"timed out waiting for {what} ({seconds // 60} min)")


def demo() -> None:
    started = time.time()
    check_prerequisites()
    say("Creating the throwaway workspace (.demo/workspace) with the demo bug...")
    branch = create_workspace()
    shutil.rmtree(OUTPUT, ignore_errors=True)
    OUTPUT.mkdir()
    say(
        "Starting the stack with the demo override (first run builds images: a few minutes)..."
    )
    compose("up", "-d", "--build", "--wait")
    agent_logs = run([*COMPOSE, "logs", "oncall-agent"]).stdout
    mode = (
        "replayed (no LLM_API_KEY)"
        if '"llm": "ReplayLLM"' in agent_logs
        else "live LLM"
    )
    say(
        f"Stack up. Responder: local mode, {mode}. Grafana: http://localhost:3000 (dashboard 'Para Luego')."
    )

    user = User()
    say(
        f"Saving a short title: {user.save('Corto')} | a long title (> 40 chars): {user.save(LONG_TITLE)} (the bug)"
    )
    say(
        "Saving long titles every few seconds until SaveItemFailing fires (~2-3 min)..."
    )
    wait_for(
        "the incident", lambda: bool(index()), user, LONG_TITLE, TIMEOUTS["incident"]
    )
    incident = index()[0]
    number = incident["number"]
    say(f"Incident opened: demo-output/incident-{number}.md - {incident['title']}")

    say(
        "The responder investigates with the MCP tools (make responder-logs to follow)..."
    )

    def finished():
        item = next(i for i in index() if i["number"] == number)
        return (OUTPUT / f"fix-{number}.diff").exists() or "needs-human" in item[
            "labels"
        ]

    wait_for("the responder", finished, user, LONG_TITLE, TIMEOUTS["fix"])
    if not (OUTPUT / f"fix-{number}.diff").exists():
        fail(
            f"the responder escalated (needs-human): read demo-output/incident-{number}.md"
        )
    say(f"Fix written to the workspace: demo-output/fix-{number}.diff")
    say(
        f"Draft release PR for a human: demo-output/prod-pr-{number}.md (nothing pushed or deployed)"
    )

    say("Rebuilding the backend from the fixed workspace (bug flag still on)...")
    compose("up", "-d", "--build", "--no-deps", "--wait", "backend")
    say(f"Long title after the fix: {user.save(LONG_TITLE)} (303 = saved)")
    say(
        "Waiting for the alert to resolve and the responder to close the incident (~4-6 min)..."
    )

    def closed():
        return next(i for i in index() if i["number"] == number)["state"] == "closed"

    wait_for("the incident to close", closed, user, LONG_TITLE, TIMEOUTS["closed"])

    minutes = (time.time() - started) / 60
    print(
        f"""
Demo finished in {minutes:.1f} min. Investigation: {mode}.
  incident        demo-output/incident-{number}.md   (cause, evidence, diff, resolution)
  fix             demo-output/fix-{number}.diff       (applied to .demo/workspace, branch {branch})
  draft prod PR   demo-output/prod-pr-{number}.md     (a human would review and merge it)
  Grafana         http://localhost:3000             (alerts, traces, logs)
Nothing was pushed, deployed or changed on main. The stack keeps running;
`make demo-local-clean` removes the workspace and the demo files.
"""
    )


def clean() -> None:
    check_prerequisites()
    say("Stopping the demo containers...")
    run([*COMPOSE, "down"])
    say("Removing .demo/ (worktree and demo/* branches) and demo-output/...")
    remove_workspace()
    shutil.rmtree(OUTPUT, ignore_errors=True)
    say("Clean. `make up` runs main again.")


if __name__ == "__main__":
    {"run": demo, "clean": clean}.get(
        sys.argv[1] if len(sys.argv) > 1 else "run", demo
    )()
