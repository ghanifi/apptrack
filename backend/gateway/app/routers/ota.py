import hashlib
import uuid
import httpx
from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Project, Credential
from app.crypto import decrypt

router = APIRouter()


class OTAUpdateCreate(BaseModel):
    project_id: str
    message: str = ""
    channel: str = "production"
    platform: Literal["android", "ios", "all"] = "all"
    runtime_version: str = "1.0.0"
    bundle_url: str = ""


class EASUpdateCreate(BaseModel):
    project_id: str
    expo_app_id: str
    eas_token: str = ""
    branch: str = "production"
    message: str = ""
    platform: Literal["android", "ios", "all"] = "all"


async def _get_credential(db: AsyncSession, owner_id: str, provider: str, key_name: str) -> str | None:
    result = await db.execute(
        select(Credential).where(
            and_(
                Credential.owner_id == owner_id,
                Credential.provider == provider,
                Credential.key_name == key_name,
            )
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        return None
    try:
        return decrypt(cred.encrypted_value)
    except Exception:
        return None


@router.post("/eas-update")
async def trigger_eas_update(
    req: EASUpdateCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj_result = await db.execute(
        select(Project).where(
            and_(Project.id == req.project_id, Project.owner_id == current_user["id"])
        )
    )
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    eas_token = req.eas_token or await _get_credential(db, current_user["id"], "eas", "EAS_TOKEN")
    expo_app_id = req.expo_app_id or await _get_credential(db, current_user["id"], "eas", "EXPO_APP_ID")

    if not eas_token or not expo_app_id:
        raise HTTPException(
            status_code=400,
            detail="EAS_TOKEN and EXPO_APP_ID are required. Configure them in the credentials manager.",
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.expo.dev/v2/projects/{expo_app_id}/updates",
                headers={"Authorization": f"Bearer {eas_token}", "Content-Type": "application/json"},
                json={
                    "branchName": req.branch,
                    "message": req.message or f"OTA update {datetime.utcnow().isoformat()}",
                    "platform": req.platform,
                },
            )
        if resp.status_code in (200, 201):
            data = resp.json().get("data") or resp.json()
            return {
                "status": "triggered",
                "update_id": data.get("id"),
                "branch": req.branch,
                "platform": req.platform,
                "message": req.message,
                "provider": "eas_update",
                "expo_app_id": expo_app_id,
            }
        raise HTTPException(
            status_code=502,
            detail=f"EAS Update API error {resp.status_code}: {resp.text[:300]}",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"EAS Update failed: {exc}")


@router.get("/eas-update/{expo_app_id}/branches")
async def list_eas_branches(
    expo_app_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    eas_token = await _get_credential(db, current_user["id"], "eas", "EAS_TOKEN")
    if not eas_token:
        raise HTTPException(status_code=400, detail="EAS_TOKEN not configured")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.expo.dev/v2/projects/{expo_app_id}/branches",
                headers={"Authorization": f"Bearer {eas_token}"},
            )
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=502, detail=f"EAS API error {resp.status_code}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/eas-update/{expo_app_id}/updates")
async def list_eas_updates(
    expo_app_id: str,
    branch: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    eas_token = await _get_credential(db, current_user["id"], "eas", "EAS_TOKEN")
    if not eas_token:
        raise HTTPException(status_code=400, detail="EAS_TOKEN not configured")

    params = {}
    if branch:
        params["branchName"] = branch

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.expo.dev/v2/projects/{expo_app_id}/updates",
                headers={"Authorization": f"Bearer {eas_token}"},
                params=params,
            )
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=502, detail=f"EAS API error {resp.status_code}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/rollback")
async def rollback_eas_update(
    expo_app_id: str,
    branch: str,
    update_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    eas_token = await _get_credential(db, current_user["id"], "eas", "EAS_TOKEN")
    if not eas_token:
        raise HTTPException(status_code=400, detail="EAS_TOKEN not configured")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"https://api.expo.dev/v2/projects/{expo_app_id}/branches/{branch}/rollbacks",
                headers={"Authorization": f"Bearer {eas_token}", "Content-Type": "application/json"},
                json={"targetUpdateId": update_id},
            )
        if resp.status_code in (200, 201):
            return {"status": "rolled_back", "target_update_id": update_id, "branch": branch}
        raise HTTPException(status_code=502, detail=f"EAS Rollback API error {resp.status_code}: {resp.text[:200]}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
