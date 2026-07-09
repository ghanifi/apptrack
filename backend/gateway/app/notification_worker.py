import json
import logging
import httpx
from sqlalchemy import select
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Notification, NotificationPreference, Build, Project, User, Deployment

logger = logging.getLogger(__name__)

EVENT_NOTIFICATION_MAP = {
    "build.finished": {
        "success": {"type": "build_success", "title": "Build Successful", "pref_key": "notify_build_success"},
        "failed": {"type": "build_failed", "title": "Build Failed", "pref_key": "notify_build_failed"},
    },
    "deploy.completed": {"type": "deploy_completed", "title": "Deployment Completed", "pref_key": "notify_deploy_completed"},
    "deploy.failed": {"type": "deploy_failed", "title": "Deployment Failed", "pref_key": "notify_deploy_failed"},
}


async def _send_slack(webhook_url: str, title: str, body: str):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook_url, json={
                "text": f"*{title}*\n{body}",
            })
    except Exception as exc:
        logger.error("Slack notification failed: %s", exc)


async def _send_discord(webhook_url: str, title: str, body: str):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook_url, json={
                "content": f"**{title}**\n{body}",
            })
    except Exception as exc:
        logger.error("Discord notification failed: %s", exc)


async def _send_email(to: str, title: str, body: str):
    smtp_host = getattr(settings, "SMTP_HOST", "")
    if not smtp_host:
        logger.debug("Email notification skipped — SMTP not configured")
        return
    try:
        import smtplib
        from email.mime.text import MIMEText
        smtp_port = int(getattr(settings, "SMTP_PORT", 587))
        smtp_user = getattr(settings, "SMTP_USER", "")
        smtp_pass = getattr(settings, "SMTP_PASS", "")

        msg = MIMEText(body)
        msg["Subject"] = title
        msg["From"] = smtp_user or "noreply@apptrack.dev"
        msg["To"] = to

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as exc:
        logger.error("Email notification failed: %s", exc)


async def _dispatch_notification(user_id: str, notif_type: str, title: str, body: str,
                                  resource_type: str | None = None, resource_id: str | None = None):
    async with AsyncSessionLocal() as db:
        pref_result = await db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        pref = pref_result.scalar_one_or_none()

        if pref and pref.in_app_enabled:
            notification = Notification(
                user_id=user_id,
                type=notif_type,
                title=title,
                body=body,
                channel="in_app",
                resource_type=resource_type,
                resource_id=resource_id,
            )
            db.add(notification)
            await db.commit()
        elif not pref:
            notification = Notification(
                user_id=user_id,
                type=notif_type,
                title=title,
                body=body,
                channel="in_app",
                resource_type=resource_type,
                resource_id=resource_id,
            )
            db.add(notification)
            await db.commit()

        if pref and pref.slack_enabled and pref.slack_webhook_url:
            await _send_slack(pref.slack_webhook_url, title, body)

        if pref and pref.discord_enabled and pref.discord_webhook_url:
            await _send_discord(pref.discord_webhook_url, title, body)

        if pref and pref.email_enabled:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if user:
                await _send_email(user.email, title, body)


async def _resolve_owner_id(payload: dict) -> str | None:
    """Payload'dan proje sahibini çöz. build.* eventlerinde project_id,
    deploy.* eventlerinde yalnızca deployment_id gelir — o zaman
    Deployment → Build → Project zinciriyle sahibe ulaşılır."""
    owner_id = payload.get("owner_id")
    if owner_id:
        return owner_id

    project_id = payload.get("project_id")
    deployment_id = payload.get("deployment_id")
    async with AsyncSessionLocal() as db:
        if not project_id and deployment_id:
            row = (await db.execute(
                select(Build.project_id)
                .join(Deployment, Deployment.build_id == Build.id)
                .where(Deployment.id == deployment_id)
            )).first()
            if row:
                project_id = row[0]
        if project_id:
            row = (await db.execute(
                select(Project.owner_id).where(Project.id == project_id)
            )).first()
            if row:
                owner_id = row[0]
    return owner_id


async def _process_notification_event(payload: dict, routing_key: str):
    owner_id = await _resolve_owner_id(payload)
    if not owner_id:
        logger.debug("Cannot determine owner_id for notification event %s", routing_key)
        return

    status = payload.get("status", "")
    build_id = payload.get("build_id", "")
    deployment_id = payload.get("deployment_id", "")

    # build-service başarısızlıkları ayrı bir routing key (build.failed) ile yayımlar;
    # aynı bildirim yolunu kullanmak için build.finished/status=failed'e normalize et.
    if routing_key == "build.failed":
        routing_key = "build.finished"
        status = "failed"

    if routing_key == "build.finished":
        config = EVENT_NOTIFICATION_MAP["build.finished"].get(status)
        if not config:
            return
        body = f"Build {build_id[:8]}... completed with status: {status}"
        if status == "failed":
            body = f"Build {build_id[:8]}... failed. Check logs for details."
        await _dispatch_notification(
            owner_id, config["type"], config["title"], body,
            resource_type="build", resource_id=build_id,
        )

    elif routing_key == "deploy.completed":
        config = EVENT_NOTIFICATION_MAP["deploy.completed"]
        target = payload.get("target", "store")
        body = f"Deployment {deployment_id[:8]}... to {target} completed successfully."
        await _dispatch_notification(
            owner_id, config["type"], config["title"], body,
            resource_type="deployment", resource_id=deployment_id,
        )

    elif routing_key == "deploy.failed":
        config = EVENT_NOTIFICATION_MAP["deploy.failed"]
        target = payload.get("target", "store")
        error = payload.get("error", "Unknown error")
        body = f"Deployment {deployment_id[:8]}... to {target} failed: {error}"
        await _dispatch_notification(
            owner_id, config["type"], config["title"], body,
            resource_type="deployment", resource_id=deployment_id,
        )


async def dispatch_for_event(payload: dict, routing_key: str):
    """Gateway event worker'ından in-process çağrılır. Bildirim event'leri
    default exchange üzerinden yalnızca gateway worker kuyruklarına ulaştığı için
    (ayrı bir 'notifications' exchange'ine kimse publish etmiyordu), bildirim
    gönderimi build/deploy işlendikten sonra doğrudan burada tetiklenir."""
    try:
        await _process_notification_event(payload, routing_key)
    except Exception as exc:
        logger.error("Notification dispatch failed for %s: %s", routing_key, exc)
