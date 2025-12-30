"""
Base HTTP Client with retry logic and request logging.
"""

import asyncio
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategies for HTTP requests."""
    NONE = "none"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retry_on_status: tuple = (502, 503, 504, 429)


class BaseClient:
    """
    Base HTTP client with retry logic, request logging, and error handling.

    Features:
    - Automatic retries with configurable backoff
    - Request/response logging for debugging
    - Consistent error handling
    - Timeout configuration
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 60.0,
        retry_config: Optional[RetryConfig] = None,
        log_requests: bool = False,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self.log_requests = log_requests
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for requests. Override in subclasses for auth."""
        return {}

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry based on strategy."""
        config = self.retry_config

        if config.strategy == RetryStrategy.NONE:
            return 0
        elif config.strategy == RetryStrategy.LINEAR:
            delay = config.initial_delay * attempt
        else:  # EXPONENTIAL
            delay = config.initial_delay * (2 ** (attempt - 1))

        return min(delay, config.max_delay)

    def _should_retry(self, status_code: int, attempt: int) -> bool:
        """Determine if request should be retried."""
        if attempt >= self.retry_config.max_retries:
            return False
        return status_code in self.retry_config.retry_on_status

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        """
        Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: URL path
            params: Query parameters
            json: JSON body
            data: Form data
            headers: Additional headers
            timeout: Request timeout override

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPStatusError: For non-retryable HTTP errors
            httpx.RequestError: For network/connection errors after retries
        """
        request_headers = {**self._get_headers(), **(headers or {})}
        request_timeout = timeout or self.timeout

        last_error: Optional[Exception] = None

        for attempt in range(1, self.retry_config.max_retries + 2):  # +2 for initial + retries
            try:
                if self.log_requests:
                    logger.debug(f"[{method}] {path} (attempt {attempt})")

                response = await self.client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json,
                    data=data,
                    headers=request_headers,
                    timeout=request_timeout,
                )

                if self.log_requests:
                    logger.debug(f"[{method}] {path} -> {response.status_code}")

                # Check if we should retry based on status
                if self._should_retry(response.status_code, attempt):
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Retrying {method} {path} after {delay}s "
                        f"(status={response.status_code}, attempt={attempt})"
                    )
                    await asyncio.sleep(delay)
                    continue

                return response

            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                last_error = e
                if attempt <= self.retry_config.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Connection error on {method} {path}, "
                        f"retrying in {delay}s (attempt={attempt}): {e}"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

            except httpx.TimeoutException as e:
                last_error = e
                if attempt <= self.retry_config.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Timeout on {method} {path}, "
                        f"retrying in {delay}s (attempt={attempt})"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise RuntimeError("Unexpected error in retry logic")

    async def get(
        self,
        path: str,
        params: Optional[Dict] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make a GET request and return JSON response."""
        response = await self._request("GET", path, params=params, **kwargs)
        response.raise_for_status()
        return response.json()

    async def post(
        self,
        path: str,
        json: Optional[Dict] = None,
        data: Optional[Dict] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make a POST request and return JSON response."""
        response = await self._request("POST", path, json=json, data=data, **kwargs)
        response.raise_for_status()
        return response.json()

    async def put(
        self,
        path: str,
        json: Optional[Dict] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make a PUT request and return JSON response."""
        response = await self._request("PUT", path, json=json, **kwargs)
        response.raise_for_status()
        return response.json()

    async def delete(
        self,
        path: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make a DELETE request and return JSON response."""
        response = await self._request("DELETE", path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> bool:
        """Check if the service is healthy. Override in subclasses."""
        try:
            await self._request("GET", "/health")
            return True
        except Exception:
            return False
