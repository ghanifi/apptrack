"""Staged rollout executor — store API yazma katmanı (ince).

Karar (sonraki fraction, halt eşiği) gateway state machine'inde verilir; burada yalnızca
Google Play `userFraction`/`halted` ve Apple phased-release `PAUSED` uygulanır. Google
senkron client'ı thread'e alınır. Saf yardımcılar (`_pick_release`) test edilebilirdir.
"""
import asyncio
import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)

ANDROID_PUBLISHER_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
ASC_BASE = "https://api.appstoreconnect.apple.com"


def _pick_release(releases: list[dict], statuses: tuple[str, ...]) -> dict | None:
    """Verilen statülerden ilk eşleşen release'i döndür, yoksa ilk release'i (saf)."""
    for status in statuses:
        for r in releases:
            if r.get("status") == status:
                return r
    return releases[0] if releases else None


def _google_service(key_json: str):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build as gapi_build
    creds = service_account.Credentials.from_service_account_info(
        json.loads(key_json), scopes=[ANDROID_PUBLISHER_SCOPE])
    return gapi_build("androidpublisher", "v3", credentials=creds)


def _set_fraction_sync(key_json: str, package_name: str, track: str,
                       fraction: float, complete: bool) -> list | None:
    """Yeni edit aç → mevcut release'in versionCodes'unu koru → userFraction/status güncelle → commit."""
    svc = _google_service(key_json)
    edit = svc.edits().insert(packageName=package_name, body={}).execute()
    eid = edit["id"]
    track_info = svc.edits().tracks().get(
        packageName=package_name, editId=eid, track=track).execute()
    rel = _pick_release(track_info.get("releases", []), ("inProgress", "halted", "draft"))
    version_codes = rel.get("versionCodes") if rel else None
    if complete or fraction >= 1.0:
        release = {"status": "completed", "versionCodes": version_codes}
    else:
        release = {"status": "inProgress", "userFraction": fraction, "versionCodes": version_codes}
    svc.edits().tracks().update(
        packageName=package_name, editId=eid, track=track,
        body={"releases": [release]}).execute()
    svc.edits().commit(packageName=package_name, editId=eid).execute()
    return version_codes


def _halt_sync(key_json: str, package_name: str, track: str) -> None:
    """Devam eden rollout'u `halted`'a çevir (yeni kullanıcılara dağıtımı dondurur)."""
    svc = _google_service(key_json)
    edit = svc.edits().insert(packageName=package_name, body={}).execute()
    eid = edit["id"]
    track_info = svc.edits().tracks().get(
        packageName=package_name, editId=eid, track=track).execute()
    rel = _pick_release(track_info.get("releases", []), ("inProgress",))
    if not rel or rel.get("status") != "inProgress":
        raise RuntimeError("Durdurulacak devam eden bir rollout yok.")
    svc.edits().tracks().update(
        packageName=package_name, editId=eid, track=track,
        body={"releases": [{"status": "halted",
                            "userFraction": rel.get("userFraction"),
                            "versionCodes": rel.get("versionCodes")}]}).execute()
    svc.edits().commit(packageName=package_name, editId=eid).execute()


async def set_google_fraction(key_json: str, package_name: str, track: str,
                              fraction: float, complete: bool = False) -> list | None:
    return await asyncio.to_thread(_set_fraction_sync, key_json, package_name, track, fraction, complete)


async def halt_google(key_json: str, package_name: str, track: str) -> None:
    await asyncio.to_thread(_halt_sync, key_json, package_name, track)


def _asc_jwt(key_id: str, issuer_id: str, private_key_pem: str) -> str:
    import jwt as pyjwt
    now = int(time.time())
    payload = {"iss": issuer_id, "iat": now, "exp": now + 600, "aud": "appstoreconnect-v1"}
    return pyjwt.encode(payload, private_key_pem, algorithm="ES256", headers={"kid": key_id})


async def pause_apple(key_id: str, issuer_id: str, private_key_pem: str,
                      phased_release_id: str) -> None:
    """Apple phased release'i PAUSED yap. 409 (durum uygun değil) tolere edilir."""
    token = _asc_jwt(key_id, issuer_id, private_key_pem)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.patch(
            f"{ASC_BASE}/v1/appStoreVersionPhasedReleases/{phased_release_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"data": {"type": "appStoreVersionPhasedReleases", "id": phased_release_id,
                           "attributes": {"phasedReleaseState": "PAUSED"}}})
        if r.status_code not in (200, 409):
            raise RuntimeError(f"Apple phased release duraklatılamadı ({r.status_code}).")
