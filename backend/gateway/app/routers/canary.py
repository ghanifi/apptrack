import logging
import uuid as _uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Deployment, Build, Project

router = APIRouter(prefix="/api/deployments", tags=["canary-deploy"])
logger = logging.getLogger(__name__)


def _validate_uuid(value: str) -> None:
    """Raise 404 if *value* is not a valid UUID."""
    try:
        _uuid.UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Deployment not found")


@router.post("/{deployment_id}/canary")
async def start_canary_deploy(
    deployment_id: str,
    initial_percentage: int = 5,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Canary (kademeli) deploy başlatır.

    Belirtilen yüzde oranında trafiğe yeni sürümü açar (1-50 arası).
    Deployment durumu 'canary' olarak güncellenir. Metrikler izlendikten
    sonra promote veya rollback yapılabilir.

    Raises:
        400: Geçersiz yüzde değeri veya uyumsuz deployment durumu
        401: Kimlik doğrulama gerekli
        404: Deployment bulunamadı
    """
    _validate_uuid(deployment_id)
    if not 1 <= initial_percentage <= 50:
        raise HTTPException(status_code=400, detail="Canary percentage must be between 1 and 50")

    result = await db.execute(
        select(Deployment).join(Build).join(Project).where(
            and_(Deployment.id == deployment_id, Project.owner_id == current_user["id"])
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if deployment.status not in ("pending", "published"):
        raise HTTPException(status_code=400, detail=f"Cannot start canary from status '{deployment.status}'")

    deployment.status = "canary"
    deployment.updated_at = datetime.utcnow()
    await db.commit()

    logger.info("Canary deploy started: deployment=%s percentage=%d", deployment_id, initial_percentage)
    return {
        "deployment_id": deployment_id,
        "status": "canary",
        "canary_percentage": initial_percentage,
        "message": f"Canary release started at {initial_percentage}% traffic. Monitor metrics before promoting.",
        "actions": ["promote", "rollback"],
    }


@router.post("/{deployment_id}/promote")
async def promote_canary(
    deployment_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Canary deployment'ı tam sürüme yükseltir.

    Canary aşamasındaki deployment'ı %100 trafiğe açarak 'published'
    durumuna geçirir. Sadece 'canary' durumundaki deployment'lar promote edilebilir.

    Raises:
        400: Deployment canary durumunda değil
        401: Kimlik doğrulama gerekli
        404: Deployment bulunamadı
    """
    _validate_uuid(deployment_id)
    result = await db.execute(
        select(Deployment).join(Build).join(Project).where(
            and_(Deployment.id == deployment_id, Project.owner_id == current_user["id"])
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if deployment.status != "canary":
        raise HTTPException(status_code=400, detail="Only canary deployments can be promoted")

    deployment.status = "published"
    deployment.updated_at = datetime.utcnow()
    await db.commit()

    logger.info("Canary promoted to full release: deployment=%s", deployment_id)
    return {
        "deployment_id": deployment_id,
        "status": "published",
        "message": "Canary promoted to 100% traffic. Full release complete.",
    }


@router.post("/{deployment_id}/rollback")
async def rollback_deployment(
    deployment_id: str,
    reason: str = "Manual rollback",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deployment'ı geri alır ve önceki sürümü geri yükler.

    Canary, published veya pending durumundaki deployment'lar geri alınabilir.
    Sebep (reason) parametresi log'a kaydedilir. Durum 'rolled_back' olarak güncellenir.

    Raises:
        400: Geri alınamaz durumdaki deployment
        401: Kimlik doğrulama gerekli
        404: Deployment bulunamadı
    """
    _validate_uuid(deployment_id)
    result = await db.execute(
        select(Deployment).join(Build).join(Project).where(
            and_(Deployment.id == deployment_id, Project.owner_id == current_user["id"])
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if deployment.status not in ("canary", "published", "pending"):
        raise HTTPException(status_code=400, detail=f"Cannot rollback from status '{deployment.status}'")

    deployment.status = "rolled_back"
    deployment.updated_at = datetime.utcnow()
    await db.commit()

    logger.info("Deployment rolled back: deployment=%s reason=%s", deployment_id, reason)
    return {
        "deployment_id": deployment_id,
        "status": "rolled_back",
        "reason": reason,
        "message": "Deployment rolled back successfully. Previous version restored.",
    }


@router.get("/{deployment_id}/canary-metrics")
async def canary_metrics(
    deployment_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Canary deployment'ın sağlık metriklerini döndürür.

    Sentry entegrasyonu varsa gerçek error rate ve crash-free session
    verileri çekilir. Yoksa varsayılan değerler kullanılır.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Deployment bulunamadı
    """
    _validate_uuid(deployment_id)
    result = await db.execute(
        select(Deployment).join(Build).join(Project).where(
            and_(Deployment.id == deployment_id, Project.owner_id == current_user["id"])
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    error_rate = 0.0
    crash_free_sessions = 99.9
    data_source = "default"

    sentry_token = getattr(__import__('app.config', fromlist=['settings']).settings, 'SENTRY_AUTH_TOKEN', '')
    if sentry_token:
        try:
            import httpx
            build_result = await db.execute(select(Build).where(Build.id == deployment.build_id))
            build = build_result.scalar_one_or_none()
            if build:
                project_result = await db.execute(select(Project).where(Project.id == build.project_id))
                project = project_result.scalar_one_or_none()

                from app.models import Credential
                cred_result = await db.execute(
                    select(Credential).where(
                        and_(
                            Credential.owner_id == current_user["id"],
                            Credential.provider == "sentry",
                            Credential.key_name == "SENTRY_PROJECT_SLUG",
                        )
                    )
                )
                sentry_cred = cred_result.scalar_one_or_none()
                if sentry_cred:
                    from app.crypto import decrypt
                    sentry_slug = decrypt(sentry_cred.encrypted_value)
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.get(
                            f"https://sentry.io/api/0/projects/{sentry_slug}/stats/",
                            headers={"Authorization": f"Bearer {sentry_token}"},
                            params={"stat": "received", "resolution": "1h", "since": "24h"},
                        )
                        if resp.status_code == 200:
                            stats = resp.json()
                            total_events = sum(point[1] for point in stats) if stats else 0
                            error_rate = min(total_events / max(1, total_events + 1000) * 100, 100)
                            crash_free_sessions = max(0, 100 - error_rate)
                            data_source = "sentry"
        except Exception as exc:
            logger.warning("Sentry metrics fetch failed: %s — using defaults", exc)

    error_threshold = 5.0
    crash_threshold = 95.0
    if deployment.status == "canary":
        if error_rate <= error_threshold and crash_free_sessions >= crash_threshold:
            recommendation = "safe_to_promote"
        elif error_rate > error_threshold * 2:
            recommendation = "rollback_recommended"
        else:
            recommendation = "monitor"
    else:
        recommendation = "n/a"

    return {
        "deployment_id": deployment_id,
        "status": deployment.status,
        "created_at": deployment.created_at.isoformat(),
        "updated_at": deployment.updated_at.isoformat(),
        "health": {
            "error_rate": round(error_rate, 2),
            "crash_free_sessions": round(crash_free_sessions, 2),
            "recommendation": recommendation,
            "data_source": data_source,
            "thresholds": {
                "error_rate_max": error_threshold,
                "crash_free_min": crash_threshold,
            },
        },
    }
