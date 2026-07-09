"""
AppTrack -- Notification Fan-out Tests
======================================
Tests for: dispatch_for_event / _process_notification_event / _resolve_owner_id
(backend/gateway/app/notification_worker.py)

Bildirimler default exchange uzerinden yalnizca gateway worker kuyruklarina
ulastigi icin, gonderim build/deploy islendikten sonra in-process tetiklenir.
Bu testler Slack/Discord webhook'unun gercekten cagrildigini ve sahip cozumunu dogrular.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.notification_worker as nw


class _CtxDB:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *a):
        return False


def _pref(slack=False, discord=False, in_app=False, email=False,
          slack_url="https://hooks.slack.test/x", discord_url="https://discord.test/x"):
    p = MagicMock()
    p.in_app_enabled = in_app
    p.slack_enabled = slack
    p.slack_webhook_url = slack_url
    p.discord_enabled = discord
    p.discord_webhook_url = discord_url
    p.email_enabled = email
    return p


def _db_returning_pref(pref):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = pref
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_build_success_triggers_slack():
    db = _db_returning_pref(_pref(slack=True))
    sent = AsyncMock()
    with patch.object(nw, "AsyncSessionLocal", lambda: _CtxDB(db)), \
         patch.object(nw, "_send_slack", sent):
        await nw.dispatch_for_event(
            {"owner_id": "u1", "build_id": "abcdef1234", "status": "success"},
            "build.finished",
        )
    sent.assert_awaited_once()
    assert sent.await_args.args[0] == "https://hooks.slack.test/x"
    assert "Successful" in sent.await_args.args[1]


@pytest.mark.asyncio
async def test_build_failed_routing_maps_to_failed_title():
    db = _db_returning_pref(_pref(discord=True))
    sent = AsyncMock()
    with patch.object(nw, "AsyncSessionLocal", lambda: _CtxDB(db)), \
         patch.object(nw, "_send_discord", sent):
        # build.failed ayri routing key ile gelir; failed basligina normalize edilmeli
        await nw.dispatch_for_event(
            {"owner_id": "u1", "build_id": "abcdef1234", "error": "boom"},
            "build.failed",
        )
    sent.assert_awaited_once()
    assert "Failed" in sent.await_args.args[1]


@pytest.mark.asyncio
async def test_no_slack_when_disabled():
    db = _db_returning_pref(_pref(slack=False))
    sent = AsyncMock()
    with patch.object(nw, "AsyncSessionLocal", lambda: _CtxDB(db)), \
         patch.object(nw, "_send_slack", sent):
        await nw.dispatch_for_event(
            {"owner_id": "u1", "build_id": "abcdef1234", "status": "success"},
            "build.finished",
        )
    sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_owner_from_project_id():
    db = AsyncMock()
    row = MagicMock()
    row.first.return_value = ("owner-proj",)
    db.execute.return_value = row
    with patch.object(nw, "AsyncSessionLocal", lambda: _CtxDB(db)):
        owner = await nw._resolve_owner_id({"project_id": "p1"})
    assert owner == "owner-proj"


@pytest.mark.asyncio
async def test_resolve_owner_from_deployment_chain():
    db = AsyncMock()
    r1 = MagicMock(); r1.first.return_value = ("p1",)        # Deployment -> Build.project_id
    r2 = MagicMock(); r2.first.return_value = ("owner-dep",)  # Project.owner_id
    db.execute.side_effect = [r1, r2]
    with patch.object(nw, "AsyncSessionLocal", lambda: _CtxDB(db)):
        owner = await nw._resolve_owner_id({"deployment_id": "d1"})
    assert owner == "owner-dep"


@pytest.mark.asyncio
async def test_deploy_completed_triggers_slack():
    db = _db_returning_pref(_pref(slack=True))
    sent = AsyncMock()
    with patch.object(nw, "AsyncSessionLocal", lambda: _CtxDB(db)), \
         patch.object(nw, "_send_slack", sent):
        await nw.dispatch_for_event(
            {"owner_id": "u1", "deployment_id": "dep12345", "target": "google_play"},
            "deploy.completed",
        )
    sent.assert_awaited_once()
    assert "google_play" in sent.await_args.args[2]
