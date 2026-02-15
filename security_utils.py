"""
Security Utilities - Credential management and security features.

Features:
- Credential encryption/decryption
- Token rotation helpers
- Input validation
- Rate limit tracking
- Security audit logging

Author: Content Factory Team
Version: 2.0.0
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

import config

logger = config.get_logger("security")

T = TypeVar("T")


# ============================================================================
# Credential Encryption
# ============================================================================


class CredentialManager:
    """
    Secure credential management with Fernet (AES-128-CBC) encryption.

    Uses the ``cryptography`` library for industry-standard encryption.
    Falls back gracefully if the library is not installed.
    """

    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize credential manager.

        Args:
            master_key: Master encryption key (from env if not provided)
        """
        self.master_key = master_key or os.getenv("MASTER_ENCRYPTION_KEY", "")

        if not self.master_key:
            # Generate and persist a key on first run
            key_file = Path(__file__).parent / ".master_key"
            if key_file.exists():
                self.master_key = key_file.read_text().strip()
            else:
                self.master_key = secrets.token_hex(32)
                try:
                    key_file.write_text(self.master_key)
                    logger.info("🔑 Generated and saved master encryption key")
                except OSError:
                    logger.warning("⚠️ Could not persist master key — using ephemeral key")

        # Derive a Fernet key from the master key
        self._fernet = self._build_fernet()

    def _get_key_bytes(self) -> bytes:
        """Get key as bytes (SHA-256 of master key)."""
        return hashlib.sha256(self.master_key.encode()).digest()

    def _build_fernet(self):
        """Build a Fernet instance from the master key."""
        try:
            from cryptography.fernet import Fernet
            fernet_key = base64.urlsafe_b64encode(self._get_key_bytes())
            return Fernet(fernet_key)
        except ImportError:
            logger.warning("⚠️ cryptography package not installed — encryption disabled")
            return None

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string using Fernet (AES-128-CBC + HMAC).

        Args:
            plaintext: Text to encrypt

        Returns:
            Base64-encoded encrypted string prefixed with 'fernet:'
        """
        if not plaintext:
            return ""

        if self._fernet is None:
            logger.warning("Encryption unavailable — storing as plaintext")
            return plaintext

        try:
            token = self._fernet.encrypt(plaintext.encode("utf-8"))
            return "fernet:" + token.decode("utf-8")
        except Exception as e:
            logger.error("Encryption failed: %s", e)
            return plaintext

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string (supports both Fernet and legacy XOR).

        Args:
            ciphertext: Encrypted string (Fernet-prefixed or legacy base64)

        Returns:
            Decrypted plaintext
        """
        if not ciphertext:
            return ""

        # New Fernet format
        if ciphertext.startswith("fernet:"):
            if self._fernet is None:
                logger.error("Cannot decrypt — cryptography package not installed")
                return ""
            try:
                token = ciphertext[7:].encode("utf-8")
                return self._fernet.decrypt(token).decode("utf-8")
            except Exception as e:
                logger.error("Fernet decryption failed: %s", e)
                return ""

        # Legacy XOR format — auto-migrate on next encrypt
        try:
            key = self._get_key_bytes()
            encrypted = base64.b64decode(ciphertext.encode("utf-8"))
            decrypted = bytes(c ^ key[i % len(key)] for i, c in enumerate(encrypted))
            plaintext = decrypted.decode("utf-8")
            logger.info("🔄 Decrypted legacy XOR data — will re-encrypt with Fernet on next save")
            return plaintext
        except Exception as e:
            logger.error("Decryption failed: %s", e)
            return ""

    def hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Hash a password with salt.

        Args:
            password: Password to hash
            salt: Optional salt (generated if not provided)

        Returns:
            Tuple of (hash, salt)
        """
        if salt is None:
            salt = secrets.token_hex(16)

        salted = f"{salt}{password}".encode("utf-8")
        hashed = hashlib.pbkdf2_hmac("sha256", salted, salt.encode("utf-8"), 100000)

        return base64.b64encode(hashed).decode("utf-8"), salt

    def verify_password(self, password: str, hashed: str, salt: str) -> bool:
        """
        Verify a password against its hash.

        Args:
            password: Password to verify
            hashed: Stored hash
            salt: Stored salt

        Returns:
            True if password matches
        """
        new_hash, _ = self.hash_password(password, salt)
        return hmac.compare_digest(new_hash, hashed)


# ============================================================================
# Token Management
# ============================================================================


@dataclass
class TokenInfo:
    """Information about an API token."""

    token_id: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]
    usage_count: int
    is_active: bool


class TokenRotationManager:
    """
    Manage API token rotation for security.

    Tracks token usage and expiration, provides rotation reminders.
    """

    def __init__(self):
        self.tokens: Dict[str, TokenInfo] = {}
        self._load_token_metadata()

    def _load_token_metadata(self) -> None:
        """Load token metadata from database."""
        try:
            # TODO: Implement database loading
            # client = config.get_supabase_client()
            # For now, we'll track in memory
            pass
        except Exception:
            pass

    def register_token(
        self,
        name: str,
        token_preview: str,  # Only store first/last 4 chars
        expires_in_days: Optional[int] = None,
    ) -> str:
        """
        Register a new token for tracking.

        Args:
            name: Token name (e.g., "facebook_access_token")
            token_preview: Preview of token (first 4 + last 4 chars)
            expires_in_days: Days until expiration

        Returns:
            Token ID
        """
        token_id = secrets.token_hex(8)

        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)

        self.tokens[token_id] = TokenInfo(
            token_id=token_id,
            name=name,
            created_at=datetime.now(),
            expires_at=expires_at,
            last_used=None,
            usage_count=0,
            is_active=True,
        )

        logger.info("Registered token: %s (preview: %s)", name, token_preview)
        return token_id

    def record_usage(self, token_id: str) -> None:
        """Record token usage."""
        if token_id in self.tokens:
            self.tokens[token_id].last_used = datetime.now()
            self.tokens[token_id].usage_count += 1

    def check_expiration(self) -> List[Tuple[str, int]]:
        """
        Check for tokens nearing expiration.

        Returns:
            List of (token_name, days_until_expiration) for expiring tokens
        """
        expiring = []
        now = datetime.now()

        for token in self.tokens.values():
            if token.expires_at and token.is_active:
                days_left = (token.expires_at - now).days
                if days_left <= 7:  # Warn if expires within 7 days
                    expiring.append((token.name, days_left))
                    logger.warning("⚠️ Token '%s' expires in %d days!", token.name, days_left)

        return expiring

    def get_rotation_recommendations(self) -> List[str]:
        """Get token rotation recommendations."""
        recommendations = []

        # Check for old tokens
        for token in self.tokens.values():
            age_days = (datetime.now() - token.created_at).days

            if age_days > 60:
                recommendations.append(
                    f"🔄 Token '{token.name}' is {age_days} days old. Consider rotating."
                )

            if token.expires_at:
                days_left = (token.expires_at - datetime.now()).days
                if days_left <= 0:
                    recommendations.append(
                        f"❌ Token '{token.name}' has EXPIRED! Rotate immediately."
                    )
                elif days_left <= 7:
                    recommendations.append(
                        f"⚠️ Token '{token.name}' expires in {days_left} days. Rotate soon."
                    )

        return recommendations


# ============================================================================
# Input Validation
# ============================================================================


class InputValidator:
    """
    Validate and sanitize user inputs.
    """

    # Patterns for validation
    URL_PATTERN = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
        r"localhost|"  # localhost
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # IP
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    UUID_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )

    @classmethod
    def is_valid_url(cls, url: str) -> bool:
        """Check if string is a valid URL."""
        return bool(cls.URL_PATTERN.match(url))

    @classmethod
    def is_valid_uuid(cls, value: str) -> bool:
        """Check if string is a valid UUID."""
        return bool(cls.UUID_PATTERN.match(value))

    @classmethod
    def sanitize_text(cls, text: str, max_length: int = 10000) -> str:
        """
        Sanitize text input.

        Args:
            text: Text to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Truncate if too long
        text = text[:max_length]

        # Remove null bytes
        text = text.replace("\x00", "")

        # Remove control characters (except newlines and tabs)
        text = "".join(
            char for char in text if char == "\n" or char == "\t" or not (0 <= ord(char) < 32)
        )

        return text.strip()

    @classmethod
    def validate_api_key(cls, key: str) -> Tuple[bool, str]:
        """
        Validate API key format.

        Args:
            key: API key to validate

        Returns:
            Tuple of (is_valid, message)
        """
        if not key:
            return False, "API key is empty"

        if len(key) < 20:
            return False, "API key seems too short"

        if len(key) > 256:
            return False, "API key seems too long"

        # Check for common placeholders
        placeholders = ["your_api_key", "xxx", "test", "example", "placeholder"]
        if any(p in key.lower() for p in placeholders):
            return False, "API key appears to be a placeholder"

        return True, "Valid"


