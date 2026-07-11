"""Staged rollout router — kademeli yayın başlat / ilerlet / durdur / durum.

State machine (sonraki yüzde) burada; store API yazımı store-deploy executor'ında.
Ownership: rollout → project.owner_id. Health auto-halt poller tarafında (rollout_poller).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Build, Project, Deployment, ReleaseRollout, ReleaseHealthSample
from app.routers.credentials import get_user_credential
from app import events
from app.event_crypto import pack_secrets
from app.rollout_poller import POLL_INTERVAL

logger = logging.getLogger(__name__)
router = APIRouter()

# Rollout yüzde adımları (Android). Apple sabit programı sürer, bu adımlar bilgi amaçlı.
ROLLOUT_STEPS = [0.01, 0.1, 0.5, 1.0]


def next_fraction(current: float) -> float:
    """Mevcut orandan bir sonraki adım. %100'de kalır."""
    for step in ROLLOUT_STEPS:
        if step > current + 1e-9:
            return step
    return 1.0


class RolloutDeployRequest(BaseModel):
    target: str = "google_play"
    track: str = "production"
    package_name: str = ""
    start_fraction: float = 0.01
    auto_halt: bool = True
    crash_free_threshold: float = 0.99
    min_users: int = 1000


async def _load_owned_rollout(db: AsyncSession, rollout_id: str, user_id: str) -> ReleaseRollout:
    rollout = (await db.execute(
        select(ReleaseRollout).where(ReleaseRollout.id == rollout_id))).scalar_one_or_none()
    if not rollout:
        raise HTTPException(status_code=404, detail="Rollout not found")
    project = (await db.execute(
        select(Project).where(Project.id == rollout.project_id))).scalar_one_or_none()
    if not project or project.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Rollout not found")
    return rollout


def _serialize(rollout: ReleaseRollout, samples: list[ReleaseHealthSample] | None = None) -> dict:
    data = {
        "id": rollout.id,
        "deployment_id": rollout.deployment_id,
        "project_id": rollout.project_id,
        "platform": rollout.platform,
        "package_name": rollout.package_name,
        "track": rollout.track,
        "current_fraction": rollout.current_fraction,
        "state": rollout.state,
        "auto_halt_enabled": rollout.auto_halt_enabled,
        "crash_free_threshold": rollout.crash_free_threshold,
        "baseline_crash_free": rollout.baseline_crash_free,
        "min_users": rollout.min_users,
        "halted_reason": rollout.halted_reason,
        "last_error": rollout.last_error,
        "release_version": rollout.release_version,
        "next_fraction": next_fraction(rollout.current_fraction),
    }
    if samples is not None:
        # Sağlık sinyalinin canlılığı — "auto-halt sessizce ölü" durumunu görünür kılar.
        if not rollout.auto_halt_enabled:
            health = "disabled"
        elif not samples:
            health = "no_data"
        else:
            from datetime import datetime as _dt
            last = samples[-1].sampled_at
            age = (_dt.utcnow() - last).total_seconds() if last else 1e9
            health = "stale" if age > 3 * POLL_INTERVAL else "ok"
        data["health_status"] = health
    if samples is not None:
        data["samples"] = [{
            "sampled_at": s.sampled_at.isoformat() if s.sampled_at else None,
            "crash_free_rate": s.crash_free_rate,
            "anr_rate": s.anr_rate,
            "distinct_users": s.distinct_users,
            "adoption": s.adoption,
        } for s in samples]
    return data


