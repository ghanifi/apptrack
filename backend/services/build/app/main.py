import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from pydantic_settings import BaseSettings
import aio_pika
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    GATEWAY_URL: str = "http://gateway:8000"
    EAS_WEBHOOK_SECRET: str = ""
    CODEMAGIC_WEBHOOK_SECRET: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
_channel: aio_pika.abc.AbstractChannel | None = None


def _verify_hmac(body: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def publish_event(channel: aio_pika.abc.AbstractChannel, routing_key: str, payload: dict) -> None:
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=routing_key,
    )
    logger.info("Published %s", routing_key)


async def _trigger_eas(build_id: str, payload: dict, channel: aio_pika.abc.AbstractChannel):
    eas_token = payload.get("eas_token")
    expo_app_id = payload.get("expo_app_id", "")
    if not eas_token or not expo_app_id:
        logger.warning("EAS: missing EAS_TOKEN or EXPO_APP_ID for build %s — simulating", build_id)
        await publish_event(channel, "build.finished", {
            "build_id": build_id,
            "project_id": payload["project_id"],
            "framework": payload.get("framework", "expo"),
            "status": "success",
            "artifact_url": None,
            "provider": "eas",
            "note": "Simulated — EAS_TOKEN or EXPO_APP_ID not configured",
        })
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://api.expo.dev/v2/projects/{expo_app_id}/builds",
            headers={"Authorization": f"Bearer {eas_token}", "Content-Type": "application/json"},
            json={
                "platform": payload.get("platform", "all"),
                "buildProfile": "production",
                "gitRef": payload.get("branch", "main"),
            },
        )

    if resp.status_code in (200, 201):
        external_id = (resp.json().get("data") or {}).get("id") or resp.json().get("buildId")
        await publish_event(channel, "build.started", {
            "build_id": build_id,
            "project_id": payload["project_id"],
            "framework": payload.get("framework"),
            "external_build_id": external_id,
            "provider": "eas",
        })
        logger.info("EAS build queued: internal=%s external=%s", build_id, external_id)
    else:
        logger.error("EAS trigger failed %s: %s", resp.status_code, resp.text[:300])
        await publish_event(channel, "build.failed", {
            "build_id": build_id,
            "project_id": payload["project_id"],
            "error": f"EAS API error {resp.status_code}: {resp.text[:200]}",
        })


async def _trigger_codemagic(build_id: str, payload: dict, channel: aio_pika.abc.AbstractChannel):
    codemagic_token = payload.get("codemagic_token")
    codemagic_app_id = payload.get("codemagic_app_id", "")
    if not codemagic_token or not codemagic_app_id:
        logger.warning("Codemagic: missing token or app ID for build %s — simulating", build_id)
        await publish_event(channel, "build.finished", {
            "build_id": build_id,
            "project_id": payload["project_id"],
            "framework": payload.get("framework", "flutter"),
            "status": "success",
            "artifact_url": None,
            "provider": "codemagic",
            "note": "Simulated — CODEMAGIC_TOKEN or CODEMAGIC_APP_ID not configured",
        })
        return

    platform = payload.get("platform", "android")
    workflow_id = "android-workflow" if platform == "android" else "ios-workflow" if platform == "ios" else "android-and-ios"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.codemagic.io/builds",
            headers={"x-auth-token": codemagic_token, "Content-Type": "application/json"},
            json={
                "appId": codemagic_app_id,
                "workflowId": workflow_id,
                "branch": payload.get("branch", "main"),
            },
        )

    if resp.status_code in (200, 201):
        external_id = resp.json().get("buildId") or resp.json().get("id")
        await publish_event(channel, "build.started", {
            "build_id": build_id,
            "project_id": payload["project_id"],
            "framework": payload.get("framework"),
            "external_build_id": external_id,
            "provider": "codemagic",
        })
        logger.info("Codemagic build queued: internal=%s external=%s", build_id, external_id)
    else:
        logger.error("Codemagic trigger failed %s: %s", resp.status_code, resp.text[:300])
        await publish_event(channel, "build.failed", {
            "build_id": build_id,
            "project_id": payload["project_id"],
            "error": f"Codemagic API error {resp.status_code}",
        })


async def _trigger_github_actions(build_id: str, payload: dict, channel: aio_pika.abc.AbstractChannel):
    github_token = payload.get("github_token") or os.getenv("GITHUB_ACTIONS_TOKEN", "")
    repo_url = payload.get("repo_url", "")
    branch = payload.get("branch", "main")
    platform = payload.get("platform", "android")

    owner_repo = ""
    if "github.com/" in repo_url:
        parts = repo_url.rstrip("/").rstrip(".git").split("github.com/")[-1]
        owner_repo = parts

    if not github_token or not owner_repo:
        logger.warning("GitHub Actions: no token or repo, simulating build %s", build_id)
        await publish_event(channel, "build.finished", {
            "build_id": build_id,
            "project_id": payload["project_id"],
            "framework": payload.get("framework", "native"),
            "status": "success",
            "artifact_url": None,
            "provider": "github_actions",
            "note": "Simulated — GITHUB_ACTIONS_TOKEN or repo_url not configured",
        })
        return

    workflow_file = f"build-{platform}.yml"
    if payload.get("framework") == "swift":
        workflow_file = "build-ios.yml"
    elif payload.get("framework") == "kotlin":
        workflow_file = "build-android.yml"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://api.github.com/repos/{owner_repo}/actions/workflows/{workflow_file}/dispatches",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "ref": branch,
                "inputs": {
                    "build_id": build_id,
                    "platform": platform,
                    "project_id": payload["project_id"],
                },
            },
        )

    if resp.status_code == 204:
        await publish_event(channel, "build.started", {
            "build_id": build_id,
            "project_id": payload["project_id"],
            "framework": payload.get("framework"),
            "external_build_id": f"gh-{owner_repo}-{build_id[:8]}",
            "provider": "github_actions",
        })
        logger.info("GitHub Actions workflow dispatched: %s/%s for build %s", owner_repo, workflow_file, build_id)
    else:
        logger.error("GitHub Actions trigger failed %s: %s", resp.status_code, resp.text[:300])
        await publish_event(channel, "build.failed", {
            "build_id": build_id,
            "project_id": payload["project_id"],
            "error": f"GitHub Actions API error {resp.status_code}: {resp.text[:200]}",
        })


