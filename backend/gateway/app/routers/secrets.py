import uuid
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models import Credential, SecretRotationLog
from app.dependencies import get_current_user
from app.crypto import encrypt, decrypt, re_encrypt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/secrets", tags=["secrets"])

DEFAULT_ROTATION_DAYS = 90
EXPIRY_WARNING_DAYS = 14


class RotationPolicy(BaseModel):
    rotation_interval_days: int = DEFAULT_ROTATION_DAYS
    auto_rotate: bool = False


class CredentialHealthResponse(BaseModel):
    credential_id: str
    provider: str
    key_name: str
    status: str
    days_until_expiry: int | None = None
    days_until_rotation: int | None = None
    last_rotated: str | None = None
    rotation_count: int = 0


class RotationResponse(BaseModel):
    credential_id: str
    old_version: str
    new_version: str
    status: str


@router.get("/health")
async def credential_health_check(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Credential).where(Credential.owner_id == user.id)
    )
    creds = result.scalars().all()
    now = datetime.utcnow()
    health_report = []

    for cred in creds:
        status = "healthy"
        days_until_expiry = None
        days_until_rotation = None

        if cred.expires_at:
            delta = (cred.expires_at - now).days
            days_until_expiry = delta
            if delta <= 0:
                status = "expired"
            elif delta <= EXPIRY_WARNING_DAYS:
                status = "expiring_soon"

        if cred.rotation_due_at:
            rot_delta = (cred.rotation_due_at - now).days
            days_until_rotation = rot_delta
            if rot_delta <= 0 and status == "healthy":
                status = "rotation_overdue"
            elif rot_delta <= EXPIRY_WARNING_DAYS and status == "healthy":
                status = "rotation_due_soon"

        health_report.append(CredentialHealthResponse(
            credential_id=cred.id,
            provider=cred.provider,
            key_name=cred.key_name,
            status=status,
            days_until_expiry=days_until_expiry,
            days_until_rotation=days_until_rotation,
            last_rotated=cred.last_rotated_at.isoformat() if cred.last_rotated_at else None,
            rotation_count=cred.rotation_count or 0,
        ))

    expired_count = sum(1 for h in health_report if h.status == "expired")
    warning_count = sum(1 for h in health_report if h.status in ("expiring_soon", "rotation_overdue", "rotation_due_soon"))

    return {
        "total": len(health_report),
        "healthy": len(health_report) - expired_count - warning_count,
        "warnings": warning_count,
        "expired": expired_count,
        "credentials": [h.model_dump() for h in health_report],
    }


@router.post("/rotate/{credential_id}")
async def rotate_credential(
    credential_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Credential).where(
            and_(Credential.id == credential_id, Credential.owner_id == user.id)
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    old_version = cred.key_version or "v1"
    new_version_num = int(old_version.replace("v", "")) + 1
    new_version = f"v{new_version_num}"

    re_encrypted = re_encrypt(cred.encrypted_value)
    if re_encrypted is None:
        raise HTTPException(status_code=500, detail="Failed to re-encrypt credential")

    cred.encrypted_value = re_encrypted
    cred.key_version = new_version
    cred.last_rotated_at = datetime.utcnow()
    cred.rotation_count = (cred.rotation_count or 0) + 1
    cred.rotation_due_at = datetime.utcnow() + timedelta(days=DEFAULT_ROTATION_DAYS)

    rotation_log = SecretRotationLog(
        id=str(uuid.uuid4()),
        credential_id=cred.id,
        old_key_version=old_version,
        new_key_version=new_version,
        rotation_type="manual",
        triggered_by=user.id,
        status="completed",
    )
    db.add(rotation_log)
    await db.commit()

    logger.info(f"Credential {cred.id} rotated from {old_version} to {new_version} by user {user.id}")

    return RotationResponse(
        credential_id=cred.id,
        old_version=old_version,
        new_version=new_version,
        status="completed",
    )


@router.post("/rotate-all")
async def rotate_all_credentials(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Credential).where(Credential.owner_id == user.id)
    )
    creds = result.scalars().all()
    rotated = []

    for cred in creds:
        old_version = cred.key_version or "v1"
        new_version_num = int(old_version.replace("v", "")) + 1
        new_version = f"v{new_version_num}"

        re_encrypted = re_encrypt(cred.encrypted_value)
        if re_encrypted is None:
            continue

        cred.encrypted_value = re_encrypted
        cred.key_version = new_version
        cred.last_rotated_at = datetime.utcnow()
        cred.rotation_count = (cred.rotation_count or 0) + 1
        cred.rotation_due_at = datetime.utcnow() + timedelta(days=DEFAULT_ROTATION_DAYS)

        rotation_log = SecretRotationLog(
            id=str(uuid.uuid4()),
            credential_id=cred.id,
            old_key_version=old_version,
            new_key_version=new_version,
            rotation_type="bulk_manual",
            triggered_by=user.id,
            status="completed",
        )
        db.add(rotation_log)
        rotated.append(cred.id)

    await db.commit()

    return {"rotated_count": len(rotated), "credential_ids": rotated}


@router.put("/policy/{credential_id}")
async def set_rotation_policy(
    credential_id: str,
    policy: RotationPolicy,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Credential).where(
            and_(Credential.id == credential_id, Credential.owner_id == user.id)
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    cred.rotation_due_at = datetime.utcnow() + timedelta(days=policy.rotation_interval_days)
    if cred.expires_at is None:
        cred.expires_at = datetime.utcnow() + timedelta(days=policy.rotation_interval_days * 2)

    await db.commit()

    return {
        "credential_id": cred.id,
        "rotation_due_at": cred.rotation_due_at.isoformat(),
        "expires_at": cred.expires_at.isoformat(),
    }


@router.get("/rotation-history/{credential_id}")
async def get_rotation_history(
    credential_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cred_result = await db.execute(
        select(Credential).where(
            and_(Credential.id == credential_id, Credential.owner_id == user.id)
        )
    )
    if not cred_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Credential not found")

    result = await db.execute(
        select(SecretRotationLog)
        .where(SecretRotationLog.credential_id == credential_id)
        .order_by(SecretRotationLog.rotated_at.desc())
        .limit(50)
    )
    logs = result.scalars().all()

    return {
        "credential_id": credential_id,
        "history": [
            {
                "id": log.id,
                "old_version": log.old_key_version,
                "new_version": log.new_key_version,
                "type": log.rotation_type,
                "status": log.status,
                "rotated_at": log.rotated_at.isoformat(),
            }
            for log in logs
        ],
    }


@router.get("/expiring")
async def get_expiring_credentials(
    days: int = 30,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    threshold = datetime.utcnow() + timedelta(days=days)
    result = await db.execute(
        select(Credential).where(
            and_(
                Credential.owner_id == user.id,
                Credential.expires_at <= threshold,
                Credential.expires_at != None,
            )
        ).order_by(Credential.expires_at.asc())
    )
    creds = result.scalars().all()
    now = datetime.utcnow()

    return {
        "count": len(creds),
        "credentials": [
            {
                "id": c.id,
                "provider": c.provider,
                "key_name": c.key_name,
                "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                "days_remaining": (c.expires_at - now).days if c.expires_at else None,
            }
            for c in creds
        ],
    }
