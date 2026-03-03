import logging
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Project, StoreMetadata

router = APIRouter()
logger = logging.getLogger(__name__)

SUPPORTED_LOCALES = [
    "en-US", "tr-TR", "de-DE", "fr-FR", "es-ES", "it-IT", "pt-BR", "ja-JP",
    "ko-KR", "zh-CN", "zh-TW", "ar-SA", "nl-NL", "pl-PL", "ru-RU", "sv-SE",
    "da-DK", "fi-FI", "nb-NO", "id-ID", "th-TH", "vi-VN", "ms-MY", "hi-IN",
]

SCREENSHOT_SPECS = {
    "ios": {
        "iphone_6_7": {"label": "iPhone 6.7\"", "width": 1290, "height": 2796, "required": True},
        "iphone_6_5": {"label": "iPhone 6.5\"", "width": 1242, "height": 2688, "required": False},
        "iphone_5_5": {"label": "iPhone 5.5\"", "width": 1242, "height": 2208, "required": False},
        "ipad_12_9": {"label": "iPad 12.9\"", "width": 2048, "height": 2732, "required": False},
    },
    "android": {
        "phone": {"label": "Phone", "width": 1080, "height": 1920, "required": True},
        "tablet_7": {"label": "7\" Tablet", "width": 1200, "height": 1920, "required": False},
        "tablet_10": {"label": "10\" Tablet", "width": 1920, "height": 1200, "required": False},
    },
}

ICON_SPECS = {
    "ios": {"width": 1024, "height": 1024, "alpha": False, "format": "PNG"},
    "android": {"width": 512, "height": 512, "alpha": True, "format": "PNG"},
}


class StoreMetadataUpsert(BaseModel):
    app_name: Optional[str] = None
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    keywords: Optional[str] = None
    privacy_url: Optional[str] = None
    support_url: Optional[str] = None
    marketing_url: Optional[str] = None
    category: Optional[str] = None
    bundle_id: Optional[str] = None
    version: Optional[str] = None
    icon_url: Optional[str] = None
    screenshots: Optional[dict] = None
    feature_graphic_url: Optional[str] = None


def _serialize(meta: StoreMetadata) -> dict:
    return {
        "id": meta.id,
        "project_id": meta.project_id,
        "platform": meta.platform,
        "locale": meta.locale,
        "app_name": meta.app_name,
        "short_description": meta.short_description,
        "full_description": meta.full_description,
        "keywords": meta.keywords,
        "privacy_url": meta.privacy_url,
        "support_url": meta.support_url,
        "marketing_url": meta.marketing_url,
        "category": meta.category,
        "bundle_id": meta.bundle_id,
        "version": meta.version,
        "icon_url": meta.icon_url,
        "screenshots": meta.screenshots,
        "feature_graphic_url": meta.feature_graphic_url,
        "created_at": meta.created_at.isoformat(),
        "updated_at": meta.updated_at.isoformat(),
    }


