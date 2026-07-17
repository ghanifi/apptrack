"""
Admin-gate regresyon testi (SAST H-B / missing-auth düzeltmesi).

Platform-geneli ayrıcalıklı uçlar artık require_admin_dep ile kapılı: normal
(is_admin=False) bir kullanıcı 403 almalı. Gate bir route-dependency olduğundan
403, handler gövdesi (DB) çalışmadan döner — bu yüzden DB mock'u gerekmez.
"""
import os
import sys
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from jose import jwt


def _token(is_admin=False):
    from app.config import settings
    payload = {"sub": "u-1", "email": "u@apptrack.io", "name": "U", "type": "access"}
    if is_admin:
        payload["is_admin"] = True
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _app():
    from app.routers import compliance, immutable_audit, metrics_kpi, flags, backups
    app = FastAPI()
    app.include_router(compliance.router)
    app.include_router(immutable_audit.router)
    app.include_router(metrics_kpi.router)
    app.include_router(flags.router, prefix="/api/flags")
    app.include_router(backups.router)
    return app


# (method, path) — gate'lenen 14 uç
GATED = [
    ("post", "/api/compliance/purge-expired"),
    ("post", "/api/compliance/legal-hold/build/x"),
    ("get", "/api/compliance/audit-export"),
    ("get", "/api/immutable-audit/entries"),
    ("get", "/api/immutable-audit/verify"),
    ("get", "/api/immutable-audit/entry/1"),
    ("get", "/api/metrics/platform-kpis"),
    ("post", "/api/flags"),
    ("patch", "/api/flags/some-flag"),
    ("post", "/api/backups/trigger"),
    ("get", "/api/backups/list"),
    ("get", "/api/backups/abc"),
    ("post", "/api/backups/verify-restore"),
    ("get", "/api/backups/stats/summary"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", GATED)
async def test_non_admin_gets_403(method, path):
    app = _app()
    headers = {"Authorization": f"Bearer {_token(is_admin=False)}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await getattr(ac, method)(path, headers=headers)
    assert resp.status_code == 403, f"{method.upper()} {path} -> {resp.status_code} (403 bekleniyordu)"
    assert "admin" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_no_token_gets_401_or_403():
    """Token'sız istek de gate'e takılır (401 kimlik yok / 403)."""
    app = _app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/compliance/purge-expired")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_passes_gate_not_403():
    """Admin token gate'i geçer — 403 DÖNMEZ. get_db mock'lanır ki gerçek DB'ye
    bağlanıp asılmasın; asıl amaç gate'in admin'i geçirmesi (403 olmaması)."""
    from unittest.mock import AsyncMock, MagicMock
    from app.database import get_db
    app = _app()

    async def _fake_db():
        db = AsyncMock()
        scalar = MagicMock()
        scalar.scalar_one_or_none.return_value = None
        scalar.scalars.return_value.all.return_value = []
        scalar.scalar.return_value = 0
        db.execute.return_value = scalar
        yield db

    app.dependency_overrides[get_db] = _fake_db
    headers = {"Authorization": f"Bearer {_token(is_admin=True)}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/metrics/platform-kpis", headers=headers)
    assert resp.status_code != 403
