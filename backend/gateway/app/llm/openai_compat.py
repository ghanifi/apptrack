"""OpenAI-uyumlu /chat/completions adaptörü — OpenAI, OpenRouter, NVIDIA, Gemini-compat.
Yalnız base_url + api_key (+ ops. header) değişir. Anthropic native ayrı adaptörde."""
import json

import httpx

from app.llm.base import LLMMessage, LLMResult, LLMError


class OpenAICompatProvider:
    def __init__(self, base_url: str, api_key: str, extra_headers: dict | None = None, transport=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.extra_headers = extra_headers or {}
        self._transport = transport

    async def complete(self, messages: list[LLMMessage], model: str,
                       max_tokens: int = 1024, temperature: float = 0.2) -> LLMResult:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                   **self.extra_headers}
        body = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=60.0, transport=self._transport) as c:
            resp = await c.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
        if resp.status_code >= 400:
            raise LLMError(f"LLM sağlayıcı hatası ({resp.status_code}): {resp.text[:300]}",
                           status=resp.status_code)
        data = resp.json()
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        usage = data.get("usage") or {}
        return LLMResult(
            text=text, model=data.get("model", model),
            usage={"input_tokens": usage.get("prompt_tokens", 0),
                   "output_tokens": usage.get("completion_tokens", 0)},
        )

    async def agentic_step(self, transcript: list[dict], tools: list, model: str,
                           max_tokens: int = 4000, temperature: float = 0.2):
        """Tool-calling turu: transcript'i OpenAI formatına serialize et, tools ilet, tool_calls parse et."""
        from app.llm.base import ToolCall, AgenticResult
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                   **self.extra_headers}
        messages = []
        for e in transcript:
            if e["role"] == "assistant" and e.get("tool_calls"):
                messages.append({"role": "assistant", "content": e.get("content") or "",
                                 "tool_calls": [{"id": tc.id, "type": "function",
                                     "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
                                     for tc in e["tool_calls"]]})
            elif e["role"] == "tool":
                messages.append({"role": "tool", "tool_call_id": e["tool_call_id"],
                                 "content": e["content"]})
            else:
                messages.append({"role": e["role"], "content": e["content"]})
        body = {"model": model, "messages": messages, "max_tokens": max_tokens,
                "temperature": temperature, "tool_choice": "auto",
                "tools": [{"type": "function",
                           "function": {"name": t.name, "description": t.description,
                                        "parameters": t.parameters}} for t in tools]}
        async with httpx.AsyncClient(timeout=90.0, transport=self._transport) as c:
            resp = await c.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
        if resp.status_code >= 400:
            raise LLMError(f"LLM agentic hatası ({resp.status_code}): {resp.text[:300]}",
                           status=resp.status_code)
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {}) or {}
        calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {}) or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except (TypeError, ValueError):
                args = {}
            calls.append(ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args))
        usage = data.get("usage") or {}
        return AgenticResult(
            text=msg.get("content") or "", tool_calls=calls,
            usage={"input_tokens": usage.get("prompt_tokens", 0),
                   "output_tokens": usage.get("completion_tokens", 0)},
            stop_reason=choice.get("finish_reason", ""))

    async def list_models(self) -> list[dict]:
        """Sağlayıcının OpenAI-uyumlu /models listesi → [{id, free}]. Canlı; anahtar gerekir.
        free: OpenRouter pricing=0 veya ':free' son eki → True; aksi belirsizse None."""
        headers = {"Authorization": f"Bearer {self.api_key}", **self.extra_headers}
        async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as c:
            resp = await c.get(f"{self.base_url}/models", headers=headers)
        if resp.status_code >= 400:
            raise LLMError(f"Model listesi alınamadı ({resp.status_code}): {resp.text[:200]}",
                           status=resp.status_code)
        out = []
        for m in resp.json().get("data", []) or []:
            mid = m.get("id")
            if not mid:
                continue
            if mid.startswith("models/"):  # Gemini compat /models 'models/' önekiyle döner; completion temiz id ister
                mid = mid[len("models/"):]
            free = None
            pricing = m.get("pricing")
            if isinstance(pricing, dict):
                try:
                    free = (float(pricing.get("prompt", 1) or 0) == 0
                            and float(pricing.get("completion", 1) or 0) == 0)
                except (TypeError, ValueError):
                    free = None
            if mid.endswith(":free"):
                free = True
            out.append({"id": mid, "free": free})
        return out
