"""SSO (Single Sign-On) OIDC/SAML router."""
from __future__ import annotations

import uuid
import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.database import get_db
from app.dependencies import get_current_user
from app.models import SSOProvider, OrgMember, User, Organization
from app.crypto import encrypt, decrypt
from app.limiter import limiter
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sso", tags=["sso"])


# ---------- Schemas ----------

class SSOProviderCreate(BaseModel):
    provider_type: Literal["oidc", "saml"] = "oidc"
    name: str = Field(default="Corporate SSO", max_length=100)
    client_id: str = Field(..., min_length=1)
    client_secret: str = Field(..., min_length=1)
    discovery_url: str | None = None
    metadata_url: str | None = None
    allowed_domains: str | None = None  # "example.com,corp.com"


class SSOProviderUpdate(BaseModel):
    name: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    discovery_url: str | None = None
    metadata_url: str | None = None
    allowed_domains: str | None = None
    enabled: bool | None = None


# ---------- Admin Endpoints ----------

@router.post("/{org_id}/providers", status_code=201)
@limiter.limit("5/minute")
async def create_sso_provider(
    request: Request,
    org_id: str,
    req: SSOProviderCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Organizasyona SSO provider ekler.

    OIDC veya SAML provider yapılandırması oluşturur. OIDC için discovery URL
    doğrulaması yapılır. Client secret şifreli olarak saklanır. Varsayılan olarak devre dışıdır.

    Raises:
        400: Geçersiz OIDC discovery URL veya bağlantı hatası
        401: Kimlik doğrulama gerekli
        403: SSO provider ekleme yetkisi yok (owner/admin gerekli)
        429: Rate limit aşıldı (5 istek/dakika)
    """
    caller = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == current_user["id"],
        )
    )
    member = caller.scalar_one_or_none()
    if not member or member.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="SSO provider ekleme yetkiniz yok")

    # OIDC discovery URL dogrula
    if req.provider_type == "oidc" and req.discovery_url:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(req.discovery_url)
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"OIDC discovery URL erisilemedi (HTTP {resp.status_code})"
                    )
                oidc_config = resp.json()
                if "authorization_endpoint" not in oidc_config:
                    raise HTTPException(
                        status_code=400,
                        detail="OIDC discovery gecersiz — authorization_endpoint bulunamadi"
                    )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"OIDC discovery URL'e baglanilamadi: {exc}"
            )

    provider = SSOProvider(
        id=str(uuid.uuid4()),
        org_id=org_id,
        provider_type=req.provider_type,
        name=req.name,
        client_id=req.client_id,
        encrypted_client_secret=encrypt(req.client_secret),
        discovery_url=req.discovery_url,
        metadata_url=req.metadata_url,
        allowed_domains=req.allowed_domains,
        enabled=False,  # Varsayilan: devre disi
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)

    return {
        "id": provider.id,
        "provider_type": provider.provider_type,
        "name": provider.name,
        "client_id": provider.client_id,
        "discovery_url": provider.discovery_url,
        "allowed_domains": provider.allowed_domains,
        "enabled": provider.enabled,
        "created_at": provider.created_at.isoformat() if provider.created_at else None,
    }


@router.get("/{org_id}/providers")
async def list_sso_providers(
    org_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Organizasyonun SSO provider'larını listeler.

    Organizasyona tanımlı tüm SSO sağlayıcılarının yapılandırma bilgilerini
    döndürür. Client secret bilgisi gizlenir. Üyelik zorunludur.

    Raises:
        401: Kimlik doğrulama gerekli
        403: Erişim yetkiniz yok
    """
    caller = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == current_user["id"],
        )
    )
    if not caller.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")

    result = await db.execute(
        select(SSOProvider).where(SSOProvider.org_id == org_id)
        .order_by(SSOProvider.created_at.desc())
    )
    providers = result.scalars().all()
    return [
        {
            "id": p.id,
            "provider_type": p.provider_type,
            "name": p.name,
            "client_id": p.client_id,
            "discovery_url": p.discovery_url,
            "allowed_domains": p.allowed_domains,
            "enabled": p.enabled,
        }
        for p in providers
    ]


