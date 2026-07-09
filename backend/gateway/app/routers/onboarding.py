import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func, and_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.limiter import limiter
from app.models import Project, Build, Deployment

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])
logger = logging.getLogger(__name__)

# "Algılandı" sayılmayan framework durumları
_UNDETECTED = ("", "unknown", "detecting", "pending")


@router.get("/status")
@limiter.limit("30/minute")
async def onboarding_status(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının aktivasyon ilerlemesi — Dashboard onboarding checklist'i besler.
    Dört adım kullanıcının gerçek verisinden hesaplanır (kalıcı state tutulmaz)."""
    user_id = current_user["id"]

    project_count = (await db.execute(
        select(func.count()).select_from(Project).where(Project.owner_id == user_id)
    )).scalar() or 0

    framework_detected = (await db.execute(
        select(exists().where(and_(
            Project.owner_id == user_id,
            Project.framework.is_not(None),
            Project.framework.notin_(_UNDETECTED),
        )))
    )).scalar() or False

    has_build = (await db.execute(
        select(exists().where(and_(
            Build.project_id == Project.id,
            Project.owner_id == user_id,
        )))
    )).scalar() or False

    has_deploy = (await db.execute(
        select(exists().where(and_(
            Deployment.build_id == Build.id,
            Build.project_id == Project.id,
            Project.owner_id == user_id,
        )))
    )).scalar() or False

    steps = [
        {"key": "connect_repo", "done": project_count > 0},
        {"key": "framework_detected", "done": bool(framework_detected)},
        {"key": "first_build", "done": bool(has_build)},
        {"key": "first_deploy", "done": bool(has_deploy)},
    ]
    completed = sum(1 for s in steps if s["done"])

    return {
        "steps": steps,
        "completed": completed,
        "total": len(steps),
        "all_done": completed == len(steps),
    }
