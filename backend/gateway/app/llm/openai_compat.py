"""OpenAI-uyumlu /chat/completions adaptörü — OpenAI, OpenRouter, NVIDIA, Gemini-compat.
Yalnız base_url + api_key (+ ops. header) değişir. Anthropic native ayrı adaptörde."""
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
