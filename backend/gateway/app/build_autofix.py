"""Deterministik build-hatası otomatik düzeltme (kural-tabanlı → GitHub PR).

build_diagnosis'in tespit ettiği auto_fix'lenebilir hatalar için kullanıcı reposuna
tek-tık fix PR açar. Yamalar deterministiktir (LLM yok); patch fonksiyonları saf ve
test edilebilirdir. PR açma tek dışa-dönük eylemdir (kullanıcı butonla tetikler).
"""
import base64
import logging
import re

import httpx

logger = logging.getLogger(__name__)


# Diagnosis id -> deterministik yama tanımı.
FIXABLE_PATCHES: dict[str, dict] = {
    "gradle_oom": {
        "title": "Increase Gradle heap size",
        "kind": "gradle_property",
        "files": ["gradle.properties", "android/gradle.properties"],
        "create_if_missing": "gradle.properties",
        "properties": {"org.gradle.jvmargs": "-Xmx4096m -XX:MaxMetaspaceSize=512m"},
    },
    "gradle_jetifier": {
        "title": "Enable AndroidX and Jetifier",
        "kind": "gradle_property",
        "files": ["gradle.properties", "android/gradle.properties"],
        "create_if_missing": "gradle.properties",
        "properties": {"android.useAndroidX": "true", "android.enableJetifier": "true"},
    },
    "gradle_min_sdk": {
        "title": "Raise minSdkVersion to satisfy dependency",
        "kind": "min_sdk",
        "files": ["app/build.gradle", "android/app/build.gradle", "app/build.gradle.kts",
                  "android/app/build.gradle.kts"],
        "create_if_missing": None,
    },
    "flutter_cocoapods": {
        "title": "Reset Podfile.lock to re-resolve CocoaPods",
        "kind": "delete_file",
        "files": ["ios/Podfile.lock", "Podfile.lock"],
        "create_if_missing": None,
    },
    "xcode_deployment_target": {
        "title": "Raise iOS deployment target in Podfile",
        "kind": "podfile_platform",
        "files": ["ios/Podfile", "Podfile"],
        "create_if_missing": None,
    },
    "xcode_bitcode": {
        "title": "Disable Bitcode (no longer required by Apple)",
        "kind": "regex_replace",
        "files": ["ios/Runner.xcodeproj/project.pbxproj", "ios/App.xcodeproj/project.pbxproj"],
        "create_if_missing": None,
        "pattern": r"ENABLE_BITCODE\s*=\s*YES",
        "replacement": "ENABLE_BITCODE = NO",
    },
}


def apply_gradle_property(content: str, props: dict[str, str]) -> str | None:
    """gradle.properties içeriğinde verilen anahtarları set/ekle. Değişiklik yoksa None."""
    lines = content.splitlines()
    changed = False
    remaining = dict(props)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            desired = f"{key}={remaining[key]}"
            if lines[i] != desired:
                lines[i] = desired
                changed = True
            del remaining[key]
    for key, value in remaining.items():
        lines.append(f"{key}={value}")
        changed = True
    if not changed:
        return None
    return "\n".join(lines) + "\n"


def extract_min_sdk_target(log_output: str) -> int | None:
    """'cannot be smaller than version N' log satırından gereken minSdk'yı çıkar."""
    m = re.search(r"cannot be smaller than version (\d+)", log_output, re.IGNORECASE)
    return int(m.group(1)) if m else None


def apply_min_sdk(content: str, target: int) -> str | None:
    """build.gradle(.kts) içindeki minSdk(Version) değerini target'a yükselt (yalnız daha küçükse)."""
    # Groovy: `minSdkVersion 21` / `minSdkVersion = 21`  · Kotlin DSL: `minSdk = 21` / `minSdk(21)`
    pattern = re.compile(r"(minSdk(?:Version)?\s*(?:=|\(|\s)\s*)(\d+)")
    changed = False

    def _repl(mm: re.Match) -> str:
        nonlocal changed
        current = int(mm.group(2))
        if current < target:
            changed = True
            return f"{mm.group(1)}{target}"
        return mm.group(0)

    new_content = pattern.sub(_repl, content)
    return new_content if changed else None


