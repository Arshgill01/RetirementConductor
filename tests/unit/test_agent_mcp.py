from __future__ import annotations

import asyncio
from typing import Any, cast

from mcp.client import Client

from retirement_conductor.agent import AgentCommandRuntime
from retirement_conductor.agent_mcp import SERVER_INSTRUCTIONS, create_server


class FakeRuntime:
    def __init__(self) -> None:
        self.apply_calls: list[dict[str, Any]] = []

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


def test_mcp_server_advertises_focused_annotated_tools() -> None:
    runtime = FakeRuntime()

    async def exercise() -> None:
        server = create_server(cast(AgentCommandRuntime, runtime))
        async with Client(server) as client:
            tools = (await client.list_tools()).tools
            by_name = {tool.name: tool for tool in tools}

            assert len(tools) == 14
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
