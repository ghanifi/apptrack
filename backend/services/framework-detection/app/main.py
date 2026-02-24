import json
import logging
import os
import glob as glob_module
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import aio_pika

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    CLONE_BASE_DIR: str = "/tmp/repos"

    class Config:
        env_file = ".env"


settings = Settings()

FRAMEWORK_RULES = [
    ("flutter", ["pubspec.yaml"], 0.98),
    ("expo", ["app.json", "app.config.js", "app.config.ts"], 0.97),
    ("react_native", ["package.json"], 0.85),
    ("kotlin", ["build.gradle", "build.gradle.kts"], 0.97),
    ("swift", [".xcodeproj", ".xcworkspace"], 0.97),
]

BUILD_PROVIDER_MAP = {
    "flutter": "codemagic",
    "expo": "eas",
    "react_native": "eas",
    "swift": "github_actions",
    "kotlin": "github_actions",
    "unknown": "github_actions",
}

PREVIEW_MODE_MAP = {
    "flutter": "web",
    "expo": "expo_preview",
    "react_native": "expo_preview",
    "swift": "simulator",
    "kotlin": "simulator",
    "unknown": "none",
}


def _detect(project_path: str) -> tuple[str, float]:
    for framework, indicators, confidence in FRAMEWORK_RULES:
        for indicator in indicators:
            pattern = os.path.join(project_path, "**", indicator)
            matches = glob_module.glob(pattern, recursive=True)
            if matches:
                if framework == "react_native":
                    for m in matches:
                        try:
                            with open(m) as f:
                                pkg = json.load(f)
                            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                            if "react-native" in deps:
                                return "react_native", confidence
                            if "expo" in deps:
                                return "expo", confidence
                        except Exception:
                            pass
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
    return {"status": "ok", "service": "framework-detection"}


@app.post("/detect")
def detect_framework(req: DetectionRequest):
    framework, confidence = _detect(req.project_path)
    return {
        "framework": framework,
        "build_provider": BUILD_PROVIDER_MAP[framework],
        "preview_mode": PREVIEW_MODE_MAP[framework],
        "confidence": confidence,
    }
