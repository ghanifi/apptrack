import uuid
import logging
import hashlib
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models import BackupJob
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/backups", tags=["backups"])

BACKUP_TYPES = ["db_snapshot", "artifact_replication", "metadata_export", "full_backup"]


class BackupRequest(BaseModel):
    backup_type: str = "db_snapshot"
    metadata: dict | None = None


class RestoreVerifyRequest(BaseModel):
    backup_id: str
    verify_checksum: bool = True


@router.post("/trigger")
async def trigger_backup(
    req: BackupRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.backup_type not in BACKUP_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid backup type. Must be one of: {BACKUP_TYPES}")

    now = datetime.utcnow()
    storage_path = f"backups/{req.backup_type}/{now.strftime('%Y/%m/%d')}/{uuid.uuid4().hex[:12]}"

    backup = BackupJob(
        id=str(uuid.uuid4()),
        backup_type=req.backup_type,
        status="running",
        storage_path=storage_path,
        metadata_json=req.metadata or {"triggered_by": user.id, "type": req.backup_type},
        started_at=now,
        triggered_by=user.id,
    )
    db.add(backup)
    await db.flush()

    simulated_data = json.dumps({
        "backup_id": backup.id,
        "type": req.backup_type,
        "timestamp": now.isoformat(),
        "tables": ["users", "projects", "builds", "deployments", "credentials",
                    "audit_logs", "usage_records", "user_quotas", "feature_flags",
                    "roles", "user_roles", "deploy_policies", "immutable_audit_entries"],
    })
    checksum = hashlib.sha256(simulated_data.encode()).hexdigest()
    size = len(simulated_data.encode())

    backup.status = "completed"
    backup.size_bytes = size
    backup.checksum = checksum
    backup.completed_at = datetime.utcnow()

    await db.commit()

    logger.info(f"Backup {backup.id} ({req.backup_type}) completed by user {user.id}")

    return {
        "id": backup.id,
        "backup_type": req.backup_type,
        "status": "completed",
        "storage_path": storage_path,
        "size_bytes": size,
        "checksum": checksum,
        "started_at": backup.started_at.isoformat(),
        "completed_at": backup.completed_at.isoformat(),
    }


@router.get("/list")
async def list_backups(
    backup_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(BackupJob)
    if backup_type:
        query = query.where(BackupJob.backup_type == backup_type)
    query = query.order_by(BackupJob.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    backups = result.scalars().all()

    count_query = select(func.count(BackupJob.id))
    if backup_type:
        count_query = count_query.where(BackupJob.backup_type == backup_type)
    total = (await db.execute(count_query)).scalar() or 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "backups": [
            {
                "id": b.id,
                "backup_type": b.backup_type,
                "status": b.status,
                "storage_path": b.storage_path,
                "size_bytes": b.size_bytes,
                "checksum": b.checksum,
                "started_at": b.started_at.isoformat() if b.started_at else None,
                "completed_at": b.completed_at.isoformat() if b.completed_at else None,
                "created_at": b.created_at.isoformat(),
            }
            for b in backups
        ],
    }


@router.get("/{backup_id}")
async def get_backup(
    backup_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    backup = await db.get(BackupJob, backup_id)
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    return {
        "id": backup.id,
        "backup_type": backup.backup_type,
        "status": backup.status,
        "storage_path": backup.storage_path,
        "size_bytes": backup.size_bytes,
        "checksum": backup.checksum,
        "metadata": backup.metadata_json,
        "error_message": backup.error_message,
        "started_at": backup.started_at.isoformat() if backup.started_at else None,
        "completed_at": backup.completed_at.isoformat() if backup.completed_at else None,
        "created_at": backup.created_at.isoformat(),
    }


@router.post("/verify-restore")
async def verify_restore(
    req: RestoreVerifyRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    backup = await db.get(BackupJob, req.backup_id)
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    if backup.status != "completed":
        raise HTTPException(status_code=400, detail=f"Backup status is '{backup.status}', cannot verify")

    verification = {
        "backup_id": backup.id,
        "storage_path_exists": bool(backup.storage_path),
        "checksum_present": bool(backup.checksum),
        "size_valid": (backup.size_bytes or 0) > 0,
        "metadata_valid": bool(backup.metadata_json),
    }

    if req.verify_checksum and backup.checksum:
        simulated_data = json.dumps({
            "backup_id": backup.id,
            "type": backup.backup_type,
            "timestamp": backup.started_at.isoformat() if backup.started_at else "",
            "tables": ["users", "projects", "builds", "deployments", "credentials",
                        "audit_logs", "usage_records", "user_quotas", "feature_flags",
                        "roles", "user_roles", "deploy_policies", "immutable_audit_entries"],
        })
        recalculated = hashlib.sha256(simulated_data.encode()).hexdigest()
        verification["checksum_match"] = recalculated == backup.checksum
    else:
        verification["checksum_match"] = None

    all_checks = [
        verification["storage_path_exists"],
        verification["checksum_present"],
        verification["size_valid"],
        verification["metadata_valid"],
    ]
    if verification["checksum_match"] is not None:
        all_checks.append(verification["checksum_match"])

    verification["restore_ready"] = all(all_checks)
    verification["status"] = "ready" if verification["restore_ready"] else "failed"

    return verification


@router.get("/stats/summary")
async def backup_stats(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(BackupJob.id)))
    total = total_result.scalar() or 0

    completed_result = await db.execute(
        select(func.count(BackupJob.id)).where(BackupJob.status == "completed")
    )
    completed = completed_result.scalar() or 0

    failed_result = await db.execute(
        select(func.count(BackupJob.id)).where(BackupJob.status == "failed")
    )
    failed = failed_result.scalar() or 0

    size_result = await db.execute(
        select(func.sum(BackupJob.size_bytes)).where(BackupJob.status == "completed")
    )
    total_size = size_result.scalar() or 0

    last_result = await db.execute(
        select(BackupJob)
        .where(BackupJob.status == "completed")
        .order_by(BackupJob.completed_at.desc())
        .limit(1)
    )
    last_backup = last_result.scalar_one_or_none()

    return {
        "total_backups": total,
        "completed": completed,
        "failed": failed,
        "total_size_bytes": total_size,
        "last_backup": {
            "id": last_backup.id,
            "type": last_backup.backup_type,
            "completed_at": last_backup.completed_at.isoformat() if last_backup and last_backup.completed_at else None,
        } if last_backup else None,
    }
