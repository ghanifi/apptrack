"""
AppTrack — OTA Router Tests
=============================
Tests for backend/gateway/app/routers/ota.py

Covers: push_custom_bundle, list_custom_bundle_updates, check_for_update (public),
        rollback (custom bundle), validation errors
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

# Patch database engine creation before import — SQLite doesn't support pool_size params
from unittest.mock import patch as _patch
from sqlalchemy.pool import StaticPool
_orig_create = None

def _patched_create_engine(url, **kwargs):
    """Strip pool params incompatible with SQLite/StaticPool."""
    for k in ("pool_size", "max_overflow", "pool_timeout", "pool_recycle"):
        kwargs.pop(k, None)
    kwargs["poolclass"] = StaticPool
    from sqlalchemy.ext.asyncio import create_async_engine as _real_create
    return _real_create.__wrapped__(url, **kwargs) if hasattr(_real_create, '__wrapped__') else _orig_create(url, **kwargs)

import sqlalchemy.ext.asyncio as _sea
_orig_create = _sea.create_async_engine
_sea.create_async_engine = _patched_create_engine

from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Build a minimal FastAPI app with the OTA router."""
    from fastapi import FastAPI
    from app.routers import ota

    app = FastAPI()
    app.include_router(ota.router, prefix="/api/ota")
    return app


def _fake_project(**overrides):
    """Return a MagicMock that behaves like a Project ORM instance."""
    defaults = dict(
        id="proj-001",
        owner_id="550e8400-e29b-41d4-a716-446655440000",
        name="test-capacitor-app",
        framework="capacitor",
    )
    defaults.update(overrides)
    project = MagicMock()
    for k, v in defaults.items():
        setattr(project, k, v)
    return project


def _fake_ota_update(**overrides):
    """Return a MagicMock that behaves like an OTAUpdate ORM instance."""
    now = datetime.utcnow()
    defaults = dict(
        id="upd-001",
        project_id="proj-001",
        channel="production",
        platform="all",
        runtime_version="1.0.0",
        bundle_url="https://storage.example.com/bundles/v1.zip",
        message="Bug fixes",
        status="published",
        created_by="550e8400-e29b-41d4-a716-446655440000",
        created_at=now,
    )
    defaults.update(overrides)
    update = MagicMock()
    for k, v in defaults.items():
        setattr(update, k, v)
    return update


def _override_deps(app, mock_db, current_user):
    """Override get_db and get_current_user dependencies."""
    from app.database import get_db
    from app.dependencies import get_current_user as gcu

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[gcu] = lambda: current_user


# ---------------------------------------------------------------------------
# 1. Push custom bundle — success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_push_custom_bundle_success(mock_db, test_user, auth_headers):
    """POST /api/ota/custom-bundle creates an OTA update record."""
    project = _fake_project(owner_id=test_user["id"])
    mock_db.get = AsyncMock(return_value=project)

    async def _fake_refresh(obj):
        obj.id = "upd-new-001"
        obj.status = "published"
        obj.channel = "production"
        obj.platform = "all"
        obj.runtime_version = "1.0.0"
        obj.bundle_url = "https://storage.example.com/bundles/v1.zip"
        obj.message = "Test update"

    mock_db.refresh = AsyncMock(side_effect=_fake_refresh)

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/ota/custom-bundle", json={
            "project_id": "proj-001",
            "channel": "production",
            "platform": "all",
            "runtime_version": "1.0.0",
            "bundle_url": "https://storage.example.com/bundles/v1.zip",
            "message": "Test update",
        }, headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "published"
    assert data["channel"] == "production"
    assert data["bundle_url"] == "https://storage.example.com/bundles/v1.zip"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Push custom bundle — missing bundle_url
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_push_custom_bundle_missing_url(mock_db, test_user, auth_headers):
    """POST /api/ota/custom-bundle without bundle_url returns 400."""
    project = _fake_project(owner_id=test_user["id"])
    mock_db.get = AsyncMock(return_value=project)

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/ota/custom-bundle", json={
            "project_id": "proj-001",
            "channel": "production",
            "platform": "all",
            "runtime_version": "1.0.0",
            "bundle_url": "",
            "message": "No URL",
        }, headers=auth_headers)

    assert resp.status_code == 400
    assert "bundle_url" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. Push custom bundle — project not found
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_push_custom_bundle_project_not_found(mock_db, test_user, auth_headers):
    """POST /api/ota/custom-bundle with nonexistent project returns 404."""
    mock_db.get = AsyncMock(return_value=None)

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/ota/custom-bundle", json={
            "project_id": "nonexistent",
            "channel": "production",
            "bundle_url": "https://example.com/bundle.zip",
        }, headers=auth_headers)

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 4. Push custom bundle — not owned
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_push_custom_bundle_not_owned(mock_db, test_user, auth_headers):
    """POST /api/ota/custom-bundle for another user's project returns 404."""
    project = _fake_project(owner_id="someone-else-id")
    mock_db.get = AsyncMock(return_value=project)

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/ota/custom-bundle", json={
            "project_id": "proj-001",
            "channel": "production",
            "bundle_url": "https://example.com/bundle.zip",
        }, headers=auth_headers)

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. List custom bundle history — success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_custom_bundle_history(mock_db, test_user, auth_headers):
    """GET /api/ota/custom-bundle/{project_id}/history returns update list."""
    project = _fake_project(owner_id=test_user["id"])
    mock_db.get = AsyncMock(return_value=project)

    upd1 = _fake_ota_update(id="upd-1", message="First update")
    upd2 = _fake_ota_update(id="upd-2", message="Second update")

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [upd1, upd2]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_db.execute = AsyncMock(return_value=result_mock)

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/ota/custom-bundle/proj-001/history",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["update_id"] == "upd-1"
    assert data[1]["update_id"] == "upd-2"


