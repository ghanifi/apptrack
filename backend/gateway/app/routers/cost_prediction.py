"""
Build Cost Prediction Router
=============================
Predicts build costs based on historical build data for a given project,
platform, and provider combination. Uses actual build duration history
to compute estimated costs, confidence scores, and monthly projections.
"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Build, Project

router = APIRouter(prefix="/api/cost-prediction", tags=["cost-prediction"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider cost rates (USD per minute) by platform
# ---------------------------------------------------------------------------

PROVIDER_COSTS: dict[str, dict[str, float]] = {
    "eas": {
        "android": 0.02,
        "ios": 0.04,
    },
    "codemagic": {
        "android": 0.015,
        "ios": 0.035,
    },
    "github_actions": {
        "android": 0.008,
        "ios": 0.08,  # macOS runner — significantly more expensive
    },
}

VALID_PLATFORMS = {"android", "ios"}
VALID_PROVIDERS = set(PROVIDER_COSTS.keys())

# Number of recent builds to sample for prediction
HISTORY_SAMPLE_SIZE = 20


def _get_cost_per_minute(provider: str, platform: str) -> float | None:
    """
    Look up the per-minute cost rate for a provider/platform combination.

    Args:
        provider: Build provider (eas, codemagic, github_actions).
        platform: Target platform (android, ios).

    Returns:
        Cost per minute in USD, or None if the combination is unknown.
    """
    provider_rates = PROVIDER_COSTS.get(provider)
    if not provider_rates:
        return None
    return provider_rates.get(platform)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@router.get("/predict/{project_id}")
async def predict_build_cost(
    project_id: str,
    platform: str = Query("android", description="Target platform: android or ios"),
    provider: str = Query("eas", description="Build provider: eas, codemagic, or github_actions"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Predict the cost of the next build for a project based on historical data.

    Queries the last 20 completed builds for this project/platform/provider
    combination, calculates average duration, and multiplies by the provider's
    per-minute cost rate. Returns a confidence score based on the amount of
    history available (confidence = min(history_count / 20, 1.0)).

    - **project_id**: UUID of the project.
    - **platform**: Target platform (android, ios).
    - **provider**: Build provider (eas, codemagic, github_actions).
    """
    # Validate inputs
    if platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform '{platform}'. Must be one of: {', '.join(sorted(VALID_PLATFORMS))}",
        )
    if provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider '{provider}'. Must be one of: {', '.join(sorted(VALID_PROVIDERS))}",
        )

    # Verify project ownership
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    cost_per_minute = _get_cost_per_minute(provider, platform)
    if cost_per_minute is None:
        raise HTTPException(
            status_code=400,
            detail=f"No cost data available for provider '{provider}' on platform '{platform}'.",
        )

    # Query recent completed builds with valid duration data
    builds_result = await db.execute(
        select(Build).where(
            and_(
                Build.project_id == project_id,
                Build.platform == platform,
                Build.provider == provider,
                Build.status == "success",
                Build.started_at.isnot(None),
                Build.finished_at.isnot(None),
            )
        ).order_by(Build.created_at.desc()).limit(HISTORY_SAMPLE_SIZE)
    )
    past_builds = builds_result.scalars().all()
    history_count = len(past_builds)

    if history_count == 0:
        return {
            "project_id": project_id,
            "platform": platform,
            "provider": provider,
            "estimated_cost_usd": None,
            "estimated_duration_seconds": None,
            "cost_per_minute_usd": cost_per_minute,
            "confidence": 0.0,
            "based_on_builds": 0,
            "message": f"No completed builds found for this project with provider '{provider}' "
                       f"on platform '{platform}'. Build at least once to enable cost prediction.",
        }

    # Calculate average duration in seconds
    durations = [
        (b.finished_at - b.started_at).total_seconds()
        for b in past_builds
        if b.finished_at > b.started_at  # guard against negative durations
    ]

    if not durations:
        return {
            "project_id": project_id,
            "platform": platform,
            "provider": provider,
            "estimated_cost_usd": None,
            "estimated_duration_seconds": None,
            "cost_per_minute_usd": cost_per_minute,
            "confidence": 0.0,
            "based_on_builds": history_count,
            "message": "Build duration data is invalid (finished before started). Cannot predict cost.",
        }

    avg_duration_seconds = sum(durations) / len(durations)
    avg_duration_minutes = avg_duration_seconds / 60.0
    estimated_cost = round(avg_duration_minutes * cost_per_minute, 4)
    confidence = round(min(len(durations) / HISTORY_SAMPLE_SIZE, 1.0), 2)

    # Also compute min/max for range
    min_duration = min(durations)
    max_duration = max(durations)
    min_cost = round((min_duration / 60.0) * cost_per_minute, 4)
    max_cost = round((max_duration / 60.0) * cost_per_minute, 4)

    logger.info(
        "Cost prediction: project=%s provider=%s platform=%s est_cost=$%.4f confidence=%.2f builds=%d",
        project_id, provider, platform, estimated_cost, confidence, len(durations),
    )

    return {
        "project_id": project_id,
        "platform": platform,
        "provider": provider,
        "estimated_cost_usd": estimated_cost,
        "estimated_duration_seconds": round(avg_duration_seconds, 1),
        "cost_per_minute_usd": cost_per_minute,
        "confidence": confidence,
        "based_on_builds": len(durations),
        "cost_range": {
            "min_usd": min_cost,
            "max_usd": max_cost,
            "min_duration_seconds": round(min_duration, 1),
            "max_duration_seconds": round(max_duration, 1),
        },
    }


