import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from app.config import settings

logger = logging.getLogger(__name__)

MAX_BYTES = settings.MAX_REQUEST_SIZE_MB * 1024 * 1024


class RequestSizeGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BYTES:
            logger.warning(
                "Oversized request rejected: %s bytes from %s %s",
                content_length,
                request.client.host if request.client else "unknown",
                request.url.path,
            )
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large. Maximum size is {settings.MAX_REQUEST_SIZE_MB}MB.",
                    "max_bytes": MAX_BYTES,
                },
            )
        return await call_next(request)
