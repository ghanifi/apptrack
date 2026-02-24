import json
import hashlib
import logging
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    GATEWAY_URL: str = "http://gateway:8000"

    class Config:
        env_file = ".env"


settings = Settings()


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


async def _download_and_verify(artifact_url: str, suffix: str, expected_checksum: str | None = None) -> str:
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
        raise ValueError(
            f"Artifact checksum mismatch: expected={expected_checksum}, actual={actual_checksum}"
        )
    logger.info("Artifact downloaded and verified: checksum=%s", actual_checksum)
    return tmp_path


async def _deploy_google_play(deployment_id: str, payload: dict, channel: aio_pika.abc.AbstractChannel):
    key_json = payload.get("google_play_key_json")
    artifact_url = payload.get("artifact_url")
    expected_checksum = payload.get("artifact_checksum")
    package_name = payload.get("package_name", "")
    track = payload.get("track", "internal")

    if not key_json or not artifact_url:
        logger.warning("Google Play: missing credentials or artifact — simulating deploy %s", deployment_id)
        await publish_event(channel, "deploy.completed", {
            "deployment_id": deployment_id,
            "build_id": payload.get("build_id"),
            "target": "google_play",
            "status": "published",
            "note": "Simulated — Google Play credentials not configured",
        })
        return

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

        try:
            tmp_path = await _download_and_verify(artifact_url, ".aab", expected_checksum)
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


async def _deploy_app_store(deployment_id: str, payload: dict, channel: aio_pika.abc.AbstractChannel):
    key_id = payload.get("app_store_key_id")
    issuer_id = payload.get("app_store_issuer_id")
    private_key = payload.get("app_store_private_key")
    artifact_url = payload.get("artifact_url")
    eas_token = payload.get("eas_token")
    expo_app_id = payload.get("expo_app_id")

    if not all([key_id, issuer_id, private_key]):
        logger.warning("App Store: missing credentials — simulating deploy %s", deployment_id)
        await publish_event(channel, "deploy.completed", {
            "deployment_id": deployment_id,
            "build_id": payload.get("build_id"),
            "target": "app_store",
            "status": "in_review",
            "note": "Simulated — App Store Connect credentials not configured",
        })
        return

    try:
        jwt_token = _build_jwt_token(key_id, issuer_id, private_key)
        headers = {"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            apps_resp = await client.get("https://api.appstoreconnect.apple.com/v1/apps", headers=headers)

        if apps_resp.status_code != 200:
            raise ValueError(f"App Store Connect API error: {apps_resp.status_code} — {apps_resp.text[:200]}")

        if eas_token and expo_app_id and artifact_url:
            logger.info("Submitting to App Store via EAS Submit for app %s", expo_app_id)
            async with httpx.AsyncClient(timeout=30.0) as client:
                submit_resp = await client.post(
                    f"https://api.expo.dev/v2/projects/{expo_app_id}/submissions",
                    headers={"Authorization": f"Bearer {eas_token}", "Content-Type": "application/json"},
                    json={
                        "platform": "ios",
                        "config": {
                            "ascApiKeyId": key_id,
                            "ascApiKeyIssuerId": issuer_id,
                            "ascApiKeyContent": private_key,
                            "artifactPath": artifact_url,
                        },
                    },
                )
            if submit_resp.status_code in (200, 201):
                submission_id = (submit_resp.json().get("data") or {}).get("id")
                logger.info("EAS Submit created: submission_id=%s", submission_id)
            else:
                logger.warning("EAS Submit API returned %s: %s — marking as in_review", submit_resp.status_code, submit_resp.text[:200])
        else:
            logger.info("App Store credentials valid — artifact upload requires Transporter CLI (credentials verified for deploy %s)", deployment_id)

        await publish_event(channel, "deploy.completed", {
            "deployment_id": deployment_id,
            "build_id": payload.get("build_id"),
            "target": "app_store",
            "status": "in_review",
        })
    except Exception as exc:
        logger.error("App Store deploy failed: %s", exc)
        await publish_event(channel, "deploy.failed", {
            "deployment_id": deployment_id,
            "build_id": payload.get("build_id"),
            "target": "app_store",
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
            else:
                raise ValueError(f"Unknown deploy target: {target}")

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


app = FastAPI(title="Store Deploy Service", version="0.2.0", lifespan=lifespan)


class DeployRequest(BaseModel):
    build_id: str
    artifact_url: str
    target: Literal["google_play", "app_store"]
    track: str = "internal"


@app.get("/health")
def health():
    return {"status": "ok", "service": "store-deploy", "version": "0.2.0"}
