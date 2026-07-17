"""
AppTrack — Billing Router Tests
=================================
Tests for backend/gateway/app/routers/billing.py

Covers: list_plans, subscribe (upgrade), cancel_subscription (downgrade),
        webhook_handler (Stripe), usage_check (current plan)
"""
import os
import sys
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Build a minimal FastAPI app with the billing router.

    Note: billing router has its own prefix="/api/billing" built in.
    """
    from fastapi import FastAPI
    from app.routers import billing

    app = FastAPI()
    app.include_router(billing.router)
    return app


def _fake_quota(**overrides):
    """Return a MagicMock that behaves like a UserQuota ORM instance."""
    now = datetime.utcnow()
    defaults = dict(
        id="quota-001",
        user_id="550e8400-e29b-41d4-a716-446655440000",
        plan="free",
        max_projects=3,
        max_builds_per_month=10,
        max_deploys_per_month=5,
        max_storage_mb=500,
        max_concurrent_builds=1,
        max_preview_sessions=2,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    quota = MagicMock()
    for k, v in defaults.items():
        setattr(quota, k, v)
    return quota


def _override_deps(app, mock_db, current_user):
    """Override get_db and get_current_user dependencies."""
    from app.database import get_db
    from app.dependencies import get_current_user as gcu

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[gcu] = lambda: current_user


# ---------------------------------------------------------------------------
# 1. List plans — returns all available plans
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_plans():
    """GET /api/billing/plans returns all plans with pricing."""
    app = _make_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/billing/plans")

    assert resp.status_code == 200
    data = resp.json()
    assert "plans" in data
    plans = data["plans"]
    assert isinstance(plans, list)
    assert len(plans) >= 3  # free, pro, enterprise

    plan_names = [p["name"] for p in plans]
    assert "free" in plan_names
    assert "pro" in plan_names
    assert "enterprise" in plan_names

    for plan in plans:
        assert "name" in plan
        assert "price_usd" in plan
        assert "features" in plan
        assert isinstance(plan["price_usd"], (int, float))


# ---------------------------------------------------------------------------
# 2. List plans — free plan has zero price
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_plans_free_is_zero():
    """GET /api/billing/plans — free plan price should be 0."""
    app = _make_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/billing/plans")

    assert resp.status_code == 200
    plans = resp.json()["plans"]
    free_plan = next(p for p in plans if p["name"] == "free")
    assert free_plan["price_usd"] == 0


# ---------------------------------------------------------------------------
# 3. Subscribe (upgrade) — from free to pro
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upgrade_plan(mock_db, test_user, auth_headers):
    """POST /api/billing/upgrade?plan=pro returns checkout redirect info."""
    quota = _fake_quota(plan="free", user_id=test_user["id"])

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.billing.get_or_create_quota", new_callable=AsyncMock, return_value=quota):
            resp = await ac.post(
                "/api/billing/upgrade",
                params={"plan": "pro"},
                headers=auth_headers,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "redirect_to_checkout"
    assert data["current_plan"] == "free"
    assert data["target_plan"] == "pro"
    assert data["price_usd"] == 29
    assert "message" in data


# ---------------------------------------------------------------------------
# 4. Subscribe (upgrade) — invalid plan
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upgrade_invalid_plan(mock_db, test_user, auth_headers):
    """POST /api/billing/upgrade?plan=invalid returns 400."""
    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/billing/upgrade",
            params={"plan": "nonexistent-plan"},
            headers=auth_headers,
        )

    assert resp.status_code == 400
    assert "invalid plan" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Subscribe (upgrade) — cannot downgrade via upgrade endpoint
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upgrade_cannot_downgrade(mock_db, test_user, auth_headers):
    """POST /api/billing/upgrade from pro to free returns 400."""
    quota = _fake_quota(plan="pro", user_id=test_user["id"])

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.billing.get_or_create_quota", new_callable=AsyncMock, return_value=quota):
            resp = await ac.post(
                "/api/billing/upgrade",
                params={"plan": "free"},
                headers=auth_headers,
            )

    assert resp.status_code == 400
    assert "cannot upgrade" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 6. Cancel subscription (downgrade) — from pro to free
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_downgrade_plan(mock_db, test_user, auth_headers):
    """POST /api/billing/downgrade?plan=free downgrades the plan."""
    quota = _fake_quota(plan="pro", user_id=test_user["id"])

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.billing.get_or_create_quota", new_callable=AsyncMock, return_value=quota):
            resp = await ac.post(
                "/api/billing/downgrade",
                params={"plan": "free"},
                headers=auth_headers,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "free"
    assert data["price_usd"] == 0
    assert "quotas" in data
    assert "message" in data
    assert "downgraded" in data["message"].lower()


# ---------------------------------------------------------------------------
# 7. Cancel subscription (downgrade) — cannot upgrade via downgrade endpoint
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_downgrade_cannot_upgrade(mock_db, test_user, auth_headers):
    """POST /api/billing/downgrade from free to pro returns 400."""
    quota = _fake_quota(plan="free", user_id=test_user["id"])

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.billing.get_or_create_quota", new_callable=AsyncMock, return_value=quota):
            resp = await ac.post(
                "/api/billing/downgrade",
                params={"plan": "pro"},
                headers=auth_headers,
            )

    assert resp.status_code == 400
    assert "cannot downgrade" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 8. Webhook handler — valid Stripe event processed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stripe_webhook_valid(mock_db):
    """POST /api/billing/webhook/stripe processes a valid event."""
    event_payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer_details": {"email": "buyer@apptrack.io"},
                "line_items": {
                    "data": [{"price": {"id": "price_pro_monthly"}}],
                },
            },
        },
    }

    app = _make_app()
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.billing.STRIPE_WEBHOOK_SECRET", "whsec_test"), patch("app.routers.billing.verify_stripe_signature", return_value=True):
            with patch("app.routers.billing.handle_checkout_completed", new_callable=AsyncMock) as mock_handler:
                resp = await ac.post(
                    "/api/billing/webhook/stripe",
                    content=json.dumps(event_payload),
                    headers={"Content-Type": "application/json"},
                )

    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
    mock_handler.assert_called_once()


# ---------------------------------------------------------------------------
# 9. Webhook handler — invalid JSON
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stripe_webhook_invalid_json(mock_db):
    """POST /api/billing/webhook/stripe with invalid JSON returns 400."""
    app = _make_app()
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.billing.STRIPE_WEBHOOK_SECRET", "whsec_test"), patch("app.routers.billing.verify_stripe_signature", return_value=True):
            resp = await ac.post(
                "/api/billing/webhook/stripe",
                content="this is not json{{{",
                headers={"Content-Type": "application/json"},
            )

    assert resp.status_code == 400
    assert "invalid json" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 10. Webhook handler — unhandled event type still returns 200
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stripe_webhook_unhandled_event(mock_db):
    """POST /api/billing/webhook/stripe with unknown event type returns 200."""
    event_payload = {
        "type": "some.unknown.event",
        "data": {"object": {}},
    }

    app = _make_app()
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.billing.STRIPE_WEBHOOK_SECRET", "whsec_test"), patch("app.routers.billing.verify_stripe_signature", return_value=True):
            resp = await ac.post(
                "/api/billing/webhook/stripe",
                content=json.dumps(event_payload),
                headers={"Content-Type": "application/json"},
            )

    assert resp.status_code == 200
    assert resp.json()["received"] is True


# ---------------------------------------------------------------------------
# 11. Usage check — current plan returns quota info
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_current_plan(mock_db, test_user, auth_headers):
    """GET /api/billing/current returns current plan and quotas."""
    quota = _fake_quota(plan="pro", user_id=test_user["id"],
                        max_projects=20, max_builds_per_month=100)

    app = _make_app()
    _override_deps(app, mock_db, test_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("app.routers.billing.get_or_create_quota", new_callable=AsyncMock, return_value=quota):
            resp = await ac.get(
                "/api/billing/current",
                headers=auth_headers,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "pro"
    assert data["price_usd"] == 29
    assert "quotas" in data
    quotas = data["quotas"]
    assert quotas["max_projects"] == 20
    assert quotas["max_builds_per_month"] == 100
    assert "max_deploys_per_month" in quotas
    assert "max_storage_mb" in quotas
    assert "max_concurrent_builds" in quotas
    assert "max_preview_sessions" in quotas


# ---------------------------------------------------------------------------
# 12. Usage check — unauthenticated access
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_current_plan_unauthenticated(mock_db):
    """GET /api/billing/current without auth returns 401/403."""
    app = _make_app()
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/billing/current")

    # FastAPI HTTPBearer returns 403 by default when no token is provided
    assert resp.status_code in (401, 403)