# ---------------------------------------------------------------------------
# 6. Check for update — public endpoint (no auth), update available
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_check_for_update_available(mock_db):
    """GET /api/ota/check/{project_id} returns available=true when update exists."""
    update = _fake_ota_update()

    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = update
    mock_db.execute = AsyncMock(return_value=scalar_mock)

    app = _make_app()
    # Only override get_db — no auth override needed (public endpoint)
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/ota/check/proj-001",
            params={"channel": "production", "platform": "all"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["bundle_url"] == "https://storage.example.com/bundles/v1.zip"
    assert data["runtime_version"] == "1.0.0"
    assert data["channel"] == "production"


# ---------------------------------------------------------------------------
# 7. Check for update — no update available
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_check_for_update_not_available(mock_db):
    """GET /api/ota/check/{project_id} returns available=false when no update."""
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=scalar_mock)

    app = _make_app()
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/ota/check/proj-001",
            params={"channel": "staging", "platform": "ios"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False


# ---------------------------------------------------------------------------
# 8. Check for update — no auth required (public)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_check_for_update_no_auth_required(mock_db):
    """GET /api/ota/check/{project_id} works without auth headers."""
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=scalar_mock)

    app = _make_app()
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    # Explicitly NOT overriding get_current_user — endpoint shouldn't need it

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/ota/check/proj-001")

    # Should NOT get 401/403
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 9. Rollback — custom bundle (no EAS token)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rollback_custom_bundle(mock_db, test_user, auth_headers):
    """POST /api/ota/rollback rolls back to previous custom bundle."""
    project = _fake_project(owner_id=test_user["id"])
    mock_db.get = AsyncMock(return_value=project)

    prev_update = _fake_ota_update(
        id="upd-prev",
        bundle_url="https://storage.example.com/bundles/v0.9.zip",
        runtime_version="0.9.0",
    )
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = prev_update
    mock_db.execute = AsyncMock(return_value=scalar_mock)

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    # Patch _get_credential to return None (no EAS token → custom bundle rollback path)
    with patch("app.routers.ota._get_credential", new_callable=AsyncMock, return_value=None):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/ota/rollback",
                params={"project_id": "proj-001", "channel": "production", "platform": "all"},
                headers=auth_headers,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rolled_back"
    assert data["bundle_url"] == "https://storage.example.com/bundles/v0.9.zip"
    assert data["runtime_version"] == "0.9.0"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# 10. Rollback — no previous update found
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rollback_no_previous_update(mock_db, test_user, auth_headers):
    """POST /api/ota/rollback returns 404 when no previous update exists."""
    project = _fake_project(owner_id=test_user["id"])
    mock_db.get = AsyncMock(return_value=project)

    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=scalar_mock)

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    with patch("app.routers.ota._get_credential", new_callable=AsyncMock, return_value=None):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/ota/rollback",
                params={"project_id": "proj-001", "channel": "production", "platform": "all"},
                headers=auth_headers,
            )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 11. Rollback — missing project_id without EAS token
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rollback_missing_project_id(mock_db, test_user, auth_headers):
    """POST /api/ota/rollback without project_id and without EAS token returns 400."""
    app = _make_app()
    _override_deps(app, mock_db, test_user)

    with patch("app.routers.ota._get_credential", new_callable=AsyncMock, return_value=None):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/ota/rollback",
                headers=auth_headers,
            )

    assert resp.status_code == 400
