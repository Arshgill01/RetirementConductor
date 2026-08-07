from __future__ import annotations

from scripts.run_agent_acceptance import completed_tool_calls


def test_completed_tool_calls_excludes_started_and_non_mcp_items() -> None:
    events = [
        {
            "type": "item.started",
            "item": {
                "type": "mcp_tool_call",
                "tool": "inspect_retirement_campaign",
            },
        },
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "working"},
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "tool": "inspect_retirement_campaign",
                "status": "completed",
            },
        },
    ]

    assert [call["tool"] for call in completed_tool_calls(events)] == [
        "inspect_retirement_campaign"
    ]
