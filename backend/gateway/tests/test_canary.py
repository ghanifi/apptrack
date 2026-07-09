"""
AppTrack -- Canary Deployment Router Tests
===========================================
Tests for: start_canary_deploy, promote_canary, rollback_deployment, canary_metrics

Router: backend/gateway/app/routers/canary.py
Prefix: /api/deployments (set in router itself)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.routers.canary import router
from app.dependencies import get_current_user
from app.database import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_app(user_override: dict, db_override: AsyncMock) -> FastAPI:
    """Build a minimal FastAPI app with the canary router and dependency overrides."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user_override
    app.dependency_overrides[get_db] = lambda: db_override
    return app


def _make_deployment(status: str = "pending"):
    """Create a mock Deployment ORM object."""
    dep = MagicMock()
    dep.id = "d0000000-0000-4000-8000-000000000001"
    dep.status = status
    dep.created_at = datetime(2025, 6, 1, 12, 0, 0)
    dep.updated_at = datetime(2025, 6, 1, 12, 0, 0)
    return dep


# ===========================================================================
# 1. start_canary_deploy
# ===========================================================================

class TestStartCanaryDeploy:
    """POST /{deployment_id}/canary"""

    @pytest.mark.anyio
    async def test_start_canary_success(self, test_user, mock_db):
        deployment = _make_deployment(status="pending")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deployment
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/d0000000-0000-4000-8000-000000000001/canary?initial_percentage=10")

        assert resp.status_code == 200
        data = resp.json()
        assert data["deployment_id"] == "d0000000-0000-4000-8000-000000000001"
        assert data["status"] == "canary"
        assert data["canary_percentage"] == 10
        assert "promote" in data["actions"]
        assert "rollback" in data["actions"]
        # Verify deployment status was updated
        assert deployment.status == "canary"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_start_canary_default_percentage(self, test_user, mock_db):
        deployment = _make_deployment(status="published")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deployment
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/d0000000-0000-4000-8000-000000000001/canary")

        assert resp.status_code == 200
        assert resp.json()["canary_percentage"] == 5  # default

    @pytest.mark.anyio
    async def test_start_canary_invalid_percentage_too_low(self, test_user, mock_db):
        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/d0000000-0000-4000-8000-000000000001/canary?initial_percentage=0")

        assert resp.status_code == 400
        assert "between 1 and 50" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_start_canary_invalid_percentage_too_high(self, test_user, mock_db):
        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/d0000000-0000-4000-8000-000000000001/canary?initial_percentage=51")

        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_start_canary_deployment_not_found(self, test_user, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/deploy-999/canary?initial_percentage=5")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.anyio
    async def test_start_canary_wrong_status(self, test_user, mock_db):
        deployment = _make_deployment(status="rolled_back")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deployment
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/d0000000-0000-4000-8000-000000000001/canary?initial_percentage=5")

        assert resp.status_code == 400
        assert "Cannot start canary" in resp.json()["detail"]


# ===========================================================================
# 2. promote_canary
# ===========================================================================

class TestPromoteCanary:
    """POST /{deployment_id}/promote"""

    @pytest.mark.anyio
    async def test_promote_success(self, test_user, mock_db):
        deployment = _make_deployment(status="canary")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deployment
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/d0000000-0000-4000-8000-000000000001/promote")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "published"
        assert "100%" in data["message"]
        assert deployment.status == "published"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_promote_not_found(self, test_user, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/deploy-999/promote")

        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_promote_wrong_status(self, test_user, mock_db):
        deployment = _make_deployment(status="pending")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deployment
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/d0000000-0000-4000-8000-000000000001/promote")

        assert resp.status_code == 400
        assert "Only canary" in resp.json()["detail"]


# ===========================================================================
# 3. rollback_deployment
# ===========================================================================

class TestRollbackDeployment:
    """POST /{deployment_id}/rollback"""

    @pytest.mark.anyio
    async def test_rollback_canary_success(self, test_user, mock_db):
        deployment = _make_deployment(status="canary")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deployment
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/d0000000-0000-4000-8000-000000000001/rollback?reason=high+error+rate")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rolled_back"
        assert data["reason"] == "high error rate"
        assert deployment.status == "rolled_back"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_rollback_published_success(self, test_user, mock_db):
        deployment = _make_deployment(status="published")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deployment
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/d0000000-0000-4000-8000-000000000001/rollback")

        assert resp.status_code == 200
        assert resp.json()["status"] == "rolled_back"
        assert resp.json()["reason"] == "Manual rollback"  # default reason

    @pytest.mark.anyio
    async def test_rollback_not_found(self, test_user, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/d0000000-0000-4000-8000-000000000001/rollback")

        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_rollback_invalid_status(self, test_user, mock_db):
        deployment = _make_deployment(status="rolled_back")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deployment
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/deployments/d0000000-0000-4000-8000-000000000001/rollback")

        assert resp.status_code == 400
        assert "Cannot rollback" in resp.json()["detail"]


# ===========================================================================
# 4. canary_metrics (get_status)
# ===========================================================================

class TestCanaryMetrics:
    """GET /{deployment_id}/canary-metrics"""

    @pytest.mark.anyio
    async def test_metrics_canary_status(self, test_user, mock_db):
        deployment = _make_deployment(status="canary")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deployment
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/deployments/d0000000-0000-4000-8000-000000000001/canary-metrics")

        assert resp.status_code == 200
        data = resp.json()
        assert data["deployment_id"] == "d0000000-0000-4000-8000-000000000001"
        assert data["status"] == "canary"
        assert data["health"]["recommendation"] == "safe_to_promote"
        assert data["health"]["crash_free_sessions"] == 99.9
        assert data["health"]["error_rate"] == 0.0
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.anyio
    async def test_metrics_published_status(self, test_user, mock_db):
        deployment = _make_deployment(status="published")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deployment
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/deployments/d0000000-0000-4000-8000-000000000001/canary-metrics")

        assert resp.status_code == 200
        data = resp.json()
        assert data["health"]["recommendation"] == "n/a"

    @pytest.mark.anyio
    async def test_metrics_not_found(self, test_user, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/deployments/deploy-999/canary-metrics")

        assert resp.status_code == 404
