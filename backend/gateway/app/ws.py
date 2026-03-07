import json
import logging
import asyncio
from datetime import datetime
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._user_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str, channels: list[str]):
        await websocket.accept()
        if user_id not in self._user_connections:
            self._user_connections[user_id] = []
        self._user_connections[user_id].append(websocket)

        for channel in channels:
            if channel not in self._connections:
                self._connections[channel] = []
            self._connections[channel].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str, channels: list[str]):
        if user_id in self._user_connections:
            self._user_connections[user_id] = [
                ws for ws in self._user_connections[user_id] if ws != websocket
            ]
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]

        for channel in channels:
            if channel in self._connections:
                self._connections[channel] = [
                    ws for ws in self._connections[channel] if ws != websocket
                ]
                if not self._connections[channel]:
                    del self._connections[channel]

    async def broadcast_to_channel(self, channel: str, data: dict[str, Any]):
        message = json.dumps({"channel": channel, "data": data, "timestamp": datetime.utcnow().isoformat()})
        connections = self._connections.get(channel, [])
        disconnected = []
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            if channel in self._connections:
                self._connections[channel] = [c for c in self._connections[channel] if c != ws]

    async def send_to_user(self, user_id: str, data: dict[str, Any]):
        message = json.dumps({"channel": f"user.{user_id}", "data": data, "timestamp": datetime.utcnow().isoformat()})
        connections = self._user_connections.get(user_id, [])
        disconnected = []
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            if user_id in self._user_connections:
                self._user_connections[user_id] = [c for c in self._user_connections[user_id] if c != ws]

    @property
    def active_connections_count(self) -> int:
        return sum(len(conns) for conns in self._user_connections.values())


manager = ConnectionManager()


def _verify_ws_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") not in ("access", None):
            return None
        return {"id": payload["sub"], "email": payload.get("email", "")}
    except JWTError:
        return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    channels: str = Query(default=""),
):
    user = _verify_ws_token(token)
    if not user:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id = user["id"]
    channel_list = [c.strip() for c in channels.split(",") if c.strip()] if channels else []
    channel_list.append(f"notifications.{user_id}")

    await manager.connect(websocket, user_id, channel_list)
    logger.info("WebSocket connected: user=%s channels=%s", user_id, channel_list)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                action = msg.get("action")
                if action == "subscribe":
                    new_channel = msg.get("channel", "")
                    if new_channel and new_channel not in channel_list:
                        channel_list.append(new_channel)
                        if new_channel not in manager._connections:
                            manager._connections[new_channel] = []
                        manager._connections[new_channel].append(websocket)
                        await websocket.send_text(json.dumps({"type": "subscribed", "channel": new_channel}))

                elif action == "unsubscribe":
                    old_channel = msg.get("channel", "")
                    if old_channel in channel_list:
                        channel_list.remove(old_channel)
                        if old_channel in manager._connections:
                            manager._connections[old_channel] = [
                                c for c in manager._connections[old_channel] if c != websocket
                            ]

                elif action == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id, channel_list)
        logger.info("WebSocket disconnected: user=%s", user_id)


async def broadcast_build_progress(build_id: str, data: dict):
    await manager.broadcast_to_channel(f"build.{build_id}.progress", data)


async def broadcast_deployment_status(deployment_id: str, data: dict):
    await manager.broadcast_to_channel(f"deployment.{deployment_id}.status", data)


async def broadcast_notification(user_id: str, data: dict):
    await manager.send_to_user(user_id, {
        "type": "notification",
        **data,
    })
