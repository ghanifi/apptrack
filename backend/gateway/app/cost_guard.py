import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models import UserQuota, Build, Project, UsageRecord

logger = logging.getLogger(__name__)

PROVIDER_COST_PER_MINUTE = {
    "eas": 0.05,
    "codemagic": 0.038,
    "github_actions": 0.008,
    "simulation": 0.0,
}

ESTIMATED_BUILD_MINUTES = {
    "eas": {"android": 12, "ios": 18},
    "codemagic": {"android": 10, "ios": 15},
    "github_actions": {"android": 8, "ios": 25},
    "simulation": {"android": 0, "ios": 0},
}

PLAN_MONTHLY_BUDGET_USD = {
    "free": 0.0,
    "pro": 50.0,
    "enterprise": 500.0,
}

AUTO_SUSPEND_THRESHOLD = 1.0


async def estimate_build_cost(provider: str, platform: str) -> dict:
    minutes = ESTIMATED_BUILD_MINUTES.get(provider, {}).get(platform, 15)
    rate = PROVIDER_COST_PER_MINUTE.get(provider, 0.05)
    estimated_usd = round(minutes * rate, 2)
    return {
        "provider": provider,
        "platform": platform,
        "estimated_minutes": minutes,
        "rate_per_minute": rate,
        "estimated_cost_usd": estimated_usd,
    }


async def get_monthly_spend(db: AsyncSession, user_id: str) -> float:
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(UsageRecord).where(
            and_(
                UsageRecord.user_id == user_id,
                UsageRecord.metric_type == "build_cost_usd",
                UsageRecord.period_start == month_start,
            )
        )
    )
    record = result.scalar_one_or_none()
    return record.value if record else 0.0


async def check_budget_limit(db: AsyncSession, user_id: str, estimated_cost: float):
    quota = await _get_quota(db, user_id)
    budget = PLAN_MONTHLY_BUDGET_USD.get(quota.plan, 0.0)

    if budget <= 0.0:
        return

    current_spend = await get_monthly_spend(db, user_id)
    projected = current_spend + estimated_cost

    if projected > budget * AUTO_SUSPEND_THRESHOLD:
        remaining = max(0.0, budget - current_spend)
        raise HTTPException(
            status_code=429,
            detail=(
                f"Monthly budget limit approaching. "
                f"Current spend: ${current_spend:.2f} / ${budget:.2f}. "
                f"Estimated cost: ${estimated_cost:.2f}. "
                f"Remaining: ${remaining:.2f}. "
                f"Upgrade your plan or wait for next billing cycle."
            ),
        )


async def record_build_cost(
    db: AsyncSession, user_id: str, provider: str, platform: str, actual_minutes: float | None = None
):
    if actual_minutes is None:
        actual_minutes = ESTIMATED_BUILD_MINUTES.get(provider, {}).get(platform, 15)
    rate = PROVIDER_COST_PER_MINUTE.get(provider, 0.05)
    cost = round(actual_minutes * rate, 2)

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

    result = await db.execute(
        select(UsageRecord).where(
            and_(
                UsageRecord.user_id == user_id,
                UsageRecord.metric_type == "build_cost_usd",
                UsageRecord.period_start == month_start,
            )
        )
    )
    record = result.scalar_one_or_none()
    if record:
        record.value += cost
    else:
        record = UsageRecord(
            user_id=user_id,
            metric_type="build_cost_usd",
            value=cost,
            period_start=month_start,
            period_end=month_end,
            metadata_json={"currency": "usd"},
        )
        db.add(record)

    return cost


async def _get_quota(db: AsyncSession, user_id: str) -> UserQuota:
    result = await db.execute(select(UserQuota).where(UserQuota.user_id == user_id))
    quota = result.scalar_one_or_none()
    if not quota:
        quota = UserQuota(user_id=user_id, plan="free")
        db.add(quota)
        await db.flush()
    return quota
