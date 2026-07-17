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
    """Stripe webhook olaylarını işler.

    Checkout tamamlama, abonelik güncelleme/silme ve ödeme başarısızlığı
    olaylarını imza doğrulaması ile alıp ilgili handler'a yönlendirir.

    Raises:
        400: Geçersiz imza veya JSON formatı
        503: Webhook secret yapılandırılmamış (fail-closed)
    """
    body = await request.body()
    sig = request.headers.get("stripe-signature", "")

    # Fail-closed (diğer webhook'larla — EAS/Codemagic/ASC — aynı disiplin, H1):
    # secret yoksa doğrulama ATLANMAZ; aksi halde saldırgan gövdeden plan set eder
    # (metadata.plan) → bedava enterprise upgrade.
    if not STRIPE_WEBHOOK_SECRET:
        logger.error("Stripe webhook imza doğrulaması kapalı — STRIPE_WEBHOOK_SECRET yapılandırılmamış")
        raise HTTPException(status_code=503, detail="Stripe webhook doğrulaması yapılandırılmamış")
    if not verify_stripe_signature(body, sig, STRIPE_WEBHOOK_SECRET):
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
    """Mevcut abonelik planlarını ve özelliklerini listeler.

    Her plan için fiyat, kota limitleri ve dahil olan
    özelliklerin detaylarını döndürür.
    """
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
    """Mevcut kullanıcının aktif planını ve kota bilgilerini getirir.

    Plan adı, fiyatı ve proje, build, deploy, depolama gibi
    tüm kota limitlerini döndürür.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    quota = await get_or_create_quota(db, current_user["id"])
    return {
        "plan": quota.plan,
        "price_usd": PLAN_PRICES_USD.get(quota.plan, 0),
        "stripe_configured": bool(getattr(settings, "STRIPE_API_KEY", "")),
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
    """Plan yükseltme işlemini başlatır.

    Mevcut plandan daha üst bir plana geçiş için Stripe checkout
    yönlendirmesi oluşturur. Alt plana geçiş kabul edilmez.

    Raises:
        400: Geçersiz plan veya alt plana yükseltme denemesi
        401: Kimlik doğrulama gerekli
    """
    if plan not in PLAN_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Options: {list(PLAN_DEFAULTS.keys())}")

    quota = await get_or_create_quota(db, current_user["id"])
    plan_order = {"free": 0, "pro": 1, "enterprise": 2}

    if plan_order.get(plan, 0) <= plan_order.get(quota.plan, 0):
        raise HTTPException(status_code=400, detail=f"Cannot upgrade from {quota.plan} to {plan}")

    stripe_key = settings.STRIPE_API_KEY
    if not stripe_key:
        return {
            "action": "redirect_to_checkout",
            "current_plan": quota.plan,
            "target_plan": plan,
            "price_usd": PLAN_PRICES_USD.get(plan, 0),
            "message": f"Stripe not configured. To upgrade to {plan}, configure STRIPE_API_KEY.",
        }

    try:
        import stripe
        stripe.api_key = stripe_key

        price_map = {
            "pro": getattr(settings, "STRIPE_PRICE_PRO", ""),
            "enterprise": getattr(settings, "STRIPE_PRICE_ENTERPRISE", ""),
        }
        price_id = price_map.get(plan)
        if not price_id:
            raise HTTPException(status_code=400, detail=f"Stripe price not configured for plan: {plan}")

        customer_id = quota.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                email=current_user.get("email", ""),
                metadata={"user_id": current_user["id"]},
            )
            customer_id = customer.id
            quota.stripe_customer_id = customer_id
            await db.commit()

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{settings.FRONTEND_URL}/dashboard/settings?billing=success",
            cancel_url=f"{settings.FRONTEND_URL}/dashboard/settings?billing=cancelled",
            metadata={"user_id": current_user["id"], "plan": plan},
        )

        return {
            "action": "redirect_to_checkout",
            "checkout_url": session.url,
            "session_id": session.id,
            "current_plan": quota.plan,
            "target_plan": plan,
        }

    except ImportError:
        return {
            "action": "redirect_to_checkout",
            "current_plan": quota.plan,
            "target_plan": plan,
            "price_usd": PLAN_PRICES_USD.get(plan, 0),
            "message": f"Stripe SDK not available. Install stripe package.",
        }


@router.post("/portal")
async def billing_portal(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stripe müşteri portalı oturumu oluşturur.

    Kullanıcının aboneliğini yönetmesi, ödeme yöntemini güncellemesi
    ve fatura geçmişini görüntülemesi için Stripe portal URL'si döndürür.

    Raises:
        400: Stripe yapılandırılmamış veya müşteri kaydı yok
        401: Kimlik doğrulama gerekli
    """
    stripe_key = settings.STRIPE_API_KEY
    if not stripe_key:
        raise HTTPException(status_code=400, detail="Stripe not configured")

    quota = await get_or_create_quota(db, current_user["id"])
    if not quota.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found. Please upgrade first.")

    try:
        import stripe
        stripe.api_key = stripe_key

        session = stripe.billing_portal.Session.create(
            customer=quota.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/dashboard/settings",
        )
        return {"portal_url": session.url}
    except ImportError:
        raise HTTPException(status_code=400, detail="Stripe SDK not available")


@router.post("/downgrade")
async def downgrade_plan(
    plan: str = Query(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Planı daha alt seviyeye düşürür.

    Mevcut plandan daha düşük bir plana geçiş yapar ve kotaları
    hemen günceller. Üst plana geçiş kabul edilmez.

    Raises:
        400: Geçersiz plan veya üst plana düşürme denemesi
        401: Kimlik doğrulama gerekli
    """
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
