"""
Correlation ID module for request tracing across the system.

This module provides:
- Context variable to store correlation ID per-request
- Middleware to extract/generate correlation IDs
- Helper functions to access correlation ID from anywhere in the code
"""
import uuid
import logging
from contextvars import ContextVar
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Context variable to store correlation ID for each request
# This is async-safe and works with asyncio
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

# Header names for correlation ID
CORRELATION_ID_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"


def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID from context.

    Returns:
        The correlation ID for the current request, or None if not set.
    """
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID in context.

    Args:
        correlation_id: The correlation ID to set
    """
    _correlation_id.set(correlation_id)


def generate_correlation_id() -> str:
    """
    Generate a new correlation ID.

    Returns:
        A new UUID-based correlation ID
    """
    return str(uuid.uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that handles correlation ID for request tracing.

    - Extracts correlation ID from incoming request headers (X-Correlation-ID or X-Request-ID)
    - Generates a new correlation ID if none provided
    - Stores it in context for access throughout the request lifecycle
    - Adds it to response headers
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Try to get correlation ID from request headers
        correlation_id = (
            request.headers.get(CORRELATION_ID_HEADER) or
            request.headers.get(REQUEST_ID_HEADER)
        )

        # Generate new ID if not provided
        if not correlation_id:
            correlation_id = generate_correlation_id()

        # Set in context
        set_correlation_id(correlation_id)

        # Log the incoming request with correlation ID
        logger.debug(
            f"Request started: {request.method} {request.url.path} "
            f"[correlation_id={correlation_id}]"
        )

        try:
            # Process the request
            response = await call_next(request)

            # Add correlation ID to response headers
            response.headers[CORRELATION_ID_HEADER] = correlation_id

            return response
        except Exception as e:
            # Log exception with correlation ID
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"[correlation_id={correlation_id}] error={str(e)}"
            )
            raise
        finally:
            # Clear context (optional, but good practice)
            _correlation_id.set(None)


class CorrelationIdFilter(logging.Filter):
    """
    Logging filter that adds correlation ID to log records.

    This allows the correlation ID to be included in log format strings
    using %(correlation_id)s
    """

    def filter(self, record: logging.LogRecord) -> bool:
        correlation_id = get_correlation_id()
        record.correlation_id = correlation_id or "-"
        return True


def get_logger_with_correlation(name: str) -> logging.Logger:
    """
    Get a logger that includes correlation ID in its output.

    This is a convenience function for modules that want to ensure
    correlation ID is always logged.

    Args:
        name: The logger name (usually __name__)

    Returns:
        A logger configured with correlation ID filter
    """
    logger = logging.getLogger(name)
    # Add filter if not already present
    if not any(isinstance(f, CorrelationIdFilter) for f in logger.filters):
        logger.addFilter(CorrelationIdFilter())
    return logger
