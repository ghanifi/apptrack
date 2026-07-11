"""IPA imza incelemesi — indirilen artifact zip'inden imza durumu çıkarır.

GitHub Actions artifact'ı dış bir zip'tir; içinde .ipa (kendisi de zip) bulunur.
İnceleme tamamen lokal ve saftır; hata build'i asla düşürmez (None döner).
"""
import logging
import os
import plistlib
import re
import tempfile
import zipfile
from datetime import datetime

logger = logging.getLogger(__name__)

_PROVISION_RE = re.compile(rb"Payload/[^/]+\.app/embedded\.mobileprovision$")
_CODESIGN_RE = re.compile(rb"Payload/[^/]+\.app/_CodeSignature/CodeResources$")

# Zip bombası koruması (H1): dış zip boyutu üst katmanda sınırlı ama DEFLATE ~1000:1
# açılabilir — iç .ipa çıkarımına ve provision okumasına mutlak sınır koyulur.
_MAX_INNER_IPA_BYTES = 2 * 1024 * 1024 * 1024   # 2 GB
_MAX_PROVISION_BYTES = 5 * 1024 * 1024          # 5 MB


def _parse_provision(blob: bytes) -> tuple[str | None, str | None]:
    """CMS-imzalı .mobileprovision içinden (Name, ExpirationDate ISO) çıkar."""
    try:
        start = blob.index(b"<?xml")
        end = blob.index(b"</plist>") + len(b"</plist>")
        data = plistlib.loads(blob[start:end])
        name = data.get("Name")
        exp = data.get("ExpirationDate")
        exp_iso = exp.isoformat() if isinstance(exp, datetime) else None
        return (name if isinstance(name, str) else None), exp_iso
    except Exception:
        return None, None


def _inspect_ipa_file(ipa_path: str) -> dict:
    """Lokal .ipa dosyasını incele: imza göstergeleri + profil bilgisi."""
    result = {"has_ipa": True, "signed": False, "profile_name": None, "profile_expires": None}
    with zipfile.ZipFile(ipa_path) as z:
        names = [n.encode() for n in z.namelist()]
        has_codesign = any(_CODESIGN_RE.search(n) for n in names)
        prov_entry = next((n for n in names if _PROVISION_RE.search(n)), None)
        if prov_entry:
            info = z.getinfo(prov_entry.decode())
            if info.file_size > _MAX_PROVISION_BYTES:
                logger.warning("mobileprovision şüpheli büyüklükte (%d B) — atlanıyor", info.file_size)
            else:
                blob = z.read(prov_entry.decode())
                result["profile_name"], result["profile_expires"] = _parse_provision(blob)
        result["signed"] = bool(has_codesign and prov_entry)
    return result


def inspect_artifact_zip(artifact_zip_path: str) -> dict | None:
    """Dış artifact zip'inde .ipa ara ve imza durumunu döndür.

    Dönüş: {"has_ipa": bool, "signed": bool, "profile_name": ..., "profile_expires": ...}
    .ipa yoksa {"has_ipa": False}; herhangi bir hata → None (build akışını etkilemez).
    """
    try:
        with zipfile.ZipFile(artifact_zip_path) as outer:
            ipa_name = next((n for n in outer.namelist() if n.lower().endswith(".ipa")), None)
            if not ipa_name:
                return {"has_ipa": False}
            # Zip bombası ön kontrolü: bildirilen açılmış boyut sınırı aşıyorsa hiç başlama.
            declared = outer.getinfo(ipa_name).file_size
            if declared > _MAX_INNER_IPA_BYTES:
                logger.warning("İç .ipa bildirilen boyutu sınırı aşıyor (%d B) — inceleme atlandı", declared)
                return {"has_ipa": True, "signed": None, "profile_name": None, "profile_expires": None}
            # İç zip'i rastgele-erişim için geçici dosyaya çıkar — yazılan bayt da sınırlı
            # (bildirilen boyut yalan olabilir).
            written = 0
            with tempfile.NamedTemporaryFile(suffix=".ipa", delete=False) as tmp:
                with outer.open(ipa_name) as src:
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > _MAX_INNER_IPA_BYTES:
                            tmp.close()
                            os.unlink(tmp.name)
                            logger.warning("İç .ipa çıkarım sınırını aştı — zip bombası olabilir")
                            return {"has_ipa": True, "signed": None, "profile_name": None, "profile_expires": None}
                        tmp.write(chunk)
                tmp_path = tmp.name
        try:
            return _inspect_ipa_file(tmp_path)
        except Exception as exc:
            # Dış zip'te .ipa VAR ama iç parse başarısız — sinyali tamamen kaybetme (F8):
            # signed=None "inceleme yapılamadı" demektir, "imzasız" değil.
            logger.warning("İç IPA parse edilemedi: %s", exc)
            return {"has_ipa": True, "signed": None, "profile_name": None, "profile_expires": None}
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception as exc:
        logger.warning("IPA inspection failed for %s: %s", artifact_zip_path, exc)
        return None
