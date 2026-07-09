"""
AppTrack -- Preview Router Tests
=================================
Tests for: start_preview, get_preview (get_status), stop_preview

The preview router proxies all requests to an external preview-service
via httpx. All tests mock httpx.AsyncClient to avoid real HTTP calls.

Router: backend/gateway/app/routers/preview.py
Prefix: /api/preview (set in main.py include_router)

NOTE: The router has no screenshot endpoint. Tests cover: start, get, stop.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.routers.preview import router
from app.dependencies import get_current_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_app(user_override: dict) -> FastAPI:
    """Build a minimal FastAPI app with the preview router and auth override."""
    app = FastAPI()
    app.include_router(router, prefix="/api/preview")
    app.dependency_overrides[get_current_user] = lambda: user_override
    return app


def _mock_httpx_response(status_code: int = 200, json_data: dict = None):
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


@asynccontextmanager
async def _mock_client(response):
    """Async context manager that mimics httpx.AsyncClient."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    client.delete = AsyncMock(return_value=response)
    yield client


# ===========================================================================
# 1. start_preview
# ===========================================================================

class TestStartPreview:
    """POST /api/preview/{project_id}/start"""

    @pytest.mark.anyio
    @patch("app.routers.preview.httpx.AsyncClient")
    async def test_start_preview_success(self, mock_client_cls, test_user):
        response_data = {
            "project_id": "proj-001",
            "status": "running",
            "url": "https://preview.apptrack.io/proj-001",
        }
        mock_resp = _mock_httpx_response(200, response_data)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        app = _build_app(test_user)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/preview/proj-001/start",
                json={"framework": "react-native", "project_path": "/app"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "proj-001"
        assert data["status"] == "running"

    @pytest.mark.anyio
    @patch("app.routers.preview.httpx.AsyncClient")
    async def test_start_preview_service_error(self, mock_client_cls, test_user):
        mock_resp = _mock_httpx_response(500)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        app = _build_app(test_user)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/preview/proj-001/start",
                json={"framework": "react-native"},
            )

        assert resp.status_code == 500
        assert "Preview service error" in resp.json()["detail"]

    @pytest.mark.anyio
    @patch("app.routers.preview.httpx.AsyncClient")
    async def test_start_preview_service_unavailable(self, mock_client_cls, test_user):
        """When preview service is completely unreachable, return 503."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=ConnectionError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        app = _build_app(test_user)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/preview/proj-001/start",
                json={"framework": "react-native"},
            )

        assert resp.status_code == 503
        assert "unavailable" in resp.json()["detail"].lower()

    @pytest.mark.anyio
    async def test_start_preview_missing_framework(self, test_user):
        """Framework is required in the request body."""
        app = _build_app(test_user)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/preview/proj-001/start", json={})

        assert resp.status_code == 422  # validation error


# ===========================================================================
# 2. get_preview (get_status)
# ===========================================================================

class TestGetPreview:
    """GET /api/preview/{project_id}"""

    @pytest.mark.anyio
    @patch("app.routers.preview.httpx.AsyncClient")
    async def test_get_preview_running(self, mock_client_cls, test_user):
        response_data = {
            "project_id": "proj-001",
            "status": "running",
            "url": "https://preview.apptrack.io/proj-001",
        }
        mock_resp = _mock_httpx_response(200, response_data)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        app = _build_app(test_user)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/preview/proj-001")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["project_id"] == "proj-001"

    @pytest.mark.anyio
    @patch("app.routers.preview.httpx.AsyncClient")
    async def test_get_preview_not_ready(self, mock_client_cls, test_user):
        """Non-200 response from preview service returns not_ready."""
        mock_resp = _mock_httpx_response(404)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        app = _build_app(test_user)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/preview/proj-001")

        assert resp.status_code == 200
        assert resp.json()["status"] == "not_ready"

    @pytest.mark.anyio
    @patch("app.routers.preview.httpx.AsyncClient")
    async def test_get_preview_service_down(self, mock_client_cls, test_user):
        """If preview service is unreachable, return not_ready (graceful)."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        app = _build_app(test_user)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/preview/proj-001")

        assert resp.status_code == 200
        assert resp.json()["status"] == "not_ready"


# ===========================================================================
# 3. stop_preview
# ===========================================================================

class TestStopPreview:
    """DELETE /api/preview/{project_id}"""

    @pytest.mark.anyio
    @patch("app.routers.preview.httpx.AsyncClient")
    async def test_stop_preview_success(self, mock_client_cls, test_user):
        response_data = {"status": "stopped", "project_id": "proj-001"}
        mock_resp = _mock_httpx_response(200, response_data)
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        app = _build_app(test_user)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/preview/proj-001")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopped"

    @pytest.mark.anyio
    @patch("app.routers.preview.httpx.AsyncClient")
    async def test_stop_preview_service_error(self, mock_client_cls, test_user):
        mock_resp = _mock_httpx_response(500)
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        app = _build_app(test_user)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/preview/proj-001")

        assert resp.status_code == 500
        assert "Preview service error" in resp.json()["detail"]

    @pytest.mark.anyio
    @patch("app.routers.preview.httpx.AsyncClient")
    async def test_stop_preview_service_unavailable(self, mock_client_cls, test_user):
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(side_effect=ConnectionError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        app = _build_app(test_user)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/preview/proj-001")

        assert resp.status_code == 503
        assert "unavailable" in resp.json()["detail"].lower()


# ===========================================================================
# 4. get_screenshot -- Router has no screenshot endpoint
#    Testing that a request to a non-existent screenshot path returns 404/405
# ===========================================================================

class TestScreenshotNotImplemented:
    """Verify no screenshot endpoint exists on the preview router."""

    @pytest.mark.anyio
    async def test_screenshot_endpoint_not_found(self, test_user):
        app = _build_app(test_user)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/preview/proj-001/screenshot")

        # Should be 404 or 405 since the endpoint does not exist
        assert resp.status_code in (404, 405)
