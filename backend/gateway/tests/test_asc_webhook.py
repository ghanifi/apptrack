"""
AppTrack -- App Store Connect Webhook Tests
============================================
Tests for: asc_webhook (POST /api/webhooks/asc)

Router: backend/gateway/app/routers/webhooks.py
Prefix: /api/webhooks (set in main.py include_router)
"""
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.routers.webhooks import router
from app.database import get_db

SECRET = "test-asc-secret"
BUNDLE_ID = "io.apptrack.demo"
DEPLOY_ID = "c0000000-0000-4000-8000-000000000001"
PROJECT_ID = "c0000000-0000-4000-8000-000000000002"


def _sign(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def _payload(new_state: str = "READY_FOR_SALE", bundle_id: str = BUNDLE_ID) -> bytes:
    return json.dumps({
        "data": {
            "type": "appStoreVersionAppVersionStateUpdated",
            "attributes": {"newState": new_state, "bundleId": bundle_id},
        }
    }).encode()


def _build_app(db_override: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/webhooks")
    app.dependency_overrides[get_db] = lambda: db_override
    return app


def _make_db(project_id: str | None = PROJECT_ID, deployment=None,
             nonce_exists: bool = False, with_delivery_id: bool = False):
    """execute() cagrilari sirali doner: [nonce (delivery-id gonderilirse)], StoreMetadata, Deployment."""
    db = AsyncMock()
    results = []

    if with_delivery_id:
        nonce_result = MagicMock()
        nonce_result.scalar_one_or_none.return_value = MagicMock() if nonce_exists else None
        results.append(nonce_result)

    meta_result = MagicMock()
    meta_result.scalar_one_or_none.return_value = project_id
    results.append(meta_result)

    dep_result = MagicMock()
    dep_result.scalar_one_or_none.return_value = deployment
    results.append(dep_result)

    db.execute.side_effect = results
    return db


def _make_deployment():
    dep = MagicMock()
    dep.id = DEPLOY_ID
    dep.status = "processing"
    return dep


async def _post(app, body: bytes, headers: dict):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.post("/api/webhooks/asc", content=body, headers=headers)


@pytest.mark.anyio
class TestAscSignature:
    async def test_missing_secret_returns_503(self):
        app = _build_app(_make_db())
        with patch("app.routers.webhooks.settings") as mock_settings:
            mock_settings.ASC_WEBHOOK_SECRET = ""
            resp = await _post(app, _payload(), {"x-apple-signature": "deadbeef"})
        assert resp.status_code == 503

    async def test_invalid_signature_returns_400(self):
        app = _build_app(_make_db())
        with patch("app.routers.webhooks.settings") as mock_settings:
            mock_settings.ASC_WEBHOOK_SECRET = SECRET
            resp = await _post(app, _payload(), {"x-apple-signature": "kotu-imza"})
        assert resp.status_code == 400

    async def test_sha256_prefixed_signature_accepted(self):
        body = _payload()
        deployment = _make_deployment()
        app = _build_app(_make_db(deployment=deployment))
        with patch("app.routers.webhooks.settings") as mock_settings, \
             patch("app.routers.webhooks.events.publish_event", new_callable=AsyncMock):
            mock_settings.ASC_WEBHOOK_SECRET = SECRET
            resp = await _post(app, body, {"x-apple-signature": "sha256=" + _sign(body)})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.anyio
class TestAscStateMapping:
    async def test_ready_for_sale_publishes_deploy_completed(self):
        body = _payload("READY_FOR_SALE")
        deployment = _make_deployment()
        app = _build_app(_make_db(deployment=deployment))
        with patch("app.routers.webhooks.settings") as mock_settings, \
             patch("app.routers.webhooks.events.publish_event", new_callable=AsyncMock) as mock_pub:
            mock_settings.ASC_WEBHOOK_SECRET = SECRET
            resp = await _post(app, body, {"x-apple-signature": _sign(body)})
        assert resp.status_code == 200
        assert resp.json()["mapped_status"] == "published"
        event_name, event_payload = mock_pub.call_args[0]
        assert event_name == "deploy.completed"
        assert event_payload["deployment_id"] == DEPLOY_ID

    async def test_rejected_publishes_deploy_failed(self):
        body = _payload("REJECTED")
        deployment = _make_deployment()
        app = _build_app(_make_db(deployment=deployment))
        with patch("app.routers.webhooks.settings") as mock_settings, \
             patch("app.routers.webhooks.events.publish_event", new_callable=AsyncMock) as mock_pub:
            mock_settings.ASC_WEBHOOK_SECRET = SECRET
            resp = await _post(app, body, {"x-apple-signature": _sign(body)})
        assert resp.status_code == 200
        event_name, event_payload = mock_pub.call_args[0]
        assert event_name == "deploy.failed"
        assert event_payload["asc_state"] == "REJECTED"

    async def test_intermediate_state_ignored(self):
        body = _payload("WAITING_FOR_REVIEW")
        app = _build_app(_make_db())
        with patch("app.routers.webhooks.settings") as mock_settings, \
             patch("app.routers.webhooks.events.publish_event", new_callable=AsyncMock) as mock_pub:
            mock_settings.ASC_WEBHOOK_SECRET = SECRET
            resp = await _post(app, body, {"x-apple-signature": _sign(body)})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
        mock_pub.assert_not_called()


@pytest.mark.anyio
class TestAscCorrelation:
    async def test_unknown_bundle_id_ignored(self):
        body = _payload("READY_FOR_SALE")
        app = _build_app(_make_db(project_id=None))
        with patch("app.routers.webhooks.settings") as mock_settings, \
             patch("app.routers.webhooks.events.publish_event", new_callable=AsyncMock) as mock_pub:
            mock_settings.ASC_WEBHOOK_SECRET = SECRET
            resp = await _post(app, body, {"x-apple-signature": _sign(body)})
        assert resp.status_code == 200
        assert resp.json()["reason"] == "unknown bundleId"
        mock_pub.assert_not_called()

    async def test_no_active_deployment_ignored(self):
        body = _payload("READY_FOR_SALE")
        app = _build_app(_make_db(deployment=None))
        with patch("app.routers.webhooks.settings") as mock_settings, \
             patch("app.routers.webhooks.events.publish_event", new_callable=AsyncMock) as mock_pub:
            mock_settings.ASC_WEBHOOK_SECRET = SECRET
            resp = await _post(app, body, {"x-apple-signature": _sign(body)})
        assert resp.status_code == 200
        assert resp.json()["reason"] == "no active app_store deployment"
        mock_pub.assert_not_called()

    async def test_duplicate_delivery_id_returns_duplicate(self):
        body = _payload("READY_FOR_SALE")
        app = _build_app(_make_db(nonce_exists=True, with_delivery_id=True))
        with patch("app.routers.webhooks.settings") as mock_settings, \
             patch("app.routers.webhooks.events.publish_event", new_callable=AsyncMock) as mock_pub:
            mock_settings.ASC_WEBHOOK_SECRET = SECRET
            resp = await _post(app, body, {
                "x-apple-signature": _sign(body),
                "x-apple-delivery-id": "delivery-001",
            })
        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicate"
        mock_pub.assert_not_called()
