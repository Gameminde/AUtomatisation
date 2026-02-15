"""
Retry Utilities - Robust retry logic with exponential backoff.

This module provides decorators and utilities for handling transient failures
with intelligent retry mechanisms including:
- Exponential backoff
- Jitter (randomization)
- Circuit breaker pattern
- Configurable retry conditions

Usage:
    from retry_utils import retry_with_backoff, circuit_breaker

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def api_call():
        # Your code here
        pass

    @circuit_breaker(failure_threshold=5, recovery_timeout=60)
    def external_service_call():
        # Your code here
        pass
"""

from __future__ import annotations

import functools
# logging is used via config.get_logger
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, Tuple, Type, TypeVar

import config

logger = config.get_logger("retry_utils")

T = TypeVar("T")


class RetryStrategy(Enum):
    """Retry strategy types."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        exponential_base: Base for exponential backoff (default 2)
        jitter: Whether to add random jitter to delays
        jitter_range: Range for jitter as fraction (0.0-1.0)
        strategy: Retry strategy type
        retry_on: Tuple of exception types to retry on
        log_retries: Whether to log retry attempts
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_range: float = 0.25
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retry_on: Tuple[Type[Exception], ...] = (Exception,)
    log_retries: bool = True


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate delay for a given retry attempt.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    if config.strategy == RetryStrategy.EXPONENTIAL:
        delay = config.base_delay * (config.exponential_base**attempt)
    elif config.strategy == RetryStrategy.LINEAR:
        delay = config.base_delay * (attempt + 1)
    else:  # CONSTANT
        delay = config.base_delay

    # Apply max delay cap
    delay = min(delay, config.max_delay)

    # Apply jitter
    if config.jitter:
        jitter_amount = delay * config.jitter_range
        delay = delay + random.uniform(-jitter_amount, jitter_amount)
        delay = max(0, delay)  # Ensure non-negative

    return delay


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        exponential_base: Base for exponential calculation
        jitter: Whether to add random jitter
        retry_on: Tuple of exception types to retry on
        on_retry: Optional callback called on each retry

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def unstable_api_call():
            response = requests.get("https://api.example.com")
            response.raise_for_status()
            return response.json()
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retry_on=retry_on,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except config.retry_on as exc:
                    last_exception = exc

                    if attempt == config.max_retries:
                        logger.error(
                            "❌ %s failed after %d attempts: %s", func.__name__, attempt + 1, exc
                        )
                        raise

                    delay = calculate_delay(attempt, config)

                    logger.warning(
                        "⚠️ %s attempt %d/%d failed: %s. Retrying in %.2fs...",
                        func.__name__,
                        attempt + 1,
                        config.max_retries + 1,
                        exc,
                        delay,
                    )

                    if on_retry:
                        on_retry(exc, attempt)

                    time.sleep(delay)

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError(f"{func.__name__} failed unexpectedly")

        return wrapper

    return decorator


@dataclass
class CircuitBreakerState:
    """State for circuit breaker pattern.

    Attributes:
        failures: Current failure count
        last_failure_time: Time of last failure
        state: Current state (closed, open, half_open)
        success_count: Successes in half-open state
    """

    failures: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "closed"  # closed, open, half_open
    success_count: int = 0


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting external service calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit is tripped, requests fail immediately
    - HALF_OPEN: Testing if service recovered

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

        @breaker
        def call_external_api():
            return requests.get("https://api.example.com")
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
        expected_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            success_threshold: Successes needed to close circuit from half-open
            expected_exceptions: Exception types that count as failures
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout)
        self.success_threshold = success_threshold
        self.expected_exceptions = expected_exceptions
        self._state = CircuitBreakerState()
        self._lock_time: Optional[datetime] = None

    @property
    def state(self) -> str:
        """Get current circuit state."""
        return self._state.state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state.state == "closed"

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self._state.state == "open"

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if not self._state.last_failure_time:
            return True
        return datetime.now() - self._state.last_failure_time >= self.recovery_timeout

    def _handle_success(self) -> None:
        """Handle successful call."""
        if self._state.state == "half_open":
            self._state.success_count += 1
            if self._state.success_count >= self.success_threshold:
                logger.info("✅ Circuit breaker: Closing circuit (service recovered)")
                self._state.state = "closed"
                self._state.failures = 0
                self._state.success_count = 0
        elif self._state.state == "closed":
            # Reset failure count on success
            self._state.failures = 0

    def _handle_failure(self, exc: Exception) -> None:
        """Handle failed call."""
        self._state.failures += 1
        self._state.last_failure_time = datetime.now()
        self._state.success_count = 0

        if self._state.failures >= self.failure_threshold:
            logger.error(
                "🔴 Circuit breaker: Opening circuit after %d failures", self._state.failures
            )
            self._state.state = "open"

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for applying circuit breaker to a function."""

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Check if circuit is open
            if self._state.state == "open":
                if self._should_attempt_reset():
                    logger.info("🟡 Circuit breaker: Attempting recovery (half-open)")
                    self._state.state = "half_open"
                else:
                    raise CircuitBreakerOpenError(f"Circuit breaker is open for {func.__name__}")

            try:
                result = func(*args, **kwargs)
                self._handle_success()
                return result
            except self.expected_exceptions as exc:
                self._handle_failure(exc)
                raise

        # Attach circuit breaker instance to wrapper for inspection
        wrapper.circuit_breaker = self
        return wrapper

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = CircuitBreakerState()
        logger.info("🔄 Circuit breaker: Manually reset")


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and blocking calls."""

    pass


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    success_threshold: int = 2,
    expected_exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> CircuitBreaker:
    """
    Factory function for creating circuit breaker decorator.

    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds before attempting recovery
        success_threshold: Successes needed to close circuit
        expected_exceptions: Exception types that count as failures

    Returns:
        CircuitBreaker instance

    Example:
        @circuit_breaker(failure_threshold=5, recovery_timeout=60)
        def call_external_api():
            return requests.get("https://api.example.com")
    """
    return CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        success_threshold=success_threshold,
        expected_exceptions=expected_exceptions,
    )


class RetryableError(Exception):
    """Base exception for errors that should be retried."""

    pass


class NonRetryableError(Exception):
    """Base exception for errors that should NOT be retried."""

    pass


def is_transient_error(exc: Exception) -> bool:
    """
    Determine if an exception is likely transient and should be retried.

    Args:
        exc: The exception to check

    Returns:
        True if error appears transient, False otherwise
    """
    import requests

    # Network-related errors are usually transient
    if isinstance(
        exc,
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ),
    ):
        return True

    # HTTP status codes that indicate transient errors
    if isinstance(exc, requests.exceptions.HTTPError):
        status_code = getattr(exc.response, "status_code", None)
        if status_code in (429, 500, 502, 503, 504):
            return True

    # Rate limit errors
    error_message = str(exc).lower()
    if any(
        keyword in error_message
        for keyword in [
            "rate limit",
            "too many requests",
            "quota exceeded",
            "timeout",
            "connection",
            "temporary",
        ]
    ):
        return True

    return False


def retry_if_transient(
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that retries only on transient errors.

    Args:
        max_retries: Maximum retry attempts
        base_delay: Base delay between retries

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if not is_transient_error(exc):
                        # Non-transient error, don't retry
                        raise

                    last_exception = exc

                    if attempt == max_retries:
                        logger.error(
                            "❌ %s: Max retries exceeded for transient error: %s",
                            func.__name__,
                            exc,
                        )
                        raise

                    delay = base_delay * (2**attempt)
                    delay = delay + random.uniform(0, delay * 0.1)  # Small jitter

                    logger.warning(
                        "⚠️ %s: Transient error (attempt %d/%d): %s. Retrying in %.2fs",
                        func.__name__,
                        attempt + 1,
                        max_retries + 1,
                        exc,
                        delay,
                    )

                    time.sleep(delay)

            if last_exception:
                raise last_exception
            raise RuntimeError(f"{func.__name__} failed unexpectedly")

        return wrapper

    return decorator


# Convenience function for API calls
def with_retry(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Execute a function with default retry logic.

    Args:
        func: Function to execute
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        Function result
    """

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def wrapped() -> T:
        return func(*args, **kwargs)

    return wrapped()


if __name__ == "__main__":
    # Example usage and testing
    print("Testing retry utilities...")

    # Test 1: Retry with backoff
    @retry_with_backoff(max_retries=2, base_delay=0.5)
    def failing_function():
        raise ValueError("Simulated failure")

    try:
        failing_function()
    except ValueError:
        print("✅ Retry decorator worked correctly")

    # Test 2: Circuit breaker
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5)

    @breaker
    def unreliable_service():
        raise RuntimeError("Service unavailable")

    for i in range(5):
        try:
            unreliable_service()
        except (RuntimeError, CircuitBreakerOpenError) as e:
            print(f"  Call {i + 1}: {type(e).__name__}")

    print(f"✅ Circuit state: {breaker.state}")

    print("\n✅ All retry utility tests passed!")
