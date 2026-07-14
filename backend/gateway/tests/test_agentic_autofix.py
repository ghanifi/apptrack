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


def _cap_transport(captured: dict, response_json: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=response_json)
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_openai_agentic_step_parses_tool_calls():
    from app.llm.openai_compat import OpenAICompatProvider
    from app.llm.base import ToolSpec
    cap = {}
    resp = {"choices": [{"finish_reason": "tool_calls", "message": {"content": "",
             "tool_calls": [{"id": "c1", "type": "function",
                             "function": {"name": "read_file", "arguments": "{\"path\": \"package.json\"}"}}]}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 4}}
    p = OpenAICompatProvider("https://api.openai.com/v1", "sk", transport=_cap_transport(cap, resp))
    tools = [ToolSpec("read_file", "oku", {"type": "object", "properties": {"path": {"type": "string"}}})]
    transcript = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hata"}]
    res = await p.agentic_step(transcript, tools, model="gpt-5-nano")
    assert res.stop_reason == "tool_calls"
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].name == "read_file"
    assert res.tool_calls[0].arguments == {"path": "package.json"}
    assert res.usage == {"input_tokens": 10, "output_tokens": 4}
    assert cap["body"]["tools"][0]["type"] == "function"
    assert cap["body"]["tools"][0]["function"]["name"] == "read_file"
    assert cap["body"]["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_openai_agentic_step_serializes_assistant_and_tool_turns():
    from app.llm.openai_compat import OpenAICompatProvider
    from app.llm.base import ToolCall, ToolSpec
    cap = {}
    resp = {"choices": [{"finish_reason": "stop", "message": {"content": "bitti", "tool_calls": []}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    p = OpenAICompatProvider("https://api.openai.com/v1", "sk", transport=_cap_transport(cap, resp))
    transcript = [
        {"role": "user", "content": "hata"},
        {"role": "assistant", "content": "", "tool_calls": [ToolCall("c1", "read_file", {"path": "a"})]},
        {"role": "tool", "tool_call_id": "c1", "content": "dosya içeriği"},
    ]
    res = await p.agentic_step(transcript, [ToolSpec("read_file", "d", {})], model="m")
    assert res.text == "bitti"
    msgs = cap["body"]["messages"]
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["tool_calls"][0]["function"]["name"] == "read_file"
    assert json.loads(msgs[1]["tool_calls"][0]["function"]["arguments"]) == {"path": "a"}
    assert msgs[2] == {"role": "tool", "tool_call_id": "c1", "content": "dosya içeriği"}
