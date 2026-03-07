import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update, text
from datetime import datetime, timedelta
from app.dependencies import get_current_user
from app.database import get_db
from app.models import (
    User, Project, Build, Deployment, AuditLog, UserQuota,
    UsageRecord, Credential, ImmutableAuditEntry,
)
from app.quotas import PLAN_DEFAULTS

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)

ADMIN_EMAILS = {"admin@apptrack.dev", "admin@apptrack.io"}


async def _require_admin(current_user: dict):
    if current_user.get("email") not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/tenants")
async def list_tenants(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tüm tenant (kullanıcı) listesini sayfalı olarak getirir.

    E-posta ile arama destekler. Her tenant için proje sayısı
    ve plan bilgisi dahil özet bilgileri döndürür.

    Raises:
        401: Kimlik doğrulama gerekli
        403: Admin yetkisi gerekli
    """
    await _require_admin(current_user)

    base_q = select(User)
    if search:
        base_q = base_q.where(User.email.ilike(f"%{search}%"))
    base_q = base_q.order_by(User.created_at.desc())

    count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total = count_result.scalar() or 0
    offset = (page - 1) * size
    result = await db.execute(base_q.offset(offset).limit(size))

    tenants = []
    for user in result.scalars().all():
        proj_count = (await db.execute(
            select(func.count()).where(Project.owner_id == user.id)
        )).scalar() or 0

        quota_result = await db.execute(select(UserQuota).where(UserQuota.user_id == user.id))
        quota = quota_result.scalar_one_or_none()

        tenants.append({
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "plan": quota.plan if quota else "free",
            "project_count": proj_count,
            "created_at": user.created_at.isoformat(),
        })

    return {"items": tenants, "total": total, "page": page, "size": size}


@router.get("/tenants/{user_id}/debug")
async def tenant_debug_view(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tenant için detaylı debug görünümü sağlar.

    Projeler, son build'ler, deployment'lar, denetim kayıtları,
    kota bilgileri ve aylık kullanım istatistiklerini içerir.

    Raises:
        401: Kimlik doğrulama gerekli
        403: Admin yetkisi gerekli
        404: Tenant bulunamadı
    """
    await _require_admin(current_user)

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Tenant not found")

    projects = (await db.execute(
        select(Project).where(Project.owner_id == user_id).order_by(Project.created_at.desc())
    )).scalars().all()

    recent_builds = (await db.execute(
        select(Build).join(Project).where(Project.owner_id == user_id)
        .order_by(Build.created_at.desc()).limit(20)
    )).scalars().all()

    recent_deploys = (await db.execute(
        select(Deployment).join(Build).join(Project).where(Project.owner_id == user_id)
        .order_by(Deployment.created_at.desc()).limit(20)
    )).scalars().all()

    recent_audit = (await db.execute(
        select(AuditLog).where(AuditLog.user_id == user_id)
        .order_by(AuditLog.created_at.desc()).limit(50)
    )).scalars().all()

    quota_result = await db.execute(select(UserQuota).where(UserQuota.user_id == user_id))
    quota = quota_result.scalar_one_or_none()

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage_result = await db.execute(
        select(UsageRecord).where(
            and_(UsageRecord.user_id == user_id, UsageRecord.period_start == month_start)
        )
    )

    cred_count = (await db.execute(
        select(func.count()).where(Credential.owner_id == user_id)
    )).scalar() or 0

    return {
        "tenant": {
            "id": user.id, "name": user.name, "email": user.email,
            "github_connected": bool(user.github_id),
            "created_at": user.created_at.isoformat(),
        },
        "plan": {
            "name": quota.plan if quota else "free",
            "max_projects": quota.max_projects if quota else 3,
            "max_builds": quota.max_builds_per_month if quota else 10,
            "max_deploys": quota.max_deploys_per_month if quota else 5,
        },
        "stats": {
            "projects": len(projects),
            "credentials_configured": cred_count,
            "builds_this_month": sum(1 for b in recent_builds if b.created_at >= month_start),
            "deploys_this_month": sum(1 for d in recent_deploys if d.created_at >= month_start),
            "active_builds": sum(1 for b in recent_builds if b.status in ("queued", "running")),
            "failed_builds": sum(1 for b in recent_builds if b.status == "failed"),
        },
        "projects": [
            {"id": p.id, "name": p.name, "framework": p.framework, "status": p.status}
            for p in projects
        ],
        "recent_builds": [
            {"id": b.id, "project_id": b.project_id, "provider": b.provider,
             "status": b.status, "created_at": b.created_at.isoformat()}
            for b in recent_builds[:10]
        ],
        "recent_deploys": [
            {"id": d.id, "build_id": d.build_id, "target": d.target,
             "status": d.status, "created_at": d.created_at.isoformat()}
            for d in recent_deploys[:10]
        ],
        "recent_audit": [
            {"action": a.action, "resource_type": a.resource_type,
             "resource_id": a.resource_id, "created_at": a.created_at.isoformat()}
            for a in recent_audit[:20]
        ],
        "usage": [
            {"metric_type": u.metric_type, "value": u.value}
            for u in usage_result.scalars().all()
        ],
    }


@router.post("/builds/{build_id}/retry")
async def admin_retry_build(
    build_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Başarısız build'i admin olarak yeniden kuyruğa alır.

    Yalnızca failed, cancelled veya timeout durumundaki build'ler
    için yeni bir build oluşturarak kuyruğa ekler.

    Raises:
        400: Build durumu yeniden denemeye uygun değil
        401: Kimlik doğrulama gerekli
        403: Admin yetkisi gerekli
        404: Build bulunamadı
    """
    await _require_admin(current_user)

    result = await db.execute(select(Build).where(Build.id == build_id))
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    if build.status not in ("failed", "cancelled", "timeout"):
        raise HTTPException(status_code=400, detail=f"Cannot retry build in {build.status} state")

    import uuid
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
    logger.info("Admin retry: build %s -> new build %s by %s", build_id, new_build.id, current_user["email"])
    return {"original_build_id": build_id, "new_build_id": new_build.id, "status": "queued"}


@router.post("/tenants/{user_id}/change-plan")
async def admin_change_plan(
    user_id: str,
    plan: str = Query(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tenant'ın abonelik planını admin olarak değiştirir.

    Kullanıcının kotasını seçilen plana göre günceller.
    Mevcut kota yoksa yeni kota kaydı oluşturur.

    Raises:
        400: Geçersiz plan adı
        401: Kimlik doğrulama gerekli
        403: Admin yetkisi gerekli
    """
    await _require_admin(current_user)

    if plan not in PLAN_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan}. Must be one of: {list(PLAN_DEFAULTS.keys())}")

    quota_result = await db.execute(select(UserQuota).where(UserQuota.user_id == user_id))
    quota = quota_result.scalar_one_or_none()

    defaults = PLAN_DEFAULTS[plan]
    if quota:
        quota.plan = plan
        for k, v in defaults.items():
            setattr(quota, k, v)
        quota.updated_at = datetime.utcnow()
    else:
        quota = UserQuota(user_id=user_id, plan=plan, **defaults)
        db.add(quota)

    await db.commit()
    logger.info("Admin plan change: user %s -> %s by %s", user_id, plan, current_user["email"])
    return {"user_id": user_id, "plan": plan, "quotas": defaults}


@router.post("/tenants/{user_id}/suspend")
async def admin_suspend_tenant(
    user_id: str,
    reason: str = Query("admin_action"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tenant hesabını askıya alır.

    Kullanıcının çalışan ve kuyruktaki tüm build'lerini iptal eder.
    Askıya alma nedeni kayıt altına alınır.

    Raises:
        401: Kimlik doğrulama gerekli
        403: Admin yetkisi gerekli
    """
    await _require_admin(current_user)

    await db.execute(
        update(Build).where(
            and_(
                Build.project_id.in_(select(Project.id).where(Project.owner_id == user_id)),
                Build.status.in_(["queued", "running"]),
            )
        ).values(status="cancelled", finished_at=datetime.utcnow())
    )
    await db.commit()

    logger.warning("Admin suspended tenant %s reason=%s by %s", user_id, reason, current_user["email"])
    return {"user_id": user_id, "action": "suspended", "reason": reason}


@router.get("/overview")
async def admin_overview(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Platform genelinde admin özet panelini döndürür.

    Toplam kullanıcı, proje, günlük/aylık build ve deployment
    sayıları ile aktif ve başarısız build istatistiklerini içerir.

    Raises:
        401: Kimlik doğrulama gerekli
        403: Admin yetkisi gerekli
    """
    await _require_admin(current_user)

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    day_ago = now - timedelta(days=1)
    hour_ago = now - timedelta(hours=1)

    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    total_projects = (await db.execute(select(func.count()).select_from(Project))).scalar() or 0

    builds_today = (await db.execute(
        select(func.count()).where(Build.created_at >= day_ago)
    )).scalar() or 0
    builds_month = (await db.execute(
        select(func.count()).where(Build.created_at >= month_start)
    )).scalar() or 0
    active_builds = (await db.execute(
        select(func.count()).where(Build.status.in_(["queued", "running"]))
    )).scalar() or 0
    failed_builds_today = (await db.execute(
        select(func.count()).where(and_(Build.status == "failed", Build.created_at >= day_ago))
    )).scalar() or 0

    deploys_today = (await db.execute(
        select(func.count()).where(Deployment.created_at >= day_ago)
    )).scalar() or 0
    deploys_month = (await db.execute(
        select(func.count()).where(Deployment.created_at >= month_start)
    )).scalar() or 0

    return {
        "timestamp": now.isoformat(),
        "users": {"total": total_users},
        "projects": {"total": total_projects},
        "builds": {
            "today": builds_today,
            "this_month": builds_month,
            "active": active_builds,
            "failed_today": failed_builds_today,
        },
        "deploys": {"today": deploys_today, "this_month": deploys_month},
    }


@router.get("/audit-export")
async def export_audit_logs(
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Denetim günlüklerini dışa aktarır.

    Kullanıcı ve aksiyon bazında filtreleme ile belirtilen gün aralığındaki
    en fazla 1000 denetim kaydını döndürür.

    Raises:
        401: Kimlik doğrulama gerekli
        403: Admin yetkisi gerekli
    """
    await _require_admin(current_user)

    since = datetime.utcnow() - timedelta(days=days)
    base_q = select(AuditLog).where(AuditLog.created_at >= since)
    if user_id:
        base_q = base_q.where(AuditLog.user_id == user_id)
    if action:
        base_q = base_q.where(AuditLog.action == action)
    base_q = base_q.order_by(AuditLog.created_at.desc()).limit(1000)

    result = await db.execute(base_q)
    return [
        {
            "id": a.id, "user_id": a.user_id, "action": a.action,
            "resource_type": a.resource_type, "resource_id": a.resource_id,
            "details": a.details, "ip_address": a.ip_address,
            "trace_id": a.trace_id, "created_at": a.created_at.isoformat(),
        }
        for a in result.scalars().all()
    ]
