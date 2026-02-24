import hashlib
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import FeatureFlag

logger = logging.getLogger(__name__)

_cache: dict[str, FeatureFlag] = {}
_cache_ts: float = 0
CACHE_TTL = 30


async def _load_flags(db: AsyncSession) -> dict[str, FeatureFlag]:
    import time
    global _cache, _cache_ts
    now = time.time()
    if _cache and (now - _cache_ts) < CACHE_TTL:
        return _cache
    result = await db.execute(select(FeatureFlag))
    flags = {f.name: f for f in result.scalars().all()}
    _cache = flags
    _cache_ts = now
    return flags


def invalidate_cache():
    global _cache, _cache_ts
    _cache = {}
    _cache_ts = 0


async def is_enabled(db: AsyncSession, flag_name: str, user_id: str | None = None) -> bool:
    flags = await _load_flags(db)
    flag = flags.get(flag_name)
    if not flag:
        return True
    if not flag.enabled:
        return False
    if flag.allowed_users and user_id:
        user_list = flag.allowed_users.get("users", [])
        if user_list and user_id not in user_list:
            if flag.percentage > 0:
                h = int(hashlib.md5(f"{flag_name}:{user_id}".encode()).hexdigest()[:8], 16)
                return (h % 100) < flag.percentage
            return False
    if flag.percentage > 0 and flag.percentage < 100 and user_id:
        h = int(hashlib.md5(f"{flag_name}:{user_id}".encode()).hexdigest()[:8], 16)
        return (h % 100) < flag.percentage
    return True