@router.post("/deploy/{build_id}")
async def start_rollout(
    build_id: str,
    req: RolloutDeployRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Başarılı bir build için kademeli (staged) yayın başlatır."""
    build = (await db.execute(select(Build).where(Build.id == build_id))).scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    project = (await db.execute(
        select(Project).where(Project.id == build.project_id))).scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Build not found")
    if build.status != "success" or not build.artifact_url:
        raise HTTPException(status_code=400, detail="Build is not ready for deployment.")
    if req.target not in ("google_play", "app_store"):
        raise HTTPException(status_code=400, detail="Staged rollout only supports google_play or app_store.")
    if not req.package_name.strip():
        raise HTTPException(status_code=400, detail="package_name zorunlu — halt/health bu kimlikle çalışır.")
    if not (0.0 < req.start_fraction <= 1.0) or not (0.0 < req.crash_free_threshold <= 1.0) or req.min_users < 0:
        raise HTTPException(status_code=400, detail="Geçersiz rollout parametreleri (0<fraction≤1, 0<threshold≤1, min_users≥0).")
    # Aynı proje+platformda ikinci aktif rollout store edit çakışması yaratır.
    existing = (await db.execute(select(ReleaseRollout).where(
        ReleaseRollout.project_id == project.id, ReleaseRollout.platform == req.target,
        ReleaseRollout.state == "in_progress"))).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="Bu proje+platformda zaten aktif bir rollout var.")

    # Android: Play Reporting her zaman mevcut (deploy creds ile).
    # iOS: yalnızca kullanıcı Sentry bağladıysa auto-halt açılabilir.
    auto_halt = req.auto_halt and req.target == "google_play"
    if req.auto_halt and req.target == "app_store":
        sentry_ok = all([
            await get_user_credential(db, current_user["id"], "sentry", "SENTRY_AUTH_TOKEN"),
            await get_user_credential(db, current_user["id"], "sentry", "SENTRY_ORG_SLUG"),
            await get_user_credential(db, current_user["id"], "sentry", "SENTRY_PROJECT_SLUG"),
        ])
        auto_halt = sentry_ok

    dep = Deployment(build_id=build_id, target=req.target, track=req.track)
    db.add(dep)
    await db.flush()
    rollout = ReleaseRollout(
        deployment_id=dep.id, project_id=project.id, platform=req.target,
        package_name=req.package_name, track=req.track,
        current_fraction=req.start_fraction, state="in_progress",
        auto_halt_enabled=auto_halt, crash_free_threshold=req.crash_free_threshold,
        min_users=req.min_users,
    )
    db.add(rollout)
    await db.commit()
    await db.refresh(rollout)

    payload = {
        "deployment_id": dep.id, "rollout_id": rollout.id, "build_id": build_id,
        "owner_id": project.owner_id, "target": req.target, "track": req.track,
        "artifact_url": build.artifact_url,
        "artifact_checksum": getattr(build, "artifact_checksum", None),
        "package_name": req.package_name, "rollout": True, "start_fraction": req.start_fraction,
    }
    if req.target == "google_play":
        key_json = await get_user_credential(db, current_user["id"], "google_play", "GOOGLE_PLAY_KEY_JSON")
        if not key_json:
            raise HTTPException(status_code=400, detail="Google Play service account key eksik — Settings > Credentials.")
        payload = pack_secrets(payload, {"google_play_key_json": key_json})
    else:
        asc = {
            "app_store_key_id": await get_user_credential(db, current_user["id"], "app_store", "APP_STORE_KEY_ID"),
            "app_store_issuer_id": await get_user_credential(db, current_user["id"], "app_store", "APP_STORE_ISSUER_ID"),
            "app_store_private_key": await get_user_credential(db, current_user["id"], "app_store", "APP_STORE_PRIVATE_KEY"),
        }
        if not all(asc.values()):
            raise HTTPException(status_code=400, detail="App Store Connect API anahtarları eksik — Settings > Credentials.")
        payload = pack_secrets(payload, asc)

    ok = await events.publish_event("deploy.triggered", payload)
    if not ok:
        rollout.state = "failed"
        rollout.last_error = "deploy.triggered yayınlanamadı (RabbitMQ)"
        await db.commit()
        raise HTTPException(status_code=502, detail="Deploy kuyruğa yazılamadı — tekrar deneyin.")
    return _serialize(rollout)


@router.post("/{rollout_id}/advance")
async def advance_rollout(
    rollout_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rollout'u bir sonraki yüzdeye ilerlet (%100'de tamamlar). Yalnız google_play."""
    rollout = await _load_owned_rollout(db, rollout_id, current_user["id"])
    if rollout.state not in ("in_progress",):
        raise HTTPException(status_code=400, detail=f"Cannot advance a rollout in state '{rollout.state}'.")
    if rollout.platform != "google_play":
        raise HTTPException(status_code=400, detail="Manual advance is only for Google Play (Apple sürer).")

    key_json = await get_user_credential(db, current_user["id"], "google_play", "GOOGLE_PLAY_KEY_JSON")
    if not key_json:
        raise HTTPException(status_code=400, detail="Google Play service account key eksik — Settings > Credentials.")

    prev_fraction = rollout.current_fraction
    target_fraction = next_fraction(rollout.current_fraction)
    complete = target_fraction >= 1.0
    rollout.current_fraction = target_fraction
    if complete:
        rollout.state = "completed"
    rollout.last_error = None
    await db.commit()

    payload = pack_secrets({
        "rollout_id": rollout.id, "target": rollout.platform,
        "package_name": rollout.package_name,
        "track": rollout.track, "fraction": target_fraction, "complete": complete,
        "prev_fraction": prev_fraction, "prev_state": "in_progress",
    }, {"google_play_key_json": key_json})
    ok = await events.publish_event("rollout.set", payload)
    if not ok:
        # Store'a hiç gitmedi — iyimser güncellemeyi geri al.
        rollout.current_fraction = prev_fraction
        rollout.state = "in_progress"
        rollout.last_error = "rollout.set yayınlanamadı (RabbitMQ)"
        await db.commit()
        raise HTTPException(status_code=502, detail="İlerletme kuyruğa yazılamadı — tekrar deneyin.")
    return _serialize(rollout)


@router.post("/{rollout_id}/halt")
async def halt_rollout(
    rollout_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rollout'u manuel durdur — Google `halted`, Apple phased release `PAUSED`."""
    rollout = await _load_owned_rollout(db, rollout_id, current_user["id"])
    if rollout.state not in ("in_progress", "paused"):
        raise HTTPException(status_code=400, detail=f"Cannot halt a rollout in state '{rollout.state}'.")
    prev_state = rollout.state
    rollout.state = "halted"
    rollout.halted_reason = "Manuel olarak durduruldu"
    rollout.last_error = None
    await db.commit()

    payload = {
        "rollout_id": rollout.id, "target": rollout.platform,
        "package_name": rollout.package_name, "track": rollout.track,
        "reason": rollout.halted_reason, "external_ref": rollout.external_ref,
        "prev_state": prev_state,
    }
    if rollout.platform == "google_play":
        key_json = await get_user_credential(db, current_user["id"], "google_play", "GOOGLE_PLAY_KEY_JSON")
        payload = pack_secrets(payload, {"google_play_key_json": key_json})
    else:
        payload = pack_secrets(payload, {
            "app_store_key_id": await get_user_credential(db, current_user["id"], "app_store", "APP_STORE_KEY_ID"),
            "app_store_issuer_id": await get_user_credential(db, current_user["id"], "app_store", "APP_STORE_ISSUER_ID"),
            "app_store_private_key": await get_user_credential(db, current_user["id"], "app_store", "APP_STORE_PRIVATE_KEY"),
        })
    ok = await events.publish_event("rollout.halt", payload)
    if not ok:
        rollout.state = prev_state
        rollout.last_error = "rollout.halt yayınlanamadı (RabbitMQ) — rollout store'da hâlâ AKTİF"
        await db.commit()
        raise HTTPException(status_code=502, detail="Durdurma kuyruğa yazılamadı — rollout hâlâ aktif! Tekrar deneyin.")
    return _serialize(rollout)


@router.get("/by-build/{build_id}")
async def rollout_by_build(
    build_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bir build'in en güncel rollout'unu döndür (yoksa null)."""
    build = (await db.execute(select(Build).where(Build.id == build_id))).scalar_one_or_none()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    project = (await db.execute(
        select(Project).where(Project.id == build.project_id))).scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Build not found")
    rollout = (await db.execute(
        select(ReleaseRollout).join(Deployment, ReleaseRollout.deployment_id == Deployment.id)
        .where(Deployment.build_id == build_id)
        .order_by(desc(ReleaseRollout.created_at)))).scalars().first()
    if not rollout:
        return None
    samples = (await db.execute(
        select(ReleaseHealthSample).where(ReleaseHealthSample.rollout_id == rollout.id)
        .order_by(ReleaseHealthSample.sampled_at))).scalars().all()
    return _serialize(rollout, samples)


@router.get("/by-project/{project_id}/active")
async def active_rollout_by_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Projenin en güncel *canlı* rollout'unu döndür (yoksa null).

    Rollout, deploy edilen build'e bağlıdır; ama panel proje detayında
    "en son başarılı build"e kilitliydi. iOS build'i en yeni başarılıyken
    Android build'e açılmış bir rollout görünmez kalıyordu. Bu uç-nokta
    rollout'u build'den bağımsız, proje düzeyinde yüzeye çıkarır.
    Terminal durumlar (completed) hariç — biten rollout yeni yayın başlatmayı engellemesin.
    """
    project = (await db.execute(
        select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    rollout = (await db.execute(
        select(ReleaseRollout).join(Deployment, ReleaseRollout.deployment_id == Deployment.id)
        .join(Build, Deployment.build_id == Build.id)
        .where(Build.project_id == project_id)
        .where(ReleaseRollout.state != "completed")
        .order_by(desc(ReleaseRollout.created_at)))).scalars().first()
    if not rollout:
        return None
    samples = (await db.execute(
        select(ReleaseHealthSample).where(ReleaseHealthSample.rollout_id == rollout.id)
        .order_by(ReleaseHealthSample.sampled_at))).scalars().all()
    return _serialize(rollout, samples)


@router.get("/{rollout_id}")
async def get_rollout(
    rollout_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rollout durumu + son sağlık örnekleri (dashboard grafiği)."""
    rollout = await _load_owned_rollout(db, rollout_id, current_user["id"])
    samples = (await db.execute(
        select(ReleaseHealthSample).where(ReleaseHealthSample.rollout_id == rollout.id)
        .order_by(ReleaseHealthSample.sampled_at))).scalars().all()
    return _serialize(rollout, samples)
