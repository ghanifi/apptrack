import hashlib
import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.limiter import limiter
from app.models import ApiKey, User
from app.routers.auth import create_access_token

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])
logger = logging.getLogger(__name__)

_KEY_BYTES = 24  # -> 48 hex karakter


def _generate_key() -> tuple[str, str, str]:
    """Ham anahtar, prefix (görüntüleme), hash döner. Ham anahtar yalnız 1 kez gösterilir."""
    raw = "atk_" + secrets.token_hex(_KEY_BYTES)
    prefix = raw[:12]  # 'atk_' + 8 hex
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, prefix, key_hash


class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyExchange(BaseModel):
    api_key: str


@router.post("")
@limiter.limit("10/minute")
async def create_api_key(
    request: Request,
    body: ApiKeyCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yeni API anahtarı oluşturur. Ham anahtar SADECE bu yanıtta döner — saklayın."""
    name = (body.name or "").strip() or "API Key"
    raw, prefix, key_hash = _generate_key()
    key = ApiKey(user_id=current_user["id"], name=name[:100], key_prefix=prefix, key_hash=key_hash)
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return {
        "id": key.id,
        "name": key.name,
        "key_prefix": key.key_prefix,
        "api_key": raw,  # bir kez!
        "created_at": key.created_at.isoformat(),
    }


@router.get("")
@limiter.limit("30/minute")
async def list_api_keys(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(ApiKey).where(ApiKey.user_id == current_user["id"]).order_by(ApiKey.created_at.desc())
    )).scalars().all()
    return {
        "items": [
            {
                "id": k.id,
                "name": k.name,
                "key_prefix": k.key_prefix,
                "revoked": k.revoked,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "created_at": k.created_at.isoformat(),
            }
            for k in rows
        ]
    }


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = (await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user["id"])
    )).scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.revoked = True
    await db.commit()
    return {"status": "revoked"}


@router.post("/exchange")
@limiter.limit("30/minute")
async def exchange_api_key(
    request: Request,
    body: ApiKeyExchange,
    db: AsyncSession = Depends(get_db),
):
    """API anahtarını kısa ömürlü access token'a çevirir (MCP server / CLI kullanır).
    Tüm REST uçları JWT beklediğinden, programatik istemciler önce burada takas yapar."""
    raw = (body.api_key or "").strip()
    if not raw.startswith("atk_"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    key = (await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked == False)  # noqa: E712
    )).scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    user = (await db.execute(select(User).where(User.id == key.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Key owner not found")

    await db.execute(update(ApiKey).where(ApiKey.id == key.id).values(last_used_at=datetime.utcnow()))
    await db.commit()

    token = create_access_token({"sub": user.id, "email": user.email, "name": getattr(user, "name", None)})
    from app.config import settings
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
