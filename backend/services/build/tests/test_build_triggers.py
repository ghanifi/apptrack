"""
Build Service -- test_build_triggers.py
Comprehensive tests for build trigger handlers across all providers.

Covers:
  - ConfigurationError paths for EAS, Codemagic, GitHub Actions
  - Unknown provider handling
  - Successful EAS build (mocked API)
  - External API error propagation (build.failed)
"""

import json
import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# PATH SETUP -- make the build service importable
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
    # process() context-manager should be a no-op
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
# Tests -- ConfigurationError paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_eas_build_missing_token():
    """EAS build with eas_token=None must publish build.failed with error_type=configuration_error."""
    import main as build_main

    channel = _make_channel()
    body = {
        "build_id": "b-eas-001",
        "project_id": "proj-001",
        "provider": "eas",
        "eas_token": None,
        "expo_app_id": "my-expo-app",
        "platform": "all",
        "framework": "expo",
    }
    msg = _make_message(body)

    await build_main.handle_build_triggered(msg, channel)

    event = _find_event(channel, "build.failed")
    assert event is not None, "Expected build.failed event"
    assert event["build_id"] == "b-eas-001"
    assert event["error_type"] == "configuration_error"
    assert "EAS_TOKEN" in event["error"]


@pytest.mark.asyncio
async def test_eas_build_missing_app_id():
    """EAS build with expo_app_id empty must publish build.failed with configuration_error."""
    import main as build_main

    channel = _make_channel()
    body = {
        "build_id": "b-eas-002",
        "project_id": "proj-002",
        "provider": "eas",
        "eas_token": "valid-token",
        "expo_app_id": "",
        "platform": "all",
        "framework": "expo",
    }
    msg = _make_message(body)

    await build_main.handle_build_triggered(msg, channel)

    event = _find_event(channel, "build.failed")
    assert event is not None, "Expected build.failed event"
    assert event["build_id"] == "b-eas-002"
    assert event["error_type"] == "configuration_error"
    assert "EXPO_APP_ID" in event["error"]


@pytest.mark.asyncio
async def test_codemagic_build_missing_token():
    """Codemagic build without token must publish build.failed / configuration_error."""
    import main as build_main

    channel = _make_channel()
    body = {
        "build_id": "b-cm-001",
        "project_id": "proj-003",
        "provider": "codemagic",
        "codemagic_token": "",
        "codemagic_app_id": "cm-app-1",
        "platform": "android",
        "framework": "kotlin",
    }
    msg = _make_message(body)

    await build_main.handle_build_triggered(msg, channel)

    event = _find_event(channel, "build.failed")
    assert event is not None, "Expected build.failed event"
    assert event["build_id"] == "b-cm-001"
    assert event["error_type"] == "configuration_error"
    assert "CODEMAGIC_TOKEN" in event["error"]


@pytest.mark.asyncio
async def test_github_actions_build_missing_token():
    """GitHub Actions build without github_token (and no env fallback) must raise configuration_error."""
    import main as build_main

    channel = _make_channel()
    body = {
        "build_id": "b-gh-001",
        "project_id": "proj-004",
        "provider": "github_actions",
        "github_token": "",
        "repo_url": "https://github.com/acme/app",
        "branch": "main",
        "platform": "android",
        "framework": "kotlin",
    }
    msg = _make_message(body)

    # Also ensure the settings-level fallback is empty
    with patch.object(build_main.settings, "GITHUB_ACTIONS_TOKEN", ""):
        await build_main.handle_build_triggered(msg, channel)

    event = _find_event(channel, "build.failed")
    assert event is not None, "Expected build.failed event"
    assert event["build_id"] == "b-gh-001"
    assert event["error_type"] == "configuration_error"
    assert "GITHUB_ACTIONS_TOKEN" in event["error"]


# ---------------------------------------------------------------------------
# Tests -- Unknown provider
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_provider():
    """Unsupported provider string must publish build.failed with error_type=unsupported_provider."""
    import main as build_main

    channel = _make_channel()
    body = {
        "build_id": "b-unk-001",
        "project_id": "proj-005",
        "provider": "bitrise",
        "framework": "flutter",
    }
    msg = _make_message(body)

    await build_main.handle_build_triggered(msg, channel)

    event = _find_event(channel, "build.failed")
    assert event is not None, "Expected build.failed event for unknown provider"
    assert event["build_id"] == "b-unk-001"
    assert event.get("error_type") == "unsupported_provider"
    assert "bitrise" in event["error"]


# ---------------------------------------------------------------------------
# Tests -- Successful EAS build (mocked HTTP)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_eas_build():
    """Mocked 200 response from EAS API must produce build.started event with external_build_id."""
    import main as build_main

    channel = _make_channel()
    body = {
        "build_id": "b-eas-ok-001",
        "project_id": "proj-006",
        "provider": "eas",
        "eas_token": "tok-abc-123",
        "expo_app_id": "my-expo-app",
        "platform": "android",
        "framework": "expo",
        "branch": "main",
    }
    msg = _make_message(body)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"id": "eas-ext-999"}}
    mock_response.text = '{"data":{"id":"eas-ext-999"}}'

    with patch("main.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.post = AsyncMock(return_value=mock_response)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=client_instance)
        ctx.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = ctx

        await build_main.handle_build_triggered(msg, channel)

    event = _find_event(channel, "build.started")
    assert event is not None, "Expected build.started event after successful EAS call"
    assert event["build_id"] == "b-eas-ok-001"
    assert event["project_id"] == "proj-006"
    assert event["provider"] == "eas"
    assert event["external_build_id"] == "eas-ext-999"

    # Should NOT have a build.failed
    failed = _find_event(channel, "build.failed")
    assert failed is None, "Unexpected build.failed event on success path"


# ---------------------------------------------------------------------------
# Tests -- External API returning an error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_api_error():
    """EAS API returning 500 must produce build.failed with the status code in the error string."""
    import main as build_main

    channel = _make_channel()
    body = {
        "build_id": "b-eas-err-001",
        "project_id": "proj-007",
        "provider": "eas",
        "eas_token": "tok-good",
        "expo_app_id": "my-expo-app",
        "platform": "ios",
        "framework": "expo",
        "branch": "main",
    }
    msg = _make_message(body)

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"error": "internal server error"}
    mock_response.text = "Internal Server Error -- queue overloaded"

    with patch("main.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.post = AsyncMock(return_value=mock_response)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=client_instance)
        ctx.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = ctx

        await build_main.handle_build_triggered(msg, channel)

    event = _find_event(channel, "build.failed")
    assert event is not None, "Expected build.failed event on API error"
    assert event["build_id"] == "b-eas-err-001"
    assert event["project_id"] == "proj-007"
    assert "500" in event["error"]

    # No build.started expected
    started = _find_event(channel, "build.started")
    assert started is None, "Unexpected build.started event when API returns 500"