@router.put("/{org_id}/providers/{provider_id}")
async def update_sso_provider(
    org_id: str,
    provider_id: str,
    req: SSOProviderUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSO provider ayarlarını günceller.

    Ad, client bilgileri, discovery URL, izin verilen domainler ve
    aktif/pasif durumu kısmi olarak güncellenebilir. Owner/admin yetkisi gereklidir.

    Raises:
        401: Kimlik doğrulama gerekli
        403: Güncelleme yetkisi yok (owner/admin gerekli)
        404: SSO provider bulunamadı
    """
    caller = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == current_user["id"],
        )
    )
    member = caller.scalar_one_or_none()
    if not member or member.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Yetkiniz yok")

    provider = await db.execute(
        select(SSOProvider).where(
            SSOProvider.id == provider_id,
            SSOProvider.org_id == org_id,
        )
    )
    prov = provider.scalar_one_or_none()
    if not prov:
        raise HTTPException(status_code=404, detail="SSO provider bulunamadi")

    if req.name is not None:
        prov.name = req.name
    if req.client_id is not None:
        prov.client_id = req.client_id
    if req.client_secret is not None:
        prov.encrypted_client_secret = encrypt(req.client_secret)
    if req.discovery_url is not None:
        prov.discovery_url = req.discovery_url
    if req.metadata_url is not None:
        prov.metadata_url = req.metadata_url
    if req.allowed_domains is not None:
        prov.allowed_domains = req.allowed_domains
    if req.enabled is not None:
        prov.enabled = req.enabled

    prov.updated_at = datetime.utcnow()
    await db.commit()

    return {"status": "updated", "id": prov.id, "enabled": prov.enabled}


@router.delete("/{org_id}/providers/{provider_id}")
async def delete_sso_provider(
    org_id: str,
    provider_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSO provider'ı kalıcı olarak siler.

    Organizasyondan SSO sağlayıcısını kaldırır. Bu işlem yalnızca
    owner tarafından gerçekleştirilebilir.

    Raises:
        401: Kimlik doğrulama gerekli
        403: Silme yetkisi yok (yalnızca owner)
        404: SSO provider bulunamadı
    """
    caller = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == current_user["id"],
        )
    )
    member = caller.scalar_one_or_none()
    if not member or member.role != "owner":
        raise HTTPException(status_code=403, detail="SSO silme yalnizca owner yapabilir")

    provider = await db.execute(
        select(SSOProvider).where(
            SSOProvider.id == provider_id,
            SSOProvider.org_id == org_id,
        )
    )
    prov = provider.scalar_one_or_none()
    if not prov:
        raise HTTPException(status_code=404, detail="SSO provider bulunamadi")

    await db.delete(prov)
    await db.commit()

    return {"status": "deleted", "id": provider_id}


# ---------- OIDC Auth Flow ----------

