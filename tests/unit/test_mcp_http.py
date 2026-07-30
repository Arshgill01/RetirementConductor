from __future__ import annotations

from retirement_conductor.mcp_http import unwrap_tool_result


def test_unwrap_prefers_structured_content() -> None:
    result = unwrap_tool_result(
        {
            "structuredContent": {"total": 1},
            "content": [{"type": "text", "text": '{"total":2}'}],
        }
    )
    assert result == {"total": 1}


def test_unwrap_parses_json_text_fallback() -> None:
    result = unwrap_tool_result({"content": [{"type": "text", "text": '{"total":2}'}]})
    assert result == {"total": 2}
