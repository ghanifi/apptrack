import re
import hashlib
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Project, Build, Deployment, User
from app import events
from app.config import settings
from app.routers.credentials import get_user_credential
from app.crypto import decrypt
from app.limiter import limiter
from app.validators import validate_repo_url, validate_branch, AppError
from app.audit import record_audit_with_db
from app.quotas import check_project_quota, check_build_quota, track_usage
from app.abuse_guard import check_build_spam
from app.cost_guard import estimate_build_cost, check_budget_limit

router = APIRouter()
logger = logging.getLogger(__name__)


async def _register_github_webhook(project: Project, token: str) -> None:
    match = re.match(r'https://github\.com/([^/]+)/([^/\.]+)', project.repo_url)
    if not match:
        return
    owner, repo = match.groups()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{owner}/{repo}/hooks",
                headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
                json={
                    "name": "web",
                    "active": True,
                    "events": ["push"],
                    "config": {
                        "url": f"{settings.GATEWAY_URL}/api/webhooks/github",
                        "content_type": "json",
                        "secret": settings.GITHUB_WEBHOOK_SECRET,
                        "insecure_ssl": "0",
                    },
                },
            )
            if resp.status_code in (201, 422):
                logger.info("GitHub webhook registered for %s/%s (status=%s)", owner, repo, resp.status_code)
            else:
                logger.warning("Webhook registration failed %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("_register_github_webhook error: %s", exc)


class ProjectCreate(BaseModel):
    name: str
    repo_url: str
    branch: str = "main"


class ProjectUpdate(BaseModel):
    name: str | None = None
    branch: str | None = None


class BuildResponse(BaseModel):
    id: str
    platform: str
    provider: str
    status: str
    artifact_url: str | None
    created_at: str

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: str
    name: str
    repo_url: str
    branch: str
    framework: str
    status: str
    created_at: str
    updated_at: str
    owner_id: str
    builds: List[BuildResponse] = []

    class Config:
        from_attributes = True


def _serialize_project(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "repo_url": p.repo_url,
        "branch": p.branch,
        "framework": p.framework,
        "status": p.status,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
        "owner_id": p.owner_id,
        "builds": [
            {
                "id": b.id,
                "platform": b.platform,
                "provider": b.provider,
                "status": b.status,
                "artifact_url": b.artifact_url,
                "created_at": b.created_at.isoformat(),
            }
            for b in p.builds
        ],
    }


@router.get("")
async def list_projects(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_q = select(Project).where(Project.owner_id == current_user["id"])
    if status_filter:
        base_q = base_q.where(Project.status == status_filter)
    base_q = base_q.order_by(Project.created_at.desc())

    count_result = await db.execute(
        select(func.count()).select_from(base_q.subquery())
    )
    total = count_result.scalar() or 0

    offset = (page - 1) * size
    result = await db.execute(base_q.offset(offset).limit(size))
    projects = result.scalars().all()
    return {
        "items": [_serialize_project(p) for p in projects],
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, (total + size - 1) // size),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ProjectCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo_url = validate_repo_url(req.repo_url)
    branch = validate_branch(req.branch)

    await check_project_quota(db, current_user["id"])

    project = Project(
        name=req.name.strip(),
        repo_url=repo_url,
        branch=branch,
        owner_id=current_user["id"],
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    await record_audit_with_db(
        db, action="project.created", resource_type="project",
        resource_id=project.id, user_id=current_user["id"],
        details={"name": project.name, "repo_url": project.repo_url},
    )
    await db.commit()

    await events.publish_event(
        "project.created",
        {
            "project_id": project.id,
            "repo_url": project.repo_url,
            "branch": project.branch,
            "owner_id": project.owner_id,
            "trace_id": getattr(req, "trace_id", None),
        },
    )

    user_result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = user_result.scalar_one_or_none()
    if user and user.github_access_token and settings.GITHUB_WEBHOOK_SECRET:
        try:
            raw_token = decrypt(user.github_access_token)
        except Exception:
            raw_token = user.github_access_token
        await _register_github_webhook(project, raw_token)

    return _serialize_project(project)


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    return _serialize_project(project)


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    req: ProjectUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    if req.name:
        project.name = req.name
    if req.branch:
        project.branch = req.branch
    project.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(project)
    return _serialize_project(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()


@router.post("/{project_id}/sync")
async def sync_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    project.status = "analyzing"
    project.updated_at = datetime.utcnow()
    await db.commit()

    await events.publish_event(
        "project.created",
        {"project_id": project.id, "repo_url": project.repo_url, "branch": project.branch, "owner_id": project.owner_id},
    )
    return {"status": "sync_triggered", "project_id": project_id}


@router.post("/{project_id}/build")
@limiter.limit("10/hour")
async def trigger_build(
    request: Request,
    project_id: str,
    platform: str = "both",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.framework == "unknown":
        raise HTTPException(status_code=400, detail="Framework not detected yet")

    await check_build_quota(db, current_user["id"])

    spam_msg = check_build_spam(current_user["id"])
    if spam_msg:
        raise HTTPException(status_code=429, detail=spam_msg)

    provider_map = {
        "flutter": "codemagic",
        "expo": "eas",
        "react_native": "eas",
        "swift": "github_actions",
        "kotlin": "github_actions",
    }
    provider = provider_map.get(project.framework, "github_actions")

    cost_estimate = await estimate_build_cost(provider, platform)
    await check_budget_limit(db, current_user["id"], cost_estimate["estimated_cost_usd"])

    idem_key = hashlib.sha256(f"{project.id}:{project.branch}:{platform}".encode()).hexdigest()
    existing = await db.execute(
        select(Build).where(
            and_(
                Build.idempotency_key == idem_key,
                Build.status.in_(["queued", "running"]),
                Build.created_at >= datetime.utcnow() - timedelta(minutes=10),
            )
        )
    )
    dup = existing.scalar_one_or_none()
    if dup:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate build — an active build ({dup.id}) already exists for this project/platform. Wait for it to finish or cancel it first.",
        )

    build = Build(
        project_id=project.id,
        platform=platform,
        provider=provider,
        status="queued",
        idempotency_key=idem_key,
    )
    db.add(build)
    project.status = "building"
    project.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(build)

    await record_audit_with_db(
        db, action="build.triggered", resource_type="build",
        resource_id=build.id, user_id=current_user["id"],
        details={"project_id": project.id, "platform": platform, "provider": provider},
        request=request,
    )
    await track_usage(db, current_user["id"], "builds", 1, {"provider": provider, "platform": platform})
    await db.commit()

    await events.publish_event(
        "build.triggered",
        {
            "build_id": build.id,
            "project_id": project.id,
            "owner_id": project.owner_id,
            "framework": project.framework,
            "platform": platform,
            "provider": provider,
            "repo_url": project.repo_url,
            "branch": project.branch,
            "clone_path": project.clone_path,
            "eas_token": await get_user_credential(db, current_user["id"], "eas", "EAS_TOKEN") if provider == "eas" else None,
            "expo_app_id": await get_user_credential(db, current_user["id"], "eas", "EXPO_APP_ID") if provider == "eas" else None,
            "codemagic_token": await get_user_credential(db, current_user["id"], "codemagic", "CODEMAGIC_TOKEN") if provider == "codemagic" else None,
            "codemagic_app_id": await get_user_credential(db, current_user["id"], "codemagic", "CODEMAGIC_APP_ID") if provider == "codemagic" else None,
        },
    )

    return {
        "build_id": build.id,
        "status": "queued",
        "provider": provider,
        "platform": platform,
        "cost_estimate": cost_estimate,
    }


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


class DeployRequest(BaseModel):
    target: str = "google_play"
    track: str = "internal"
    package_name: str = ""


@router.get("/{project_id}/deployments")
async def list_project_deployments(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    dep_result = await db.execute(
        select(Deployment)
        .join(Build, Deployment.build_id == Build.id)
        .where(Build.project_id == project_id)
        .order_by(Deployment.created_at.desc())
    )
    return [_serialize_dep(d) for d in dep_result.scalars().all()]


@router.post("/{project_id}/deploy")
@limiter.limit("10/hour")
async def deploy_project(
    request: Request,
    project_id: str,
    req: DeployRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    build_result = await db.execute(
        select(Build)
        .where(Build.project_id == project_id, Build.status == "success")
        .order_by(Build.created_at.desc())
        .limit(1)
    )
    build = build_result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=400, detail="No successful build found for this project")

    dep = Deployment(build_id=build.id, target=req.target, track=req.track)
    db.add(dep)
    await db.commit()
    await db.refresh(dep)

    event_payload: dict = {
        "deployment_id": dep.id,
        "build_id": build.id,
        "owner_id": project.owner_id,
        "target": req.target,
        "track": req.track,
        "artifact_url": build.artifact_url,
        "package_name": req.package_name,
    }

    if req.target == "google_play":
        event_payload["google_play_key_json"] = await get_user_credential(
            db, current_user["id"], "google_play", "GOOGLE_PLAY_KEY_JSON"
        )
    elif req.target == "app_store":
        event_payload["app_store_key_id"] = await get_user_credential(
            db, current_user["id"], "app_store", "APP_STORE_KEY_ID"
        )
        event_payload["app_store_issuer_id"] = await get_user_credential(
            db, current_user["id"], "app_store", "APP_STORE_ISSUER_ID"
        )
        event_payload["app_store_private_key"] = await get_user_credential(
            db, current_user["id"], "app_store", "APP_STORE_PRIVATE_KEY"
        )
        event_payload["eas_token"] = await get_user_credential(
            db, current_user["id"], "eas", "EAS_TOKEN"
        )
        event_payload["expo_app_id"] = await get_user_credential(
            db, current_user["id"], "eas", "EXPO_APP_ID"
        )

    await events.publish_event("deploy.triggered", event_payload)
    return _serialize_dep(dep)
