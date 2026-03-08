import json
import hashlib
import logging
import shutil
import subprocess
import time
import tempfile
import os
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI
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

    class Config:
        env_file = ".env"


settings = Settings()


class ConfigurationError(Exception):
    """Credential veya konfigürasyon eksikliği — deploy başlatılamaz."""


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


def _build_jwt_token(key_id: str, issuer_id: str, private_key_pem: str) -> str:
    import jwt as pyjwt
    payload = {
        "iss": issuer_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + 1200,
        "aud": "appstoreconnect-v1",
    }
    return pyjwt.encode(payload, private_key_pem, algorithm="ES256", headers={"kid": key_id})


async def _download_artifact(artifact_url: str, suffix: str, expected_checksum: str | None = None) -> str:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name

    sha256 = hashlib.sha256()
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream("GET", artifact_url) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as f:
                async for chunk in resp.aiter_bytes(1024 * 1024):
                    f.write(chunk)
                    sha256.update(chunk)

    actual_checksum = sha256.hexdigest()
    if expected_checksum and actual_checksum != expected_checksum:
        os.unlink(tmp_path)
        raise ValueError(f"Checksum mismatch: expected={expected_checksum} actual={actual_checksum}")
    logger.info("Artifact downloaded: checksum=%s path=%s", actual_checksum, tmp_path)
    return tmp_path


async def _deploy_google_play(deployment_id: str, payload: dict, channel: aio_pika.abc.AbstractChannel):
    key_json = payload.get("google_play_key_json")
    artifact_url = payload.get("artifact_url")
    expected_checksum = payload.get("artifact_checksum")
    package_name = payload.get("package_name", "")
    track = payload.get("track", "internal")

    if not key_json:
        raise ConfigurationError(
            "Google Play service account key eksik. "
            "Settings > Credentials bölümünden Google Play JSON Key ekleyin."
        )
    if not artifact_url:
        raise ConfigurationError(
            "Artifact URL bulunamadı. "
            "Deploy tetiklemeden önce başarılı bir Android build tamamlanmalıdır."
        )

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build as gapi_build
        from googleapiclient.http import MediaFileUpload

        key_data = json.loads(key_json)
        creds = service_account.Credentials.from_service_account_info(
            key_data,
            scopes=["https://www.googleapis.com/auth/androidpublisher"],
        )
        service = gapi_build("androidpublisher", "v3", credentials=creds)
        edit = service.edits().insert(packageName=package_name, body={}).execute()
        edit_id = edit["id"]

        tmp_path = await _download_artifact(artifact_url, ".aab", expected_checksum)
        try:
            media = MediaFileUpload(tmp_path, mimetype="application/octet-stream", resumable=True)
            service.edits().bundles().upload(
                packageName=package_name, editId=edit_id, media_body=media
            ).execute()
            service.edits().tracks().update(
                packageName=package_name, editId=edit_id, track=track,
                body={"releases": [{"status": "completed"}]},
            ).execute()
            service.edits().commit(packageName=package_name, editId=edit_id).execute()
        finally:
            os.unlink(tmp_path)

        await publish_event(channel, "deploy.completed", {
            "deployment_id": deployment_id,
            "build_id": payload.get("build_id"),
            "target": "google_play",
            "status": "published",
        })
    except Exception as exc:
        logger.error("Google Play deploy failed: %s", exc)
        await publish_event(channel, "deploy.failed", {
            "deployment_id": deployment_id,
            "build_id": payload.get("build_id"),
            "target": "google_play",
            "error": str(exc),
        })


