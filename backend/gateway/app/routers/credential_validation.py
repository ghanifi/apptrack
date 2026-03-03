import logging
import json
import httpx
import jwt
import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_current_user
from app.database import get_db
from app.routers.credentials import get_user_credential

router = APIRouter(prefix="/api/credentials", tags=["credentials"])
logger = logging.getLogger(__name__)

GOOGLE_PLAY_SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
APP_STORE_API_BASE = "https://api.appstoreconnect.apple.com/v1"


async def _validate_google_play(service_account_json: str) -> dict:
    try:
        sa = json.loads(service_account_json)
    except (json.JSONDecodeError, TypeError):
        return {"valid": False, "error": "Invalid JSON format", "provider": "google_play"}

    required_fields = ["client_email", "private_key", "token_uri"]
    missing = [f for f in required_fields if f not in sa]
    if missing:
        return {"valid": False, "error": f"Missing fields: {', '.join(missing)}", "provider": "google_play"}

    try:
        now = int(time.time())
        payload = {
            "iss": sa["client_email"],
            "scope": " ".join(GOOGLE_PLAY_SCOPES),
            "aud": sa.get("token_uri", GOOGLE_TOKEN_URL),
            "iat": now,
            "exp": now + 3600,
        }
        signed_jwt = jwt.encode(payload, sa["private_key"], algorithm="RS256")

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                sa.get("token_uri", GOOGLE_TOKEN_URL),
                data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": signed_jwt},
            )
            if resp.status_code == 200:
                return {"valid": True, "provider": "google_play", "email": sa["client_email"]}
            else:
                detail = resp.json().get("error_description", resp.text[:200])
                return {"valid": False, "error": f"Auth failed: {detail}", "provider": "google_play"}
    except Exception as e:
        return {"valid": False, "error": f"Validation error: {str(e)[:200]}", "provider": "google_play"}


async def _validate_app_store(key_id: str, issuer_id: str, private_key: str) -> dict:
    if not key_id or not issuer_id or not private_key:
        return {"valid": False, "error": "Missing Key ID, Issuer ID, or Private Key", "provider": "app_store"}

    try:
        now = int(time.time())
        payload = {
            "iss": issuer_id,
            "iat": now,
            "exp": now + 1200,
            "aud": "appstoreconnect-v1",
        }
        headers = {"kid": key_id, "typ": "JWT"}
        token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{APP_STORE_API_BASE}/apps",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": 1},
            )
            if resp.status_code == 200:
                apps = resp.json().get("data", [])
                return {
                    "valid": True,
                    "provider": "app_store",
                    "app_count": len(apps),
                    "team_id": issuer_id[:8] + "...",
                }
            elif resp.status_code == 401:
                return {"valid": False, "error": "Invalid credentials — check Key ID and Issuer ID", "provider": "app_store"}
            elif resp.status_code == 403:
                return {"valid": False, "error": "Key lacks required permissions — grant App Manager role", "provider": "app_store"}
            else:
                return {"valid": False, "error": f"API returned {resp.status_code}", "provider": "app_store"}
    except jwt.exceptions.InvalidKeyError:
        return {"valid": False, "error": "Invalid private key format — paste the full .p8 file content", "provider": "app_store"}
    except Exception as e:
        return {"valid": False, "error": f"Validation error: {str(e)[:200]}", "provider": "app_store"}


@router.post("/validate/google_play")
async def validate_google_play_credentials(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Google Play service account kimlik bilgilerini doğrular.

    Kaydedilmiş service account JSON anahtarını kullanarak Google OAuth2
    token endpoint'ine bağlanır ve kimlik doğrulamasını test eder.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Google Play service account anahtarı bulunamadı
    """
    key_json = await get_user_credential(db, current_user["id"], "google_play", "GOOGLE_PLAY_KEY_JSON")
    if not key_json:
        raise HTTPException(status_code=404, detail="Google Play service account key not found. Add it in Settings first.")
    result = await _validate_google_play(key_json)
    return result


@router.post("/validate/app_store")
async def validate_app_store_credentials(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """App Store Connect API kimlik bilgilerini doğrular.

    Key ID, Issuer ID ve Private Key ile JWT token oluşturarak
    App Store Connect API'ye test isteği gönderir.

    Raises:
        401: Kimlik doğrulama gerekli
        404: App Store credential'larından biri veya birkaçı eksik
    """
    key_id = await get_user_credential(db, current_user["id"], "app_store", "APP_STORE_KEY_ID")
    issuer_id = await get_user_credential(db, current_user["id"], "app_store", "APP_STORE_ISSUER_ID")
    private_key = await get_user_credential(db, current_user["id"], "app_store", "APP_STORE_PRIVATE_KEY")
    if not all([key_id, issuer_id, private_key]):
        missing = []
        if not key_id:
            missing.append("Key ID")
        if not issuer_id:
            missing.append("Issuer ID")
        if not private_key:
            missing.append("Private Key")
        raise HTTPException(status_code=404, detail=f"Missing App Store credentials: {', '.join(missing)}")
    result = await _validate_app_store(key_id, issuer_id, private_key)
    return result
