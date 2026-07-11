"""AppTrack — İmzalama doktoru teşhis motoru testleri (saf fonksiyonlar).

Sahte p12 + .mobileprovision plist ile bundle-eşleşme, sertifika-profil bağı,
şifre çözme, süre bitimi senaryoları. Apple API / DB'ye dokunmaz.
"""
import base64
import hashlib
import plistlib
from datetime import datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12, BestAvailableEncryption
from cryptography.x509.oid import NameOID

from app.routers import auto_signing as sig


def _make_cert(not_after: datetime):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AppTrack Test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_after - timedelta(days=365))
        .not_valid_after(not_after)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _p12_b64(key, cert, password: str) -> str:
    raw = pkcs12.serialize_key_and_certificates(
        name=b"AppTrack", key=key, cert=cert, cas=None,
        encryption_algorithm=BestAvailableEncryption(password.encode()),
    )
    return base64.b64encode(raw).decode()


def _cert_der_sha(cert) -> str:
    der = cert.public_bytes(serialization.Encoding.DER)
    return hashlib.sha256(der).hexdigest()


def _profile_b64(bundle: str, expiry: datetime, cert_ders: list[bytes]) -> str:
    plist = plistlib.dumps({
        "ExpirationDate": expiry,
        "Entitlements": {"application-identifier": f"TEAMID123.{bundle}"},
        "DeveloperCertificates": cert_ders,
    })
    raw = b"\x30\x82CMS-HEADER" + plist + b"TRAILER"
    return base64.b64encode(raw).decode()


def test_parse_profile_extracts_bundle_and_certs():
    key, cert = _make_cert(datetime.utcnow() + timedelta(days=100))
    der = cert.public_bytes(serialization.Encoding.DER)
    b64 = _profile_b64("com.example.app", datetime.utcnow() + timedelta(days=100), [der])
    parsed = sig.parse_provisioning_profile(b64)
    assert parsed["bundle_id"] == "com.example.app"
    assert _cert_der_sha(cert) in parsed["cert_shas"]


def test_parse_profile_wildcard_bundle():
    b64 = _profile_b64("*", datetime.utcnow() + timedelta(days=100), [])
    assert sig.parse_provisioning_profile(b64)["bundle_id"] == "*"


def test_diagnose_bundle_mismatch():
    key, cert = _make_cert(datetime.utcnow() + timedelta(days=100))
    der = cert.public_bytes(serialization.Encoding.DER)
    p12 = _p12_b64(key, cert, "pw")
    prof = _profile_b64("com.other.app", datetime.utcnow() + timedelta(days=100), [der])
    res = sig.diagnose_signing(p12, "pw", prof, "com.example.app", asc_configured=True)
    match = next(c for c in res["checks"] if c["id"] == "bundle_match")
    assert match["status"] == "mismatch"
    assert res["can_auto_repair"] is True  # asc + bundle var, düzeltilebilir sorun var


def test_diagnose_bundle_wildcard_ok():
    key, cert = _make_cert(datetime.utcnow() + timedelta(days=100))
    der = cert.public_bytes(serialization.Encoding.DER)
    p12 = _p12_b64(key, cert, "pw")
    prof = _profile_b64("*", datetime.utcnow() + timedelta(days=100), [der])
    res = sig.diagnose_signing(p12, "pw", prof, "com.example.app", asc_configured=True)
    match = next(c for c in res["checks"] if c["id"] == "bundle_match")
    assert match["status"] == "ok"


def test_diagnose_cert_not_in_profile():
    key1, cert1 = _make_cert(datetime.utcnow() + timedelta(days=100))
    key2, cert2 = _make_cert(datetime.utcnow() + timedelta(days=100))
    p12 = _p12_b64(key1, cert1, "pw")
    other_der = cert2.public_bytes(serialization.Encoding.DER)
    prof = _profile_b64("com.example.app", datetime.utcnow() + timedelta(days=100), [other_der])
    res = sig.diagnose_signing(p12, "pw", prof, "com.example.app", asc_configured=True)
    link = next(c for c in res["checks"] if c["id"] == "cert_in_profile")
    assert link["status"] == "error"


def test_diagnose_wrong_password():
    key, cert = _make_cert(datetime.utcnow() + timedelta(days=100))
    p12 = _p12_b64(key, cert, "correct")
    res = sig.diagnose_signing(p12, "wrong", None, "com.example.app", asc_configured=True)
    pw = next(c for c in res["checks"] if c["id"] == "cert_password")
    assert pw["status"] == "error"


def test_diagnose_expired_cert():
    key, cert = _make_cert(datetime.utcnow() - timedelta(days=2))
    p12 = _p12_b64(key, cert, "pw")
    res = sig.diagnose_signing(p12, "pw", None, "com.example.app", asc_configured=True)
    c = next(x for x in res["checks"] if x["id"] == "certificate")
    assert c["status"] == "expired"
    assert res["overall"] == "expired"


def test_diagnose_not_configured():
    res = sig.diagnose_signing(None, None, None, "com.example.app", asc_configured=False)
    assert res["configured"] is False
    assert res["overall"] == "not_configured"
    assert res["can_auto_repair"] is False


def test_diagnose_healthy_no_repair():
    key, cert = _make_cert(datetime.utcnow() + timedelta(days=200))
    der = cert.public_bytes(serialization.Encoding.DER)
    p12 = _p12_b64(key, cert, "pw")
    prof = _profile_b64("com.example.app", datetime.utcnow() + timedelta(days=200), [der])
    res = sig.diagnose_signing(p12, "pw", prof, "com.example.app", asc_configured=True)
    assert res["overall"] == "ok"
    assert res["can_auto_repair"] is False  # düzeltilecek sorun yok
