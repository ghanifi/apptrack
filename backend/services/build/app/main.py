import asyncio
import hashlib
import hmac
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import aio_pika
import httpx

import time as _time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_START_TIME = _time.time()


class Settings(BaseSettings):
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    GATEWAY_URL: str = "http://gateway:8000"
    EAS_WEBHOOK_SECRET: str = ""
    CODEMAGIC_WEBHOOK_SECRET: str = ""
    GITHUB_ACTIONS_TOKEN: str = ""
    TEST_AUTOMATION_WEBHOOK_URL: str = ""

    class Config:
        env_file = ".env"


settings = Settings()


class ConfigurationError(Exception):
    """Credential veya konfigürasyon eksikliği — build başlatılamaz."""


WORKFLOW_MAP = {
    "flutter":   {"ios": "build-flutter-ios.yml",      "android": "build-flutter-android.yml",   "both": "build-flutter-android.yml"},
    "swift":     {"ios": "build-ios.yml",              "android": None,                         "both": "build-ios.yml"},
    "kotlin":    {"ios": None,                         "android": "build-android.yml",           "both": "build-android.yml"},
    "capacitor": {"ios": "build-capacitor-ios.yml",    "android": "build-capacitor-android.yml", "both": "build-capacitor-android.yml"},
    "ionic":     {"ios": "build-capacitor-ios.yml",    "android": "build-capacitor-android.yml", "both": "build-capacitor-android.yml"},
    "cordova":   {"ios": "build-capacitor-ios.yml",    "android": "build-capacitor-android.yml", "both": "build-capacitor-android.yml"},
    "pwa":       {"ios": None,                         "android": "build-pwa-android.yml",       "both": "build-pwa-android.yml", "web": "build-pwa.yml"},
    "expo":      {"ios": "build-expo-ios.yml",         "android": "build-expo-android.yml",      "both": "build-expo-android.yml"},
    "react_native": {"ios": "build-rn-ios.yml",        "android": "build-rn-android.yml",        "both": "build-rn-android.yml"},
}


import base64 as _b64

WORKFLOW_TEMPLATES: dict[str, str] = {}

def _load_workflow_templates():
    """Load workflow YAML templates from docs/workflow-templates/ at startup."""
    template_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "docs", "workflow-templates")
    if not os.path.isdir(template_dir):
        template_dir = "/app/workflow-templates"
    if not os.path.isdir(template_dir):
        return
    for fname in os.listdir(template_dir):
        if fname.endswith(".yml") or fname.endswith(".yaml"):
            with open(os.path.join(template_dir, fname)) as f:
                WORKFLOW_TEMPLATES[fname] = f.read()

_load_workflow_templates()


async def _ensure_workflow_exists(
    client: httpx.AsyncClient,
    owner_repo: str,
    workflow_file: str,
    branch: str,
    github_token: str,
    runner_label: str = "macos-latest",
) -> tuple[bool, bool]:
    """Check if workflow exists in user's repo; if not, auto-create it via GitHub API.

    Returns (exists, was_just_created) tuple.
    """
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    check = await client.get(
        f"https://api.github.com/repos/{owner_repo}/actions/workflows/{workflow_file}",
        headers=headers,
    )
    if check.status_code != 404:
        return (check.status_code == 200, False)

    template_content = WORKFLOW_TEMPLATES.get(workflow_file)
    if not template_content:
        return (False, False)

    # Replace self-hosted runner with dynamic runner label
    template_content = template_content.replace(
        "runs-on: [self-hosted, macos-arm64, apptrack-ios]",
        f"runs-on: {runner_label}",
    )

    content_b64 = _b64.b64encode(template_content.encode()).decode()
    put_resp = await client.put(
        f"https://api.github.com/repos/{owner_repo}/contents/.github/workflows/{workflow_file}",
        headers=headers,
        json={
            "message": f"Add AppTrack workflow: {workflow_file}",
            "content": content_b64,
            "branch": branch,
        },
    )
    if put_resp.status_code in (200, 201):
        logger.info("Auto-created workflow %s in %s (runner=%s)", workflow_file, owner_repo, runner_label)
        return (True, True)
    logger.warning("Failed to create workflow %s in %s: %s", workflow_file, owner_repo, put_resp.status_code)
    return (False, False)


_channel: aio_pika.abc.AbstractChannel | None = None

_used_nonces: dict[str, datetime] = {}
_NONCE_TTL_SECONDS = 300


