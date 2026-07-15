"""Agentic autofix endpoint guard testleri (sahiplik + LLM config). Arka plan görevi
orkestratör unit testlerinde kapsanır; burada sadece senkron guard yolları test edilir."""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies import get_current_user


@pytest.mark.asyncio
async def test_agentic_status_404_for_unknown_job():
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/build-diagnosis/autofix/status/does-not-exist")
    app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_agentic_status_owner_isolation():
    """Başka kullanıcının job_id'si 404 döner (owner_id eşleşmezse)."""
    from app.routers import build_autofix_jobs as mod
    mod._JOBS["job-x"] = {"owner_id": "owner-a", "state": "running", "steps": [],
                          "pr_url": None, "error": None, "created_at": 0.0}
    app.dependency_overrides[get_current_user] = lambda: {"id": "owner-b"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/build-diagnosis/autofix/status/job-x")
    app.dependency_overrides.clear()
    mod._JOBS.pop("job-x", None)
    assert r.status_code == 404
