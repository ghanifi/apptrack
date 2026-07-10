"""
AppTrack -- Self-healing pipeline tests
build_autofix patch logic (deterministic) + signing doctor expiry parsing.
"""
import base64
import plistlib
from datetime import datetime, timedelta

import pytest

from app import build_autofix as bf
from app.routers import auto_signing as sign


# ---- build_autofix: gradle.properties ----

def test_gradle_property_appends_missing():
    out = bf.apply_gradle_property("# header\n", {"org.gradle.jvmargs": "-Xmx4096m"})
    assert "org.gradle.jvmargs=-Xmx4096m" in out


def test_gradle_property_replaces_existing():
    out = bf.apply_gradle_property("org.gradle.jvmargs=-Xmx512m\n", {"org.gradle.jvmargs": "-Xmx4096m"})
    assert "org.gradle.jvmargs=-Xmx4096m" in out
    assert "-Xmx512m" not in out


def test_gradle_property_no_change_returns_none():
    assert bf.apply_gradle_property("android.useAndroidX=true\n", {"android.useAndroidX": "true"}) is None


# ---- build_autofix: minSdk ----

def test_extract_min_sdk_target():
    log = "uses-sdk:minSdkVersion 16 cannot be smaller than version 21 declared in library"
    assert bf.extract_min_sdk_target(log) == 21


def test_apply_min_sdk_raises_groovy():
    out = bf.apply_min_sdk("android {\n  minSdkVersion 16\n}", 21)
    assert "minSdkVersion 21" in out


def test_apply_min_sdk_kotlin_dsl():
    out = bf.apply_min_sdk("minSdk = 19", 24)
    assert "minSdk = 24" in out


def test_apply_min_sdk_no_downgrade():
    # mevcut zaten hedeften buyukse degistirme
    assert bf.apply_min_sdk("minSdkVersion 26", 21) is None


# ---- build_autofix: plan_fix ----

def test_plan_fix_selects_first_fixable():
    diagnoses = [
        {"id": "gradle_dependency_resolution", "auto_fix": False},
        {"id": "gradle_oom", "auto_fix": True},
    ]
    plan = bf.plan_fix(diagnoses, "")
    assert plan["id"] == "gradle_oom" and plan["kind"] == "gradle_property"


def test_plan_fix_min_sdk_needs_target():
    # min_sdk secilir ama log'da hedef yoksa atlanir
    diagnoses = [{"id": "gradle_min_sdk", "auto_fix": True}]
    assert bf.plan_fix(diagnoses, "no version here") is None
    plan = bf.plan_fix(diagnoses, "cannot be smaller than version 23")
    assert plan and plan["target"] == 23


def test_plan_fix_none_when_no_defined_patch():
    assert bf.plan_fix([{"id": "unknown_error", "auto_fix": True}], "") is None


# ---- signing doctor: expiry parsing ----

def _make_p12(not_after: datetime) -> str:
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.serialization import pkcs12, BestAvailableEncryption
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AppTrack Test")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow() - timedelta(days=1))
            .not_valid_after(not_after).sign(key, hashes.SHA256()))
    data = pkcs12.serialize_key_and_certificates(b"t", key, cert, None, BestAvailableEncryption(b"pw"))
    return base64.b64encode(data).decode()


def test_parse_cert_expiry_roundtrip():
    exp = datetime(2027, 6, 1, 12, 0, 0)
    got = sign.parse_cert_expiry(_make_p12(exp), "pw")
    assert got is not None and got.date() == exp.date()


def test_parse_cert_expiry_bad_input():
    assert sign.parse_cert_expiry("not-base64!!", "pw") is None


def test_parse_provisioning_expiry():
    exp = datetime(2027, 3, 15, 0, 0, 0)
    plist = plistlib.dumps({"Name": "Profile", "ExpirationDate": exp})
    blob = b"\x30\x82CMSPREFIX" + plist + b"CMSSUFFIX\x00"
    got = sign.parse_provisioning_expiry(base64.b64encode(blob).decode())
    assert got is not None and got.date() == exp.date()


def test_health_item_statuses():
    assert sign._health_item("c", "certificate", datetime.utcnow() - timedelta(days=1))["status"] == "expired"
    assert sign._health_item("c", "certificate", datetime.utcnow() + timedelta(days=10))["status"] == "expiring_soon"
    assert sign._health_item("c", "certificate", datetime.utcnow() + timedelta(days=200))["status"] == "ok"
    assert sign._health_item("c", "certificate", None)["status"] == "unknown"