async def _verify_project_ownership(db: AsyncSession, project_id: str, user_id: str) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/store-metadata")
async def get_store_metadata(
    project_id: str,
    locale: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Projenin mağaza metadata kayıtlarını getirir.

    İsteğe bağlı locale parametresi ile filtrelenebilir.
    Tüm platform ve dil kombinasyonları için metadata döndürülür.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
    """
    await _verify_project_ownership(db, project_id, current_user["id"])
    stmt = select(StoreMetadata).where(StoreMetadata.project_id == project_id)
    if locale:
        stmt = stmt.where(StoreMetadata.locale == locale)
    result = await db.execute(stmt)
    entries = result.scalars().all()
    return [_serialize(e) for e in entries]


@router.get("/{project_id}/store-metadata/locales")
async def get_configured_locales(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Proje için yapılandırılmış dil/platform kombinasyonlarını listeler.

    Hangi locale'lerin hangi platformlar için tanımlı olduğunu ve
    desteklenen tüm locale listesini döndürür.

    Raises:
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
    """
    await _verify_project_ownership(db, project_id, current_user["id"])
    result = await db.execute(
        select(StoreMetadata.locale, StoreMetadata.platform)
        .where(StoreMetadata.project_id == project_id)
        .distinct()
    )
    rows = result.all()
    configured = {}
    for locale, platform in rows:
        if locale not in configured:
            configured[locale] = []
        configured[locale].append(platform)
    return {
        "configured": configured,
        "supported": SUPPORTED_LOCALES,
    }


@router.put("/{project_id}/store-metadata/{platform}")
async def upsert_store_metadata(
    project_id: str,
    platform: str,
    req: StoreMetadataUpsert,
    locale: str = Query("en-US"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mağaza metadata'sını oluşturur veya günceller (upsert).

    Platform, locale ve proje kombinasyonu için metadata kaydı yoksa oluşturur,
    varsa sadece gönderilen alanları günceller. 24 desteklenen locale mevcuttur.

    Raises:
        400: Geçersiz platform veya desteklenmeyen locale
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
    """
    if platform not in ("android", "ios"):
        raise HTTPException(status_code=400, detail="Platform must be 'android' or 'ios'")
    if locale not in SUPPORTED_LOCALES:
        raise HTTPException(status_code=400, detail=f"Unsupported locale: {locale}")
    await _verify_project_ownership(db, project_id, current_user["id"])

    result = await db.execute(
        select(StoreMetadata).where(
            StoreMetadata.project_id == project_id,
            StoreMetadata.platform == platform,
            StoreMetadata.locale == locale,
        )
    )
    meta = result.scalar_one_or_none()

    if meta:
        for field, value in req.model_dump(exclude_unset=True).items():
            setattr(meta, field, value)
        meta.updated_at = datetime.utcnow()
    else:
        meta = StoreMetadata(
            project_id=project_id,
            platform=platform,
            locale=locale,
            **req.model_dump(exclude_unset=True),
        )
        db.add(meta)

    await db.commit()
    await db.refresh(meta)
    return _serialize(meta)


@router.post("/{project_id}/store-metadata/{platform}/icon")
async def update_icon_url(
    project_id: str,
    platform: str,
    req: dict,
    locale: str = Query("en-US"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Uygulama ikonunun URL'sini günceller.

    Metadata kaydı yoksa otomatik oluşturulur. iOS için 1024x1024px,
    Android için 512x512px PNG formatı önerilir.

    Raises:
        400: Geçersiz platform
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
    """
    if platform not in ("android", "ios"):
        raise HTTPException(status_code=400, detail="Platform must be 'android' or 'ios'")
    await _verify_project_ownership(db, project_id, current_user["id"])

    result = await db.execute(
        select(StoreMetadata).where(
            StoreMetadata.project_id == project_id,
            StoreMetadata.platform == platform,
            StoreMetadata.locale == locale,
        )
    )
    meta = result.scalar_one_or_none()
    if not meta:
        meta = StoreMetadata(project_id=project_id, platform=platform, locale=locale)
        db.add(meta)

    meta.icon_url = req.get("icon_url", "")
    meta.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(meta)
    return _serialize(meta)


@router.post("/{project_id}/store-metadata/{platform}/screenshots")
async def update_screenshots(
    project_id: str,
    platform: str,
    req: dict,
    locale: str = Query("en-US"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ekran görüntülerini günceller.

    Metadata kaydı yoksa otomatik oluşturulur. Platform'a göre farklı
    cihaz boyutları desteklenir (iPhone, iPad, telefon, tablet).

    Raises:
        400: Geçersiz platform
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
    """
    if platform not in ("android", "ios"):
        raise HTTPException(status_code=400, detail="Platform must be 'android' or 'ios'")
    await _verify_project_ownership(db, project_id, current_user["id"])

    result = await db.execute(
        select(StoreMetadata).where(
            StoreMetadata.project_id == project_id,
            StoreMetadata.platform == platform,
            StoreMetadata.locale == locale,
        )
    )
    meta = result.scalar_one_or_none()
    if not meta:
        meta = StoreMetadata(project_id=project_id, platform=platform, locale=locale)
        db.add(meta)

    meta.screenshots = req.get("screenshots", {})
    meta.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(meta)
    return _serialize(meta)


def _validate_icon(platform: str, icon_url: str | None) -> list[dict]:
    issues = []
    spec = ICON_SPECS.get(platform, {})
    if not icon_url:
        issues.append({
            "field": "icon",
            "severity": "error",
            "message": f"App icon is required ({spec.get('width')}x{spec.get('height')}px {spec.get('format')})",
            "spec": spec,
        })
    else:
        if not icon_url.lower().endswith((".png", ".webp")):
            issues.append({
                "field": "icon",
                "severity": "warning",
                "message": f"Icon should be {spec.get('format')} format for best compatibility",
                "spec": spec,
            })
    return issues


def _validate_screenshots(platform: str, screenshots: dict | None) -> list[dict]:
    issues = []
    specs = SCREENSHOT_SPECS.get(platform, {})
    phone_shots = (screenshots or {}).get("phone", [])

    min_required = 2
    max_allowed = 10 if platform == "ios" else 8
    if len(phone_shots) < min_required:
        issues.append({
            "field": "screenshots",
            "severity": "error",
            "message": f"Minimum {min_required} phone screenshots required (currently {len(phone_shots)})",
        })
    if len(phone_shots) > max_allowed:
        issues.append({
            "field": "screenshots",
            "severity": "error",
            "message": f"Maximum {max_allowed} screenshots allowed (currently {len(phone_shots)})",
        })

    for key, spec in specs.items():
        if spec.get("required") and key not in (screenshots or {}):
            if key != "phone":
                issues.append({
                    "field": f"screenshots.{key}",
                    "severity": "warning",
                    "message": f"{spec['label']} screenshots recommended ({spec['width']}x{spec['height']}px)",
                })
    return issues


def _validate_metadata(platform: str, meta: StoreMetadata | None) -> list[dict]:
    issues = []
    if not meta:
        return [{"field": "metadata", "severity": "error", "message": "No metadata configured for this platform"}]

    if not meta.app_name or len(meta.app_name.strip()) == 0:
        issues.append({"field": "app_name", "severity": "error", "message": "App name is required"})
    elif len(meta.app_name) > 30 and platform == "ios":
        issues.append({"field": "app_name", "severity": "warning", "message": "iOS app names over 30 chars may be truncated"})

    if not meta.bundle_id:
        issues.append({"field": "bundle_id", "severity": "error", "message": "Bundle ID / Package name is required"})
    elif not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$", meta.bundle_id):
        issues.append({"field": "bundle_id", "severity": "error", "message": "Invalid bundle ID format (e.g., com.company.app)"})

    if not meta.full_description:
        issues.append({"field": "full_description", "severity": "error", "message": "Full description is required"})
    elif len(meta.full_description) < 80:
        issues.append({"field": "full_description", "severity": "warning", "message": "Description under 80 chars hurts discoverability"})

    if not meta.short_description:
        issues.append({"field": "short_description", "severity": "warning", "message": "Short description / subtitle improves conversion"})

    if not meta.privacy_url:
        issues.append({"field": "privacy_url", "severity": "error", "message": "Privacy policy URL is required by both stores"})
    elif not meta.privacy_url.startswith("https://"):
        issues.append({"field": "privacy_url", "severity": "error", "message": "Privacy URL must use HTTPS"})

    if not meta.category:
        issues.append({"field": "category", "severity": "warning", "message": "Category improves store discoverability"})

    if platform == "ios" and (not meta.keywords or len(meta.keywords.strip()) == 0):
        issues.append({"field": "keywords", "severity": "warning", "message": "Keywords are important for App Store search ranking"})

    if platform == "android" and not meta.feature_graphic_url:
        issues.append({"field": "feature_graphic", "severity": "warning", "message": "Feature graphic (1024x500) recommended for Google Play"})

    return issues


@router.get("/{project_id}/store-metadata/{platform}/compliance")
async def check_store_compliance(
    project_id: str,
    platform: str,
    locale: str = Query("en-US"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mağaza uyumluluk kontrolü yapar.

    Metadata, ikon ve ekran görüntülerini mağaza gereksinimlerine göre doğrular.
    Hata ve uyarıları ayrı listeler, hazırlık skoru (0-100) ve yayın hazırlığı durumu döndürür.

    Raises:
        400: Geçersiz platform
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
    """
    if platform not in ("android", "ios"):
        raise HTTPException(status_code=400, detail="Platform must be 'android' or 'ios'")
    await _verify_project_ownership(db, project_id, current_user["id"])

    result = await db.execute(
        select(StoreMetadata).where(
            StoreMetadata.project_id == project_id,
            StoreMetadata.platform == platform,
            StoreMetadata.locale == locale,
        )
    )
    meta = result.scalar_one_or_none()

    issues = []
    issues.extend(_validate_metadata(platform, meta))
    issues.extend(_validate_icon(platform, meta.icon_url if meta else None))
    issues.extend(_validate_screenshots(platform, meta.screenshots if meta else None))

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]

    ready = len(errors) == 0
    score = max(0, 100 - (len(errors) * 15) - (len(warnings) * 5))

    return {
        "ready": ready,
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "platform": platform,
        "locale": locale,
        "icon_spec": ICON_SPECS.get(platform),
        "screenshot_specs": SCREENSHOT_SPECS.get(platform),
    }


@router.get("/{project_id}/store-metadata/{platform}/simulate-review")
async def simulate_store_review(
    project_id: str,
    platform: str,
    locale: str = Query("en-US"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mağaza inceleme sürecini simüle eder.

    App name, bundle ID, gizlilik politikası, ikon, screenshot ve açıklama kontrolü yapar.
    Tahmini onay süresi ve olası red/onay/iyileştirme gerekli kararını döndürür.

    Raises:
        400: Geçersiz platform
        401: Kimlik doğrulama gerekli
        404: Proje bulunamadı veya erişim yetkisi yok
    """
    if platform not in ("android", "ios"):
        raise HTTPException(status_code=400, detail="Platform must be 'android' or 'ios'")
    await _verify_project_ownership(db, project_id, current_user["id"])

    result = await db.execute(
        select(StoreMetadata).where(
            StoreMetadata.project_id == project_id,
            StoreMetadata.platform == platform,
            StoreMetadata.locale == locale,
        )
    )
    meta = result.scalar_one_or_none()

    checks = []

    checks.append({
        "check": "App Name",
        "status": "pass" if meta and meta.app_name else "fail",
        "detail": meta.app_name if meta and meta.app_name else "Missing",
    })
    checks.append({
        "check": "Bundle ID",
        "status": "pass" if meta and meta.bundle_id else "fail",
        "detail": meta.bundle_id if meta and meta.bundle_id else "Missing",
    })
    checks.append({
        "check": "Privacy Policy",
        "status": "pass" if meta and meta.privacy_url and meta.privacy_url.startswith("https://") else "fail",
        "detail": "Valid HTTPS URL" if meta and meta.privacy_url and meta.privacy_url.startswith("https://") else "Missing or not HTTPS",
    })
    checks.append({
        "check": "App Icon",
        "status": "pass" if meta and meta.icon_url else "fail",
        "detail": "Uploaded" if meta and meta.icon_url else "Missing",
    })

    phone_count = len((meta.screenshots or {}).get("phone", [])) if meta else 0
    checks.append({
        "check": "Screenshots",
        "status": "pass" if phone_count >= 2 else "fail",
        "detail": f"{phone_count} phone screenshots" if phone_count > 0 else "No screenshots",
    })
    checks.append({
        "check": "Description",
        "status": "pass" if meta and meta.full_description and len(meta.full_description) >= 80 else "warning" if meta and meta.full_description else "fail",
        "detail": f"{len(meta.full_description)} chars" if meta and meta.full_description else "Missing",
    })
    checks.append({
        "check": "Category",
        "status": "pass" if meta and meta.category else "warning",
        "detail": meta.category if meta and meta.category else "Not selected",
    })

    if platform == "ios":
        checks.append({
            "check": "Keywords",
            "status": "pass" if meta and meta.keywords else "warning",
            "detail": f"{len(meta.keywords)} chars" if meta and meta.keywords else "Empty",
        })

    if platform == "android":
        checks.append({
            "check": "Feature Graphic",
            "status": "pass" if meta and meta.feature_graphic_url else "warning",
            "detail": "Uploaded" if meta and meta.feature_graphic_url else "Missing (recommended)",
        })

    pass_count = sum(1 for c in checks if c["status"] == "pass")
    fail_count = sum(1 for c in checks if c["status"] == "fail")
    total = len(checks)

    if fail_count > 0:
        verdict = "likely_rejected"
        estimated_time = None
    elif pass_count == total:
        verdict = "likely_approved"
        estimated_time = "1-3 days" if platform == "ios" else "2-7 days (first submission) or hours (updates)"
    else:
        verdict = "needs_improvement"
        estimated_time = "3-7 days" if platform == "ios" else "2-7 days"

    return {
        "verdict": verdict,
        "checks": checks,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "total": total,
        "estimated_review_time": estimated_time,
        "platform": platform,
        "locale": locale,
    }
