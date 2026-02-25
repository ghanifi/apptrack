import json
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.config import settings
from app.billing import (
    verify_stripe_signature,
    handle_checkout_completed,
    handle_subscription_updated,
    handle_invoice_payment_failed,
    handle_subscription_deleted,
    PLAN_PRICES_USD,
    STRIPE_PLAN_MAP,
)
from app.models import UserQuota
from app.quotas import PLAN_DEFAULTS, get_or_create_quota
from sqlalchemy import select
from datetime import datetime

router = APIRouter(prefix="/api/billing", tags=["billing"])
logger = logging.getLogger(__name__)

STRIPE_WEBHOOK_SECRET = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if STRIPE_WEBHOOK_SECRET and not verify_stripe_signature(body, sig, STRIPE_WEBHOOK_SECRET):
        logger.warning("Stripe webhook signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = event.get("type", "")
    event_data = event.get("data", {}).get("object", {})

    handlers = {
        "checkout.session.completed": handle_checkout_completed,
        "customer.subscription.updated": handle_subscription_updated,
        "customer.subscription.deleted": handle_subscription_deleted,
        "invoice.payment_failed": handle_invoice_payment_failed,
    }

    handler = handlers.get(event_type)
    if handler:
        await handler(db, event_data)
        logger.info("Stripe event processed: %s", event_type)
    else:
        logger.debug("Unhandled Stripe event: %s", event_type)

    return {"received": True}


@router.get("/plans")
async def list_plans():
    plans = []
    for plan_name, defaults in PLAN_DEFAULTS.items():
        plans.append({
            "name": plan_name,
            "price_usd": PLAN_PRICES_USD.get(plan_name, 0),
            "features": defaults,
        })
    return {"plans": plans}


@router.get("/current")
async def current_plan(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    quota = await get_or_create_quota(db, current_user["id"])
    return {
        "plan": quota.plan,
        "price_usd": PLAN_PRICES_USD.get(quota.plan, 0),
        "quotas": {
            "max_projects": quota.max_projects,
            "max_builds_per_month": quota.max_builds_per_month,
            "max_deploys_per_month": quota.max_deploys_per_month,
            "max_storage_mb": quota.max_storage_mb,
            "max_concurrent_builds": quota.max_concurrent_builds,
            "max_preview_sessions": quota.max_preview_sessions,
        },
    }


@router.post("/upgrade")
async def upgrade_plan(
    plan: str = Query(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if plan not in PLAN_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Options: {list(PLAN_DEFAULTS.keys())}")

    quota = await get_or_create_quota(db, current_user["id"])
    plan_order = {"free": 0, "pro": 1, "enterprise": 2}

    if plan_order.get(plan, 0) <= plan_order.get(quota.plan, 0):
        raise HTTPException(status_code=400, detail=f"Cannot upgrade from {quota.plan} to {plan}")

    return {
        "action": "redirect_to_checkout",
        "current_plan": quota.plan,
        "target_plan": plan,
        "price_usd": PLAN_PRICES_USD.get(plan, 0),
        "message": f"To upgrade to {plan}, complete payment via Stripe checkout.",
    }


@router.post("/downgrade")
async def downgrade_plan(
    plan: str = Query(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if plan not in PLAN_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Options: {list(PLAN_DEFAULTS.keys())}")

    quota = await get_or_create_quota(db, current_user["id"])
    plan_order = {"free": 0, "pro": 1, "enterprise": 2}

    if plan_order.get(plan, 0) >= plan_order.get(quota.plan, 0):
        raise HTTPException(status_code=400, detail=f"Cannot downgrade from {quota.plan} to {plan}")

    defaults = PLAN_DEFAULTS[plan]
    quota.plan = plan
    for k, v in defaults.items():
        setattr(quota, k, v)
    quota.updated_at = datetime.utcnow()
    await db.commit()

    return {
        "plan": plan,
        "price_usd": PLAN_PRICES_USD.get(plan, 0),
        "quotas": defaults,
        "message": f"Downgraded to {plan}. Changes effective immediately.",
    }
