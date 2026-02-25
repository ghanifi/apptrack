import hashlib
import logging
from datetime import datetime
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import AuditLog, ImmutableAuditEntry
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


def _compute_hash(sequence: int, action: str, resource_type: str, resource_id: str, details: dict, previous_hash: str) -> str:
    data = f"{sequence}:{action}:{resource_type}:{resource_id}:{details}:{previous_hash}"
    return hashlib.sha256(data.encode()).hexdigest()


async def create_immutable_audit(
    db: AsyncSession,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str = None,
    details: dict = None,
    ip_address: str = None,
) -> ImmutableAuditEntry:
    max_seq = await db.execute(select(func.max(ImmutableAuditEntry.sequence_number)))
    last_seq = max_seq.scalar() or 0
    new_seq = last_seq + 1

    last_entry = await db.execute(
        select(ImmutableAuditEntry).where(ImmutableAuditEntry.sequence_number == last_seq)
    )
    prev = last_entry.scalar_one_or_none()
    previous_hash = prev.entry_hash if prev else "0" * 64

    entry_hash = _compute_hash(new_seq, action, resource_type, resource_id or "", details or {}, previous_hash)

    entry = ImmutableAuditEntry(
        sequence_number=new_seq,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
    )
    db.add(entry)
    await db.flush()
    return entry
