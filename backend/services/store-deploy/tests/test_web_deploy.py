"""
Store Deploy Service -- test_web_deploy.py
Tests for web deploy handler (_deploy_web / Netlify deployment).

Covers:
  - ConfigurationError: missing netlify_token
  - ConfigurationError: missing artifact_url
  - Successful Netlify deploy (mocked HTTP)
  - Netlify API error propagation
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
# Tests -- Web deploy: missing netlify token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_web_deploy_missing_netlify_token():
    """Web deploy with no netlify_token must emit deploy.failed / configuration_error."""
    import main as deploy_main

    channel = _make_channel()
    body = {
        "deployment_id": "dep-web-001",
        "build_id": "bld-web-001",
        "target": "web",
        "netlify_token": None,
        "artifact_url": "https://storage.example.com/dist.zip",
    }
    msg = _make_message(body)

    await deploy_main.handle_deploy_triggered(msg, channel)

    event = _find_event(channel, "deploy.failed")
    assert event is not None, "Expected deploy.failed event"
    assert event["deployment_id"] == "dep-web-001"
    assert event["error_type"] == "configuration_error"
    assert "netlify" in event["error"].lower() or "NETLIFY_TOKEN" in event["error"]


# ---------------------------------------------------------------------------
# Tests -- Web deploy: missing artifact URL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_web_deploy_missing_artifact():
    """Web deploy with no artifact_url must emit deploy.failed / configuration_error."""
    import main as deploy_main

    channel = _make_channel()
    body = {
        "deployment_id": "dep-web-002",
        "build_id": "bld-web-002",
        "target": "web",
        "netlify_token": "nfp_test_token_123",
        "artifact_url": None,
    }
    msg = _make_message(body)

    await deploy_main.handle_deploy_triggered(msg, channel)

    event = _find_event(channel, "deploy.failed")
    assert event is not None, "Expected deploy.failed event"
    assert event["deployment_id"] == "dep-web-002"
    assert event["error_type"] == "configuration_error"
    assert "artifact" in event["error"].lower()


# ---------------------------------------------------------------------------
# Tests -- Successful Netlify deploy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_netlify_deploy():
    """Web deploy with valid token and artifact must emit deploy.completed."""
    import main as deploy_main

    channel = _make_channel()
    body = {
        "deployment_id": "dep-web-ok-001",
        "build_id": "bld-web-ok-001",
        "target": "web",
        "netlify_token": "nfp_real_token_456",
        "artifact_url": "https://storage.example.com/dist.zip",
        "deploy_url": "https://my-app.netlify.app",
    }
    msg = _make_message(body)

    # Mock: download artifact, then Netlify API returns success
    mock_dl_response = MagicMock()
    mock_dl_response.status_code = 200
    mock_dl_response.content = b"PK\x03\x04fake-zip-content"

    mock_deploy_response = MagicMock()
    mock_deploy_response.status_code = 200
    mock_deploy_response.json.return_value = {
        "id": "netlify-deploy-001",
        "url": "https://my-app.netlify.app",
        "state": "ready",
    }

    with patch("main.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        # First call: download artifact, Second call: Netlify deploy
        client_instance.get = AsyncMock(return_value=mock_dl_response)
        client_instance.post = AsyncMock(return_value=mock_deploy_response)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=client_instance)
        ctx.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = ctx

        with patch("os.unlink"):
            await deploy_main.handle_deploy_triggered(msg, channel)

    event = _find_event(channel, "deploy.completed")
    assert event is not None, "Expected deploy.completed event"
    assert event["deployment_id"] == "dep-web-ok-001"
    assert event["target"] == "web"

    failed = _find_event(channel, "deploy.failed")
    assert failed is None, "Unexpected deploy.failed on success path"


# ---------------------------------------------------------------------------
# Tests -- Netlify API error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_netlify_api_error():
    """Web deploy where Netlify API returns error must emit deploy.failed."""
    import main as deploy_main

    channel = _make_channel()
    body = {
        "deployment_id": "dep-web-err-001",
        "build_id": "bld-web-err-001",
        "target": "web",
        "netlify_token": "nfp_real_token_456",
        "artifact_url": "https://storage.example.com/dist.zip",
    }
    msg = _make_message(body)

    # Mock stream response for _download_artifact (uses client.stream("GET", ...))
    mock_stream_response = AsyncMock()
    mock_stream_response.raise_for_status = MagicMock()
    async def _fake_aiter_bytes(chunk_size=None):
        yield b"PK\x03\x04fake-zip-content"
    mock_stream_response.aiter_bytes = _fake_aiter_bytes

    stream_ctx = AsyncMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_response)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)

    # Mock Netlify POST response (error)
    mock_deploy_response = MagicMock()
    mock_deploy_response.status_code = 422
    mock_deploy_response.text = "Unprocessable Entity: invalid zip"
    mock_deploy_response.json.return_value = {"message": "invalid zip"}

    with patch("main.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.stream = MagicMock(return_value=stream_ctx)
        client_instance.post = AsyncMock(return_value=mock_deploy_response)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=client_instance)
        ctx.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = ctx

        with patch("os.unlink"):
            await deploy_main.handle_deploy_triggered(msg, channel)

    event = _find_event(channel, "deploy.failed")
    assert event is not None, "Expected deploy.failed event on Netlify API error"
    assert event["deployment_id"] == "dep-web-err-001"
    assert "422" in event.get("error", "") or "invalid" in event.get("error", "").lower()
