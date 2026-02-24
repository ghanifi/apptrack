import logging
from datetime import datetime
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AuditLog
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def record_audit(
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    user_id: str | None = None,
    details: dict | None = None,
    request: Request | None = None,
):
    try:
        ip_address = None
        user_agent = None
        trace_id = None
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent", "")[:500]
            trace_id = getattr(request.state, "trace_id", None)

        async with AsyncSessionLocal() as db:
            log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                trace_id=trace_id,
            )
            db.add(log)
            await db.commit()
    except Exception as exc:
        logger.error("Failed to record audit log: %s", exc)


async def record_audit_with_db(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    user_id: str | None = None,
    details: dict | None = None,
    request: Request | None = None,
):
    try:
        ip_address = None
        user_agent = None
        trace_id = None
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent", "")[:500]
            trace_id = getattr(request.state, "trace_id", None)

        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            trace_id=trace_id,
        )
        db.add(log)
    except Exception as exc:
        logger.error("Failed to record audit log: %s", exc)