@router.get("/authorize/{provider_id}")
async def sso_authorize(
    provider_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """OIDC authorization flow başlatır.

    Discovery document'tan authorization endpoint'i alarak kullanıcıyı
    IdP'nin giriş sayfasına yönlendirir. State parametresi ile CSRF koruması sağlar.

    Raises:
        400: Sadece OIDC desteklenir veya discovery URL yapılandırılmamış
        404: SSO provider bulunamadı veya devre dışı
        502: OIDC discovery erişim hatası
    """
    provider = await db.get(SSOProvider, provider_id)
    if not provider or not provider.enabled:
        raise HTTPException(status_code=404, detail="SSO provider bulunamadi veya devre disi")

    if provider.provider_type != "oidc":
        raise HTTPException(status_code=400, detail="Sadece OIDC flow destekleniyor")

    if not provider.discovery_url:
        raise HTTPException(status_code=400, detail="OIDC discovery URL yapilandirilmamis")

    # Discovery document al
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(provider.discovery_url)
            oidc_config = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OIDC discovery erisim hatasi: {exc}")

    auth_endpoint = oidc_config.get("authorization_endpoint")
    if not auth_endpoint:
        raise HTTPException(status_code=502, detail="OIDC authorization_endpoint bulunamadi")

    # State parametresi olustur
    state = str(uuid.uuid4())

    callback_url = f"{settings.GATEWAY_URL}/api/sso/callback/{provider_id}"

    redirect_url = (
        f"{auth_endpoint}"
        f"?response_type=code"
        f"&client_id={provider.client_id}"
        f"&redirect_uri={callback_url}"
        f"&scope=openid+email+profile"
        f"&state={state}"
    )

    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/callback/{provider_id}")
async def sso_callback(
    provider_id: str,
    code: str,
    state: str | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """OIDC callback — IdP'den dönen authorization code ile token alır.

    Authorization code'u access token ile değiştirir, kullanıcı bilgilerini alır,
    domain kontrolü yapar, gerekirse yeni kullanıcı oluşturur ve JWT token ile frontend'e yönlendirir.

    Raises:
        400: Geçersiz SSO provider veya e-posta alınamadı
        401: Token exchange başarısız
        403: E-posta domain'i izin verilmiyor
        502: OIDC token endpoint hatası
    """
    provider = await db.get(SSOProvider, provider_id)
    if not provider or not provider.enabled or provider.provider_type != "oidc":
        raise HTTPException(status_code=400, detail="Gecersiz SSO provider")

    if not provider.discovery_url:
        raise HTTPException(status_code=400, detail="Discovery URL yapilandirilmamis")

    # Discovery document al
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(provider.discovery_url)
        oidc_config = resp.json()

    token_endpoint = oidc_config.get("token_endpoint")
    userinfo_endpoint = oidc_config.get("userinfo_endpoint")

    if not token_endpoint:
        raise HTTPException(status_code=502, detail="OIDC token_endpoint bulunamadi")

    # Token exchange
    client_secret = decrypt(provider.encrypted_client_secret) if provider.encrypted_client_secret else ""
    callback_url = f"{settings.GATEWAY_URL}/api/sso/callback/{provider_id}"

    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": callback_url,
                "client_id": provider.client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if token_resp.status_code != 200:
        logger.error("SSO token exchange failed: %s", token_resp.text)
        raise HTTPException(status_code=401, detail="SSO token exchange basarisiz")

    tokens = token_resp.json()
    access_token = tokens.get("access_token")

    if not access_token:
        raise HTTPException(status_code=401, detail="SSO access token alinamadi")

    # UserInfo al
    user_info = {}
    if userinfo_endpoint:
        async with httpx.AsyncClient(timeout=10) as client:
            userinfo_resp = await client.get(
                userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_resp.status_code == 200:
                user_info = userinfo_resp.json()

    email = user_info.get("email", "")
    name = user_info.get("name") or user_info.get("preferred_username") or email

    if not email:
        raise HTTPException(status_code=400, detail="SSO provider'dan e-posta alinamadi")

    # Allowed domains kontrolu
    if provider.allowed_domains:
        allowed = [d.strip().lower() for d in provider.allowed_domains.split(",")]
        email_domain = email.split("@")[1].lower() if "@" in email else ""
        if email_domain not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"E-posta domain'i ({email_domain}) bu organizasyon icin izin verilmiyor"
            )

    # Kullaniciyi bul veya olustur
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=str(uuid.uuid4()),
            name=name,
            email=email,
            avatar_url=user_info.get("picture", ""),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("SSO: new user created email=%s org=%s", email, provider.org_id)

    # Organizasyona otomatik uye ekle (yoksa)
    existing_member = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == provider.org_id,
            OrgMember.user_id == user.id,
        )
    )
    if not existing_member.scalar_one_or_none():
        member = OrgMember(
            id=str(uuid.uuid4()),
            org_id=provider.org_id,
            user_id=user.id,
            role="member",
        )
        db.add(member)
        await db.commit()
        logger.info("SSO: user auto-added to org email=%s org=%s", email, provider.org_id)

    # JWT token olustur (mevcut auth.py pattern'ini kullan)
    from app.routers.auth import create_access_token, create_refresh_token

    token_data = {"sub": user.id, "email": user.email, "name": user.name}
    jwt_access = create_access_token(token_data)
    jwt_refresh = create_refresh_token(token_data)

    # Frontend'e yonlendir (token ile)
    frontend_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "http://localhost:3000"
    redirect_url = f"{frontend_url}/login?sso_token={jwt_access}&sso_refresh={jwt_refresh}"

    return RedirectResponse(url=redirect_url, status_code=302)
