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
            # İç zip'i rastgele-erişim için geçici dosyaya çıkar (boyut üst katmanda sınırlı).
            with tempfile.NamedTemporaryFile(suffix=".ipa", delete=False) as tmp:
                with outer.open(ipa_name) as src:
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk:
                            break
                        tmp.write(chunk)
                tmp_path = tmp.name
        try:
            return _inspect_ipa_file(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception as exc:
        logger.warning("IPA inspection failed for %s: %s", artifact_zip_path, exc)
        return None
