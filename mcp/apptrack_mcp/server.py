"""AppTrack MCP server (stdio).

Claude Code / Cursor gibi AI ajanlarının AppTrack'e bağlanıp proje listeleyip
build tetiklemesini ve durum sorgulamasını sağlar.

Kimlik: AppTrack API anahtarı (Settings → API Keys) — SADECE env'den okunur:
    APPTRACK_API_KEY   (zorunlu, 'atk_' ile başlar)
    APPTRACK_API_URL   (varsayılan http://localhost:8000)

Anahtar doğrudan REST'e gönderilmez; önce /api/api-keys/exchange ile kısa ömürlü
access token'a çevrilir (tüm REST uçları JWT bekler), token süresi dolunca yenilenir.

Kurulum:  pip install "mcp[cli]>=1.28,<2" httpx
Çalıştırma: python -m apptrack_mcp.server
"""
import os
import time

import httpx
from mcp.server.fastmcp import FastMCP

API_URL = os.environ.get("APPTRACK_API_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("APPTRACK_API_KEY", "")

mcp = FastMCP("apptrack")

# Exchange edilen access token önbelleği (süre dolmadan yeniden kullan).
_token: dict = {"value": None, "exp": 0.0}


async def _access_token(client: httpx.AsyncClient) -> str:
    if not API_KEY.startswith("atk_"):
        raise RuntimeError("APPTRACK_API_KEY environment variable not set or invalid (must start with 'atk_')")
    now = time.time()
    if _token["value"] and now < _token["exp"] - 30:
        return _token["value"]
    resp = await client.post(f"{API_URL}/api/api-keys/exchange", json={"api_key": API_KEY})
    if resp.status_code != 200:
        raise RuntimeError(f"API key exchange failed ({resp.status_code}). Check the key is valid and not revoked.")
    data = resp.json()
    _token["value"] = data["access_token"]
    _token["exp"] = now + float(data.get("expires_in", 900))
    return _token["value"]


async def _request(method: str, path: str, **kwargs) -> httpx.Response:
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await _access_token(client)
        resp = await client.request(
            method, f"{API_URL}{path}",
            headers={"Authorization": f"Bearer {token}"},
            **kwargs,
        )
        resp.raise_for_status()
        return resp


@mcp.tool()
async def list_projects() -> list[dict]:
    """List the caller's AppTrack projects with their id, name, framework and status."""
    resp = await _request("GET", "/api/projects")
    body = resp.json()
    items = body.get("items", body) if isinstance(body, dict) else body
    return [
        {"id": p["id"], "name": p["name"], "framework": p.get("framework"), "status": p.get("status")}
        for p in items
    ]


@mcp.tool()
async def get_project(project_id: str) -> dict:
    """Get one AppTrack project's details, including its runner type and recent builds.

    Args:
        project_id: The project ID (from list_projects).
    """
    resp = await _request("GET", f"/api/projects/{project_id}")
    p = resp.json()
    builds = [
        {"id": b["id"], "platform": b.get("platform"), "status": b.get("status"),
         "created_at": b.get("created_at")}
        for b in (p.get("builds") or [])[:10]
    ]
    return {
        "id": p["id"], "name": p["name"], "framework": p.get("framework"),
        "status": p.get("status"), "repo_url": p.get("repo_url"),
        "runner_type": p.get("runner_type", "hosted"), "builds": builds,
    }


@mcp.tool()
async def trigger_build(project_id: str, platform: str = "android") -> dict:
    """Trigger a new build for an AppTrack project. This starts a real CI build.

    Args:
        project_id: The project ID (from list_projects).
        platform: 'android', 'ios', or 'both'.
    """
    resp = await _request("POST", f"/api/projects/{project_id}/build", params={"platform": platform})
    b = resp.json()
    return {"build_id": b.get("id"), "status": b.get("status"), "platform": platform}


@mcp.tool()
async def get_build_status(project_id: str) -> list[dict]:
    """Get the recent builds and their statuses for an AppTrack project.

    Args:
        project_id: The project ID (from list_projects).
    """
    resp = await _request("GET", f"/api/projects/{project_id}")
    p = resp.json()
    return [
        {"id": b["id"], "platform": b.get("platform"), "provider": b.get("provider"),
         "status": b.get("status"), "artifact_url": b.get("artifact_url"),
         "created_at": b.get("created_at")}
        for b in (p.get("builds") or [])[:10]
    ]


def main():
    mcp.run()  # stdio (v1.x varsayılan transport)


if __name__ == "__main__":
    main()
