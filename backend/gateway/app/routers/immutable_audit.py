import uuid
import json
import hashlib
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models import ImmutableAuditEntry
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/immutable-audit", tags=["immutable-audit"])

GENESIS_HASH = "0" * 64


def compute_entry_hash(
    sequence_number: int,
    user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    details: dict | None,
    previous_hash: str,
    timestamp: str,
) -> str:
    payload = json.dumps({
        "seq": sequence_number,
        "user": user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "prev": previous_hash,
        "ts": timestamp,
    }, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


async def append_immutable_entry(
    db: AsyncSession,
    user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> ImmutableAuditEntry:
    await db.execute(text("SELECT pg_advisory_xact_lock(20240101)"))
    last_result = await db.execute(
        select(ImmutableAuditEntry)
        .order_by(ImmutableAuditEntry.sequence_number.desc())
        .limit(1)
        .with_for_update()
    )
    last_entry = last_result.scalar_one_or_none()

    previous_hash = last_entry.entry_hash if last_entry else GENESIS_HASH
    next_seq = (last_entry.sequence_number + 1) if last_entry else 1

    now = datetime.utcnow()
    entry_hash = compute_entry_hash(
        sequence_number=next_seq,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        previous_hash=previous_hash,
        timestamp=now.isoformat(),
    )

    entry = ImmutableAuditEntry(
        id=str(uuid.uuid4()),
        sequence_number=next_seq,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
        created_at=now,
    )
    db.add(entry)
    return entry


@router.get("/entries")
async def list_audit_entries(
    page: int = 1,
    page_size: int = 50,
    action: str | None = None,
    resource_type: str | None = None,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Değiştirilemez denetim günlüğü kayıtlarını sayfalı olarak listeler.

    Aksiyon ve kaynak türüne göre filtreleme destekler.
    Kayıtlar sıra numarasına göre en yeniden en eskiye sıralanır.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    query = select(ImmutableAuditEntry)
    if action:
        query = query.where(ImmutableAuditEntry.action == action)
    if resource_type:
        query = query.where(ImmutableAuditEntry.resource_type == resource_type)

    query = query.order_by(ImmutableAuditEntry.sequence_number.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    entries = result.scalars().all()

    count_query = select(func.count(ImmutableAuditEntry.id))
    if action:
        count_query = count_query.where(ImmutableAuditEntry.action == action)
    if resource_type:
        count_query = count_query.where(ImmutableAuditEntry.resource_type == resource_type)
    total = (await db.execute(count_query)).scalar() or 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "entries": [
            {
                "id": e.id,
                "sequence_number": e.sequence_number,
                "user_id": e.user_id,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "details": e.details,
                "previous_hash": e.previous_hash,
                "entry_hash": e.entry_hash,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
    }


@router.get("/verify")
async def verify_chain_integrity(
    limit: int = 1000,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Denetim günlüğü hash zincirinin bütünlüğünü doğrular.

    Her kaydın hash değerini yeniden hesaplayarak ve önceki hash bağlantısını
    kontrol ederek zincirin manipüle edilip edilmediğini tespit eder.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    result = await db.execute(
        select(ImmutableAuditEntry)
        .order_by(ImmutableAuditEntry.sequence_number.asc())
        .limit(limit)
    )
    entries = result.scalars().all()

    if not entries:
        return {"status": "empty", "verified_count": 0, "tampered": False}

    tampered_entries = []
    previous_hash = GENESIS_HASH

    for entry in entries:
        if entry.previous_hash != previous_hash:
            tampered_entries.append({
                "sequence_number": entry.sequence_number,
                "issue": "previous_hash_mismatch",
                "expected": previous_hash,
                "actual": entry.previous_hash,
            })

        expected_hash = compute_entry_hash(
            sequence_number=entry.sequence_number,
            user_id=entry.user_id,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            details=entry.details,
            previous_hash=entry.previous_hash,
            timestamp=entry.created_at.isoformat(),
        )
        if entry.entry_hash != expected_hash:
            tampered_entries.append({
                "sequence_number": entry.sequence_number,
                "issue": "entry_hash_mismatch",
                "expected": expected_hash,
                "actual": entry.entry_hash,
            })

        previous_hash = entry.entry_hash

    return {
        "status": "tampered" if tampered_entries else "intact",
        "verified_count": len(entries),
        "tampered": len(tampered_entries) > 0,
        "tampered_entries": tampered_entries[:20],
    }


@router.get("/entry/{sequence_number}")
async def get_audit_entry(
    sequence_number: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Belirtilen sıra numarasına sahip denetim kaydını getirir.

    Kayıt detaylarını, hash değerlerini ve IP adresi bilgisini
    içeren tam denetim günlüğü girişini döndürür.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Denetim kaydı bulunamadı
    """
    result = await db.execute(
        select(ImmutableAuditEntry).where(
            ImmutableAuditEntry.sequence_number == sequence_number
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    return {
        "id": entry.id,
        "sequence_number": entry.sequence_number,
        "user_id": entry.user_id,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "details": entry.details,
        "ip_address": entry.ip_address,
        "previous_hash": entry.previous_hash,
        "entry_hash": entry.entry_hash,
        "created_at": entry.created_at.isoformat(),
    }
