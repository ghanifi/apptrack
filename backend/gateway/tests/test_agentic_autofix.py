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


@pytest.mark.asyncio
async def test_anthropic_agentic_step_parses_tool_use():
    from app.llm.anthropic import AnthropicProvider
    from app.llm.base import ToolSpec
    cap = {}
    resp = {"stop_reason": "tool_use", "usage": {"input_tokens": 8, "output_tokens": 5},
            "content": [{"type": "text", "text": "bakıyorum"},
                        {"type": "tool_use", "id": "tu1", "name": "read_file", "input": {"path": "pubspec.yaml"}}]}
    p = AnthropicProvider("ak", transport=_cap_transport(cap, resp))
    tools = [ToolSpec("read_file", "oku", {"type": "object", "properties": {"path": {"type": "string"}}})]
    res = await p.agentic_step([{"role": "system", "content": "sys"},
                                {"role": "user", "content": "hata"}], tools, model="claude-haiku-4-5")
    assert res.stop_reason == "tool_use"
    assert res.tool_calls[0].name == "read_file"
    assert res.tool_calls[0].arguments == {"path": "pubspec.yaml"}
    assert res.usage == {"input_tokens": 8, "output_tokens": 5}
    assert cap["body"]["system"] == "sys"
    assert cap["body"]["tools"][0]["name"] == "read_file"
    assert cap["body"]["tools"][0]["input_schema"]["type"] == "object"


@pytest.mark.asyncio
async def test_anthropic_agentic_merges_consecutive_tool_results():
    from app.llm.anthropic import AnthropicProvider
    from app.llm.base import ToolCall, ToolSpec
    cap = {}
    resp = {"stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1},
            "content": [{"type": "text", "text": "tamam"}]}
    p = AnthropicProvider("ak", transport=_cap_transport(cap, resp))
    transcript = [
        {"role": "user", "content": "hata"},
        {"role": "assistant", "content": "", "tool_calls": [ToolCall("tu1", "read_file", {"path": "a"}),
                                                             ToolCall("tu2", "read_file", {"path": "b"})]},
        {"role": "tool", "tool_call_id": "tu1", "content": "içerik a"},
        {"role": "tool", "tool_call_id": "tu2", "content": "içerik b"},
    ]
    await p.agentic_step(transcript, [ToolSpec("read_file", "d", {})], model="m")
    msgs = cap["body"]["messages"]
    assert msgs[1]["role"] == "assistant"
    assert [b["type"] for b in msgs[1]["content"]] == ["tool_use", "tool_use"]
    assert msgs[2]["role"] == "user"
    assert [b["type"] for b in msgs[2]["content"]] == ["tool_result", "tool_result"]
    assert msgs[2]["content"][0]["tool_use_id"] == "tu1"
    assert msgs[2]["content"][1]["tool_use_id"] == "tu2"


def test_validate_patch_json():
    from app.build_autofix_agentic import validate_patch
    assert validate_patch("package.json", '{"a": 1}') is None
    assert validate_patch("package.json", '{"a": 1,}') is not None


def test_validate_patch_yaml():
    from app.build_autofix_agentic import validate_patch
    assert validate_patch("pubspec.yaml", "name: app\nversion: 1.0.0\n") is None
    assert validate_patch("pubspec.yaml", "name: app\n  bad: : :\n") is not None


def test_validate_patch_gradle_properties():
    from app.build_autofix_agentic import validate_patch
    assert validate_patch("gradle.properties", "# yorum\norg.gradle.jvmargs=-Xmx4g\n") is None
    assert validate_patch("gradle.properties", "bu bir key=value değil satır\n") is not None


def test_validate_patch_unknown_type_nonempty():
    from app.build_autofix_agentic import validate_patch
    assert validate_patch("ios/Runner/Info.plist.txt", "herhangi içerik") is None
    assert validate_patch("weird.xyz", "   \n  ") is not None


class _FakeAdapter:
    """Önceden yazılmış AgenticResult dizisini sırayla döndürür; agentic_step imzasını taklit eder."""
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    async def agentic_step(self, transcript, tools, model, max_tokens=4000, temperature=0.2):
        self.calls += 1
        return self._results.pop(0)


def _ar(tool_calls, usage=None, text="", stop="tool_calls"):
    return AgenticResult(text=text, tool_calls=tool_calls, usage=usage or {"input_tokens": 5, "output_tokens": 5},
                         stop_reason=stop)


@pytest.mark.asyncio
async def test_orchestrator_read_then_patch_with_critique():
    from app.build_autofix_agentic import run_agentic_autofix
    steps = []
    files = {"package.json": '{"name": "x"}'}

    async def fetch(path):
        return files.get(path)

    valid = '{"name": "x", "scripts": {"build": "vite"}}'
    adapter = _FakeAdapter([
        _ar([ToolCall("c1", "read_file", {"path": "package.json"})]),
        _ar([ToolCall("c2", "propose_patch", {"path": "package.json", "new_content": valid, "summary": "scripts ekle"})]),
        _ar([ToolCall("c3", "propose_patch", {"path": "package.json", "new_content": valid, "summary": "scripts ekle"})]),
    ])
    out = await run_agentic_autofix(adapter, "m", "log", ["package.json"], "expo", fetch, steps.append)
    assert out["status"] == "done"
    assert out["patch"]["path"] == "package.json"
    assert adapter.calls == 3
    assert any("öz-eleştiri" in s for s in steps)


