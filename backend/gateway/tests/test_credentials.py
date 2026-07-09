"""
AppTrack — Credentials Router Tests
=====================================
Tests for backend/gateway/app/routers/credentials.py

Covers: store_credential (upsert), list_credentials, rotate_credential,
        delete_credential, empty_value_guard
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
    """Build a minimal FastAPI app with the credentials router."""
    from fastapi import FastAPI
    from app.routers import credentials

    app = FastAPI()
    app.include_router(credentials.router, prefix="/api/credentials")
    return app


def _fake_credential(**overrides):
    """Return a MagicMock that behaves like a Credential ORM instance."""
    now = datetime.utcnow()
    defaults = dict(
        id="cred-001",
        owner_id="550e8400-e29b-41d4-a716-446655440000",
        provider="eas",
        key_name="EAS_TOKEN",
        encrypted_value="encrypted-value-here",
        key_version="v1",
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    cred = MagicMock()
    for k, v in defaults.items():
        setattr(cred, k, v)
    return cred


def _override_deps(app, mock_db, current_user):
    """Override get_db and get_current_user dependencies."""
    from app.database import get_db
    from app.dependencies import get_current_user as gcu

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[gcu] = lambda: current_user


# ---------------------------------------------------------------------------
# 1. Store credential (upsert) — new credential
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_store_credential_new(mock_db, test_user, auth_headers):
    """PUT /api/credentials creates a new credential when none exists."""
    # DB returns None (no existing credential)
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = scalar_mock

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.credentials.encrypt", return_value="encrypted-value"):
            with patch("app.routers.credentials.record_audit_with_db", new_callable=AsyncMock):
                resp = await ac.put("/api/credentials", json={
                    "provider": "eas",
                    "key_name": "EAS_TOKEN",
                    "value": "my-secret-token",
                }, headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "saved"
    assert data["provider"] == "eas"
    assert data["key_name"] == "EAS_TOKEN"
    mock_db.add.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Store credential (upsert) — update existing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_store_credential_update(mock_db, test_user, auth_headers):
    """PUT /api/credentials updates an existing credential."""
    existing = _fake_credential(owner_id=test_user["id"])
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = existing
    mock_db.execute.return_value = scalar_mock

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.credentials.encrypt", return_value="new-encrypted-val"):
            with patch("app.routers.credentials.record_audit_with_db", new_callable=AsyncMock):
                resp = await ac.put("/api/credentials", json={
                    "provider": "eas",
                    "key_name": "EAS_TOKEN",
                    "value": "updated-secret-token",
                }, headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "saved"
    # The existing credential should be updated (not added)
    mock_db.add.assert_not_called()
    assert existing.encrypted_value == "new-encrypted-val"


# ---------------------------------------------------------------------------
# 3. Store credential — invalid provider/key combination
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_store_credential_invalid_provider(mock_db, test_user, auth_headers):
    """PUT /api/credentials with unknown provider returns 400."""
    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.put("/api/credentials", json={
            "provider": "unknown_provider",
            "key_name": "SOME_KEY",
            "value": "some-value",
        }, headers=auth_headers)

    assert resp.status_code == 400
    assert "unknown provider" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. List credentials — returns credential info without values
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_credentials(mock_db, test_user, auth_headers):
    """GET /api/credentials returns list of credential metadata."""
    cred1 = _fake_credential(id="cred-1", provider="eas", key_name="EAS_TOKEN")
    cred2 = _fake_credential(id="cred-2", provider="codemagic", key_name="CODEMAGIC_TOKEN")

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [cred1, cred2]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_db.execute.return_value = result_mock

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/credentials", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["provider"] == "eas"
    assert data[0]["key_name"] == "EAS_TOKEN"
    # Values should NOT be in the response
    for item in data:
        assert "encrypted_value" not in item
        assert "value" not in item
        assert "id" in item
        assert "created_at" in item
        assert "updated_at" in item


# ---------------------------------------------------------------------------
# 5. Rotate credentials — rotates encryption keys
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rotate_credentials(mock_db, test_user, auth_headers):
    """POST /api/credentials/rotate-keys re-encrypts all credentials."""
    cred1 = _fake_credential(id="cred-1", encrypted_value="old-encrypted-1")
    cred2 = _fake_credential(id="cred-2", encrypted_value="old-encrypted-2")

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [cred1, cred2]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_db.execute.return_value = result_mock

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.credentials.re_encrypt", return_value="new-encrypted"):
            resp = await ac.post("/api/credentials/rotate-keys", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "rotated" in data
    assert "total" in data
    assert data["total"] == 2


# ---------------------------------------------------------------------------
# 6. Delete credential — success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_delete_credential(mock_db, test_user, auth_headers):
    """DELETE /api/credentials/{provider}/{key_name} returns 204."""
    mock_db.execute.return_value = MagicMock()

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.delete(
            "/api/credentials/eas/EAS_TOKEN",
            headers=auth_headers,
        )

    assert resp.status_code == 204
    mock_db.commit.assert_called()


# ---------------------------------------------------------------------------
# 7. Empty value guard — pydantic validation rejects blank values
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_value_guard(mock_db, test_user, auth_headers):
    """PUT /api/credentials with empty value returns 422 validation error."""
    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.put("/api/credentials", json={
            "provider": "eas",
            "key_name": "EAS_TOKEN",
            "value": "",
        }, headers=auth_headers)

    assert resp.status_code == 422
    # Pydantic should catch the empty value via the field_validator


# ---------------------------------------------------------------------------
# 8. Empty value guard — whitespace-only value
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_whitespace_value_guard(mock_db, test_user, auth_headers):
    """PUT /api/credentials with whitespace-only value returns 422."""
    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.put("/api/credentials", json={
            "provider": "eas",
            "key_name": "EAS_TOKEN",
            "value": "   ",
        }, headers=auth_headers)

    assert resp.status_code == 422
