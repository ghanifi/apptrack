"""Release health poller — aktif rollout'ları periyodik izler, eşik aşılırsa auto-halt.

Free/low-cost (çekirdek ilke): yalnızca `state=in_progress` ve `auto_halt_enabled`
rollout'lar sorgulanır; terminal durumda listeden düşer; sağlık sağlayıcısı yoksa
(get_release_health → None) o tur atlanır ve maliyet doğmaz. Aralık ~30 dk (Play
Reporting verisi zaten saatlik/günlük tazelenir, daha sık sorgu anlamsız + kotayı yer).
"""
import asyncio
import logging
import os

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import ReleaseRollout, ReleaseHealthSample, Project
from app.routers.credentials import get_user_credential
from app import release_health, events, notification_worker

logger = logging.getLogger(__name__)

POLL_INTERVAL = int(os.getenv("ROLLOUT_POLL_INTERVAL", "1800"))  # 30 dk


async def _resolve_health(db, owner_id: str, rollout: ReleaseRollout):
    """Platforma göre sağlık sağlayıcısı: Android=Play Reporting, iOS=Sentry."""
    if rollout.platform == "google_play":
        key_json = await get_user_credential(db, owner_id, "google_play", "GOOGLE_PLAY_KEY_JSON")
        return await release_health.get_release_health(rollout.platform, rollout.package_name, key_json), key_json
    if rollout.platform == "app_store":
        token = await get_user_credential(db, owner_id, "sentry", "SENTRY_AUTH_TOKEN")
        org = await get_user_credential(db, owner_id, "sentry", "SENTRY_ORG_SLUG")
        proj = await get_user_credential(db, owner_id, "sentry", "SENTRY_PROJECT_SLUG")
        if not (token and org and proj):
            return None, None
        return await release_health.get_sentry_health(token, org, proj), None
    return None, None


async def _halt_payload(db, owner_id: str, rollout: ReleaseRollout,
                        reason: str, google_key_json: str | None) -> dict:
    payload = {"rollout_id": rollout.id, "target": rollout.platform, "reason": reason,
               "package_name": rollout.package_name, "track": rollout.track,
               "external_ref": rollout.external_ref}
    if rollout.platform == "google_play":
        payload["google_play_key_json"] = google_key_json or await get_user_credential(
            db, owner_id, "google_play", "GOOGLE_PLAY_KEY_JSON")
    else:
        payload["app_store_key_id"] = await get_user_credential(db, owner_id, "app_store", "APP_STORE_KEY_ID")
        payload["app_store_issuer_id"] = await get_user_credential(db, owner_id, "app_store", "APP_STORE_ISSUER_ID")
        payload["app_store_private_key"] = await get_user_credential(db, owner_id, "app_store", "APP_STORE_PRIVATE_KEY")
    return payload


async def _check_rollout(db, rollout: ReleaseRollout) -> None:
    project = (await db.execute(
        select(Project).where(Project.id == rollout.project_id))).scalar_one_or_none()
    if not project:
        return
    snap, key_json = await _resolve_health(db, project.owner_id, rollout)
    if snap is None:
        return  # bu tur sağlık verisi yok — maliyet yok, sonraki turda dene

    db.add(ReleaseHealthSample(
        rollout_id=rollout.id, crash_free_rate=snap.crash_free_rate,
        anr_rate=snap.anr_rate, distinct_users=snap.distinct_users, adoption=snap.adoption))
    if rollout.baseline_crash_free is None:
        rollout.baseline_crash_free = snap.crash_free_rate

    halt, reason = release_health.evaluate_halt(
        snap, rollout.crash_free_threshold, rollout.baseline_crash_free, rollout.min_users)
    if halt:
        rollout.state = "halted"
        rollout.halted_reason = reason
    await db.commit()

    if halt:
        await events.publish_event(
            "rollout.halt",
            await _halt_payload(db, project.owner_id, rollout, reason, key_json))
        await notification_worker.dispatch_for_event(
            {"rollout_id": rollout.id, "project_id": rollout.project_id, "reason": reason},
            "rollout.auto_halted")
        logger.warning("Auto-halted rollout %s: %s", rollout.id, reason)


async def _poll_once() -> None:
    async with AsyncSessionLocal() as db:
        rollouts = (await db.execute(select(ReleaseRollout).where(
            ReleaseRollout.state == "in_progress",
            ReleaseRollout.auto_halt_enabled.is_(True)))).scalars().all()
        for rollout in rollouts:
            try:
                await _check_rollout(db, rollout)
            except Exception as exc:  # tek rollout hatası döngüyü düşürmez
                logger.error("Rollout %s health check error: %s", rollout.id, exc)


async def poll_release_health() -> None:
    logger.info("Rollout health poller started (interval=%ss)", POLL_INTERVAL)
    while True:
        try:
            await _poll_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Rollout poll cycle error: %s", exc)
        await asyncio.sleep(POLL_INTERVAL)
