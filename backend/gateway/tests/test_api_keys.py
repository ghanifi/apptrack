"""
AppTrack -- API Keys Tests (programmatic access / MCP)
create, list, revoke, exchange (key -> access token).
"""
import hashlib
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.routers import api_keys as ak
from app.database import get_db
from app.dependencies import get_current_user as gcu

USER = {"id": "550e8400-e29b-41d4-a716-446655440000", "email": "u@apptrack.io", "name": "U"}


def _app(db, with_auth=True):
    app = FastAPI()
    app.include_router(ak.router)
    app.dependency_overrides[get_db] = lambda: db
    if with_auth:
        app.dependency_overrides[gcu] = lambda: USER
    from app.limiter import limiter
    app.state.limiter = limiter
    return app


@pytest.mark.asyncio
async def test_create_returns_raw_key_once():
    db = AsyncMock()
    async def _refresh(obj):
        obj.id = "key-1"
        obj.created_at = datetime.utcnow()
    db.refresh = AsyncMock(side_effect=_refresh)
    app = _app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.post("/api/api-keys", json={"name": "MCP"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["api_key"].startswith("atk_")
    assert data["key_prefix"] == data["api_key"][:12]
    assert data["name"] == "MCP"


@pytest.mark.asyncio
async def test_list_keys_never_returns_raw():
    key = MagicMock()
    key.id = "key-1"; key.name = "MCP"; key.key_prefix = "atk_12345678"
    key.revoked = False; key.last_used_at = None; key.created_at = datetime.utcnow()
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [key]
    db.execute.return_value = result
    app = _app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.get("/api/api-keys")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["key_prefix"] == "atk_12345678"
    assert "api_key" not in item and "key_hash" not in item


@pytest.mark.asyncio
async def test_revoke_missing_404():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    app = _app(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.delete("/api/api-keys/nope")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_exchange_valid_key_returns_token():
    raw = "atk_" + "a" * 48
    key = MagicMock()
    key.id = "key-1"; key.user_id = USER["id"]; key.key_hash = hashlib.sha256(raw.encode()).hexdigest()
    user = MagicMock(); user.id = USER["id"]; user.email = USER["email"]; user.name = "U"

    db = AsyncMock()
    r_key = MagicMock(); r_key.scalar_one_or_none.return_value = key
    r_user = MagicMock(); r_user.scalar_one_or_none.return_value = user
    db.execute.side_effect = [r_key, r_user, MagicMock()]  # select key, select user, update last_used
    app = _app(db, with_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.post("/api/api-keys/exchange", json={"api_key": raw})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_exchange_bad_prefix_401():
    db = AsyncMock()
    app = _app(db, with_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.post("/api/api-keys/exchange", json={"api_key": "nope"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_exchange_unknown_key_401():
    db = AsyncMock()
    r_key = MagicMock(); r_key.scalar_one_or_none.return_value = None
    db.execute.return_value = r_key
    app = _app(db, with_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        resp = await ac.post("/api/api-keys/exchange", json={"api_key": "atk_" + "b" * 48})
    assert resp.status_code == 401
