"""Crash reporting integration — Sentry project stats and release creation."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Project, Credential, Build
from app.crypto import decrypt
from app.config import settings

router = APIRouter(prefix="/api/projects", tags=["crash-reporting"])
logger = logging.getLogger(__name__)


@router.get("/{project_id}/crash-stats")
async def get_crash_stats(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Projenin Sentry crash istatistiklerini getirir.

    Sentry DSN ve project slug credential olarak kayıtlıysa gerçek
    veriler çekilir. Yoksa varsayılan boş istatistik döner.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı
    """
    project = await _verify_project_owner(db, project_id, current_user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    sentry_slug = await _get_sentry_slug(db, current_user["id"])
    if not sentry_slug:
        return {
            "project_id": project_id,
            "connected": False,
            "message": "Sentry not configured. Add SENTRY_PROJECT_SLUG credential.",
        }

    sentry_token = settings.SENTRY_AUTH_TOKEN
    if not sentry_token:
        return {
            "project_id": project_id,
            "connected": False,
            "message": "SENTRY_AUTH_TOKEN not set in server config.",
        }

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://sentry.io/api/0/projects/{sentry_slug}/stats/",
                headers={"Authorization": f"Bearer {sentry_token}"},
                params={"stat": "received", "resolution": "1d"},
            )
            if resp.status_code != 200:
                return {
                    "project_id": project_id,
                    "connected": True,
                    "error": f"Sentry API returned {resp.status_code}",
                }

            stats = resp.json()
            total_events = sum(point[1] for point in stats) if stats else 0

            sessions_resp = await client.get(
                f"https://sentry.io/api/0/projects/{sentry_slug}/",
                headers={"Authorization": f"Bearer {sentry_token}"},
            )
            project_info = sessions_resp.json() if sessions_resp.status_code == 200 else {}

            return {
                "project_id": project_id,
                "connected": True,
                "sentry_project": project_info.get("name", sentry_slug),
                "stats": {
                    "total_events_24h": total_events,
                    "crash_free_rate": max(0, 100 - (total_events / max(1, total_events + 1000) * 100)),
                },
                "data_source": "sentry",
            }
    except Exception as exc:
        logger.warning("Sentry stats fetch failed: %s", exc)
        return {
            "project_id": project_id,
            "connected": True,
            "error": str(exc),
        }


@router.post("/{project_id}/sentry-release")
async def create_sentry_release(
    project_id: str,
    build_id: str,
    version: str = "",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Build sonrası Sentry'de otomatik release oluşturur.

    Build bilgilerinden version ve commit SHA alarak Sentry API
    üzerinden yeni release kaydı yapar.

    Raises:
        400: Sentry yapılandırılmamış
        401: Kimlik doğrulama gerekli
        404: Proje veya build bulunamadı
    """
    project = await _verify_project_owner(db, project_id, current_user["id"])
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    build_result = await db.execute(
        select(Build).where(and_(Build.id == build_id, Build.project_id == project_id))
    )
    build = build_result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    sentry_slug = await _get_sentry_slug(db, current_user["id"])
    sentry_token = settings.SENTRY_AUTH_TOKEN
    if not sentry_slug or not sentry_token:
        raise HTTPException(status_code=400, detail="Sentry not configured")

    release_version = version or f"{project.name}@{build_id[:8]}"

    try:
        import httpx
        org_slug = sentry_slug.split("/")[0] if "/" in sentry_slug else sentry_slug

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://sentry.io/api/0/organizations/{org_slug}/releases/",
                headers={"Authorization": f"Bearer {sentry_token}"},
                json={
                    "version": release_version,
                    "projects": [sentry_slug.split("/")[1]] if "/" in sentry_slug else [],
                    "refs": [{"repository": project.repo_url, "commit": build.commit_sha}]
                    if build.commit_sha else [],
                },
            )

            if resp.status_code in (200, 201):
                return {
                    "status": "created",
                    "version": release_version,
                    "sentry_response": resp.json(),
                }
            else:
                return {
                    "status": "error",
                    "sentry_status": resp.status_code,
                    "detail": resp.text,
                }
    except Exception as exc:
        logger.error("Sentry release creation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Sentry API error: {exc}")


async def _get_sentry_slug(db: AsyncSession, user_id: str) -> str | None:
    result = await db.execute(
        select(Credential).where(
            and_(
                Credential.owner_id == user_id,
                Credential.provider == "sentry",
                Credential.key_name == "SENTRY_PROJECT_SLUG",
            )
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        return None
    return decrypt(cred.encrypted_value)


async def _verify_project_owner(db: AsyncSession, project_id: str, user_id: str):
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == user_id))
    )
    return result.scalar_one_or_none()
