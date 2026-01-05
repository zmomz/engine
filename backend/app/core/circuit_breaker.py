"""
Circuit Breaker pattern implementation for exchange connectors.
Prevents cascading failures when an exchange is unresponsive or failing.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Failing fast, requests are rejected immediately
- HALF_OPEN: Testing if the service has recovered
"""
import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Dict, Optional, Any
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing fast, rejecting requests
    HALF_OPEN = "half_open" # Testing recovery


class CircuitBreakerError(Exception):
    """Raised when the circuit breaker is open."""
    def __init__(self, message: str, circuit_name: str, time_until_retry: float):
        self.circuit_name = circuit_name
        self.time_until_retry = time_until_retry
        super().__init__(message)


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    Usage:
        breaker = CircuitBreaker(name="binance", failure_threshold=5)

        async with breaker:
            await make_request()

        # Or using decorator
        @breaker.protect
        async def make_request():
            ...
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        reset_timeout: float = 60.0,
        half_open_max_calls: int = 3
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker
            failure_threshold: Number of failures before opening circuit
            success_threshold: Number of successes in HALF_OPEN to close circuit
            reset_timeout: Seconds to wait before transitioning from OPEN to HALF_OPEN
            half_open_max_calls: Max concurrent calls allowed in HALF_OPEN state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

        # Metrics
        self._total_calls = 0
        self._total_failures = 0
        self._total_rejections = 0

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state == CircuitState.HALF_OPEN

    def _get_time_until_retry(self) -> float:
        """Get remaining time until circuit transitions to HALF_OPEN."""
        if self._last_failure_time is None:
            return 0
        elapsed = time.time() - self._last_failure_time
        remaining = self.reset_timeout - elapsed
        return max(0, remaining)

    async def _check_state_transition(self):
        """Check if state should transition based on timeout."""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.reset_timeout:
                    await self._transition_to_half_open()

    async def _transition_to_open(self):
        """Transition to OPEN state."""
        self._state = CircuitState.OPEN
        self._last_failure_time = time.time()
        logger.warning(
            f"Circuit breaker '{self.name}' OPENED after {self._failure_count} failures. "
            f"Will retry after {self.reset_timeout}s"
        )

    async def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        self._success_count = 0
        logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN for recovery testing")

    async def _transition_to_closed(self):
        """Transition to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = None
        logger.info(f"Circuit breaker '{self.name}' CLOSED - service recovered")

    async def record_success(self):
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self._half_open_calls = max(0, self._half_open_calls - 1)

                if self._success_count >= self.success_threshold:
                    await self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def record_failure(self):
        """Record a failed call."""
        async with self._lock:
            self._total_failures += 1

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN immediately opens circuit
                await self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    await self._transition_to_open()

    async def can_execute(self) -> bool:
        """
        Check if a request can be executed.
        Returns True if allowed, False if should be rejected.
        """
        async with self._lock:
            await self._check_state_transition()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                self._total_rejections += 1
                return False

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

            return False

    async def __aenter__(self):
        """Context manager entry - check if execution is allowed."""
        self._total_calls += 1

        if not await self.can_execute():
            time_until_retry = self._get_time_until_retry()
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is OPEN. Retry after {time_until_retry:.1f}s",
                circuit_name=self.name,
                time_until_retry=time_until_retry
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - record success or failure."""
        if exc_type is None:
            await self.record_success()
        else:
            await self.record_failure()
        return False  # Don't suppress exceptions

    def protect(self, func: Callable):
        """
        Decorator to protect an async function with circuit breaker.

        Usage:
            @breaker.protect
            async def make_request():
                ...
        """
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with self:
                return await func(*args, **kwargs)
        return wrapper

    def get_metrics(self) -> dict:
        """Get circuit breaker metrics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "total_rejections": self._total_rejections,
            "time_until_retry": self._get_time_until_retry() if self.is_open else 0,
            "half_open_calls": self._half_open_calls
        }

    async def reset(self):
        """Manually reset the circuit breaker to closed state."""
        async with self._lock:
            await self._transition_to_closed()
            logger.info(f"Circuit breaker '{self.name}' manually reset to CLOSED")


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    Provides centralized access to circuit breakers by name.
    """

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        reset_timeout: float = 60.0,
        half_open_max_calls: int = 3
    ) -> CircuitBreaker:
        """
        Get existing circuit breaker or create a new one.

        Args:
            name: Unique identifier for the circuit breaker
            failure_threshold: Failures before opening (used only on creation)
            success_threshold: Successes in HALF_OPEN to close (used only on creation)
            reset_timeout: Seconds before OPEN -> HALF_OPEN (used only on creation)
            half_open_max_calls: Max calls in HALF_OPEN (used only on creation)

        Returns:
            CircuitBreaker instance
        """
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    success_threshold=success_threshold,
                    reset_timeout=reset_timeout,
                    half_open_max_calls=half_open_max_calls
                )
            return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name, or None if not found."""
        return self._breakers.get(name)

    def get_all_metrics(self) -> Dict[str, dict]:
        """Get metrics for all circuit breakers."""
        return {name: breaker.get_metrics() for name, breaker in self._breakers.items()}

    async def reset_all(self):
        """Reset all circuit breakers to closed state."""
        for breaker in self._breakers.values():
            await breaker.reset()

    def is_healthy(self, name: str) -> bool:
        """Check if a specific circuit breaker is healthy (CLOSED)."""
        breaker = self._breakers.get(name)
        return breaker.is_closed if breaker else True


# Global registry instance
_circuit_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    global _circuit_registry
    if _circuit_registry is None:
        _circuit_registry = CircuitBreakerRegistry()
    return _circuit_registry


async def get_exchange_circuit(exchange_name: str) -> CircuitBreaker:
    """
    Get the circuit breaker for a specific exchange.

    Args:
        exchange_name: Exchange identifier (e.g., "binance", "bybit")

    Returns:
        CircuitBreaker for the exchange
    """
    registry = get_circuit_registry()
    return await registry.get_or_create(
        name=f"exchange:{exchange_name}",
        failure_threshold=5,
        success_threshold=2,
        reset_timeout=60.0,
        half_open_max_calls=3
    )
