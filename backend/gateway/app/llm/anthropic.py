"""Anthropic native Messages adaptörü. system mesajları ayrı `system` alanına taşınır."""
import httpx

from app.llm.base import LLMMessage, LLMResult, LLMError

_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider:
    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com/v1", transport=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._transport = transport

    async def complete(self, messages: list[LLMMessage], model: str,
                       max_tokens: int = 1024, temperature: float = 0.2) -> LLMResult:
        system = "\n".join(m.content for m in messages if m.role == "system") or None
        convo = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        headers = {"x-api-key": self.api_key, "anthropic-version": _ANTHROPIC_VERSION,
                   "Content-Type": "application/json"}
        body = {"model": model, "max_tokens": max_tokens, "temperature": temperature, "messages": convo}
        if system:
            body["system"] = system
        async with httpx.AsyncClient(timeout=60.0, transport=self._transport) as c:
            resp = await c.post(f"{self.base_url}/messages", headers=headers, json=body)
        if resp.status_code >= 400:
            raise LLMError(f"Anthropic hatası ({resp.status_code}): {resp.text[:300]}",
                           status=resp.status_code)
        data = resp.json()
        parts = data.get("content") or []
        text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        usage = data.get("usage") or {}
        return LLMResult(text=text, model=data.get("model", model),
                         usage={"input_tokens": usage.get("input_tokens", 0),
                                "output_tokens": usage.get("output_tokens", 0)})

    async def list_models(self) -> list[dict]:
        """Anthropic /models → [{id, free}]. Tümü ücretli (free=False)."""
        headers = {"x-api-key": self.api_key, "anthropic-version": _ANTHROPIC_VERSION}
        async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as c:
            resp = await c.get(f"{self.base_url}/models", headers=headers)
        if resp.status_code >= 400:
            raise LLMError(f"Model listesi alınamadı ({resp.status_code}): {resp.text[:200]}",
                           status=resp.status_code)
        return [{"id": m["id"], "free": False} for m in resp.json().get("data", []) or [] if m.get("id")]
