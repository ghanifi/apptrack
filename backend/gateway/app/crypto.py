import base64
import logging
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from app.config import settings

logger = logging.getLogger(__name__)

KEY_VERSION_PREFIX = "v1:"
_multi_fernet: MultiFernet | None = None
_primary_fernet: Fernet | None = None


def _derive_fernet(secret: str, salt: str) -> Fernet:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.encode(),
        iterations=100_000,
        backend=default_backend(),
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return Fernet(key)


def _build_multi_fernet() -> tuple[Fernet, MultiFernet]:
    primary = _derive_fernet(settings.SECRET_KEY, settings.FERNET_SALT)
    keys = [primary]
    old_keys_csv = getattr(settings, "SECRET_KEY_OLD", "") or ""
    if old_keys_csv:
        for old_key in old_keys_csv.split(","):
            old_key = old_key.strip()
            if old_key:
                keys.append(_derive_fernet(old_key, settings.FERNET_SALT))
                logger.info("Loaded 1 rotated key for decryption fallback")
    return primary, MultiFernet(keys)


def _get_multi() -> tuple[Fernet, MultiFernet]:
    global _primary_fernet, _multi_fernet
    if _multi_fernet is None:
        _primary_fernet, _multi_fernet = _build_multi_fernet()
    return _primary_fernet, _multi_fernet


def _get_fernet() -> Fernet:
    p, _ = _get_multi()
    return p


def encrypt(value: str) -> str:
    p, _ = _get_multi()
    token = p.encrypt(value.encode()).decode()
    return KEY_VERSION_PREFIX + token


def decrypt(token: str) -> str:
    _, mf = _get_multi()
    if token.startswith(KEY_VERSION_PREFIX):
        token = token[len(KEY_VERSION_PREFIX):]
    return mf.decrypt(token.encode()).decode()


def re_encrypt(token: str) -> str | None:
    _, mf = _get_multi()
    raw = token
    if raw.startswith(KEY_VERSION_PREFIX):
        raw = raw[len(KEY_VERSION_PREFIX):]
    try:
        decrypted = mf.decrypt(raw.encode())
    except InvalidToken:
        return None
    return encrypt(decrypted.decode())


def rotate_all_tokens(tokens: list[str]) -> list[tuple[str, str]]:
    results = []
    for t in tokens:
        new = re_encrypt(t)
        if new and new != t:
            results.append((t, new))
    return results


_tenant_fernet_cache: dict[str, Fernet] = {}


def _get_tenant_fernet(tenant_id: str) -> Fernet:
    if tenant_id not in _tenant_fernet_cache:
        tenant_salt = f"{settings.FERNET_SALT}:tenant:{tenant_id}"
        _tenant_fernet_cache[tenant_id] = _derive_fernet(settings.SECRET_KEY, tenant_salt)
    return _tenant_fernet_cache[tenant_id]


def encrypt_for_tenant(value: str, tenant_id: str) -> str:
    f = _get_tenant_fernet(tenant_id)
    token = f.encrypt(value.encode()).decode()
    return f"t1:{tenant_id[:8]}:{token}"


def decrypt_for_tenant(token: str, tenant_id: str) -> str:
    if token.startswith("t1:"):
        parts = token.split(":", 2)
        if len(parts) == 3:
            token = parts[2]
    f = _get_tenant_fernet(tenant_id)
    return f.decrypt(token.encode()).decode()
