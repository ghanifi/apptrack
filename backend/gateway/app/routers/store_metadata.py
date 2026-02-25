import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Project, StoreMetadata

router = APIRouter()
logger = logging.getLogger(__name__)


class StoreMetadataUpsert(BaseModel):
    app_name: Optional[str] = None
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    keywords: Optional[str] = None
    privacy_url: Optional[str] = None
    support_url: Optional[str] = None
    marketing_url: Optional[str] = None
    category: Optional[str] = None
    bundle_id: Optional[str] = None
    version: Optional[str] = None
    icon_url: Optional[str] = None
    screenshots: Optional[dict] = None
    feature_graphic_url: Optional[str] = None


def _serialize(meta: StoreMetadata) -> dict:
    return {
        "id": meta.id,
        "project_id": meta.project_id,
        "platform": meta.platform,
        "app_name": meta.app_name,
        "short_description": meta.short_description,
        "full_description": meta.full_description,
        "keywords": meta.keywords,
        "privacy_url": meta.privacy_url,
        "support_url": meta.support_url,
        "marketing_url": meta.marketing_url,
        "category": meta.category,
        "bundle_id": meta.bundle_id,
        "version": meta.version,
        "icon_url": meta.icon_url,
        "screenshots": meta.screenshots,
        "feature_graphic_url": meta.feature_graphic_url,
        "created_at": meta.created_at.isoformat(),
        "updated_at": meta.updated_at.isoformat(),
    }


async def _verify_project_ownership(db: AsyncSession, project_id: str, user_id: str) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/store-metadata")
async def get_store_metadata(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_ownership(db, project_id, current_user["id"])
    result = await db.execute(
        select(StoreMetadata).where(StoreMetadata.project_id == project_id)
    )
    entries = result.scalars().all()
    return [_serialize(e) for e in entries]


@router.put("/{project_id}/store-metadata/{platform}")
async def upsert_store_metadata(
    project_id: str,
    platform: str,
    req: StoreMetadataUpsert,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if platform not in ("android", "ios"):
        raise HTTPException(status_code=400, detail="Platform must be 'android' or 'ios'")
    await _verify_project_ownership(db, project_id, current_user["id"])

    result = await db.execute(
        select(StoreMetadata).where(
            StoreMetadata.project_id == project_id,
            StoreMetadata.platform == platform,
        )
    )
    meta = result.scalar_one_or_none()

    if meta:
        for field, value in req.model_dump(exclude_unset=True).items():
            setattr(meta, field, value)
        meta.updated_at = datetime.utcnow()
    else:
        meta = StoreMetadata(
            project_id=project_id,
            platform=platform,
            **req.model_dump(exclude_unset=True),
        )
        db.add(meta)

    await db.commit()
    await db.refresh(meta)
    return _serialize(meta)


@router.post("/{project_id}/store-metadata/{platform}/icon")
async def update_icon_url(
    project_id: str,
    platform: str,
    req: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if platform not in ("android", "ios"):
        raise HTTPException(status_code=400, detail="Platform must be 'android' or 'ios'")
    await _verify_project_ownership(db, project_id, current_user["id"])

    result = await db.execute(
        select(StoreMetadata).where(
            StoreMetadata.project_id == project_id,
            StoreMetadata.platform == platform,
        )
    )
    meta = result.scalar_one_or_none()
    if not meta:
        meta = StoreMetadata(project_id=project_id, platform=platform)
        db.add(meta)

    meta.icon_url = req.get("icon_url", "")
    meta.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(meta)
    return _serialize(meta)


@router.post("/{project_id}/store-metadata/{platform}/screenshots")
async def update_screenshots(
    project_id: str,
    platform: str,
    req: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if platform not in ("android", "ios"):
        raise HTTPException(status_code=400, detail="Platform must be 'android' or 'ios'")
    await _verify_project_ownership(db, project_id, current_user["id"])

    result = await db.execute(
        select(StoreMetadata).where(
            StoreMetadata.project_id == project_id,
            StoreMetadata.platform == platform,
        )
    )
    meta = result.scalar_one_or_none()
    if not meta:
        meta = StoreMetadata(project_id=project_id, platform=platform)
        db.add(meta)

    meta.screenshots = req.get("screenshots", {})
    meta.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(meta)
    return _serialize(meta)
