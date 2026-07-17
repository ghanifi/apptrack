"""
Business-logic güvenlik regresyonları (SAST H-D / H-E / M-G).

- H-D: Stripe webhook fail-closed (secret yoksa 503, imza yanlışsa 400).
- H-E: record_build_cost imzası (db, user_id, provider, platform) — eski (db, build)
  çağrısı TypeError'dı, aylık bütçe cap'ini ölü bırakıyordu.
- M-G: bilinmeyen price_id -> "free" (yetki yükseltmeyi önler).
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport


def _app():
    from app.routers import billing as billing_router
    from app.database import get_db
    app = FastAPI()
    app.include_router(billing_router.router)

    async def _fake_db():
        yield AsyncMock()
    app.dependency_overrides[get_db] = _fake_db
    return app


@pytest.mark.asyncio
async def test_stripe_webhook_fail_closed_no_secret(monkeypatch):
    """Secret yoksa 503 — auth'suz gövdeden plan set edilemez (H-D)."""
    from app.routers import billing as billing_router
    monkeypatch.setattr(billing_router, "STRIPE_WEBHOOK_SECRET", "")
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as ac:
        resp = await ac.post("/api/billing/webhook/stripe",
                             json={"type": "checkout.session.completed",
                                   "data": {"object": {"metadata": {"plan": "enterprise"}}}})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_stripe_webhook_bad_signature_400(monkeypatch):
    """Secret var ama imza yanlış -> 400 (H-D)."""
    from app.routers import billing as billing_router
    monkeypatch.setattr(billing_router, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as ac:
        resp = await ac.post("/api/billing/webhook/stripe",
                             headers={"stripe-signature": "t=1,v1=deadbeef"},
                             json={"type": "checkout.session.completed", "data": {"object": {}}})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_unknown_price_id_defaults_to_free():
    """Bilinmeyen price_id -> plan 'free' (M-G)."""
    from app import billing as billing_logic
    captured = {}

    async def _capture(db, email, plan, reason):
        captured["plan"] = plan

    with patch.object(billing_logic, "_update_user_plan", _capture):
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)
        await billing_logic.handle_subscription_updated(db, {
            "customer_email": "u@x.io", "id": "sub_1", "status": "active",
            "items": {"data": [{"price": {"id": "price_UNKNOWN_XYZ"}}]},
        })
    assert captured.get("plan") == "free"


@pytest.mark.asyncio
async def test_record_build_cost_signature():
    """record_build_cost 4-arg imzasıyla çalışır; eski 2-arg çağrı TypeError (H-E)."""
    from app.cost_guard import record_build_cost
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)
    # doğru imza — hata atmamalı
    await record_build_cost(db, "user-1", "github_actions", "android")
    db.add.assert_called()  # yeni UsageRecord eklendi
    # eski hatalı çağrı (db, build) -> TypeError (regresyon guard)
    with pytest.raises(TypeError):
        await record_build_cost(db, MagicMock())
