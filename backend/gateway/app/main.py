import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram
from app.limiter import limiter
from app.tracing import TracingMiddleware
from app.request_guard import RequestSizeGuardMiddleware
from app.tenant_middleware import TenantIsolationMiddleware
from app.logging_config import setup_logging
from app.routers import auth, projects, builds, deployments, credentials, github, preview, webhooks, audit, flags, usage
from app.routers import quotas as quotas_router
from app.routers import secrets, rbac, immutable_audit, deploy_policies, backups
from app.routers import ota
from app.routers import admin as admin_router
from app.routers import billing as billing_router
from app.routers import credential_validation, deploy_simulator, metrics_kpi, canary, compliance
from app.routers import build_diagnosis, cost_prediction, provider_recommendation
from app.routers import store_metadata
from app.routers import auto_signing as auto_signing_router
from app.routers import support as support_router
from app.routers import organizations as organizations_router
from app.routers import sso as sso_router
from app.routers import notifications as notifications_router
from app.routers import incidents as incidents_router
from app.routers import releases as releases_router
from app.routers import cache as cache_router
from app.routers import crash_reporting as crash_reporting_router
from app.ws import router as ws_router
import time as _time
from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app import events

_START_TIME = _time.time()
from app.worker import start_event_worker
from app.cleanup import cleanup_stale_builds
from app.webhook_guard import cleanup_expired_nonces
from app.waf import WAFMiddleware
from app.notification_worker import start_notification_worker

setup_logging(level="INFO", json_output=True)
logger = logging.getLogger(__name__)

BUILD_TRIGGER_COUNTER = Counter(
    "apptrack_builds_triggered_total",
    "Total build triggers",
    ["framework", "provider", "platform"],
)
BUILD_RESULT_COUNTER = Counter(
    "apptrack_builds_completed_total",
    "Total build completions",
    ["status", "provider"],
)
DEPLOY_TRIGGER_COUNTER = Counter(
    "apptrack_deploys_triggered_total",
    "Total deploy triggers",
    ["target"],
)
DEPLOY_RESULT_COUNTER = Counter(
    "apptrack_deploys_completed_total",
    "Total deploy completions",
    ["target", "status"],
)
BUILD_DURATION = Histogram(
    "apptrack_build_duration_seconds",
    "Build duration in seconds",
    ["provider"],
    buckets=[30, 60, 120, 300, 600, 1200, 1800, 3600],
)
WEBHOOK_COUNTER = Counter(
    "apptrack_webhooks_received_total",
    "Total webhooks received",
    ["source", "status"],
)
QUOTA_EXCEEDED_COUNTER = Counter(
    "apptrack_quota_exceeded_total",
    "Total quota limit hits",
    ["resource", "plan"],
)
ARTIFACT_SIZE = Histogram(
    "apptrack_artifact_size_bytes",
    "Artifact file sizes",
    ["provider"],
    buckets=[1e6, 5e6, 10e6, 50e6, 100e6, 200e6, 500e6],
)
AUTH_FAILURE_COUNTER = Counter(
    "apptrack_auth_failures_total",
    "Total authentication failures",
    ["reason"],
)
DEPLOY_FAILURE_COUNTER = Counter(
    "apptrack_deploy_failures_total",
    "Total deploy failures",
    ["target", "reason"],
)
WEBHOOK_SIGNATURE_FAILURE = Counter(
    "apptrack_webhook_signature_failures_total",
    "Total webhook signature verification failures",
    ["source"],
)
REQUEST_SIZE_REJECTED = Counter(
    "apptrack_request_size_rejected_total",
    "Requests rejected due to size limit",
)
IDEMPOTENCY_DUPLICATE = Counter(
    "apptrack_idempotency_duplicates_total",
    "Total duplicate requests caught by idempotency",
    ["endpoint"],
)
SERVICE_AUTH_FAILURE = Counter(
    "apptrack_service_auth_failures_total",
    "Total service-to-service auth failures",
    ["service"],
)

_worker_conn = None
_background_tasks: dict[str, asyncio.Task] = {}
_shutdown_event = asyncio.Event()


async def _check_db() -> bool:
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _check_rabbitmq() -> bool:
    try:
        import aio_pika
        conn = await aio_pika.connect_robust(settings.RABBITMQ_URL, timeout=3)
        await conn.close()
        return True
    except Exception:
        return False


async def _check_redis() -> bool:
    try:
        if not settings.REDIS_URL:
            return False
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, socket_timeout=3)
        await r.ping()
        await r.aclose()
        return True
    except Exception:
        return False