@pytest.mark.asyncio
async def test_orchestrator_text_confirmation_finalizes_pending():
    """Öz-eleştiri turunda model propose_patch yerine METİNLE onaylarsa (Gemini davranışı),
    doğrulanmış pending yama final sayılmalı — no_fix DEĞİL. (Canlı testte yakalandı.)"""
    from app.build_autofix_agentic import run_agentic_autofix

    async def fetch(path):
        return "{}"

    good = '{"name": "x", "dependencies": {"expo-router": "^3.0.0"}}'
    adapter = _FakeAdapter([
        _ar([ToolCall("c1", "propose_patch", {"path": "package.json", "new_content": good, "summary": "expo-router ekle"})]),
        _ar([], text="Yama geçerli ve expo-router ekleyerek hatayı çözer.", stop="stop"),
    ])
    out = await run_agentic_autofix(adapter, "m", "log", ["package.json"], "expo", fetch, lambda _s: None)
    assert out["status"] == "done"
    assert out["patch"]["new_content"] == good


@pytest.mark.asyncio
async def test_orchestrator_no_patch_text_only_is_no_fix():
    """Hiç yama önerilmeden model sadece metin dönerse no_fix (pending yok)."""
    from app.build_autofix_agentic import run_agentic_autofix

    async def fetch(path):
        return "x"

    adapter = _FakeAdapter([_ar([], text="Bu hatayı çözemiyorum.", stop="stop")])
    out = await run_agentic_autofix(adapter, "m", "log", ["a"], None, fetch, lambda _s: None)
    assert out["status"] == "no_fix"


@pytest.mark.asyncio
async def test_orchestrator_invalid_json_then_recover():
    from app.build_autofix_agentic import run_agentic_autofix

    async def fetch(path):
        return "{}"

    bad = '{"name": "x",}'
    good = '{"name": "x"}'
    adapter = _FakeAdapter([
        _ar([ToolCall("c1", "propose_patch", {"path": "package.json", "new_content": bad, "summary": "s"})]),
        _ar([ToolCall("c2", "propose_patch", {"path": "package.json", "new_content": good, "summary": "s"})]),
        _ar([ToolCall("c3", "propose_patch", {"path": "package.json", "new_content": good, "summary": "s"})]),
    ])
    out = await run_agentic_autofix(adapter, "m", "log", ["package.json"], None, fetch, lambda _s: None)
    assert out["status"] == "done" and out["patch"]["new_content"] == good


@pytest.mark.asyncio
async def test_orchestrator_token_budget_abort():
    from app.build_autofix_agentic import run_agentic_autofix

    async def fetch(path):
        return "x"

    adapter = _FakeAdapter([
        _ar([ToolCall("c1", "read_file", {"path": "a"})], usage={"input_tokens": 70000, "output_tokens": 0}),
    ])
    out = await run_agentic_autofix(adapter, "m", "log", ["a"], None, fetch, lambda _s: None)
    assert out["status"] == "aborted" and "token" in out["reason"]


@pytest.mark.asyncio
async def test_orchestrator_tool_unsupported_fallback():
    from app.build_autofix_agentic import run_agentic_autofix
    from app.llm.base import LLMError

    class _Boom:
        async def agentic_step(self, *a, **k):
            raise LLMError("no tools", status=400)

    out = await run_agentic_autofix(_Boom(), "m", "log", ["a"], None,
                                    lambda p: None, lambda _s: None)
    assert out["status"] == "fallback"


# --- M1: yol güvenliği (build-config allowlist) ------------------------------
def test_is_patchable_path_allows_build_config():
    from app.build_autofix_agentic import is_patchable_path
    for p in ["android/gradle.properties", "ios/Podfile", "app/build.gradle",
              "ios/App/App.xcodeproj/project.pbxproj", "ios/App/Info.plist",
              "package.json", "pubspec.yaml", "android/app/build.gradle.kts"]:
        assert is_patchable_path(p) is True, p


def test_is_patchable_path_blocks_ci_and_scripts():
    from app.build_autofix_agentic import is_patchable_path
    for p in [".github/workflows/build.yml", ".github/workflows/ci.yaml",
              ".github/actions/x/action.yml", ".gitlab-ci.yml", ".circleci/config.yml",
              "scripts/deploy.sh", "fastlane/Fastfile", "app.config.js", "Makefile",
              "Dockerfile", "src/main.py", "tools/run.mjs", "../../../etc/passwd"]:
        assert is_patchable_path(p) is False, p


@pytest.mark.asyncio
async def test_agentic_rejects_patch_to_ci_workflow():
    """LLM bir CI workflow'unu yamalamaya çalışırsa döngü REDDEDİLDİ döndürür, PR açılmaz."""
    from app.build_autofix_agentic import run_agentic_autofix
    from app.llm.base import AgenticResult, ToolCall

    calls = [
        AgenticResult(text="", tool_calls=[ToolCall(
            id="c1", name="propose_patch",
            arguments={"path": ".github/workflows/build.yml",
                       "new_content": "name: x\non: push\njobs: {}\n",
                       "summary": "kötü niyetli"})], usage={"input_tokens": 10, "output_tokens": 10}),
        AgenticResult(text="tamam", tool_calls=[], usage={"input_tokens": 5, "output_tokens": 5}),
    ]

    class _Adapter:
        def __init__(self):
            self.i = 0

        async def agentic_step(self, transcript, tools, model, max_tokens=None):
            r = calls[self.i]
            self.i += 1
            # reddedilen yamanın tool sonucu transcript'e REDDEDİLDİ olarak yazılmalı
            return r

    steps = []
    res = await run_agentic_autofix(
        _Adapter(), "m", "hata log", [".github/workflows/build.yml", "gradle.properties"],
        "android", lambda p: "", steps.append)
    # geçerli pending yama yok -> done değil; PR açılmamalı
    assert res["status"] != "done"
    assert res["patch"] is None