# ============================================================================
# Rate Limit Tracking
# ============================================================================


@dataclass
class RateLimitInfo:
    """Rate limit tracking info."""

    api_name: str
    limit: int
    remaining: int
    reset_time: datetime
    window_seconds: int


class RateLimitTracker:
    """
    Track rate limits across APIs.
    """

    def __init__(self):
        self.limits: Dict[str, RateLimitInfo] = {}

    def update_limit(
        self,
        api_name: str,
        limit: int,
        remaining: int,
        reset_time: Optional[datetime] = None,
        window_seconds: int = 60,
    ) -> None:
        """
        Update rate limit info for an API.

        Args:
            api_name: Name of the API
            limit: Total limit
            remaining: Remaining calls
            reset_time: When limit resets
            window_seconds: Window duration
        """
        if reset_time is None:
            reset_time = datetime.now() + timedelta(seconds=window_seconds)

        self.limits[api_name] = RateLimitInfo(
            api_name=api_name,
            limit=limit,
            remaining=remaining,
            reset_time=reset_time,
            window_seconds=window_seconds,
        )

        # Log warnings
        if remaining <= 5:
            logger.warning("⚠️ Rate limit low for %s: %d/%d remaining", api_name, remaining, limit)
        elif remaining == 0:
            logger.error(
                "❌ Rate limit exhausted for %s! Resets at %s", api_name, reset_time.isoformat()
            )

    def can_make_request(self, api_name: str) -> Tuple[bool, Optional[float]]:
        """
        Check if a request can be made to an API.

        Args:
            api_name: Name of the API

        Returns:
            Tuple of (can_make_request, wait_seconds if not)
        """
        if api_name not in self.limits:
            return True, None

        info = self.limits[api_name]

        # Check if reset time has passed
        if datetime.now() >= info.reset_time:
            # Reset assumed
            return True, None

        if info.remaining > 0:
            return True, None

        wait_seconds = (info.reset_time - datetime.now()).total_seconds()
        return False, max(0, wait_seconds)

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all tracked APIs."""
        status = {}
        for name, info in self.limits.items():
            status[name] = {
                "limit": info.limit,
                "remaining": info.remaining,
                "reset_time": info.reset_time.isoformat(),
                "percent_used": (
                    round((1 - info.remaining / info.limit) * 100, 1) if info.limit > 0 else 0
                ),
            }
        return status


# ============================================================================
# Security Audit Logging
# ============================================================================


class SecurityAuditLogger:
    """
    Log security-relevant events for auditing.
    """

    def __init__(self):
        self.audit_log = config.get_logger("security_audit")

    def log_access(
        self,
        action: str,
        resource: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log an access event.

        Args:
            action: Action performed (e.g., "api_call", "login")
            resource: Resource accessed
            success: Whether action succeeded
            details: Additional details
        """
        message = f"[AUDIT] {action} on {resource} - {'SUCCESS' if success else 'FAILED'}"
        if details:
            message += f" | Details: {details}"

        if success:
            self.audit_log.info(message)
        else:
            self.audit_log.warning(message)

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log a security event.

        Args:
            event_type: Type of event (e.g., "rate_limit", "auth_failure")
            severity: Severity level (LOW, MEDIUM, HIGH, CRITICAL)
            message: Event message
            details: Additional details
        """
        log_message = f"[SECURITY] [{severity}] {event_type}: {message}"
        if details:
            log_message += f" | {details}"

        if severity == "CRITICAL":
            self.audit_log.critical(log_message)
        elif severity == "HIGH":
            self.audit_log.error(log_message)
        elif severity == "MEDIUM":
            self.audit_log.warning(log_message)
        else:
            self.audit_log.info(log_message)


# ============================================================================
# Decorator for Secure Function Calls
# ============================================================================


def secure_call(
    validate_inputs: bool = True,
    log_access: bool = True,
    rate_limit_api: Optional[str] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for adding security features to function calls.

    Args:
        validate_inputs: Whether to validate string inputs
        log_access: Whether to log access
        rate_limit_api: API name for rate limit checking

    Returns:
        Decorated function
    """
    audit_logger = SecurityAuditLogger()
    rate_tracker = RateLimitTracker()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Check rate limit
            if rate_limit_api:
                can_proceed, wait_time = rate_tracker.can_make_request(rate_limit_api)
                if not can_proceed:
                    audit_logger.log_security_event(
                        "rate_limit",
                        "MEDIUM",
                        f"Rate limited for {rate_limit_api}",
                        {"wait_seconds": wait_time},
                    )
                    raise RuntimeError(f"Rate limited. Wait {wait_time:.1f}s")

            # Validate inputs
            if validate_inputs:
                for arg in args:
                    if isinstance(arg, str):
                        InputValidator.sanitize_text(arg)
                for value in kwargs.values():
                    if isinstance(value, str):
                        InputValidator.sanitize_text(value)

            # Execute function
            try:
                result = func(*args, **kwargs)

                if log_access:
                    audit_logger.log_access(
                        func.__name__,
                        func.__module__,
                        success=True,
                    )

                return result

            except Exception as e:
                if log_access:
                    audit_logger.log_access(
                        func.__name__, func.__module__, success=False, details={"error": str(e)}
                    )
                raise

        return wrapper

    return decorator


