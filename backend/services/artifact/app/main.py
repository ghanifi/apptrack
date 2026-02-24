import json
import hashlib
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from typing import Optional
from pydantic_settings import BaseSettings
import boto3
from botocore.client import Config
import aio_pika

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "artifacts"
    MINIO_PUBLIC_URL: str = "http://localhost:9000"
    SERVICE_TOKEN_SECRET: str = ""
    SIGNED_URL_EXPIRY: int = 3600

    class Config:
        env_file = ".env"


settings = Settings()
ARTIFACTS_META: dict = {}


def get_s3():
    return boto3.client(
        "s3",
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket():
    s3 = get_s3()
    try:
        s3.head_bucket(Bucket=settings.MINIO_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=settings.MINIO_BUCKET)
        s3.put_bucket_policy(
            Bucket=settings.MINIO_BUCKET,
            Policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{settings.MINIO_BUCKET}/*"],
                }],
            }),
        )
        logger.info("Created MinIO bucket: %s", settings.MINIO_BUCKET)


def _compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def publish_event(channel: aio_pika.abc.AbstractChannel, routing_key: str, payload: dict) -> None:
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=routing_key,
    )


async def start_consumer():
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    logger.info("Artifact service RabbitMQ connected")
    return connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_bucket()
    except Exception as exc:
        logger.warning("MinIO bucket init failed (will retry on upload): %s", exc)
    conn = await start_consumer()
    yield
    await conn.close()


app = FastAPI(title="Artifact Storage Service", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "artifact", "version": "0.2.0"}


@app.post("/upload")
async def upload_artifact(
    build_id: str,
    platform: str,
    owner_id: str = "",
    file: UploadFile = File(...),
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
):
    artifact_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "bin"
    tenant_prefix = f"{owner_id}/" if owner_id else ""
    object_key = f"{tenant_prefix}{build_id}/{artifact_id}.{ext}"

    try:
        ensure_bucket()
        content = await file.read()
        checksum = _compute_checksum(content)
        s3 = get_s3()
        s3.put_object(
            Bucket=settings.MINIO_BUCKET,
            Key=object_key,
            Body=content,
            ContentType=file.content_type or "application/octet-stream",
            Metadata={"sha256": checksum, "owner_id": owner_id},
        )
        url = f"{settings.MINIO_PUBLIC_URL}/{settings.MINIO_BUCKET}/{object_key}"
    except Exception as exc:
        logger.error("MinIO upload failed: %s", exc)
        url = None
        checksum = None

    artifact = {
        "id": artifact_id,
        "build_id": build_id,
        "owner_id": owner_id,
        "platform": platform,
        "filename": file.filename,
        "object_key": object_key,
        "url": url,
        "checksum": checksum,
        "size_bytes": len(content) if url else 0,
        "created_at": datetime.utcnow().isoformat(),
    }
    ARTIFACTS_META[artifact_id] = artifact
    logger.info("Uploaded artifact %s for build %s (checksum=%s, size=%d)", artifact_id, build_id, checksum, artifact.get("size_bytes", 0))
    return artifact


@app.get("/build/{build_id}")
def get_artifacts_by_build(build_id: str):
    return [a for a in ARTIFACTS_META.values() if a["build_id"] == build_id]


@app.get("/{artifact_id}/download")
def download_url(artifact_id: str, owner_id: Optional[str] = None):
    artifact = ARTIFACTS_META.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if owner_id and artifact.get("owner_id") and artifact["owner_id"] != owner_id:
        raise HTTPException(status_code=403, detail="Access denied — tenant mismatch")
    try:
        s3 = get_s3()
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.MINIO_BUCKET, "Key": artifact["object_key"]},
            ExpiresIn=settings.SIGNED_URL_EXPIRY,
        )
        return {"download_url": url, "expires_in": settings.SIGNED_URL_EXPIRY, "checksum": artifact.get("checksum")}
    except Exception as exc:
        logger.error("Presigned URL generation failed: %s", exc)
        return {"download_url": artifact.get("url"), "checksum": artifact.get("checksum")}


@app.get("/{artifact_id}/verify")
def verify_artifact(artifact_id: str, expected_checksum: Optional[str] = None):
    artifact = ARTIFACTS_META.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    stored_checksum = artifact.get("checksum")
    if expected_checksum and stored_checksum:
        match = stored_checksum == expected_checksum
        return {"artifact_id": artifact_id, "checksum": stored_checksum, "expected": expected_checksum, "match": match}
    return {"artifact_id": artifact_id, "checksum": stored_checksum, "match": None}
