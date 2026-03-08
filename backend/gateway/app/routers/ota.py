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
from app.models import Project, Credential, OTAUpdate
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
    """Expo EAS Update API üzerinden OTA güncelleme tetikler.

    EAS token ve Expo app ID ile Expo sunucusuna güncelleme isteği gönderir.
    Credential'lar istek veya credential yöneticisinden alınır.

    Raises:
        400: EAS_TOKEN veya EXPO_APP_ID eksik
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı
        502: EAS Update API hatası
        503: EAS Update bağlantı hatası
    """
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
    """EAS projesine ait güncelleme dallarını listeler.

    Expo API üzerinden belirtilen uygulama için tanımlı
    tüm branch bilgilerini getirir.

    Raises:
        400: EAS_TOKEN yapılandırılmamış
        401: Kimlik doğrulama gerekli
        502: EAS API hatası
        503: Bağlantı hatası
    """
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
    """EAS projesine ait OTA güncellemelerini listeler.

    İsteğe bağlı olarak branch'e göre filtreleme yaparak
    Expo API üzerinden güncelleme geçmişini getirir.

    Raises:
        400: EAS_TOKEN yapılandırılmamış
        401: Kimlik doğrulama gerekli
        502: EAS API hatası
        503: Bağlantı hatası
    """
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


@router.get("/check/{project_id}")
async def check_for_update(
    project_id: str,
    channel: str = "production",
    platform: str = "all",
    runtime_version: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — no auth required. Called by mobile apps to check for OTA updates.

    Returns the latest published update for the given project/channel/platform.
    If runtime_version is provided, only returns updates with matching runtime_version.
    """
    query = (
        select(OTAUpdate)
        .where(
            OTAUpdate.project_id == project_id,
            OTAUpdate.channel == channel,
            OTAUpdate.status == "published",
            OTAUpdate.platform.in_([platform, "all"]),
        )
    )
    if runtime_version:
        query = query.where(OTAUpdate.runtime_version == runtime_version)

    query = query.order_by(OTAUpdate.created_at.desc()).limit(1)
    result = await db.execute(query)
    update = result.scalar_one_or_none()

    if not update:
        return {"available": False}

    return {
        "available": True,
        "update_id": update.id,
        "bundle_url": update.bundle_url,
        "runtime_version": update.runtime_version,
        "channel": update.channel,
        "platform": update.platform,
        "message": update.message,
        "created_at": update.created_at.isoformat() if update.created_at else None,
    }


@router.post("/custom-bundle")
async def push_custom_bundle(
    req: OTAUpdateCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Non-EAS projeler icin custom bundle ile OTA update gonderir (Flutter, React Native bare)."""
    project = await db.get(Project, req.project_id)
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Proje bulunamadi")

    if not req.bundle_url:
        raise HTTPException(
            status_code=400,
            detail="bundle_url zorunludur. MinIO'ya yuklenen artifact URL'ini belirtin."
        )

    update = OTAUpdate(
        id=str(uuid.uuid4()),
        project_id=req.project_id,
        channel=req.channel,
        platform=req.platform,
        runtime_version=req.runtime_version,
        bundle_url=req.bundle_url,
        message=req.message,
        status="published",
        created_by=current_user["id"],
    )
    db.add(update)
    await db.commit()
    await db.refresh(update)

    return {
        "status": "published",
        "update_id": update.id,
        "bundle_url": update.bundle_url,
        "channel": update.channel,
        "platform": update.platform,
        "runtime_version": update.runtime_version,
        "message": update.message,
    }


@router.get("/custom-bundle/{project_id}/history")
async def list_custom_bundle_updates(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Projenin custom bundle OTA guncelleme gecmisini listeler."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Proje bulunamadi")

    result = await db.execute(
        select(OTAUpdate)
        .where(OTAUpdate.project_id == project_id)
        .order_by(OTAUpdate.created_at.desc())
        .limit(50)
    )
    updates = result.scalars().all()
    return [
        {
            "update_id": u.id,
            "channel": u.channel,
            "platform": u.platform,
            "runtime_version": u.runtime_version,
            "bundle_url": u.bundle_url,
            "message": u.message,
            "status": u.status,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in updates
    ]


@router.post("/rollback")
async def rollback_eas_update(
    expo_app_id: str = "",
    branch: str = "",
    update_id: str = "",
    project_id: str = "",
    channel: str = "production",
    platform: str = "all",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """OTA güncellemesini önceki versiyona geri alır.

    EAS projesi ise Expo Rollback API kullanır. Custom bundle projesi ise
    bir önceki başarılı bundle URL'i ile yeni güncelleme yayınlar.

    Raises:
        400: Gerekli parametreler eksik
        401: Kimlik doğrulama gerekli
        404: Proje veya önceki güncelleme bulunamadı
        502: EAS Rollback API hatası
        503: Bağlantı hatası
    """
    eas_token = await _get_credential(db, current_user["id"], "eas", "EAS_TOKEN")

    # EAS projesi degilse custom bundle rollback
    if not eas_token:
        if not project_id:
            raise HTTPException(
                status_code=400,
                detail="EAS_TOKEN bulunamadi ve project_id belirtilmedi. "
                       "EAS rollback icin EAS_TOKEN, custom bundle rollback icin project_id gereklidir.",
            )

        project = await db.get(Project, project_id)
        if not project or project.owner_id != current_user["id"]:
            raise HTTPException(status_code=404, detail="Proje bulunamadi")

        # Son basarili bundle'a geri don
        last_good = await db.execute(
            select(OTAUpdate)
            .where(
                OTAUpdate.project_id == project_id,
                OTAUpdate.status == "published",
            )
            .order_by(OTAUpdate.created_at.desc())
            .offset(1)  # skip current, get previous
            .limit(1)
        )
        prev_update = last_good.scalar_one_or_none()
        if not prev_update:
            raise HTTPException(status_code=404, detail="Geri donulecek onceki guncelleme bulunamadi")

        # Yeni update olarak publish et (eski bundle URL ile)
        rollback_update = OTAUpdate(
            id=str(uuid.uuid4()),
            project_id=project_id,
            channel=channel,
            platform=platform,
            runtime_version=prev_update.runtime_version,
            bundle_url=prev_update.bundle_url,
            message=f"Rollback to {prev_update.runtime_version}",
            status="published",
            created_by=current_user["id"],
        )
        db.add(rollback_update)
        await db.commit()
        return {
            "status": "rolled_back",
            "rollback_to": prev_update.id,
            "bundle_url": prev_update.bundle_url,
            "runtime_version": prev_update.runtime_version,
        }

    # EAS rollback
    if not expo_app_id or not branch or not update_id:
        raise HTTPException(
            status_code=400,
            detail="EAS rollback icin expo_app_id, branch ve update_id zorunludur.",
        )

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