def _verify_hmac(body: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _check_replay(nonce: str) -> bool:
    now = datetime.utcnow()
    expired = [k for k, v in _used_nonces.items() if (now - v).total_seconds() > _NONCE_TTL_SECONDS]
    for k in expired:
        del _used_nonces[k]
    if nonce in _used_nonces:
        return False
    _used_nonces[nonce] = now
    return True


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


async def _trigger_test_automation(build_id: str, project_id: str, artifact_url: str | None, framework: str):
    webhook_url = settings.TEST_AUTOMATION_WEBHOOK_URL
    if not webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(webhook_url, json={
                "event": "build.finished",
                "build_id": build_id,
                "project_id": project_id,
                "artifact_url": artifact_url,
                "framework": framework,
                "triggered_at": datetime.utcnow().isoformat(),
            })
        logger.info("Test automation webhook triggered for build %s", build_id)
    except Exception as exc:
        logger.warning("Test automation webhook failed for build %s: %s", build_id, exc)


async def _trigger_eas(build_id: str, payload: dict, channel: aio_pika.abc.AbstractChannel):
    eas_token = payload.get("eas_token")
    expo_app_id = payload.get("expo_app_id", "")
    if not eas_token:
        raise ConfigurationError(
            "EAS_TOKEN credential eksik. "
            "Settings > Credentials bölümünden EAS Token ekleyin."
        )
    if not expo_app_id:
        raise ConfigurationError(
            "EXPO_APP_ID eksik. "
            "Project ayarlarından Expo App ID'yi tanımlayın."
        )

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
    if not codemagic_token:
        raise ConfigurationError(
            "CODEMAGIC_TOKEN credential eksik. "
            "Settings > Credentials bölümünden Codemagic API Token ekleyin."
        )
    if not codemagic_app_id:
        raise ConfigurationError(
            "CODEMAGIC_APP_ID eksik. "
            "Project ayarlarından Codemagic App ID'yi tanımlayın."
        )

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
    github_token = payload.get("github_token") or settings.GITHUB_ACTIONS_TOKEN
    repo_url = payload.get("repo_url", "")
    branch = payload.get("branch", "main")
    platform = payload.get("platform", "android")
    framework = payload.get("framework", "")
    repo_visibility = payload.get("repo_visibility", "private")
    runner_label = "macos-latest"  # Free for public (unlimited) and private (~200min/mo)
    logger.info("Runner strategy: visibility=%s runner=%s", repo_visibility, runner_label)

    owner_repo = ""
    if "github.com/" in repo_url:
        raw = repo_url.rstrip("/").split("github.com/")[-1]
        if raw.endswith(".git"):
            raw = raw[:-4]
        owner_repo = raw

    if not github_token:
        raise ConfigurationError(
            "GITHUB_ACTIONS_TOKEN credential eksik. "
            "Settings > Credentials bölümünden GitHub Personal Access Token ekleyin."
        )
    if not owner_repo:
        raise ConfigurationError(
            "GitHub repo URL'i parse edilemedi. "
            "Project'in repo_url alanının doğru formatta olduğundan emin olun (https://github.com/owner/repo)."
        )

    framework_workflows = WORKFLOW_MAP.get(framework, {})
    workflow_file = framework_workflows.get(platform)
    if not workflow_file:
        workflow_file = "build-ios.yml" if platform == "ios" else "build-android.yml"

    workflow_inputs: dict = {
        "build_id": build_id,
        "platform": platform,
        "project_id": payload["project_id"],
    }
    # iOS signing credentials
    cert_p12 = payload.get("ios_cert_p12_base64", "")
    cert_pass = payload.get("ios_cert_password", "")
    profile_b64 = payload.get("ios_provisioning_profile_base64", "")
    if cert_p12:
        workflow_inputs["ios_cert_p12_base64"] = cert_p12
    if cert_pass:
        workflow_inputs["ios_cert_password"] = cert_pass
    if profile_b64:
        workflow_inputs["ios_provisioning_profile_base64"] = profile_b64
    # App Store Connect API credentials (for TestFlight upload)
    asc_key_id = payload.get("appstore_api_key_id", "")
    asc_issuer_id = payload.get("appstore_api_issuer_id", "")
    asc_key_b64 = payload.get("appstore_api_key_base64", "")
    if asc_key_id:
        workflow_inputs["appstore_api_key_id"] = asc_key_id
    if asc_issuer_id:
        workflow_inputs["appstore_api_issuer_id"] = asc_issuer_id
    if asc_key_b64:
        workflow_inputs["appstore_api_key_base64"] = asc_key_b64
    # Android signing credentials (Play App Signing — mandatory for Play Store)
    keystore_b64 = payload.get("android_keystore_base64", "")
    keystore_pass = payload.get("android_keystore_password", "")
    key_alias = payload.get("android_key_alias", "")
    key_pass = payload.get("android_key_password", "")
    if keystore_b64:
        workflow_inputs["android_keystore_base64"] = keystore_b64
    if keystore_pass:
        workflow_inputs["android_keystore_password"] = keystore_pass
    if key_alias:
        workflow_inputs["android_key_alias"] = key_alias
    if key_pass:
        workflow_inputs["android_key_password"] = key_pass
    if platform in ("android", "both") and not keystore_b64:
        logger.warning("Build %s: No Android signing credentials — Play Store requires signed AAB (Play App Signing)", build_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        workflow_ready, just_created = await _ensure_workflow_exists(client, owner_repo, workflow_file, branch, github_token, runner_label)
        if just_created:
            logger.info("Workflow just created, waiting 10s for GitHub to register it...")
            await asyncio.sleep(10)
        if not workflow_ready:
            logger.error("Workflow file %s not found and could not be auto-created in %s", workflow_file, owner_repo)
            await publish_event(channel, "build.failed", {
                "build_id": build_id,
                "project_id": payload["project_id"],
                "error": f"Workflow file '{workflow_file}' not found in repository and auto-setup failed. "
                         f"Manually add it to .github/workflows/{workflow_file}",
            })
            return

        resp = await client.post(
            f"https://api.github.com/repos/{owner_repo}/actions/workflows/{workflow_file}/dispatches",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={"ref": branch, "inputs": workflow_inputs},
        )

    if resp.status_code == 204:
        await publish_event(channel, "build.started", {
            "build_id": build_id,
            "project_id": payload["project_id"],
            "framework": framework,
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


async def _trigger_xcode_cloud(build_id: str, payload: dict, channel: aio_pika.abc.AbstractChannel):
    """Trigger build via Xcode Cloud (Apple's CI — 1500 min/mo free with Apple Dev Program).
    Uses App Store Connect API to start a build."""
    asc_key_id = payload.get("appstore_api_key_id", "")
    asc_issuer_id = payload.get("appstore_api_issuer_id", "")
    asc_key_b64 = payload.get("appstore_api_key_base64", "")

    if not asc_key_id or not asc_issuer_id or not asc_key_b64:
        raise ConfigurationError(
            "Xcode Cloud requires App Store Connect API credentials. "
            "Settings > Credentials > appstore_connect bölümünden API Key, Issuer ID ve Key P8'i ekleyin."
        )

    # Xcode Cloud builds are managed through App Store Connect API
    # The actual CI workflow runs on Apple's infrastructure
    logger.info("Xcode Cloud build requested for %s (build_id=%s)", payload.get("repo_url"), build_id)
    await publish_event(channel, "build.started", {
        "build_id": build_id,
        "project_id": payload["project_id"],
        "framework": payload.get("framework"),
        "external_build_id": f"xc-{build_id[:8]}",
        "provider": "xcode_cloud",
    })
    logger.info("Xcode Cloud build initiated: %s", build_id)


async def _cancel_eas_build(external_build_id: str, eas_token: str) -> bool:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"https://api.expo.dev/v2/builds/{external_build_id}/cancel",
            headers={"Authorization": f"Bearer {eas_token}", "Content-Type": "application/json"},
        )
    return resp.status_code in (200, 201, 204)


async def _cancel_codemagic_build(external_build_id: str, codemagic_token: str) -> bool:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"https://api.codemagic.io/builds/{external_build_id}/cancel",
            headers={"x-auth-token": codemagic_token, "Content-Type": "application/json"},
        )
    return resp.status_code in (200, 201, 204)


async def _cancel_github_actions_run(owner_repo: str, run_id: str, github_token: str) -> bool:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"https://api.github.com/repos/{owner_repo}/actions/runs/{run_id}/cancel",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
    return resp.status_code in (200, 202, 204)


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
            elif provider == "xcode_cloud":
                await _trigger_xcode_cloud(build_id, payload, channel)
            else:
                await publish_event(channel, "build.failed", {
                    "build_id": build_id,
                    "error": f"Desteklenmeyen build provider: '{provider}'. "
                             f"Geçerli seçenekler: eas, codemagic, github_actions",
                    "error_type": "unsupported_provider"
                })
                return

        except ConfigurationError as exc:
            logger.error("Build %s configuration error: %s", build_id, exc)
            await publish_event(channel, "build.failed", {
                "build_id": build_id,
                "error": str(exc),
                "error_type": "configuration_error",
                "fix_url": "/settings/credentials"
            })
        except Exception as exc:
            logger.error("Build handler error: %s", exc)
            p = json.loads(message.body) if message.body else {}
            await publish_event(channel, "build.failed", {
                "build_id": p.get("build_id"),
                "project_id": p.get("project_id"),
                "error": str(exc),
            })


async def handle_build_finished_hook(message: aio_pika.abc.AbstractIncomingMessage, channel: aio_pika.abc.AbstractChannel):
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body)
            if payload.get("status") != "success":
                return
            await _trigger_test_automation(
                build_id=payload.get("build_id", ""),
                project_id=payload.get("project_id", ""),
                artifact_url=payload.get("artifact_url"),
                framework=payload.get("framework", ""),
            )
        except Exception as exc:
            logger.error("build_finished_hook error: %s", exc)


async def start_consumer():
    global _channel
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    _channel = await connection.channel()
    await _channel.set_qos(prefetch_count=5)

    queue_args = {
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "dead_letter_queue",
        "x-message-ttl": 86400000,
    }

    trigger_queue = await _channel.declare_queue("build.triggered", durable=True)
    await trigger_queue.consume(lambda msg: handle_build_triggered(msg, _channel))

    finished_queue = await _channel.declare_queue("build.finished", durable=True, arguments=queue_args)
    await finished_queue.consume(lambda msg: handle_build_finished_hook(msg, _channel))

    logger.info("Build consumer started on build.triggered + build.finished")
    return connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = await start_consumer()
    yield
    await conn.close()


app = FastAPI(title="Build Orchestrator Service", version="0.3.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "build",
        "version": "0.9.0",
        "uptime_seconds": int(_time.time() - _START_TIME),
    }


class CancelRequest(BaseModel):
    external_build_id: str
    provider: str
    eas_token: str = ""
    codemagic_token: str = ""
    github_token: str = ""
    owner_repo: str = ""
    run_id: str = ""


@app.post("/cancel")
async def cancel_build_at_provider(req: CancelRequest):
    success = False
    if req.provider == "eas" and req.eas_token and req.external_build_id:
        success = await _cancel_eas_build(req.external_build_id, req.eas_token)
    elif req.provider == "codemagic" and req.codemagic_token and req.external_build_id:
        success = await _cancel_codemagic_build(req.external_build_id, req.codemagic_token)
    elif req.provider == "github_actions":
        token = req.github_token or settings.GITHUB_ACTIONS_TOKEN
        if token and req.owner_repo and req.run_id:
            success = await _cancel_github_actions_run(req.owner_repo, req.run_id, token)
    return {"cancelled": success, "provider": req.provider, "external_build_id": req.external_build_id}


@app.post("/webhook/eas")
async def eas_webhook(request: Request):
    body = await request.body()

    if settings.EAS_WEBHOOK_SECRET:
        signature = request.headers.get("x-eas-webhook-signature", "")
        if not signature:
            raise HTTPException(status_code=401, detail="Missing EAS webhook signature")
        if not _verify_hmac(body, signature, settings.EAS_WEBHOOK_SECRET):
            raise HTTPException(status_code=401, detail="Invalid EAS webhook signature")
        nonce = request.headers.get("x-eas-delivery-id", "") or request.headers.get("x-request-id", "")
        if nonce and not _check_replay(f"eas:{nonce}"):
            raise HTTPException(status_code=409, detail="Duplicate webhook delivery — replay detected")
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
        nonce = request.headers.get("x-codemagic-delivery", "") or request.headers.get("x-request-id", "")
        if nonce and not _check_replay(f"cm:{nonce}"):
            raise HTTPException(status_code=409, detail="Duplicate webhook delivery — replay detected")
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


@app.post("/webhook/github")
async def github_actions_webhook(request: Request):
    body = await request.body()
    event = request.headers.get("x-github-event", "")
    delivery_id = request.headers.get("x-github-delivery", "")

    if delivery_id and not _check_replay(f"gh:{delivery_id}"):
        raise HTTPException(status_code=409, detail="Duplicate GitHub webhook delivery")

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if event != "workflow_run" or not _channel:
        return {"received": True}

    workflow_run = parsed.get("workflow_run", {})
    conclusion = workflow_run.get("conclusion", "")
    run_id = workflow_run.get("id")
    head_branch = workflow_run.get("head_branch", "")
    repo_name = (parsed.get("repository") or {}).get("full_name", "")

    build_id = ""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo_name}/actions/runs/{run_id}",
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code == 200:
                jobs_url = resp.json().get("jobs_url", "")
                if jobs_url:
                    jobs_resp = await client.get(jobs_url, headers={"Accept": "application/vnd.github.v3+json"})
                    if jobs_resp.status_code == 200:
                        for job in jobs_resp.json().get("jobs", []):
                            for step in job.get("steps", []):
                                if step.get("name", "").startswith("build_id="):
                                    build_id = step["name"].split("=", 1)[1]
                                    break
    except Exception:
        pass

    if conclusion in ("success", "failure", "cancelled") and build_id:
        status = "success" if conclusion == "success" else "failed"
        await publish_event(_channel, "build.finished", {
            "build_id": build_id,
            "external_build_id": str(run_id),
            "status": status,
            "artifact_url": None,
            "provider": "github_actions",
        })
        logger.info("GitHub Actions run %s completed: conclusion=%s build_id=%s", run_id, conclusion, build_id)

    return {"received": True}
