"""OpenAI-compatible Chat Completions with tool calling, over httpx."""

import httpx


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
