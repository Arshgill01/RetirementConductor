from __future__ import annotations

import json
from pathlib import Path

from retirement_conductor.canonical import verify_digest
from scripts.run_agent_acceptance import completed_tool_calls

ROOT = Path(__file__).resolve().parents[2]


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


def test_public_agent_acceptance_is_digest_bound_and_failure_closed() -> None:
    evidence = json.loads(
        (ROOT / "artifacts/public/agent/agent-acceptance.json").read_text(
            encoding="utf-8"
        )
    )

    verify_digest(evidence, "agent_acceptance_digest")
    assert evidence["observed_campaign"]["decision"] == "UNSAFE"
    assert evidence["observed_campaign"]["blocker_codes"] == [
        "POLICY_CONSUMER_OPAQUE",
        "RECONCILIATION_NEW_CONSUMER",
    ]
    assert evidence["trace"]["shell_call_count"] == 0
    assert set(evidence["trace"]["tool_order"]) == {
        "inspect_retirement_campaign",
        "explain_retirement_campaign",
    }
    assert evidence["acceptance"]["producer_action_attempted"] is False
