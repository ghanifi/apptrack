import logging
import uuid
import contextvars
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("apptrack.tracing")

TRACE_HEADER = "X-Trace-Id"
SPAN_HEADER = "X-Span-Id"
PARENT_SPAN_HEADER = "X-Parent-Span-Id"

current_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_trace_id", default="")
current_span_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_span_id", default="")


def generate_trace_id() -> str:
    return uuid.uuid4().hex


def generate_span_id() -> str:
    return uuid.uuid4().hex[:16]


class TraceContextFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = current_trace_id.get("")
        record.span_id = current_span_id.get("")
        return True


class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = request.headers.get(TRACE_HEADER) or generate_trace_id()
        parent_span = request.headers.get(SPAN_HEADER, "")
        span_id = generate_span_id()

        request.state.trace_id = trace_id
        request.state.span_id = span_id
        request.state.parent_span_id = parent_span

        current_trace_id.set(trace_id)
        current_span_id.set(span_id)

        import time
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000

        response.headers[TRACE_HEADER] = trace_id
        response.headers[SPAN_HEADER] = span_id

        logger.info(
            "trace_id=%s span_id=%s parent=%s method=%s path=%s status=%d duration_ms=%.1f",
            trace_id,
            span_id,
            parent_span or "-",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response