async def _simulate_build(build_id: str, project_id: str, framework: str, provider: str, channel: aio_pika.abc.AbstractChannel):
    logger.warning("Simulating build %s via %s (no credentials)", build_id, provider)
    await publish_event(channel, "build.finished", {
        "build_id": build_id,
        "project_id": project_id,
        "framework": framework,
        "status": "success",
        "artifact_url": None,
        "provider": provider,
        "note": f"Simulated — {provider} credentials not configured",
    })


async def handle_build_triggered(message: aio_pika.abc.AbstractIncomingMessage, channel: aio_pika.abc.AbstractChannel):
    async with message.process(requeue=True):
        try:
            payload = json.loads(message.body)
            build_id = payload["build_id"]
            provider = payload.get("provider", "github_actions")
            framework = payload.get("framework", "unknown")
            logger.info("Processing build %s via %s (framework=%s)", build_id, provider, framework)

            if provider == "eas":
                await _trigger_eas(build_id, payload, channel)
            elif provider == "codemagic":
                await _trigger_codemagic(build_id, payload, channel)
            elif provider == "github_actions":
                await _trigger_github_actions(build_id, payload, channel)
            else:
                await _simulate_build(build_id, payload["project_id"], framework, provider, channel)

        except Exception as exc:
            logger.error("Build handler error: %s", exc)
            p = json.loads(message.body) if message.body else {}
            await publish_event(channel, "build.failed", {
                "build_id": p.get("build_id"),
                "project_id": p.get("project_id"),
                "error": str(exc),
            })


async def start_consumer():
    global _channel
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    _channel = await connection.channel()
    await _channel.set_qos(prefetch_count=5)
    queue = await _channel.declare_queue("build.triggered", durable=True)
    await queue.consume(lambda msg: handle_build_triggered(msg, _channel))
    logger.info("Build consumer started on build.triggered")
    return connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = await start_consumer()
    yield
    await conn.close()


app = FastAPI(title="Build Orchestrator Service", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "build"}


@app.post("/webhook/eas")
async def eas_webhook(request: Request):
    body = await request.body()

    if settings.EAS_WEBHOOK_SECRET:
        signature = request.headers.get("x-eas-webhook-signature", "")
        if not signature:
            raise HTTPException(status_code=401, detail="Missing EAS webhook signature")
        if not _verify_hmac(body, signature, settings.EAS_WEBHOOK_SECRET):
            raise HTTPException(status_code=401, detail="Invalid EAS webhook signature")
    else:
        raise HTTPException(status_code=503, detail="EAS_WEBHOOK_SECRET not configured — webhook disabled")

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.info("EAS webhook: %s", parsed)

    if not _channel:
        return {"received": True, "note": "channel not ready"}

    eas_build_id = parsed.get("id") or parsed.get("buildId")
    raw_status = parsed.get("status", "")
    status_map = {"finished": "success", "errored": "failed", "canceled": "failed"}
    status = status_map.get(raw_status, "running")

    artifacts = parsed.get("artifacts", {})
    artifact_url = artifacts.get("buildUrl") or artifacts.get("url") or artifacts.get("applicationArchiveUrl")

    if status in ("success", "failed") and eas_build_id:
        await publish_event(_channel, "build.finished", {
            "external_build_id": eas_build_id,
            "status": status,
            "artifact_url": artifact_url,
            "provider": "eas",
            "framework": parsed.get("metadata", {}).get("appName", ""),
        })
        logger.info("EAS build %s completed: status=%s artifact=%s", eas_build_id, status, artifact_url)

    return {"received": True}


@app.post("/webhook/codemagic")
async def codemagic_webhook(request: Request):
    body = await request.body()

    if settings.CODEMAGIC_WEBHOOK_SECRET:
        signature = request.headers.get("x-codemagic-signature", "")
        if not signature:
            raise HTTPException(status_code=401, detail="Missing Codemagic webhook signature")
        if not _verify_hmac(body, signature, settings.CODEMAGIC_WEBHOOK_SECRET):
            raise HTTPException(status_code=401, detail="Invalid Codemagic webhook signature")
    else:
        raise HTTPException(status_code=503, detail="CODEMAGIC_WEBHOOK_SECRET not configured — webhook disabled")

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.info("Codemagic webhook: %s", parsed)

    if not _channel:
        return {"received": True, "note": "channel not ready"}

    cm_build_id = parsed.get("buildId") or parsed.get("id")
    raw_status = parsed.get("status", "").upper()
    status = "success" if raw_status in ("SUCCESS", "FINISHED") else "failed" if raw_status in ("FAILED", "ERROR", "CANCELED") else "running"

    artifact_urls = parsed.get("artifactUrls", [])
    artifact_url = artifact_urls[0] if artifact_urls else None

    if status in ("success", "failed") and cm_build_id:
        await publish_event(_channel, "build.finished", {
            "external_build_id": cm_build_id,
            "status": status,
            "artifact_url": artifact_url,
            "provider": "codemagic",
        })
        logger.info("Codemagic build %s completed: status=%s artifact=%s", cm_build_id, status, artifact_url)

    return {"received": True}
