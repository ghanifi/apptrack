import hashlib
import logging
from fastapi import Request

logger = logging.getLogger(__name__)


def generate_fingerprint(request: Request) -> str:
    ip = request.client.host if request.client else "0.0.0.0"
    ua = request.headers.get("user-agent", "")
    raw = f"{ip}:{ua}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def validate_fingerprint(request: Request, token_fingerprint: str | None) -> bool:
    if not token_fingerprint:
        return True
    current = generate_fingerprint(request)
    return current == token_fingerprint
