from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_key(request: Request) -> str:
    user = getattr(request.state, "current_user_id", None)
    if user:
        return f"user:{user}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=_get_key,
    default_limits=["200/minute"],
    storage_uri="memory://",
)
