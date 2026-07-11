"""
Auto Signing — generates iOS Distribution certificate + provisioning profile
and Android release keystore using pure Python cryptography.

No Mac, no keytool, no openssl CLI, no OS-specific tools required.
Works on Linux, Windows, macOS — anywhere Python runs.
"""

import base64
import logging
import plistlib
from datetime import datetime

import httpx
import jwt as pyjwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs12, BestAvailableEncryption

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.database import get_db
from app.crypto import encrypt
from app.routers.credentials import get_user_credential
from app.audit import record_audit_with_db
from app.models import Credential
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

router = APIRouter()

APPLE_API_BASE = "https://api.appstoreconnect.apple.com/v1"


class AutoSignRequest(BaseModel):
    bundle_id: str | None = None
    cert_password: str = "apptrack-auto"


class AutoSignResponse(BaseModel):
    status: str
    certificate_id: str | None = None
    profile_id: str | None = None
    bundle_id: str | None = None
    message: str


class AndroidKeystoreRequest(BaseModel):
    key_alias: str = "upload"
    keystore_password: str = "apptrack-auto"
    key_password: str | None = None  # defaults to keystore_password
    common_name: str = "AppTrack Auto"
    organization: str = "AppTrack"
    country: str = "US"
    validity_years: int = 25


class AndroidKeystoreResponse(BaseModel):
    status: str
    key_alias: str
    message: str


def _generate_apple_jwt(key_id: str, issuer_id: str, private_key_pem: str) -> str:
    """Generate short-lived JWT for App Store Connect API authentication."""
    now = datetime.utcnow()
    payload = {
        "iss": issuer_id,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + 1200,  # 20 minutes
        "aud": "appstoreconnect-v1",
    }
    return pyjwt.encode(payload, private_key_pem, algorithm="ES256", headers={"kid": key_id})