async def _upload_ipa_via_fastlane(ipa_path: str, key_id: str, issuer_id: str, private_key_pem: str) -> tuple[bool, str]:
    if not shutil.which("fastlane"):
        return False, "fastlane not installed"

    key_file = tempfile.NamedTemporaryFile(suffix=".p8", delete=False, mode="w")
    key_file.write(private_key_pem)
    key_file.close()

    try:
        result = subprocess.run(
            [
                "fastlane", "deliver",
                "--ipa", ipa_path,
                "--api_key_path", "/dev/stdin",
                "--skip_metadata", "true",
                "--skip_screenshots", "true",
                "--submit_for_review", "false",
            ],
            input=json.dumps({
                "key_id": key_id,
                "issuer_id": issuer_id,
                "key": private_key_pem,
                "in_house": False,
                "is_key_content_base64": False,
            }),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            return True, "Uploaded via Fastlane deliver"
        return False, f"Fastlane exited {result.returncode}: {result.stderr[-500:]}"
    except subprocess.TimeoutExpired:
        return False, "Fastlane timed out after 600s"
    except Exception as exc:
        return False, str(exc)
    finally:
        os.unlink(key_file.name)


async def _upload_ipa_via_altool(ipa_path: str, key_id: str, issuer_id: str, private_key_pem: str) -> tuple[bool, str]:
    altool = shutil.which("altool") or shutil.which("xcrun")
    if not altool:
        return False, "altool / xcrun not installed (macOS required)"

    key_file = tempfile.NamedTemporaryFile(suffix=".p8", delete=False, mode="w")
    key_file.write(private_key_pem)
    key_file.close()

    cmd = (
        ["xcrun", "altool", "--upload-app", "--type", "ios", "--file", ipa_path,
         "--apiKey", key_id, "--apiIssuer", issuer_id, "--show-progress"]
        if altool.endswith("xcrun")
        else ["altool", "--upload-app", "--type", "ios", "--file", ipa_path,
              "--apiKey", key_id, "--apiIssuer", issuer_id]
    )

    env = os.environ.copy()
    env["API_PRIVATE_KEYS_DIR"] = os.path.dirname(key_file.name)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
        if result.returncode == 0:
            return True, "Uploaded via altool"
        return False, f"altool exited {result.returncode}: {result.stderr[-500:]}"
    except subprocess.TimeoutExpired:
        return False, "altool timed out after 600s"
    except Exception as exc:
        return False, str(exc)
    finally:
        os.unlink(key_file.name)


async def _verify_app_store_credentials(key_id: str, issuer_id: str, private_key_pem: str) -> tuple[bool, str]:
    try:
        jwt_token = _build_jwt_token(key_id, issuer_id, private_key_pem)
        headers = {"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://api.appstoreconnect.apple.com/v1/apps", headers=headers)
        if resp.status_code == 200:
            return True, jwt_token
        return False, f"App Store Connect API returned {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:
        return False, str(exc)


async def _submit_via_eas(artifact_url: str, eas_token: str, expo_app_id: str,
                          key_id: str, issuer_id: str, private_key_pem: str) -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.expo.dev/v2/projects/{expo_app_id}/submissions",
                headers={"Authorization": f"Bearer {eas_token}", "Content-Type": "application/json"},
                json={
                    "platform": "ios",
                    "config": {
                        "ascApiKeyId": key_id,
                        "ascApiKeyIssuerId": issuer_id,
                        "ascApiKeyContent": private_key_pem,
                        "artifactPath": artifact_url,
                    },
                },
            )
        if resp.status_code in (200, 201):
            submission_id = (resp.json().get("data") or {}).get("id")
            return True, f"EAS Submit created: submission_id={submission_id}"
        return False, f"EAS Submit returned {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:
        return False, str(exc)


async def _deploy_app_store(deployment_id: str, payload: dict, channel: aio_pika.abc.AbstractChannel):
    key_id = payload.get("app_store_key_id")
    issuer_id = payload.get("app_store_issuer_id")
    private_key = payload.get("app_store_private_key")
    artifact_url = payload.get("artifact_url")
    eas_token = payload.get("eas_token")
    expo_app_id = payload.get("expo_app_id")

    if not key_id:
        raise ConfigurationError(
            "App Store Connect Key ID eksik. "
            "Settings > Credentials bölümünden App Store Connect Key ID ekleyin."
        )
    if not issuer_id:
        raise ConfigurationError(
            "App Store Connect Issuer ID eksik. "
            "Settings > Credentials bölümünden App Store Connect Issuer ID ekleyin."
        )
    if not private_key:
        raise ConfigurationError(
            "App Store Connect Private Key (.p8) eksik. "
            "Settings > Credentials bölümünden App Store Connect Private Key ekleyin."
        )

    cred_ok, cred_msg = await _verify_app_store_credentials(key_id, issuer_id, private_key)
    if not cred_ok:
        logger.error("App Store credential verification failed for deploy %s: %s", deployment_id, cred_msg)
        await publish_event(channel, "deploy.failed", {
            "deployment_id": deployment_id,
            "build_id": payload.get("build_id"),
            "target": "app_store",
            "error": f"App Store Connect credential invalid: {cred_msg}",
        })
        return

    if not artifact_url:
        raise ConfigurationError(
            "Artifact URL bulunamadı. "
            "iOS build tamamlanmalı — deploy tetiklemeden önce başarılı bir iOS build gereklidir."
        )

    upload_ok = False
    upload_note = ""

    if eas_token and expo_app_id:
        upload_ok, upload_note = await _submit_via_eas(artifact_url, eas_token, expo_app_id, key_id, issuer_id, private_key)
        if upload_ok:
            logger.info("App Store submit via EAS succeeded for deploy %s: %s", deployment_id, upload_note)

    if not upload_ok:
        tmp_path = None
        try:
            tmp_path = await _download_artifact(artifact_url, ".ipa", payload.get("artifact_checksum"))
            upload_ok, upload_note = await _upload_ipa_via_fastlane(tmp_path, key_id, issuer_id, private_key)
            if upload_ok:
                logger.info("App Store upload via Fastlane succeeded for deploy %s", deployment_id)
        except Exception as dl_exc:
            upload_note = str(dl_exc)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    if not upload_ok:
        tmp_path = None
        try:
            tmp_path = await _download_artifact(artifact_url, ".ipa", payload.get("artifact_checksum"))
            upload_ok, upload_note = await _upload_ipa_via_altool(tmp_path, key_id, issuer_id, private_key)
            if upload_ok:
                logger.info("App Store upload via altool succeeded for deploy %s", deployment_id)
        except Exception as dl_exc:
            upload_note = str(dl_exc)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    if upload_ok:
        await publish_event(channel, "deploy.completed", {
            "deployment_id": deployment_id,
            "build_id": payload.get("build_id"),
            "target": "app_store",
            "status": "in_review",
            "note": upload_note,
        })
    else:
        logger.error("App Store upload failed for deploy %s — all methods exhausted: %s", deployment_id, upload_note)
        await publish_event(channel, "deploy.failed", {
            "deployment_id": deployment_id,
            "build_id": payload.get("build_id"),
            "target": "app_store",
            "error": f"Upload failed — {upload_note}. Install Fastlane or use EAS Submit.",
            "hint": "Run: gem install fastlane && fastlane add_plugin deliver",
        })


