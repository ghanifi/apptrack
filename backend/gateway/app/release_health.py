"""Release health sağlayıcı soyutlaması.

Android: Play Developer Reporting API (`crashRateMetricSet`) — deploy ile AYNI service
account, SDK gömme yok, ek maliyet yok. Sağlayıcı/creds yoksa veya herhangi bir hata
olursa `None` döner → çağıran auto-halt'ı zarifçe devre dışı bırakır.

iOS için canlı crash-free pratik değil (bkz. spec) → v1'de google_play dışı platform None.
Parse fonksiyonları saf ve test edilebilirdir; canlı API çağrısı thread'e alınır.
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

PLAY_REPORTING_SCOPE = "https://www.googleapis.com/auth/playdeveloperreporting"


@dataclass
class HealthSnapshot:
    crash_free_rate: float           # 0.0–1.0
    distinct_users: int
    anr_rate: float | None = None
    adoption: float | None = None
    sampled_at: datetime | None = None


def _decimal(metric_value: dict | None) -> float | None:
    """Reporting API metrik değeri → float. `decimalValue.value` (string) formatını çözer."""
    if not metric_value:
        return None
    dv = metric_value.get("decimalValue") or {}
    for src in (dv.get("value"), metric_value.get("value")):
        if src is not None:
            try:
                return float(src)
            except (TypeError, ValueError):
                return None
    return None


def _parse_crash_rate_response(resp: dict) -> HealthSnapshot | None:
    """`vitals.crashrate.query` yanıtından EN GÜNCEL satırı çöz.

    `userPerceivedCrashRate` (0–1) → crash_free_rate = 1 - rate. `distinctUsers` alınır.
    Veri yoksa None."""
    rows = resp.get("rows") or []
    # En güncel, crash_rate içeren satırı sondan bul (boş/kısmi satırları atla).
    for row in reversed(rows):
        crash_rate = None
        distinct = 0
        for m in row.get("metrics", []):
            name = m.get("metric")
            val = _decimal(m)
            if val is None:
                continue
            if name in ("userPerceivedCrashRate", "crashRate"):
                crash_rate = val
            elif name == "distinctUsers":
                distinct = int(val)
        if crash_rate is not None:
            return HealthSnapshot(
                crash_free_rate=max(0.0, min(1.0, 1.0 - crash_rate)),
                distinct_users=distinct,
            )
    return None


def _daily_window(days_back: int = 7) -> dict:
    """Son `days_back` gün için DAILY timelineSpec (bugün dahil)."""
    end = datetime.utcnow()
    start = end - timedelta(days=days_back)
    def _d(dt: datetime) -> dict:
        return {"year": dt.year, "month": dt.month, "day": dt.day}
    return {"aggregationPeriod": "DAILY", "startTime": _d(start), "endTime": _d(end)}


def _query_crash_rate(key_json: str, package_name: str) -> dict:
    """Senkron Google API çağrısı (thread'e alınır). Play Developer Reporting."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build as gapi_build

    creds = service_account.Credentials.from_service_account_info(
        json.loads(key_json), scopes=[PLAY_REPORTING_SCOPE])
    service = gapi_build("playdeveloperreporting", "v1beta1", credentials=creds)
    name = f"apps/{package_name}/crashRateMetricSet"
    body = {
        "metrics": ["userPerceivedCrashRate", "distinctUsers"],
        "timelineSpec": _daily_window(),
    }
    return service.vitals().crashrate().query(name=name, body=body).execute()


async def get_release_health(platform: str, package_name: str | None,
                             key_json: str | None) -> HealthSnapshot | None:
    """Platforma göre release health döndür. Sağlayıcı yok/creds yok/hata → None.

    Android (`google_play`) → Play Reporting crashRateMetricSet. Diğer platform → None.
    """
    if platform != "google_play" or not key_json or not package_name:
        return None
    try:
        resp = await asyncio.to_thread(_query_crash_rate, key_json, package_name)
    except Exception as exc:  # yetki yok / API disabled / ağ — hepsi graceful None
        logger.warning("Release health alınamadı (%s): %s", package_name, exc)
        return None
    snap = _parse_crash_rate_response(resp)
    if snap:
        snap.sampled_at = datetime.utcnow()
    return snap


def _parse_sentry_sessions(resp: dict) -> HealthSnapshot | None:
    """Sentry sessions API yanıtından crash-free + kullanıcı sayısını çöz (saf).

    Beklenen: {"groups": [{"totals": {"crash_free_rate(user)": 0.998,
    "count_unique(user)": 1234}}]}. Oran >1 gelirse yüzde varsayıp /100."""
    groups = resp.get("groups") or []
    for g in groups:
        totals = g.get("totals") or {}
        rate = totals.get("crash_free_rate(user)")
        if rate is None:
            continue
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            continue
        if rate > 1.0:
            rate = rate / 100.0
        users = totals.get("count_unique(user)") or 0
        return HealthSnapshot(
            crash_free_rate=max(0.0, min(1.0, rate)),
            distinct_users=int(users),
        )
    return None


async def get_sentry_health(auth_token: str, org_slug: str,
                            project_slug: str) -> HealthSnapshot | None:
    """Sentry release health — iOS (ve istenirse tüm platformlar) için crash-free.

    Kullanıcının kendi Sentry hesabı; bize maliyet yok. Hata → None (auto-halt
    o tur atlanır)."""
    import httpx
    headers = {"Authorization": f"Bearer {auth_token}"}
    try:
        async with httpx.AsyncClient(timeout=20, headers=headers,
                                     base_url="https://sentry.io/api/0") as c:
            projects = await c.get(f"/organizations/{org_slug}/projects/")
            if projects.status_code != 200:
                logger.warning("Sentry projects listelenemedi (%s)", projects.status_code)
                return None
            proj_id = next((p["id"] for p in projects.json()
                            if p.get("slug") == project_slug), None)
            if not proj_id:
                logger.warning("Sentry projesi bulunamadı: %s", project_slug)
                return None
            sessions = await c.get(
                f"/organizations/{org_slug}/sessions/",
                params=[("field", "crash_free_rate(user)"),
                        ("field", "count_unique(user)"),
                        ("project", proj_id), ("statsPeriod", "24h")])
            if sessions.status_code != 200:
                logger.warning("Sentry sessions sorgusu başarısız (%s)", sessions.status_code)
                return None
    except Exception as exc:
        logger.warning("Sentry health alınamadı: %s", exc)
        return None
    snap = _parse_sentry_sessions(sessions.json())
    if snap:
        snap.sampled_at = datetime.utcnow()
    return snap


def evaluate_halt(snapshot: HealthSnapshot, threshold: float,
                  baseline: float | None, min_users: int) -> tuple[bool, str | None]:
    """Sağlık örneğine göre halt kararı. (halt?, reason). Saf ve test edilebilir.

    - distinct_users < min_users → değerlendirme yok (gürültü koruması).
    - crash_free_rate < threshold (mutlak) → halt.
    - baseline varsa ve düşüş > 0.5pp (0.005) → halt.
    """
    if snapshot.distinct_users < min_users:
        return False, None
    if snapshot.crash_free_rate < threshold:
        return True, (f"Crash-free %{snapshot.crash_free_rate * 100:.2f} < eşik "
                      f"%{threshold * 100:.2f} ({snapshot.distinct_users} kullanıcı)")
    if baseline is not None and (baseline - snapshot.crash_free_rate) > 0.005:
        return True, (f"Crash-free baseline'dan düştü: %{baseline * 100:.2f} → "
                      f"%{snapshot.crash_free_rate * 100:.2f}")
    return False, None
