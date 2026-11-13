"""Local mode of the responder (#69): incidents, fixes and the draft prod PR are
files in DEMO_OUTPUT, and the fix is written into the demo workspace. Same
methods as `GitHub`, so the responder doesn't change; nothing leaves the machine.
"""

import difflib
import hashlib
import json
import re
from pathlib import Path

from oncall.agent.github import NEEDS_HUMAN_LABEL, incident_title
from oncall.mcp_server.redact import redact

INDEX = "incidents.json"


class LocalTracker:
    def __init__(self, output: Path, workspace: Path):
        self.output = output
        self.workspace = workspace
        self.output.mkdir(parents=True, exist_ok=True)

    # --- index of incidents (incidents.json) ---------------------------------------

    def _index(self) -> list[dict]:
        path = self.output / INDEX
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, index: list[dict]) -> None:
        (self.output / INDEX).write_text(json.dumps(index, indent=1), encoding="utf-8")

    def _file(self, number: int) -> Path:
        return self.output / f"incident-{number}.md"

    def _append(self, number: int, text: str) -> None:
        with self._file(number).open("a", encoding="utf-8") as f:
            f.write("\n\n---\n\n" + redact(text) + "\n")

    # --- the GitHub-like interface -------------------------------------------------

    async def open_incident(self, alertname: str) -> dict | None:
        prefix = f"[incident] {alertname}:"
        return next(
            (
                {"number": i["number"], "title": i["title"]}
                for i in self._index()
                if i["state"] == "open" and i["title"].startswith(prefix)
            ),
            None,
        )

    async def create_incident(self, alertname: str, summary: str, body: str) -> int:
        index = self._index()
        number = max((i["number"] for i in index), default=0) + 1
        title = redact(incident_title(alertname, summary))
        index.append(
            {"number": number, "title": title, "state": "open", "labels": ["incident"]}
        )
        self._save(index)
        self._file(number).write_text(
            f"# #{number} {title}\n\nState: **open** · labels: incident\n\n{redact(body)}\n",
            encoding="utf-8",
        )
        return number

    async def comment(self, number: int, body: str) -> None:
        self._append(number, body)

    async def label(self, number: int, label: str) -> None:
        index = self._index()
        for item in index:
            if item["number"] == number and label not in item["labels"]:
                item["labels"].append(label)
        self._save(index)
        if label == NEEDS_HUMAN_LABEL:
            self._append(number, "Label: **needs-human** (Needs human on-call)")

    async def labels(self, number: int) -> list[str]:
        return next((i["labels"] for i in self._index() if i["number"] == number), [])

    async def close(self, number: int) -> None:
        index = self._index()
        for item in index:
            if item["number"] == number:
                item["state"] = "closed"
        self._save(index)
        self._append(number, "State: **closed**")

    async def commit_files(
        self, branch: str, files: dict[str, str], message: str
    ) -> str:
        """Write the fix into the workspace and save its diff; returns a short id."""
        number = _incident_number(message)
        chunks = []
        for path, content in files.items():
            target = self.workspace / path
            old = target.read_text(encoding="utf-8") if target.exists() else ""
            chunks.extend(
                difflib.unified_diff(
                    old.splitlines(),
                    content.splitlines(),
                    f"a/{path}",
                    f"b/{path}",
                    lineterm="",
                )
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        diff = redact("\n".join(chunks)) + "\n"
        (self.output / f"fix-{number}.diff").write_text(diff, encoding="utf-8")
        (self.output / f"fix-{number}.message.txt").write_text(
            redact(message), encoding="utf-8"
        )
        return "local-" + hashlib.sha256(diff.encode()).hexdigest()[:7]

    async def prod_pr(self, incident: int) -> str:
        """Write the release PR a human would review; returns its path."""
        diff_path = self.output / f"fix-{incident}.diff"
        diff = diff_path.read_text(encoding="utf-8") if diff_path.exists() else ""
        message_path = self.output / f"fix-{incident}.message.txt"
        message = (
            message_path.read_text(encoding="utf-8") if message_path.exists() else ""
        )
        path = self.output / f"prod-pr-{incident}.md"
        path.write_text(
            "# Draft PR: Release: main to prod\n\n"
            "_Local demo (#69): this file is what the responder would propose. Nothing was "
            "pushed or deployed. In the real flow the fix lands on `main` (CI, then CD to dev) "
            "and **a human reviews and merges** this PR to release it to production._\n\n"
            f"**Base:** `prod` · **Head:** `main` · **Incident:** #{incident}\n\n"
            f"## Changes\n\n```\n{message}\n```\n\n"
            f"## Diff\n\n```diff\n{diff}```\n\n"
            "Merge with **Create a merge commit**: Deploy prod then deploys the image dev ran "
            "for the head of main.\n",
            encoding="utf-8",
        )
        return path.name


def _incident_number(message: str) -> int:
    match = re.search(r"#(\d+)", message)
    return int(match.group(1)) if match else 0
