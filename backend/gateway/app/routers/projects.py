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
from sqlalchemy.orm import selectinload
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
from app.quotas import check_project_quota, check_build_quota, check_deploy_quota, track_usage
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
                    "events": ["push", "pull_request"],
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


async def _fetch_repo_visibility(repo_url: str, token: str | None) -> str:
    """GitHub API'den repo visibility bilgisini ceker. Default: private."""
    match = re.match(r'https://github\.com/([^/]+)/([^/\.]+)', repo_url)
    if not match:
        return "private"
    owner, repo = match.groups()
    headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
            if resp.status_code == 200:
                return "public" if not resp.json().get("private", True) else "private"
    except Exception as exc:
        logger.warning("_fetch_repo_visibility error: %s", exc)
    return "private"


class ProjectCreate(BaseModel):
    name: str
    repo_url: str
    branch: str = "main"


class ProjectUpdate(BaseModel):
    name: str | None = None
    branch: str | None = None
    runner_type: str | None = None
    runner_labels: str | None = None


class BuildResponse(BaseModel):
    id: str
    platform: str
    provider: str
    status: str
    artifact_url: str | None = None
    log_output: str | None = None
    created_at: str
    # Build geçmişi rozetleri/metadata (imza, commit, süre, tetikleyici) — response_model
    # bu alanları tanımlamazsa frontend'e hiç ulaşmaz.
    artifact_signature: dict | None = None
    commit_sha: str | None = None
    trigger_type: str | None = None
    pr_number: int | None = None
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: str
    name: str
    repo_url: str
    branch: str
    framework: Optional[str] = None
    status: str
    created_at: datetime | str
    updated_at: datetime | str
    owner_id: str
    runner_type: str = "hosted"
    runner_labels: Optional[str] = None
    builds: List[BuildResponse] = []

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    items: List[ProjectResponse]
    total: int


class PaginatedProjectResponse(BaseModel):
    items: List[ProjectResponse]
    total: int
    page: int
    size: int
    pages: int


class SyncResponse(BaseModel):
    status: str
    project_id: str


class TriggerBuildResponse(BaseModel):
    build_id: str
    status: str
    provider: str
    platform: str
    cost_estimate: dict


class DeploymentResponse(BaseModel):
    id: str
    build_id: str
    target: str
    track: str
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


def _serialize_project(p: Project) -> dict:
    try:
        builds = list(p.builds)
    except Exception:
        builds = []
    # Tip-güvenli okuma: ORM'de her zaman str/None, ama savunmacı.
    _rt = getattr(p, "runner_type", None)
    runner_type = _rt if isinstance(_rt, str) else "hosted"
    _rl = getattr(p, "runner_labels", None)
    runner_labels = _rl if isinstance(_rl, str) else None
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
        "repo_visibility": getattr(p, "repo_visibility", "private"),
        "runner_type": runner_type,
        "runner_labels": runner_labels,
        "builds": [
            {
                "id": b.id,
                "platform": b.platform,
                "provider": b.provider,
                "status": b.status,
                "artifact_url": b.artifact_url,
                "log_output": b.log_output,
                "created_at": b.created_at.isoformat(),
                # Frontend build geçmişi bu alanları gösterir (imza rozeti, commit, süre,
                # PR/manual etiketi) — serializer'da eksikti, bu yüzden hepsi görünmüyordu.
                "artifact_signature": (
                    _sig if isinstance((_sig := getattr(b, "artifact_signature", None)), dict) else None
                ),
                "commit_sha": getattr(b, "commit_sha", None),
                "trigger_type": getattr(b, "trigger_type", None),
                "pr_number": getattr(b, "pr_number", None),
                "error_message": getattr(b, "error_message", None),
                "started_at": (
                    b.started_at.isoformat() if getattr(b, "started_at", None) else None
                ),
                "finished_at": (
                    b.finished_at.isoformat() if getattr(b, "finished_at", None) else None
                ),
            }
            for b in builds
        ],
    }


