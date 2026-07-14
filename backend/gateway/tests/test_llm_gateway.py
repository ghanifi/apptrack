"""LLM ağ geçidi testleri — httpx MockTransport ile (gerçek sağlayıcıya gitmez)."""
import json
import httpx
import pytest

from app.llm.base import LLMMessage, LLMError
from app.llm.openai_compat import OpenAICompatProvider
from app.llm.anthropic import AnthropicProvider
from app.llm import registry


def _openai_transport(captured: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "model": "gpt-5-nano",
            "choices": [{"message": {"role": "assistant", "content": "merhaba"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        })
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_openai_compat_happy_path():
    cap = {}
    p = OpenAICompatProvider("https://api.openai.com/v1", "sk-test", transport=_openai_transport(cap))
    res = await p.complete([LLMMessage("user", "selam")], model="gpt-5-nano", max_tokens=16)
    assert res.text == "merhaba"
    assert res.model == "gpt-5-nano"
    assert res.usage == {"input_tokens": 5, "output_tokens": 2}
    assert cap["url"] == "https://api.openai.com/v1/chat/completions"
    assert cap["auth"] == "Bearer sk-test"
    assert cap["body"]["messages"][0] == {"role": "user", "content": "selam"}
    assert cap["body"]["max_tokens"] == 16


@pytest.mark.asyncio
async def test_openai_compat_extra_headers():
    cap = {}
    def handler(req):
        cap["ref"] = req.headers.get("http-referer")
        return httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": "x"}}], "usage": {}})
    p = OpenAICompatProvider("https://openrouter.ai/api/v1", "k",
                             extra_headers={"HTTP-Referer": "https://apptrack.dev"},
                             transport=httpx.MockTransport(handler))
    await p.complete([LLMMessage("user", "hi")], model="m")
    assert cap["ref"] == "https://apptrack.dev"


@pytest.mark.asyncio
async def test_openai_compat_401_raises_llmerror():
    def handler(req):
        return httpx.Response(401, json={"error": {"message": "bad key"}})
    p = OpenAICompatProvider("https://api.openai.com/v1", "bad", transport=httpx.MockTransport(handler))
    with pytest.raises(LLMError) as exc:
        await p.complete([LLMMessage("user", "hi")], model="m")
    assert exc.value.status == 401


@pytest.mark.asyncio
async def test_anthropic_native_parse_and_headers():
    cap = {}
    def handler(req: httpx.Request):
        cap["url"] = str(req.url)
        cap["ver"] = req.headers.get("anthropic-version")
        cap["key"] = req.headers.get("x-api-key")
        cap["body"] = json.loads(req.content)
        return httpx.Response(200, json={
            "model": "claude-haiku-4-5",
            "content": [{"type": "text", "text": "yanit"}],
            "usage": {"input_tokens": 7, "output_tokens": 3},
        })
    p = AnthropicProvider("ak-test", transport=httpx.MockTransport(handler))
    res = await p.complete([LLMMessage("system", "sen bir asistansın"), LLMMessage("user", "selam")],
                           model="claude-haiku-4-5", max_tokens=32)
    assert res.text == "yanit"
    assert res.usage == {"input_tokens": 7, "output_tokens": 3}
    assert cap["url"] == "https://api.anthropic.com/v1/messages"
    assert cap["ver"] == "2023-06-01"
    assert cap["key"] == "ak-test"
    assert cap["body"]["system"] == "sen bir asistansın"
    assert cap["body"]["messages"] == [{"role": "user", "content": "selam"}]
    assert cap["body"]["max_tokens"] == 32


def test_registry_build_openai_compat_and_defaults():
    assert registry.PROVIDERS["gemini"]["default_model"] == "gemini-2.5-flash-lite"
    assert registry.PROVIDERS["openrouter"]["free"] is True
    p = registry.build_provider("nvidia", "nvapi-x")
    from app.llm.openai_compat import OpenAICompatProvider as OC
    assert isinstance(p, OC)
    assert p.base_url == "https://integrate.api.nvidia.com/v1"


def test_registry_build_anthropic():
    p = registry.build_provider("anthropic", "ak")
    assert isinstance(p, AnthropicProvider)


def test_registry_unknown_provider_raises():
    with pytest.raises(ValueError):
        registry.build_provider("bogus", "k")
