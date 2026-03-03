import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Build, Project, Credential
from app.cost_guard import estimate_build_cost

router = APIRouter(prefix="/api/projects", tags=["deploy-simulator"])
logger = logging.getLogger(__name__)

ESTIMATED_BUILD_MINUTES = {
    "eas": {"android": 4, "ios": 8, "both": 12},
    "codemagic": {"android": 5, "ios": 10, "both": 15},
    "github_actions": {"android": 6, "ios": 12, "both": 18},
}

ESTIMATED_REVIEW_HOURS = {
    "google_play": {"internal": 0.5, "alpha": 2, "beta": 6, "production": 24},
    "app_store": {"internal": 0, "beta": 1, "production": 48},
}

FRAMEWORK_PROVIDER_MAP = {
    "react_native": "eas",
    "expo": "eas",
    "flutter": "codemagic",
    "swift": "github_actions",
    "kotlin": "github_actions",
    "unknown": "github_actions",
}


@router.get("/{project_id}/deploy-estimate")
async def estimate_deploy(
    project_id: str,
    platform: str = "android",
    target: str = "google_play",
    track: str = "internal",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deploy sürecinin tahmini süre, maliyet ve hazırlık durumunu hesaplar.

    Framework, platform ve hedef mağazaya göre build süresi, review süresi
    ve maliyet tahmini yapar. Geçmiş build verilerini de dikkate alır.
    Credential eksikliklerini kontrol ederek hazırlık raporu sunar.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    provider = FRAMEWORK_PROVIDER_MAP.get(project.framework, "github_actions")
    build_times = ESTIMATED_BUILD_MINUTES.get(provider, ESTIMATED_BUILD_MINUTES["github_actions"])
    est_build_min = build_times.get(platform, build_times.get("android", 6))

    review_times = ESTIMATED_REVIEW_HOURS.get(target, ESTIMATED_REVIEW_HOURS["google_play"])
    est_review_hrs = review_times.get(track, 24)

    cost_est = await estimate_build_cost(provider, platform)

    past_builds = await db.execute(
        select(Build).where(
            and_(Build.project_id == project_id, Build.status == "success", Build.finished_at.isnot(None), Build.started_at.isnot(None))
        ).order_by(Build.created_at.desc()).limit(5)
    )
    past = past_builds.scalars().all()
    if past:
        durations = [(b.finished_at - b.started_at).total_seconds() / 60 for b in past]
        avg_build_min = round(sum(durations) / len(durations), 1)
    else:
        avg_build_min = est_build_min

    gp_cred = await db.execute(
        select(func.count()).where(
            and_(Credential.owner_id == current_user["id"], Credential.provider == "google_play")
        )
    )
    as_cred = await db.execute(
        select(func.count()).where(
            and_(Credential.owner_id == current_user["id"], Credential.provider == "app_store")
        )
    )
    has_google_play = (gp_cred.scalar() or 0) > 0
    has_app_store = (as_cred.scalar() or 0) >= 3

    readiness_checks = []
    if target == "google_play" and not has_google_play:
        readiness_checks.append({"check": "Google Play credentials", "status": "missing", "action": "Add Service Account JSON in Settings"})
    if target == "app_store" and not has_app_store:
        readiness_checks.append({"check": "App Store credentials", "status": "missing", "action": "Add Key ID, Issuer ID, and Private Key in Settings"})

    return {
        "project_id": project_id,
        "framework": project.framework,
        "provider": provider,
        "platform": platform,
        "target": target,
        "track": track,
        "estimates": {
            "build_minutes": avg_build_min,
            "build_minutes_estimated": est_build_min,
            "review_hours": est_review_hrs,
            "total_hours_to_live": round(avg_build_min / 60 + est_review_hrs, 1),
            "cost_usd": cost_est,
        },
        "readiness": {
            "credentials_ready": len(readiness_checks) == 0,
            "checks": readiness_checks,
        },
        "tips": _get_tips(target, track),
    }


def _get_tips(target: str, track: str) -> list[str]:
    tips = []
    if track == "production":
        tips.append("Production releases require full store review and may take 24-72 hours.")
        if target == "app_store":
            tips.append("Ensure your app metadata (screenshots, description) is complete in App Store Connect.")
        if target == "google_play":
            tips.append("Your app must pass Google Play policy compliance checks.")
    elif track == "internal":
        tips.append("Internal testing is fastest — builds are available within minutes.")
    if target == "app_store":
        tips.append("iOS builds require a valid signing certificate and provisioning profile.")
    return tips
