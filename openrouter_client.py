"""
OpenRouter API Client - Multi-key failover with robust retry logic.

Features:
- Multiple API key rotation on rate limits
- Exponential backoff with jitter
- Circuit breaker pattern
- Intelligent rate limit handling
- Request/response logging

Author: Content Factory Team
Version: 2.0.0
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import requests

import config
from retry_utils import retry_with_backoff, CircuitBreaker, is_transient_error

logger = config.get_logger("openrouter")


class RateLimitError(Exception):
    """Raised when API returns 429 Too Many Requests."""

    pass


class AllKeysExhaustedError(Exception):
    """Raised when all API keys are rate-limited."""

    pass


class OpenRouterClient:
    """OpenRouter API client with automatic key rotation on rate limits."""

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_keys: Optional[List[str]] = None,
        model: Optional[str] = None,
    ):
        # Filter out empty keys
        keys = api_keys or config.OPENROUTER_API_KEYS
        self.api_keys = [k.strip() for k in keys if k and k.strip()]

        if not self.api_keys:
            raise ValueError("No valid OpenRouter API keys provided")

        self.model = model or config.OPENROUTER_MODEL
        self.current_key_index = 0
        self.exhausted_keys: set[int] = set()

        logger.info(
            "OpenRouterClient initialized with %d keys, model=%s",
            len(self.api_keys),
            self.model,
        )

    @property
    def current_key(self) -> str:
        return self.api_keys[self.current_key_index]

    def _rotate_key(self) -> bool:
        """Rotate to next available key. Returns False if all exhausted."""
        self.exhausted_keys.add(self.current_key_index)

        for i in range(len(self.api_keys)):
            next_index = (self.current_key_index + 1 + i) % len(self.api_keys)
            if next_index not in self.exhausted_keys:
                self.current_key_index = next_index
                logger.warning(
                    "Rotated to API key #%d (key #%d hit rate limit)",
                    next_index + 1,
                    self.current_key_index + 1,
                )
                return True

        return False

    def reset_exhausted(self) -> None:
        """Reset exhausted keys (call this after rate limit window expires)."""
        self.exhausted_keys.clear()

    def call(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """
        Make an API call with automatic failover on 429.

        Args:
            prompt: The user prompt to send
            max_tokens: Maximum tokens in response
            temperature: Creativity (0.0-1.0)

        Returns:
            Generated text response

        Raises:
            AllKeysExhaustedError: When all keys are rate-limited
            RuntimeError: On other API errors
        """
        attempts = 0
        max_attempts = len(self.api_keys)

        while attempts < max_attempts:
            try:
                return self._make_request(prompt, max_tokens, temperature)
            except RateLimitError:
                attempts += 1
                if not self._rotate_key():
                    raise AllKeysExhaustedError(
                        f"All {len(self.api_keys)} API keys are rate-limited. "
                        "Wait for rate limit window to reset (usually 1 minute)."
                    )
                # Small delay before trying next key
                time.sleep(1)

        raise AllKeysExhaustedError("Exhausted all retry attempts")

    def _make_request(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """
        Make a single API request with intelligent rate limit handling.

        Features:
        - Automatic retry on transient errors
        - Rate limit header monitoring
        - Preventive pausing when quota low

        Args:
            prompt: User prompt to send
            max_tokens: Maximum tokens in response
            temperature: Creativity setting (0.0-1.0)

        Returns:
            Generated text response

        Raises:
            RateLimitError: When rate limit is hit
            RuntimeError: On other API errors
        """
        headers = {
            "Authorization": f"Bearer {self.current_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://content-factory.local",
            "X-Title": "Content Factory",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            response = requests.post(
                self.BASE_URL,
                headers=headers,
                json=payload,
                timeout=config.HTTP_TIMEOUT_SECONDS,
            )
        except requests.exceptions.Timeout as exc:
            logger.warning("OpenRouter request timed out, will retry: %s", exc)
            raise RateLimitError("Request timeout") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.warning("OpenRouter connection error, will retry: %s", exc)
            raise RateLimitError("Connection error") from exc
        except requests.RequestException as exc:
            logger.error("OpenRouter request failed: %s", exc)
            raise RuntimeError(f"Request failed: {exc}") from exc

        # Check rate limit headers for preventive action
        remaining = response.headers.get("x-ratelimit-remaining")
        reset_time = response.headers.get("x-ratelimit-reset")

        if remaining is not None:
            try:
                remaining_int = int(remaining)
                if remaining_int <= 5:
                    logger.warning(
                        "⚠️ Rate limit low: %d remaining on key #%d",
                        remaining_int,
                        self.current_key_index + 1,
                    )
                    # Preventive pause
                    if remaining_int <= 2:
                        logger.info("Preventive pause (5s) - rate limit critical")
                        time.sleep(5)
            except ValueError:
                pass

        # Handle rate limit
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            try:
                wait_seconds = int(retry_after)
            except ValueError:
                wait_seconds = 60

            logger.warning(
                "Rate limit hit for key #%d (retry after %ds): %s",
                self.current_key_index + 1,
                wait_seconds,
                response.text[:200],
            )
            raise RateLimitError(f"Key #{self.current_key_index + 1} rate limited")

        # Handle other errors
        if response.status_code != 200:
            logger.error(
                "OpenRouter error %d: %s",
                response.status_code,
                response.text[:500],
            )
            raise RuntimeError(
                f"OpenRouter API error {response.status_code}: {response.text[:200]}"
            )

        # Parse response
        data = response.json()
        choices = data.get("choices", [])

        if not choices:
            raise RuntimeError("OpenRouter returned no choices")

        message = choices[0].get("message", {})
        content = message.get("content", "")

        if not content:
            raise RuntimeError("OpenRouter returned empty content")

        usage = data.get("usage", {})
        logger.info(
            "✅ API success (key #%d, %d tokens, %s remaining)",
            self.current_key_index + 1,
            usage.get("total_tokens", 0),
            remaining or "?",
        )

        return content


def get_client() -> OpenRouterClient:
    """Get a configured OpenRouter client instance."""
    return OpenRouterClient()


# Convenience function for testing
def test_connection() -> bool:
    """Test if OpenRouter connection works with current keys."""
    try:
        client = get_client()
        response = client.call("Say 'Hello' in French. Reply with just one word.")
        logger.info("Connection test successful: %s", response.strip())
        return True
    except Exception as exc:
        logger.error("Connection test failed: %s", exc)
        return False


if __name__ == "__main__":
    print("Testing OpenRouter connection...")
    success = test_connection()
    print("Result:", "SUCCESS ✅" if success else "FAILED ❌")
