import logging
import hmac
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import UserQuota, User, Build, Project, AuditLog
from app.quotas import PLAN_DEFAULTS

logger = logging.getLogger(__name__)

STRIPE_PLAN_MAP = {
    "price_free": "free",
    "price_pro_monthly": "pro",
    "price_pro_yearly": "pro",
    "price_enterprise_monthly": "enterprise",
    "price_enterprise_yearly": "enterprise",
}

PLAN_PRICES_USD = {
    "free": 0,
    "pro": 29,
    "enterprise": 199,
}

GRACE_PERIOD_DAYS = 7
SUSPEND_AFTER_DAYS = 14


def verify_stripe_signature(payload: bytes, sig_header: str, webhook_secret: str) -> bool:
    if not webhook_secret:
        return False
    try:
        parts = dict(item.split("=", 1) for item in sig_header.split(","))
        timestamp = parts.get("t", "")
        expected_sig = parts.get("v1", "")
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        computed = hmac.new(
            webhook_secret.encode(), signed_payload.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(computed, expected_sig)
    except Exception:
        return False


async def handle_checkout_completed(db: AsyncSession, event_data: dict):
    customer_email = event_data.get("customer_details", {}).get("email")
    price_id = None
    line_items = event_data.get("line_items", {}).get("data", [])
    if line_items:
        price_id = line_items[0].get("price", {}).get("id")

    if not customer_email or not price_id:
        logger.warning("Checkout completed but missing email or price_id")
        return

    plan = STRIPE_PLAN_MAP.get(price_id, "pro")
    await _update_user_plan(db, customer_email, plan, f"checkout:{price_id}")


async def handle_subscription_updated(db: AsyncSession, event_data: dict):
    customer_email = event_data.get("customer_email")
    items = event_data.get("items", {}).get("data", [])
    if not items:
        return

    price_id = items[0].get("price", {}).get("id", "")
    plan = STRIPE_PLAN_MAP.get(price_id, "pro")
    status = event_data.get("status", "")

    if status in ("active", "trialing"):
        await _update_user_plan(db, customer_email, plan, f"subscription_updated:{status}")
    elif status == "past_due":
        logger.warning("Subscription past_due for %s — grace period started", customer_email)
    elif status in ("canceled", "unpaid"):
        await _downgrade_to_free(db, customer_email, f"subscription_{status}")


async def handle_invoice_payment_failed(db: AsyncSession, event_data: dict):
    customer_email = event_data.get("customer_email")
    attempt_count = event_data.get("attempt_count", 0)
    logger.warning("Invoice payment failed for %s (attempt %d)", customer_email, attempt_count)

    if attempt_count >= 3:
        await _suspend_user(db, customer_email, "payment_failed_3x")


async def handle_subscription_deleted(db: AsyncSession, event_data: dict):
    customer_email = event_data.get("customer_email")
    await _downgrade_to_free(db, customer_email, "subscription_deleted")


async def _update_user_plan(db: AsyncSession, email: str, plan: str, reason: str):
    if not email:
        return
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        logger.warning("Plan update for unknown email: %s", email)
        return

    defaults = PLAN_DEFAULTS.get(plan, PLAN_DEFAULTS["free"])

    quota_result = await db.execute(select(UserQuota).where(UserQuota.user_id == user.id))
    quota = quota_result.scalar_one_or_none()

    if quota:
        quota.plan = plan
        for k, v in defaults.items():
            setattr(quota, k, v)
        quota.updated_at = datetime.utcnow()
    else:
        quota = UserQuota(user_id=user.id, plan=plan, **defaults)
        db.add(quota)

    audit = AuditLog(
        user_id=user.id,
        action="billing.plan_changed",
        resource_type="quota",
        resource_id=user.id,
        details={"plan": plan, "reason": reason},
    )
    db.add(audit)
    await db.commit()
    logger.info("Plan updated: user=%s plan=%s reason=%s", email, plan, reason)


async def _downgrade_to_free(db: AsyncSession, email: str, reason: str):
    await _update_user_plan(db, email, "free", reason)


async def _suspend_user(db: AsyncSession, email: str, reason: str):
    if not email:
        return
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        return

    await db.execute(
        update(Build).where(
            and_(
                Build.project_id.in_(select(Project.id).where(Project.owner_id == user.id)),
                Build.status.in_(["queued", "running"]),
            )
        ).values(status="cancelled", finished_at=datetime.utcnow())
    )

    await _update_user_plan(db, email, "free", f"suspended:{reason}")
    logger.warning("User suspended: %s reason=%s", email, reason)


async def check_overdue_subscriptions(db: AsyncSession):
    cutoff = datetime.utcnow() - timedelta(days=SUSPEND_AFTER_DAYS)
    result = await db.execute(
        select(AuditLog).where(
            and_(
                AuditLog.action == "billing.plan_changed",
                AuditLog.created_at <= cutoff,
            )
        ).order_by(AuditLog.created_at.desc()).limit(100)
    )
    logger.info("Overdue subscription check completed")
