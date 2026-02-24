from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Deployment, Build, Project, IdempotencyRecord
from app import events
from app.routers.credentials import get_user_credential
from app.limiter import limiter
from app.audit import record_audit_with_db
from app.quotas import check_deploy_quota, track_usage

router = APIRouter()

ARTIFACT_MAX_AGE_HOURS = 24


def _serialize_dep(d: Deployment) -> dict:
    return {
        "id": d.id,
        "build_id": d.build_id,
        "target": d.target,
        "track": d.track,
        "status": d.status,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    }


@router.get("")
async def list_deployments(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_q = (
        select(Deployment)
        .join(Build, Deployment.build_id == Build.id)
        .join(Project, Build.project_id == Project.id)
        .where(Project.owner_id == current_user["id"])
    )
    if status_filter:
        base_q = base_q.where(Deployment.status == status_filter)
    base_q = base_q.order_by(Deployment.created_at.desc())

    count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total = count_result.scalar() or 0
    offset = (page - 1) * size
    result = await db.execute(base_q.offset(offset).limit(size))

    return {
        "items": [_serialize_dep(d) for d in result.scalars().all()],
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, (total + size - 1) // size),
    }


@router.get("/project/{project_id}")
async def list_project_deployments(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj = await db.execute(select(Project).where(Project.id == project_id))
    project = proj.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Deployment)
        .join(Build, Deployment.build_id == Build.id)
        .where(Build.project_id == project_id)
        .order_by(Deployment.created_at.desc())
    )
    return [_serialize_dep(d) for d in result.scalars().all()]


class DeployRequest(BaseModel):
    target: str = "google_play"
    track: str = "internal"
    package_name: str = ""


@router.post("/{build_id}/deploy")
@limiter.limit("10/hour")
async def deploy(
    request: Request,
    build_id: str,
    req: DeployRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    if x_idempotency_key:
        existing = await db.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.key == x_idempotency_key,
                IdempotencyRecord.endpoint == "deploy",
                IdempotencyRecord.user_id == current_user["id"],
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Duplicate request — this deploy was already submitted")

    result = await db.execute(select(Build).where(Build.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    proj = await db.execute(select(Project).where(Project.id == build.project_id))
    project = proj.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    if build.status != "success" or not build.artifact_url:
        raise HTTPException(
            status_code=400,
            detail=f"Build is not ready for deployment (status={build.status}, artifact_url={'present' if build.artifact_url else 'missing'})",
        )

    if build.finished_at:
        age = datetime.utcnow() - build.finished_at
        if age > timedelta(hours=ARTIFACT_MAX_AGE_HOURS):
            raise HTTPException(
                status_code=400,
                detail=f"Artifact is too old ({age.total_seconds()/3600:.1f}h). Maximum age is {ARTIFACT_MAX_AGE_HOURS}h. Please rebuild.",
            )

    await check_deploy_quota(db, current_user["id"])

    dep = Deployment(build_id=build_id, target=req.target, track=req.track)
    db.add(dep)

    if x_idempotency_key:
        idem = IdempotencyRecord(
            key=x_idempotency_key,
            endpoint="deploy",
            user_id=current_user["id"],
        )
        db.add(idem)

    await db.commit()
    await db.refresh(dep)

    await record_audit_with_db(
        db, action="deploy.triggered", resource_type="deployment",
        resource_id=dep.id, user_id=current_user["id"],
        details={"build_id": build_id, "target": req.target, "track": req.track},
        request=request,
    )
    await track_usage(db, current_user["id"], "deploys", 1, {"target": req.target})
    await db.commit()

    event_payload: dict = {
        "deployment_id": dep.id,
        "build_id": build_id,
        "owner_id": project.owner_id if project else current_user["id"],
        "target": req.target,
        "track": req.track,
        "artifact_url": build.artifact_url,
        "artifact_checksum": getattr(build, "artifact_checksum", None),
        "package_name": req.package_name,
    }

    if req.target == "google_play":
        key_json = await get_user_credential(db, current_user["id"], "google_play", "GOOGLE_PLAY_KEY_JSON")
        event_payload["google_play_key_json"] = key_json
    elif req.target == "app_store":
        event_payload["app_store_key_id"] = await get_user_credential(db, current_user["id"], "app_store", "APP_STORE_KEY_ID")
        event_payload["app_store_issuer_id"] = await get_user_credential(db, current_user["id"], "app_store", "APP_STORE_ISSUER_ID")
        event_payload["app_store_private_key"] = await get_user_credential(db, current_user["id"], "app_store", "APP_STORE_PRIVATE_KEY")
        event_payload["eas_token"] = await get_user_credential(db, current_user["id"], "eas", "EAS_TOKEN")
        event_payload["expo_app_id"] = await get_user_credential(db, current_user["id"], "eas", "EXPO_APP_ID")

    await events.publish_event("deploy.triggered", event_payload)
    return _serialize_dep(dep)
