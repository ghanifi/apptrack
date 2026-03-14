"""
AppTrack -- SSO (Single Sign-On) Router Tests
===============================================
Tests for: create_provider, list_providers (get_providers),
           sso_authorize (authorize_url), sso_callback (callback_flow),
           delete_provider (disable_provider)

Router: backend/gateway/app/routers/sso.py
Prefix: /api/sso (router prefix="/sso", main.py prefix="/api")
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, Request

from app.routers.sso import router
from app.dependencies import get_current_user
from app.database import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_app(user_override: dict | None, db_override: AsyncMock) -> FastAPI:
    """Build a minimal FastAPI app with SSO router and dependency overrides."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    if user_override is not None:
        app.dependency_overrides[get_current_user] = lambda: user_override
    app.dependency_overrides[get_db] = lambda: db_override

    # Disable rate limiter for tests
    from app.limiter import limiter
    app.state.limiter = limiter

    @app.middleware("http")
    async def add_client_ip(request: Request, call_next):
        if user_override:
            request.state.current_user_id = user_override["id"]
        return await call_next(request)

    return app


def _make_member(role="owner", user_id="test-user-id"):
    m = MagicMock()
    m.id = "mem-001"
    m.org_id = "org-001"
    m.user_id = user_id
    m.role = role
    return m


def _make_provider(
    provider_id="prov-001",
    org_id="org-001",
    provider_type="oidc",
    enabled=False,
    discovery_url="https://idp.example.com/.well-known/openid-configuration",
    client_id="client-abc",
):
    p = MagicMock()
    p.id = provider_id
    p.org_id = org_id
    p.provider_type = provider_type
    p.name = "Corporate SSO"
    p.client_id = client_id
    p.encrypted_client_secret = "encrypted-secret"
    p.discovery_url = discovery_url
    p.metadata_url = None
    p.allowed_domains = "example.com"
    p.enabled = enabled
    p.created_at = datetime(2025, 6, 1)
    p.updated_at = datetime(2025, 6, 1)
    return p


# ===========================================================================
# 1. create_sso_provider
# ===========================================================================

