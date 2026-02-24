import hashlib
import hmac
import logging
import time
from app.config import settings

logger = logging.getLogger(__name__)

SERVICE_TOKEN_TTL = 300


def generate_service_token(service_name: str) -> str:
    if not settings.SERVICE_TOKEN_SECRET:
        return ""
    ts = str(int(time.time()))
    message = f"{service_name}:{ts}"
    sig = hmac.new(settings.SERVICE_TOKEN_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"{service_name}:{ts}:{sig}"


def verify_service_token(token: str, allowed_services: list[str] | None = None) -> tuple[bool, str]:
    if not settings.SERVICE_TOKEN_SECRET:
        return True, "service-auth-disabled"
    if not token:
        return False, "missing-token"
    parts = token.split(":", 2)
    if len(parts) != 3:
        return False, "malformed-token"
    service_name, ts_str, sig = parts
    if allowed_services and service_name not in allowed_services:
        return False, f"unauthorized-service:{service_name}"
    try:
        ts = int(ts_str)
    except ValueError:
        return False, "invalid-timestamp"
    if abs(time.time() - ts) > SERVICE_TOKEN_TTL:
        return False, "expired-token"
    expected = hmac.new(
        settings.SERVICE_TOKEN_SECRET.encode(),
        f"{service_name}:{ts_str}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False, "invalid-signature"
    return True, service_name
