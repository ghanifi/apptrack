import json
import logging
import random
import asyncio
import aio_pika
from sqlalchemy import update, select
from datetime import datetime
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Project, Build, Deployment

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BASE_DELAY = 1.0
MAX_DELAY = 60.0

_retry_counts: dict[str, int] = {}


def _get_retry_key(queue_name: str, payload: dict) -> str:
    return (f"{queue_name}:{payload.get('build_id', '')}:{payload.get('project_id', '')}"
            f":{payload.get('deployment_id', '')}:{payload.get('rollout_id', '')}")


async def _with_retry(message: aio_pika.abc.AbstractIncomingMessage, queue_name: str, handler):
    try:
        payload = json.loads(message.body)
    except Exception:
        logger.error("Unparseable message in %s — sending to DLQ", queue_name)
        await message.nack(requeue=False)
        return

    retry_key = _get_retry_key(queue_name, payload)
    try:
        await handler(payload)
        _retry_counts.pop(retry_key, None)
        await message.ack()
    except Exception as exc:
        count = _retry_counts.get(retry_key, 0) + 1
        _retry_counts[retry_key] = count
        if count >= MAX_RETRIES:
            logger.error(
                "Permanent failure after %d retries in %s: %s — sending to DLQ",
                count, queue_name, exc,
            )
            _retry_counts.pop(retry_key, None)
            await message.nack(requeue=False)
        else:
            delay = min(BASE_DELAY * (2 ** (count - 1)) + random.uniform(0, 1), MAX_DELAY)
            logger.warning(
                "Transient failure in %s (attempt %d/%d): %s — retrying in %.1fs",
                queue_name, count, MAX_RETRIES, exc, delay,
            )
            await asyncio.sleep(delay)
            await message.nack(requeue=True)


async def _process_framework_detected(payload: dict):
    project_id = payload["project_id"]
    framework = payload["framework"]
    clone_path = payload.get("clone_path")
    logger.info("Framework detected for project %s: %s", project_id, framework)
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Project)
            .where(Project.id == project_id)
            .values(framework=framework, status="ready", clone_path=clone_path, updated_at=datetime.utcnow())
        )
        await db.commit()


async def _process_repo_sync_failed(payload: dict):
    project_id = payload.get("project_id")
    logger.warning("Repo sync failed for project %s: %s", project_id, payload.get("error"))
    if project_id:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(status="error", updated_at=datetime.utcnow())
            )
            await db.commit()


async def _process_build_started(payload: dict):
    build_id = payload.get("build_id")
    external_id = payload.get("external_build_id")
    if build_id:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Build)
                .where(Build.id == build_id)
                .values(status="running", external_build_id=external_id, started_at=datetime.utcnow())
            )
            await db.commit()