@router.get("/monthly/{project_id}")
async def monthly_cost_projection(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Project the monthly build cost for a project based on current-month activity.

    Calculates the actual cost of builds this month (from build durations and
    provider rates), then extrapolates to the full month based on the fraction
    of the month elapsed. Breaks down costs by provider and platform.

    - **project_id**: UUID of the project.
    """
    # Verify project ownership
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Calculate days in this month
    if now.month == 12:
        next_month_start = month_start.replace(year=now.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=now.month + 1)
    days_in_month = (next_month_start - month_start).days
    days_elapsed = max((now - month_start).total_seconds() / 86400.0, 0.01)  # avoid division by zero

    # Query all completed builds this month for the project
    builds_result = await db.execute(
        select(Build).where(
            and_(
                Build.project_id == project_id,
                Build.status == "success",
                Build.started_at.isnot(None),
                Build.finished_at.isnot(None),
                Build.created_at >= month_start,
            )
        ).order_by(Build.created_at.desc())
    )
    monthly_builds = builds_result.scalars().all()

    if not monthly_builds:
        return {
            "project_id": project_id,
            "month": month_start.strftime("%Y-%m"),
            "days_elapsed": round(days_elapsed, 1),
            "days_in_month": days_in_month,
            "actual_cost_usd": 0.0,
            "projected_monthly_cost_usd": 0.0,
            "build_count": 0,
            "breakdown": [],
            "message": "No completed builds found this month for this project.",
        }

    # Calculate actual costs broken down by provider/platform
    breakdown: dict[str, dict] = {}
    total_actual_cost = 0.0

    for build in monthly_builds:
        duration_seconds = (build.finished_at - build.started_at).total_seconds()
        if duration_seconds <= 0:
            continue

        duration_minutes = duration_seconds / 60.0
        cost_rate = _get_cost_per_minute(build.provider, build.platform)
        if cost_rate is None:
            cost_rate = 0.0

        build_cost = duration_minutes * cost_rate
        total_actual_cost += build_cost

        key = f"{build.provider}:{build.platform}"
        if key not in breakdown:
            breakdown[key] = {
                "provider": build.provider,
                "platform": build.platform,
                "build_count": 0,
                "total_duration_seconds": 0.0,
                "total_cost_usd": 0.0,
                "cost_per_minute_usd": cost_rate,
            }
        breakdown[key]["build_count"] += 1
        breakdown[key]["total_duration_seconds"] += duration_seconds
        breakdown[key]["total_cost_usd"] += build_cost

    # Round breakdown values
    breakdown_list = []
    for entry in breakdown.values():
        entry["total_cost_usd"] = round(entry["total_cost_usd"], 4)
        entry["total_duration_seconds"] = round(entry["total_duration_seconds"], 1)
        breakdown_list.append(entry)

    # Sort breakdown by cost descending
    breakdown_list.sort(key=lambda x: x["total_cost_usd"], reverse=True)

    total_actual_cost = round(total_actual_cost, 4)
    # Extrapolate to full month
    projected_cost = round(total_actual_cost * (days_in_month / days_elapsed), 4)

    logger.info(
        "Monthly projection: project=%s actual=$%.4f projected=$%.4f builds=%d",
        project_id, total_actual_cost, projected_cost, len(monthly_builds),
    )

    return {
        "project_id": project_id,
        "month": month_start.strftime("%Y-%m"),
        "days_elapsed": round(days_elapsed, 1),
        "days_in_month": days_in_month,
        "actual_cost_usd": total_actual_cost,
        "projected_monthly_cost_usd": projected_cost,
        "build_count": len(monthly_builds),
        "breakdown": breakdown_list,
    }
