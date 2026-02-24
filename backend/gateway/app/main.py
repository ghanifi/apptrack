import asyncio
import logging
from contextlib import asynccontextmanager
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
from app.routers import secrets, rbac, immutable_audit, deploy_policies, backups
from app.config import settings
from app.database import engine, Base
from app import events
from app.worker import start_event_worker
from app.cleanup import cleanup_stale_builds
from app.webhook_guard import cleanup_expired_nonces

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
_cleanup_task = None
_nonce_cleanup_task = None
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_conn, _cleanup_task, _nonce_cleanup_task
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        _worker_conn = await start_event_worker()
        logger.info("Event worker started")
    except Exception as exc:
        logger.warning("Event worker unavailable: %s", exc)

    _cleanup_task = asyncio.create_task(cleanup_stale_builds())
    logger.info("Stale build cleanup task started")

    _nonce_cleanup_task = asyncio.create_task(cleanup_expired_nonces())
    logger.info("Webhook nonce cleanup task started")

    logger.info("AppTrack gateway started (v0.7.0)")
    yield

    logger.info("Shutting down gracefully...")
    _shutdown_event.set()
    for task in [_cleanup_task, _nonce_cleanup_task]:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    await events.close_connection()
    if _worker_conn:
        await _worker_conn.close()
    await engine.dispose()
    logger.info("Gateway shutdown complete")


app = FastAPI(
    title="AppTrack API Gateway",
    version="0.7.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
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
app.include_router(secrets.router)
app.include_router(rbac.router)
app.include_router(immutable_audit.router)
app.include_router(deploy_policies.router)
app.include_router(backups.router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "gateway", "version": "0.7.0"}


@app.get("/api/health/deep")
async def deep_health():
    db_ok = await _check_db()
    mq_ok = await _check_rabbitmq()
    all_ok = db_ok and mq_ok
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "healthy" if all_ok else "degraded",
            "service": "gateway",
            "version": "0.7.0",
            "checks": {
                "database": "ok" if db_ok else "unreachable",
                "rabbitmq": "ok" if mq_ok else "unreachable",
            },
        },
    )
