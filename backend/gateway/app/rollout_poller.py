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


async def _check_rollout(db, rollout: ReleaseRollout) -> None:
    project = (await db.execute(
        select(Project).where(Project.id == rollout.project_id))).scalar_one_or_none()
    if not project:
        return
    key_json = await get_user_credential(db, project.owner_id, "google_play", "GOOGLE_PLAY_KEY_JSON")
    snap = await release_health.get_release_health(rollout.platform, rollout.package_name, key_json)
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
        await events.publish_event("rollout.halt", {
            "rollout_id": rollout.id, "target": rollout.platform, "reason": reason,
            "google_play_key_json": key_json, "package_name": rollout.package_name,
            "track": rollout.track,
        })
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
