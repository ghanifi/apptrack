"""
Sertleştirme regresyonları (SAST M-A / L-B).

- M-A: production'da zayıf/varsayılan SECRET_KEY/FERNET_SALT reddedilir.
- L-B: store metadata *_url alanları yalnız http(s) kabul eder (javascript:/data: XSS reddi).
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))


# --- M-A: config prod-guard -------------------------------------------------
@pytest.mark.parametrize("secret_key,should_reject", [
    ("dev-secret-key", True),          # docker default
    ("short", True),                    # <32
    ("change-me-abcdefghij1234567890", True),
    ("a" * 40, False),                  # güçlü
])
def test_prod_rejects_weak_secret(secret_key, should_reject):
    from app.config import Settings
    try:
        Settings(SECRET_KEY=secret_key, FERNET_SALT="x" * 20, ENVIRONMENT="production")
        rejected = False
    except Exception:
        rejected = True
    assert rejected == should_reject


def test_dev_allows_weak_secret():
    """development'ta zayıf değer kabul edilir (guard yalnız production'da)."""
    from app.config import Settings
    s = Settings(SECRET_KEY="dev-secret-key", FERNET_SALT="salt", ENVIRONMENT="development")
    assert s.SECRET_KEY == "dev-secret-key"


# --- L-B: store_metadata url şeması ----------------------------------------
@pytest.mark.parametrize("url,ok", [
    ("https://example.com/privacy", True),
    ("http://example.com/privacy", True),
    ("", True),
    (None, True),
    ("javascript:alert(1)", False),
    ("data:text/html,<script>alert(1)</script>", False),
    ("vbscript:msgbox(1)", False),
])
def test_store_metadata_url_scheme(url, ok):
    from app.routers.store_metadata import StoreMetadataUpsert
    from pydantic import ValidationError
    if ok:
        m = StoreMetadataUpsert(privacy_url=url)
        assert m.privacy_url == url
    else:
        with pytest.raises(ValidationError):
            StoreMetadataUpsert(privacy_url=url)
