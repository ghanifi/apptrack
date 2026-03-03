import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.config import settings
from app.database import get_db
from app.models import Project, WebhookNonce
from app.limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/github")
@limiter.limit("30/minute")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(...),
    x_hub_signature_256: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    """GitHub push webhook'unu alır ve ilgili projeleri otomatik senkronize eder.

    HMAC-SHA256 imza doğrulaması yapılır. Push event'lerinde eşleşen
    repo URL ve branch'e sahip projeler için otomatik analiz tetiklenir.
    Ping event'lerine pong yanıtı verilir.

    Raises:
        401: Webhook imzası eksik veya geçersiz
        503: Webhook secret yapılandırılmamış
    """
    body = await request.body()

    if settings.GITHUB_WEBHOOK_SECRET:
        if not x_hub_signature_256:
            raise HTTPException(status_code=401, detail="Missing webhook signature")
        if not _verify_signature(body, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    else:
        raise HTTPException(
            status_code=503,
            detail="Webhook signature verification disabled — GITHUB_WEBHOOK_SECRET not configured",
        )

    if x_github_event == "ping":
        return {"status": "pong"}

    if x_github_event != "push":
        return {"status": "ignored", "event": x_github_event}

    payload = json.loads(body)
    repo_url = payload.get("repository", {}).get("clone_url", "")
    ref = payload.get("ref", "")
    branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ""

    if not repo_url or not branch:
        return {"status": "skipped", "reason": "no repo_url or branch"}

    result = await db.execute(
        select(Project).where(Project.repo_url == repo_url, Project.branch == branch)
    )
    projects = result.scalars().all()

    triggered = 0
    for project in projects:
        await events.publish_event("project.created", {
            "project_id": project.id,
            "repo_url": project.repo_url,
            "branch": project.branch,
            "owner_id": project.owner_id,
            "triggered_by": "github_webhook",
        })
        triggered += 1
        logger.info("Auto-sync triggered for project %s via GitHub push", project.id)

    return {"status": "ok", "triggered": triggered, "repo": repo_url, "branch": branch}


@router.post("/eas")
@limiter.limit("60/minute")
async def eas_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """EAS (Expo Application Services) build webhook'unu işler.

    İmza doğrulaması ve nonce replay koruması uygulanır.
    Build durumu (finished/errored/canceled) iç duruma eşlenir ve
    build.finished event'i yayınlanır.

    Raises:
        400: Geçersiz imza veya JSON payload
    """
    body = await request.body()
    signature = request.headers.get("x-eas-webhook-signature", "")
    secret = settings.EAS_WEBHOOK_SECRET

    if secret and not _verify_signature(body, signature, secret):
        raise HTTPException(status_code=400, detail="EAS webhook imzası geçersiz")

    delivery_id = request.headers.get("x-eas-delivery-id", "")
    if delivery_id:
        # Nonce replay koruması
        existing = await db.execute(
            select(WebhookNonce).where(WebhookNonce.nonce_value == delivery_id)
        )
        if existing.scalar_one_or_none():
            return {"status": "duplicate", "delivery_id": delivery_id}
        nonce = WebhookNonce(
            source="eas",
            nonce_value=delivery_id,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.add(nonce)
        await db.commit()

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz JSON payload")

    # EAS status mapping
    eas_status = payload.get("status", "")
    build_id = payload.get("metadata", {}).get("buildId") or payload.get("id", "")

    status_map = {
        "finished": "success",
        "errored": "failed",
        "canceled": "failed",
    }
    mapped_status = status_map.get(eas_status)
    if not mapped_status or not build_id:
        return {"status": "ignored", "eas_status": eas_status}

    artifacts = payload.get("artifacts", {})
    artifact_url = artifacts.get("buildUrl") or artifacts.get("url") or ""

    await events.publish_event("build.finished", {
        "build_id": build_id,
        "status": mapped_status,
        "artifact_url": artifact_url,
        "provider": "eas",
        "source": "eas_webhook",
    })

    logger.info("EAS webhook processed: build_id=%s status=%s", build_id, mapped_status)
    return {"status": "ok", "build_id": build_id}


@router.post("/codemagic")
@limiter.limit("60/minute")
async def codemagic_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Codemagic build webhook'unu işler.

    İmza doğrulaması ve nonce replay koruması uygulanır.
    Build durumu (SUCCESS/FAILED/CANCELED vb.) iç duruma eşlenir
    ve build.finished event'i yayınlanır.

    Raises:
        400: Geçersiz imza veya JSON payload
    """
    body = await request.body()
    signature = request.headers.get("x-codemagic-signature", "")
    secret = settings.CODEMAGIC_WEBHOOK_SECRET

    if secret and not _verify_signature(body, signature, secret):
        raise HTTPException(status_code=400, detail="Codemagic webhook imzası geçersiz")

    delivery_id = request.headers.get("x-codemagic-delivery", "")
    if delivery_id:
        existing = await db.execute(
            select(WebhookNonce).where(WebhookNonce.nonce_value == delivery_id)
        )
        if existing.scalar_one_or_none():
            return {"status": "duplicate", "delivery_id": delivery_id}
        nonce = WebhookNonce(
            source="codemagic",
            nonce_value=delivery_id,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.add(nonce)
        await db.commit()

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz JSON payload")

    cm_status = payload.get("status", "").upper()
    build_id = payload.get("buildId") or payload.get("build", {}).get("id", "")

    status_map = {
        "SUCCESS": "success",
        "FINISHED": "success",
        "FAILED": "failed",
        "ERROR": "failed",
        "CANCELED": "failed",
        "CANCELLED": "failed",
    }
    mapped_status = status_map.get(cm_status)
    if not mapped_status or not build_id:
        return {"status": "ignored", "cm_status": cm_status}

    artifact_urls = payload.get("artifactUrls") or payload.get("artifacts", [])
    artifact_url = artifact_urls[0] if isinstance(artifact_urls, list) and artifact_urls else ""

    await events.publish_event("build.finished", {
        "build_id": build_id,
        "status": mapped_status,
        "artifact_url": artifact_url,
        "provider": "codemagic",
        "source": "codemagic_webhook",
    })

    logger.info("Codemagic webhook processed: build_id=%s status=%s", build_id, mapped_status)
    return {"status": "ok", "build_id": build_id}
