"""Minimal streamable-HTTP MCP client used by the DataHub adapter."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode


class HttpMCPClient:
    """Call a stateless MCP server without adding an application dependency."""

    def __init__(self, endpoint: str, *, timeout_seconds: float) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self._request_id = 0
        self._initialized = False
        self._session_id: str | None = None

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _post(
        self,
        method: str,
        params: dict[str, Any] | None,
        *,
        notification: bool = False,
    ) -> dict[str, Any] | None:
        request_id = None if notification else self._next_id()
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if request_id is not None:
            payload["id"] = request_id
        if params is not None:
            payload["params"] = params
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2025-06-18",
        }
        if self._session_id is not None:
            headers["Mcp-Session-Id"] = self._session_id
        request = Request(
            self.endpoint,
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self._session_id = session_id
                raw = response.read().decode("utf-8")
                content_type = response.headers.get("Content-Type", "")
        except HTTPError as exc:
            code = (
                RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED
                if exc.code in {401, 403}
                else RefusalCode.SOURCE_DATAHUB_UNAVAILABLE
            )
            raise Refusal(
                code,
                "The DataHub MCP endpoint refused the request.",
                {"status": exc.code, "method": method},
            ) from exc
        except (URLError, TimeoutError, UnicodeError) as exc:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "The DataHub MCP endpoint was unavailable.",
                {"method": method, "error_type": type(exc).__name__},
            ) from exc
        if notification or not raw.strip():
            return None
        message = _parse_response(raw, content_type, request_id)
        if "error" in message:
            error = message["error"]
            safe_code = error.get("code") if isinstance(error, dict) else None
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "The DataHub MCP server returned a protocol error.",
                {"method": method, "protocol_error_code": safe_code},
            )
        result = message.get("result")
        if not isinstance(result, dict):
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "The DataHub MCP response did not contain an object result.",
                {"method": method},
            )
        return result

    def initialize(self) -> None:
        if self._initialized:
            return
        result = self._post(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {
                    "name": "retirement-conductor",
                    "version": "0.1.0",
                },
            },
        )
        if result is None or "serverInfo" not in result:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "The DataHub MCP server did not complete initialization.",
            )
        self._post("notifications/initialized", None, notification=True)
        self._initialized = True

    def list_tools(self) -> list[dict[str, Any]]:
        self.initialize()
        result = self._post("tools/list", {})
        tools = result.get("tools") if result is not None else None
        if not isinstance(tools, list) or not all(
            isinstance(tool, dict) for tool in tools
        ):
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "The MCP tool inventory was malformed.",
            )
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.initialize()
        result = self._post(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        if result is None:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "The MCP tool returned no result.",
                {"tool": name},
            )
        if result.get("isError") is True:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "The DataHub MCP tool failed.",
                {"tool": name},
            )
        return unwrap_tool_result(result)


def _parse_response(
    raw: str,
    content_type: str,
    request_id: int | None,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    if "text/event-stream" in content_type:
        for line in raw.splitlines():
            if not line.startswith("data:"):
                continue
            value = json.loads(line.removeprefix("data:").strip())
            if isinstance(value, dict):
                candidates.append(value)
    else:
        value = json.loads(raw)
        if isinstance(value, dict):
            candidates.append(value)
    for candidate in candidates:
        if candidate.get("id") == request_id:
            return candidate
    raise Refusal(
        RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
        "The MCP response did not match the request identifier.",
    )


def unwrap_tool_result(result: dict[str, Any]) -> Any:
    """Extract FastMCP structured output or its JSON text fallback."""

    structured = result.get("structuredContent")
    if structured is not None:
        if isinstance(structured, dict) and set(structured) == {"result"}:
            return structured["result"]
        return structured
    content = result.get("content")
    if not isinstance(content, list):
        return result
    for item in content:
        if not isinstance(item, dict) or item.get("type") not in {None, "text"}:
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return result
