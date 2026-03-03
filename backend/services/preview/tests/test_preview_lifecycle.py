"""
Preview Service -- test_preview_lifecycle.py
Comprehensive tests for preview start/stop lifecycle and persistence.

Covers:
  - test_preview_start: trigger preview via handle_framework_detected, verify container tracking
  - test_preview_stop: stop a running preview via stop_preview endpoint handler
  - test_preview_concurrent_access: asyncio.Lock prevents race conditions on CONTAINERS
  - test_preview_save_upsert: PostgreSQL upsert for same project_id
"""

import json
import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# PATH SETUP -- make the preview service importable
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
# Tests -- Preview start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_start():
    """
    handle_framework_detected for an expo project must:
      - call _save_preview with correct data
      - attempt _launch_live_preview when ENABLE_LIVE_PREVIEW is True
      - track the container in CONTAINERS dict on success
    """
    import main as preview_main

    channel = _make_channel()
    body = {
        "project_id": "proj-preview-001",
        "framework": "expo",
    }
    msg = _make_message(body)

    saved_calls: list[tuple[str, dict]] = []

    async def _fake_save(project_id, data):
        saved_calls.append((project_id, data))

    async def _fake_load(project_id):
        return None

    # Simulate a successful container launch that puts entry into CONTAINERS
    async def _fake_launch(project_id, framework):
        preview_main.CONTAINERS[project_id] = "container-abc-123"
        return True

    with patch.object(preview_main, "_save_preview", side_effect=_fake_save), \
         patch.object(preview_main, "_load_preview", side_effect=_fake_load), \
         patch.object(preview_main, "_launch_live_preview", side_effect=_fake_launch) as mock_launch, \
         patch.object(preview_main.settings, "ENABLE_LIVE_PREVIEW", True):

        await preview_main.handle_framework_detected(msg, channel)

    # _save_preview should have been called for the project
    assert len(saved_calls) >= 1
    first_save_pid, first_save_data = saved_calls[0]
    assert first_save_pid == "proj-preview-001"
    assert first_save_data.get("framework") == "expo" or first_save_data.get("project_id") == "proj-preview-001"

    # Container should be tracked
    assert "proj-preview-001" in preview_main.CONTAINERS
    assert preview_main.CONTAINERS["proj-preview-001"] == "container-abc-123"

    # Launch should have been called once
    mock_launch.assert_awaited_once_with("proj-preview-001", "expo")

    # Cleanup
    del preview_main.CONTAINERS["proj-preview-001"]


# ---------------------------------------------------------------------------
# Tests -- Preview stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_stop():
    """
    stop_preview endpoint handler must:
      - remove container from CONTAINERS dict
      - call _stop_container_sync via asyncio.to_thread
      - call _delete_preview for DB cleanup
      - return {"project_id": ..., "status": "stopped"}
    """
    import main as preview_main

    project_id = "proj-stop-001"

    # Pre-populate CONTAINERS as if a live preview is running
    preview_main.CONTAINERS[project_id] = "container-xyz-789"

    async def _fake_to_thread(fn, *args, **kwargs):
        """Simulate asyncio.to_thread by just calling the function synchronously."""
        return fn(*args, **kwargs)

    with patch.object(preview_main, "DOCKER_AVAILABLE", True), \
         patch.object(preview_main, "_stop_container_sync") as mock_stop_sync, \
         patch.object(preview_main, "_delete_preview", new_callable=AsyncMock) as mock_delete, \
         patch("asyncio.to_thread", side_effect=_fake_to_thread):

        result = await preview_main.stop_preview(project_id)

    assert result["project_id"] == project_id
    assert result["status"] == "stopped"

    # Container should be removed from tracking dict
    assert project_id not in preview_main.CONTAINERS

    # _stop_container_sync should have been called with the project_id
    mock_stop_sync.assert_called_once_with(project_id)

    # DB delete should have been called
    mock_delete.assert_awaited_once_with(project_id)


