import logging
from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.dependencies import get_current_user
from app.database import get_db
from app.models import AuditLog

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının audit log kayıtlarını sayfalanmış olarak listeler.

    Action ve resource_type bazında filtreleme destekler. Sonuçlar tarih
    sırasıyla azalan şekilde döndürülür. IP adresi ve trace ID bilgileri dahildir.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    base_q = select(AuditLog).where(AuditLog.user_id == current_user["id"])
    if action:
        base_q = base_q.where(AuditLog.action == action)
    if resource_type:
        base_q = base_q.where(AuditLog.resource_type == resource_type)
    base_q = base_q.order_by(AuditLog.created_at.desc())

    count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total = count_result.scalar() or 0
    offset = (page - 1) * size
    result = await db.execute(base_q.offset(offset).limit(size))
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": log.id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "trace_id": log.trace_id,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, (total + size - 1) // size),
    }


@router.get("/actions")
async def list_audit_actions(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının audit log'larındaki benzersiz action türlerini listeler.

    Her action türü ve kaç kez gerçekleştiği bilgisini döndürür.
    Sayıya göre azalan sırada sıralanır. Filtreleme için kullanılabilir.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    result = await db.execute(
        select(AuditLog.action, func.count().label("count"))
        .where(AuditLog.user_id == current_user["id"])
        .group_by(AuditLog.action)
        .order_by(func.count().desc())
    )
    return [{"action": row[0], "count": row[1]} for row in result.all()]
