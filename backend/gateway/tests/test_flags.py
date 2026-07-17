"""
AppTrack -- Feature Flags Router Tests
=======================================
Tests for: create_flag, update_flag (toggle), check_flag (evaluate), list_flags

Router: backend/gateway/app/routers/flags.py
Prefix: /api/flags (set in main.py include_router)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.routers.flags import router
from app.dependencies import get_current_user
from app.database import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_app(user_override: dict, db_override: AsyncMock) -> FastAPI:
    """Build a minimal FastAPI app with the flags router and dependency overrides."""
    app = FastAPI()
    app.include_router(router, prefix="/api/flags")
    app.dependency_overrides[get_current_user] = lambda: user_override
    app.dependency_overrides[get_db] = lambda: db_override
    return app


def _make_flag(
    flag_id: str = "flag-001",
    name: str = "dark_mode",
    enabled: bool = False,
    description: str = "Dark mode toggle",
    percentage: int = 0,
    allowed_users: dict = None,
):
    """Create a mock FeatureFlag ORM object."""
    flag = MagicMock()
    flag.id = flag_id
    flag.name = name
    flag.enabled = enabled
    flag.description = description
    flag.percentage = percentage
    flag.allowed_users = allowed_users
    flag.updated_at = datetime(2025, 6, 1, 12, 0, 0)
    return flag


# ===========================================================================
# 1. create_flag
# ===========================================================================

class TestCreateFlag:
    """POST /api/flags"""

    @pytest.mark.anyio
    @patch("app.routers.flags.invalidate_cache")
    async def test_create_flag_success(self, mock_invalidate, admin_user, mock_db):
        created_flag = _make_flag(name="new_feature", enabled=True)
        mock_db.refresh = AsyncMock(return_value=None)

        # After db.refresh, the flag object should have id/name/enabled
        async def fake_refresh(obj):
            obj.id = created_flag.id
            obj.name = created_flag.name
            obj.enabled = created_flag.enabled

        mock_db.refresh.side_effect = fake_refresh

        app = _build_app(admin_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/flags",
                json={"name": "new_feature", "enabled": True, "description": "A new feature", "percentage": 50},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "new_feature"
        assert data["enabled"] is True
        assert "id" in data
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_invalidate.assert_called_once()

    @pytest.mark.anyio
    @patch("app.routers.flags.invalidate_cache")
    async def test_create_flag_defaults(self, mock_invalidate, admin_user, mock_db):
        """Flag created with defaults: enabled=False, percentage=0."""
        async def fake_refresh(obj):
            obj.id = "flag-002"
            obj.name = "beta_ui"
            obj.enabled = False

        mock_db.refresh.side_effect = fake_refresh

        app = _build_app(admin_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/flags", json={"name": "beta_ui"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        mock_db.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_create_flag_missing_name(self, admin_user, mock_db):
        """Name is required."""
        app = _build_app(admin_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/flags", json={})

        assert resp.status_code == 422  # validation error


# ===========================================================================
# 2. update_flag (toggle_flag)
# ===========================================================================

class TestUpdateFlag:
    """PATCH /api/flags/{flag_name}"""

    @pytest.mark.anyio
    @patch("app.routers.flags.invalidate_cache")
    async def test_toggle_flag_enable(self, mock_invalidate, admin_user, mock_db):
        flag = _make_flag(name="dark_mode", enabled=False)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = flag
        mock_db.execute.return_value = mock_result

        app = _build_app(admin_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.patch("/api/flags/dark_mode", json={"enabled": True})

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "dark_mode"
        assert data["enabled"] is True
        assert flag.enabled is True
        mock_db.commit.assert_awaited_once()
        mock_invalidate.assert_called_once()

    @pytest.mark.anyio
    @patch("app.routers.flags.invalidate_cache")
    async def test_toggle_flag_disable(self, mock_invalidate, admin_user, mock_db):
        flag = _make_flag(name="dark_mode", enabled=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = flag
        mock_db.execute.return_value = mock_result

        app = _build_app(admin_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.patch("/api/flags/dark_mode", json={"enabled": False})

        assert resp.status_code == 200
        assert flag.enabled is False

    @pytest.mark.anyio
    @patch("app.routers.flags.invalidate_cache")
    async def test_update_flag_percentage(self, mock_invalidate, admin_user, mock_db):
        flag = _make_flag(name="gradual_rollout", percentage=0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = flag
        mock_db.execute.return_value = mock_result

        app = _build_app(admin_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.patch("/api/flags/gradual_rollout", json={"percentage": 25})

        assert resp.status_code == 200
        assert flag.percentage == 25

    @pytest.mark.anyio
    @patch("app.routers.flags.invalidate_cache")
    async def test_update_flag_description(self, mock_invalidate, admin_user, mock_db):
        flag = _make_flag(name="beta", description="Old desc")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = flag
        mock_db.execute.return_value = mock_result

        app = _build_app(admin_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.patch("/api/flags/beta", json={"description": "Updated desc"})

        assert resp.status_code == 200
        assert flag.description == "Updated desc"

    @pytest.mark.anyio
    async def test_update_flag_not_found(self, admin_user, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        app = _build_app(admin_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.patch("/api/flags/nonexistent", json={"enabled": True})

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ===========================================================================
# 3. check_flag (evaluate_flag)
# ===========================================================================

class TestCheckFlag:
    """GET /api/flags/check/{flag_name}"""

    @pytest.mark.anyio
    @patch("app.routers.flags.is_enabled", new_callable=AsyncMock)
    async def test_check_flag_enabled(self, mock_is_enabled, test_user, mock_db):
        mock_is_enabled.return_value = True

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/flags/check/dark_mode")

        assert resp.status_code == 200
        data = resp.json()
        assert data["flag"] == "dark_mode"
        assert data["enabled"] is True
        mock_is_enabled.assert_awaited_once_with(mock_db, "dark_mode", test_user["id"])

    @pytest.mark.anyio
    @patch("app.routers.flags.is_enabled", new_callable=AsyncMock)
    async def test_check_flag_disabled(self, mock_is_enabled, test_user, mock_db):
        mock_is_enabled.return_value = False

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/flags/check/experimental")

        assert resp.status_code == 200
        data = resp.json()
        assert data["flag"] == "experimental"
        assert data["enabled"] is False


# ===========================================================================
# 4. list_flags
# ===========================================================================

class TestListFlags:
    """GET /api/flags"""

    @pytest.mark.anyio
    async def test_list_flags_returns_all(self, test_user, mock_db):
        flags = [
            _make_flag("f1", "alpha_feature", True),
            _make_flag("f2", "beta_feature", False),
            _make_flag("f3", "dark_mode", True, percentage=50),
        ]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = flags
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/flags")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["name"] == "alpha_feature"
        assert data[0]["enabled"] is True
        assert data[1]["name"] == "beta_feature"
        assert data[2]["name"] == "dark_mode"
        # Verify structure
        for item in data:
            assert "id" in item
            assert "name" in item
            assert "enabled" in item
            assert "description" in item
            assert "percentage" in item
            assert "updated_at" in item

    @pytest.mark.anyio
    async def test_list_flags_empty(self, test_user, mock_db):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/flags")

        assert resp.status_code == 200
        assert resp.json() == []
