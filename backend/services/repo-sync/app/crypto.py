import base64
from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

KEY_VERSION_PREFIX = "v1:"


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


def decrypt(token: str, secret_key: str, fernet_salt: str) -> str:
    fernet = _derive_fernet(secret_key, fernet_salt)
    mf = MultiFernet([fernet])
    if token.startswith(KEY_VERSION_PREFIX):
        token = token[len(KEY_VERSION_PREFIX):]
    return mf.decrypt(token.encode()).decode()
