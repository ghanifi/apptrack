import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.dependencies import get_current_user

router = APIRouter()

PREVIEW_SERVICE_URL = "http://preview-service:8005"


class PreviewStartRequest(BaseModel):
    framework: str
    project_path: str = ""


@router.get("/{project_id}")
async def get_preview(
    project_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Projenin önizleme durumunu sorgular.

    Preview servisinden projenin mevcut önizleme oturum bilgisini getirir.
    Servis erişilemezse veya önizleme yoksa 'not_ready' durumu döner.

    Raises:
        401: Kimlik doğrulama gerekli
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{PREVIEW_SERVICE_URL}/preview/{project_id}")
            if resp.status_code == 200:
                return resp.json()
            return {"status": "not_ready"}
    except Exception:
        return {"status": "not_ready"}


@router.post("/{project_id}/start")
async def start_preview(
    project_id: str,
    req: PreviewStartRequest,
    current_user: dict = Depends(get_current_user),
):
    """Proje için canlı önizleme oturumu başlatır.

    Preview servisine framework ve proje yolu bilgisiyle başlatma isteği gönderir.
    Servis kullanılamıyorsa 503 hatası döner.

    Raises:
        401: Kimlik doğrulama gerekli
        503: Preview servisi erişilemez
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{PREVIEW_SERVICE_URL}/start",
                json={"project_id": project_id, "framework": req.framework, "project_path": req.project_path},
            )
            if resp.status_code == 200:
                return resp.json()
            raise HTTPException(status_code=resp.status_code, detail="Preview service error")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Preview service unavailable: {exc}")


@router.delete("/{project_id}")
async def stop_preview(
    project_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Projenin aktif önizleme oturumunu durdurur.

    Preview servisine durdurma isteği göndererek kaynakları serbest bırakır.
    Servis kullanılamıyorsa 503 hatası döner.

    Raises:
        401: Kimlik doğrulama gerekli
        503: Preview servisi erişilemez
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(f"{PREVIEW_SERVICE_URL}/{project_id}")
            if resp.status_code == 200:
                return resp.json()
            raise HTTPException(status_code=resp.status_code, detail="Preview service error")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Preview service unavailable: {exc}")