async def _check_service(url: str) -> bool:
    """Check if a microservice is reachable via its /health endpoint."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{url}/health")
            return resp.status_code < 500
    except Exception:
        return False


async def _credential_rotation_checker() -> None:
    """Her 24 saatte bir expiry yaklaşan credential'ları kontrol eder."""
    import asyncio as _asyncio
    while True:
        try:
            await _asyncio.sleep(24 * 3600)  # 24 saatte bir çalış
            async with AsyncSessionLocal() as db:
                from app.models import Credential
                from sqlalchemy import select as _select
                threshold = datetime.utcnow() + timedelta(days=7)
                result = await db.execute(
                    _select(Credential).where(
                        Credential.rotation_due_at != None,
                        Credential.rotation_due_at <= threshold,
                        Credential.rotation_due_at > datetime.utcnow(),
                    )
                )
                for cred in result.scalars():
                    logger.warning(
                        "Credential rotation due soon: user_id=%s provider=%s key=%s due=%s",
                        cred.owner_id, cred.provider, cred.key_name,
                        cred.rotation_due_at.isoformat() if cred.rotation_due_at else "N/A"
                    )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Credential rotation checker error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_conn
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        _worker_conn = await start_event_worker()
        logger.info("Event worker started")
    except Exception as exc:
        logger.warning("Event worker unavailable: %s", exc)

    try:
        import aio_pika
        notif_conn = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        notif_channel = await notif_conn.channel()
        await start_notification_worker(notif_channel)
        logger.info("Notification worker started")
    except Exception as exc:
        logger.warning("Notification worker unavailable: %s", exc)

    _background_tasks["stale_build_cleanup"] = asyncio.create_task(cleanup_stale_builds())
    logger.info("Stale build cleanup task started")

    _background_tasks["nonce_cleanup"] = asyncio.create_task(cleanup_expired_nonces())
    logger.info("Webhook nonce cleanup task started")

    _background_tasks["credential_rotation"] = asyncio.create_task(_credential_rotation_checker())
    logger.info("Credential rotation checker task started")

    logger.info("AppTrack gateway started (v0.9.0)")
    yield

    logger.info("Shutting down gracefully...")
    _shutdown_event.set()
    for task_name, task in _background_tasks.items():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Background task %s cancelled", task_name)
    _background_tasks.clear()
    await events.close_connection()
    if _worker_conn:
        await _worker_conn.close()
    await engine.dispose()
    logger.info("Gateway shutdown complete")


app = FastAPI(
    title="AppTrack API Gateway",
    description="Mobil uygulama CI/CD ve Store yönetim platformu. Build tetikleme, artifact yönetimi, Google Play / App Store deploy, RBAC, SSO ve organizasyon yönetimi.",
    version="0.9.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth", "description": "Kimlik doğrulama — kayıt, giriş, GitHub OAuth, token yenileme"},
        {"name": "projects", "description": "Proje CRUD, repo sync, build tetikleme, deploy"},
        {"name": "builds", "description": "Build listeleme, iptal, yeniden deneme, maliyet tahmini"},
        {"name": "deployments", "description": "Store deploy tetikleme ve takibi"},
        {"name": "credentials", "description": "Şifreli credential (API key, token) yönetimi"},
        {"name": "github", "description": "GitHub repo listeleme ve branch bilgisi"},
        {"name": "preview", "description": "Canlı önizleme container yönetimi"},
        {"name": "webhooks", "description": "GitHub, EAS ve Codemagic webhook alıcıları"},
        {"name": "audit", "description": "Audit log sorgulama ve filtreleme"},
        {"name": "feature-flags", "description": "Feature flag oluşturma, toggle ve değerlendirme"},
        {"name": "usage", "description": "Kullanım istatistikleri ve kota takibi"},
        {"name": "ota-updates", "description": "OTA güncellemeleri — EAS ve custom bundle"},
        {"name": "store-metadata", "description": "Store listing metadata, icon ve screenshot yönetimi"},
        {"name": "secrets", "description": "Secret yönetimi ve şifreleme"},
        {"name": "rbac", "description": "Rol bazlı erişim kontrolü — rol atama ve izin yönetimi"},
        {"name": "immutable-audit", "description": "Değiştirilemez audit log — hash chain ile bütünlük garantisi"},
        {"name": "deploy-policies", "description": "Deploy politikaları — branch, zaman ve onay kuralları"},
        {"name": "backups", "description": "Veritabanı backup yönetimi"},
        {"name": "admin", "description": "Admin paneli — kullanıcı yönetimi ve sistem istatistikleri"},
        {"name": "billing", "description": "Abonelik planları, ödeme ve fatura yönetimi"},
        {"name": "credential-validation", "description": "Credential doğrulama — API key/token geçerlilik kontrolü"},
        {"name": "deploy-simulator", "description": "Deploy simülasyonu — pre-publish kontrolleri"},
        {"name": "metrics-kpi", "description": "KPI metrikleri — build/deploy başarı oranları, trendler"},
        {"name": "canary", "description": "Canary deploy — kademeli yayınlama ve geri alma"},
        {"name": "compliance", "description": "Uyumluluk kontrolleri — store gereksinimleri doğrulama"},
        {"name": "support", "description": "Destek talebi oluşturma ve takibi"},
        {"name": "organizations", "description": "Organizasyon yönetimi — üye davet, rol atama"},
        {"name": "sso", "description": "SSO/OIDC yapılandırma ve kimlik doğrulama"},
        {"name": "build-diagnosis", "description": "Build hata tanılama — otomatik analiz ve çözüm önerisi"},
        {"name": "cost-prediction", "description": "Build maliyet tahmini — geçmiş veriye dayalı projeksiyon"},
        {"name": "provider-recommendation", "description": "CI provider önerisi — performans ve maliyet analizi"},
        {"name": "notifications", "description": "Bildirim yönetimi — CRUD, tercihleri, okundu işaretleme"},
        {"name": "incidents", "description": "Status page olayları — incident ve güncelleme yönetimi"},
        {"name": "releases", "description": "Release notes — otomatik üretim ve düzenleme"},
        {"name": "build-cache", "description": "Build cache yönetimi — cache bilgisi, temizleme"},
        {"name": "crash-reporting", "description": "Crash reporting — Sentry entegrasyonu, crash stats, release"},
    ],
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(WAFMiddleware)
app.add_middleware(TracingMiddleware)
app.add_middleware(RequestSizeGuardMiddleware)
app.add_middleware(TenantIsolationMiddleware)

