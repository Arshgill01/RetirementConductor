from __future__ import annotations

import asyncio
from typing import Any, cast

from mcp.client import Client

from retirement_conductor.agent import AgentCommandRuntime
from retirement_conductor.agent_mcp import SERVER_INSTRUCTIONS, create_server


class FakeRuntime:
    def __init__(self) -> None:
        self.apply_calls: list[dict[str, Any]] = []
        self.watch_calls: list[str] = []

    def inspect_campaign(self, campaign_id: str) -> dict[str, Any]:
        return {
            "result": "OK",
            "command_exit_code": 0,
            "view": {
                "campaign": {"id": campaign_id},
                "decision": "UNSAFE",
                "blockers": [{"code": "POLICY_CONSUMER_OPAQUE"}],
            },
            "manifest": {},
        }

    def git_dbt_apply(
        self,
        campaign_id: str,
        *,
        confirmed_plan_digest: str,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        self.apply_calls.append(
            {
                "campaign_id": campaign_id,
                "confirmed_plan_digest": confirmed_plan_digest,
                "occurred_at": occurred_at,
            }
        )
        return {
            "result": "REFUSED",
            "refusal_code": "AUTH_APPROVAL_MISSING",
            "message": "A human approval is required.",
            "command_exit_code": 2,
        }

    def inspect_retirement_lease(
        self,
        campaign_id: str,
        *,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        return {
            "result": "OK",
            "lease": {
                "campaign_id": campaign_id,
                "status": "ISSUED",
                "observed_at": observed_at,
            },
            "command_exit_code": 0,
        }

    def reconcile_retirement_lease_now(self, campaign_id: str) -> dict[str, Any]:
        self.watch_calls.append(campaign_id)
        return {
            "result": "REVERSED",
            "lease": {"status_before": "ISSUED", "status_after": "INVALIDATED"},
            "command_exit_code": 3,
        }


def test_mcp_server_advertises_focused_annotated_tools() -> None:
    runtime = FakeRuntime()

    async def exercise() -> None:
        server = create_server(cast(AgentCommandRuntime, runtime))
        async with Client(server) as client:
            tools = (await client.list_tools()).tools
            by_name = {tool.name: tool for tool in tools}

            assert len(tools) == 16
            assert by_name["inspect_retirement_campaign"].annotations is not None
            assert (
                by_name["inspect_retirement_campaign"].annotations.read_only_hint
                is True
            )
            assert by_name["apply_git_dbt_migration"].annotations is not None
            assert (
                by_name["apply_git_dbt_migration"].annotations.destructive_hint is True
            )
            assert "human records authorization outside this server" in (
                SERVER_INSTRUCTIONS
            )
            assert (
                "plan"
                not in by_name["execute_retirement_gate"].input_schema["properties"]
            )
            description = by_name["prepare_producer_retirement_plan"].description
            assert description is not None
            assert "15 minutes" in description
            assert set(
                by_name["get_human_authorization_instructions"].input_schema[
                    "properties"
                ]
            ) == {"campaign_id"}
            assert set(
                by_name["prepare_producer_retirement_plan"].input_schema["properties"]
            ) == {"campaign_id"}
            assert by_name["inspect_retirement_lease"].annotations is not None
            assert (
                by_name["inspect_retirement_lease"].annotations.read_only_hint is True
            )
            assert by_name["reconcile_retirement_lease_now"].annotations is not None
            assert (
                by_name["reconcile_retirement_lease_now"].annotations.open_world_hint
                is True
            )

    asyncio.run(exercise())


def test_mcp_server_exposes_readiness_reversal_as_a_safety_result() -> None:
    runtime = FakeRuntime()

    async def exercise() -> None:
        server = create_server(cast(AgentCommandRuntime, runtime))
        async with Client(server) as client:
            status = await client.call_tool(
                "inspect_retirement_lease",
                {
                    "campaign_id": "ret-orders",
                    "observed_at": "2026-08-09T12:00:00Z",
                },
            )
            watched = await client.call_tool(
                "reconcile_retirement_lease_now",
                {"campaign_id": "ret-orders"},
            )

            assert status.structured_content is not None
            assert status.structured_content["lease"]["status"] == "ISSUED"
            assert watched.structured_content is not None
            assert watched.structured_content["result"] == "REVERSED"
            assert watched.structured_content["command_exit_code"] == 3
            assert runtime.watch_calls == ["ret-orders"]

    asyncio.run(exercise())


def test_mcp_server_preserves_structured_refusal() -> None:
    runtime = FakeRuntime()

    async def exercise() -> None:
        server = create_server(cast(AgentCommandRuntime, runtime))
        async with Client(server) as client:
            result = await client.call_tool(
                "apply_git_dbt_migration",
                {
                    "campaign_id": "ret-orders",
                    "confirmed_plan_digest": "sha256:" + ("a" * 64),
                },
            )

            assert result.structured_content is not None
            assert result.structured_content["refusal_code"] == "AUTH_APPROVAL_MISSING"
            assert runtime.apply_calls == [
                {
                    "campaign_id": "ret-orders",
                    "confirmed_plan_digest": "sha256:" + ("a" * 64),
                    "occurred_at": None,
                }
            ]

    asyncio.run(exercise())
