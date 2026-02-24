import asyncio
import json
import logging
import time
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import aio_pika
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    PREVIEW_BASE_URL: str = "http://localhost:8005"
    PREVIEW_HOST: str = "localhost"
    CLONE_BASE_DIR: str = "/tmp/repos"
    APPETIZE_API_TOKEN: str = ""
    DOCKER_ANDROID_URL: str = ""
    ENABLE_LIVE_PREVIEW: bool = True
    PREVIEW_STATE_DIR: str = "/data/preview-state"

    class Config:
        env_file = ".env"


settings = Settings()

STATE_DIR = Path(settings.PREVIEW_STATE_DIR)
STATE_DIR.mkdir(parents=True, exist_ok=True)

CONTAINERS: dict = {}
APPETIZE_API_URL = "https://api.appetize.io/apps"

_channel = None


def _state_path(project_id: str) -> Path:
    return STATE_DIR / f"{project_id}.json"


def _save_preview(project_id: str, data: dict):
    _state_path(project_id).write_text(json.dumps(data, default=str), encoding="utf-8")


def _load_preview(project_id: str) -> dict | None:
    p = _state_path(project_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _delete_preview(project_id: str):
    p = _state_path(project_id)
    if p.exists():
        p.unlink(missing_ok=True)

try:
    import docker as docker_sdk
    _docker_client = docker_sdk.DockerClient(base_url="unix:///var/run/docker.sock")
    _docker_client.ping()
    DOCKER_AVAILABLE = True
    logger.info("Docker socket connected — live preview enabled")
except Exception as _e:
    _docker_client = None
    DOCKER_AVAILABLE = False
    logger.warning("Docker unavailable (%s) — live preview disabled", _e)


async def _publish_event(channel: aio_pika.abc.AbstractChannel, routing_key: str, payload: dict) -> None:
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=routing_key,
    )


