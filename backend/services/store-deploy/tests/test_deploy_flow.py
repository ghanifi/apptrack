"""
Store Deploy Service -- test_deploy_flow.py
Comprehensive tests for deploy trigger handlers (Google Play + App Store).

Covers:
  - ConfigurationError: missing Google Play key JSON
  - ConfigurationError: missing artifact URL for Google Play
  - ConfigurationError: missing App Store key_id
  - ConfigurationError: missing App Store private_key
  - Successful Google Play deploy (fully mocked)
  - External API failure producing deploy.failed event
"""

import json
import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# PATH SETUP -- make the store-deploy service importable
# (directory name has a hyphen, so we add the app/ dir to sys.path directly)
# ---------------------------------------------------------------------------
_SERVICE_ROOT = os.path.join(os.path.dirname(__file__), "..")
_APP_DIR = os.path.join(_SERVICE_ROOT, "app")
sys.path.insert(0, _APP_DIR)

import aio_pika


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_channel() -> AsyncMock:
    """Return a mock aio_pika channel whose default_exchange.publish is async."""
    channel = AsyncMock(spec=aio_pika.abc.AbstractChannel)
    channel.default_exchange = AsyncMock()
    channel.default_exchange.publish = AsyncMock()
    return channel


def _make_message(body: dict) -> AsyncMock:
    """Return a mock IncomingMessage wrapping *body* as JSON bytes."""
    msg = AsyncMock(spec=aio_pika.abc.AbstractIncomingMessage)
    msg.body = json.dumps(body).encode()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=None)
    ctx.__aexit__ = AsyncMock(return_value=False)
    msg.process = MagicMock(return_value=ctx)
    return msg


def _published_events(channel: AsyncMock) -> list[tuple[str, dict]]:
    """Extract (routing_key, payload) tuples from all publish() calls."""
    events = []
    for call in channel.default_exchange.publish.call_args_list:
        args, kwargs = call
        message_obj = args[0] if args else kwargs.get("message")
        routing_key = kwargs.get("routing_key", args[1] if len(args) > 1 else "")
        body = json.loads(message_obj.body) if hasattr(message_obj, "body") else {}
        events.append((routing_key, body))
    return events


def _find_event(channel: AsyncMock, routing_key: str) -> dict | None:
    """Return the first published event matching *routing_key*, or None."""
    for rk, payload in _published_events(channel):
        if rk == routing_key:
            return payload
    return None


# ---------------------------------------------------------------------------
# Tests -- ConfigurationError: Google Play
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_google_play_missing_key_json():
    """Google Play deploy with no service-account key JSON must emit deploy.failed / configuration_error."""
    import main as deploy_main

    channel = _make_channel()
    body = {
        "deployment_id": "dep-gp-001",
        "build_id": "bld-001",
        "target": "google_play",
        "google_play_key_json": None,
        "artifact_url": "https://storage.example.com/app.aab",
        "package_name": "com.example.app",
        "track": "internal",
    }
    msg = _make_message(body)

    await deploy_main.handle_deploy_triggered(msg, channel)

    event = _find_event(channel, "deploy.failed")
    assert event is not None, "Expected deploy.failed event"
    assert event["deployment_id"] == "dep-gp-001"
    assert event["error_type"] == "configuration_error"
    assert "key" in event["error"].lower() or "Google Play" in event["error"]


@pytest.mark.asyncio
async def test_google_play_missing_artifact():
    """Google Play deploy with no artifact_url must emit deploy.failed / configuration_error."""
    import main as deploy_main

    channel = _make_channel()
    body = {
        "deployment_id": "dep-gp-002",
        "build_id": "bld-002",
        "target": "google_play",
        "google_play_key_json": '{"type":"service_account","project_id":"x"}',
        "artifact_url": None,
        "package_name": "com.example.app",
        "track": "internal",
    }
    msg = _make_message(body)

    await deploy_main.handle_deploy_triggered(msg, channel)

    event = _find_event(channel, "deploy.failed")
    assert event is not None, "Expected deploy.failed event"
    assert event["deployment_id"] == "dep-gp-002"
    assert event["error_type"] == "configuration_error"
    assert "Artifact" in event["error"] or "artifact" in event["error"].lower()


# ---------------------------------------------------------------------------
# Tests -- ConfigurationError: App Store
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_app_store_missing_key_id():
    """App Store deploy with no key_id must emit deploy.failed / configuration_error."""
    import main as deploy_main

    channel = _make_channel()
    body = {
        "deployment_id": "dep-as-001",
        "build_id": "bld-003",
        "target": "app_store",
        "app_store_key_id": None,
        "app_store_issuer_id": "issuer-abc",
        "app_store_private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----",
        "artifact_url": "https://storage.example.com/app.ipa",
    }
    msg = _make_message(body)

    await deploy_main.handle_deploy_triggered(msg, channel)

    event = _find_event(channel, "deploy.failed")
    assert event is not None, "Expected deploy.failed event"
    assert event["deployment_id"] == "dep-as-001"
    assert event["error_type"] == "configuration_error"
    assert "Key ID" in event["error"]


