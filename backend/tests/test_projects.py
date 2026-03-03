"""
AppTrack — Projects Router Tests
=================================
Tests for backend/gateway/app/routers/projects.py

Covers: create_project, list_projects, get_project, update_project,
        delete_project, framework_detection (via serialization)
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
    """Build a minimal FastAPI app with the projects router."""
    from fastapi import FastAPI
    from app.routers import projects

    app = FastAPI()
    app.include_router(projects.router, prefix="/api/projects")
    return app


def _fake_project(**overrides):
    """Return a MagicMock that behaves like a Project ORM instance."""
    now = datetime.utcnow()
    defaults = dict(
        id="660e8400-e29b-41d4-a716-446655440000",
        owner_id="550e8400-e29b-41d4-a716-446655440000",
        name="test-app",
        repo_url="https://github.com/test/test-app",
        branch="main",
        framework="react_native",
        status="active",
        clone_path=None,
        created_at=now,
        updated_at=now,
        builds=[],
    )
    defaults.update(overrides)
    project = MagicMock()
    for k, v in defaults.items():
        setattr(project, k, v)
    return project


def _override_deps(app, mock_db, current_user):
    """Override get_db and get_current_user dependencies."""
    from app.database import get_db
    from app.dependencies import get_current_user as gcu

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[gcu] = lambda: current_user


# ---------------------------------------------------------------------------
# 1. Create project — success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_project(mock_db, test_user, auth_headers):
    """POST /api/projects creates a project and returns 201."""
    project = _fake_project(owner_id=test_user["id"])

    # Mock: db.refresh populates the project attrs
    async def _fake_refresh(obj):
        for attr in ("id", "name", "repo_url", "branch", "framework", "status",
                      "created_at", "updated_at", "owner_id", "builds"):
            setattr(obj, attr, getattr(project, attr))

    mock_db.refresh = AsyncMock(side_effect=_fake_refresh)

    # Mock execute for the user lookup (for GitHub webhook registration)
    user_mock = MagicMock()
    user_mock.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = user_mock

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.projects.validate_repo_url", side_effect=lambda u: u):
            with patch("app.routers.projects.validate_branch", side_effect=lambda b: b):
                with patch("app.routers.projects.check_project_quota", new_callable=AsyncMock):
                    with patch("app.routers.projects.record_audit_with_db", new_callable=AsyncMock):
                        with patch("app.routers.projects.events") as mock_events:
                            mock_events.publish_event = AsyncMock()
                            resp = await ac.post(
                                "/api/projects",
                                json={
                                    "name": "test-app",
                                    "repo_url": "https://github.com/test/test-app",
                                    "branch": "main",
                                },
                                headers=auth_headers,
                            )

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-app"
    assert data["repo_url"] == "https://github.com/test/test-app"
    assert data["branch"] == "main"
    assert "id" in data
    mock_db.add.assert_called_once()


# ---------------------------------------------------------------------------
# 2. List projects — returns paginated results
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_projects(mock_db, test_user, auth_headers):
    """GET /api/projects returns paginated project list."""
    project1 = _fake_project(id="proj-1", name="app-one")
    project2 = _fake_project(id="proj-2", name="app-two")

    call_count = 0

    async def _mock_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # Count query
            result.scalar.return_value = 2
        else:
            # List query
            scalars = MagicMock()
            scalars.all.return_value = [project1, project2]
            result.scalars.return_value = scalars
        return result

    mock_db.execute = AsyncMock(side_effect=_mock_execute)

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/projects", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert data["total"] == 2
    assert len(data["items"]) == 2


# ---------------------------------------------------------------------------
# 3. Get project — found
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_project(mock_db, test_user, auth_headers):
    """GET /api/projects/{id} returns the project when it exists."""
    project = _fake_project(owner_id=test_user["id"])

    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = project
    mock_db.execute.return_value = scalar_mock

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/projects/{project.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == project.id
    assert data["name"] == project.name
    assert data["framework"] == project.framework


# ---------------------------------------------------------------------------
# 4. Get project — not found
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_project_not_found(mock_db, test_user, auth_headers):
    """GET /api/projects/{id} returns 404 for nonexistent project."""
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = scalar_mock

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/projects/nonexistent-id",
            headers=auth_headers,
        )

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Update project — success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_project(mock_db, test_user, auth_headers):
    """PATCH /api/projects/{id} updates project fields."""
    project = _fake_project(owner_id=test_user["id"])

    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = project
    mock_db.execute.return_value = scalar_mock

    async def _fake_refresh(obj):
        obj.name = "updated-app"
        obj.branch = "develop"

    mock_db.refresh = AsyncMock(side_effect=_fake_refresh)

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.patch(
            f"/api/projects/{project.id}",
            json={"name": "updated-app", "branch": "develop"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "updated-app"


# ---------------------------------------------------------------------------
# 6. Delete project — success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_delete_project(mock_db, test_user, auth_headers):
    """DELETE /api/projects/{id} returns 204."""
    project = _fake_project(owner_id=test_user["id"])

    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = project
    mock_db.execute.return_value = scalar_mock

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.delete(
            f"/api/projects/{project.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 204
    mock_db.delete.assert_called_once()


# ---------------------------------------------------------------------------
# 7. Delete project — not owned (404)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_delete_project_not_owned(mock_db, test_user, auth_headers):
    """DELETE /api/projects/{id} returns 404 when project belongs to another user."""
    project = _fake_project(owner_id="someone-else-id")

    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = project
    mock_db.execute.return_value = scalar_mock

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.delete(
            f"/api/projects/{project.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 8. Framework detection — serialization includes framework field
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_framework_detection_in_response(mock_db, test_user, auth_headers):
    """GET /api/projects/{id} includes the detected framework in response."""
    project = _fake_project(
        owner_id=test_user["id"],
        framework="flutter",
    )

    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = project
    mock_db.execute.return_value = scalar_mock

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            f"/api/projects/{project.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["framework"] == "flutter"
    assert "status" in data
    assert "builds" in data


# ---------------------------------------------------------------------------
# 9. Create project — unauthenticated (no auth headers)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_project_unauthenticated(mock_db):
    """POST /api/projects without auth returns 403 or 401."""
    app = _make_app()
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    # Do NOT override get_current_user, so the real dep tries to validate

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/projects", json={
            "name": "hack-app",
            "repo_url": "https://github.com/evil/app",
        })

    # Should be 401 or 403 (FastAPI HTTPBearer returns 403 by default)
    assert resp.status_code in (401, 403, 422)
