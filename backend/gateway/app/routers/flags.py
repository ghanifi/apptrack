import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from app.dependencies import get_current_user
from app.authz import require_admin_dep
from app.database import get_db
from app.models import FeatureFlag
from app.feature_flags import invalidate_cache, is_enabled

router = APIRouter()
logger = logging.getLogger(__name__)


class FlagCreate(BaseModel):
    name: str
    enabled: bool = False
    description: Optional[str] = None
    percentage: int = 0


class FlagUpdate(BaseModel):
    enabled: Optional[bool] = None
    description: Optional[str] = None
    percentage: Optional[int] = None
    allowed_users: Optional[dict] = None


@router.get("")
async def list_flags(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tüm feature flag'leri listeler.

    Sistemde tanımlı tüm özellik bayraklarını isim sırasıyla döndürür.
    Her flag için durum, yüzde, izin verilen kullanıcılar ve açıklama bilgisi dahildir.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    result = await db.execute(select(FeatureFlag).order_by(FeatureFlag.name))
    return [
        {
            "id": f.id,
            "name": f.name,
            "enabled": f.enabled,
            "description": f.description,
            "percentage": f.percentage,
            "allowed_users": f.allowed_users,
            "updated_at": f.updated_at.isoformat(),
        }
        for f in result.scalars().all()
    ]


@router.post("", dependencies=[Depends(require_admin_dep)])
async def create_flag(
    req: FlagCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yeni bir feature flag oluşturur.

    İsim, başlangıç durumu, açıklama ve yüzde ile yeni flag tanımlar.
    Oluşturma sonrası flag cache'i invalidate edilir.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    flag = FeatureFlag(
        name=req.name,
        enabled=req.enabled,
        description=req.description,
        percentage=req.percentage,
    )
    db.add(flag)
    await db.commit()
    await db.refresh(flag)
    invalidate_cache()
    return {"id": flag.id, "name": flag.name, "enabled": flag.enabled}


@router.patch("/{flag_name}", dependencies=[Depends(require_admin_dep)])
async def update_flag(
    flag_name: str,
    req: FlagUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mevcut bir feature flag'i günceller.

    Durum, açıklama, yüzde ve izin verilen kullanıcılar kısmi olarak güncellenebilir.
    Güncelleme sonrası flag cache'i invalidate edilir.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Feature flag bulunamadı
    """
    result = await db.execute(select(FeatureFlag).where(FeatureFlag.name == flag_name))
    flag = result.scalar_one_or_none()
    if not flag:
        raise HTTPException(status_code=404, detail="Feature flag not found")
    if req.enabled is not None:
        flag.enabled = req.enabled
    if req.description is not None:
        flag.description = req.description
    if req.percentage is not None:
        flag.percentage = req.percentage
    if req.allowed_users is not None:
        flag.allowed_users = req.allowed_users
    flag.updated_at = datetime.utcnow()
    await db.commit()
    invalidate_cache()
    return {"name": flag.name, "enabled": flag.enabled, "percentage": flag.percentage}


@router.get("/check/{flag_name}")
async def check_flag(
    flag_name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Belirtilen feature flag'in mevcut kullanıcı için aktif olup olmadığını kontrol eder.

    Flag'in genel durumu, yüzde tabanlı rollout ve kullanıcı bazlı
    izin listesi değerlendirilerek sonuç döndürülür.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    enabled = await is_enabled(db, flag_name, current_user["id"])
    return {"flag": flag_name, "enabled": enabled}
