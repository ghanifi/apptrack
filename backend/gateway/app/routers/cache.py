import logging
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from app.dependencies import get_current_user
from app.database import get_db
from app.models import BuildCache, Project

router = APIRouter(prefix="/api/projects", tags=["build-cache"])
logger = logging.getLogger(__name__)


@router.get("/{project_id}/cache")
async def get_cache_info(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Proje build cache bilgilerini döndürür.

    Toplam cache boyutu, cache sayısı ve her cache kaydının
    detaylarını listeler.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı
    """
    project = await _verify_project_owner(db, project_id, current_user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(BuildCache)
        .where(BuildCache.project_id == project_id)
        .order_by(BuildCache.last_used.desc())
    )
    caches = result.scalars().all()

    total_size = sum(c.size_bytes for c in caches)

    return {
        "project_id": project_id,
        "cache_count": len(caches),
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "caches": [
            {
                "id": c.id,
                "cache_key": c.cache_key,
                "s3_path": c.s3_path,
                "size_bytes": c.size_bytes,
                "size_mb": round(c.size_bytes / (1024 * 1024), 2),
                "last_used": c.last_used.isoformat(),
                "created_at": c.created_at.isoformat(),
            }
            for c in caches
        ],
    }


@router.delete("/{project_id}/cache")
async def clear_cache(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Projenin tüm build cache kayıtlarını siler.

    MinIO/S3'teki cache nesneleri de temizlenmek üzere işaretlenir.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı
    """
    project = await _verify_project_owner(db, project_id, current_user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(func.count()).select_from(BuildCache).where(BuildCache.project_id == project_id)
    )
    count = result.scalar() or 0

    await db.execute(delete(BuildCache).where(BuildCache.project_id == project_id))
    await db.commit()

    logger.info("Cache cleared: project=%s entries=%d", project_id, count)
    return {"deleted": count, "message": f"Cleared {count} cache entries."}


@router.delete("/{project_id}/cache/{cache_id}")
async def delete_cache_entry(
    project_id: str,
    cache_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Belirli bir build cache kaydını siler.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Proje veya cache kaydı bulunamadı
    """
    project = await _verify_project_owner(db, project_id, current_user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(BuildCache).where(
            and_(BuildCache.id == cache_id, BuildCache.project_id == project_id)
        )
    )
    cache = result.scalar_one_or_none()
    if not cache:
        raise HTTPException(status_code=404, detail="Cache entry not found")

    await db.delete(cache)
    await db.commit()
    return {"deleted": True}


def compute_cache_key(lockfile_content: str, branch: str) -> str:
    """Lockfile içeriği ve branch adından cache key hesaplar."""
    data = f"{branch}:{lockfile_content}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


async def get_or_create_cache(
    db: AsyncSession, project_id: str, cache_key: str, s3_path: str, size_bytes: int = 0
) -> BuildCache:
    """Cache kaydını getirir veya yeni oluşturur."""
    result = await db.execute(
        select(BuildCache).where(
            and_(BuildCache.project_id == project_id, BuildCache.cache_key == cache_key)
        )
    )
    cache = result.scalar_one_or_none()
    if cache:
        cache.last_used = datetime.utcnow()
        cache.s3_path = s3_path
        cache.size_bytes = size_bytes
    else:
        cache = BuildCache(
            project_id=project_id,
            cache_key=cache_key,
            s3_path=s3_path,
            size_bytes=size_bytes,
        )
        db.add(cache)
    await db.flush()
    return cache


async def _verify_project_owner(db: AsyncSession, project_id: str, user_id: str):
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == user_id))
    )
    return result.scalar_one_or_none()
