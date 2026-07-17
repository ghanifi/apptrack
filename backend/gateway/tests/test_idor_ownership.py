"""
IDOR sahiplik regresyon testi (SAST H-C/M-E/M-F düzeltmeleri).

deploy_policies / preview / releases uçları artık kaynağı sahiplik zinciriyle
kapılıyor. Başka birine ait kaynağa erişen kullanıcı 404 almalı. Mock db her
projeyi 'other-owner' sahipli döndürür; istek kullanıcısı 'u-1' → 404.
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from jose import jwt


def _token():
    from app.config import settings
    return jwt.encode({"sub": "u-1", "email": "u@x.io", "name": "U", "type": "access"},
                      settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _mock_db():
    db = AsyncMock()
    proj = MagicMock(owner_id="other-owner", id="p-1")
    build = MagicMock(project_id="p-1", id="b-1")
    dep = MagicMock(build_id="b-1", id="d-1")

    async def _get(model, oid):
        name = getattr(model, "__name__", "")
        return {"Project": proj, "Build": build, "Deployment": dep}.get(name)

    db.get.side_effect = _get
    # releases join sorgusu -> sahip olmadığı için boş
    scalar = MagicMock()
    scalar.scalar_one_or_none.return_value = None
    scalar.scalars.return_value.all.return_value = []
    db.execute.return_value = scalar
    return db


def _app():
    from app.routers import deploy_policies, preview, releases
    from app.database import get_db
    app = FastAPI()
    app.include_router(deploy_policies.router)
    app.include_router(preview.router, prefix="/api/preview")
    app.include_router(releases.router)

    async def _fake_db():
        yield _mock_db()
    app.dependency_overrides[get_db] = _fake_db
    return app


# (method, path) — sahiplik kontrolü eklenen uçlar; hepsi başkasının kaynağı → 404
IDOR_CASES = [
    ("get", "/api/deploy-policies/p-1"),                 # list_policies
    ("put", "/api/deploy-policies/p-1/pol-1"),           # update_policy
    ("delete", "/api/deploy-policies/p-1/pol-1"),        # delete_policy
    ("post", "/api/deploy-policies/evaluate/p-1/b-1"),   # evaluate_policies
    ("post", "/api/deploy-policies/approve/d-1"),        # approve_deployment (sahte oy)
    ("get", "/api/deploy-policies/approvals/d-1"),       # list_approvals
    ("get", "/api/preview/p-1"),                         # get_preview
    ("post", "/api/preview/p-1/start"),                  # start_preview
    ("delete", "/api/preview/p-1"),                      # stop_preview
    ("put", "/api/releases/releases/r-1"),               # update_release_notes
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", IDOR_CASES)
async def test_non_owner_gets_404(method, path):
    app = _app()
    headers = {"Authorization": f"Bearer {_token()}"}
    kwargs = {"headers": headers}
    # gövde gerektiren uçlara minimal JSON
    if method in ("put", "post") and ("policies/p-1/pol-1" in path or path.endswith("/start")
                                       or "approve" in path or path.endswith("/releases/r-1")):
        kwargs["json"] = {"name": "x", "framework": "flutter", "decision": "approved",
                          "policy_type": "approval_required", "rules": {}, "title": "t"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await getattr(ac, method)(path, **kwargs)
    assert resp.status_code == 404, f"{method.upper()} {path} -> {resp.status_code} (404 bekleniyordu)"
