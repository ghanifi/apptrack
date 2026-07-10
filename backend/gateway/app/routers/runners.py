"""Self-hosted runner kurulum sihirbazı — GitHub Actions runner yönetimi proxy'si.

Kullanıcının kendi OAuth token'ı ile çalışır (repo scope + repo admin gerekir).
Registration token 1 saat ömürlüdür ve ASLA saklanmaz — talep anında üretilir.
Runner sürümü hardcode edilmez; GitHub'ın /runners/downloads endpoint'inden çekilir.
`build_setup_script` saf ve test edilebilirdir.
"""
import logging
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Project
from app.crypto import decrypt

logger = logging.getLogger(__name__)
router = APIRouter()

GITHUB_API = "https://api.github.com"

# Platforma göre varsayılan label seti (custom label her zaman öncelikli).
DEFAULT_LABELS = {
    ("osx", "arm64"): "self-hosted,macOS,ARM64",
    ("osx", "x64"): "self-hosted,macOS,X64",
    ("linux", "x64"): "self-hosted,Linux,X64",
    ("linux", "arm64"): "self-hosted,Linux,ARM64",
}


def pick_download(downloads: list[dict], os_name: str, arch: str) -> dict | None:
    """GitHub /runners/downloads yanıtından os/arch eşleşen girdiyi seç (saf)."""
    for d in downloads:
        if d.get("os") == os_name and d.get("architecture") == arch:
            return d
    return None


def resolve_labels(custom: str | None, os_name: str, arch: str) -> str:
    """Proje custom label'ı doluysa onu, boşsa platform varsayılanını döndür (saf)."""
    if custom and custom.strip():
        return ",".join(p.strip() for p in custom.split(",") if p.strip())
    return DEFAULT_LABELS.get((os_name, arch), "self-hosted")


def build_setup_script(repo_url: str, download_url: str, filename: str,
                       token: str, labels: str, os_name: str) -> str:
    """Kopyala-yapıştır kurulum bloğu üret (saf). Linux'ta svc.sh sudo'lu, macOS'ta sudo'suz."""
    svc = "sudo ./svc.sh install && sudo ./svc.sh start" if os_name == "linux" \
        else "./svc.sh install && ./svc.sh start"
    return (
        "mkdir -p actions-runner && cd actions-runner\n"
        f"curl -o {filename} -L {download_url}\n"
        f"tar xzf {filename}\n"
        f"./config.sh --url {repo_url} --token {token} --labels {labels} --unattended --replace\n"
        f"{svc}\n"
    )


def _owner_repo(repo_url: str) -> str:
    if "github.com/" not in repo_url:
        return ""
    raw = repo_url.rstrip("/").split("github.com/")[-1]
    return raw[:-4] if raw.endswith(".git") else raw


async def _load_project_and_token(db: AsyncSession, project_id: str, user_id: str) -> tuple[Project, str, str]:
    """Ownership doğrula, GitHub token'ı çöz, owner/repo çıkar."""
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project or project.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    owner_repo = _owner_repo(project.repo_url)
    if not owner_repo:
        raise HTTPException(status_code=400, detail="Proje bir GitHub reposuna bağlı değil.")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.github_access_token:
        raise HTTPException(status_code=400, detail="GitHub hesabı bağlı değil.")
    try:
        token = decrypt(user.github_access_token)
    except Exception:
        token = user.github_access_token
    return project, token, owner_repo


def _map_github_error(resp: httpx.Response) -> HTTPException:
    if resp.status_code == 403:
        return HTTPException(status_code=403, detail=(
            "Bu repo için admin yetkiniz yok. Runner kaydı repo admin izni gerektirir "
            "(org repolarında OAuth app kısıtı da engelleyebilir)."))
    if resp.status_code == 404:
        return HTTPException(status_code=404, detail="GitHub reposu bulunamadı.")
    return HTTPException(status_code=502, detail=f"GitHub API hatası ({resp.status_code}).")


@router.get("/{project_id}/runners")
async def list_runners(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reponun self-hosted runner listesi (canlı durum)."""
    _, token, owner_repo = await _load_project_and_token(db, project_id, current_user["id"])
    async with httpx.AsyncClient(timeout=15) as c:
        resp = await c.get(f"{GITHUB_API}/repos/{owner_repo}/actions/runners",
                           headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        raise _map_github_error(resp)
    return [{
        "id": r["id"],
        "name": r["name"],
        "os": r.get("os"),
        "status": r.get("status"),
        "busy": r.get("busy", False),
        "labels": [lb["name"] for lb in r.get("labels", [])],
        "version": r.get("version"),
    } for r in resp.json().get("runners", [])]


class SetupCommandRequest(BaseModel):
    os: Literal["osx", "linux"] = "osx"
    arch: Literal["arm64", "x64"] = "arm64"


@router.post("/{project_id}/runners/setup-command")
async def setup_command(
    project_id: str,
    req: SetupCommandRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Registration token (1 saat) + güncel indirme URL'i ile kurulum bloğu üretir.

    Token DB'ye yazılmaz; yalnızca üretilen script içinde kullanıcıya döner.
    """
    project, token, owner_repo = await _load_project_and_token(db, project_id, current_user["id"])
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=20, headers=headers) as c:
        dl = await c.get(f"{GITHUB_API}/repos/{owner_repo}/actions/runners/downloads")
        if dl.status_code != 200:
            raise _map_github_error(dl)
        entry = pick_download(dl.json(), req.os, req.arch)
        if not entry:
            raise HTTPException(status_code=502, detail=f"İndirme bulunamadı: {req.os}/{req.arch}.")

        reg = await c.post(f"{GITHUB_API}/repos/{owner_repo}/actions/runners/registration-token")
        if reg.status_code != 201:
            raise _map_github_error(reg)
        reg_data = reg.json()

    labels = resolve_labels(getattr(project, "runner_labels", None), req.os, req.arch)
    script = build_setup_script(
        repo_url=f"https://github.com/{owner_repo}",
        download_url=entry["download_url"], filename=entry["filename"],
        token=reg_data["token"], labels=labels, os_name=req.os,
    )
    return {"script": script, "expires_at": reg_data.get("expires_at"),
            "labels": labels, "download_url": entry["download_url"]}


@router.delete("/{project_id}/runners/{runner_id}")
async def remove_runner(
    project_id: str,
    runner_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Runner'ı repodan kaldırır (GitHub DELETE proxy)."""
    _, token, owner_repo = await _load_project_and_token(db, project_id, current_user["id"])
    async with httpx.AsyncClient(timeout=15) as c:
        resp = await c.delete(f"{GITHUB_API}/repos/{owner_repo}/actions/runners/{runner_id}",
                              headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 204:
        raise _map_github_error(resp)
    return {"removed": True}