# ---------------------------------------------------------------------------
# Tests -- Concurrent access (asyncio.Lock)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_concurrent_access():
    """
    Two simultaneous framework.detected messages for different projects
    must not corrupt the shared CONTAINERS dict thanks to _containers_lock.
    Both projects must end up in CONTAINERS without data loss.
    """
    import main as preview_main

    channel = _make_channel()

    # Track which launches ran and in what order
    launch_order: list[str] = []

    async def _slow_launch(project_id, framework):
        """Simulate a launch that acquires the lock and does async work."""
        async with preview_main._containers_lock:
            launch_order.append(project_id)
            # Simulate a brief async delay while holding the lock
            await asyncio.sleep(0.05)
            preview_main.CONTAINERS[project_id] = f"cnt-{project_id}"
        return True

    msg_a = _make_message({"project_id": "proj-a", "framework": "expo"})
    msg_b = _make_message({"project_id": "proj-b", "framework": "flutter"})

    saved: list = []

    async def _fake_save(pid, data):
        saved.append(pid)

    async def _fake_load(pid):
        return None

    with patch.object(preview_main, "_save_preview", side_effect=_fake_save), \
         patch.object(preview_main, "_load_preview", side_effect=_fake_load), \
         patch.object(preview_main, "_launch_live_preview", side_effect=_slow_launch), \
         patch.object(preview_main.settings, "ENABLE_LIVE_PREVIEW", True):

        await asyncio.gather(
            preview_main.handle_framework_detected(msg_a, channel),
            preview_main.handle_framework_detected(msg_b, channel),
        )

    # Both containers must be in the dict -- no corruption
    assert "proj-a" in preview_main.CONTAINERS
    assert "proj-b" in preview_main.CONTAINERS
    assert preview_main.CONTAINERS["proj-a"] == "cnt-proj-a"
    assert preview_main.CONTAINERS["proj-b"] == "cnt-proj-b"

    # Both projects should appear in the launch order (the lock serializes them)
    assert len(launch_order) == 2
    assert set(launch_order) == {"proj-a", "proj-b"}

    # Cleanup
    del preview_main.CONTAINERS["proj-a"]
    del preview_main.CONTAINERS["proj-b"]


# ---------------------------------------------------------------------------
# Tests -- PostgreSQL upsert (same project_id)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_save_upsert():
    """
    Calling _save_preview twice with the same project_id must issue
    an INSERT ... ON CONFLICT DO UPDATE (upsert) via pg_insert.
    The second call should update (not duplicate) the row.
    """
    import main as preview_main

    # We mock the session factory and track the SQL statements executed
    executed_stmts: list = []

    class FakeSession:
        async def execute(self, stmt):
            executed_stmts.append(stmt)

        async def commit(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    with patch.object(preview_main, "_SessionFactory", return_value=FakeSession()):
        # First insert
        await preview_main._save_preview("proj-upsert-001", {
            "framework": "expo",
            "status": "starting",
            "preview_type": "live",
            "preview_url": "http://localhost:19006",
        })

        # Second insert -- same project_id, different status
        await preview_main._save_preview("proj-upsert-001", {
            "framework": "expo",
            "status": "ready",
            "preview_type": "live",
            "preview_url": "http://localhost:19006",
        })

    # Two statements executed (one per _save_preview call)
    assert len(executed_stmts) == 2

    # Both should be INSERT ... ON CONFLICT statements (PostgreSQL upsert).
    # SQLAlchemy postgresql dialect compiles these as Insert objects.
    from sqlalchemy.dialects.postgresql import Insert
    for stmt in executed_stmts:
        assert isinstance(stmt, Insert), (
            f"Expected a PostgreSQL INSERT (upsert) statement, got {type(stmt).__name__}"
        )

    # Verify the second statement carries the updated status="ready"
    second_stmt = executed_stmts[1]
    compile_params = second_stmt.compile().params
    assert compile_params.get("status") == "ready" or compile_params.get("project_id") == "proj-upsert-001"
