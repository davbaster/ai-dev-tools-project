"""The few GitHub REST calls the responder needs. Everything it posts goes
through redaction. Commits go through the Git Data API (no `git` here)."""

import httpx

from oncall.mcp_server.redact import redact

API = "https://api.github.com"
INCIDENT_LABEL = "incident"
NEEDS_HUMAN_LABEL = "needs-human"


def incident_title(alertname: str, summary: str) -> str:
    return f"[incident] {alertname}: {summary}"[:200]


class GitHubError(RuntimeError):
    pass


class GitHub:
    def __init__(self, token: str, repository: str, transport=None):
        self.repo = repository
        self._client = httpx.AsyncClient(
            base_url=API,
            timeout=30,
            transport=transport,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "para-luego-oncall",
            },
        )

    async def _call(self, method: str, path: str, **kwargs):
        response = await self._client.request(
            method, f"/repos/{self.repo}{path}", **kwargs
        )
        if response.status_code >= 400:
            # Nunca el token: solo método, ruta y el mensaje de GitHub.
            message = redact(response.text[:300])
            raise GitHubError(
                f"GitHub {method} {path} -> {response.status_code}: {message}"
            )
        return response.json() if response.content else None

    async def open_incident(self, alertname: str) -> dict | None:
        issues = await self._call(
            "GET",
            "/issues",
            params={"labels": INCIDENT_LABEL, "state": "open", "per_page": 50},
        )
        prefix = f"[incident] {alertname}:"
        return next((i for i in issues if i["title"].startswith(prefix)), None)

    async def create_incident(self, alertname: str, summary: str, body: str) -> int:
        issue = await self._call(
            "POST",
            "/issues",
            json={
                "title": redact(incident_title(alertname, summary)),
                "body": redact(body),
                "labels": [INCIDENT_LABEL],
            },
        )
        return issue["number"]

    async def comment(self, number: int, body: str) -> None:
        await self._call(
            "POST", f"/issues/{number}/comments", json={"body": redact(body)}
        )

    async def label(self, number: int, label: str) -> None:
        await self._call("POST", f"/issues/{number}/labels", json={"labels": [label]})

    async def labels(self, number: int) -> list[str]:
        issue = await self._call("GET", f"/issues/{number}")
        return [label["name"] for label in issue.get("labels", [])]

    async def close(self, number: int) -> None:
        await self._call("PATCH", f"/issues/{number}", json={"state": "closed"})

    async def commit_files(
        self, branch: str, files: dict[str, str], message: str
    ) -> str:
        """One commit on branch with these whole-file contents; returns its SHA."""
        ref = await self._call("GET", f"/git/ref/heads/{branch}")
        parent = ref["object"]["sha"]
        base_tree = (await self._call("GET", f"/git/commits/{parent}"))["tree"]["sha"]
        tree = await self._call(
            "POST",
            "/git/trees",
            json={
                "base_tree": base_tree,
                "tree": [
                    {"path": path, "mode": "100644", "type": "blob", "content": content}
                    for path, content in files.items()
                ],
            },
        )
        commit = await self._call(
            "POST",
            "/git/commits",
            json={"message": redact(message), "tree": tree["sha"], "parents": [parent]},
        )
        await self._call(
            "PATCH", f"/git/refs/heads/{branch}", json={"sha": commit["sha"]}
        )
        return commit["sha"]

    async def prod_pr(self, incident: int) -> str:
        """Open (or reuse) the PR main -> prod and link the incident; returns its URL."""
        owner = self.repo.split("/")[0]
        open_prs = await self._call(
            "GET",
            "/pulls",
            params={"base": "prod", "head": f"{owner}:main", "state": "open"},
        )
        if open_prs:
            pr = open_prs[0]
            await self.comment(
                pr["number"], f"Includes the fix for incident #{incident}."
            )
            return pr["html_url"]
        pr = await self._call(
            "POST",
            "/pulls",
            json={
                "title": "Release: main to prod",
                "head": "main",
                "base": "prod",
                "body": (
                    f"Release to prod, including the on-call fix for #{incident}. "
                    "Merge with **Create a merge commit**: Deploy prod then deploys "
                    "the image dev ran for the head of main. Opened by the on-call responder."
                ),
            },
        )
        return pr["html_url"]
