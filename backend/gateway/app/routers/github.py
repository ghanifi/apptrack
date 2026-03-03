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
    """Kullanıcının GitHub repo'larını listeler.

    Bağlı GitHub hesabı üzerinden kullanıcının erişebildiği tüm repo'ları
    sayfalanmış olarak döndürür. Güncelleme tarihine göre sıralanır.

    Raises:
        400: GitHub hesabı bağlı değil
        401: Kimlik doğrulama gerekli
        502: GitHub API'den yanıt alınamadı
    """
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


@router.get("/repos/{owner}/{repo}/branches")
async def list_repo_branches(
    owner: str,
    repo: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Belirtilen GitHub repo'sunun branch'lerini listeler.

    Owner ve repo adı ile GitHub API'den branch listesini çeker.
    Her branch için isim, koruma durumu ve son commit SHA'sı döndürülür.

    Raises:
        400: GitHub hesabı bağlı değil
        401: Kimlik doğrulama gerekli
        502: GitHub API'den yanıt alınamadı
    """
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    if not user or not user.github_access_token:
        raise HTTPException(status_code=400, detail="GitHub account not connected")

    try:
        raw_token = decrypt(user.github_access_token)
    except Exception:
        raw_token = user.github_access_token

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/branches",
            headers={"Authorization": f"Bearer {raw_token}"},
            params={"per_page": 100},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch branches from GitHub")

    branches = resp.json()
    return [
        {
            "name": b["name"],
            "protected": b.get("protected", False),
            "sha": b["commit"]["sha"],
        }
        for b in branches
    ]


@router.get("/repos/{owner}/{repo}/contents")
async def list_repo_contents(
    owner: str,
    repo: str,
    path: str = "",
    ref: str = "main",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Belirtilen repo yolundaki dosya ve klasörleri listeler.

    GitHub Contents API üzerinden repo içeriğini getirir.
    İsteğe bağlı path ve ref (branch/tag) parametreleri desteklenir.

    Raises:
        400: GitHub hesabı bağlı değil
        401: Kimlik doğrulama gerekli
        502: GitHub API'den yanıt alınamadı
    """
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    if not user or not user.github_access_token:
        raise HTTPException(status_code=400, detail="GitHub account not connected")

    try:
        raw_token = decrypt(user.github_access_token)
    except Exception:
        raw_token = user.github_access_token

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {raw_token}"},
            params={"ref": ref},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch repo contents from GitHub")

    return resp.json()


@router.delete("/disconnect")
async def disconnect_github(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """GitHub hesap bağlantısını keser.

    Kullanıcının GitHub access token ve GitHub ID bilgilerini sıfırlar.
    Bu işlemden sonra GitHub ile ilgili özellikler kullanılamaz hale gelir.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Kullanıcı bulunamadı
    """
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.github_access_token = None
    user.github_id = None
    await db.commit()
    return {"status": "disconnected", "message": "GitHub account unlinked"}


@router.get("/profile")
async def github_profile(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Kullanıcının profil bilgilerini ve GitHub bağlantı durumunu döndürür.

    Kullanıcı adı, e-posta, avatar URL ve GitHub hesabının bağlı olup
    olmadığı bilgisini içerir.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "github_connected": bool(user.github_access_token),
    }
