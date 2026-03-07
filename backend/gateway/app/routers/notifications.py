import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.limiter import limiter
from app.models import Notification, NotificationPreference

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool | None = None
    slack_enabled: bool | None = None
    slack_webhook_url: str | None = None
    discord_enabled: bool | None = None
    discord_webhook_url: str | None = None
    in_app_enabled: bool | None = None
    notify_build_success: bool | None = None
    notify_build_failed: bool | None = None
    notify_deploy_completed: bool | None = None
    notify_deploy_failed: bool | None = None
    notify_quota_warning: bool | None = None


@router.get("")
@limiter.limit("30/minute")
async def list_notifications(
    request,
    unread_only: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Notification).where(
        Notification.user_id == current_user["id"]
    ).order_by(Notification.created_at.desc()).offset(offset).limit(limit)

    if unread_only:
        query = query.where(Notification.read == False)

    result = await db.execute(query)
    notifications = result.scalars().all()

    unread_count = (await db.execute(
        select(func.count()).where(
            and_(Notification.user_id == current_user["id"], Notification.read == False)
        )
    )).scalar() or 0

    return {
        "items": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "read": n.read,
                "channel": n.channel,
                "resource_type": n.resource_type,
                "resource_id": n.resource_id,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
        "unread_count": unread_count,
    }


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            and_(Notification.id == notification_id, Notification.user_id == current_user["id"])
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.read = True
    await db.commit()
    return {"status": "ok"}


@router.post("/read-all")
async def mark_all_as_read(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(and_(Notification.user_id == current_user["id"], Notification.read == False))
        .values(read=True)
    )
    await db.commit()
    return {"status": "ok"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            and_(Notification.id == notification_id, Notification.user_id == current_user["id"])
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    await db.delete(notification)
    await db.commit()
    return {"status": "deleted"}


@router.get("/preferences")
async def get_preferences(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user["id"]
        )
    )
    pref = result.scalar_one_or_none()
    if not pref:
        pref = NotificationPreference(user_id=current_user["id"])
        db.add(pref)
        await db.commit()
        await db.refresh(pref)

    return {
        "email_enabled": pref.email_enabled,
        "slack_enabled": pref.slack_enabled,
        "slack_webhook_url": pref.slack_webhook_url,
        "discord_enabled": pref.discord_enabled,
        "discord_webhook_url": pref.discord_webhook_url,
        "in_app_enabled": pref.in_app_enabled,
        "notify_build_success": pref.notify_build_success,
        "notify_build_failed": pref.notify_build_failed,
        "notify_deploy_completed": pref.notify_deploy_completed,
        "notify_deploy_failed": pref.notify_deploy_failed,
        "notify_quota_warning": pref.notify_quota_warning,
    }


@router.put("/preferences")
async def update_preferences(
    body: NotificationPreferenceUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user["id"]
        )
    )
    pref = result.scalar_one_or_none()
    if not pref:
        pref = NotificationPreference(user_id=current_user["id"])
        db.add(pref)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(pref, field, value)

    pref.updated_at = datetime.utcnow()
    await db.commit()
    return {"status": "updated"}
