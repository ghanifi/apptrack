import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.database import get_db
from app.models import Role, RolePermission, UserRole, User, Project
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rbac", tags=["rbac"])


class AssignRoleRequest(BaseModel):
    user_id: str
    role_name: str
    project_id: str


class PermissionCheckRequest(BaseModel):
    resource: str
    action: str
    project_id: str


async def get_user_permissions(db: AsyncSession, user_id: str, project_id: str) -> set[tuple[str, str]]:
    result = await db.execute(
        select(RolePermission)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            and_(
                UserRole.user_id == user_id,
                UserRole.project_id == project_id,
            )
        )
    )
    perms = result.scalars().all()
    return {(p.resource, p.action) for p in perms}


async def check_permission(db: AsyncSession, user_id: str, project_id: str, resource: str, action: str) -> bool:
    project = await db.get(Project, project_id)
    if project and project.owner_id == user_id:
        return True

    perms = await get_user_permissions(db, user_id, project_id)
    return (resource, action) in perms


async def require_permission(db: AsyncSession, user_id: str, project_id: str, resource: str, action: str):
    has_perm = await check_permission(db, user_id, project_id, resource, action)
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {resource}:{action}",
        )


@router.get("/roles")
async def list_roles(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions))
    )
    roles = result.scalars().all()
    return {
        "roles": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "is_system": r.is_system,
                "permissions": [
                    {"resource": p.resource, "action": p.action}
                    for p in r.permissions
                ],
            }
            for r in roles
        ]
    }


@router.post("/assign")
async def assign_role(
    req: AssignRoleRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_permission(db, user.id, req.project_id, "member", "invite")

    role_result = await db.execute(
        select(Role).where(Role.name == req.role_name)
    )
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role '{req.role_name}' not found")

    target_user = await db.get(User, req.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    project = await db.get(Project, req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    existing = await db.execute(
        select(UserRole).where(
            and_(
                UserRole.user_id == req.user_id,
                UserRole.project_id == req.project_id,
            )
        )
    )
    existing_role = existing.scalar_one_or_none()

    if existing_role:
        existing_role.role_id = role.id
    else:
        new_role = UserRole(
            id=str(uuid.uuid4()),
            user_id=req.user_id,
            role_id=role.id,
            project_id=req.project_id,
            granted_by=user.id,
        )
        db.add(new_role)

    await db.commit()

    logger.info(f"Role '{req.role_name}' assigned to user {req.user_id} for project {req.project_id} by {user.id}")

    return {
        "user_id": req.user_id,
        "role": req.role_name,
        "project_id": req.project_id,
        "status": "assigned",
    }


@router.delete("/revoke")
async def revoke_role(
    user_id: str,
    project_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_permission(db, user.id, project_id, "member", "remove")

    result = await db.execute(
        select(UserRole).where(
            and_(UserRole.user_id == user_id, UserRole.project_id == project_id)
        )
    )
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Role assignment not found")

    await db.delete(existing)
    await db.commit()

    return {"user_id": user_id, "project_id": project_id, "status": "revoked"}


@router.get("/members/{project_id}")
async def list_project_members(
    project_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_permission(db, user.id, project_id, "member", "read")

    result = await db.execute(
        select(UserRole, User, Role)
        .join(User, User.id == UserRole.user_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.project_id == project_id)
    )
    members = result.all()

    project = await db.get(Project, project_id)
    member_list = []

    if project:
        member_list.append({
            "user_id": project.owner_id,
            "role": "owner",
            "is_owner": True,
            "granted_at": project.created_at.isoformat(),
        })

    for ur, u, r in members:
        if u.id == project.owner_id:
            continue
        member_list.append({
            "user_id": u.id,
            "name": u.name,
            "email": u.email,
            "role": r.name,
            "is_owner": False,
            "granted_at": ur.created_at.isoformat(),
        })

    return {"project_id": project_id, "members": member_list}


@router.post("/check-permission")
async def check_user_permission(
    req: PermissionCheckRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    has_perm = await check_permission(db, user.id, req.project_id, req.resource, req.action)
    return {
        "user_id": user.id,
        "resource": req.resource,
        "action": req.action,
        "project_id": req.project_id,
        "allowed": has_perm,
    }


@router.get("/my-permissions/{project_id}")
async def get_my_permissions(
    project_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.owner_id == user.id:
        role_result = await db.execute(
            select(Role).options(selectinload(Role.permissions)).where(Role.name == "owner")
        )
        owner_role = role_result.scalar_one_or_none()
        if owner_role:
            return {
                "role": "owner",
                "is_owner": True,
                "permissions": [
                    {"resource": p.resource, "action": p.action}
                    for p in owner_role.permissions
                ],
            }

    perms = await get_user_permissions(db, user.id, project_id)

    ur_result = await db.execute(
        select(UserRole, Role)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            and_(UserRole.user_id == user.id, UserRole.project_id == project_id)
        )
    )
    ur_row = ur_result.first()
    role_name = ur_row[1].name if ur_row else "none"

    return {
        "role": role_name,
        "is_owner": False,
        "permissions": [
            {"resource": r, "action": a} for r, a in perms
        ],
    }