async def _process_build_finished(payload: dict):
    build_id = payload.get("build_id")
    external_build_id = payload.get("external_build_id")
    project_id = payload.get("project_id")
    status = payload.get("status", "success")
    artifact_url = payload.get("artifact_url")
    artifact_checksum = payload.get("artifact_checksum")

    if not build_id and not external_build_id:
        logger.error(
            "build.finished message has neither build_id nor external_build_id — discarding: %s",
            payload,
        )
        return

    async with AsyncSessionLocal() as db:
        if not build_id and external_build_id:
            result = await db.execute(
                select(Build).where(Build.external_build_id == external_build_id)
            )
            build = result.scalar_one_or_none()
            if build:
                build_id = build.id
                if not project_id:
                    project_id = build.project_id
                logger.info("Resolved external_build_id=%s -> build_id=%s", external_build_id, build_id)
            else:
                logger.warning("No build found for external_build_id=%s", external_build_id)

        if build_id:
            vals = dict(status=status, artifact_url=artifact_url, finished_at=datetime.utcnow())
            if artifact_checksum:
                vals["artifact_checksum"] = artifact_checksum
            if isinstance(payload.get("artifact_signature"), dict):
                vals["artifact_signature"] = payload["artifact_signature"]
            await db.execute(update(Build).where(Build.id == build_id).values(**vals))
        if project_id:
            new_status = "ready" if status == "success" else "error"
            await db.execute(
                update(Project).where(Project.id == project_id).values(status=new_status, updated_at=datetime.utcnow())
            )
        await db.commit()
        logger.info(
            "Build finished: build_id=%s status=%s artifact=%s checksum=%s trace_id=%s",
            build_id, status, artifact_url, artifact_checksum, payload.get("trace_id"),
        )

        # WebSocket broadcast for build progress
        try:
            from app.ws import broadcast_build_progress
            await broadcast_build_progress(build_id, {
                "build_id": build_id,
                "status": status,
                "artifact_url": artifact_url,
                "finished_at": datetime.utcnow().isoformat(),
            })
        except Exception as ws_exc:
            logger.debug("WebSocket broadcast failed for build %s: %s", build_id, ws_exc)

        if status == "success" and build_id:
            # Cost recording with retry
            _MAX_COST_RETRIES = 3
            for _attempt in range(_MAX_COST_RETRIES):
                try:
                    from app.cost_guard import record_build_cost
                    result = await db.execute(select(Build).where(Build.id == build_id))
                    finished_build = result.scalar_one_or_none()
                    if finished_build:
                        # record_build_cost imzası: (db, user_id, provider, platform).
                        # Eski çağrı (db, build) her seferinde TypeError atıyordu →
                        # maliyet hiç kaydedilmiyor, aylık bütçe cap'i uygulanmıyordu.
                        proj_res = await db.execute(
                            select(Project).where(Project.id == finished_build.project_id)
                        )
                        project = proj_res.scalar_one_or_none()
                        if project:
                            await record_build_cost(
                                db, project.owner_id, finished_build.provider, finished_build.platform
                            )
                    break
                except Exception as cost_exc:
                    if _attempt == _MAX_COST_RETRIES - 1:
                        logger.error(
                            "Cost recording FAILED after %d attempts for build %s: %s — MANUAL REVIEW REQUIRED",
                            _MAX_COST_RETRIES, build_id, cost_exc
                        )
                    else:
                        await asyncio.sleep(2 ** _attempt)

        try:
            from app.main import BUILD_RESULT_COUNTER, BUILD_DURATION
            provider = payload.get("provider", "unknown")
            BUILD_RESULT_COUNTER.labels(status=status, provider=provider).inc()
            duration = payload.get("duration_seconds")
            if duration:
                BUILD_DURATION.labels(provider=provider).observe(float(duration))
        except Exception as exc:
            logger.warning("Metrics recording failed for build %s: %s", build_id, exc)

    from app.notification_worker import dispatch_for_event
    await dispatch_for_event(payload, "build.finished")


async def _process_build_failed(payload: dict):
    build_id = payload.get("build_id")
    project_id = payload.get("project_id")
    error_text = payload.get("error")
    async with AsyncSessionLocal() as db:
        if build_id:
            values = {"status": "failed", "finished_at": datetime.utcnow()}
            if error_text:
                # Hata nedeni diagnosis'in okuduğu log_output alanına yazılır;
                # aksi halde UI "No build log output available" gösterir.
                values["log_output"] = error_text
            await db.execute(
                update(Build).where(Build.id == build_id).values(**values)
            )
        if project_id:
            await db.execute(
                update(Project).where(Project.id == project_id)
                .values(status="error", updated_at=datetime.utcnow())
            )
        await db.commit()

    from app.notification_worker import dispatch_for_event
    await dispatch_for_event(payload, "build.failed")


async def _process_deploy_completed(payload: dict):
    deployment_id = payload.get("deployment_id")
    status = payload.get("status", "published")
    logger.info("Deploy completed: %s status=%s", deployment_id, status)
    if deployment_id:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Deployment)
                .where(Deployment.id == deployment_id)
                .values(status=status, updated_at=datetime.utcnow())
            )
            await db.commit()

        try:
            from app.ws import broadcast_deployment_status
            await broadcast_deployment_status(deployment_id, {
                "deployment_id": deployment_id,
                "status": status,
                "updated_at": datetime.utcnow().isoformat(),
            })
        except Exception as ws_exc:
            logger.debug("WebSocket broadcast failed for deployment %s: %s", deployment_id, ws_exc)

        try:
            from app.main import DEPLOY_RESULT_COUNTER
            target = payload.get("target", "unknown")
            DEPLOY_RESULT_COUNTER.labels(target=target, status=status).inc()
        except Exception as exc:
            logger.warning("Metrics recording failed for deployment %s: %s", deployment_id, exc)

    from app.notification_worker import dispatch_for_event
    await dispatch_for_event(payload, "deploy.completed")


