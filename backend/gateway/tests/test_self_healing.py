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


# ---- open_fix_pr: real HTTP flow via MockTransport ----

import httpx


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _patch_client(monkeypatch, handler):
    """bf.httpx.AsyncClient'ı MockTransport'lu istemciyle değiştir (header/timeout yut)."""
    real_cls = httpx.AsyncClient
    def _factory(*args, **kwargs):
        return real_cls(transport=httpx.MockTransport(handler),
                        base_url="https://api.github.com")
    monkeypatch.setattr(bf.httpx, "AsyncClient", _factory)


OOM_PLAN = {"id": "gradle_oom", "title": "Increase Gradle heap size", "kind": "gradle_property",
            "files": ["gradle.properties", "android/gradle.properties"],
            "create_if_missing": "gradle.properties",
            "properties": {"org.gradle.jvmargs": "-Xmx4096m -XX:MaxMetaspaceSize=512m"}}
FIXED = "org.gradle.jvmargs=-Xmx4096m -XX:MaxMetaspaceSize=512m\n"


@pytest.mark.asyncio
async def test_open_fix_pr_first_run_creates_pr(monkeypatch):
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path))
        p = req.url.path
        if req.method == "GET" and p.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "abc1234deadbeef"}})
        if req.method == "GET" and "/contents/" in p:
            return httpx.Response(404, json={})  # dosya base'de yok → create_if_missing
        if req.method == "POST" and p.endswith("/git/refs"):
            return httpx.Response(201, json={})  # branch oluştu
        if req.method == "PUT" and "/contents/" in p:
            return httpx.Response(201, json={})
        if req.method == "POST" and p.endswith("/pulls"):
            return httpx.Response(201, json={"html_url": "https://github.com/o/r/pull/1"})
        return httpx.Response(500, json={})

    _patch_client(monkeypatch, handler)
    res = await bf.open_fix_pr("o/r", "main", "tok", OOM_PLAN)
    assert res["reused"] is False
    assert res["pr_url"].endswith("/pull/1")
    assert res["file"] == "gradle.properties"
    assert ("PUT", "/repos/o/r/contents/gradle.properties") in calls


@pytest.mark.asyncio
async def test_open_fix_pr_second_run_reuses_pr(monkeypatch):
    """Tekrar-tık: branch+dosya zaten var, PR açık → yeni commit yok, mevcut PR döner."""
    put_calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if req.method == "GET" and p.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "abc1234deadbeef"}})
        if req.method == "GET" and "/contents/" in p:
            ref = req.url.params.get("ref", "")
            if ref == "main":
                return httpx.Response(404, json={})           # base'de yok
            return httpx.Response(200, json={"sha": "blob99", "content": _b64(FIXED)})  # branch'te var, aynı içerik
        if req.method == "POST" and p.endswith("/git/refs"):
            return httpx.Response(422, json={"message": "Reference already exists"})
        if req.method == "PUT" and "/contents/" in p:
            put_calls.append(p)
            return httpx.Response(201, json={})
        if req.method == "POST" and p.endswith("/pulls"):
            return httpx.Response(422, json={"message": "A pull request already exists"})
        if req.method == "GET" and p.endswith("/pulls"):
            return httpx.Response(200, json=[{"html_url": "https://github.com/o/r/pull/1"}])
        return httpx.Response(500, json={})

    _patch_client(monkeypatch, handler)
    res = await bf.open_fix_pr("o/r", "main", "tok", OOM_PLAN)
    assert res["reused"] is True
    assert res["pr_url"].endswith("/pull/1")
    assert put_calls == []  # içerik aynı olduğu için yeniden commit YOK


# ---- Autofix genişletme: iOS/CocoaPods yamaları ----

def test_extract_ios_target_patterns():
    assert bf.extract_ios_target("the range of supported deployment target versions is 12.0 to 17.5") == "12.0"
    assert bf.extract_ios_target("requires a minimum deployment target of iOS 13.0") == "13.0"
    assert bf.extract_ios_target("no version hint here") is None


def test_apply_podfile_platform_raises():
    out = bf.apply_podfile_platform("platform :ios, '11.0'\ntarget 'Runner' do\n", "12.0")
    assert "platform :ios, '12.0'" in out


def test_apply_podfile_platform_no_downgrade():
    assert bf.apply_podfile_platform("platform :ios, '15.0'", "12.0") is None


def test_apply_podfile_platform_double_quotes():
    out = bf.apply_podfile_platform('platform :ios, "10.0"', "12.0")
    assert 'platform :ios, "12.0"' in out


def test_apply_regex_replace_bitcode():
    content = "ENABLE_BITCODE = YES;\nOTHER = 1;\nENABLE_BITCODE = YES;\n"
    out = bf.apply_regex_replace(content, r"ENABLE_BITCODE\s*=\s*YES", "ENABLE_BITCODE = NO")
    assert out.count("ENABLE_BITCODE = NO") == 2
    assert "YES" not in out


