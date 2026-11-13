"""The on-call responder (#17) with a fake GitHub, LLM, MCP server and checks."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from oncall.agent.app import create_app
from oncall.agent.checks import CheckResult
from oncall.agent.config import Config
from oncall.agent.github import GitHub
from oncall.agent.llm import LLMError
from oncall.agent.responder import Responder, _validate_fix

ROOT = Path(__file__).resolve().parents[2]
TOKEN_IN_LOGS = "ghp_" + "Z" * 36


def config(**kwargs) -> Config:
    base = {
        "webhook_token": "hook-token",
        "mcp_url": "http://mcp.test/mcp",
        "mcp_token": "mcp-token",
        "github_token": "gh-token",
        "github_repository": "davbaster/ai-dev-tools-project",
        "llm_base_url": "http://llm.test",
        "llm_api_key": "llm-key",
        "llm_model": "test-model",
        "allow_push": True,
        "target_branch": "main",
        "repo_root": ROOT,
    }
    return Config(**{**base, **kwargs})


def alert(status="firing", name="SaveItemFailing") -> dict:
    return {
        "status": status,
        "groupLabels": {"alertname": name},
        "alerts": [
            {
                "status": status,
                "labels": {"alertname": name, "severity": "page"},
                "annotations": {
                    "summary": "Saving items fails",
                    "description": "5xx > 5%",
                },
                "startsAt": "2026-11-13T03:34:30Z",
                "endsAt": "2026-11-13T03:40:00Z",
                "generatorURL": "http://localhost:3000/alerting/x",
            }
        ],
    }


class FakeGitHub:
    """Answers the GitHub API calls the responder makes and records them."""

    def __init__(self, open_issues=None):
        self.calls: list[tuple[str, str, dict]] = []
        self.open_issues = open_issues or []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/repos/davbaster/ai-dev-tools-project")
        body = json.loads(request.content) if request.content else {}
        self.calls.append((request.method, path, body))
        assert request.headers["authorization"] == "Bearer gh-token"
        if request.method == "GET" and path == "/issues":
            return httpx.Response(200, json=self.open_issues)
        if request.method == "POST" and path == "/issues":
            self.open_issues.append({"number": 7, "title": body["title"]})
            return httpx.Response(201, json={"number": 7})
        if path.startswith("/git/ref/heads/"):
            return httpx.Response(200, json={"object": {"sha": "parent"}})
        if path == "/git/commits/parent":
            return httpx.Response(200, json={"tree": {"sha": "tree0"}})
        if path == "/git/trees":
            return httpx.Response(201, json={"sha": "tree1"})
        if path == "/git/commits":
            return httpx.Response(201, json={"sha": "abc1234def"})
        if request.method == "GET" and path == "/pulls":
            return httpx.Response(200, json=[])
        if request.method == "POST" and path == "/pulls":
            return httpx.Response(201, json={"number": 9, "html_url": "https://pr/9"})
        return httpx.Response(200, json={})

    def posted(self, method, prefix):
        return [
            body for m, p, body in self.calls if m == method and p.startswith(prefix)
        ]


class FakeLLM:
    def __init__(self, *messages):
        self.messages = list(messages)
        self.seen = []

    async def chat(self, messages, tools):
        self.seen.append([t["function"]["name"] for t in tools])
        if not self.messages:
            return {"role": "assistant", "content": "thinking"}
        item = self.messages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        names = ("get_recent_logs", "query_metrics", "check_health", "read_source_file")
        return [
            {"name": n, "description": n, "parameters": {"type": "object"}}
            for n in names
        ]

    async def call(self, name, args):
        self.calls.append((name, args))
        return f'{{"lines": ["error trace_id=4bf92f3577b34da6a3ce929d0e0e4736 {TOKEN_IN_LOGS}"]}}'


def tool_call(name, args, call_id="c1"):
    return {
        "role": "assistant",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    }


FIX = {
    "files": [
        {"path": "backend/items.py", "content": "x = 1\n"},
        {
            "path": "tests/unit/test_fix.py",
            "content": "def test_x():\n    assert True\n",
        },
    ],
    "summary": "Save items with long titles",
    "cause": "items.py raises on titles over 50 characters",
    "evidence": f"log line with {TOKEN_IN_LOGS}",
}


async def passing(root, files):
    return CheckResult(True, "ruff check: exit 0\npytest: exit 0")


def responder(gh: FakeGitHub, llm: FakeLLM, checker=passing, **cfg):
    return Responder(
        config(**cfg),
        GitHub(
            "gh-token",
            "davbaster/ai-dev-tools-project",
            transport=httpx.MockTransport(gh),
        ),
        llm,
        FakeMCP(),
        checker=checker,
    )


def run(coro):
    return asyncio.run(coro)


def test_webhook_needs_the_token():
    r = responder(FakeGitHub(), FakeLLM())
    with TestClient(create_app(r, "hook-token")) as client:
        assert client.post("/alerts", json=alert()).status_code == 401
        bad = client.post(
            "/alerts", json=alert(), headers={"Authorization": "Bearer nope"}
        )
        assert bad.status_code == 401
        assert client.get("/health").json() == {"status": "ok"}


def test_fix_path_opens_incident_commits_and_opens_prod_pr():
    gh = FakeGitHub()
    llm = FakeLLM(
        tool_call("get_recent_logs", {"service": "backend", "level": "ERROR"}),
        tool_call("propose_fix", FIX),
    )
    r = responder(gh, llm)
    run(r.handle_alert(alert()))
    issue = gh.posted("POST", "/issues")[0]
    assert issue["title"].startswith("[incident] SaveItemFailing:") and issue[
        "labels"
    ] == ["incident"]
    tree = gh.posted("POST", "/git/trees")[0]
    assert {t["path"] for t in tree["tree"]} == {
        "backend/items.py",
        "tests/unit/test_fix.py",
    }
    commit = gh.posted("POST", "/git/commits")[0]
    assert commit["message"].endswith("Fixes #7") and commit["parents"] == ["parent"]
    assert gh.posted("PATCH", "/git/refs/heads/main") == [{"sha": "abc1234def"}]
    assert gh.posted("POST", "/pulls")[0]["base"] == "prod"
    report = gh.posted("POST", "/issues/7/comments")[-1]["body"]
    assert "## Cause" in report and "https://pr/9" in report and "abc1234" in report
    assert TOKEN_IN_LOGS not in json.dumps(gh.calls)  # redacted everywhere
    assert llm.seen[0] == [
        "get_recent_logs",
        "query_metrics",
        "check_health",
        "read_source_file",
        "propose_fix",
        "escalate",
    ]
    assert r.incidents["SaveItemFailing"].fixed


def test_qa_branch_gets_the_commit_but_no_prod_pr():
    gh = FakeGitHub()
    run(
        responder(
            gh, FakeLLM(tool_call("propose_fix", FIX)), target_branch="qa"
        ).handle_alert(alert())
    )
    assert gh.posted("PATCH", "/git/refs/heads/qa") and not gh.posted("POST", "/pulls")


def test_push_disabled_posts_the_diff_and_asks_a_human():
    gh = FakeGitHub()
    run(
        responder(
            gh, FakeLLM(tool_call("propose_fix", FIX)), allow_push=False
        ).handle_alert(alert())
    )
    assert not gh.posted("POST", "/git/commits")
    assert "```diff" in gh.posted("POST", "/issues/7/comments")[-1]["body"]
    assert gh.posted("POST", "/issues/7/labels") == [{"labels": ["needs-human"]}]


def test_failing_checks_twice_escalates_without_pushing():
    async def failing(root, files):
        return CheckResult(False, "pytest: exit 1\nFAILED test_fix")

    gh = FakeGitHub()
    llm = FakeLLM(tool_call("propose_fix", FIX), tool_call("propose_fix", FIX))
    run(responder(gh, llm, checker=failing).handle_alert(alert()))
    assert not gh.posted("POST", "/git/commits")
    assert gh.posted("POST", "/issues/7/labels") == [{"labels": ["needs-human"]}]
    assert (
        "failed its checks 2 times"
        in gh.posted("POST", "/issues/7/comments")[-1]["body"]
    )


def test_escalate_and_limits_label_needs_human():
    gh = FakeGitHub()
    args = {
        "checked": "logs, metrics",
        "ruled_out": "code",
        "next_steps": "check the DB",
    }
    run(responder(gh, FakeLLM(tool_call("escalate", args))).handle_alert(alert()))
    body = gh.posted("POST", "/issues/7/comments")[-1]["body"]
    assert "Needs human on-call" in body and "check the DB" in body

    gh2 = FakeGitHub()
    run(responder(gh2, FakeLLM(), max_steps=3).handle_alert(alert()))
    assert (
        "step limit (3 steps)" in gh2.posted("POST", "/issues/7/comments")[-1]["body"]
    )

    gh3 = FakeGitHub()
    run(
        responder(gh3, FakeLLM(LLMError("LLM_API_KEY is not set"))).handle_alert(
            alert()
        )
    )
    assert (
        "LLM_API_KEY is not set" in gh3.posted("POST", "/issues/7/comments")[-1]["body"]
    )


def test_repeated_alert_comments_on_the_open_incident():
    gh = FakeGitHub(
        open_issues=[{"number": 3, "title": "[incident] SaveItemFailing: x"}]
    )
    llm = FakeLLM()
    run(responder(gh, llm).handle_alert(alert()))
    assert not [b for m, p, b in gh.calls if (m, p) == ("POST", "/issues")]
    assert not llm.seen
    assert "still firing" in gh.posted("POST", "/issues/3/comments")[0]["body"]


def test_resolved_closes_only_after_a_fix():
    gh = FakeGitHub()
    r = responder(gh, FakeLLM(tool_call("propose_fix", FIX)))
    run(r.handle_alert(alert()))
    run(r.handle_alert(alert("resolved")))
    assert gh.posted("PATCH", "/issues/7") == [{"state": "closed"}]

    gh2 = FakeGitHub(
        open_issues=[{"number": 4, "title": "[incident] SaveItemFailing: x"}]
    )
    run(responder(gh2, FakeLLM()).handle_alert(alert("resolved")))
    assert not gh2.posted("PATCH", "/issues/4")
    assert (
        "left open for a human" in gh2.posted("POST", "/issues/4/comments")[0]["body"]
    )


@pytest.mark.parametrize(
    "files",
    [
        [
            {"path": ".github/workflows/ci.yml", "content": "x"},
            {"path": "tests/t.py", "content": ""},
        ],
        [
            {"path": "backend/../Makefile", "content": "x"},
            {"path": "tests/t.py", "content": ""},
        ],
        [{"path": "backend/x.py", "content": "x"}],
        [{"path": f"tests/t{i}.py", "content": ""} for i in range(4)],
    ],
)
def test_fix_paths_and_size_are_limited(files):
    assert isinstance(_validate_fix(files), str)
