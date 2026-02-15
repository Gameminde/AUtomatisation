"""
Unit tests for retry_utils module.

Tests cover:
- Retry with backoff
- Circuit breaker pattern
- Delay calculations
- Transient error detection
"""

import pytest
# time module used in retries
# unittest.mock used in other tests


class TestCalculateDelay:
    """Tests for calculate_delay function."""

    def test_exponential_delay(self):
        """Test exponential backoff delay calculation."""
        from retry_utils import calculate_delay, RetryConfig, RetryStrategy

        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            jitter=False,
            strategy=RetryStrategy.EXPONENTIAL,
        )

        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 2.0
        assert calculate_delay(2, config) == 4.0
        assert calculate_delay(3, config) == 8.0

    def test_linear_delay(self):
        """Test linear delay calculation."""
        from retry_utils import calculate_delay, RetryConfig, RetryStrategy

        config = RetryConfig(
            base_delay=1.0,
            jitter=False,
            strategy=RetryStrategy.LINEAR,
        )

        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 2.0
        assert calculate_delay(2, config) == 3.0

    def test_constant_delay(self):
        """Test constant delay calculation."""
        from retry_utils import calculate_delay, RetryConfig, RetryStrategy

        config = RetryConfig(
            base_delay=5.0,
            jitter=False,
            strategy=RetryStrategy.CONSTANT,
        )

        assert calculate_delay(0, config) == 5.0
        assert calculate_delay(1, config) == 5.0
        assert calculate_delay(5, config) == 5.0

    def test_max_delay_cap(self):
        """Test maximum delay cap."""
        from retry_utils import calculate_delay, RetryConfig, RetryStrategy

        config = RetryConfig(
            base_delay=1.0,
            max_delay=10.0,
            jitter=False,
            strategy=RetryStrategy.EXPONENTIAL,
        )

        # 2^10 = 1024, but should be capped at 10
        assert calculate_delay(10, config) == 10.0

    def test_jitter_applied(self):
        """Test that jitter is applied when enabled."""
        from retry_utils import calculate_delay, RetryConfig

        config = RetryConfig(
            base_delay=10.0,
            jitter=True,
            jitter_range=0.25,
        )

        delays = [calculate_delay(0, config) for _ in range(10)]

        # With jitter, delays should vary
        assert len(set(delays)) > 1


class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator."""

    def test_success_no_retry(self):
        """Test successful call doesn't retry."""
        from retry_utils import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_function()

        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure(self):
        """Test retry on failure."""
        from retry_utils import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = failing_then_success()

        assert result == "success"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        """Test exception raised when max retries exceeded."""
        from retry_utils import retry_with_backoff

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fails():
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            always_fails()

    def test_retry_specific_exceptions(self):
        """Test retry only on specific exceptions."""
        from retry_utils import retry_with_backoff

        @retry_with_backoff(max_retries=3, base_delay=0.01, retry_on=(ValueError,))
        def raises_type_error():
            raise TypeError("Not retryable")

        with pytest.raises(TypeError):
            raises_type_error()


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_circuit_starts_closed(self):
        """Test circuit starts in closed state."""
        from retry_utils import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=3)

        assert breaker.is_closed
        assert not breaker.is_open

    def test_circuit_opens_after_failures(self):
        """Test circuit opens after threshold failures."""
        from retry_utils import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

        @breaker
        def failing_function():
            raise RuntimeError("Failure")

        for _ in range(3):
            try:
                failing_function()
            except RuntimeError:
                pass

        assert breaker.is_open

    def test_circuit_fails_fast_when_open(self):
        """Test circuit fails fast when open."""
        from retry_utils import CircuitBreaker, CircuitBreakerOpenError

        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=300)

        @breaker
        def failing_function():
            raise RuntimeError("Failure")

        # Trip the circuit
        for _ in range(2):
            try:
                failing_function()
            except RuntimeError:
                pass

        # Now should fail fast
        with pytest.raises(CircuitBreakerOpenError):
            failing_function()

    def test_circuit_reset(self):
        """Test manual circuit reset."""
        from retry_utils import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=2)

        @breaker
        def failing_function():
            raise RuntimeError("Failure")

        # Trip the circuit
        for _ in range(2):
            try:
                failing_function()
            except RuntimeError:
                pass

        assert breaker.is_open

        # Reset
        breaker.reset()

        assert breaker.is_closed


class TestIsTransientError:
    """Tests for is_transient_error function."""

    def test_timeout_is_transient(self):
        """Test that timeout errors are transient."""
        from retry_utils import is_transient_error
        import requests

        exc = requests.exceptions.Timeout("Connection timed out")

        assert is_transient_error(exc) is True

    def test_connection_error_is_transient(self):
        """Test that connection errors are transient."""
        from retry_utils import is_transient_error
        import requests

        exc = requests.exceptions.ConnectionError("Failed to connect")

        assert is_transient_error(exc) is True

    def test_rate_limit_message_is_transient(self):
        """Test that rate limit messages are detected."""
        from retry_utils import is_transient_error

        exc = Exception("Rate limit exceeded, please wait")

        assert is_transient_error(exc) is True

    def test_generic_error_not_transient(self):
        """Test that generic errors are not transient."""
        from retry_utils import is_transient_error

        exc = ValueError("Invalid input")

        assert is_transient_error(exc) is False


class TestRetryIfTransient:
    """Tests for retry_if_transient decorator."""

    def test_retries_transient_errors(self):
        """Test that transient errors are retried."""
        from retry_utils import retry_if_transient
        import requests

        call_count = 0

        @retry_if_transient(max_retries=3, base_delay=0.01)
        def transient_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise requests.exceptions.Timeout("Timeout")
            return "success"

        result = transient_then_success()

        assert result == "success"
        assert call_count == 2

    def test_does_not_retry_non_transient(self):
        """Test that non-transient errors are not retried."""
        from retry_utils import retry_if_transient

        call_count = 0

        @retry_if_transient(max_retries=3, base_delay=0.01)
        def non_transient_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")

        with pytest.raises(ValueError):
            non_transient_error()

        assert call_count == 1


class TestWithRetry:
    """Tests for with_retry convenience function."""

    def test_with_retry_success(self):
        """Test with_retry with successful function."""
        from retry_utils import with_retry

        def simple_func(x):
            return x * 2

        result = with_retry(simple_func, 5)

        assert result == 10