@pytest.mark.asyncio
async def test_app_store_missing_private_key():
    """App Store deploy with no private_key must emit deploy.failed / configuration_error."""
    import main as deploy_main

    channel = _make_channel()
    body = {
        "deployment_id": "dep-as-002",
        "build_id": "bld-004",
        "target": "app_store",
        "app_store_key_id": "key-id-123",
        "app_store_issuer_id": "issuer-abc",
        "app_store_private_key": "",
        "artifact_url": "https://storage.example.com/app.ipa",
    }
    msg = _make_message(body)

    await deploy_main.handle_deploy_triggered(msg, channel)

    event = _find_event(channel, "deploy.failed")
    assert event is not None, "Expected deploy.failed event"
    assert event["deployment_id"] == "dep-as-002"
    assert event["error_type"] == "configuration_error"
    assert "Private Key" in event["error"]


# ---------------------------------------------------------------------------
# Tests -- Successful Google Play deploy (fully mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_google_play_deploy():
    """Google Play deploy with all credentials + mocked Google API must emit deploy.completed."""
    import main as deploy_main

    channel = _make_channel()
    key_json_str = json.dumps({
        "type": "service_account",
        "project_id": "my-proj",
        "private_key_id": "key-1",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
        "client_email": "svc@my-proj.iam.gserviceaccount.com",
        "client_id": "123",
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    body = {
        "deployment_id": "dep-gp-ok-001",
        "build_id": "bld-ok-001",
        "target": "google_play",
        "google_play_key_json": key_json_str,
        "artifact_url": "https://storage.example.com/app.aab",
        "artifact_checksum": None,
        "package_name": "com.example.app",
        "track": "internal",
    }
    msg = _make_message(body)

    # Mock the entire Google API chain inside _deploy_google_play
    mock_creds = MagicMock()
    mock_service = MagicMock()
    # edits().insert().execute() -> {"id": "edit-1"}
    mock_service.edits.return_value.insert.return_value.execute.return_value = {"id": "edit-1"}
    mock_service.edits.return_value.bundles.return_value.upload.return_value.execute.return_value = {}
    mock_service.edits.return_value.tracks.return_value.update.return_value.execute.return_value = {}
    mock_service.edits.return_value.commit.return_value.execute.return_value = {}

    with patch.object(deploy_main, "_download_artifact", new_callable=AsyncMock) as mock_dl, \
         patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value=mock_creds), \
         patch("googleapiclient.discovery.build", return_value=mock_service), \
         patch("os.unlink"):

        mock_dl.return_value = "/tmp/fake-artifact.aab"
        await deploy_main.handle_deploy_triggered(msg, channel)

    event = _find_event(channel, "deploy.completed")
    assert event is not None, "Expected deploy.completed event after successful Google Play deploy"
    assert event["deployment_id"] == "dep-gp-ok-001"
    assert event["target"] == "google_play"
    assert event["status"] == "published"

    # No failure expected
    failed = _find_event(channel, "deploy.failed")
    assert failed is None, "Unexpected deploy.failed event on success path"


# ---------------------------------------------------------------------------
# Tests -- External API failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deploy_api_error():
    """Google Play deploy where the Google API raises an exception must produce deploy.failed."""
    import main as deploy_main

    channel = _make_channel()
    key_json_str = json.dumps({
        "type": "service_account",
        "project_id": "my-proj",
        "private_key_id": "key-1",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
        "client_email": "svc@my-proj.iam.gserviceaccount.com",
        "client_id": "123",
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    body = {
        "deployment_id": "dep-gp-err-001",
        "build_id": "bld-err-001",
        "target": "google_play",
        "google_play_key_json": key_json_str,
        "artifact_url": "https://storage.example.com/app.aab",
        "artifact_checksum": None,
        "package_name": "com.example.app",
        "track": "internal",
    }
    msg = _make_message(body)

    # Make the Google API blow up during edits().insert().execute()
    with patch.object(deploy_main, "_download_artifact", new_callable=AsyncMock) as mock_dl, \
         patch("google.oauth2.service_account.Credentials.from_service_account_info") as mock_creds_fn, \
         patch("googleapiclient.discovery.build") as mock_gapi_build:

        mock_dl.return_value = "/tmp/fake-artifact.aab"
        mock_creds_fn.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service.edits.return_value.insert.return_value.execute.side_effect = Exception(
            "Google API: 403 Forbidden -- insufficient permissions"
        )
        mock_gapi_build.return_value = mock_service

        await deploy_main.handle_deploy_triggered(msg, channel)

    event = _find_event(channel, "deploy.failed")
    assert event is not None, "Expected deploy.failed event when Google API raises"
    assert event["deployment_id"] == "dep-gp-err-001"
    assert "403" in event.get("error", "") or "Forbidden" in event.get("error", "")

    # No deploy.completed
    completed = _find_event(channel, "deploy.completed")
    assert completed is None, "Unexpected deploy.completed when API errored"
