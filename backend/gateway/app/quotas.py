import logging
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import UserQuota, Project, Build, Deployment, UsageRecord, Notification

logger = logging.getLogger(__name__)

QUOTA_WARNING_THRESHOLD = 0.8  # 80%

PLAN_DEFAULTS = {
    "free": {
        "max_projects": 3,
        "max_builds_per_month": 10,
        "max_deploys_per_month": 5,
        "max_storage_mb": 500,
        "max_concurrent_builds": 1,
        "max_preview_sessions": 2,
    },
    "pro": {
        "max_projects": 20,
        "max_builds_per_month": 100,
        "max_deploys_per_month": 50,
        "max_storage_mb": 5000,
        "max_concurrent_builds": 5,
        "max_preview_sessions": 10,
    },
    "enterprise": {
        "max_projects": 999,
        "max_builds_per_month": 999,
        "max_deploys_per_month": 999,
        "max_storage_mb": 50000,
        "max_concurrent_builds": 20,
        "max_preview_sessions": 50,
    },
}


async def get_or_create_quota(db: AsyncSession, user_id: str) -> UserQuota:
    result = await db.execute(select(UserQuota).where(UserQuota.user_id == user_id))
    quota = result.scalar_one_or_none()
    if not quota:
        quota = UserQuota(user_id=user_id, plan="free")
        db.add(quota)
        await db.flush()
    return quota


def _month_start() -> datetime:
    now = datetime.utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _send_quota_warning(db: AsyncSession, user_id: str, metric: str, current: int, limit: int):
    """Send an in-app notification when usage reaches 80% of quota."""
    if limit <= 0:
        return
    ratio = current / limit
    if ratio < QUOTA_WARNING_THRESHOLD:
        return

    existing = await db.execute(
        select(func.count()).select_from(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.type == "quota_warning",
                Notification.resource_type == metric,
                Notification.created_at >= _month_start(),
            )
        )
    )
    if (existing.scalar() or 0) > 0:
        return

    pct = int(ratio * 100)
    notification = Notification(
        user_id=user_id,
        type="quota_warning",
        title=f"{metric.replace('_', ' ').title()} quota at {pct}%",
        body=f"You've used {current} of {limit} {metric.replace('_', ' ')}. Consider upgrading your plan.",
        channel="in_app",
        resource_type=metric,
    )
    db.add(notification)
    logger.info("Quota warning sent: user=%s metric=%s %d/%d", user_id, metric, current, limit)


async def check_project_quota(db: AsyncSession, user_id: str):
    quota = await get_or_create_quota(db, user_id)
    count_result = await db.execute(
        select(func.count()).where(Project.owner_id == user_id)
    )
    current = count_result.scalar() or 0
    if current >= quota.max_projects:
        raise HTTPException(
            status_code=429,
            detail=f"Project limit reached ({quota.max_projects} for {quota.plan} plan). Upgrade to create more projects.",
        )
    await _send_quota_warning(db, user_id, "projects", current, quota.max_projects)


async def check_build_quota(db: AsyncSession, user_id: str):
    quota = await get_or_create_quota(db, user_id)
    month_start = _month_start()

    count_result = await db.execute(
        select(func.count())
        .select_from(Build)
        .join(Project, Build.project_id == Project.id)
        .where(and_(Project.owner_id == user_id, Build.created_at >= month_start))
    )
    current = count_result.scalar() or 0
    if current >= quota.max_builds_per_month:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly build limit reached ({quota.max_builds_per_month} for {quota.plan} plan).",
        )
    await _send_quota_warning(db, user_id, "builds", current, quota.max_builds_per_month)

    concurrent_result = await db.execute(
        select(func.count())
        .select_from(Build)
        .join(Project, Build.project_id == Project.id)
        .where(
            and_(
                Project.owner_id == user_id,
                Build.status.in_(["queued", "running"]),
            )
        )
    )
    concurrent = concurrent_result.scalar() or 0
    if concurrent >= quota.max_concurrent_builds:
        raise HTTPException(
            status_code=429,
            detail=f"Concurrent build limit reached ({quota.max_concurrent_builds} for {quota.plan} plan). Wait for current build to finish.",
        )


async def check_deploy_quota(db: AsyncSession, user_id: str):
    quota = await get_or_create_quota(db, user_id)
    month_start = _month_start()

    count_result = await db.execute(
        select(func.count())
        .select_from(Deployment)
        .join(Build, Deployment.build_id == Build.id)
        .join(Project, Build.project_id == Project.id)
        .where(and_(Project.owner_id == user_id, Deployment.created_at >= month_start))
    )
    current = count_result.scalar() or 0
    if current >= quota.max_deploys_per_month:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly deploy limit reached ({quota.max_deploys_per_month} for {quota.plan} plan).",
        )
    await _send_quota_warning(db, user_id, "deploys", current, quota.max_deploys_per_month)


async def track_usage(
    db: AsyncSession,
    user_id: str,
    metric_type: str,
    value: float,
    metadata: dict | None = None,
):
    month_start = _month_start()
    month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

    result = await db.execute(
        select(UsageRecord).where(
            and_(
                UsageRecord.user_id == user_id,
                UsageRecord.metric_type == metric_type,
                UsageRecord.period_start == month_start,
            )
        )
    )
    record = result.scalar_one_or_none()
    if record:
        record.value += value
        if metadata:
            existing = record.metadata_json or {}
            existing.update(metadata)
            record.metadata_json = existing
    else:
        record = UsageRecord(
            user_id=user_id,
            metric_type=metric_type,
            value=value,
            period_start=month_start,
            period_end=month_end,
            metadata_json=metadata,
        )
        db.add(record)