ALLOWED_ORIGINS = settings.CORS_ORIGINS if settings.CORS_ORIGINS != ["*"] else ["http://localhost:3000", "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-Id", "X-Idempotency-Key", "X-Service-Token"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later.", "retry_after": str(exc.retry_after)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", "unknown")
    logger.error("Unhandled error trace_id=%s: %s", trace_id, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "trace_id": trace_id},
    )


app.include_router(auth.router,        prefix="/api/auth",        tags=["auth"])
app.include_router(projects.router,    prefix="/api/projects",    tags=["projects"])
app.include_router(builds.router,      prefix="/api/builds",      tags=["builds"])
app.include_router(deployments.router, prefix="/api/deployments", tags=["deployments"])
app.include_router(credentials.router, prefix="/api/credentials", tags=["credentials"])
app.include_router(github.router,      prefix="/api/github",      tags=["github"])
app.include_router(preview.router,     prefix="/api/preview",     tags=["preview"])
app.include_router(webhooks.router,    prefix="/api/webhooks",    tags=["webhooks"])
app.include_router(audit.router,       prefix="/api/audit",       tags=["audit"])
app.include_router(flags.router,       prefix="/api/flags",       tags=["feature-flags"])
app.include_router(usage.router,       prefix="/api/usage",       tags=["usage"])
app.include_router(quotas_router.router, prefix="/api/quotas",    tags=["usage"])
app.include_router(secrets.router,              tags=["secrets"])
app.include_router(rbac.router,                 tags=["rbac"])
app.include_router(immutable_audit.router,      tags=["immutable-audit"])
app.include_router(deploy_policies.router,      tags=["deploy-policies"])
app.include_router(backups.router,              tags=["backups"])
app.include_router(ota.router, prefix="/api/ota", tags=["ota-updates"])
app.include_router(admin_router.router,         tags=["admin"])
app.include_router(billing_router.router,       tags=["billing"])
app.include_router(credential_validation.router, tags=["credential-validation"])
app.include_router(deploy_simulator.router,     tags=["deploy-simulator"])
app.include_router(metrics_kpi.router,          tags=["metrics-kpi"])
app.include_router(canary.router,               tags=["canary"])
app.include_router(compliance.router,           tags=["compliance"])
app.include_router(store_metadata.router, prefix="/api/projects", tags=["store-metadata"])
app.include_router(support_router.router, prefix="/api", tags=["support"])
app.include_router(organizations_router.router, prefix="/api", tags=["organizations"])
app.include_router(sso_router.router, prefix="/api", tags=["sso"])
app.include_router(build_diagnosis.router)
app.include_router(cost_prediction.router)
app.include_router(provider_recommendation.router)
app.include_router(notifications_router.router)
app.include_router(incidents_router.router)
app.include_router(releases_router.router)
app.include_router(cache_router.router)
app.include_router(crash_reporting_router.router)
app.include_router(auto_signing_router.router, prefix="/api/signing", tags=["auto-signing"])
app.include_router(ws_router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "gateway",
        "version": "0.9.0",
        "uptime_seconds": int(_time.time() - _START_TIME),
    }