@router.get("", response_model=PaginatedProjectResponse)
async def list_projects(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının projelerini sayfalanmış olarak listeler.

    Duruma göre filtreleme destekler. Sonuçlar oluşturulma tarihine göre
    azalan sırada döndürülür. Her proje ile birlikte build bilgileri dahildir.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    base_q = select(Project).where(Project.owner_id == current_user["id"])
    if status_filter:
        base_q = base_q.where(Project.status == status_filter)
    base_q = base_q.order_by(Project.created_at.desc())

    count_result = await db.execute(
        select(func.count()).select_from(base_q.subquery())
    )
    total = count_result.scalar() or 0

    offset = (page - 1) * size
    result = await db.execute(base_q.options(selectinload(Project.builds)).offset(offset).limit(size))
    projects = result.scalars().all()
    return {
        "items": [_serialize_project(p) for p in projects],
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, (total + size - 1) // size),
    }


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
async def create_project(
    req: ProjectCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yeni bir proje oluşturur.

    Repo URL ve branch doğrulanır, proje kotası kontrol edilir.
    Proje oluşturulduktan sonra analiz event'i yayınlanır ve
    GitHub webhook otomatik olarak kaydedilir.

    Raises:
        400: Geçersiz repo URL veya branch formatı
        401: Kimlik doğrulama gerekli
        403: Proje kotası aşıldı
    """
    repo_url = validate_repo_url(req.repo_url)
    branch = validate_branch(req.branch)

    await check_project_quota(db, current_user["id"])

    # Fetch GitHub token early — needed for visibility check and webhook
    user_result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = user_result.scalar_one_or_none()
    github_token_encrypted = user.github_access_token if user else None
    github_token_plain = None
    if github_token_encrypted:
        try:
            github_token_plain = decrypt(github_token_encrypted)
        except Exception:
            github_token_plain = github_token_encrypted

    repo_visibility = await _fetch_repo_visibility(repo_url, github_token_plain)

    project = Project(
        name=req.name.strip(),
        repo_url=repo_url,
        branch=branch,
        owner_id=current_user["id"],
        repo_visibility=repo_visibility,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    await record_audit_with_db(
        db, action="project.created", resource_type="project",
        resource_id=project.id, user_id=current_user["id"],
        details={"name": project.name, "repo_url": project.repo_url, "repo_visibility": repo_visibility},
        request=request,
    )
    await db.commit()

    await events.publish_event(
        "project.created",
        {
            "project_id": project.id,
            "repo_url": project.repo_url,
            "branch": project.branch,
            "owner_id": project.owner_id,
            "github_token": github_token_encrypted,
            "repo_visibility": project.repo_visibility,
            "trace_id": getattr(req, "trace_id", None),
        },
    )

    if user and github_token_plain and settings.GITHUB_WEBHOOK_SECRET:
        await _register_github_webhook(project, github_token_plain)

    return _serialize_project(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Belirtilen projenin detaylarını getirir.

    Proje bilgileri ve ilişkili build'ler dahil tam detay döndürür.
    Sadece proje sahibi erişebilir.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
    """
    result = await db.execute(
        select(Project).options(selectinload(Project.builds)).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    return _serialize_project(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    req: ProjectUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Projenin adını veya branch bilgisini günceller.

    Kısmi güncelleme destekler (PATCH). Sadece gönderilen alanlar güncellenir.
    Proje sahibi dışında kimse güncelleyemez.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
    """
    result = await db.execute(
        select(Project).options(selectinload(Project.builds)).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    if req.name:
        project.name = req.name
    if req.branch:
        project.branch = req.branch
    if req.runner_type is not None:
        if req.runner_type not in ("hosted", "self_hosted"):
            raise HTTPException(status_code=422, detail="runner_type must be 'hosted' or 'self_hosted'")
        project.runner_type = req.runner_type
    if req.runner_labels is not None:
        # Boş string -> None (varsayılan label seti kullanılsın)
        project.runner_labels = req.runner_labels.strip() or None
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
    """Belirtilen projeyi kalıcı olarak siler.

    Proje ve ilişkili tüm veriler veritabanından kaldırılır.
    Bu işlem geri alınamaz. Sadece proje sahibi silebilir.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()


@router.post("/{project_id}/sync", response_model=SyncResponse)
async def sync_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Proje repo'sunu yeniden analiz etmek için senkronizasyon başlatır.

    Proje durumunu 'analyzing' olarak günceller ve analiz event'i yayınlar.
    Framework tespiti ve repo yapısı yeniden değerlendirilir.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    project.status = "analyzing"
    project.updated_at = datetime.utcnow()
    await db.commit()

    # Get GitHub token (encrypted) for private repo access
    user_result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = user_result.scalar_one_or_none()
    github_token_encrypted = user.github_access_token if user else None

    await events.publish_event(
        "project.created",
        {
            "project_id": project.id,
            "repo_url": project.repo_url,
            "branch": project.branch,
            "owner_id": project.owner_id,
            "github_token": github_token_encrypted,
        },
    )
    return {"status": "sync_triggered", "project_id": project_id}


@router.post("/{project_id}/build", response_model=TriggerBuildResponse)
@limiter.limit("10/hour")
async def trigger_build(
    request: Request,
    project_id: str,
    platform: str = "both",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Proje için yeni bir build işlemi başlatır.

    Framework'e göre uygun build sağlayıcı seçilir (EAS, Codemagic, GitHub Actions).
    Build kotası, spam koruması, bütçe limiti ve idempotency kontrolü yapılır.
    Maliyet tahmini hesaplanır ve build event'i yayınlanır.

    Raises:
        400: Framework henüz tespit edilmedi
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
        409: Aynı proje/platform için aktif build zaten mevcut
        429: Build spam koruması veya rate limit aşıldı
    """
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
        "capacitor": "github_actions",
        "ionic": "github_actions",
        "cordova": "github_actions",
        "pwa": "github_actions",
    }
    provider = project.build_provider or provider_map.get(project.framework, "github_actions")

    # Auto-fallback to github_actions if user has no credential for the preferred provider
    if provider == "codemagic" and not await get_user_credential(db, current_user["id"], "codemagic", "CODEMAGIC_TOKEN"):
        provider = "github_actions"
    elif provider == "eas" and not await get_user_credential(db, current_user["id"], "eas", "EAS_TOKEN"):
        provider = "github_actions"

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

    event_payload: dict = {
        "build_id": build.id,
        "project_id": project.id,
        "owner_id": project.owner_id,
        "framework": project.framework,
        "platform": platform,
        "provider": provider,
        "repo_url": project.repo_url,
        "branch": project.branch,
        "clone_path": project.clone_path,
        "repo_visibility": project.repo_visibility or "private",
        "runner_type": getattr(project, "runner_type", "hosted") or "hosted",
        "runner_labels": getattr(project, "runner_labels", None),
    }

    if provider == "eas":
        event_payload["eas_token"] = await get_user_credential(db, current_user["id"], "eas", "EAS_TOKEN")
        event_payload["expo_app_id"] = await get_user_credential(db, current_user["id"], "eas", "EXPO_APP_ID")
    elif provider == "codemagic":
        event_payload["codemagic_token"] = await get_user_credential(db, current_user["id"], "codemagic", "CODEMAGIC_TOKEN")
        event_payload["codemagic_app_id"] = await get_user_credential(db, current_user["id"], "codemagic", "CODEMAGIC_APP_ID")
    elif provider == "github_actions":
        github_token = await get_user_credential(db, current_user["id"], "github_actions", "GITHUB_ACTIONS_TOKEN")
        if not github_token:
            user_result = await db.execute(select(User).where(User.id == current_user["id"]))
            user_obj = user_result.scalar_one_or_none()
            if user_obj and user_obj.github_access_token:
                try:
                    github_token = decrypt(user_obj.github_access_token)
                except Exception:
                    pass
        event_payload["github_token"] = github_token
        # iOS signing credentials
        event_payload["ios_cert_p12_base64"] = await get_user_credential(db, current_user["id"], "ios_signing", "IOS_CERT_P12_BASE64")
        event_payload["ios_cert_password"] = await get_user_credential(db, current_user["id"], "ios_signing", "IOS_CERT_PASSWORD")
        event_payload["ios_provisioning_profile_base64"] = await get_user_credential(db, current_user["id"], "ios_signing", "IOS_PROVISIONING_PROFILE_BASE64")
        # Android signing credentials
        event_payload["android_keystore_base64"] = await get_user_credential(db, current_user["id"], "android_signing", "ANDROID_KEYSTORE_BASE64")
        event_payload["android_keystore_password"] = await get_user_credential(db, current_user["id"], "android_signing", "ANDROID_KEYSTORE_PASSWORD")
        event_payload["android_key_alias"] = await get_user_credential(db, current_user["id"], "android_signing", "ANDROID_KEY_ALIAS")
        event_payload["android_key_password"] = await get_user_credential(db, current_user["id"], "android_signing", "ANDROID_KEY_PASSWORD")
        # App Store Connect API credentials (TestFlight upload)
        event_payload["appstore_api_key_id"] = await get_user_credential(db, current_user["id"], "appstore_connect", "APPSTORE_API_KEY_ID")
        event_payload["appstore_api_issuer_id"] = await get_user_credential(db, current_user["id"], "appstore_connect", "APPSTORE_API_ISSUER_ID")
        event_payload["appstore_api_key_base64"] = await get_user_credential(db, current_user["id"], "appstore_connect", "APPSTORE_API_KEY_BASE64")

    await events.publish_event("build.triggered", event_payload)

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
    deploy_url: str = ""


@router.get("/{project_id}/deployments", response_model=List[DeploymentResponse])
async def list_project_deployments(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Projeye ait tüm deployment'ları listeler.

    İlişkili build'ler üzerinden projenin deployment geçmişini döndürür.
    Sonuçlar oluşturulma tarihine göre azalan sırada sıralanır.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
    """
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


@router.post("/{project_id}/deploy", response_model=DeploymentResponse)
@limiter.limit("10/hour")
async def deploy_project(
    request: Request,
    project_id: str,
    req: DeployRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Projenin en son başarılı build'ini mağazaya deploy eder.

    Google Play veya App Store hedefine deploy başlatır.
    Başarılı bir build gereklidir. Hedef mağazaya göre gerekli
    credential'lar otomatik olarak event payload'a eklenir.

    Raises:
        400: Başarılı build bulunamadı
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
        429: Rate limit aşıldı
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    await check_deploy_quota(db, current_user["id"])

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

    await track_usage(db, current_user["id"], "deploys", 1, {"target": req.target, "track": req.track})
    await db.commit()

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
    elif req.target == "web":
        event_payload["deploy_url"] = req.deploy_url
        event_payload["netlify_token"] = await get_user_credential(
            db, current_user["id"], "netlify", "NETLIFY_TOKEN"
        )

    await events.publish_event("deploy.triggered", event_payload)
    return _serialize_dep(dep)


@router.get("/{project_id}/compliance-checklist")
async def get_compliance_checklist(
    project_id: str,
    platform: str = "both",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """2026 App Store / Play Store uyumluluk kontrol listesi.

    Projenin yayınlanmaya hazır olup olmadığını kontrol eder.
    Her madde pass/fail/warning durumundadır.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    checks: list[dict] = []

    # --- iOS Checks ---
    if platform in ("ios", "both"):
        # iOS signing credentials
        ios_cert = await get_user_credential(db, current_user["id"], "ios_signing", "IOS_CERT_P12_BASE64")
        ios_profile = await get_user_credential(db, current_user["id"], "ios_signing", "IOS_PROVISIONING_PROFILE_BASE64")
        checks.append({
            "id": "ios_signing",
            "platform": "ios",
            "category": "signing",
            "title": "iOS Distribution Certificate & Provisioning Profile",
            "status": "pass" if (ios_cert and ios_profile) else "fail",
            "message": "Signing credentials configured" if (ios_cert and ios_profile) else "Missing iOS signing credentials — use Auto-Generate in Settings (no Mac needed)",
            "fix_url": "/dashboard/settings",
        })

        # App Store Connect API
        asc_key = await get_user_credential(db, current_user["id"], "appstore_connect", "APPSTORE_API_KEY_ID")
        checks.append({
            "id": "appstore_connect",
            "platform": "ios",
            "category": "publishing",
            "title": "App Store Connect API Key",
            "status": "pass" if asc_key else "warning",
            "message": "API key configured — auto-upload enabled" if asc_key else "No API key — manual upload required after build",
            "fix_url": "/dashboard/settings",
        })

        # PrivacyInfo.xcprivacy (auto-generated in workflow)
        checks.append({
            "id": "privacy_manifest",
            "platform": "ios",
            "category": "compliance",
            "title": "PrivacyInfo.xcprivacy (Apple 2026 mandatory)",
            "status": "pass",
            "message": "Auto-generated during build if not present in project",
        })

        # Bitcode disabled
        checks.append({
            "id": "bitcode_disabled",
            "platform": "ios",
            "category": "build_config",
            "title": "ENABLE_BITCODE=NO",
            "status": "pass",
            "message": "Enforced in build workflow",
        })

        # Xcode 26 SDK (ASC, 28 Nisan 2026'dan beri zorunlu)
        checks.append({
            "id": "xcode_26_sdk",
            "platform": "ios",
            "category": "compliance",
            "title": "Built with Xcode 26 / iOS 26 SDK (ASC requirement since 28 Apr 2026)",
            "status": "pass",
            "message": "Build workflow pinned to macos-26 runner (Xcode 26)",
        })

        # Yaş derecelendirme (ASC, 31 Ocak 2026'dan beri güncel yanıtlar zorunlu)
        checks.append({
            "id": "age_rating_2026",
            "platform": "ios",
            "category": "metadata",
            "title": "Updated Age Rating Questionnaire (ASC, since 31 Jan 2026)",
            "status": "warning",
            "message": "Answer the updated age rating questions in App Store Connect — submissions are blocked until completed",
            "help_url": "https://developer.apple.com/news/upcoming-requirements/",
        })

    # --- Android Checks ---
    if platform in ("android", "both"):
        # Android signing
        keystore = await get_user_credential(db, current_user["id"], "android_signing", "ANDROID_KEYSTORE_BASE64")
        checks.append({
            "id": "android_signing",
            "platform": "android",
            "category": "signing",
            "title": "Android Signing Keystore (Play App Signing)",
            "status": "pass" if keystore else "fail",
            "message": "Keystore configured" if keystore else "Missing Android signing keystore — required for Play Store AAB upload",
            "fix_url": "/dashboard/settings",
        })

        # AAB format
        checks.append({
            "id": "aab_format",
            "platform": "android",
            "category": "build_config",
            "title": "AAB Format (Play Store 2026 mandatory)",
            "status": "pass",
            "message": "Release builds produce AAB (not APK) automatically",
        })

        # targetSdkVersion
        checks.append({
            "id": "target_sdk_version",
            "platform": "android",
            "category": "compliance",
            "title": "targetSdkVersion >= 36 (Google Play, from 31 Aug 2026)",
            "status": "pass",
            "message": "Auto-checked and fixed during build if below 36",
        })

        # Data Safety — AppTrack'te beyan kaydedildiyse hazır say (Play Console'a manuel girilir)
        from app.models import StoreMetadata as _SM
        _ds_row = (await db.execute(
            select(_SM).where(_SM.project_id == project_id, _SM.data_safety.isnot(None))
        )).scalars().first()
        checks.append({
            "id": "data_safety",
            "platform": "android",
            "category": "metadata",
            "title": "Data Safety Section",
            "status": "passed" if _ds_row else "warning",
            "message": ("Declared in AppTrack store metadata — remember to mirror it in Play Console (API cannot set it)"
                        if _ds_row else
                        "Must be manually configured in Google Play Console — declare it in AppTrack Store Config to track readiness"),
            "help_url": "https://support.google.com/googleplay/android-developer/answer/10787469",
        })

        # Google Checks
        google_checks_configured = bool(await get_user_credential(db, current_user["id"], "google_play", "GOOGLE_PLAY_KEY_JSON"))
        checks.append({
            "id": "google_checks",
            "platform": "android",
            "category": "compliance",
            "title": "Google Checks Compliance Scan",
            "status": "pass" if google_checks_configured else "warning",
            "message": "Enabled in build workflow" if google_checks_configured else "Optional — add Google Checks account ID for automated compliance scanning",
        })

    # --- Cross-Platform Checks ---
    checks.append({
        "id": "privacy_policy",
        "platform": "both",
        "category": "metadata",
        "title": "Privacy Policy URL",
        "status": "warning",
        "message": "Ensure privacy policy URL is set in store listing — required by both Apple and Google",
    })

    # AB DSA trader status (Şubat 2025'ten beri doğrulanmamış app'ler AB'de kaldırılıyor)
    checks.append({
        "id": "eu_trader_status",
        "platform": "both",
        "category": "compliance",
        "title": "EU DSA Trader Status Verified",
        "status": "warning",
        "message": "If distributing in the EU, verify trader status in App Store Connect and Play Console — unverified apps are removed from EU storefronts",
        "help_url": "https://developer.apple.com/help/app-store-connect/manage-compliance-information/manage-european-union-digital-services-act-trader-requirements/",
    })

    total = len(checks)
    passed = sum(1 for c in checks if c["status"] == "pass")
    warnings = sum(1 for c in checks if c["status"] == "warning")
    failed = sum(1 for c in checks if c["status"] == "fail")
    ready = failed == 0

    return {
        "project_id": project_id,
        "framework": project.framework,
        "platform": platform,
        "ready_to_publish": ready,
        "summary": {"total": total, "passed": passed, "warnings": warnings, "failed": failed},
        "checks": checks,
    }
