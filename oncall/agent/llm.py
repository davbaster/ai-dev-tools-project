"""OpenAI-compatible Chat Completions with tool calling, over httpx."""

import json
from pathlib import Path

import httpx

from oncall.mcp_server.redact import redact_value


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        reasoning_effort: str = "",
        transport=None,
    ):
        self.model = model
        self._api_key = api_key
        # OpenAI's reasoning models only accept function tools on Chat Completions
        # with reasoning_effort "none" (found in #17's QA). Empty = not sent, for
        # providers that don't know the parameter.
        self._reasoning_effort = reasoning_effort
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=120, transport=transport
        )

    async def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        """Return the assistant message (content and/or tool_calls)."""
        if not self._api_key:
            raise LLMError("LLM_API_KEY is not set")
        body = {"model": self.model, "messages": messages, "tools": tools}
        if self._reasoning_effort:
            body["reasoning_effort"] = self._reasoning_effort
        try:
            response = await self._client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=body,
            )
        except httpx.HTTPError as error:
            raise LLMError(f"LLM is unreachable ({type(error).__name__})") from error
        if response.status_code >= 400:
            raise LLMError(f"LLM error {response.status_code}: {response.text[:300]}")
        return response.json()["choices"][0]["message"]


REPLAY_NOTE = (
    "replayed investigation: no LLM_API_KEY, so the model's choices come from a "
    "recorded real run; the tools, checks and fix run for real on this machine."
)
OUT_OF_DATE = (
    "replay out of date: a recorded step no longer applies to this code. Record it "
    "again with RESPONDER_RECORD and an LLM_API_KEY"
)


class ReplayLLM:
    """Plays back the assistant messages of a recorded run, in order (#69)."""

    note = REPLAY_NOTE

    def __init__(self, path: Path):
        self.path = path
        self._messages: list[dict] | None = None
        self._next = 0

    def _load(self) -> list[dict]:
        if self._messages is None:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._messages = data["messages"]
            self._next = 0
        return self._messages

    async def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        recorded = self._load()
        # Si el último paso grabado falló acá (otro código), no se improvisa.
        last_tools = [m for m in messages if m.get("role") == "tool"][-3:]
        if any(
            str(m.get("content", "")).startswith(("REFUSED", "CHECKS FAILED"))
            for m in last_tools
        ):
            raise LLMError(OUT_OF_DATE)
        if self._next >= len(recorded):
            raise LLMError("replay finished without propose_fix or escalate")
        message = recorded[self._next]
        self._next += 1
        return message

    def restart(self) -> None:
        """Each new incident replays from the start."""
        self._messages = None


class RecordingLLM:
    """Wraps the real LLM and saves its messages (redacted) after every call."""

    def __init__(self, llm: LLM, path: Path):
        self.llm = llm
        self.path = path
        self.messages: list[dict] = []

    @property
    def note(self) -> str:
        return ""

    async def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        message = await self.llm.chat(messages, tools)
        self.messages.append(
            {k: v for k, v in message.items() if k in ("role", "content", "tool_calls")}
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {"model": self.llm.model, "messages": redact_value(self.messages)},
                indent=1,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return message
