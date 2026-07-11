"""Gateway'in şifrelediği event credential'larını çözme (M2).

Gateway crypto.py ile AYNI türetim: PBKDF2-SHA256(SECRET_KEY, FERNET_SALT, 100k)
→ Fernet, "v1:" prefix. Payload'da `enc_credentials` varsa çözüp payload'a
merge eder; yoksa payload'ı aynen döndürür (geri uyumluluk).
"""
import base64
import json
import logging
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        secret = os.environ.get("SECRET_KEY", "dev-secret-key")
        salt = os.environ.get("FERNET_SALT", "apptrack-fernet-salt-change-me")
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                         salt=salt.encode(), iterations=100_000)
        _fernet = Fernet(base64.urlsafe_b64encode(kdf.derive(secret.encode())))
    return _fernet


def unpack_secrets(payload: dict) -> dict:
    """`enc_credentials` alanını çözüp payload'a merge et (yoksa no-op)."""
    token = payload.get("enc_credentials")
    if not token:
        return payload
    if token.startswith("v1:"):
        token = token[3:]
    try:
        secrets = json.loads(_get_fernet().decrypt(token.encode()).decode())
    except Exception as exc:
        logger.error("enc_credentials çözülemedi: %s — SECRET_KEY/FERNET_SALT eşleşiyor mu?", exc)
        return payload
    merged = dict(payload)
    merged.update(secrets)
    return merged
