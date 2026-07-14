"""LLM sağlayıcı tablosu + config→adaptör çözümü. Model id'leri VARSAYILAN — kullanıcı override eder."""
from app.llm.openai_compat import OpenAICompatProvider
from app.llm.anthropic import AnthropicProvider

PROVIDERS: dict[str, dict] = {
    "openai": {"label": "OpenAI", "base_url": "https://api.openai.com/v1",
               "key_name": "OPENAI_API_KEY", "default_model": "gpt-5-nano",
               "free": False, "kind": "openai_compat"},
    "openrouter": {"label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1",
                   "key_name": "OPENROUTER_API_KEY", "default_model": "qwen/qwen3-coder:free",
                   "free": True, "kind": "openai_compat",
                   "extra_headers": {"HTTP-Referer": "https://apptrack.dev", "X-Title": "AppTrack"}},
    "nvidia": {"label": "NVIDIA", "base_url": "https://integrate.api.nvidia.com/v1",
               "key_name": "NVIDIA_API_KEY", "default_model": "meta/llama-3.3-70b-instruct",
               "free": True, "kind": "openai_compat"},
    "gemini": {"label": "Google Gemini",
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "key_name": "GEMINI_API_KEY", "default_model": "gemini-2.5-flash-lite",
               "free": True, "kind": "openai_compat"},
    "anthropic": {"label": "Anthropic Claude", "base_url": "https://api.anthropic.com/v1",
                  "key_name": "ANTHROPIC_API_KEY", "default_model": "claude-haiku-4-5",
                  "free": False, "kind": "anthropic"},
}


def build_provider(provider_id: str, api_key: str, transport=None):
    spec = PROVIDERS.get(provider_id)
    if not spec:
        raise ValueError(f"Bilinmeyen LLM sağlayıcı: {provider_id}")
    if spec["kind"] == "anthropic":
        return AnthropicProvider(api_key, base_url=spec["base_url"], transport=transport)
    return OpenAICompatProvider(spec["base_url"], api_key,
                                extra_headers=spec.get("extra_headers"), transport=transport)
