"""AI sağlayıcı ayarları (BYOK) — seçim/model + bağlantı testi. Anahtarlar credentials'ta şifreli.
Autofix LLM fallback bunu tüketir. MCP DEĞİL — giden HTTPS."""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.crypto import encrypt
from app.models import Credential
from app.routers.credentials import get_user_credential
from app.llm import registry
from app.llm.base import LLMMessage, LLMError

logger = logging.getLogger(__name__)
router = APIRouter()
_LLM = "llm"


class AiConfigBody(BaseModel):
    provider: str
    model: str | None = None
    api_key: str | None = None


async def _put_cred(db: AsyncSession, uid: str, key_name: str, value: str):
    row = (await db.execute(select(Credential).where(and_(
        Credential.owner_id == uid, Credential.provider == _LLM,
        Credential.key_name == key_name)))).scalar_one_or_none()
    enc = encrypt(value)
    if row:
        row.encrypted_value = enc
    else:
        db.add(Credential(owner_id=uid, provider=_LLM, key_name=key_name, encrypted_value=enc))


@router.get("/config")
async def get_ai_config(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    uid = current_user["id"]
    provider = await get_user_credential(db, uid, _LLM, "LLM_PROVIDER")
    model = await get_user_credential(db, uid, _LLM, "LLM_MODEL")
    configured = {}
    for pid, spec in registry.PROVIDERS.items():
        configured[pid] = bool(await get_user_credential(db, uid, _LLM, spec["key_name"]))
    return {
        "provider": provider, "model": model,
        "providers": [{"id": pid, "label": s["label"], "default_model": s["default_model"], "free": s["free"]}
                      for pid, s in registry.PROVIDERS.items()],
        "configured": configured,
    }


@router.put("/config")
async def put_ai_config(body: AiConfigBody, current_user: dict = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    if body.provider not in registry.PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Bilinmeyen sağlayıcı: {body.provider}")
    uid = current_user["id"]
    await _put_cred(db, uid, "LLM_PROVIDER", body.provider)
    await _put_cred(db, uid, "LLM_MODEL", body.model or registry.PROVIDERS[body.provider]["default_model"])
    if body.api_key:
        await _put_cred(db, uid, registry.PROVIDERS[body.provider]["key_name"], body.api_key)
    await db.commit()
    return {"ok": True}


@router.post("/test")
async def test_ai(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    uid = current_user["id"]
    provider = await get_user_credential(db, uid, _LLM, "LLM_PROVIDER")
    if not provider or provider not in registry.PROVIDERS:
        return {"ok": False, "model": None, "latency_ms": None, "error": "Önce bir sağlayıcı seçin."}
    spec = registry.PROVIDERS[provider]
    api_key = await get_user_credential(db, uid, _LLM, spec["key_name"])
    if not api_key:
        return {"ok": False, "model": None, "latency_ms": None,
                "error": f"{spec['label']} için API anahtarı girilmemiş."}
    model = await get_user_credential(db, uid, _LLM, "LLM_MODEL") or spec["default_model"]
    prov = registry.build_provider(provider, api_key)
    t0 = time.monotonic()
    try:
        res = await prov.complete([LLMMessage("user", "ping")], model=model, max_tokens=5)
    except LLMError as exc:
        return {"ok": False, "model": model, "latency_ms": None, "error": str(exc)}
    except Exception as exc:
        logger.error("AI test beklenmedik hata: %s", exc)
        return {"ok": False, "model": model, "latency_ms": None, "error": "Bağlantı hatası."}
    return {"ok": True, "model": res.model or model,
            "latency_ms": int((time.monotonic() - t0) * 1000), "error": None}
