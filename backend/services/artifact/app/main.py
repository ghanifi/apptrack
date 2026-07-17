import hashlib
import secrets
import json
import logging
import uuid
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from pydantic_settings import BaseSettings
import boto3
from botocore.client import Config
import aio_pika
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, BigInteger, DateTime, select, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID

import time as _time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_START_TIME = _time.time()


class Settings(BaseSettings):
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "artifacts"
    MINIO_PUBLIC_URL: str = "http://localhost:9000"
    SERVICE_TOKEN_SECRET: str = ""
    SIGNED_URL_EXPIRY: int = 3600
    MAX_ARTIFACT_MB: int = 1024  # yükleme boyut tavanı (bellek DoS koruması)
    DATABASE_URL: str = "postgresql+asyncpg://apptrack:apptrack@postgres:5432/apptrack"

    class Config:
        env_file = ".env"


settings = Settings()

_engine = create_async_engine(settings.DATABASE_URL, echo=False)
_SessionFactory = async_sessionmaker(_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("build_id", "platform", name="uq_artifact_build_platform"),
    )

    id: Mapped[str] = mapped_column(PGUUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    build_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(64), default="")
    platform: Mapped[str] = mapped_column(String(20), default="")
    filename: Mapped[Optional[str]] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text)
    checksum: Mapped[Optional[str]] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def _init_db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
        logger.info("Created MinIO bucket: %s", settings.MINIO_BUCKET)


def _compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def start_consumer():
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    logger.info("Artifact service RabbitMQ connected")
    return connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _init_db()
    try:
        ensure_bucket()
    except Exception as exc:
        logger.warning("MinIO bucket init failed (will retry on upload): %s", exc)
    conn = await start_consumer()
    yield
    await conn.close()
    await _engine.dispose()


app = FastAPI(title="Artifact Storage Service", version="0.3.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "artifact",
        "version": "0.9.0",
        "uptime_seconds": int(_time.time() - _START_TIME),
    }


@app.post("/upload")
async def upload_artifact(
    build_id: str,
    platform: str,
    owner_id: str = "",
    file: UploadFile = File(...),
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
):
    # Fail-closed servis-token: MinIO+DB'ye yazan iç uç; kimliksiz erişime kapalı.
    # (Port zaten host'a expose edilmez — bu derinlemesine savunma.)
    if not settings.SERVICE_TOKEN_SECRET:
        raise HTTPException(status_code=503, detail="Artifact upload servis-token doğrulaması yapılandırılmamış")
    if not x_service_token or not secrets.compare_digest(x_service_token, settings.SERVICE_TOKEN_SECRET):
        raise HTTPException(status_code=401, detail="Geçersiz servis token")

    artifact_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "bin"
    tenant_prefix = f"{owner_id}/" if owner_id else ""
    object_key = f"{tenant_prefix}{build_id}/{artifact_id}.{ext}"

    # Boyut tavanı: bellek DoS'una karşı MAX+1 bayta kadar oku, aşarsa reddet.
    max_bytes = settings.MAX_ARTIFACT_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Artifact {settings.MAX_ARTIFACT_MB}MB sınırını aşıyor")

    url = None
    checksum = None
    size = 0

    try:
        ensure_bucket()
        checksum = _compute_checksum(content)
        size = len(content)
        s3 = get_s3()
        s3.put_object(
            Bucket=settings.MINIO_BUCKET,
            Key=object_key,
            Body=content,
            # Saldırgan Content-Type'ı saklamak storage-origin stored-XSS doğurur →
            # her zaman indirmeye zorlayan octet-stream olarak sakla.
            ContentType="application/octet-stream",
            Metadata={"sha256": checksum, "owner_id": owner_id},
        )
        url = f"{settings.MINIO_PUBLIC_URL}/{settings.MINIO_BUCKET}/{object_key}"
    except Exception as exc:
        logger.error("MinIO upload failed: %s", exc)
        content = b""

    async with _SessionFactory() as session:
        artifact = Artifact(
            id=artifact_id,
            build_id=build_id,
            owner_id=owner_id,
            platform=platform,
            filename=file.filename,
            object_key=object_key,
            url=url,
            checksum=checksum,
            size_bytes=size,
            created_at=datetime.utcnow(),
        )
        session.add(artifact)
        await session.commit()

    logger.info("Uploaded artifact %s for build %s (checksum=%s size=%d)", artifact_id, build_id, checksum, size)
    return {
        "id": artifact_id,
        "build_id": build_id,
        "owner_id": owner_id,
        "platform": platform,
        "filename": file.filename,
        "object_key": object_key,
        "url": url,
        "checksum": checksum,
        "size_bytes": size,
        "created_at": datetime.utcnow().isoformat(),
    }


@app.get("/build/{build_id}")
async def get_artifacts_by_build(build_id: str):
    async with _SessionFactory() as session:
        result = await session.execute(select(Artifact).where(Artifact.build_id == build_id))
        artifacts = result.scalars().all()
    return [
        {
            "id": a.id, "build_id": a.build_id, "owner_id": a.owner_id,
            "platform": a.platform, "filename": a.filename,
            "object_key": a.object_key, "url": a.url, "checksum": a.checksum,
            "size_bytes": a.size_bytes, "created_at": a.created_at.isoformat(),
        }
        for a in artifacts
    ]


@app.get("/{artifact_id}/download")
async def download_url(artifact_id: str, owner_id: Optional[str] = None):
    async with _SessionFactory() as session:
        result = await session.execute(select(Artifact).where(Artifact.id == artifact_id))
        artifact = result.scalar_one_or_none()

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if owner_id and artifact.owner_id and artifact.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Access denied — tenant mismatch")

    try:
        s3 = get_s3()
        signed_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.MINIO_BUCKET, "Key": artifact.object_key},
            ExpiresIn=settings.SIGNED_URL_EXPIRY,
        )
        return {"download_url": signed_url, "expires_in": settings.SIGNED_URL_EXPIRY, "checksum": artifact.checksum}
    except Exception as exc:
        logger.error("Presigned URL generation failed: %s", exc)
        return {"download_url": artifact.url, "checksum": artifact.checksum}


@app.get("/{artifact_id}/verify")
async def verify_artifact(artifact_id: str, expected_checksum: Optional[str] = None):
    async with _SessionFactory() as session:
        result = await session.execute(select(Artifact).where(Artifact.id == artifact_id))
        artifact = result.scalar_one_or_none()

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    stored_checksum = artifact.checksum
    if expected_checksum and stored_checksum:
        match = stored_checksum == expected_checksum
        return {"artifact_id": artifact_id, "checksum": stored_checksum, "expected": expected_checksum, "match": match}
    return {"artifact_id": artifact_id, "checksum": stored_checksum, "match": None}
