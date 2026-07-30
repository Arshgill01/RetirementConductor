"""Secret-safe HTTP and GraphQL access to DataHub GMS."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode


class DataHubGraphClient:
    """Small GMS client for health, capability, and pagination fallbacks."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None,
        timeout_seconds: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> Any:
        headers = {"Accept": "application/json"}
        data = None
        method = "GET"
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, separators=(",", ":")).encode()
            method = "POST"
        if self.token is not None:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            code = (
                RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED
                if exc.code in {401, 403}
                else RefusalCode.SOURCE_DATAHUB_UNAVAILABLE
            )
            raise Refusal(
                code,
                "The DataHub GMS endpoint refused the request.",
                {"path": path, "status": exc.code},
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "The DataHub GMS endpoint was unavailable.",
                {"path": path, "error_type": type(exc).__name__},
            ) from exc
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (UnicodeError, json.JSONDecodeError):
            return {"response_text": raw.decode("utf-8", errors="replace")[:200]}

    def health(self) -> Any:
        return self._request("/health")

    def server_config(self) -> Any:
        return self._request("/config")

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = self._request(
            "/api/graphql",
            body={"query": query, "variables": variables},
        )
        if not isinstance(response, dict):
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "The DataHub GraphQL response was not an object.",
            )
        errors = response.get("errors")
        if errors:
            safe_messages = [
                str(item.get("message", "GraphQL error"))[:240]
                for item in errors
                if isinstance(item, dict)
            ]
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "DataHub GraphQL returned an error.",
                {"messages": safe_messages},
            )
        data = response.get("data")
        if not isinstance(data, dict):
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "The DataHub GraphQL response had no data object.",
            )
        return data
