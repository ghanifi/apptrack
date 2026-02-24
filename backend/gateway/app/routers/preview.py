import httpx
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_current_user

router = APIRouter()

PREVIEW_SERVICE_URL = "http://preview-service:8005"


@router.get("/{project_id}")
async def get_preview(
    project_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{PREVIEW_SERVICE_URL}/preview/{project_id}")
            if resp.status_code == 200:
                return resp.json()
            return {"status": "not_ready"}
    except Exception:
        return {"status": "not_ready"}
