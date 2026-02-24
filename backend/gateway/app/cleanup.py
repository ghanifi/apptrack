import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, and_, update
from app.database import AsyncSessionLocal
from app.models import Build

logger = logging.getLogger(__name__)

STALE_BUILD_TIMEOUT_MINUTES = 60
CLEANUP_INTERVAL_SECONDS = 300


async def cleanup_stale_builds():
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            cutoff = datetime.utcnow() - timedelta(minutes=STALE_BUILD_TIMEOUT_MINUTES)
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Build).where(
                        and_(
                            Build.status.in_(["queued", "running"]),
                            Build.created_at < cutoff,
                        )
                    )
                )
                stale = result.scalars().all()
                if stale:
                    for build in stale:
                        build.status = "timeout"
                        build.finished_at = datetime.utcnow()
                        logger.warning(
                            "Marking stale build as timeout: build_id=%s project_id=%s age_min=%d",
                            build.id,
                            build.project_id,
                            (datetime.utcnow() - build.created_at).total_seconds() / 60,
                        )
                    await db.commit()
                    logger.info("Cleaned up %d stale builds", len(stale))
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Stale build cleanup error: %s", exc)
