"""Loopback-only HTTP boundary for the Retirement Workbench."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from retirement_conductor.errors import Refusal
from retirement_conductor.store import CampaignStore
from retirement_conductor.workbench import build_workbench_view

ActionRunner = Callable[[str], Mapping[str, Any]]


class WorkbenchApplication:
    """Read canonical state and dispatch the two explicitly enabled operations."""

    def __init__(
        self,
        *,
        store: Path,
        writer_id: str,
        campaign_id: str,
        actions_enabled: bool,
        action_runner: ActionRunner,
    ) -> None:
        self.store = store
        self.writer_id = writer_id
        self.campaign_id = campaign_id
        self.actions_enabled = actions_enabled
        self.action_runner = action_runner

    def view(self) -> dict[str, Any]:
        with CampaignStore(self.store, writer_id=self.writer_id) as store:
            manifest = store.materialize(self.campaign_id)
            events = store.events(self.campaign_id)
        return build_workbench_view(
            manifest,
            events,
            actions_enabled=self.actions_enabled,
        )

    def run(self, operation: str) -> dict[str, Any]:
        if not self.actions_enabled:
            raise Refusal(
                "AUTH_APPROVAL_MISSING",
                "Workbench actions were not enabled when this local server started.",
            )
        if operation not in {"inventory", "reconcile"}:
            raise Refusal(
                "SCOPE_TARGET_NOT_ALLOWED",
                "The Workbench exposes only inventory and reconciliation operations.",
            )
        result = dict(self.action_runner(operation))
        if int(result.get("command_exit_code", 0)) != 0:
            raise Refusal(
                str(result.get("refusal_code") or "RUNTIME_COMMAND_FAILED"),
                str(result.get("message") or "The campaign operation was refused."),
            )
        return {"result": result, "view": self.view()}


def _handler(
    application: WorkbenchApplication,
    allowed_origins: frozenset[str],
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "RetirementWorkbench/0.1"

        def _origin(self) -> str | None:
            value = self.headers.get("Origin")
            return value.rstrip("/") if value else None

        def _origin_allowed(self) -> bool:
            origin = self._origin()
            return origin is None or origin in allowed_origins

        def _send(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
            body = json.dumps(
                payload,
                allow_nan=False,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            origin = self._origin()
            if origin in allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            if not self._origin_allowed():
                self._send(HTTPStatus.FORBIDDEN, {"error": "Origin is not allowed."})
                return
            self.send_response(HTTPStatus.NO_CONTENT)
            origin = self._origin()
            if origin in allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, X-Retirement-Conductor-Action",
            )
            self.send_header("Access-Control-Max-Age", "600")
            self.end_headers()

        def do_GET(self) -> None:
            if not self._origin_allowed():
                self._send(HTTPStatus.FORBIDDEN, {"error": "Origin is not allowed."})
                return
            path = urlparse(self.path).path
            try:
                if path == "/api/health":
                    self._send(
                        HTTPStatus.OK,
                        {
                            "result": "OK",
                            "campaign_id": application.campaign_id,
                            "mode": (
                                "live-local"
                                if application.actions_enabled
                                else "read-only"
                            ),
                        },
                    )
                elif path == "/api/workbench":
                    self._send(HTTPStatus.OK, application.view())
                else:
                    self._send(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            except Refusal as refusal:
                self._send(HTTPStatus.CONFLICT, refusal.as_dict())

        def do_POST(self) -> None:
            if not self._origin_allowed():
                self._send(HTTPStatus.FORBIDDEN, {"error": "Origin is not allowed."})
                return
            path = urlparse(self.path).path
            if path != "/api/workbench/action":
                self._send(HTTPStatus.NOT_FOUND, {"error": "Not found."})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 2 or size > 256:
                    raise Refusal(
                        "SPEC_SCHEMA_INVALID",
                        "Workbench action bodies must be small JSON objects.",
                    )
                payload = json.loads(self.rfile.read(size))
                operation = str(
                    payload.get("operation") if isinstance(payload, dict) else ""
                )
                if self.headers.get("X-Retirement-Conductor-Action") != operation:
                    raise Refusal(
                        "AUTH_APPROVAL_MISSING",
                        "The action confirmation header must match the requested "
                        "operation.",
                    )
                self._send(HTTPStatus.OK, application.run(operation))
            except (ValueError, json.JSONDecodeError):
                self._send(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "The request body must be valid JSON."},
                )
            except Refusal as refusal:
                self._send(HTTPStatus.CONFLICT, refusal.as_dict())

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def serve_workbench(
    application: WorkbenchApplication,
    *,
    host: str,
    port: int,
    allowed_origins: Sequence[str],
) -> None:
    """Serve until interrupted; refuse exposure beyond the local machine."""

    if host != "127.0.0.1":
        raise Refusal(
            "SCOPE_TARGET_NOT_ALLOWED",
            "The Workbench server may bind only to 127.0.0.1.",
        )
    normalized_origins = frozenset(origin.rstrip("/") for origin in allowed_origins)
    for origin in normalized_origins:
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "127.0.0.1",
            "localhost",
        }:
            raise Refusal(
                "SCOPE_TARGET_NOT_ALLOWED",
                "Workbench browser origins must be loopback HTTP origins.",
            )
    server = ThreadingHTTPServer(
        (host, port),
        _handler(application, normalized_origins),
    )
    try:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return
    finally:
        server.server_close()
