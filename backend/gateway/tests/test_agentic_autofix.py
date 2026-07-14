"""Agentic autofix testleri — nötr tipler, adaptör agentic_step, orkestratör, doğrulayıcılar."""
import json
import httpx
import pytest

from app.llm.base import ToolSpec, ToolCall, AgenticResult


def test_neutral_types_construct():
    ts = ToolSpec(name="read_file", description="oku", parameters={"type": "object"})
    tc = ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})
    ar = AgenticResult(text="", tool_calls=[tc], usage={"input_tokens": 3}, stop_reason="tool_calls")
    assert ts.name == "read_file" and ts.parameters == {"type": "object"}
    assert tc.arguments["path"] == "a.txt"
    assert ar.tool_calls[0].name == "read_file" and ar.stop_reason == "tool_calls"
