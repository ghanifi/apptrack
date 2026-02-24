import uuid
import logging
from datetime import datetime, time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models import DeployPolicy, DeployApproval, Build, Deployment, Project
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/deploy-policies", tags=["deploy-policies"])


POLICY_TYPES = [
    "branch_restriction",
    "approval_required",
    "time_window",
    "artifact_age_limit",
    "artifact_signature",
    "build_status_check",
]


class PolicyCreateRequest(BaseModel):
    name: str
    policy_type: str
    rules: dict
    enabled: bool = True


class PolicyUpdateRequest(BaseModel):
    name: str | None = None
    rules: dict | None = None
    enabled: bool | None = None


class ApprovalRequest(BaseModel):
    decision: str
    comment: str | None = None


@router.post("/{project_id}")
async def create_policy(
    project_id: str,
    req: PolicyCreateRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    if req.policy_type not in POLICY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid policy type. Must be one of: {POLICY_TYPES}")

    policy = DeployPolicy(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=req.name,
        enabled=req.enabled,
        policy_type=req.policy_type,
        rules=req.rules,
        created_by=user.id,
    )
    db.add(policy)
    await db.commit()

    return {
        "id": policy.id,
        "name": policy.name,
        "policy_type": policy.policy_type,
        "rules": policy.rules,
        "enabled": policy.enabled,
    }


@router.get("/{project_id}")
async def list_policies(
    project_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DeployPolicy).where(DeployPolicy.project_id == project_id)
        .order_by(DeployPolicy.created_at.desc())
    )
    policies = result.scalars().all()

    return {
        "project_id": project_id,
        "policies": [
            {
                "id": p.id,
                "name": p.name,
                "policy_type": p.policy_type,
                "rules": p.rules,
                "enabled": p.enabled,
                "created_at": p.created_at.isoformat(),
            }
            for p in policies
        ],
    }


@router.put("/{project_id}/{policy_id}")
async def update_policy(
    project_id: str,
    policy_id: str,
    req: PolicyUpdateRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DeployPolicy).where(
            and_(DeployPolicy.id == policy_id, DeployPolicy.project_id == project_id)
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    if req.name is not None:
        policy.name = req.name
    if req.rules is not None:
        policy.rules = req.rules
    if req.enabled is not None:
        policy.enabled = req.enabled

    await db.commit()

    return {
        "id": policy.id,
        "name": policy.name,
        "rules": policy.rules,
        "enabled": policy.enabled,
    }


@router.delete("/{project_id}/{policy_id}")
async def delete_policy(
    project_id: str,
    policy_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DeployPolicy).where(
            and_(DeployPolicy.id == policy_id, DeployPolicy.project_id == project_id)
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    await db.delete(policy)
    await db.commit()

    return {"status": "deleted", "policy_id": policy_id}


async def evaluate_deploy_policies(
    db: AsyncSession,
    project_id: str,
    build: Build,
    deployment: Deployment | None = None,
) -> dict:
    result = await db.execute(
        select(DeployPolicy).where(
            and_(DeployPolicy.project_id == project_id, DeployPolicy.enabled == True)
        )
    )
    policies = result.scalars().all()

    violations = []
    warnings = []

    project = await db.get(Project, project_id)

    for policy in policies:
        if policy.policy_type == "branch_restriction":
            allowed = policy.rules.get("allowed_branches", ["main"])
            if project and project.branch not in allowed:
                violations.append({
                    "policy": policy.name,
                    "type": "branch_restriction",
                    "message": f"Branch '{project.branch}' is not in allowed list: {allowed}",
                })

        elif policy.policy_type == "build_status_check":
            required_status = policy.rules.get("required_status", "success")
            if build.status != required_status:
                violations.append({
                    "policy": policy.name,
                    "type": "build_status_check",
                    "message": f"Build status is '{build.status}', required '{required_status}'",
                })

        elif policy.policy_type == "artifact_age_limit":
            max_hours = policy.rules.get("max_age_hours", 24)
            if build.finished_at:
                age = (datetime.utcnow() - build.finished_at).total_seconds() / 3600
                if age > max_hours:
                    violations.append({
                        "policy": policy.name,
                        "type": "artifact_age_limit",
                        "message": f"Artifact age {age:.1f}h exceeds limit {max_hours}h",
                    })

        elif policy.policy_type == "artifact_signature":
            require_checksum = policy.rules.get("require_checksum", True)
            if require_checksum and not build.artifact_checksum:
                violations.append({
                    "policy": policy.name,
                    "type": "artifact_signature",
                    "message": "Artifact checksum is missing",
                })

        elif policy.policy_type == "time_window":
            allowed_start = policy.rules.get("start_hour", 9)
            allowed_end = policy.rules.get("end_hour", 17)
            allowed_days = policy.rules.get("allowed_days", [0, 1, 2, 3, 4])
            now = datetime.utcnow()
            if now.weekday() not in allowed_days:
                violations.append({
                    "policy": policy.name,
                    "type": "time_window",
                    "message": f"Deploy not allowed on {now.strftime('%A')}",
                })
            elif not (allowed_start <= now.hour < allowed_end):
                violations.append({
                    "policy": policy.name,
                    "type": "time_window",
                    "message": f"Deploy not allowed at {now.hour}:00 (window: {allowed_start}-{allowed_end})",
                })

        elif policy.policy_type == "approval_required":
            if deployment:
                min_approvals = policy.rules.get("min_approvals", 1)
                approval_result = await db.execute(
                    select(DeployApproval).where(
                        and_(
                            DeployApproval.deployment_id == deployment.id,
                            DeployApproval.decision == "approved",
                        )
                    )
                )
                approvals = approval_result.scalars().all()
                if len(approvals) < min_approvals:
                    violations.append({
                        "policy": policy.name,
                        "type": "approval_required",
                        "message": f"Need {min_approvals} approvals, have {len(approvals)}",
                    })

    return {
        "allowed": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
        "policies_evaluated": len(policies),
    }


@router.post("/evaluate/{project_id}/{build_id}")
async def evaluate_policies(
    project_id: str,
    build_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    build = await db.get(Build, build_id)
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    evaluation = await evaluate_deploy_policies(db, project_id, build)
    return evaluation


@router.post("/approve/{deployment_id}")
async def approve_deployment(
    deployment_id: str,
    req: ApprovalRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deployment = await db.get(Deployment, deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    if req.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'")

    existing = await db.execute(
        select(DeployApproval).where(
            and_(
                DeployApproval.deployment_id == deployment_id,
                DeployApproval.approver_id == user.id,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already submitted approval")

    approval = DeployApproval(
        id=str(uuid.uuid4()),
        deployment_id=deployment_id,
        approver_id=user.id,
        decision=req.decision,
        comment=req.comment,
    )
    db.add(approval)
    await db.commit()

    return {
        "deployment_id": deployment_id,
        "approver_id": user.id,
        "decision": req.decision,
        "status": "recorded",
    }


@router.get("/approvals/{deployment_id}")
async def list_approvals(
    deployment_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DeployApproval).where(DeployApproval.deployment_id == deployment_id)
    )
    approvals = result.scalars().all()

    return {
        "deployment_id": deployment_id,
        "approvals": [
            {
                "id": a.id,
                "approver_id": a.approver_id,
                "decision": a.decision,
                "comment": a.comment,
                "created_at": a.created_at.isoformat(),
            }
            for a in approvals
        ],
    }
