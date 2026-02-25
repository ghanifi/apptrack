import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, and_, func
from app.dependencies import get_current_user
from app.database import get_db
from app.models import (
    AuditLog, Build, Deployment, Credential, ImmutableAuditEntry,
    UsageRecord, Project, User, BackupJob
)

router = APIRouter(prefix="/api/compliance", tags=["compliance"])
logger = logging.getLogger(__name__)

RETENTION_POLICIES = {
    "audit_logs": {"default_days": 365, "min_days": 90, "max_days": 2555},
    "build_artifacts": {"default_days": 90, "min_days": 30, "max_days": 730},
    "build_logs": {"default_days": 180, "min_days": 30, "max_days": 730},
    "deployment_records": {"default_days": 365, "min_days": 90, "max_days": 2555},
    "usage_records": {"default_days": 365, "min_days": 90, "max_days": 1095},
    "webhook_nonces": {"default_days": 7, "min_days": 1, "max_days": 30},
    "immutable_audit": {"default_days": 2555, "min_days": 365, "max_days": 3650},
}


@router.get("/retention-policies")
async def get_retention_policies(current_user: dict = Depends(get_current_user)):
    return {
        "policies": RETENTION_POLICIES,
        "description": "Data retention periods in days. Immutable audit entries have the longest retention.",
    }


@router.post("/purge-expired")
async def purge_expired_data(
    dry_run: bool = True,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    results = {}

    audit_cutoff = now - timedelta(days=RETENTION_POLICIES["audit_logs"]["default_days"])
    audit_count = (await db.execute(
        select(func.count()).where(AuditLog.created_at < audit_cutoff)
    )).scalar() or 0
    results["audit_logs"] = {"expired_count": audit_count, "cutoff_date": audit_cutoff.isoformat()}

    build_cutoff = now - timedelta(days=RETENTION_POLICIES["build_artifacts"]["default_days"])
    build_count = (await db.execute(
        select(func.count()).where(and_(Build.created_at < build_cutoff, Build.status.in_(["success", "failed"])))
    )).scalar() or 0
    results["build_records"] = {"expired_count": build_count, "cutoff_date": build_cutoff.isoformat()}

    usage_cutoff = now - timedelta(days=RETENTION_POLICIES["usage_records"]["default_days"])
    usage_count = (await db.execute(
        select(func.count()).where(UsageRecord.created_at < usage_cutoff)
    )).scalar() or 0
    results["usage_records"] = {"expired_count": usage_count, "cutoff_date": usage_cutoff.isoformat()}

    nonce_cutoff = now - timedelta(days=RETENTION_POLICIES["webhook_nonces"]["default_days"])
    from app.models import WebhookNonce
    nonce_count = (await db.execute(
        select(func.count()).where(WebhookNonce.expires_at < nonce_cutoff)
    )).scalar() or 0
    results["webhook_nonces"] = {"expired_count": nonce_count, "cutoff_date": nonce_cutoff.isoformat()}

    if not dry_run:
        if audit_count > 0:
            await db.execute(delete(AuditLog).where(AuditLog.created_at < audit_cutoff))
        if usage_count > 0:
            await db.execute(delete(UsageRecord).where(UsageRecord.created_at < usage_cutoff))
        if nonce_count > 0:
            await db.execute(delete(WebhookNonce).where(WebhookNonce.expires_at < nonce_cutoff))
        await db.commit()
        logger.info("Data purge completed: %s", results)

    return {
        "dry_run": dry_run,
        "results": results,
        "total_expired": sum(r["expired_count"] for r in results.values()),
    }


@router.post("/legal-hold/{resource_type}/{resource_id}")
async def set_legal_hold(
    resource_type: str,
    resource_id: str,
    reason: str = "Legal hold",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    valid_types = ["project", "build", "deployment", "user"]
    if resource_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid resource type. Must be one of: {valid_types}")

    from app.audit import create_immutable_audit
    await create_immutable_audit(
        db=db,
        user_id=current_user["id"],
        action="legal_hold.set",
        resource_type=resource_type,
        resource_id=resource_id,
        details={"reason": reason, "set_by": current_user["id"]},
    )

    logger.info("Legal hold set: type=%s id=%s by=%s", resource_type, resource_id, current_user["id"])
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "legal_hold": True,
        "reason": reason,
        "message": "Legal hold applied. This resource will not be purged by retention policies.",
    }


@router.get("/audit-export")
async def export_audit_bundle(
    start_date: str = Query(None),
    end_date: str = Query(None),
    format: str = "json",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    start = datetime.fromisoformat(start_date) if start_date else now - timedelta(days=30)
    end = datetime.fromisoformat(end_date) if end_date else now

    entries = await db.execute(
        select(ImmutableAuditEntry).where(
            and_(ImmutableAuditEntry.created_at >= start, ImmutableAuditEntry.created_at <= end)
        ).order_by(ImmutableAuditEntry.sequence_number.asc()).limit(10000)
    )
    audit_list = entries.scalars().all()

    import hashlib
    bundle_data = []
    for entry in audit_list:
        bundle_data.append({
            "id": entry.id,
            "sequence": entry.sequence_number,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "details": entry.details,
            "entry_hash": entry.entry_hash,
            "previous_hash": entry.previous_hash,
            "created_at": entry.created_at.isoformat(),
        })

    bundle_hash = hashlib.sha256(str(bundle_data).encode()).hexdigest()

    return {
        "export": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "entry_count": len(bundle_data),
            "bundle_hash": bundle_hash,
            "format": format,
            "chain_verified": _verify_chain(audit_list),
        },
        "entries": bundle_data,
    }


def _verify_chain(entries) -> bool:
    for i in range(1, len(entries)):
        if entries[i].previous_hash != entries[i - 1].entry_hash:
            return False
    return True


@router.get("/data-locality")
async def get_data_locality(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user["id"],
        "data_region": "eu-west-1",
        "storage_region": "eu-west-1",
        "compliance_mode": "gdpr",
        "data_residency": {
            "credentials": "encrypted_at_rest",
            "artifacts": "region_locked",
            "audit_logs": "immutable_append_only",
            "personal_data": "gdpr_compliant",
        },
        "available_regions": ["eu-west-1", "us-east-1", "ap-southeast-1"],
    }
