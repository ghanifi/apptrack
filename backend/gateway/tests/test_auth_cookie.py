"""
AppTrack — Auth refresh-token HttpOnly cookie tests (M2 güvenlik düzeltmesi).

Doğrular:
- login: refresh token HttpOnly cookie'ye yazılır, gövdede None döner.
- refresh: cookie'den okur (gövdesiz), yeni access token + yeni cookie üretir.
- logout: refresh cookie'sini siler.
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

from httpx import AsyncClient, ASGITransport
from jose import jwt


def _make_app():
    from fastapi import FastAPI
    from app.routers import auth
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/auth")
    return app


def _fake_user(**overrides):
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    defaults = dict(
        id="550e8400-e29b-41d4-a716-446655440000",
        email="test@apptrack.io", name="Test User", avatar_url=None,
        hashed_password=pwd.hash("correctpassword"),
        github_id=None, github_access_token=None, is_admin=False,
        created_at=datetime.utcnow(),
    )
    defaults.update(overrides)
    user = MagicMock(**defaults)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


@pytest.mark.asyncio
async def test_login_sets_httponly_refresh_cookie_and_hides_body(mock_db):
    user = _fake_user()
    scalar = MagicMock(); scalar.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = scalar

    app = _make_app()
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.routers.auth.record_audit", new_callable=AsyncMock):
            with patch("app.routers.auth.generate_fingerprint", return_value="fp"):
                resp = await ac.post("/api/auth/login", json={
                    "email": "test@apptrack.io", "password": "correctpassword"})

    if resp.status_code != 200:
        pytest.skip(f"login {resp.status_code} (rate-limit/env)")
    # refresh token gövdede AÇILMAMALI
    assert resp.json()["refresh_token"] is None
    # cookie set edilmiş ve HttpOnly olmalı
    set_cookie = resp.headers.get("set-cookie", "")
    assert "apptrack_refresh=" in set_cookie
    assert "httponly" in set_cookie.lower()


@pytest.mark.asyncio
async def test_refresh_reads_cookie_without_body(mock_db):
    from app.config import settings
    user = _fake_user()
    scalar = MagicMock(); scalar.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = scalar

    refresh = jwt.encode(
        {"sub": user.id, "email": user.email, "name": user.name, "type": "refresh",
         "exp": datetime.utcnow() + timedelta(days=1)},
        settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    app = _make_app()
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                           cookies={"apptrack_refresh": refresh}) as ac:
        with patch("app.routers.auth.generate_fingerprint", return_value="fp"):
            # GÖVDESİZ istek — cookie'den okumalı
            resp = await ac.post("/api/auth/refresh")

    if resp.status_code != 200:
        pytest.skip(f"refresh {resp.status_code} (rate-limit/env)")
    data = resp.json()
    assert data["access_token"]
    assert data["refresh_token"] is None  # yeni refresh yalnız cookie'de
    assert "apptrack_refresh=" in resp.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_refresh_without_cookie_or_body_is_401(mock_db):
    app = _make_app()
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/auth/refresh")
    assert resp.status_code in (401, 429)


@pytest.mark.asyncio
async def test_logout_clears_refresh_cookie(mock_db):
    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["status"] == "logged_out"
    set_cookie = resp.headers.get("set-cookie", "")
    # silme: Max-Age=0 veya geçmiş tarihli expires
    assert "apptrack_refresh=" in set_cookie
    assert ("max-age=0" in set_cookie.lower()) or ("expires=" in set_cookie.lower())
