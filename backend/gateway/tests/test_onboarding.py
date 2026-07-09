"""
AppTrack -- Onboarding Checklist Router Tests
=============================================
Tests for: onboarding_status (GET /api/onboarding/status)

Router: backend/gateway/app/routers/onboarding.py
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.routers.onboarding import router
from app.dependencies import get_current_user
from app.database import get_db

USER = {"id": "550e8400-e29b-41d4-a716-446655440000", "email": "u@apptrack.io", "name": "U"}


def _build_app(db_override: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_db] = lambda: db_override
    from app.limiter import limiter
    app.state.limiter = limiter
    return app


def _make_db(project_count: int, framework: bool, has_build: bool, has_deploy: bool) -> AsyncMock:
    """execute() sirasi: count(Project), exists(framework), exists(build), exists(deploy)."""
    db = AsyncMock()
    results = []
    for value in (project_count, framework, has_build, has_deploy):
        r = MagicMock()
        r.scalar.return_value = value
        results.append(r)
    db.execute.side_effect = results
    return db


@pytest.mark.asyncio
async def test_fresh_user_all_incomplete():
    db = _make_db(project_count=0, framework=False, has_build=False, has_deploy=False)
    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.get("/api/onboarding/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["completed"] == 0
    assert data["all_done"] is False
    assert [s["done"] for s in data["steps"]] == [False, False, False, False]


@pytest.mark.asyncio
async def test_repo_connected_only():
    db = _make_db(project_count=2, framework=False, has_build=False, has_deploy=False)
    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.get("/api/onboarding/status")
    data = resp.json()
    assert data["completed"] == 1
    assert data["steps"][0] == {"key": "connect_repo", "done": True}
    assert data["all_done"] is False


@pytest.mark.asyncio
async def test_all_steps_done():
    db = _make_db(project_count=1, framework=True, has_build=True, has_deploy=True)
    app = _build_app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.get("/api/onboarding/status")
    data = resp.json()
    assert data["completed"] == 4
    assert data["all_done"] is True
