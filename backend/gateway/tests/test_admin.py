"""
AppTrack — Admin Router Tests
===============================
Tests for backend/gateway/app/routers/admin.py

Covers: list_users (tenants), system_stats (overview), toggle_user (suspend),
        audit_summary (audit-export), non-admin access denial
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Build a minimal FastAPI app with the admin router.

    Note: admin router has its own prefix="/api/admin" built in.
    """
    from fastapi import FastAPI
    from app.routers import admin

    app = FastAPI()
    app.include_router(admin.router)
    return app


def _fake_user_model(**overrides):
    """Return a MagicMock that behaves like a User ORM instance."""
    now = datetime.utcnow()
    defaults = dict(
        id="user-001",
        name="Regular User",
        email="user@apptrack.io",
        github_id=None,
        created_at=now,
    )
    defaults.update(overrides)
    user = MagicMock()
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


def _override_deps(app, mock_db, current_user):
    """Override get_db and get_current_user dependencies."""
    from app.database import get_db
    from app.dependencies import get_current_user as gcu

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[gcu] = lambda: current_user


# ---------------------------------------------------------------------------
# 1. List tenants — admin can list users
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_tenants(mock_db, admin_user, admin_auth_headers):
    """GET /api/admin/tenants returns paginated user list for admin."""
    user1 = _fake_user_model(id="u1", name="User One", email="one@test.io")
    user2 = _fake_user_model(id="u2", name="User Two", email="two@test.io")

    call_count = 0

    async def _mock_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # Count query
            result.scalar.return_value = 2
        elif call_count == 2:
            # List query
            scalars = MagicMock()
            scalars.all.return_value = [user1, user2]
            result.scalars.return_value = scalars
        elif call_count <= 4:
            # Project count queries (one per user)
            result.scalar.return_value = 3
        else:
            # Quota queries
            result.scalar_one_or_none.return_value = None
        return result

    mock_db.execute = AsyncMock(side_effect=_mock_execute)

    app = _make_app()
    _override_deps(app, mock_db, admin_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/admin/tenants", headers=admin_auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 2
    assert len(data["items"]) == 2
    for item in data["items"]:
        assert "id" in item
        assert "name" in item
        assert "email" in item
        assert "plan" in item
        assert "created_at" in item


# ---------------------------------------------------------------------------
# 2. List tenants — non-admin gets 403
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_tenants_non_admin(mock_db, test_user, auth_headers):
    """GET /api/admin/tenants returns 403 for non-admin user."""
    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/admin/tenants", headers=auth_headers)

    assert resp.status_code == 403
    assert "admin" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. System stats (overview) — admin gets system metrics
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_overview(mock_db, admin_user, admin_auth_headers):
    """GET /api/admin/overview returns system-wide statistics."""
    # All count queries return a scalar
    mock_result = MagicMock()
    mock_result.scalar.return_value = 42
    mock_db.execute = AsyncMock(return_value=mock_result)

    app = _make_app()
    _override_deps(app, mock_db, admin_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/admin/overview", headers=admin_auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "timestamp" in data
    assert "users" in data
    assert "projects" in data
    assert "builds" in data
    assert "deploys" in data
    # Check nested structure
    assert "total" in data["users"]
    assert "today" in data["builds"]
    assert "this_month" in data["builds"]
    assert "active" in data["builds"]
    assert "failed_today" in data["builds"]


# ---------------------------------------------------------------------------
# 4. System stats (overview) — non-admin gets 403
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_overview_non_admin(mock_db, test_user, auth_headers):
    """GET /api/admin/overview returns 403 for non-admin user."""
    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/admin/overview", headers=auth_headers)

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 5. Suspend tenant — admin can suspend a user
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_suspend_tenant(mock_db, admin_user, admin_auth_headers):
    """POST /api/admin/tenants/{user_id}/suspend cancels active builds."""
    mock_db.execute = AsyncMock(return_value=MagicMock())

    app = _make_app()
    _override_deps(app, mock_db, admin_user)

    target_user_id = "user-to-suspend"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/admin/tenants/{target_user_id}/suspend",
            params={"reason": "abuse"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == target_user_id
    assert data["action"] == "suspended"
    assert data["reason"] == "abuse"


# ---------------------------------------------------------------------------
# 6. Suspend tenant — non-admin gets 403
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_suspend_non_admin(mock_db, test_user, auth_headers):
    """POST /api/admin/tenants/{user_id}/suspend returns 403 for non-admin."""
    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/admin/tenants/some-user/suspend",
            headers=auth_headers,
        )

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 7. Audit export — admin retrieves audit logs
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_audit_export(mock_db, admin_user, admin_auth_headers):
    """GET /api/admin/audit-export returns audit log entries."""
    now = datetime.utcnow()
    audit1 = MagicMock(
        id="audit-1",
        user_id="user-1",
        action="project.created",
        resource_type="project",
        resource_id="proj-1",
        details={"name": "test"},
        ip_address="127.0.0.1",
        trace_id="trace-001",
        created_at=now,
    )
    audit2 = MagicMock(
        id="audit-2",
        user_id="user-2",
        action="build.triggered",
        resource_type="build",
        resource_id="build-1",
        details=None,
        ip_address="10.0.0.1",
        trace_id="trace-002",
        created_at=now,
    )

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [audit1, audit2]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_db.execute = AsyncMock(return_value=result_mock)

    app = _make_app()
    _override_deps(app, mock_db, admin_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/admin/audit-export",
            params={"days": 7},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    for entry in data:
        assert "id" in entry
        assert "user_id" in entry
        assert "action" in entry
        assert "resource_type" in entry
        assert "created_at" in entry


# ---------------------------------------------------------------------------
# 8. Audit export — non-admin gets 403
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_audit_export_non_admin(mock_db, test_user, auth_headers):
    """GET /api/admin/audit-export returns 403 for non-admin."""
    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/admin/audit-export",
            headers=auth_headers,
        )

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 9. Admin change plan — success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_change_plan(mock_db, admin_user, admin_auth_headers):
    """POST /api/admin/tenants/{user_id}/change-plan updates user plan."""
    # Mock quota lookup returns None (will create new)
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=scalar_mock)

    app = _make_app()
    _override_deps(app, mock_db, admin_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/admin/tenants/user-001/change-plan",
            params={"plan": "pro"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "user-001"
    assert data["plan"] == "pro"
    assert "quotas" in data


# ---------------------------------------------------------------------------
# 10. Admin change plan — invalid plan
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_change_plan_invalid(mock_db, admin_user, admin_auth_headers):
    """POST /api/admin/tenants/{user_id}/change-plan with invalid plan returns 400."""
    app = _make_app()
    _override_deps(app, mock_db, admin_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/admin/tenants/user-001/change-plan",
            params={"plan": "ultra-mega-plan"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 400
    assert "invalid plan" in resp.json()["detail"].lower()