def extract_ios_target(log_output: str) -> str | None:
    """Xcode/CocoaPods logundan gereken asgari iOS sürümünü çıkar (ör. '12.0')."""
    patterns = [
        r"supported deployment target versions is (\d+(?:\.\d+)?)",
        r"minimum deployment target of (?:iOS )?(\d+(?:\.\d+)?)",
        r"requires a higher minimum (?:iOS )?deployment target[^\d]*(\d+(?:\.\d+)?)",
    ]
    for p in patterns:
        m = re.search(p, log_output, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def apply_podfile_platform(content: str, target: str) -> str | None:
    """Podfile'daki `platform :ios, 'X'` değerini target'a yükselt (yalnız daha küçükse)."""
    pattern = re.compile(r"(platform\s*:ios\s*,\s*['\"])(\d+(?:\.\d+)?)(['\"])")
    changed = False

    def _ver(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split("."))

    def _repl(m: re.Match) -> str:
        nonlocal changed
        if _ver(m.group(2)) < _ver(target):
            changed = True
            return f"{m.group(1)}{target}{m.group(3)}"
        return m.group(0)

    new_content = pattern.sub(_repl, content)
    return new_content if changed else None


def apply_regex_replace(content: str, pattern: str, replacement: str) -> str | None:
    """Genel regex değiştirme. Eşleşme/değişiklik yoksa None."""
    new_content, count = re.subn(pattern, replacement, content)
    return new_content if count and new_content != content else None


def plan_fix(diagnoses: list[dict], log_output: str) -> dict | None:
    """İlk auto_fix'lenebilir ve tanımlı yaması olan tanıyı seç. Yoksa None."""
    for d in diagnoses:
        if not d.get("auto_fix"):
            continue
        patch = FIXABLE_PATCHES.get(d["id"])
        if not patch:
            continue
        plan = {"id": d["id"], "title": patch["title"], "kind": patch["kind"],
                "files": patch["files"], "create_if_missing": patch.get("create_if_missing"),
                "properties": patch.get("properties"),
                "pattern": patch.get("pattern"), "replacement": patch.get("replacement")}
        if patch["kind"] == "min_sdk":
            target = extract_min_sdk_target(log_output)
            if not target:
                continue  # gereken sürüm loglardan okunamadı → atla
            plan["target"] = target
        elif patch["kind"] == "podfile_platform":
            ios_target = extract_ios_target(log_output)
            if not ios_target:
                continue
            plan["target"] = ios_target
        return plan
    return None


def _transform(plan: dict, content: str) -> str | None:
    if plan["kind"] == "gradle_property":
        return apply_gradle_property(content, plan["properties"])
    if plan["kind"] == "min_sdk":
        return apply_min_sdk(content, plan["target"])
    if plan["kind"] == "podfile_platform":
        return apply_podfile_platform(content, plan["target"])
    if plan["kind"] == "regex_replace":
        return apply_regex_replace(content, plan["pattern"], plan["replacement"])
    return None


async def open_fix_pr(owner_repo: str, base_branch: str, github_token: str, plan: dict) -> dict:
    """Plana göre repoda hedef dosyayı bulup yamayı uygular ve fix PR açar.

    Returns {pr_url, file, branch}. Hata durumunda RuntimeError fırlatır (endpoint 400/500 döner).
    """
    headers = {"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as c:
        # 1) base branch sha
        ref = await c.get(f"https://api.github.com/repos/{owner_repo}/git/ref/heads/{base_branch}")
        if ref.status_code != 200:
            raise RuntimeError(f"Base branch '{base_branch}' bulunamadı ({ref.status_code}).")
        base_sha = ref.json()["object"]["sha"]

        # 2) hedef dosyayı bul (aday yollardan ilk var olan). min_sdk için oluşturma yok.
        target_path, current_content, file_sha = None, None, None
        for path in plan["files"]:
            r = await c.get(f"https://api.github.com/repos/{owner_repo}/contents/{path}",
                            params={"ref": base_branch})
            if r.status_code == 200:
                data = r.json()
                current_content = base64.b64decode(data["content"]).decode("utf-8", "replace")
                file_sha = data["sha"]
                target_path = path
                break
        if target_path is None:
            if plan.get("create_if_missing"):
                target_path = plan["create_if_missing"]
                current_content = ""
            else:
                raise RuntimeError("Düzeltilecek dosya repoda bulunamadı (ör. app/build.gradle).")

        # 3) yamayı uygula (delete_file'da dönüşüm yok — dosyanın varlığı yeterli)
        is_delete = plan["kind"] == "delete_file"
        if is_delete:
            new_content = None
        else:
            new_content = _transform(plan, current_content)
            if new_content is None:
                raise RuntimeError("Dosya zaten doğru görünüyor — uygulanacak değişiklik yok.")

        # 4) yeni branch oluştur
        branch = f"apptrack/fix-{plan['id']}-{base_sha[:7]}"
        create_ref = await c.post(
            f"https://api.github.com/repos/{owner_repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
        )
        if create_ref.status_code not in (200, 201) and create_ref.status_code != 422:
            # 422 = branch zaten var (tekrar tıklama) — devam et
            raise RuntimeError(f"Fix branch oluşturulamadı ({create_ref.status_code}).")

        # 5) dosyayı yeni branch'e commit'le.
        # Tekrar-tık: branch zaten varsa dosya orada değişmiş olabilir; contents PUT/DELETE
        # hedef branch'teki blob sha'sını ister (base branch'inki değil). Branch'teki
        # güncel hâli okuyup ona göre karar ver — yoksa 422 alır ve reuse'a hiç ulaşamayız.
        commit_sha = file_sha
        skip_commit = False
        if create_ref.status_code == 422:
            on_branch = await c.get(
                f"https://api.github.com/repos/{owner_repo}/contents/{target_path}",
                params={"ref": branch})
            if on_branch.status_code == 200:
                bdata = on_branch.json()
                commit_sha = bdata["sha"]
                if not is_delete:
                    branch_content = base64.b64decode(bdata["content"]).decode("utf-8", "replace")
                    if branch_content == new_content:
                        # Yama zaten branch'te — commit'i atla, doğrudan PR adımına geç.
                        skip_commit = True
            elif on_branch.status_code == 404 and is_delete:
                # Dosya branch'te zaten silinmiş (tekrar-tık) — commit'i atla.
                skip_commit = True

        if is_delete and not skip_commit:
            delete_resp = await c.request(
                "DELETE",
                f"https://api.github.com/repos/{owner_repo}/contents/{target_path}",
                json={"message": f"AppTrack auto-fix: {plan['title']}",
                      "sha": commit_sha, "branch": branch})
            if delete_resp.status_code not in (200, 201):
                raise RuntimeError(f"Dosya silinemedi ({delete_resp.status_code}).")
        if skip_commit:
            new_content = None

        if new_content is not None:
            put_body: dict = {
                "message": f"AppTrack auto-fix: {plan['title']}",
                "content": base64.b64encode(new_content.encode()).decode(),
                "branch": branch,
            }
            if commit_sha:
                put_body["sha"] = commit_sha
            put = await c.put(f"https://api.github.com/repos/{owner_repo}/contents/{target_path}",
                              json=put_body)
            if put.status_code not in (200, 201):
                raise RuntimeError(f"Yama commit edilemedi ({put.status_code}).")

        # 6) PR aç
        pr = await c.post(
            f"https://api.github.com/repos/{owner_repo}/pulls",
            json={
                "title": f"AppTrack auto-fix: {plan['title']}",
                "head": branch,
                "base": base_branch,
                "body": (f"Bu PR, AppTrack'in build hatası teşhisi tarafından otomatik oluşturuldu.\n\n"
                         f"**Düzeltme:** {plan['title']}\n**Dosya:** `{target_path}`\n\n"
                         "Değişikliği gözden geçirip birleştirin, ardından yeniden build alın."),
            },
        )
        if pr.status_code == 422:
            # Aynı head/base ile PR zaten açık olabilir
            existing = await c.get(f"https://api.github.com/repos/{owner_repo}/pulls",
                                   params={"head": f"{owner_repo.split('/')[0]}:{branch}", "state": "open"})
            items = existing.json() if existing.status_code == 200 else []
            if items:
                return {"pr_url": items[0]["html_url"], "file": target_path, "branch": branch, "reused": True}
            raise RuntimeError("PR açılamadı (422).")
        if pr.status_code not in (200, 201):
            raise RuntimeError(f"PR açılamadı ({pr.status_code}).")
        return {"pr_url": pr.json()["html_url"], "file": target_path, "branch": branch, "reused": False}