async def _process_deploy_failed(payload: dict):
    deployment_id = payload.get("deployment_id")
    logger.error("Deploy failed: %s — %s", deployment_id, payload.get("error"))
    if deployment_id:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Deployment)
                .where(Deployment.id == deployment_id)
                .values(status="failed", updated_at=datetime.utcnow())
            )
            # Staged deploy başarısızsa bağlı rollout sonsuza dek in_progress kalmasın (F3).
            from app.models import ReleaseRollout as _RR
            await db.execute(
                update(_RR).where(_RR.deployment_id == deployment_id, _RR.state == "in_progress")
                .values(state="failed", last_error=str(payload.get("error", ""))[:500],
                        updated_at=datetime.utcnow())
            )
            await db.commit()

    try:
        from app.main import DEPLOY_FAILURE_COUNTER
        target = payload.get("target", "unknown")
        reason = payload.get("error_code", "unknown")
        DEPLOY_FAILURE_COUNTER.labels(target=target, reason=reason).inc()
    except Exception as exc:
        logger.warning("Metrics recording failed for deployment %s: %s", deployment_id, exc)

    from app.notification_worker import dispatch_for_event
    await dispatch_for_event(payload, "deploy.failed")


async def _process_rollout_event(payload: dict, routing_key: str):
    """store-deploy'un rollout sonuç event'lerini ReleaseRollout DB'sine işler."""
    from app.models import ReleaseRollout
    rollout_id = payload.get("rollout_id")
    if not rollout_id:
        return
    values: dict = {"updated_at": datetime.utcnow()}
    if routing_key == "deploy.rollout.started":
        values["state"] = "in_progress"
        values["last_error"] = None
        if payload.get("fraction") is not None:
            values["current_fraction"] = float(payload["fraction"])
        if payload.get("release_version"):
            values["release_version"] = str(payload["release_version"])
        if payload.get("external_ref"):
            values["external_ref"] = str(payload["external_ref"])
    elif routing_key == "deploy.rollout.advanced":
        values["last_error"] = None
        if payload.get("fraction") is not None:
            values["current_fraction"] = float(payload["fraction"])
        if payload.get("completed"):
            values["state"] = "completed"
    elif routing_key == "deploy.rollout.halted":
        values["state"] = "halted"
        values["last_error"] = None
        if payload.get("reason"):
            values["halted_reason"] = payload["reason"]
    elif routing_key == "deploy.rollout.error":
        # Store işlemi BAŞARISIZ — iyimser DB güncellemesini geri al, kullanıcıyı uyar.
        # Aksi hâlde UI "durduruldu/ilerledi" der ama store'da hiçbir şey olmamıştır.
        error = payload.get("error", "unknown")
        op = payload.get("op", "?")
        logger.error("Rollout %s store op '%s' error: %s", rollout_id, op, error)
        values["last_error"] = f"Store işlemi başarısız ({op}): {error}"[:500]
        if payload.get("prev_state"):
            values["state"] = payload["prev_state"]
        if payload.get("prev_fraction") is not None:
            values["current_fraction"] = float(payload["prev_fraction"])
        async with AsyncSessionLocal() as db:
            await db.execute(update(ReleaseRollout).where(ReleaseRollout.id == rollout_id).values(**values))
            row = (await db.execute(select(ReleaseRollout).where(ReleaseRollout.id == rollout_id))).scalar_one_or_none()
            await db.commit()
        from app.notification_worker import dispatch_for_event
        await dispatch_for_event({
            "rollout_id": rollout_id, "project_id": row.project_id if row else None,
            "op": op, "error": error,
        }, "rollout.error")
        return
    async with AsyncSessionLocal() as db:
        await db.execute(update(ReleaseRollout).where(ReleaseRollout.id == rollout_id).values(**values))
        await db.commit()
    logger.info("Rollout %s updated from %s", rollout_id, routing_key)


async def handle_rollout_started(message: aio_pika.abc.AbstractIncomingMessage):
    await _with_retry(message, "deploy.rollout.started",
                      lambda p: _process_rollout_event(p, "deploy.rollout.started"))


