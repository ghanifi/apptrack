"""Agentic autofix iş yönetimi — in-memory job store + poll endpointleri.

POST başlatır (asyncio arka plan görevi), GET durumu poll eder. Job store in-process (build
polling ile aynı desen); gateway restart'ta kaybolur — kullanıcı yeniden başlatır (kalıcı DB YAGNI)."""
import asyncio
import base64
import logging
import time
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Build, Project
from app.routers.credentials import get_user_credential
from app.routers.build_diagnosis import (_fetch_repo_context, _parse_owner_repo, _resolve_github_token)
from app.llm import registry
from app import build_autofix
from app.build_autofix_agentic import run_agentic_autofix

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/build-diagnosis", tags=["build-diagnosis"])

_JOBS: dict[str, dict] = {}
_JOB_TTL = 3600.0  # saniye


def _prune():
    now = time.time()
    for jid in [k for k, v in _JOBS.items() if now - v.get("created_at", now) > _JOB_TTL]:
        _JOBS.pop(jid, None)


async def _github_file(owner_repo: str, branch: str, token: str, path: str) -> str | None:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as c:
        r = await c.get(f"https://api.github.com/repos/{owner_repo}/contents/{path}",
                        params={"ref": branch})
    if r.status_code != 200:
        return None
    return base64.b64decode(r.json()["content"]).decode("utf-8", "replace")


async def _run_job(job_id, provider_id, api_key, model, owner_repo, branch, token, log_tail, framework):
    job = _JOBS[job_id]

    def on_step(msg: str):
        job["steps"].append(msg)

    try:
        provider = registry.build_provider(provider_id, api_key)
        on_step("repo bağlamı alınıyor")
        repo_ctx = await _fetch_repo_context(owner_repo, branch, token)
        tree = repo_ctx["tree"]

        async def fetch_file(path):
            return await _github_file(owner_repo, branch, token, path)

        result = await run_agentic_autofix(provider, model, log_tail, tree, framework, fetch_file, on_step)

        if result["status"] == "fallback":
            on_step("model araç desteklemiyor — tek-atışa düşülüyor")
            repo_ctx["model"] = model
            proposal = await build_autofix.llm_propose_patch(provider, log_tail, repo_ctx, framework)
            if not proposal:
                job["state"] = "aborted"; job["error"] = "tek-atış da yama üretemedi"; return
            result = {"status": "done", "patch": proposal, "reason": None}

        if result["status"] != "done" or not result.get("patch"):
            job["state"] = "aborted"; job["error"] = result.get("reason") or "yama üretilemedi"; return

        patch = result["patch"]
        plan = {"id": "llm_agentic_fix", "title": patch["summary"], "kind": "llm_replace",
                "files": [patch["path"]], "new_content": patch["new_content"]}
        pr = await build_autofix.open_fix_pr(owner_repo, branch, token, plan)
        job["pr_url"] = pr["pr_url"]; job["state"] = "done"
    except Exception as exc:
        logger.error("agentic job %s hata: %s", job_id, exc)
        job["state"] = "error"; job["error"] = "Beklenmedik hata."


@router.post("/autofix/{build_id}/agentic")
async def start_agentic_autofix(build_id: str, current_user: dict = Depends(get_current_user),
                                db: AsyncSession = Depends(get_db)):
    """Başarısız build için agentic AI autofix işini başlatır (arka plan). {job_id} döner."""
    _prune()
    uid = current_user["id"]
    build = (await db.execute(select(Build).where(Build.id == build_id))).scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    project = (await db.execute(select(Project).where(Project.id == build.project_id))).scalar_one_or_none()
    if not project or project.owner_id != uid:
        raise HTTPException(status_code=404, detail="Build not found")
    if build.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed builds can be auto-fixed.")
    if not build.log_output:
        raise HTTPException(status_code=400, detail="No build log available.")

    provider_id = await get_user_credential(db, uid, "llm", "LLM_PROVIDER")
    if not provider_id or provider_id not in registry.PROVIDERS:
        raise HTTPException(status_code=400,
                            detail="Önce Ayarlar > AI Sağlayıcıları'ndan bir sağlayıcı yapılandırın.")
    api_key = await get_user_credential(db, uid, "llm", registry.PROVIDERS[provider_id]["key_name"])
    if not api_key:
        raise HTTPException(status_code=400, detail="Seçili sağlayıcı için API anahtarı yok.")
    model = await get_user_credential(db, uid, "llm", "LLM_MODEL") \
        or registry.PROVIDERS[provider_id]["default_model"]

    owner_repo = _parse_owner_repo(project.repo_url)
    token = await _resolve_github_token(db, uid)
    if not owner_repo or not token:
        raise HTTPException(status_code=400, detail="GitHub reposu/token çözümlenemedi.")

    job_id = str(uuid4())
    _JOBS[job_id] = {"owner_id": uid, "state": "running", "steps": [], "pr_url": None,
                     "error": None, "created_at": time.time()}
    branch = project.branch or "main"
    asyncio.create_task(_run_job(job_id, provider_id, api_key, model, owner_repo, branch,
                                 token, build.log_output[-8000:], project.framework))
    return {"job_id": job_id}


@router.get("/autofix/status/{job_id}")
async def agentic_status(job_id: str, current_user: dict = Depends(get_current_user)):
    job = _JOBS.get(job_id)
    if not job or job.get("owner_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"state": job["state"], "steps": job["steps"], "pr_url": job["pr_url"], "error": job["error"]}