def _generate_private_key_and_csr(email: str = "autosign@apptrack.dev") -> tuple[bytes, bytes]:
    """
    Generate RSA private key + Certificate Signing Request.
    Pure Python — no openssl CLI needed.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(
            x509.Name([
                NameOID.COMMON_NAME and x509.NameAttribute(NameOID.COMMON_NAME, "AppTrack Auto-Generated"),
                NameOID.EMAIL_ADDRESS and x509.NameAttribute(NameOID.EMAIL_ADDRESS, email),
            ])
        )
        .sign(private_key, hashes.SHA256())
    )

    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    csr_pem = csr.public_bytes(serialization.Encoding.PEM)

    return private_key_pem, csr_pem


def _create_p12(private_key_pem: bytes, cert_der: bytes, password: str) -> bytes:
    """
    Combine private key + Apple certificate into .p12 (PKCS12).
    Pure Python — no openssl CLI needed.
    """
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    certificate = x509.load_der_x509_certificate(cert_der)

    p12_data = pkcs12.serialize_key_and_certificates(
        name=b"AppTrack iOS Distribution",
        key=private_key,
        cert=certificate,
        cas=None,
        encryption_algorithm=BestAvailableEncryption(password.encode()),
    )

    return p12_data


async def _apple_api_request(
    method: str,
    path: str,
    token: str,
    json_body: dict | None = None,
) -> dict:
    """Make authenticated request to App Store Connect API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        if method == "GET":
            resp = await client.get(f"{APPLE_API_BASE}{path}", headers=headers)
        elif method == "POST":
            resp = await client.post(f"{APPLE_API_BASE}{path}", headers=headers, json=json_body)
        elif method == "DELETE":
            resp = await client.delete(f"{APPLE_API_BASE}{path}", headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")

    if resp.status_code >= 400:
        error_detail = resp.text[:500]
        logger.error("Apple API error %s %s: %s %s", method, path, resp.status_code, error_detail)
        raise HTTPException(
            status_code=502,
            detail=f"Apple API error ({resp.status_code}): {error_detail}",
        )

    if resp.status_code == 204:
        return {}
    return resp.json()


async def _save_credential(db: AsyncSession, user_id: str, provider: str, key_name: str, value: str):
    """Save or update an encrypted credential."""
    result = await db.execute(
        select(Credential).where(
            and_(
                Credential.owner_id == user_id,
                Credential.provider == provider,
                Credential.key_name == key_name,
            )
        )
    )
    cred = result.scalar_one_or_none()
    encrypted = encrypt(value)

    if cred:
        cred.encrypted_value = encrypted
        cred.updated_at = datetime.utcnow()
    else:
        cred = Credential(
            owner_id=user_id,
            provider=provider,
            key_name=key_name,
            encrypted_value=encrypted,
        )
        db.add(cred)
    await db.flush()


@router.post("/auto-generate-ios", response_model=AutoSignResponse)
async def auto_generate_ios_signing(
    req: AutoSignRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Automatically generate iOS Distribution certificate and provisioning profile.

    Requirements: App Store Connect API credentials must be saved first
    (Key ID, Issuer ID, Private Key .p8).

    Process (all server-side, no Mac needed):
    1. Generate RSA private key + CSR (Python cryptography)
    2. Submit CSR to Apple API → receive signed certificate
    3. Combine into .p12 (Python cryptography)
    4. Create/find provisioning profile via Apple API
    5. Save everything encrypted in AppTrack credentials store
    """
    user_id = current_user["id"]

    # --- Step 0: Get App Store Connect API credentials ---
    key_id = await get_user_credential(db, user_id, "app_store", "APP_STORE_KEY_ID")
    issuer_id = await get_user_credential(db, user_id, "app_store", "APP_STORE_ISSUER_ID")
    private_key_p8 = await get_user_credential(db, user_id, "app_store", "APP_STORE_PRIVATE_KEY")

    if not all([key_id, issuer_id, private_key_p8]):
        raise HTTPException(
            status_code=400,
            detail="App Store Connect API credentials required. Go to Settings > App Store Connect and enter your Key ID, Issuer ID, and Private Key (.p8).",
        )

    # Generate Apple JWT for API auth
    try:
        apple_token = _generate_apple_jwt(key_id, issuer_id, private_key_p8)
    except (ValueError, Exception) as exc:
        logger.error("Failed to create Apple JWT: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Invalid App Store Connect Private Key (.p8). Ensure you pasted the full contents of the .p8 file including BEGIN/END headers.",
        ) from exc

    # --- Step 1: Generate private key + CSR (pure Python) ---
    email = current_user.get("email", "autosign@apptrack.dev")
    private_key_pem, csr_pem = _generate_private_key_and_csr(email)

    # Extract CSR content (strip PEM headers for Apple API)
    csr_content = csr_pem.decode()

    # --- Step 2: Submit CSR to Apple → get certificate ---
    logger.info("Creating iOS Distribution certificate via Apple API for user=%s", user_id)
    cert_response = await _apple_api_request(
        "POST",
        "/certificates",
        apple_token,
        json_body={
            "data": {
                "type": "certificates",
                "attributes": {
                    "certificateType": "IOS_DISTRIBUTION",
                    "csrContent": csr_content,
                },
            }
        },
    )

    cert_data = cert_response["data"]
    cert_id = cert_data["id"]
    cert_content_base64 = cert_data["attributes"]["certificateContent"]
    cert_der = base64.b64decode(cert_content_base64)

    logger.info("Certificate created: id=%s", cert_id)

    # --- Step 3: Create .p12 (pure Python) ---
    p12_bytes = _create_p12(private_key_pem, cert_der, req.cert_password)
    p12_base64 = base64.b64encode(p12_bytes).decode()

    # --- Step 4: Find or create provisioning profile ---
    profile_id = None
    bundle_id_value = req.bundle_id

    if bundle_id_value:
        # Find the Bundle ID resource
        bundle_ids_resp = await _apple_api_request(
            "GET",
            f"/bundleIds?filter[identifier]={bundle_id_value}",
            apple_token,
        )
        bundle_id_resources = bundle_ids_resp.get("data", [])

        if bundle_id_resources:
            bundle_id_resource_id = bundle_id_resources[0]["id"]

            # Create Ad Hoc or App Store provisioning profile
            logger.info("Creating provisioning profile for bundle=%s", bundle_id_value)
            profile_resp = await _apple_api_request(
                "POST",
                "/profiles",
                apple_token,
                json_body={
                    "data": {
                        "type": "profiles",
                        "attributes": {
                            "name": f"AppTrack Auto - {bundle_id_value}",
                            "profileType": "IOS_APP_STORE",
                        },
                        "relationships": {
                            "bundleId": {
                                "data": {"type": "bundleIds", "id": bundle_id_resource_id}
                            },
                            "certificates": {
                                "data": [{"type": "certificates", "id": cert_id}]
                            },
                        },
                    }
                },
            )

            profile_data = profile_resp["data"]
            profile_id = profile_data["id"]
            profile_content_base64 = profile_data["attributes"]["profileContent"]

            # Save provisioning profile
            await _save_credential(
                db, user_id, "ios_signing",
                "IOS_PROVISIONING_PROFILE_BASE64",
                profile_content_base64,
            )
            logger.info("Provisioning profile created: id=%s", profile_id)

    # --- Step 5: Save credentials ---
    await _save_credential(db, user_id, "ios_signing", "IOS_CERT_P12_BASE64", p12_base64)
    await _save_credential(db, user_id, "ios_signing", "IOS_CERT_PASSWORD", req.cert_password)

    await db.commit()

    await record_audit_with_db(
        db, action="ios_signing.auto_generated", resource_type="credential",
        resource_id=cert_id, user_id=user_id,
        details={
            "certificate_id": cert_id,
            "profile_id": profile_id,
            "bundle_id": bundle_id_value,
            "method": "app_store_connect_api",
        },
    )
    await db.commit()

    message = "iOS Distribution certificate generated and saved."
    if profile_id:
        message += f" Provisioning profile created for {bundle_id_value}."
    elif bundle_id_value:
        message += f" Bundle ID '{bundle_id_value}' not found in your Apple account — profile not created. You can create it manually."
    else:
        message += " No bundle ID provided — provisioning profile was not created. You can generate it later."

    return AutoSignResponse(
        status="success",
        certificate_id=cert_id,
        profile_id=profile_id,
        bundle_id=bundle_id_value,
        message=message,
    )


def _generate_android_keystore(
    key_alias: str,
    keystore_password: str,
    key_password: str,
    common_name: str,
    organization: str,
    country: str,
    validity_years: int,
) -> bytes:
    """
    Generate Android release keystore (PKCS12) with self-signed certificate.
    Pure Python — no keytool CLI needed. Works on any OS.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
        x509.NameAttribute(NameOID.COUNTRY_NAME, country[:2].upper()),
    ])

    now = datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now.replace(year=now.year + validity_years))
        .sign(private_key, hashes.SHA256())
    )

    p12_data = pkcs12.serialize_key_and_certificates(
        name=key_alias.encode(),
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=BestAvailableEncryption(keystore_password.encode()),
    )

    return p12_data