# ============================================================================
# Utility Functions
# ============================================================================


def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """
    Mask a sensitive value for logging.

    Args:
        value: Value to mask
        visible_chars: Number of chars to show at start and end

    Returns:
        Masked string (e.g., "sk-a...xyz")
    """
    if not value or len(value) <= visible_chars * 2:
        return "***"

    return f"{value[:visible_chars]}...{value[-visible_chars:]}"


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure token."""
    return secrets.token_urlsafe(length)


def check_environment_security() -> Dict[str, Any]:
    """
    Check security of current environment.

    Returns:
        Dict with security status and recommendations
    """
    results = {
        "status": "OK",
        "issues": [],
        "recommendations": [],
    }

    # Check for sensitive env vars
    sensitive_vars = [
        "SUPABASE_KEY",
        "FACEBOOK_ACCESS_TOKEN",
        "OPENROUTER_API_KEY_1",
        "PEXELS_API_KEY",
    ]

    for var in sensitive_vars:
        value = os.getenv(var, "")

        if value:
            is_valid, msg = InputValidator.validate_api_key(value)
            if not is_valid:
                results["issues"].append(f"{var}: {msg}")

    # Check for master encryption key
    if not os.getenv("MASTER_ENCRYPTION_KEY"):
        results["recommendations"].append("Set MASTER_ENCRYPTION_KEY for credential encryption")

    # Check for debug mode
    if os.getenv("DEBUG", "").lower() in ("true", "1"):
        results["issues"].append("DEBUG mode is enabled - disable for production")

    if results["issues"]:
        results["status"] = "WARNINGS"

    return results


if __name__ == "__main__":
    print("🔒 Security Utilities Demo\n")

    # Demo credential encryption
    print("📝 Credential Encryption:")
    manager = CredentialManager("test-master-key")
    encrypted = manager.encrypt("super-secret-api-key")
    decrypted = manager.decrypt(encrypted)
    print("  Original: super-secret-api-key")
    print(f"  Encrypted: {encrypted}")
    print(f"  Decrypted: {decrypted}")

    # Demo input validation
    print("\n✅ Input Validation:")
    print(
        f"  Valid URL 'https://example.com': {InputValidator.is_valid_url('https://example.com')}"
    )
    print(f"  Valid URL 'not-a-url': {InputValidator.is_valid_url('not-a-url')}")
    print(f"  Valid UUID: {InputValidator.is_valid_uuid('550e8400-e29b-41d4-a716-446655440000')}")

    # Demo token masking
    print("\n🎭 Token Masking:")
    token = "sk-abc123xyz789secretkey"
    print(f"  Original: {token}")
    print(f"  Masked: {mask_sensitive(token)}")

    # Environment check
    print("\n🔍 Environment Security Check:")
    check = check_environment_security()
    print(f"  Status: {check['status']}")
    for issue in check.get("issues", []):
        print(f"  ⚠️ {issue}")
    for rec in check.get("recommendations", []):
        print(f"  💡 {rec}")

    print("\n✅ Security module ready!")
