"""Request ID middleware for request correlation."""

import uuid

import sentry_sdk
import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate or propagate a request ID for every HTTP request.

    - Accepts X-Request-ID from the incoming request, or generates a UUID4.
    - Binds request_id to structlog contextvars so all logs in the request include it.
    - Attaches request_id to Sentry scope for cross-system correlation.
    - Adds X-Request-ID to the response headers.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        scope = sentry_sdk.get_current_scope()
        scope.set_context("correlation", {"request_id": request_id})

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