class TestCreateSSOProvider:
    """POST /api/sso/{org_id}/providers"""

    @pytest.mark.anyio
    @patch("app.routers.sso.encrypt", return_value="encrypted-secret")
    async def test_create_provider_success(self, mock_encrypt, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = caller_member
        mock_db.execute.return_value = mock_result

        created_provider = _make_provider()

        async def fake_refresh(obj):
            obj.id = created_provider.id
            obj.provider_type = "oidc"
            obj.name = "Corporate SSO"
            obj.client_id = "client-abc"
            obj.discovery_url = "https://idp.example.com/.well-known/openid-configuration"
            obj.allowed_domains = "example.com"
            obj.enabled = False
            obj.created_at = datetime(2025, 6, 1)

        mock_db.refresh.side_effect = fake_refresh

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/sso/org-001/providers",
                json={
                    "provider_type": "oidc",
                    "name": "Corporate SSO",
                    "client_id": "client-abc",
                    "client_secret": "secret-xyz",
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["provider_type"] == "oidc"
        assert data["client_id"] == "client-abc"
        assert data["enabled"] is False
        assert "id" in data
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_encrypt.assert_called_once_with("secret-xyz")

    @pytest.mark.anyio
    async def test_create_provider_not_admin(self, test_user, mock_db):
        caller_member = _make_member(role="viewer", user_id=test_user["id"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = caller_member
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/sso/org-001/providers",
                json={
                    "client_id": "client-abc",
                    "client_secret": "secret-xyz",
                },
            )

        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_create_provider_not_member(self, test_user, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # not a member
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/sso/org-001/providers",
                json={
                    "client_id": "client-abc",
                    "client_secret": "secret-xyz",
                },
            )

        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_create_provider_missing_client_id(self, test_user, mock_db):
        """client_id is required."""
        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/sso/org-001/providers",
                json={"client_secret": "secret-xyz"},
            )

        assert resp.status_code == 422

    @pytest.mark.anyio
    @patch("app.routers.sso.encrypt", return_value="encrypted-secret")
    @patch("app.routers.sso.httpx.AsyncClient")
    async def test_create_provider_invalid_discovery_url(
        self, mock_httpx_cls, mock_encrypt, test_user, mock_db
    ):
        """OIDC discovery URL validation fails if HTTP is not 200."""
        caller_member = _make_member(role="admin", user_id=test_user["id"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = caller_member
        mock_db.execute.return_value = mock_result

        # Mock httpx client for discovery URL check
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_cls.return_value = mock_client

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/sso/org-001/providers",
                json={
                    "client_id": "client-abc",
                    "client_secret": "secret-xyz",
                    "discovery_url": "https://bad-idp.example.com/.well-known/openid-configuration",
                },
            )

        assert resp.status_code == 400
        assert "discovery" in resp.json()["detail"].lower()


# ===========================================================================
# 2. list_sso_providers (get_providers)
# ===========================================================================

class TestListSSOProviders:
    """GET /api/sso/{org_id}/providers"""

    @pytest.mark.anyio
    async def test_list_providers_success(self, test_user, mock_db):
        caller_member = _make_member(role="member", user_id=test_user["id"])
        providers = [
            _make_provider("prov-001", enabled=True),
            _make_provider("prov-002", provider_type="saml", enabled=False),
        ]

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                mock_scalars = MagicMock()
                mock_scalars.all.return_value = providers
                result.scalars.return_value = mock_scalars
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/sso/org-001/providers")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == "prov-001"
        assert data[1]["provider_type"] == "saml"
        for item in data:
            assert "id" in item
            assert "provider_type" in item
            assert "name" in item
            assert "enabled" in item

    @pytest.mark.anyio
    async def test_list_providers_not_member(self, test_user, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/sso/org-001/providers")

        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_list_providers_empty(self, test_user, mock_db):
        caller_member = _make_member(role="member", user_id=test_user["id"])

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                mock_scalars = MagicMock()
                mock_scalars.all.return_value = []
                result.scalars.return_value = mock_scalars
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/sso/org-001/providers")

        assert resp.status_code == 200
        assert resp.json() == []


# ===========================================================================
# 3. sso_authorize (authorize_url)
# ===========================================================================

class TestSSOAuthorize:
    """GET /api/sso/authorize/{provider_id}"""

    @pytest.mark.anyio
    @patch("app.routers.sso.httpx.AsyncClient")
    async def test_authorize_redirect(self, mock_httpx_cls, test_user, mock_db):
        """Should return a 302 redirect to IdP authorization endpoint."""
        provider = _make_provider(enabled=True)
        mock_db.get = AsyncMock(return_value=provider)

        # Mock OIDC discovery response
        oidc_config = {
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = oidc_config

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_cls.return_value = mock_client

        # Note: sso_authorize does NOT depend on get_current_user, only get_db
        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as ac:
            resp = await ac.get("/api/sso/authorize/prov-001")

        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "idp.example.com/authorize" in location
        assert "client_id=client-abc" in location
        assert "response_type=code" in location
        assert "scope=openid" in location

    @pytest.mark.anyio
    async def test_authorize_provider_not_found(self, test_user, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/sso/authorize/prov-ghost")

        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_authorize_provider_disabled(self, test_user, mock_db):
        provider = _make_provider(enabled=False)
        mock_db.get = AsyncMock(return_value=provider)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/sso/authorize/prov-001")

        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_authorize_non_oidc_provider(self, test_user, mock_db):
        provider = _make_provider(provider_type="saml", enabled=True)
        mock_db.get = AsyncMock(return_value=provider)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/sso/authorize/prov-001")

        assert resp.status_code == 400
        assert "OIDC" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_authorize_no_discovery_url(self, test_user, mock_db):
        provider = _make_provider(enabled=True, discovery_url=None)
        mock_db.get = AsyncMock(return_value=provider)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/sso/authorize/prov-001")

        assert resp.status_code == 400
        assert "discovery" in resp.json()["detail"].lower()


# ===========================================================================
# 4. sso_callback (callback_flow)
# ===========================================================================

class TestSSOCallback:
    """GET /api/sso/callback/{provider_id}"""

    @pytest.mark.anyio
    @patch("app.routers.sso.httpx.AsyncClient")
    @patch("app.routers.sso.decrypt", return_value="plain-secret")
    @patch("app.routers.sso.settings")
    async def test_callback_success_existing_user(
        self, mock_settings, mock_decrypt, mock_httpx_cls, test_user, mock_db
    ):
        """Full callback flow: token exchange -> userinfo -> find user -> redirect."""
        mock_settings.GATEWAY_URL = "http://gateway:8000"
        mock_settings.CORS_ORIGINS = ["http://localhost:3000"]

        provider = _make_provider(enabled=True)
        mock_db.get = AsyncMock(return_value=provider)

        # OIDC discovery
        oidc_config = {
            "token_endpoint": "https://idp.example.com/token",
            "userinfo_endpoint": "https://idp.example.com/userinfo",
        }
        mock_discovery_resp = MagicMock()
        mock_discovery_resp.status_code = 200
        mock_discovery_resp.json.return_value = oidc_config

        # Token exchange response
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "at-123", "id_token": "idt-456"}

        # UserInfo response
        mock_userinfo_resp = MagicMock()
        mock_userinfo_resp.status_code = 200
        mock_userinfo_resp.json.return_value = {
            "email": "test@example.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
        }

        # Mock httpx client -- the callback creates 3 separate httpx.AsyncClient contexts
        call_idx = 0

        def make_client():
            nonlocal call_idx
            call_idx += 1
            client = AsyncMock()
            if call_idx == 1:
                # Discovery fetch
                client.get = AsyncMock(return_value=mock_discovery_resp)
            elif call_idx == 2:
                # Token exchange
                client.post = AsyncMock(return_value=mock_token_resp)
            elif call_idx == 3:
                # UserInfo fetch
                client.get = AsyncMock(return_value=mock_userinfo_resp)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            return client

        mock_httpx_cls.side_effect = lambda **kwargs: make_client()

        # Existing user in DB
        existing_user = MagicMock()
        existing_user.id = "user-existing"
        existing_user.email = "test@example.com"
        existing_user.name = "Test User"

        existing_member = MagicMock()

        db_call = 0

        async def multi_execute(stmt):
            nonlocal db_call
            db_call += 1
            result = MagicMock()
            if db_call == 1:
                # Find user by email
                result.scalar_one_or_none.return_value = existing_user
            elif db_call == 2:
                # Check existing org membership
                result.scalar_one_or_none.return_value = existing_member
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        # Mock JWT creation
        with patch("app.routers.auth.create_access_token", return_value="jwt-access-token"), \
             patch("app.routers.auth.create_refresh_token", return_value="jwt-refresh-token"):

            app = _build_app(None, mock_db)  # No auth required for callback
            transport = ASGITransport(app=app)

            # Pre-populate SSO state store for CSRF validation
            from app.routers.sso import _sso_states
            _sso_states["state-abc"] = {"provider_id": "prov-001"}

            async with AsyncClient(
                transport=transport, base_url="http://test", follow_redirects=False
            ) as ac:
                resp = await ac.get("/api/sso/callback/prov-001?code=auth-code-123&state=state-abc")

        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "sso_token=jwt-access-token" in location
        assert "sso_refresh=jwt-refresh-token" in location
        assert "localhost:3000" in location

    @pytest.mark.anyio
    async def test_callback_provider_not_found(self, test_user, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        app = _build_app(None, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/sso/callback/prov-ghost?code=abc")

        assert resp.status_code == 400
        assert "Gecersiz" in resp.json()["detail"] or "provider" in resp.json()["detail"].lower()

    @pytest.mark.anyio
    async def test_callback_provider_disabled(self, test_user, mock_db):
        provider = _make_provider(enabled=False)
        mock_db.get = AsyncMock(return_value=provider)

        app = _build_app(None, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/sso/callback/prov-001?code=abc")

        assert resp.status_code == 400

    @pytest.mark.anyio
    @patch("app.routers.sso.httpx.AsyncClient")
    @patch("app.routers.sso.decrypt", return_value="plain-secret")
    @patch("app.routers.sso.settings")
    async def test_callback_token_exchange_failure(
        self, mock_settings, mock_decrypt, mock_httpx_cls, test_user, mock_db
    ):
        """Token exchange returns non-200 -> should fail with 401."""
        mock_settings.GATEWAY_URL = "http://gateway:8000"

        provider = _make_provider(enabled=True)
        mock_db.get = AsyncMock(return_value=provider)

        # OIDC discovery
        oidc_config = {
            "token_endpoint": "https://idp.example.com/token",
            "userinfo_endpoint": "https://idp.example.com/userinfo",
        }
        mock_discovery_resp = MagicMock()
        mock_discovery_resp.status_code = 200
        mock_discovery_resp.json.return_value = oidc_config

        # Token exchange fails
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 400
        mock_token_resp.text = "invalid_grant"

        call_idx = 0

        def make_client(**kwargs):
            nonlocal call_idx
            call_idx += 1
            client = AsyncMock()
            if call_idx == 1:
                client.get = AsyncMock(return_value=mock_discovery_resp)
            elif call_idx == 2:
                client.post = AsyncMock(return_value=mock_token_resp)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            return client

        mock_httpx_cls.side_effect = make_client

        app = _build_app(None, mock_db)
        transport = ASGITransport(app=app)

        # Pre-populate SSO state store for CSRF validation
        from app.routers.sso import _sso_states
        _sso_states["test-state"] = {"provider_id": "prov-001"}

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/sso/callback/prov-001?code=bad-code&state=test-state")

        assert resp.status_code == 401
        assert "token" in resp.json()["detail"].lower()


# ===========================================================================
# 5. delete_sso_provider (disable_provider)
# ===========================================================================

class TestDeleteSSOProvider:
    """DELETE /api/sso/{org_id}/providers/{provider_id}"""

    @pytest.mark.anyio
    async def test_delete_provider_success(self, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])
        provider = _make_provider()

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                result.scalar_one_or_none.return_value = provider
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/sso/org-001/providers/prov-001")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"
        assert data["id"] == "prov-001"
        mock_db.delete.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_delete_provider_not_owner(self, test_user, mock_db):
        """Only owner can delete SSO providers."""
        caller_member = _make_member(role="admin", user_id=test_user["id"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = caller_member
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/sso/org-001/providers/prov-001")

        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_delete_provider_not_found(self, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                result.scalar_one_or_none.return_value = None
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/sso/org-001/providers/prov-ghost")

        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_provider_not_member(self, test_user, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # not a member at all
        mock_db.execute.return_value = mock_result

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/sso/org-001/providers/prov-001")

        assert resp.status_code == 403


# ===========================================================================
# 6. update_sso_provider (enable/disable toggle)
# ===========================================================================

class TestUpdateSSOProvider:
    """PUT /api/sso/{org_id}/providers/{provider_id}"""

    @pytest.mark.anyio
    @patch("app.routers.sso.encrypt", return_value="new-encrypted-secret")
    async def test_enable_provider(self, mock_encrypt, test_user, mock_db):
        caller_member = _make_member(role="admin", user_id=test_user["id"])
        provider = _make_provider(enabled=False)

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                result.scalar_one_or_none.return_value = provider
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.put(
                "/api/sso/org-001/providers/prov-001",
                json={"enabled": True},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"
        assert data["enabled"] is True
        assert provider.enabled is True
        mock_db.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_update_provider_not_found(self, test_user, mock_db):
        caller_member = _make_member(role="owner", user_id=test_user["id"])

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = caller_member
            elif call_count == 2:
                result.scalar_one_or_none.return_value = None
            return result

        mock_db.execute = AsyncMock(side_effect=multi_execute)

        app = _build_app(test_user, mock_db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.put(
                "/api/sso/org-001/providers/prov-ghost",
                json={"enabled": True},
            )

        assert resp.status_code == 404
