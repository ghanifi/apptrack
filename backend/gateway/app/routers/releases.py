import logging
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Release, Build, Project

router = APIRouter(prefix="/api", tags=["releases"])
logger = logging.getLogger(__name__)

CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(?P<type>feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"!?:\s*(?P<description>.+)$",
    re.MULTILINE,
)

TYPE_LABELS = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "docs": "Documentation",
    "style": "Styling",
    "refactor": "Refactoring",
    "perf": "Performance",
    "test": "Tests",
    "chore": "Chores",
    "ci": "CI/CD",
    "build": "Build System",
    "revert": "Reverts",
}


class ReleaseUpdate(BaseModel):
    title: str | None = None
    notes: str | None = None
    version: str | None = None


def _parse_conventional_commits(log_text: str) -> str:
    sections: dict[str, list[str]] = {}
    for match in CONVENTIONAL_COMMIT_RE.finditer(log_text):
        commit_type = match.group("type")
        scope = match.group("scope")
        desc = match.group("description").strip()
        label = TYPE_LABELS.get(commit_type, "Other")
        if label not in sections:
            sections[label] = []
        entry = f"- {desc}" if not scope else f"- **{scope}:** {desc}"
        sections[label].append(entry)

    if not sections:
        lines = [l.strip() for l in log_text.strip().split("\n") if l.strip()]
        return "\n".join(f"- {l}" for l in lines[:20]) if lines else "No changes recorded."

    parts = []
    for label in ["Features", "Bug Fixes", "Performance", "Refactoring", "Documentation", "Tests", "Chores", "CI/CD", "Build System", "Styling", "Reverts", "Other"]:
        if label in sections:
            parts.append(f"### {label}\n" + "\n".join(sections[label]))

    return "\n\n".join(parts)


@router.get("/builds/{build_id}/release-notes")
async def get_build_release_notes(
    build_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Build).join(Project).where(
            and_(Build.id == build_id, Project.owner_id == current_user["id"])
        )
    )
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    release_result = await db.execute(
        select(Release).where(Release.build_id == build_id)
    )
    release = release_result.scalar_one_or_none()

    if release:
        return {
            "id": release.id,
            "build_id": build_id,
            "version": release.version,
            "title": release.title,
            "notes": release.notes,
            "auto_generated": release.auto_generated,
            "created_at": release.created_at.isoformat(),
        }

    return {
        "build_id": build_id,
        "message": "No release notes found. Use POST to generate.",
    }


@router.post("/builds/{build_id}/release-notes")
async def generate_release_notes(
    build_id: str,
    commit_log: str = "",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Build).join(Project).where(
            and_(Build.id == build_id, Project.owner_id == current_user["id"])
        )
    )
    build = result.scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    existing = await db.execute(select(Release).where(Release.build_id == build_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Release notes already exist for this build")

    notes = _parse_conventional_commits(commit_log) if commit_log else "No commit log provided."
    title = f"Release for build {build_id[:8]}"

    release = Release(
        project_id=build.project_id,
        build_id=build_id,
        title=title,
        notes=notes,
        auto_generated=True,
        created_by=current_user["id"],
    )
    db.add(release)
    await db.commit()
    await db.refresh(release)

    return {
        "id": release.id,
        "build_id": build_id,
        "title": release.title,
        "notes": release.notes,
        "auto_generated": True,
    }


@router.put("/releases/{release_id}")
async def update_release_notes(
    release_id: str,
    body: ReleaseUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # IDOR koruması: release'i sahibi olunan proje üzerinden kapıla (başkasının
    # release notunu ezmeyi engelle). Diğer uçlarla aynı owner-join deseni.
    result = await db.execute(
        select(Release).join(Project, Release.project_id == Project.id).where(
            and_(Release.id == release_id, Project.owner_id == current_user["id"])
        )
    )
    release = result.scalar_one_or_none()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")

    if body.title is not None:
        release.title = body.title
    if body.notes is not None:
        release.notes = body.notes
        release.auto_generated = False
    if body.version is not None:
        release.version = body.version

    release.updated_at = datetime.utcnow()
    await db.commit()

    return {"id": release.id, "status": "updated"}


@router.get("/projects/{project_id}/releases")
async def list_project_releases(
    project_id: str,
    limit: int = Query(default=20, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj_result = await db.execute(
        select(Project).where(
            and_(Project.id == project_id, Project.owner_id == current_user["id"])
        )
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Release).where(Release.project_id == project_id)
        .order_by(Release.created_at.desc()).limit(limit)
    )
    releases = result.scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "build_id": r.build_id,
                "version": r.version,
                "title": r.title,
                "notes": r.notes,
                "auto_generated": r.auto_generated,
                "created_at": r.created_at.isoformat(),
            }
            for r in releases
        ]
    }