async def _deploy_web(deployment_id: str, payload: dict, channel: aio_pika.abc.AbstractChannel):
    """Deploy web build to Netlify or return static URL."""
    netlify_token = payload.get("netlify_token")
    artifact_url = payload.get("artifact_url")
    deploy_url = payload.get("deploy_url")

    if deploy_url:
        # Pre-configured deploy URL (e.g. MinIO static hosting)
        await publish_event(channel, "deploy.completed", {
            "deployment_id": deployment_id,
            "build_id": payload.get("build_id"),
            "target": "web",
            "status": "published",
            "deploy_url": deploy_url,
        })
        return

    if not netlify_token:
        raise ConfigurationError(
            "Web deploy requires either a deploy_url or NETLIFY_TOKEN. "
            "Settings > Credentials bölümünden Netlify Token ekleyin."
        )

    if not artifact_url:
        raise ConfigurationError(
            "Artifact URL bulunamadı. "
            "Web deploy için başarılı bir build gereklidir."
        )

    try:
        tmp_path = await _download_artifact(artifact_url, ".zip")
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                with open(tmp_path, "rb") as f:
                    resp = await client.post(
                        "https://api.netlify.com/api/v1/sites",
                        headers={
                            "Authorization": f"Bearer {netlify_token}",
                            "Content-Type": "application/zip",
                        },
                        content=f.read(),
                    )
            if resp.status_code in (200, 201):
                data = resp.json()
                site_url = data.get("ssl_url") or data.get("url") or ""
                await publish_event(channel, "deploy.completed", {
                    "deployment_id": deployment_id,
                    "build_id": payload.get("build_id"),
                    "target": "web",
                    "status": "published",
                    "deploy_url": site_url,
                })
                logger.info("Netlify deploy succeeded for %s: %s", deployment_id, site_url)
            else:
                raise Exception(f"Netlify API error {resp.status_code}: {resp.text[:200]}")
        finally:
            os.unlink(tmp_path)
    except ConfigurationError:
        raise
    except Exception as exc:
        logger.error("Web deploy failed for %s: %s", deployment_id, exc)
        await publish_event(channel, "deploy.failed", {
            "deployment_id": deployment_id,
            "build_id": payload.get("build_id"),
            "target": "web",
            "error": str(exc),
        })


async def handle_deploy_triggered(message: aio_pika.abc.AbstractIncomingMessage, channel: aio_pika.abc.AbstractChannel):
    async with message.process(requeue=True):
        try:
            payload = json.loads(message.body)
            deployment_id = payload["deployment_id"]
            target = payload.get("target", "google_play")
            logger.info("Processing deployment %s to %s", deployment_id, target)

            if target == "google_play":
                await _deploy_google_play(deployment_id, payload, channel)
            elif target == "app_store":
                await _deploy_app_store(deployment_id, payload, channel)
            elif target == "web":
                await _deploy_web(deployment_id, payload, channel)
            else:
                raise ValueError(f"Unknown deploy target: {target}")

        except ConfigurationError as exc:
            logger.error("Deploy %s configuration error: %s", deployment_id, exc)
            await publish_event(channel, "deploy.failed", {
                "deployment_id": deployment_id,
                "error": str(exc),
                "error_type": "configuration_error",
                "fix_url": "/settings/credentials"
            })
        except Exception as exc:
            logger.error("Deploy handler error: %s", exc)
            p = json.loads(message.body) if message.body else {}
            await publish_event(channel, "deploy.failed", {
                "deployment_id": p.get("deployment_id"),
                "build_id": p.get("build_id"),
                "error": str(exc),
            })


async def start_consumer():
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=3)
    queue = await channel.declare_queue("deploy.triggered", durable=True)
    await queue.consume(lambda msg: handle_deploy_triggered(msg, channel))
    logger.info("Store-deploy consumer started on deploy.triggered")
    return connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = await start_consumer()
    yield
    await conn.close()


app = FastAPI(title="Store Deploy Service", version="0.3.0", lifespan=lifespan)


class DeployRequest(BaseModel):
    build_id: str
    artifact_url: str
    target: Literal["google_play", "app_store"]
    track: str = "internal"


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "store-deploy",
        "version": "0.9.0",
        "uptime_seconds": int(_time.time() - _START_TIME),
    }
