import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.crypto import decrypt

router = APIRouter()


@router.get("/repos")
async def list_github_repos(
    page: int = 1,
    per_page: int = 30,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    if not user or not user.github_access_token:
        raise HTTPException(status_code=400, detail="GitHub account not connected. Please link your GitHub account.")

    try:
        raw_token = decrypt(user.github_access_token)
    except Exception:
        raw_token = user.github_access_token

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.github.com/user/repos",
            headers={"Authorization": f"Bearer {raw_token}"},
            params={"page": page, "per_page": per_page, "sort": "updated", "type": "all"},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch repos from GitHub")

    repos = resp.json()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "full_name": r["full_name"],
            "description": r.get("description"),
            "clone_url": r["clone_url"],
            "html_url": r["html_url"],
            "default_branch": r["default_branch"],
            "private": r["private"],
            "language": r.get("language"),
            "updated_at": r["updated_at"],
        }
        for r in repos
    ]


@router.get("/profile")
async def github_profile(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "github_connected": bool(user.github_access_token),
    }
