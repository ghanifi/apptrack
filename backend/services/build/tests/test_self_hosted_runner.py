"""
Build Service -- test_self_hosted_runner.py
Self-hosted runner: label sanitize/injection, runs-on rewrite, preflight check.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

_SERVICE_ROOT = os.path.join(os.path.dirname(__file__), "..")
_APP_DIR = os.path.join(_SERVICE_ROOT, "app")
sys.path.insert(0, _APP_DIR)

import main  # noqa: E402


# --- label sanitize ---------------------------------------------------------

def test_sanitize_labels_valid():
    assert main._sanitize_labels("apptrack-ios, xcode_26") == ["apptrack-ios", "xcode_26"]


def test_sanitize_labels_drops_invalid():
    # bosluklu/gecersiz karakterli token atlanir
    assert main._sanitize_labels("good, bad label, ok-1, in@valid") == ["good", "ok-1"]


def test_sanitize_labels_empty():
    assert main._sanitize_labels("") == []
    assert main._sanitize_labels(None) == []


def test_self_hosted_labels_default():
    assert main._self_hosted_runner_labels(None) == ["self-hosted", "macOS", "ARM64"]


def test_self_hosted_labels_with_custom_and_dedup():
    # ozel label eklenir; zaten var olan (macOS) tekrar eklenmez
    assert main._self_hosted_runner_labels("apptrack-ios, macOS") == [
        "self-hosted", "macOS", "ARM64", "apptrack-ios"
    ]


# --- runs-on rewrite --------------------------------------------------------

def test_rewrite_runs_on_from_placeholder():
    src = "jobs:\n  build:\n    runs-on: [self-hosted, macos-arm64, apptrack-ios]\n"
    out = main._rewrite_runs_on(src, "macos-26")
    assert "runs-on: macos-26" in out
    assert "self-hosted" not in out


def test_rewrite_runs_on_from_hosted_to_self():
    src = "jobs:\n  build:\n    runs-on: macos-26\n"
    label = "[self-hosted, macOS, ARM64]"
    out = main._rewrite_runs_on(src, label)
    assert f"runs-on: {label}" in out


def test_rewrite_runs_on_leaves_ubuntu_untouched():
    src = (
        "jobs:\n"
        "  build:\n    runs-on: macos-26\n"
        "  notify:\n    runs-on: ubuntu-latest\n"
    )
    out = main._rewrite_runs_on(src, "[self-hosted, macOS, ARM64]")
    assert "runs-on: ubuntu-latest" in out          # dokunulmadi
    assert "runs-on: [self-hosted, macOS, ARM64]" in out


# --- preflight --------------------------------------------------------------

def _client_returning(status_code, payload=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload or {}
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)
    return client


def _runner(status="online", busy=False, labels=("self-hosted", "macOS", "ARM64")):
    return {"status": status, "busy": busy, "labels": [{"name": n} for n in labels]}


@pytest.mark.asyncio
async def test_preflight_available_runner():
    client = _client_returning(200, {"runners": [_runner()]})
    ok, reason = await main._check_self_hosted_runner(
        client, "o/r", "tok", ["self-hosted", "macOS", "ARM64"]
    )
    assert ok is True and reason == "runner_available"


@pytest.mark.asyncio
async def test_preflight_offline_runner_blocks():
    client = _client_returning(200, {"runners": [_runner(status="offline")]})
    ok, reason = await main._check_self_hosted_runner(
        client, "o/r", "tok", ["self-hosted", "macOS", "ARM64"]
    )
    assert ok is False and reason == "no_available_runner"


@pytest.mark.asyncio
async def test_preflight_busy_runner_blocks():
    client = _client_returning(200, {"runners": [_runner(busy=True)]})
    ok, _ = await main._check_self_hosted_runner(client, "o/r", "tok", ["self-hosted", "macOS", "ARM64"])
    assert ok is False


@pytest.mark.asyncio
async def test_preflight_label_mismatch_blocks():
    # runner online ama gerekli ozel label yok
    client = _client_returning(200, {"runners": [_runner(labels=("self-hosted", "macOS", "ARM64"))]})
    ok, _ = await main._check_self_hosted_runner(
        client, "o/r", "tok", ["self-hosted", "macOS", "ARM64", "apptrack-ios"]
    )
    assert ok is False


@pytest.mark.asyncio
async def test_preflight_403_proceeds():
    client = _client_returning(403)
    ok, reason = await main._check_self_hosted_runner(client, "o/r", "tok", ["self-hosted"])
    assert ok is True and reason == "preflight_forbidden"


@pytest.mark.asyncio
async def test_preflight_request_error_proceeds():
    client = AsyncMock()
    client.get = AsyncMock(side_effect=RuntimeError("network"))
    ok, reason = await main._check_self_hosted_runner(client, "o/r", "tok", ["self-hosted"])
    assert ok is True and reason == "preflight_error"
