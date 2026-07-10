"""
Build Service -- test_workflow_map.py
Tests for WORKFLOW_MAP and workflow selection for new frameworks.

Covers:
  - Capacitor Android workflow selection
  - Capacitor iOS workflow selection (self-hosted runner)
  - Ionic/Cordova shared workflow selection
  - PWA Android (Bubblewrap) workflow selection
  - PWA web workflow selection
  - Android signing credential forwarding
  - Successful GitHub Actions dispatch for Capacitor
"""

import json
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

_SERVICE_ROOT = os.path.join(os.path.dirname(__file__), "..")
_APP_DIR = os.path.join(_SERVICE_ROOT, "app")
sys.path.insert(0, _APP_DIR)

import aio_pika


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_channel() -> AsyncMock:
    channel = AsyncMock(spec=aio_pika.abc.AbstractChannel)
    channel.default_exchange = AsyncMock()
    channel.default_exchange.publish = AsyncMock()
    return channel


def _make_message(body: dict) -> AsyncMock:
    msg = AsyncMock(spec=aio_pika.abc.AbstractIncomingMessage)
    msg.body = json.dumps(body).encode()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=None)
    ctx.__aexit__ = AsyncMock(return_value=False)
    msg.process = MagicMock(return_value=ctx)
    return msg


def _published_events(channel: AsyncMock) -> list[tuple[str, dict]]:
    events = []
    for call in channel.default_exchange.publish.call_args_list:
        args, kwargs = call
        message_obj = args[0] if args else kwargs.get("message")
        routing_key = kwargs.get("routing_key", args[1] if len(args) > 1 else "")
        body = json.loads(message_obj.body) if hasattr(message_obj, "body") else {}
        events.append((routing_key, body))
    return events


def _find_event(channel: AsyncMock, routing_key: str) -> dict | None:
    for rk, payload in _published_events(channel):
        if rk == routing_key:
            return payload
    return None


# ---------------------------------------------------------------------------
# Tests -- WORKFLOW_MAP unit check
# ---------------------------------------------------------------------------

def test_workflow_map_exists():
    """WORKFLOW_MAP dict is defined and contains expected framework entries."""
    import main as build_main
    wmap = build_main.WORKFLOW_MAP
    assert "capacitor" in wmap
    assert "ionic" in wmap
    assert "cordova" in wmap
    assert "pwa" in wmap
    assert "swift" in wmap
    assert "kotlin" in wmap


def test_workflow_map_capacitor_android():
    """Capacitor Android maps to build-capacitor-android.yml."""
    import main as build_main
    assert build_main.WORKFLOW_MAP["capacitor"]["android"] == "build-capacitor-android.yml"


def test_workflow_map_capacitor_ios():
    """Capacitor iOS maps to build-capacitor-ios.yml."""
    import main as build_main
    assert build_main.WORKFLOW_MAP["capacitor"]["ios"] == "build-capacitor-ios.yml"


def test_workflow_map_ionic_shares_capacitor():
    """Ionic uses the same workflows as Capacitor."""
    import main as build_main
    assert build_main.WORKFLOW_MAP["ionic"]["android"] == build_main.WORKFLOW_MAP["capacitor"]["android"]
    assert build_main.WORKFLOW_MAP["ionic"]["ios"] == build_main.WORKFLOW_MAP["capacitor"]["ios"]


def test_workflow_map_cordova_shares_capacitor():
    """Cordova uses the same workflows as Capacitor."""
    import main as build_main
    assert build_main.WORKFLOW_MAP["cordova"]["android"] == build_main.WORKFLOW_MAP["capacitor"]["android"]
    assert build_main.WORKFLOW_MAP["cordova"]["ios"] == build_main.WORKFLOW_MAP["capacitor"]["ios"]


def test_workflow_map_pwa_android():
    """PWA Android maps to build-pwa-android.yml."""
    import main as build_main
    assert build_main.WORKFLOW_MAP["pwa"]["android"] == "build-pwa-android.yml"


def test_workflow_map_pwa_web():
    """PWA web maps to build-pwa.yml."""
    import main as build_main
    assert build_main.WORKFLOW_MAP["pwa"]["web"] == "build-pwa.yml"


def test_workflow_map_pwa_no_ios():
    """PWA has no iOS workflow."""
    import main as build_main
    assert build_main.WORKFLOW_MAP["pwa"].get("ios") is None


# ---------------------------------------------------------------------------
# Tests -- Capacitor Android GitHub Actions dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_capacitor_android_build_dispatch():
    """Capacitor Android build dispatches build-capacitor-android.yml workflow."""
    import main as build_main

    channel = _make_channel()
    body = {
        "build_id": "b-cap-001",
        "project_id": "proj-cap-001",
        "provider": "github_actions",
        "github_token": "ghp_test_token_123",
        "repo_url": "https://github.com/acme/my-capacitor-app",
        "branch": "main",
        "platform": "android",
        "framework": "capacitor",
    }
    msg = _make_message(body)

    mock_response = MagicMock()
    mock_response.status_code = 204

    with patch("main._ensure_workflow_exists", new_callable=AsyncMock, return_value=(True, False)):
        with patch("main.httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.post = AsyncMock(return_value=mock_response)
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=client_instance)
            ctx.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = ctx

            await build_main.handle_build_triggered(msg, channel)

    # Verify the workflow_dispatch was called
    call_args = client_instance.post.call_args
    assert call_args is not None
    url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
    assert "build-capacitor-android.yml" in url

    event = _find_event(channel, "build.started")
    assert event is not None, "Expected build.started event"
    assert event["build_id"] == "b-cap-001"


# ---------------------------------------------------------------------------
# Tests -- Android signing credential forwarding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_android_signing_credentials_forwarded():
    """Android signing credentials are forwarded in workflow_inputs."""
    import main as build_main

    channel = _make_channel()
    body = {
        "build_id": "b-cap-sign-001",
        "project_id": "proj-cap-sign-001",
        "provider": "github_actions",
        "github_token": "ghp_test_token_123",
        "repo_url": "https://github.com/acme/my-capacitor-app",
        "branch": "main",
        "platform": "android",
        "framework": "capacitor",
        "android_keystore_base64": "dGVzdA==",
        "android_keystore_password": "test123",
        "android_key_alias": "upload",
        "android_key_password": "key123",
    }
    msg = _make_message(body)

    mock_response = MagicMock()
    mock_response.status_code = 204

    with patch("main._ensure_workflow_exists", new_callable=AsyncMock, return_value=(True, False)):
        with patch("main.httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.post = AsyncMock(return_value=mock_response)
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=client_instance)
            ctx.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = ctx

            await build_main.handle_build_triggered(msg, channel)

    # Verify signing credentials were passed in the dispatch inputs
    call_args = client_instance.post.call_args
    assert call_args is not None
    json_body = call_args[1].get("json") or (call_args[0][1] if len(call_args[0]) > 1 else {})
    inputs = json_body.get("inputs", {})
    assert inputs.get("android_keystore_base64") == "dGVzdA=="
    assert inputs.get("android_keystore_password") == "test123"