async def _upload_to_appetize(artifact_url: str, platform: str) -> str | None:
    if not settings.APPETIZE_API_TOKEN:
        return None
    is_android = platform in ("android", "both")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                APPETIZE_API_URL,
                headers={"X-API-KEY": settings.APPETIZE_API_TOKEN},
                json={
                    "url": artifact_url,
                    "platform": "android" if is_android else "ios",
                    "fileType": "apk" if is_android else "ipa",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                build_id = data.get("buildId") or data.get("publicKey")
                if build_id:
                    return f"https://appetize.io/embed/{build_id}"
            logger.warning("Appetize API %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.error("Appetize upload error: %s", exc)
    return None


def _start_container_sync(image: str, command: str, project_id: str, container_port: int) -> tuple[str, int] | None:
    name = f"apptrack-preview-{project_id}"
    try:
        existing = _docker_client.containers.get(name)
        existing.reload()
        if existing.status == "running":
            bindings = existing.ports.get(f"{container_port}/tcp")
            if bindings:
                return existing.id, int(bindings[0]["HostPort"])
        existing.remove(force=True)
    except docker_sdk.errors.NotFound:
        pass
    try:
        container = _docker_client.containers.run(
            image,
            command=command,
            volumes={"repo_clones": {"bind": "/repo", "mode": "ro"}},
            ports={f"{container_port}/tcp": None},
            detach=True,
            name=name,
        )
        for _ in range(20):
            time.sleep(0.5)
            container.reload()
            bindings = container.ports.get(f"{container_port}/tcp")
            if bindings:
                host_port = int(bindings[0]["HostPort"])
                logger.info("Container %s started on port %d", name, host_port)
                return container.id, host_port
    except Exception as exc:
        logger.error("_start_container_sync error: %s", exc)
    return None


def _stop_container_sync(project_id: str) -> None:
    name = f"apptrack-preview-{project_id}"
    try:
        container = _docker_client.containers.get(name)
        container.remove(force=True)
        logger.info("Removed preview container %s", name)
    except Exception:
        pass


async def _wait_for_ready(url: str, project_id: str, framework: str, timeout: int = 300) -> None:
    async with httpx.AsyncClient(timeout=3.0) as client:
        for _ in range(timeout):
            await asyncio.sleep(1)
            try:
                resp = await client.get(url)
                if resp.status_code < 500:
                    PREVIEWS_data = _load_preview(project_id) or {}
                    PREVIEWS_data["status"] = "ready"
                    _save_preview(project_id, PREVIEWS_data)
                    if _channel:
                        await _publish_event(_channel, "preview.ready", {
                            "project_id": project_id,
                            "framework": framework,
                            "preview_url": url,
                            "type": PREVIEWS_data.get("type"),
                        })
                    logger.info("Live preview ready for %s: %s", project_id, url)
                    return
            except Exception:
                pass
    logger.warning("Preview server timed out for project %s", project_id)
    pdata = _load_preview(project_id) or {}
    pdata["status"] = "timeout"
    _save_preview(project_id, pdata)


async def _launch_live_preview(project_id: str, framework: str) -> bool:
    if not DOCKER_AVAILABLE:
        return False
    if framework in ("expo", "react_native"):
        image = "node:20-alpine"
        command = (
            f"sh -c 'cd /repo/{project_id} && "
            "npm install -g @expo/cli --silent 2>/dev/null; "
            "npm install --silent && "
            "npx expo start --web --port 19006 --non-interactive'"
        )
        port = 19006
    elif framework == "flutter":
        image = "ghcr.io/cirruslabs/flutter:stable"
        command = (
            f"sh -c 'cd /repo/{project_id} && "
            "flutter build web --release --no-sound-null-safety 2>/dev/null || flutter build web --release && "
            "python3 -m http.server 8080 --directory build/web'"
        )
        port = 8080
    else:
        return False

    result = await asyncio.to_thread(_start_container_sync, image, command, project_id, port)
    if not result:
        return False

    container_id, host_port = result
    CONTAINERS[project_id] = container_id
    preview_url = f"http://{settings.PREVIEW_HOST}:{host_port}"

    pdata = _load_preview(project_id) or {}
    pdata.update({
        "type": "live",
        "status": "starting",
        "preview_url": preview_url,
        "instructions": "Live dev server is starting, please wait...",
    })
    _save_preview(project_id, pdata)

    asyncio.create_task(_wait_for_ready(preview_url, project_id, framework))
    return True


def _static_preview_info(project_id: str, framework: str) -> dict:
    if framework in ("expo", "react_native"):
        host = settings.PREVIEW_BASE_URL.replace("http://", "").replace("https://", "")
        return {
            "type": "expo",
            "status": "ready",
            "preview_url": f"{settings.PREVIEW_BASE_URL}/preview/{project_id}",
            "qr_url": (
                f"https://qr.expo.dev/development-client"
                f"?appScheme=exp&url=exp%3A%2F%2F{host}%2F{project_id}"
            ),
            "instructions": "Scan the QR code with Expo Go on your device.",
        }
    elif framework == "flutter":
        return {
            "type": "flutter_web",
            "status": "ready",
            "preview_url": f"{settings.PREVIEW_BASE_URL}/preview/{project_id}",
            "instructions": "Flutter web preview — open the link in your browser.",
        }
    elif framework in ("swift", "kotlin"):
        return {
            "type": "native_pending",
            "status": "pending_build",
            "preview_url": None,
            "instructions": "Build your app first. After a successful build, an interactive preview will be generated via Appetize.io.",
        }
    return {
        "type": "unavailable",
        "status": "unavailable",
        "preview_url": None,
        "instructions": f"Live preview not available for {framework}.",
    }


async def handle_framework_detected(
    message: aio_pika.abc.AbstractIncomingMessage,
    channel: aio_pika.abc.AbstractChannel,
):
    async with message.process(requeue=True):
        try:
            payload = json.loads(message.body)
            project_id = payload["project_id"]
            framework = payload["framework"]
            if framework == "unknown":
                return

            info = _static_preview_info(project_id, framework)
            _save_preview(project_id, {"project_id": project_id, "framework": framework, **info})

            if settings.ENABLE_LIVE_PREVIEW and framework in ("expo", "react_native", "flutter"):
                launched = await _launch_live_preview(project_id, framework)
                if launched:
                    logger.info("Live container started for %s (%s)", project_id, framework)
                    return

            if info["status"] == "ready":
                await _publish_event(channel, "preview.ready", {
                    "project_id": project_id,
                    "framework": framework,
                    "preview_url": info["preview_url"],
                    "qr_url": info.get("qr_url"),
                    "type": info["type"],
                })
        except Exception as exc:
            logger.error("handle_framework_detected error: %s", exc)


async def handle_build_finished(
    message: aio_pika.abc.AbstractIncomingMessage,
    channel: aio_pika.abc.AbstractChannel,
):
    async with message.process(requeue=True):
        try:
            payload = json.loads(message.body)
            project_id = payload.get("project_id")
            status_val = payload.get("status", "")
            artifact_url = payload.get("artifact_url")
            platform = payload.get("platform", "android")
            framework = payload.get("framework", "")

            if status_val != "success" or not artifact_url or not project_id:
                return
            if framework not in ("swift", "kotlin"):
                return

            embed_url = await _upload_to_appetize(artifact_url, platform)

            if embed_url:
                _save_preview(project_id, {
                    "project_id": project_id,
                    "framework": framework,
                    "status": "ready",
                    "type": "appetize",
                    "preview_url": embed_url,
                    "embed_url": embed_url,
                    "instructions": "Interactive native device preview powered by Appetize.io.",
                })
                await _publish_event(channel, "preview.ready", {
                    "project_id": project_id,
                    "framework": framework,
                    "preview_url": embed_url,
                    "type": "appetize",
                })
            elif framework == "kotlin" and settings.DOCKER_ANDROID_URL:
                _save_preview(project_id, {
                    "project_id": project_id,
                    "framework": framework,
                    "status": "ready",
                    "type": "docker_android",
                    "preview_url": settings.DOCKER_ANDROID_URL,
                    "instructions": f"Android emulator in browser. Download APK: {artifact_url}",
                })
            else:
                _save_preview(project_id, {
                    "project_id": project_id,
                    "framework": framework,
                    "status": "download_only",
                    "type": "download_only",
                    "preview_url": artifact_url,
                    "instructions": "Build complete. Download and install on your device.",
                })
        except Exception as exc:
            logger.error("handle_build_finished error: %s", exc)


async def start_consumer():
    global _channel
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    _channel = await connection.channel()
    await _channel.set_qos(prefetch_count=5)

    q1 = await _channel.declare_queue("framework.detected", durable=True)
    q2 = await _channel.declare_queue("build.finished", durable=True)

    await q1.consume(lambda msg: handle_framework_detected(msg, _channel))
    await q2.consume(lambda msg: handle_build_finished(msg, _channel))

    logger.info("Preview service listening: framework.detected + build.finished")
    return connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = await start_consumer()
    yield
    await conn.close()


app = FastAPI(title="Preview Orchestrator Service", version="0.3.0", lifespan=lifespan)


class PreviewRequest(BaseModel):
    project_id: str
    framework: str
    project_path: str = ""


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "preview",
        "docker_available": DOCKER_AVAILABLE,
        "live_preview_enabled": settings.ENABLE_LIVE_PREVIEW and DOCKER_AVAILABLE,
    }


@app.get("/preview/{project_id}")
def get_preview(project_id: str):
    p = _load_preview(project_id)
    if not p:
        return {"project_id": project_id, "status": "not_ready", "preview_url": None}
    return p


@app.post("/start")
async def start_preview(req: PreviewRequest):
    info = _static_preview_info(req.project_id, req.framework)
    preview_data = {"project_id": req.project_id, "framework": req.framework, **info}
    _save_preview(req.project_id, preview_data)
    if settings.ENABLE_LIVE_PREVIEW and req.framework in ("expo", "react_native", "flutter"):
        asyncio.create_task(_launch_live_preview(req.project_id, req.framework))
    return _load_preview(req.project_id) or preview_data


@app.delete("/{project_id}")
async def stop_preview(project_id: str):
    if DOCKER_AVAILABLE and project_id in CONTAINERS:
        await asyncio.to_thread(_stop_container_sync, project_id)
        del CONTAINERS[project_id]
    _delete_preview(project_id)
    return {"project_id": project_id, "status": "stopped"}