@app.get("/api/errors/{error_code}")
def get_error_detail(error_code: str):
    from app.error_messages import get_error_message
    return get_error_message(error_code)


@app.get("/api/deploy-errors/{error_code}")
def get_deploy_error_detail(error_code: str):
    from app.deploy_error_guide import get_deploy_error_guide
    return get_deploy_error_guide(error_code)


@app.get("/api/health/deep")
async def deep_health():
    import asyncio as _aio
    db_ok, mq_ok, redis_ok, build_ok, artifact_ok, preview_ok, deploy_ok = await _aio.gather(
        _check_db(),
        _check_rabbitmq(),
        _check_redis(),
        _check_service(settings.BUILD_SERVICE_URL),
        _check_service(settings.ARTIFACT_SERVICE_URL),
        _check_service(settings.PREVIEW_SERVICE_URL),
        _check_service(settings.STORE_DEPLOY_SERVICE_URL),
    )

    services = {
        "database": "healthy" if db_ok else "unhealthy",
        "rabbitmq": "healthy" if mq_ok else "unhealthy",
        "redis": "healthy" if redis_ok else "unhealthy",
        "gateway": "healthy",
        "build_service": "healthy" if build_ok else "unhealthy",
        "artifact_service": "healthy" if artifact_ok else "unhealthy",
        "preview_service": "healthy" if preview_ok else "unhealthy",
        "store_deploy": "healthy" if deploy_ok else "unhealthy",
    }

    unhealthy_count = sum(1 for v in services.values() if v == "unhealthy")
    if unhealthy_count == 0:
        overall = "healthy"
    elif unhealthy_count <= 2:
        overall = "degraded"
    else:
        overall = "unhealthy"

    return JSONResponse(
        status_code=200 if overall == "healthy" else 503,
        content={
            "status": overall,
            "service": "gateway",
            "version": "0.9.0",
            "services": services,
            "checks": {
                "database": "ok" if db_ok else "unreachable",
                "rabbitmq": "ok" if mq_ok else "unreachable",
                "redis": "ok" if redis_ok else "unreachable",
                "build_service": "ok" if build_ok else "unreachable",
                "artifact_service": "ok" if artifact_ok else "unreachable",
                "preview_service": "ok" if preview_ok else "unreachable",
                "store_deploy": "ok" if deploy_ok else "unreachable",
            },
        },
    )


@app.get("/api/monitoring/dashboard")
async def monitoring_dashboard():
    from sqlalchemy import select, func, and_
    from app.models import Build, Deployment, User, Project
    from datetime import datetime, timedelta
    from app.database import AsyncSessionLocal

    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async with AsyncSessionLocal() as db:
        total_builds_24h = (await db.execute(
            select(func.count()).where(Build.created_at >= day_ago)
        )).scalar() or 0
        success_builds_24h = (await db.execute(
            select(func.count()).where(and_(Build.status == "success", Build.created_at >= day_ago))
        )).scalar() or 0
        failed_builds_24h = (await db.execute(
            select(func.count()).where(and_(Build.status == "failed", Build.created_at >= day_ago))
        )).scalar() or 0

        total_deploys_24h = (await db.execute(
            select(func.count()).where(Deployment.created_at >= day_ago)
        )).scalar() or 0
        success_deploys_24h = (await db.execute(
            select(func.count()).where(and_(Deployment.status == "published", Deployment.created_at >= day_ago))
        )).scalar() or 0
        failed_deploys_24h = (await db.execute(
            select(func.count()).where(and_(Deployment.status == "failed", Deployment.created_at >= day_ago))
        )).scalar() or 0

        active_builds = (await db.execute(
            select(func.count()).where(Build.status.in_(["queued", "running"]))
        )).scalar() or 0

        builds_this_month = (await db.execute(
            select(func.count()).where(Build.created_at >= month_start)
        )).scalar() or 0

    build_success_rate = round(success_builds_24h / max(total_builds_24h, 1) * 100, 1)
    deploy_success_rate = round(success_deploys_24h / max(total_deploys_24h, 1) * 100, 1)

    return {
        "timestamp": now.isoformat(),
        "builds": {
            "last_24h": {"total": total_builds_24h, "success": success_builds_24h, "failed": failed_builds_24h},
            "success_rate_24h": build_success_rate,
            "active": active_builds,
            "this_month": builds_this_month,
        },
        "deploys": {
            "last_24h": {"total": total_deploys_24h, "success": success_deploys_24h, "failed": failed_deploys_24h},
            "success_rate_24h": deploy_success_rate,
        },
    }
