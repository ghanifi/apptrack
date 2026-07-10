"""
AppTrack -- Runner Config Tests (self-hosted runner per-project setting)
Tests: PATCH /api/projects/{id} runner_type/runner_labels + serialization.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.routers import projects
from app.database import get_db
from app.dependencies import get_current_user as gcu

USER = {"id": "550e8400-e29b-41d4-a716-446655440000", "email": "u@apptrack.io", "name": "U"}
PID = "660e8400-e29b-41d4-a716-446655440000"


def _fake_project(**overrides):
    now = datetime.utcnow()
    defaults = dict(
        id=PID, owner_id=USER["id"], name="test-app",
        repo_url="https://github.com/test/test-app", branch="main",
        framework="flutter", status="ready", clone_path=None,
        created_at=now, updated_at=now, builds=[],
        repo_visibility="private", runner_type="hosted", runner_labels=None,
    )
    defaults.update(overrides)
    p = MagicMock()
    for k, v in defaults.items():
        setattr(p, k, v)
    return p


def _app(mock_db):
    app = FastAPI()
    app.include_router(projects.router, prefix="/api/projects")
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[gcu] = lambda: USER
    return app


def _db_with(project):
    db = AsyncMock()
    scalar = MagicMock()
    scalar.scalar_one_or_none.return_value = project
    db.execute.return_value = scalar
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_patch_self_hosted_with_labels():
    project = _fake_project()
    db = _db_with(project)
    app = _app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.patch(f"/api/projects/{PID}", json={
            "runner_type": "self_hosted", "runner_labels": "apptrack-ios",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["runner_type"] == "self_hosted"
    assert data["runner_labels"] == "apptrack-ios"


@pytest.mark.asyncio
async def test_patch_invalid_runner_type_422():
    project = _fake_project()
    db = _db_with(project)
    app = _app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.patch(f"/api/projects/{PID}", json={"runner_type": "bogus"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_empty_labels_becomes_null():
    project = _fake_project(runner_type="self_hosted", runner_labels="old")
    db = _db_with(project)
    app = _app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.patch(f"/api/projects/{PID}", json={"runner_labels": "   "})
    assert resp.status_code == 200
    assert resp.json()["runner_labels"] is None


@pytest.mark.asyncio
async def test_get_serializes_runner_fields():
    project = _fake_project(runner_type="self_hosted", runner_labels="apptrack-ios")
    db = _db_with(project)
    app = _app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.get(f"/api/projects/{PID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["runner_type"] == "self_hosted"
    assert data["runner_labels"] == "apptrack-ios"
