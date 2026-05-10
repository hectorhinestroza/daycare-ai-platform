"""Middleware for structured logging, request IDs, and error handling."""

import logging
import time
import traceback
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.utils.safe_logging import reset_request_id, set_request_id

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds a unique X-Request-ID header to every request/response, and
    binds it to a ContextVar so safe_log() auto-includes it in every
    record emitted during the request.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Logs the duration of each request."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration_ms:.0f}ms)")
        return response


class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    """Catches unhandled exceptions and returns clean JSON errors.

    In development: includes error details.
    In production: returns generic message, logs full stacktrace.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                f"Unhandled exception [request_id={request_id}]: {type(e).__name__}: {e}\n{traceback.format_exc()}"
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "request_id": request_id,
                },
            )
