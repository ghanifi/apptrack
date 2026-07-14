"""build-autofix LLM fallback — sahte LLM sağlayıcı ile şema parse + opt-in davranışı."""
import pytest

from app import build_autofix
from app.llm.base import LLMResult


class _FakeProvider:
    def __init__(self, text): self._text = text
    async def complete(self, messages, model, max_tokens=1024, temperature=0.2):
        return LLMResult(text=self._text, model="fake", usage={})


REPO_CTX = {"tree": ["android/build.gradle", "pubspec.yaml"],
            "files": {"android/build.gradle": "minSdkVersion 19"}}


@pytest.mark.asyncio
async def test_llm_propose_patch_parses_json():
    text = '```json\n{"path": "android/build.gradle", "new_content": "minSdkVersion 21", "summary": "minSdk yükselt"}\n```'
    plan = await build_autofix.llm_propose_patch(_FakeProvider(text), "hata logu", REPO_CTX, "flutter")
    assert plan == {"path": "android/build.gradle", "new_content": "minSdkVersion 21", "summary": "minSdk yükselt"}


@pytest.mark.asyncio
async def test_llm_propose_patch_bad_schema_returns_none():
    plan = await build_autofix.llm_propose_patch(_FakeProvider("özür dilerim, düzeltemiyorum"), "log", REPO_CTX, None)
    assert plan is None


@pytest.mark.asyncio
async def test_llm_propose_patch_path_not_in_repo_returns_none():
    text = '{"path": "yok/olmayan.txt", "new_content": "x", "summary": "y"}'
    plan = await build_autofix.llm_propose_patch(_FakeProvider(text), "log", REPO_CTX, None)
    assert plan is None  # LLM var olmayan dosya uydurdu → reddet


def test_transform_llm_replace_returns_new_content():
    plan = {"kind": "llm_replace", "new_content": "yeni içerik"}
    assert build_autofix._transform(plan, "eski") == "yeni içerik"
