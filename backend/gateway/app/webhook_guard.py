import logging
import time
from datetime import datetime, timedelta
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import WebhookNonce
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

REPLAY_WINDOW_SECONDS = 300
NONCE_CLEANUP_INTERVAL = 3600


async def check_replay(
    db: AsyncSession,
    source: str,
    nonce: str | None,
    timestamp: int | None,
) -> bool:
    if timestamp:
        now = int(time.time())
        if abs(now - timestamp) > REPLAY_WINDOW_SECONDS:
            logger.warning("Webhook replay rejected: timestamp too old (source=%s, delta=%ds)", source, abs(now - timestamp))
            return False

    if nonce:
        result = await db.execute(
            select(WebhookNonce).where(
                and_(
                    WebhookNonce.source == source,
                    WebhookNonce.nonce_value == nonce,
                    WebhookNonce.expires_at > datetime.utcnow(),
                )
            )
        )
        if result.scalar_one_or_none():
            logger.warning("Webhook replay rejected: duplicate nonce (source=%s, nonce=%s)", source, nonce)
            return False

        entry = WebhookNonce(
            source=source,
            nonce_value=nonce,
            expires_at=datetime.utcnow() + timedelta(seconds=REPLAY_WINDOW_SECONDS * 2),
        )
        db.add(entry)
        await db.flush()

    return True


async def cleanup_expired_nonces():
    import asyncio
    while True:
        try:
            await asyncio.sleep(NONCE_CLEANUP_INTERVAL)
            async with AsyncSessionLocal() as db:
                await db.execute(
                    delete(WebhookNonce).where(WebhookNonce.expires_at < datetime.utcnow())
                )
                await db.commit()
                logger.info("Cleaned up expired webhook nonces")
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Nonce cleanup error: %s", exc)
