"""Build Service -- test_ipa_inspect.py

IPA imza incelemesi: sahte iç-içe zip'lerle signed/unsigned/ipa-yok/bozuk senaryoları.
"""
import io
import os
import plistlib
import sys
import zipfile
from datetime import datetime

_APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, _APP_DIR)

import ipa_inspect


def _fake_provision(name="AppTrack Profile", exp=datetime(2027, 3, 1)) -> bytes:
    plist = plistlib.dumps({"Name": name, "ExpirationDate": exp})
    return b"\x30\x82CMS" + plist + b"\x00TRAILER"


def _make_ipa(signed: bool, with_provision: bool = True) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Payload/Runner.app/Info.plist", b"<plist/>")
        if with_provision:
            z.writestr("Payload/Runner.app/embedded.mobileprovision", _fake_provision())
        if signed:
            z.writestr("Payload/Runner.app/_CodeSignature/CodeResources", b"<sig/>")
    return buf.getvalue()


def _make_artifact_zip(tmp_path, inner_name: str | None, inner_bytes: bytes = b"") -> str:
    path = str(tmp_path / "artifact.zip")
    with zipfile.ZipFile(path, "w") as z:
        if inner_name:
            z.writestr(inner_name, inner_bytes)
        z.writestr("build.log", b"ok")
    return path


def test_signed_ipa_detected(tmp_path):
    path = _make_artifact_zip(tmp_path, "app.ipa", _make_ipa(signed=True))
    res = ipa_inspect.inspect_artifact_zip(path)
    assert res == {
        "has_ipa": True, "signed": True,
        "profile_name": "AppTrack Profile",
        "profile_expires": "2027-03-01T00:00:00",
    }


def test_unsigned_ipa_detected(tmp_path):
    # provision var ama CodeSignature yok -> imzasiz
    path = _make_artifact_zip(tmp_path, "app.ipa", _make_ipa(signed=False))
    res = ipa_inspect.inspect_artifact_zip(path)
    assert res["has_ipa"] is True and res["signed"] is False


def test_no_provision_means_unsigned(tmp_path):
    path = _make_artifact_zip(tmp_path, "app.ipa", _make_ipa(signed=True, with_provision=False))
    res = ipa_inspect.inspect_artifact_zip(path)
    assert res["signed"] is False and res["profile_name"] is None


def test_no_ipa_in_artifact(tmp_path):
    path = _make_artifact_zip(tmp_path, None)
    assert ipa_inspect.inspect_artifact_zip(path) == {"has_ipa": False}


def test_android_apk_ignored(tmp_path):
    path = _make_artifact_zip(tmp_path, "app-release.apk", b"not-an-ipa")
    assert ipa_inspect.inspect_artifact_zip(path) == {"has_ipa": False}


def test_corrupt_outer_zip_returns_none(tmp_path):
    path = str(tmp_path / "bad.zip")
    with open(path, "wb") as f:
        f.write(b"this is not a zip")
    assert ipa_inspect.inspect_artifact_zip(path) is None


def test_corrupt_inner_ipa_returns_none(tmp_path):
    path = _make_artifact_zip(tmp_path, "app.ipa", b"garbage-not-zip")
    assert ipa_inspect.inspect_artifact_zip(path) is None
