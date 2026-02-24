from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from datetime import datetime
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Credential
from app.crypto import encrypt, decrypt, re_encrypt
from app.audit import record_audit_with_db

router = APIRouter()

ALLOWED_PROVIDERS = {
    "eas": ["EAS_TOKEN", "EXPO_APP_ID"],
    "codemagic": ["CODEMAGIC_TOKEN", "CODEMAGIC_APP_ID"],
    "google_play": ["GOOGLE_PLAY_KEY_JSON"],
    "app_store": ["APP_STORE_KEY_ID", "APP_STORE_ISSUER_ID", "APP_STORE_PRIVATE_KEY"],
}


class CredentialUpsert(BaseModel):
    provider: str
    key_name: str
    value: str

    @field_validator("value")
    @classmethod
    def value_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Credential value cannot be empty or whitespace")
        return v.strip()


class CredentialInfo(BaseModel):
    id: str
    provider: str
    key_name: str
    created_at: str
    updated_at: str


@router.get("", response_model=List[CredentialInfo])
async def list_credentials(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Credential).where(Credential.owner_id == current_user["id"]).order_by(Credential.provider, Credential.key_name)
    )
    creds = result.scalars().all()
    return [
        CredentialInfo(id=c.id, provider=c.provider, key_name=c.key_name,
                       created_at=c.created_at.isoformat(), updated_at=c.updated_at.isoformat())
        for c in creds
    ]


@router.put("")
async def upsert_credential(
    req: CredentialUpsert,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed_keys = ALLOWED_PROVIDERS.get(req.provider)
    if not allowed_keys or req.key_name not in allowed_keys:
        raise HTTPException(status_code=400, detail=f"Unknown provider/key: {req.provider}/{req.key_name}")

    result = await db.execute(
        select(Credential).where(
            and_(Credential.owner_id == current_user["id"],
                 Credential.provider == req.provider,
                 Credential.key_name == req.key_name)
        )
    )
    cred = result.scalar_one_or_none()

    encrypted = encrypt(req.value)
    if cred:
        cred.encrypted_value = encrypted
        cred.updated_at = datetime.utcnow()
    else:
        cred = Credential(
            owner_id=current_user["id"],
            provider=req.provider,
            key_name=req.key_name,
            encrypted_value=encrypted,
        )
        db.add(cred)

    await db.commit()
    await record_audit_with_db(
        db, action="credential.upserted", resource_type="credential",
        resource_id=f"{req.provider}/{req.key_name}", user_id=current_user["id"],
        details={"provider": req.provider, "key_name": req.key_name},
    )
    await db.commit()
    return {"status": "saved", "provider": req.provider, "key_name": req.key_name}


@router.delete("/{provider}/{key_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    provider: str,
    key_name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(Credential).where(
            and_(Credential.owner_id == current_user["id"],
                 Credential.provider == provider,
                 Credential.key_name == key_name)
        )
    )
    await db.commit()


async def get_user_credential(db: AsyncSession, user_id: str, provider: str, key_name: str) -> str | None:
    result = await db.execute(
        select(Credential).where(
            and_(Credential.owner_id == user_id,
                 Credential.provider == provider,
                 Credential.key_name == key_name)
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        return None
    import logging
    logging.getLogger(__name__).info(
        "Secret access: user=%s provider=%s key=%s credential_id=%s",
        user_id, provider, key_name, cred.id,
    )
    return decrypt(cred.encrypted_value)


@router.post("/rotate-keys")
async def rotate_encryption_keys(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Credential).where(Credential.owner_id == current_user["id"])
    )
    creds = result.scalars().all()
    rotated = 0
    for cred in creds:
        new_val = re_encrypt(cred.encrypted_value)
        if new_val and new_val != cred.encrypted_value:
            cred.encrypted_value = new_val
            cred.updated_at = datetime.utcnow()
            rotated += 1
    await db.commit()
    return {"status": "ok", "rotated": rotated, "total": len(creds)}