async def handle_rollout_advanced(message: aio_pika.abc.AbstractIncomingMessage):
    await _with_retry(message, "deploy.rollout.advanced",
                      lambda p: _process_rollout_event(p, "deploy.rollout.advanced"))


async def handle_rollout_halted(message: aio_pika.abc.AbstractIncomingMessage):
    await _with_retry(message, "deploy.rollout.halted",
                      lambda p: _process_rollout_event(p, "deploy.rollout.halted"))


async def handle_rollout_error(message: aio_pika.abc.AbstractIncomingMessage):
    await _with_retry(message, "deploy.rollout.error",
                      lambda p: _process_rollout_event(p, "deploy.rollout.error"))


async def handle_framework_detected(message: aio_pika.abc.AbstractIncomingMessage):
    await _with_retry(message, "framework.detected", _process_framework_detected)


async def handle_repo_sync_failed(message: aio_pika.abc.AbstractIncomingMessage):
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body)
            await _process_repo_sync_failed(payload)
        except Exception as exc:
            logger.error("Failed to handle repo.sync_failed: %s", exc)


async def _process_build_progress(payload: dict):
    """Canlı ilerlemeyi yalnızca WS'e yayınlar — DB'ye dokunmaz (yüksek frekanslı, geçici)."""
    build_id = payload.get("build_id")
    if not build_id:
        return
    try:
        from app.ws import broadcast_build_progress
        await broadcast_build_progress(build_id, {
            "build_id": build_id,
            "run_status": payload.get("run_status", ""),
            "html_url": payload.get("html_url", ""),
            "elapsed_seconds": payload.get("elapsed_seconds", 0),
            "steps": payload.get("steps", []),
        })
    except Exception as ws_exc:
        logger.debug("WebSocket progress broadcast failed for build %s: %s", build_id, ws_exc)


async def handle_build_progress(message: aio_pika.abc.AbstractIncomingMessage):
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body)
            await _process_build_progress(payload)
        except Exception as exc:
            logger.error("Failed to handle build.progress: %s", exc)


async def handle_build_started(message: aio_pika.abc.AbstractIncomingMessage):
    await _with_retry(message, "build.started", _process_build_started)


async def handle_build_finished(message: aio_pika.abc.AbstractIncomingMessage):
    await _with_retry(message, "build.finished", _process_build_finished)


async def handle_build_failed(message: aio_pika.abc.AbstractIncomingMessage):
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body)
            await _process_build_failed(payload)
        except Exception as exc:
            logger.error("Failed to handle build.failed: %s", exc)


async def handle_deploy_completed(message: aio_pika.abc.AbstractIncomingMessage):
    await _with_retry(message, "deploy.completed", _process_deploy_completed)


async def handle_deploy_failed(message: aio_pika.abc.AbstractIncomingMessage):
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body)
            await _process_deploy_failed(payload)
        except Exception as exc:
            logger.error("Failed to handle deploy.failed: %s", exc)


async def start_event_worker():
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    dlx = await channel.declare_exchange("dlx", aio_pika.ExchangeType.DIRECT, durable=True)
    dlq = await channel.declare_queue("dead_letter_queue", durable=True)
    await dlq.bind(dlx)

    queue_args = {
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "dead_letter_queue",
        "x-message-ttl": 86400000,
    }

    queues = {
        "framework.detected": handle_framework_detected,
        "repo.sync_failed": handle_repo_sync_failed,
        "build.started": handle_build_started,
        "build.progress": handle_build_progress,
        "build.finished": handle_build_finished,
        "build.failed": handle_build_failed,
        "deploy.completed": handle_deploy_completed,
        "deploy.failed": handle_deploy_failed,
        "deploy.rollout.started": handle_rollout_started,
        "deploy.rollout.advanced": handle_rollout_advanced,
        "deploy.rollout.halted": handle_rollout_halted,
        "deploy.rollout.error": handle_rollout_error,
    }

    for queue_name, handler in queues.items():
        q = await channel.declare_queue(queue_name, durable=True, arguments=queue_args)
        await q.consume(handler)

    logger.info("Gateway event worker started — listening on %s", list(queues.keys()))
    return connection