@router.post("/auto-generate-android", response_model=AndroidKeystoreResponse)
async def auto_generate_android_keystore(
    req: AndroidKeystoreRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Automatically generate Android release keystore.

    No external tools needed — pure Python cryptography.
    Generates RSA 2048 key + self-signed certificate + PKCS12 keystore,
    then saves everything encrypted in the AppTrack credentials store.
    """
    user_id = current_user["id"]
    key_password = req.key_password or req.keystore_password

    # Generate keystore
    logger.info("Generating Android keystore for user=%s alias=%s", user_id, req.key_alias)
    try:
        keystore_bytes = _generate_android_keystore(
            key_alias=req.key_alias,
            keystore_password=req.keystore_password,
            key_password=key_password,
            common_name=req.common_name,
            organization=req.organization,
            country=req.country,
            validity_years=req.validity_years,
        )
    except Exception as exc:
        logger.error("Failed to generate Android keystore: %s", exc)
        raise HTTPException(status_code=500, detail=f"Keystore generation failed: {exc}") from exc

    keystore_base64 = base64.b64encode(keystore_bytes).decode()

    # Save all credentials
    await _save_credential(db, user_id, "android_signing", "ANDROID_KEYSTORE_BASE64", keystore_base64)
    await _save_credential(db, user_id, "android_signing", "ANDROID_KEYSTORE_PASSWORD", req.keystore_password)
    await _save_credential(db, user_id, "android_signing", "ANDROID_KEY_ALIAS", req.key_alias)
    await _save_credential(db, user_id, "android_signing", "ANDROID_KEY_PASSWORD", key_password)

    await db.commit()

    await record_audit_with_db(
        db, action="android_signing.auto_generated", resource_type="credential",
        resource_id=req.key_alias, user_id=user_id,
        details={
            "key_alias": req.key_alias,
            "common_name": req.common_name,
            "organization": req.organization,
            "validity_years": req.validity_years,
            "method": "python_cryptography",
        },
    )
    await db.commit()

    return AndroidKeystoreResponse(
        status="success",
        key_alias=req.key_alias,
        message=f"Android release keystore generated and saved. Key alias: {req.key_alias}, validity: {req.validity_years} years.",
    )


# ---------------------------------------------------------------------------
# iOS Signing Doctor — sertifika/profil süre bitimini proaktif izle
# ---------------------------------------------------------------------------
def _to_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def parse_provisioning_expiry(profile_b64: str) -> datetime | None:
    """.mobileprovision (CMS-imzalı) içindeki gömülü plist'ten ExpirationDate okur."""
    try:
        raw = base64.b64decode(profile_b64)
    except Exception:
        return None
    start = raw.find(b"<?xml")
    end = raw.find(b"</plist>")
    if start == -1 or end == -1:
        return None
    try:
        data = plistlib.loads(raw[start:end + len(b"</plist>")])
    except Exception:
        return None
    return _to_naive_utc(data.get("ExpirationDate"))


def parse_cert_expiry(p12_b64: str, password: str) -> datetime | None:
    """p12 (PKCS#12) içindeki sertifikanın notAfter (bitiş) tarihini okur."""
    try:
        raw = base64.b64decode(p12_b64)
        _, cert, _ = pkcs12.load_key_and_certificates(raw, password.encode() if password else None)
    except Exception:
        return None
    if cert is None:
        return None
    expiry = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after
    return _to_naive_utc(expiry)


def _health_item(name: str, kind: str, expiry: datetime | None) -> dict:
    if expiry is None:
        return {"name": name, "kind": kind, "expires_at": None, "days_left": None,
                "status": "unknown"}
    days_left = (expiry - datetime.utcnow()).days
    if days_left < 0:
        status = "expired"
    elif days_left <= 30:
        status = "expiring_soon"
    else:
        status = "ok"
    return {"name": name, "kind": kind, "expires_at": expiry.isoformat(),
            "days_left": days_left, "status": status}


@router.get("/health")
async def signing_health(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """iOS imzalama kimlik bilgilerinin sağlığı — sertifika/profil süre bitimini raporlar.
    Yüklenmiş kimlik bilgileri okunarak (ASC API gerektirmeden) hesaplanır."""
    uid = current_user["id"]
    profile_b64 = await get_user_credential(db, uid, "ios_signing", "IOS_PROVISIONING_PROFILE_BASE64")
    cert_b64 = await get_user_credential(db, uid, "ios_signing", "IOS_CERT_P12_BASE64")
    cert_pass = await get_user_credential(db, uid, "ios_signing", "IOS_CERT_PASSWORD")

    items: list[dict] = []
    if cert_b64:
        items.append(_health_item("Signing Certificate", "certificate",
                                  parse_cert_expiry(cert_b64, cert_pass or "")))
    if profile_b64:
        items.append(_health_item("Provisioning Profile", "profile",
                                  parse_provisioning_expiry(profile_b64)))

    order = {"expired": 0, "expiring_soon": 1, "unknown": 2, "ok": 3}
    overall = min((i["status"] for i in items), key=lambda s: order.get(s, 3)) if items else "not_configured"
    return {"configured": bool(items), "overall": overall, "items": items}


# ---------------------------------------------------------------------------
# İmzalama Doktoru — proje-bağlı yerel teşhis (Apple API YOK)
# ---------------------------------------------------------------------------
import hashlib

_EXPIRY_WARN_DAYS = 30
_SEVERITY = {"expired": "critical", "error": "critical", "mismatch": "critical",
             "expiring_soon": "warning", "missing": "warning",
             "unknown": "info", "ok": "info"}
_OVERALL_ORDER = ["expired", "error", "mismatch", "expiring_soon", "missing", "unknown", "ok"]


def parse_provisioning_profile(profile_b64: str) -> dict | None:
    """.mobileprovision → {expiry, bundle_id, cert_shas}. Parse edilemezse None."""
    try:
        raw = base64.b64decode(profile_b64)
    except Exception:
        return None
    start = raw.find(b"<?xml")
    end = raw.find(b"</plist>")
    if start == -1 or end == -1:
        return None
    try:
        data = plistlib.loads(raw[start:end + len(b"</plist>")])
    except Exception:
        return None
    app_id = (data.get("Entitlements") or {}).get("application-identifier", "")
    bundle_id = app_id.split(".", 1)[1] if "." in app_id else None
    cert_shas = set()
    for der in data.get("DeveloperCertificates", []) or []:
        der_bytes = bytes(der) if isinstance(der, (bytes, bytearray, memoryview)) else None
        if der_bytes:
            cert_shas.add(hashlib.sha256(der_bytes).hexdigest())
    return {"expiry": _to_naive_utc(data.get("ExpirationDate")),
            "bundle_id": bundle_id, "cert_shas": cert_shas}


def _cert_sha256_and_expiry(p12_b64: str, password: str) -> tuple[str | None, datetime | None, bool]:
    """p12 → (sertifika DER SHA-256, notAfter, decrypt_ok). Şifre yanlışsa (None, None, False)."""
    try:
        raw = base64.b64decode(p12_b64)
        _, cert, _ = pkcs12.load_key_and_certificates(raw, password.encode() if password else None)
    except Exception:
        return None, None, False
    if cert is None:
        return None, None, True
    der = cert.public_bytes(serialization.Encoding.DER)
    expiry = _to_naive_utc(getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after)
    return hashlib.sha256(der).hexdigest(), expiry, True


def _expiry_status(expiry: datetime | None) -> str:
    if expiry is None:
        return "unknown"
    days = (expiry - datetime.utcnow()).days
    if days < 0:
        return "expired"
    return "expiring_soon" if days <= _EXPIRY_WARN_DAYS else "ok"


def _check(cid: str, title: str, status: str, detail: str, fixable: bool) -> dict:
    return {"id": cid, "title": title, "status": status,
            "severity": _SEVERITY.get(status, "info"), "detail": detail, "fixable": fixable}


def diagnose_signing(cert_b64: str | None, cert_pass: str | None, profile_b64: str | None,
                     project_bundle_id: str | None, asc_configured: bool) -> dict:
    """Saklı iOS imza kimlik bilgilerini proje bundle id'siyle çapraz-kontrol eder.
    Apple API çağrısı YOK — tamamen yerel."""
    checks: list[dict] = []
    configured = bool(cert_b64 or profile_b64)
    cert_sha = None

    # --- sertifika + şifre ---
    if not cert_b64:
        checks.append(_check("certificate", "İmzalama sertifikası", "missing",
                             "Dağıtım sertifikası yüklü değil.", True))
    else:
        cert_sha, cert_expiry, decrypt_ok = _cert_sha256_and_expiry(cert_b64, cert_pass or "")
        if not decrypt_ok:
            checks.append(_check("cert_password", "Sertifika şifresi", "error",
                                 "p12 saklı şifreyle çözülemedi — yeniden üretim düzeltir.", True))
        else:
            st = _expiry_status(cert_expiry)
            detail = {"expired": "Sertifika süresi doldu.",
                      "expiring_soon": "Sertifika 30 gün içinde doluyor.",
                      "ok": "Sertifika geçerli.", "unknown": "Süre okunamadı."}[st]
            checks.append(_check("certificate", "İmzalama sertifikası", st, detail,
                                 st in ("expired", "expiring_soon")))

    # --- profil + bundle eşleşme + sertifika-profil bağı ---
    prof = parse_provisioning_profile(profile_b64) if profile_b64 else None
    if not profile_b64:
        checks.append(_check("profile", "Provizyon profili", "missing",
                             "Provizyon profili yüklü değil.", True))
    elif prof is None:
        checks.append(_check("profile", "Provizyon profili", "error",
                             "Profil okunamadı (bozuk olabilir) — yeniden üretin.", True))
    else:
        st = _expiry_status(prof["expiry"])
        detail = {"expired": "Profil süresi doldu.",
                  "expiring_soon": "Profil 30 gün içinde doluyor.",
                  "ok": "Profil geçerli.", "unknown": "Süre okunamadı."}[st]
        checks.append(_check("profile", "Provizyon profili", st, detail,
                             st in ("expired", "expiring_soon")))
        if project_bundle_id:
            if prof["bundle_id"] in ("*", project_bundle_id):
                checks.append(_check("bundle_match", "Bundle ID eşleşmesi", "ok",
                                     f"Profil {project_bundle_id} ile eşleşiyor.", False))
            else:
                checks.append(_check("bundle_match", "Bundle ID eşleşmesi", "mismatch",
                                     f"Profil '{prof['bundle_id']}' ≠ proje '{project_bundle_id}'. "
                                     "Bu sessiz imza hatasının en yaygın sebebidir.", True))
        if cert_sha:
            if cert_sha in prof["cert_shas"]:
                checks.append(_check("cert_in_profile", "Sertifika-profil bağı", "ok",
                                     "Sertifika bu profilde kayıtlı.", False))
            else:
                checks.append(_check("cert_in_profile", "Sertifika-profil bağı", "error",
                                     "Saklı sertifika bu profilde yok — profil bu sertifikayla imzalamaz.", True))

    # --- ön koşullar ---
    if not project_bundle_id:
        checks.append(_check("project_bundle_id", "Proje bundle id", "missing",
                             "Projenin bundle id'si tanımlı değil (Store Config).", False))
    if not asc_configured:
        checks.append(_check("asc_creds", "App Store Connect API", "missing",
                             "Otomatik onarım için ASC API kimlik bilgisi gerekli (Ayarlar).", False))

    statuses = [c["status"] for c in checks]
    overall = next((s for s in _OVERALL_ORDER if s in statuses), "ok") if configured else "not_configured"
    has_fixable = any(c["fixable"] and c["status"] != "missing" for c in checks) or \
        any(c["id"] in ("certificate", "profile") and c["status"] == "missing" for c in checks)
    can_auto_repair = has_fixable and asc_configured and bool(project_bundle_id)
    return {"configured": configured, "overall": overall,
            "checks": checks, "can_auto_repair": can_auto_repair}
