"""H1 regresyon: EAS/Codemagic webhook fail-closed — secret yoksa doğrulama ATLANMAZ."""
import json
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.routers.webhooks import router
from app.routers import webhooks as wh
from app.database import get_db


def _app():
    app = FastAPI()
    app.include_router(router, prefix="/api/webhooks")
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize("path,secret_attr", [
    ("/api/webhooks/eas", "EAS_WEBHOOK_SECRET"),
    ("/api/webhooks/codemagic", "CODEMAGIC_WEBHOOK_SECRET"),
])
async def test_webhook_no_secret_fail_closed(monkeypatch, path, secret_attr):
    """Secret boşsa 503 — eski davranış imzayı hiç kontrol etmeden 200 dönüyordu (H1)."""
    monkeypatch.setattr(wh.settings, secret_attr, "")
    app = _app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(path, content=json.dumps({"x": 1}).encode())
    assert r.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize("path,secret_attr,sig_header", [
    ("/api/webhooks/eas", "EAS_WEBHOOK_SECRET", "x-eas-webhook-signature"),
    ("/api/webhooks/codemagic", "CODEMAGIC_WEBHOOK_SECRET", "x-codemagic-signature"),
])
async def test_webhook_bad_signature_401(monkeypatch, path, secret_attr, sig_header):
    """Secret set ama imza yanlış → 401 (401'ler sızıntısız reddedilir)."""
    monkeypatch.setattr(wh.settings, secret_attr, "s3cr3t")
    app = _app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(path, content=json.dumps({"x": 1}).encode(),
                          headers={sig_header: "deadbeef"})
    assert r.status_code == 401
