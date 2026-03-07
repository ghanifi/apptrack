import asyncio
import json
import logging
import os
import shutil
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic_settings import BaseSettings
import aio_pika
import git

import time as _time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_START_TIME = _time.time()


class Settings(BaseSettings):
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    CLONE_BASE_DIR: str = "/tmp/repos"
    GATEWAY_URL: str = "http://gateway:8000"
    SECRET_KEY: str = "dev-secret-key"
    FERNET_SALT: str = "apptrack-fernet-salt-change-me"

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


def _inject_token(repo_url: str, token: str) -> str:
    if "github.com" in repo_url:
        return repo_url.replace("https://github.com", f"https://{token}@github.com")
    return repo_url


def _mask_url(url: str) -> str:
    """Remove tokens from URL for safe logging."""
    import re
    return re.sub(r"https://[^@]+@", "https://***@", url)


def clone_or_pull(repo_url: str, branch: str, dest: str, github_token: str | None = None) -> str:
    clone_url = _inject_token(repo_url, github_token) if github_token else repo_url
    safe_url = _mask_url(clone_url)
    if os.path.exists(dest):
        try:
            repo = git.Repo(dest)
            origin = repo.remotes.origin
            origin.fetch()
            repo.git.checkout(branch)
            origin.pull()
            logger.info("Pulled repo %s branch %s", safe_url, branch)
        except Exception as exc:
            logger.warning("Pull failed (%s), re-cloning", exc)
            shutil.rmtree(dest, ignore_errors=True)
            git.Repo.clone_from(clone_url, dest, branch=branch, depth=1)
    else:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        git.Repo.clone_from(clone_url, dest, branch=branch, depth=1)
        logger.info("Cloned %s to %s", safe_url, dest)
    return dest


async def handle_project_created(message: aio_pika.abc.AbstractIncomingMessage, channel: aio_pika.abc.AbstractChannel):
    async with message.process(requeue=True):
        try:
            payload = json.loads(message.body)
            project_id = payload["project_id"]
            repo_url = payload["repo_url"]
            branch = payload.get("branch", "main")
            dest = os.path.join(settings.CLONE_BASE_DIR, project_id)

            # Decrypt GitHub token if present (received encrypted from gateway)
            github_token = None
            encrypted_token = payload.get("github_token")
            if encrypted_token:
                try:
                    from app.crypto import decrypt as decrypt_token
                    github_token = decrypt_token(encrypted_token, settings.SECRET_KEY, settings.FERNET_SALT)
                except Exception as exc:
                    logger.warning("Failed to decrypt github_token: %s", exc)

            logger.info("Syncing project %s from %s", project_id, repo_url)
            loop = asyncio.get_event_loop()
            clone_path = await loop.run_in_executor(None, clone_or_pull, repo_url, branch, dest, github_token)

            await publish_event(channel, "repo.synced", {
                "project_id": project_id,
                "clone_path": clone_path,
                "repo_url": repo_url,
                "branch": branch,
            })
        except Exception as exc:
            logger.error("Failed to sync: %s", exc)
            p = json.loads(message.body) if message.body else {}
            await publish_event(channel, "repo.sync_failed", {
                "project_id": p.get("project_id"),
                "error": str(exc),
            })


async def start_consumer():
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=5)
    queue = await channel.declare_queue("project.created", durable=True)
    await queue.consume(lambda msg: handle_project_created(msg, channel))
    logger.info("Consumer started on project.created")
    return connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = await start_consumer()
    yield
    await conn.close()


app = FastAPI(title="Repo Sync Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "repo-sync",
        "version": "0.9.0",
        "uptime_seconds": int(_time.time() - _START_TIME),
    }


@app.post("/sync")
async def manual_sync(repo_url: str, branch: str = "main", project_id: str = "manual"):
    dest = os.path.join(settings.CLONE_BASE_DIR, project_id)
    loop = asyncio.get_event_loop()
    clone_path = await loop.run_in_executor(None, clone_or_pull, repo_url, branch, dest)
    return {"status": "synced", "clone_path": clone_path}
