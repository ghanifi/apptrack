import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.tenant_id = None
        response = await call_next(request)
        return response


def inject_tenant(request: Request, user: dict) -> None:
    request.state.tenant_id = user.get("id")


def get_tenant_id(request: Request) -> str | None:
    return getattr(request.state, "tenant_id", None)
