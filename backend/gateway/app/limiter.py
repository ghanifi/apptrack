import logging
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


def _get_key(request: Request) -> str:
    user = getattr(request.state, "current_user_id", None)
    if user:
        return f"user:{user}"
    return get_remote_address(request)


def _get_storage_uri() -> str:
    """Return Redis URI when available, fall back to in-memory storage."""
    try:
        from app.config import settings
        redis_url = settings.REDIS_URL
        if redis_url:
            return redis_url
    except Exception as exc:
        logger.warning("Could not load REDIS_URL, falling back to memory: %s", exc)
    return "memory://"


limiter = Limiter(
    key_func=_get_key,
    default_limits=["200/minute"],
    storage_uri=_get_storage_uri(),
)
