import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_current_user
from app.database import get_db
from app.quotas import get_or_create_quota

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def get_quotas(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanicinin mevcut kota limitlerini dondurur.

    Plan bazli kota bilgilerini (proje, build, deploy, storage, preview)
    kullaniciya sunar.

    Raises:
        401: Kimlik dogrulama gerekli
    """
    user_id = current_user["id"]
    quota = await get_or_create_quota(db, user_id)
    return {
        "plan": quota.plan,
        "max_projects": quota.max_projects,
        "max_builds_per_month": quota.max_builds_per_month,
        "max_deploys_per_month": quota.max_deploys_per_month,
        "max_storage_mb": quota.max_storage_mb,
        "max_concurrent_builds": quota.max_concurrent_builds,
        "max_preview_sessions": quota.max_preview_sessions,
    }
