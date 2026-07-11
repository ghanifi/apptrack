import json
import logging
import uuid
from typing import Any
import aio_pika
from app.config import settings

logger = logging.getLogger(__name__)

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None


async def get_channel() -> aio_pika.abc.AbstractChannel:
    global _connection, _channel
    if _connection is None or _connection.is_closed:
        _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    if _channel is None or _channel.is_closed:
        _channel = await _connection.channel()
    return _channel


async def publish_event(routing_key: str, payload: dict[str, Any], trace_id: str | None = None) -> bool:
    try:
        if "trace_id" not in payload:
            payload["trace_id"] = trace_id or uuid.uuid4().hex

        channel = await get_channel()
        headers = {"x-trace-id": payload.get("trace_id", "")}
        if "owner_id" in payload:
            headers["x-tenant-id"] = payload["owner_id"]

        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                headers=headers,
            ),
            routing_key=routing_key,
        )
        logger.info("Published event %s trace_id=%s", routing_key, payload.get("trace_id"))
        return True
    except Exception as exc:
        logger.error("Failed to publish event %s: %s", routing_key, exc)
        return False


async def close_connection() -> None:
    global _connection
    if _connection and not _connection.is_closed:
        await _connection.close()
