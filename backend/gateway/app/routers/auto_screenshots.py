"""
Auto Screenshot Capture — Playwright-based automatic store screenshot generation.

Uses headless Chromium to navigate to a user's app URL and capture screenshots
at multiple device viewports matching App Store / Google Play requirements.
Completely free — Playwright is MIT licensed.
"""
import asyncio
import base64
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Project

router = APIRouter()
logger = logging.getLogger(__name__)

# Device presets matching store screenshot specs
DEVICE_PRESETS = {
    "iphone_6_7": {
        "label": "iPhone 15 Pro Max (6.7\")",
        "viewport": {"width": 430, "height": 932},
        "device_scale_factor": 3,
        "output_width": 1290,
        "output_height": 2796,
        "platform": "ios",
        "category": "phone",
    },
    "iphone_6_5": {
        "label": "iPhone 14 Plus (6.5\")",
        "viewport": {"width": 414, "height": 896},
        "device_scale_factor": 3,
        "output_width": 1242,
        "output_height": 2688,
        "platform": "ios",
        "category": "phone",
    },
    "iphone_5_5": {
        "label": "iPhone 8 Plus (5.5\")",
        "viewport": {"width": 414, "height": 736},
        "device_scale_factor": 3,
        "output_width": 1242,
        "output_height": 2208,
        "platform": "ios",
        "category": "phone",
    },
    "ipad_12_9": {
        "label": "iPad Pro 12.9\"",
        "viewport": {"width": 1024, "height": 1366},
        "device_scale_factor": 2,
        "output_width": 2048,
        "output_height": 2732,
        "platform": "ios",
        "category": "tablet",
    },
    "android_phone": {
        "label": "Pixel 7 (Phone)",
        "viewport": {"width": 412, "height": 915},
        "device_scale_factor": 2.625,
        "output_width": 1080,
        "output_height": 2400,
        "platform": "android",
        "category": "phone",
    },
    "android_tablet_7": {
        "label": "7\" Tablet",
        "viewport": {"width": 600, "height": 960},
        "device_scale_factor": 2,
        "output_width": 1200,
        "output_height": 1920,
        "platform": "android",
        "category": "tablet",
    },
    "android_tablet_10": {
        "label": "10\" Tablet (Landscape)",
        "viewport": {"width": 960, "height": 600},
        "device_scale_factor": 2,
        "output_width": 1920,
        "output_height": 1200,
        "platform": "android",
        "category": "tablet",
    },
}


class AutoCaptureRequest(BaseModel):
    url: str
    devices: list[str] = ["android_phone"]
    wait_seconds: float = 2.0
    full_page: bool = False


class CapturedScreenshot(BaseModel):
    device: str
    label: str
    category: str
    width: int
    height: int
    data_uri: str


class AutoCaptureResponse(BaseModel):
    status: str
    screenshots: list[CapturedScreenshot]
    message: str


@router.get("/devices")
async def list_devices():
    """Return available device presets for auto-capture."""
    return {
        device_id: {
            "label": preset["label"],
            "platform": preset["platform"],
            "category": preset["category"],
            "output_width": preset["output_width"],
            "output_height": preset["output_height"],
        }
        for device_id, preset in DEVICE_PRESETS.items()
    }


@router.post("/{project_id}/auto-capture", response_model=AutoCaptureResponse)
async def auto_capture_screenshots(
    project_id: str,
    req: AutoCaptureRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Capture screenshots from a running app URL using headless Chromium.

    Navigates to the provided URL with different device viewports and captures
    screenshots at store-required dimensions. Completely free — uses Playwright.

    Raises:
        400: Invalid device preset or URL
        404: Project not found
        503: Playwright not installed
    """
    # Verify project ownership
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate URL
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    # Validate devices
    invalid = [d for d in req.devices if d not in DEVICE_PRESETS]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown devices: {invalid}. Use GET /devices for available presets.",
        )

    # Clamp wait time
    wait = min(max(req.wait_seconds, 0.5), 10.0)

    # Try to import playwright
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Playwright is not installed. Run: pip install playwright && playwright install chromium",
        )

    screenshots: list[CapturedScreenshot] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for device_id in req.devices:
                preset = DEVICE_PRESETS[device_id]
                context = await browser.new_context(
                    viewport=preset["viewport"],
                    device_scale_factor=preset["device_scale_factor"],
                    is_mobile=preset["category"] == "phone",
                    has_touch=True,
                )
                page = await context.new_page()

                try:
                    await page.goto(req.url, wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(wait)

                    png_bytes = await page.screenshot(
                        full_page=req.full_page,
                        type="png",
                    )
                    b64 = base64.b64encode(png_bytes).decode()
                    data_uri = f"data:image/png;base64,{b64}"

                    screenshots.append(CapturedScreenshot(
                        device=device_id,
                        label=preset["label"],
                        category=preset["category"],
                        width=preset["output_width"],
                        height=preset["output_height"],
                        data_uri=data_uri,
                    ))
                except Exception as exc:
                    logger.warning("Screenshot capture failed for %s: %s", device_id, exc)
                finally:
                    await context.close()

            await browser.close()

    except Exception as exc:
        logger.error("Auto-capture failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Screenshot capture failed: {exc}") from exc

    return AutoCaptureResponse(
        status="success",
        screenshots=screenshots,
        message=f"Captured {len(screenshots)}/{len(req.devices)} screenshots",
    )
