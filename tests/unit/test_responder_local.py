"""The responder's local demo mode, replay and recording (#69)."""

import asyncio
import json
import shutil
from pathlib import Path

import httpx
import pytest
from test_responder import FIX, FakeLLM, FakeMCP, alert, config, passing, tool_call

from oncall.agent.app import build_responder
from oncall.agent.github import GitHub
from oncall.agent.llm import LLM, OUT_OF_DATE, RecordingLLM, ReplayLLM
from oncall.agent.local import LocalTracker
from oncall.agent.responder import Responder

ROOT = Path(__file__).resolve().parents[2]


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def workspace(tmp_path) -> Path:
    ws = tmp_path / "workspace"
    (ws / "backend").mkdir(parents=True)
    shutil.copy(ROOT / "backend" / "items.py", ws / "backend" / "items.py")
    return ws


def local_responder(tmp_path, workspace, llm, **cfg) -> Responder:
    settings = config(
        mode="local", repo_root=workspace, demo_output=tmp_path / "out", **cfg
    )
    return Responder(
        settings,
        LocalTracker(tmp_path / "out", workspace),
        llm,
        FakeMCP(),
        checker=passing,
    )


def test_local_mode_writes_incident_fix_and_draft_prod_pr(tmp_path, workspace):
    llm = FakeLLM(tool_call("propose_fix", FIX))
    responder = local_responder(tmp_path, workspace, llm)
    run(responder.handle_alert(alert()))
    out = tmp_path / "out"
    incident = (out / "incident-1.md").read_text(encoding="utf-8")
    assert "[incident] SaveItemFailing" in incident and "## Cause" in incident
    assert "prod-pr-1.md" in incident and "nothing was pushed" in incident
    assert "URL_MAX_LENGTH = 2049" in (workspace / "backend" / "items.py").read_text(
        encoding="utf-8"
    )
    assert (workspace / "tests" / "unit" / "test_fix.py").exists()
    assert "+URL_MAX_LENGTH = 2049" in (out / "fix-1.diff").read_text(encoding="utf-8")
    draft = (out / "prod-pr-1.md").read_text(encoding="utf-8")
    assert "a human reviews and merges" in draft and "Incident:** #1" in draft
    assert "ghp_" not in incident + draft  # redacted like on GitHub

    run(responder.handle_alert(alert("resolved")))
    assert json.loads((out / "incidents.json").read_text())[0]["state"] == "closed"
    assert "State: **closed**" in (out / "incident-1.md").read_text(encoding="utf-8")


def test_local_mode_never_builds_a_github_client(tmp_path, workspace):
    settings = config(mode="local", repo_root=workspace, demo_output=tmp_path / "out")
    assert settings.github_token  # aunque haya token en .env
    responder = build_responder(settings)
    assert isinstance(responder.github, LocalTracker)
    assert not isinstance(responder.github, GitHub)


def test_only_alerts_ignores_the_others(tmp_path, workspace):
    llm = FakeLLM()
    responder = local_responder(
        tmp_path, workspace, llm, only_alerts=frozenset({"SaveItemFailing"})
    )
    run(responder.handle_alert(alert(name="HighServerErrors")))
    assert not (tmp_path / "out" / "incidents.json").exists() and not llm.seen


def recorded(tmp_path, *messages) -> Path:
    path = tmp_path / "replay.json"
    path.write_text(
        json.dumps({"model": "m", "messages": list(messages)}), encoding="utf-8"
    )
    return path


def test_replay_plays_the_recorded_run_and_says_so(tmp_path, workspace):
    replay = ReplayLLM(
        recorded(
            tmp_path,
            tool_call("get_recent_logs", {"service": "backend"}),
            tool_call("propose_fix", FIX, "c2"),
        )
    )
    responder = local_responder(tmp_path, workspace, replay)
    run(responder.handle_alert(alert()))
    incident = (tmp_path / "out" / "incident-1.md").read_text(encoding="utf-8")
    assert "replayed investigation" in incident and "## Cause" in incident


def test_replay_out_of_date_escalates_instead_of_guessing(tmp_path, workspace):
    stale = {
        **FIX,
        "files": [
            {
                "path": "backend/items.py",
                "edits": [{"old": "no longer here", "new": "x"}],
            },
            FIX["files"][1],
        ],
    }
    replay = ReplayLLM(recorded(tmp_path, tool_call("propose_fix", stale)))
    responder = local_responder(tmp_path, workspace, replay)
    run(responder.handle_alert(alert()))
    incident = (tmp_path / "out" / "incident-1.md").read_text(encoding="utf-8")
    assert OUT_OF_DATE.split(":")[0] in incident and "needs-human" in incident


def test_recording_saves_redacted_messages(tmp_path):
    token = "ghp_" + "R" * 36

    def api(request):
        message = {"role": "assistant", "content": f"found {token} in a log"}
        return httpx.Response(200, json={"choices": [{"message": message}]})

    llm = LLM("http://llm.test", "k", "m", transport=httpx.MockTransport(api))
    path = tmp_path / "rec.json"
    run(RecordingLLM(llm, path).chat([], []))
    saved = path.read_text(encoding="utf-8")
    assert token not in saved and "[REDACTED]" in saved


def test_recorded_replay_still_fixes_the_demo_bug(tmp_path):
    # Si cambia display_title, la grabación queda vieja: volver a grabar (_docs/demo.md).
    from oncall.agent.responder import _validate_fix

    data = json.loads(
        (ROOT / "oncall/agent/replays/demo_bug.json").read_text(encoding="utf-8")
    )
    fix = next(
        json.loads(call["function"]["arguments"])
        for message in data["messages"]
        for call in message.get("tool_calls") or []
        if call["function"]["name"] == "propose_fix"
    )
    bug = json.loads((ROOT / "demo/bug.json").read_text(encoding="utf-8"))
    for path in ("backend/items.py", "tests/unit/test_display_title.py"):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / path, tmp_path / path)
    target = tmp_path / bug["path"]
    target.write_text(
        target.read_text(encoding="utf-8").replace(bug["old"], bug["new"], 1),
        encoding="utf-8",
    )
    files = _validate_fix(fix["files"], tmp_path)
    assert isinstance(files, dict), files
    assert "words[len(words)]" not in files["backend/items.py"]
    assert "ghp_" not in json.dumps(data) and "Bearer " not in json.dumps(data)
