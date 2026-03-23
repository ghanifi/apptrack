import json
import logging
import os
import glob as glob_module
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import aio_pika

import time as _time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_START_TIME = _time.time()


class Settings(BaseSettings):
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    CLONE_BASE_DIR: str = "/tmp/repos"

    class Config:
        env_file = ".env"


settings = Settings()

# Detection rules ordered by priority (first match wins)
# Hybrid frameworks MUST come before native because hybrid projects
# also contain native indicators (e.g. Capacitor has build.gradle + .xcodeproj)
FRAMEWORK_RULES = [
    # Cross-platform
    ("flutter", ["pubspec.yaml"], 0.98),
    ("expo", ["app.json", "app.config.js", "app.config.ts"], 0.97),
    ("react_native", ["package.json"], 0.85),
    # Hybrid mobile — checked BEFORE native (Capacitor projects contain build.gradle/.xcodeproj)
    ("capacitor", ["capacitor.config.ts", "capacitor.config.json", "capacitor.config.js"], 0.95),
    ("ionic", ["package.json"], 0.90),
    ("cordova", ["config.xml"], 0.90),
    # Native mobile — only matched if no hybrid indicator found above
    ("kotlin", ["build.gradle", "build.gradle.kts"], 0.97),
    ("swift", [".xcodeproj", ".xcworkspace"], 0.97),
    # PWA (web app packaged as mobile via TWA/PWABuilder)
    ("pwa", ["manifest.json", "manifest.webmanifest"], 0.70),
]

BUILD_PROVIDER_MAP = {
    "flutter": "codemagic",
    "expo": "eas",
    "react_native": "eas",
    "swift": "github_actions",
    "kotlin": "github_actions",
    "capacitor": "github_actions",
    "ionic": "github_actions",
    "cordova": "github_actions",
    "pwa": "github_actions",
    "unknown": "github_actions",
}

PREVIEW_MODE_MAP = {
    "flutter": "web",
    "expo": "expo_preview",
    "react_native": "expo_preview",
    "swift": "simulator",
    "kotlin": "simulator",
    "capacitor": "web",
    "ionic": "web",
    "cordova": "web",
    "pwa": "web",
    "unknown": "none",
}

# package.json dependency checks
_PKG_JSON_FRAMEWORKS = {
    "react_native": "react-native",
    "ionic": "@ionic/core",
}


def _has_pwa_intent(manifest_path: str) -> bool:
    """Check if manifest.json is a real PWA manifest (not a generic web manifest)."""
    try:
        with open(manifest_path) as f:
            data = json.load(f)
        # PWA manifests have display mode and start_url
        return "start_url" in data and "display" in data
    except Exception:
        return False


def _detect(project_path: str) -> tuple[str, float]:
    for framework, indicators, confidence in FRAMEWORK_RULES:
        for indicator in indicators:
            pattern = os.path.join(project_path, "**", indicator)
            matches = glob_module.glob(pattern, recursive=True)
            if matches:
                # Frameworks that need package.json dependency verification
                if framework in _PKG_JSON_FRAMEWORKS:
                    pkg_dep = _PKG_JSON_FRAMEWORKS[framework]
                    for m in matches:
                        try:
                            with open(m) as f:
                                pkg = json.load(f)
                            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                            if framework == "react_native":
                                if "react-native" in deps:
                                    return "react_native", confidence
                                if "expo" in deps:
                                    return "expo", confidence
                                continue
                            if pkg_dep in deps:
                                return framework, confidence
                        except Exception:
                            pass
                    continue

                # PWA needs manifest content validation
                if framework == "pwa":
                    for m in matches:
                        if _has_pwa_intent(m):
                            return "pwa", confidence
                    continue

                return framework, confidence
    return "unknown", 0.0


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


async def handle_repo_synced(message: aio_pika.abc.AbstractIncomingMessage, channel: aio_pika.abc.AbstractChannel):
    async with message.process(requeue=True):
        try:
            payload = json.loads(message.body)
            project_id = payload["project_id"]
            clone_path = payload["clone_path"]

            logger.info("Detecting framework for project %s at %s", project_id, clone_path)
            framework, confidence = _detect(clone_path)
            logger.info("Detected: %s (confidence=%.2f) for project %s", framework, confidence, project_id)

            await publish_event(channel, "framework.detected", {
                "project_id": project_id,
                "framework": framework,
                "build_provider": BUILD_PROVIDER_MAP[framework],
                "preview_mode": PREVIEW_MODE_MAP[framework],
                "confidence": confidence,
                "clone_path": clone_path,
            })
        except Exception as exc:
            logger.error("Framework detection failed: %s", exc)


async def start_consumer():
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=5)
    queue = await channel.declare_queue("repo.synced", durable=True)
    await queue.consume(lambda msg: handle_repo_synced(msg, channel))
    logger.info("Consumer started on repo.synced")
    return connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = await start_consumer()
    yield
    await conn.close()


app = FastAPI(title="Framework Detection Service", version="0.1.0", lifespan=lifespan)


class DetectionRequest(BaseModel):
    project_path: str


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "framework-detection",
        "version": "0.9.0",
        "uptime_seconds": int(_time.time() - _START_TIME),
    }


@app.post("/detect")
def detect_framework(req: DetectionRequest):
    framework, confidence = _detect(req.project_path)
    return {
        "framework": framework,
        "build_provider": BUILD_PROVIDER_MAP[framework],
        "preview_mode": PREVIEW_MODE_MAP[framework],
        "confidence": confidence,
    }
