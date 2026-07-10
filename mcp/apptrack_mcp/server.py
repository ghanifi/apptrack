"""AppTrack MCP server (stdio + Streamable HTTP).

Claude Code / Cursor gibi AI ajanlarının AppTrack'e bağlanıp proje listeleyip
build tetiklemesini ve durum sorgulamasını sağlar.

İki mod (MCP_TRANSPORT env):
  stdio (varsayılan)  — anahtar env'den: APPTRACK_API_KEY ('atk_' ile başlar).
  streamable-http     — çoklu istemci; anahtar İSTEK BAŞINA
                        `Authorization: Bearer atk_...` header'ından gelir.
                        MCP_PORT (varsayılan 8010), endpoint: /mcp

Anahtar doğrudan REST'e gönderilmez; önce /api/api-keys/exchange ile kısa ömürlü
access token'a çevrilir (tüm REST uçları JWT bekler), token süresi dolunca yenilenir.

Kurulum:  pip install "mcp[cli]>=1.28,<2" httpx uvicorn
Çalıştırma: python -m apptrack_mcp.server
"""
import contextvars
import json
import os
import time

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

API_URL = os.environ.get("APPTRACK_API_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("APPTRACK_API_KEY", "")
TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")

# stateless_http: her HTTP isteği bağımsız işlenir → contextvar ile istek-başına
# API anahtarı tool'lara güvenle akar.
# DNS-rebinding koruması kapalı: sunucu tarayıcıdan değil, Bearer anahtarlı API
# istemcilerinden çağrılır (kimlik zaten _auth_asgi'de); Host adı deploy'a göre değişir.
mcp = FastMCP("apptrack", stateless_http=True,
              transport_security=TransportSecuritySettings(
                  enable_dns_rebinding_protection=False))

# İstek-başına API anahtarı (HTTP modu). stdio'da None kalır → env kullanılır.
_current_api_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "apptrack_api_key", default=None)

# Anahtar-başına exchange edilmiş access token önbelleği.
_token_cache: dict[str, dict] = {}


def _get_api_key() -> str:
    key = _current_api_key.get() or API_KEY
    if not key.startswith("atk_"):
        raise RuntimeError(
            "AppTrack API key missing/invalid. stdio: set APPTRACK_API_KEY env; "
            "HTTP: send 'Authorization: Bearer atk_...' header.")
    return key


async def _access_token(client: httpx.AsyncClient) -> str:
    api_key = _get_api_key()
    now = time.time()
    cached = _token_cache.get(api_key)
    if cached and now < cached["exp"] - 30:
        return cached["value"]
    resp = await client.post(f"{API_URL}/api/api-keys/exchange", json={"api_key": api_key})
    if resp.status_code != 200:
        raise RuntimeError(f"API key exchange failed ({resp.status_code}). Check the key is valid and not revoked.")
    data = resp.json()
    _token_cache[api_key] = {"value": data["access_token"],
                             "exp": now + float(data.get("expires_in", 900))}
    return _token_cache[api_key]["value"]


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


# ---------------------------------------------------------------------------
# Streamable HTTP: saf ASGI auth middleware
# ---------------------------------------------------------------------------

# Edge'de doğrulanan anahtarların kısa önbelleği (her istekte exchange çağırmamak için).
_valid_keys: dict[str, float] = {}
_VALID_TTL = 300.0


async def _key_is_valid(api_key: str) -> bool:
    now = time.time()
    if _valid_keys.get(api_key, 0) > now:
        return True
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{API_URL}/api/api-keys/exchange", json={"api_key": api_key})
    if resp.status_code == 200:
        _valid_keys[api_key] = now + _VALID_TTL
        data = resp.json()
        _token_cache[api_key] = {"value": data["access_token"],
                                 "exp": now + float(data.get("expires_in", 900))}
        return True
    return False


def _auth_asgi(app):
    """Bearer atk_ anahtarını doğrular, contextvar'a koyar; /health serbest."""
    async def wrapper(scope, receive, send):
        if scope["type"] != "http":
            return await app(scope, receive, send)
        path = scope.get("path", "")
        if path == "/health":
            payload = json.dumps({"status": "healthy", "service": "apptrack-mcp"}).encode()
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": payload})
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        api_key = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
        if not api_key.startswith("atk_") or not await _key_is_valid(api_key):
            body = json.dumps({"error": "unauthorized",
                               "detail": "Send 'Authorization: Bearer atk_...' (AppTrack Settings > API Keys)."}).encode()
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"www-authenticate", b"Bearer")]})
            await send({"type": "http.response.body", "body": body})
            return
        token = _current_api_key.set(api_key)
        try:
            await app(scope, receive, send)
        finally:
            _current_api_key.reset(token)
    return wrapper


def main():
    if TRANSPORT == "streamable-http":
        import uvicorn
        app = _auth_asgi(mcp.streamable_http_app())
        port = int(os.environ.get("MCP_PORT", "8010"))
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    else:
        mcp.run()  # stdio (v1.x varsayılan transport)


if __name__ == "__main__":
    main()
