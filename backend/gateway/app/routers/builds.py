import uuid
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Build, Project, Credential
from app.crypto import decrypt
from app.config import settings as app_settings
from app.cost_guard import estimate_build_cost, get_monthly_spend
from app.routers.rbac import require_permission

router = APIRouter()


class BuildDetailResponse(BaseModel):
    id: str
    project_id: str
    platform: str
    provider: str
    status: str
    artifact_url: str | None = None
    external_build_id: str | None = None
    idempotency_key: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str

    class Config:
        from_attributes = True


class PaginatedBuildResponse(BaseModel):
    items: List[BuildDetailResponse]
    total: int
    page: int
    size: int
    pages: int


class CancelBuildResponse(BuildDetailResponse):
    provider_cancelled: bool = False


class CostEstimateResponse(BaseModel):
    provider: str | None = None
    platform: str | None = None
    estimated_cost_usd: float | None = None
    current_monthly_spend_usd: float | None = None


class BuildResponse(BaseModel):
    id: str
    project_id: str
    platform: str
    provider: str
    status: str
    artifact_url: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BuildListResponse(BaseModel):
    items: List[BuildResponse]
    total: int


BUILD_SERVICE_URL = "http://build-service:8006"


def _serialize_build(b: Build) -> dict:
    return {
        "id": b.id,
        "project_id": b.project_id,
        "platform": b.platform,
        "provider": b.provider,
        "status": b.status,
        "artifact_url": b.artifact_url,
        "external_build_id": b.external_build_id,
        "idempotency_key": b.idempotency_key,
        "started_at": b.started_at.isoformat() if b.started_at else None,
        "finished_at": b.finished_at.isoformat() if b.finished_at else None,
        "created_at": b.created_at.isoformat(),
    }


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


@router.get("", response_model=PaginatedBuildResponse)
async def list_builds(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    project_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının build'lerini sayfalanmış olarak listeler.

    Durum ve proje bazında filtreleme destekler. Sonuçlar oluşturulma
    tarihine göre azalan sırada döndürülür. Sadece kullanıcının kendi
    projelerine ait build'ler gösterilir.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    base_q = (
        select(Build)
        .join(Project, Build.project_id == Project.id)
        .where(Project.owner_id == current_user["id"])
    )
    if status_filter:
        base_q = base_q.where(Build.status == status_filter)
    if project_id:
        base_q = base_q.where(Build.project_id == project_id)
    base_q = base_q.order_by(Build.created_at.desc())

    count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * size
    result = await db.execute(base_q.offset(offset).limit(size))
    builds = result.scalars().all()

    return {
        "items": [_serialize_build(b) for b in builds],
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, (total + size - 1) // size),
    }


@router.get("/{build_id}", response_model=BuildDetailResponse)
async def get_build(build_id: str, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Belirtilen build'in detaylarını getirir.

    Build ID ile tekil build kaydını döndürür. Proje sahipliği
    kontrolü yapılır, sadece kendi projelerinin build'lerine erişilebilir.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Build bulunamadı veya erişim yetkisi yok
    """
    result = await db.execute(select(Build).where(Build.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    proj = await db.execute(select(Project).where(Project.id == build.project_id))
    project = proj.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Build not found")
    return _serialize_build(build)


@router.post("/{build_id}/cancel", response_model=CancelBuildResponse)
async def cancel_build(build_id: str, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Devam eden bir build'i iptal eder.

    Build sağlayıcıya (EAS, Codemagic, GitHub Actions) iptal isteği gönderir.
    Sağlayıcı tarafında iptal başarısız olsa bile yerel durum 'cancelled' olarak güncellenir.
    Terminal durumundaki build'ler iptal edilemez.

    Raises:
        400: Build zaten terminal durumda (success/failed/cancelled)
        401: Kimlik doğrulama gerekli
        404: Build bulunamadı veya erişim yetkisi yok
    """
    result = await db.execute(select(Build).where(Build.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    proj = await db.execute(select(Project).where(Project.id == build.project_id))
    project = proj.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Build not found")

    if build.status in ("success", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Build already in terminal state: {build.status}")

    provider_cancelled = False
    if build.external_build_id and build.provider in ("eas", "codemagic", "github_actions"):
        cancel_payload: dict = {
            "external_build_id": build.external_build_id,
            "provider": build.provider,
        }
        if build.provider == "eas":
            token = await _get_credential(db, current_user["id"], "eas", "EAS_TOKEN")
            if token:
                cancel_payload["eas_token"] = token
        elif build.provider == "codemagic":
            token = await _get_credential(db, current_user["id"], "codemagic", "CODEMAGIC_TOKEN")
            if token:
                cancel_payload["codemagic_token"] = token
        elif build.provider == "github_actions":
            token = await _get_credential(db, current_user["id"], "github_actions", "GITHUB_ACTIONS_TOKEN")
            if token:
                cancel_payload["github_token"] = token
            if project.repo_url and "github.com/" in project.repo_url:
                owner_repo = project.repo_url.rstrip("/").rstrip(".git").split("github.com/")[-1]
                cancel_payload["owner_repo"] = owner_repo
                cancel_payload["run_id"] = build.external_build_id

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{BUILD_SERVICE_URL}/cancel", json=cancel_payload)
                provider_cancelled = resp.status_code == 200 and resp.json().get("cancelled", False)
        except Exception:
            pass

    build.status = "cancelled"
    build.finished_at = datetime.utcnow()
    await db.commit()
    data = _serialize_build(build)
    data["provider_cancelled"] = provider_cancelled
    return data


@router.post("/{build_id}/retry", response_model=BuildDetailResponse)
async def retry_build(build_id: str, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Başarısız veya iptal edilmiş bir build'i yeniden başlatır.

    Orijinal build'in platform ve provider ayarlarıyla yeni bir build oluşturur.
    RBAC izin kontrolü yapılır. Sadece failed veya cancelled durumundaki
    build'ler yeniden denenebilir.

    Raises:
        400: Build yeniden denenebilir durumda değil
        401: Kimlik doğrulama gerekli
        403: Build oluşturma yetkisi yok
        404: Build bulunamadı veya erişim yetkisi yok
    """
    result = await db.execute(select(Build).where(Build.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    proj = await db.execute(select(Project).where(Project.id == build.project_id))
    project = proj.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Build not found")

    await require_permission(db, current_user["id"], build.project_id, "builds", "create")

    if build.status not in ("failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Can only retry failed or cancelled builds, current: {build.status}")

    new_build = Build(
        id=str(uuid.uuid4()),
        project_id=build.project_id,
        platform=build.platform,
        provider=build.provider,
        status="queued",
        created_at=datetime.utcnow(),
    )
    db.add(new_build)
    await db.commit()
    await db.refresh(new_build)
    return _serialize_build(new_build)


@router.get("/cost/estimate", response_model=CostEstimateResponse)
async def cost_estimate(
    provider: str = Query("eas"),
    platform: str = Query("android"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Build maliyet tahmini hesaplar.

    Belirtilen sağlayıcı ve platform için tahmini build maliyetini döndürür.
    Kullanıcının aylık toplam harcaması da yanıta eklenir.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    estimate = await estimate_build_cost(provider, platform)
    monthly_spend = await get_monthly_spend(db, current_user["id"])
    estimate["current_monthly_spend_usd"] = round(monthly_spend, 2)
    return estimate