def test_apply_regex_replace_no_match_returns_none():
    assert bf.apply_regex_replace("ENABLE_BITCODE = NO;", r"ENABLE_BITCODE\s*=\s*YES", "X") is None


def test_plan_fix_podfile_platform_needs_target():
    diags = [{"id": "xcode_deployment_target", "auto_fix": True}]
    assert bf.plan_fix(diags, "no version") is None
    plan = bf.plan_fix(diags, "supported deployment target versions is 12.0 to 17.0")
    assert plan and plan["kind"] == "podfile_platform" and plan["target"] == "12.0"


def test_plan_fix_delete_and_regex_kinds():
    plan = bf.plan_fix([{"id": "flutter_cocoapods", "auto_fix": True}], "")
    assert plan and plan["kind"] == "delete_file" and "ios/Podfile.lock" in plan["files"]
    plan2 = bf.plan_fix([{"id": "xcode_bitcode", "auto_fix": True}], "")
    assert plan2 and plan2["kind"] == "regex_replace" and plan2["pattern"]


DELETE_PLAN = {"id": "flutter_cocoapods", "title": "Reset Podfile.lock to re-resolve CocoaPods",
               "kind": "delete_file", "files": ["ios/Podfile.lock", "Podfile.lock"],
               "create_if_missing": None, "properties": None, "pattern": None, "replacement": None}


@pytest.mark.asyncio
async def test_open_fix_pr_delete_file_first_run(monkeypatch):
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path))
        p = req.url.path
        if req.method == "GET" and p.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "abc1234deadbeef"}})
        if req.method == "GET" and "/contents/" in p:
            return httpx.Response(200, json={"sha": "lock99", "content": _b64("PODS:\n")})
        if req.method == "POST" and p.endswith("/git/refs"):
            return httpx.Response(201, json={})
        if req.method == "DELETE" and "/contents/" in p:
            return httpx.Response(200, json={})
        if req.method == "POST" and p.endswith("/pulls"):
            return httpx.Response(201, json={"html_url": "https://github.com/o/r/pull/9"})
        return httpx.Response(500, json={})

    _patch_client(monkeypatch, handler)
    res = await bf.open_fix_pr("o/r", "main", "tok", DELETE_PLAN)
    assert res["reused"] is False and res["file"] == "ios/Podfile.lock"
    assert ("DELETE", "/repos/o/r/contents/ios/Podfile.lock") in calls
    # PUT hiç çağrılmamalı
    assert not any(m == "PUT" for m, _ in calls)


@pytest.mark.asyncio
async def test_open_fix_pr_delete_file_second_run_reuses(monkeypatch):
    """Tekrar-tık: branch var, dosya branch'te zaten silinmiş → commit yok, PR reuse."""
    deletes = []

    def handler(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if req.method == "GET" and p.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "abc1234deadbeef"}})
        if req.method == "GET" and "/contents/" in p:
            ref = req.url.params.get("ref", "")
            if ref == "main":
                return httpx.Response(200, json={"sha": "lock99", "content": _b64("PODS:\n")})
            return httpx.Response(404, json={})  # branch'te silinmiş
        if req.method == "POST" and p.endswith("/git/refs"):
            return httpx.Response(422, json={"message": "Reference already exists"})
        if req.method == "DELETE" and "/contents/" in p:
            deletes.append(p)
            return httpx.Response(200, json={})
        if req.method == "POST" and p.endswith("/pulls"):
            return httpx.Response(422, json={"message": "already exists"})
        if req.method == "GET" and p.endswith("/pulls"):
            return httpx.Response(200, json=[{"html_url": "https://github.com/o/r/pull/9"}])
        return httpx.Response(500, json={})

    _patch_client(monkeypatch, handler)
    res = await bf.open_fix_pr("o/r", "main", "tok", DELETE_PLAN)
    assert res["reused"] is True
    assert deletes == []  # ikinci tıkta DELETE çağrılmadı


# ---- imza hatasi teshis desenleri (signed-IPA hazirligi) ----

def test_profile_expired_pattern_matches_first():
    from app.routers.build_diagnosis import _match_error_patterns
    log = "error: Your provisioning profile 'AppTrack Dist' has expired."
    ids = [d["id"] for d in _match_error_patterns(log, framework="swift")]
    assert ids[0] == "xcode_profile_expired"


def test_no_profile_for_bundle_pattern():
    from app.routers.build_diagnosis import _match_error_patterns
    log = "error: No profiles for 'com.example.app' were found: Xcode couldn't find any provisioning profiles"
    ids = [d["id"] for d in _match_error_patterns(log, framework="swift")]
    assert "xcode_no_profile_for_bundle" in ids
    assert ids.index("xcode_no_profile_for_bundle") < ids.index("xcode_signing")
