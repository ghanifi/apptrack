import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.dependencies import get_current_user
from app.authz import require_admin_dep
from app.database import get_db
from app.models import Build, Deployment, Project, User

router = APIRouter(prefix="/api/metrics", tags=["metrics-kpi"])
logger = logging.getLogger(__name__)


@router.get("/time-to-first-deploy")
async def time_to_first_deploy(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının ilk deploy'a kadar geçen süre metriklerini hesaplar.

    Kayıt olma anından ilk proje, ilk credential, ilk başarılı build
    ve ilk deploy'a kadar geçen süreleri saniye cinsinden döndürür.
    Build başarı oranı istatistiklerini de içerir.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    user_result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = user_result.scalar_one_or_none()
    if not user:
        return {"error": "User not found"}

    signup_time = user.created_at

    first_project = await db.execute(
        select(Project).where(Project.owner_id == current_user["id"]).order_by(Project.created_at.asc()).limit(1)
    )
    proj = first_project.scalar_one_or_none()
    time_to_project = None
    if proj:
        time_to_project = (proj.created_at - signup_time).total_seconds()

    first_build = await db.execute(
        select(Build).join(Project, Build.project_id == Project.id).where(
            and_(Project.owner_id == current_user["id"], Build.status == "success")
        ).order_by(Build.created_at.asc()).limit(1)
    )
    build = first_build.scalar_one_or_none()
    time_to_build = None
    if build:
        time_to_build = (build.created_at - signup_time).total_seconds()

    first_deploy = await db.execute(
        select(Deployment).join(Build, Deployment.build_id == Build.id).join(Project, Build.project_id == Project.id).where(
            Project.owner_id == current_user["id"]
        ).order_by(Deployment.created_at.asc()).limit(1)
    )
    deploy = first_deploy.scalar_one_or_none()
    time_to_deploy = None
    if deploy:
        time_to_deploy = (deploy.created_at - signup_time).total_seconds()

    first_cred = None
    from app.models import Credential
    cred_result = await db.execute(
        select(Credential).where(Credential.owner_id == current_user["id"]).order_by(Credential.created_at.asc()).limit(1)
    )
    cred = cred_result.scalar_one_or_none()
    if cred:
        first_cred = (cred.created_at - signup_time).total_seconds()

    total_builds = await db.execute(
        select(func.count()).select_from(Build).join(Project, Build.project_id == Project.id).where(
            Project.owner_id == current_user["id"]
        )
    )
    success_builds = await db.execute(
        select(func.count()).select_from(Build).join(Project, Build.project_id == Project.id).where(
            and_(Project.owner_id == current_user["id"], Build.status == "success")
        )
    )
    total_b = total_builds.scalar() or 0
    success_b = success_builds.scalar() or 0

    return {
        "user_id": current_user["id"],
        "signup_at": signup_time.isoformat(),
        "milestones": {
            "time_to_first_project_seconds": time_to_project,
            "time_to_first_credential_seconds": first_cred,
            "time_to_first_successful_build_seconds": time_to_build,
            "time_to_first_deploy_seconds": time_to_deploy,
        },
        "build_stats": {
            "total_builds": total_b,
            "successful_builds": success_b,
            "first_build_success_rate": round(success_b / max(total_b, 1) * 100, 1),
        },
    }


@router.get("/platform-kpis", dependencies=[Depends(require_admin_dep)])
async def platform_kpis(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Platform genelindeki KPI metriklerini döndürür.

    Toplam kullanıcı, haftalık yeni kullanıcı, son 30 günlük build/deploy
    sayıları, başarı oranları ve ortalama build süresini içerir.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    new_users_week = (await db.execute(
        select(func.count()).select_from(User).where(User.created_at >= week_ago)
    )).scalar() or 0

    total_projects = (await db.execute(select(func.count()).select_from(Project))).scalar() or 0

    builds_month = (await db.execute(
        select(func.count()).where(Build.created_at >= month_ago)
    )).scalar() or 0
    success_month = (await db.execute(
        select(func.count()).where(and_(Build.created_at >= month_ago, Build.status == "success"))
    )).scalar() or 0

    deploys_month = (await db.execute(
        select(func.count()).where(Deployment.created_at >= month_ago)
    )).scalar() or 0
    published_month = (await db.execute(
        select(func.count()).where(and_(Deployment.created_at >= month_ago, Deployment.status == "published"))
    )).scalar() or 0

    avg_build_duration = await db.execute(
        select(func.avg(func.extract("epoch", Build.finished_at - Build.started_at))).where(
            and_(Build.status == "success", Build.finished_at.isnot(None), Build.started_at.isnot(None), Build.created_at >= month_ago)
        )
    )
    avg_dur = avg_build_duration.scalar()

    return {
        "timestamp": now.isoformat(),
        "users": {"total": total_users, "new_this_week": new_users_week},
        "projects": {"total": total_projects},
        "builds": {
            "last_30_days": builds_month,
            "success_rate": round(success_month / max(builds_month, 1) * 100, 1),
            "avg_duration_seconds": round(avg_dur, 1) if avg_dur else None,
        },
        "deploys": {
            "last_30_days": deploys_month,
            "success_rate": round(published_month / max(deploys_month, 1) * 100, 1),
        },
    }
