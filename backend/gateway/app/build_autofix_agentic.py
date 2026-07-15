"""Provider-nötr agentic autofix döngüsü. LLM araçlarla (read_file/propose_patch) repo'yu okur,
yama önerir; gateway yamayı yapısal doğrular; final yama build_autofix.open_fix_pr ile PR olur.

Deterministik build_autofix'ten AYRIDIR: bu modül LLM tool-calling içerir; GitHub erişimi
fetch_file enjeksiyonuyla dışarıdan verilir (saf/test edilebilir döngü)."""
import json
import logging
import plistlib

import yaml

from app.llm.base import ToolSpec, LLMError

logger = logging.getLogger(__name__)

MAX_TURNS = 8
MAX_FILES = 12
MAX_FILE_CHARS = 20000
MAX_TOKENS = 60000
REQ_MAX_TOKENS = 4000

READ_FILE = ToolSpec(
    name="read_file",
    description="Repo'daki bir dosyanın tam içeriğini oku. path repo ağacında MEVCUT olmalı.",
    parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})

PROPOSE_PATCH = ToolSpec(
    name="propose_patch",
    description=("Build hatasını çözecek TEK dosyalık yamayı öner. new_content dosyanın TAM yeni "
                 "hâlidir (parça değil). path repo ağacında mevcut olmalı."),
    parameters={"type": "object", "properties": {
        "path": {"type": "string"}, "new_content": {"type": "string"}, "summary": {"type": "string"}},
        "required": ["path", "new_content", "summary"]})

TOOLS = [READ_FILE, PROPOSE_PATCH]

_SYSTEM = (
    "Sen bir CI build hatası düzeltme asistanısın. Araçların var: read_file ile ihtiyacın olan "
    "dosyaları oku, ardından propose_patch ile TEK dosyalık tam-içerik yama öner. Yalnızca repo "
    "ağacında MEVCUT dosyaları kullan; içeriği tahmin etme, önce oku. Yama yapısal geçerli olmalı.")


def validate_patch(path: str, content: str) -> str | None:
    """Yamalanan içeriğin dosya türüne göre yapısal geçerliliğini sınar. None=geçerli, str=hata sebebi.
    Muhafazakâr: tanımadığı türü boş-değilse geçerli kabul eder (yanlış-negatif yerine geçir)."""
    name = path.rsplit("/", 1)[-1].lower()
    if name.endswith(".json"):
        try:
            json.loads(content)
            return None
        except ValueError as e:
            return f"Geçersiz JSON: {e}"
    if name.endswith((".yaml", ".yml")):
        try:
            yaml.safe_load(content)
            return None
        except yaml.YAMLError as e:
            return f"Geçersiz YAML: {str(e)[:120]}"
    if name.endswith(".properties"):
        for ln in content.splitlines():
            s = ln.strip()
            if not s or s.startswith("#") or s.startswith("!"):
                continue
            seps = [i for i in (s.find("="), s.find(":")) if i >= 0]
            sep = min(seps) if seps else -1
            if sep <= 0:
                return f"Geçersiz properties satırı: '{s[:40]}'"
            key = s[:sep].strip()
            if not key or any(ch.isspace() for ch in key):
                return f"Geçersiz properties anahtarı: '{s[:40]}'"
        return None
    if name.endswith(".plist"):
        try:
            plistlib.loads(content.encode("utf-8"))
            return None
        except Exception:
            pass  # plist olmayabilir; boş-değil kontrolüne düş
    if not content.strip():
        return "İçerik boş."
    return None


async def run_agentic_autofix(adapter, model, log_tail, repo_tree, framework, fetch_file, on_step):
    """Agentic tool-calling döngüsü. Bkz. modül docstring. on_step(msg) job'a ilerleme yazar."""
    tree_set = set(repo_tree)
    tree_txt = "\n".join(repo_tree[:400])
    transcript = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (f"Framework: {framework or 'bilinmiyor'}\n\n=== BUILD LOG (son) ===\n"
                                      f"{log_tail[:8000]}\n\n=== REPO AĞACI ===\n{tree_txt}")},
    ]
    usage_total = 0
    files_read = 0
    pending = None  # ilk geçerli yama (öz-eleştiri bekliyor)

    for turn in range(MAX_TURNS):
        try:
            res = await adapter.agentic_step(transcript, TOOLS, model, max_tokens=REQ_MAX_TOKENS)
        except LLMError as exc:
            if turn == 0 and exc.status == 400:
                return {"status": "fallback", "patch": None, "reason": "model araç desteklemiyor"}
            raise
        usage_total += res.usage.get("input_tokens", 0) + res.usage.get("output_tokens", 0)
        if usage_total > MAX_TOKENS:
            return {"status": "aborted", "patch": pending, "reason": f"token bütçesi aşıldı ({usage_total})"}
        if not res.tool_calls:
            # Model öz-eleştiri turunda propose_patch'i tekrar çağırmak yerine metinle onaylayabilir
            # (Gemini böyle davranıyor) → elimizde doğrulanmış pending yama varsa onu final say.
            if pending is not None:
                on_step("PR açılıyor")
                return {"status": "done", "patch": pending, "reason": None}
            return {"status": "no_fix", "patch": None,
                    "reason": (res.text or "model yama önermedi")[:200]}

        transcript.append({"role": "assistant", "content": res.text, "tool_calls": res.tool_calls})
        for tc in res.tool_calls:
            if tc.name == "read_file":
                path = tc.arguments.get("path", "")
                if path not in tree_set:
                    result = f"HATA: '{path}' repo ağacında yok."
                else:
                    files_read += 1
                    if files_read > MAX_FILES:
                        return {"status": "aborted", "patch": pending, "reason": "dosya okuma limiti (12)"}
                    on_step(f"okunuyor: {path}")
                    content = await fetch_file(path)
                    result = ((content or "")[:MAX_FILE_CHARS] if content is not None
                              else f"HATA: '{path}' okunamadı.")
                transcript.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            elif tc.name == "propose_patch":
                path = tc.arguments.get("path", "")
                new_content = tc.arguments.get("new_content", "")
                summary = tc.arguments.get("summary", "AI düzeltmesi")
                on_step(f"yama öneriliyor: {path}")
                if path not in tree_set:
                    transcript.append({"role": "tool", "tool_call_id": tc.id,
                                       "content": f"GEÇERSİZ: '{path}' ağaçta yok. Mevcut bir dosya seç."})
                    continue
                err = validate_patch(path, new_content)
                if err:
                    transcript.append({"role": "tool", "tool_call_id": tc.id,
                                       "content": f"GEÇERSİZ: {err} Düzeltip tekrar öner."})
                    continue
                if pending is None:
                    pending = {"path": path, "new_content": new_content, "summary": summary}
                    on_step("doğrulandı — öz-eleştiri turu")
                    transcript.append({"role": "tool", "tool_call_id": tc.id, "content": (
                        "Yama yapısal geçerli. Son kez denetle: hata varsa düzeltilmiş new_content ile "
                        "propose_patch'i tekrar çağır; doğruysa aynı içerikle tekrar çağır.")})
                else:
                    on_step("PR açılıyor")
                    return {"status": "done",
                            "patch": {"path": path, "new_content": new_content, "summary": summary},
                            "reason": None}
            else:
                transcript.append({"role": "tool", "tool_call_id": tc.id, "content": "Bilinmeyen araç."})

    if pending:
        return {"status": "done", "patch": pending,
                "reason": "öz-eleştiri tamamlanmadı; ilk geçerli yama kullanıldı"}
    return {"status": "aborted", "patch": None, "reason": "tur limiti aşıldı, geçerli yama yok"}
