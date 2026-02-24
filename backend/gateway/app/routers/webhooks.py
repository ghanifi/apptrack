import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.config import settings
from app.database import get_db
from app.models import Project
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
