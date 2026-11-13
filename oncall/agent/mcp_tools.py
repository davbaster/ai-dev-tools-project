"""The MCP server's tools (#16), seen from the responder."""

from contextlib import asynccontextmanager

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MAX_RESULT_CHARS = 8000


class MCPTools:
    """Calls the MCP server over HTTP with the bearer token."""

    def __init__(self, url: str, token: str):
        self.url = url
        self._headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "para-luego-oncall",
        }

    @asynccontextmanager
    async def _session(self):
        async with (
            httpx2.AsyncClient(headers=self._headers, timeout=120) as http,
            streamable_http_client(self.url, http_client=http) as streams,
            ClientSession(streams[0], streams[1]) as session,
        ):
            await session.initialize()
            yield session

    async def list_tools(self) -> list[dict]:
        async with self._session() as session:
            tools = (await session.list_tools()).tools
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.input_schema,
            }
            for t in tools
        ]

    async def call(self, name: str, arguments: dict) -> str:
        async with self._session() as session:
            result = await session.call_tool(name, arguments)
        text = "\n".join(getattr(c, "text", "") for c in result.content)
        if result.is_error:
            text = "ERROR: " + text
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + "\n[truncated]"
        return text
