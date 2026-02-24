import logging
from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.dependencies import get_current_user
from app.database import get_db
from app.models import UsageRecord, UserQuota, Build, Project, Deployment
from app.quotas import get_or_create_quota, _month_start

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/summary")
async def usage_summary(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user["id"]
    quota = await get_or_create_quota(db, user_id)
    month_start = _month_start()

    project_count = (await db.execute(
        select(func.count()).where(Project.owner_id == user_id)
    )).scalar() or 0

    build_count = (await db.execute(
        select(func.count())
        .select_from(Build)
        .join(Project, Build.project_id == Project.id)
        .where(and_(Project.owner_id == user_id, Build.created_at >= month_start))
    )).scalar() or 0

    deploy_count = (await db.execute(
        select(func.count())
        .select_from(Deployment)
        .join(Build, Deployment.build_id == Build.id)
        .join(Project, Build.project_id == Project.id)
        .where(and_(Project.owner_id == user_id, Deployment.created_at >= month_start))
    )).scalar() or 0

    concurrent_builds = (await db.execute(
        select(func.count())
        .select_from(Build)
        .join(Project, Build.project_id == Project.id)
        .where(and_(Project.owner_id == user_id, Build.status.in_(["queued", "running"])))
    )).scalar() or 0

    result = await db.execute(
        select(UsageRecord).where(
            and_(
                UsageRecord.user_id == user_id,
                UsageRecord.period_start == month_start,
            )
        )
    )
    usage_records = {r.metric_type: r.value for r in result.scalars().all()}

    return {
        "plan": quota.plan,
        "period": month_start.strftime("%Y-%m"),
        "usage": {
            "projects": {"current": project_count, "limit": quota.max_projects},
            "builds_this_month": {"current": build_count, "limit": quota.max_builds_per_month},
            "deploys_this_month": {"current": deploy_count, "limit": quota.max_deploys_per_month},
            "concurrent_builds": {"current": concurrent_builds, "limit": quota.max_concurrent_builds},
            "storage_mb": {"current": usage_records.get("storage_mb", 0), "limit": quota.max_storage_mb},
            "build_minutes": {"current": usage_records.get("build_minutes", 0)},
        },
        "quotas": {
            "max_projects": quota.max_projects,
            "max_builds_per_month": quota.max_builds_per_month,
            "max_deploys_per_month": quota.max_deploys_per_month,
            "max_storage_mb": quota.max_storage_mb,
            "max_concurrent_builds": quota.max_concurrent_builds,
            "max_preview_sessions": quota.max_preview_sessions,
        },
    }


@router.get("/history")
async def usage_history(
    metric_type: Optional[str] = Query(None),
    months: int = Query(6, ge=1, le=12),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user["id"]
    base_q = select(UsageRecord).where(UsageRecord.user_id == user_id)
    if metric_type:
        base_q = base_q.where(UsageRecord.metric_type == metric_type)
    base_q = base_q.order_by(UsageRecord.period_start.desc()).limit(months * 10)

    result = await db.execute(base_q)
    records = result.scalars().all()
    return [
        {
            "metric_type": r.metric_type,
            "value": r.value,
            "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(),
            "metadata": r.metadata_json,
        }
        for r in records
    ]
