"""Custom exception hierarchy for Instagram Intelligence tool.

Hierarchy:
    InstagramIntelError (base)
    +-- CredentialError      -- Missing or invalid credentials
    +-- AuthError            -- Token/permission error
    |   +-- TokenExpiredError    -- Access token has expired
    +-- APIError             -- Graph API returned an error
    +-- RateLimitError       -- Rate limit exceeded
    +-- CacheError           -- Cache read/write/clear failure
    +-- ScraperError         -- General scraping failure (Phase 2)
        +-- AntiDetectionError   -- Bot detection triggered
        +-- SelectorTimeoutError -- DOM element not found in time
"""


class InstagramIntelError(Exception):
    """Base exception for all instagram-intel errors."""

    error_type: str = "instagram_intel_error"

    def to_dict(self) -> dict:
        """Serialize for JSON error output."""
        return {"error": str(self), "type": self.error_type}


class CredentialError(InstagramIntelError):
    """Missing or invalid credentials."""

    error_type = "credential_error"


class AuthError(InstagramIntelError):
    """Authentication or permission error."""

    error_type = "auth_error"


class TokenExpiredError(AuthError):
    """Access token has expired and needs refresh."""

    error_type = "token_expired_error"


class APIError(InstagramIntelError):
    """Meta Graph API returned an error."""

    error_type = "api_error"

    def __init__(self, message: str, code: int = 0, subcode: int = 0,
                 error_type: str = "", fbtrace_id: str = ""):
        self.code = code
        self.subcode = subcode
        self.api_error_type = error_type
        self.fbtrace_id = fbtrace_id
        super().__init__(message)

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.code:
            d["code"] = self.code
        if self.fbtrace_id:
            d["fbtrace_id"] = self.fbtrace_id
        return d


class RateLimitError(InstagramIntelError):
    """Rate limit exceeded."""

    error_type = "rate_limit_error"

    def __init__(self, message: str = "Rate limited by Meta Graph API",
                 retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.retry_after:
            d["retry_after"] = self.retry_after
        return d


class CacheError(InstagramIntelError):
    """Cache read, write, or clear failure."""

    error_type = "cache_error"


class ScraperError(InstagramIntelError):
    """General scraping failure (Phase 2)."""

    error_type = "scraper_error"


class AntiDetectionError(ScraperError):
    """Bot detection was triggered."""

    error_type = "anti_detection_error"


class SelectorTimeoutError(ScraperError):
    """Expected DOM element was not found within the timeout period."""

    error_type = "selector_timeout_error"

    def __init__(self, selector: str, timeout_ms: int = 0):
        msg = f"Selector '{selector}' not found"
        if timeout_ms:
            msg += f" within {timeout_ms}ms"
        super().__init__(msg)
        self.selector = selector
        self.timeout_ms = timeout_ms

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["selector"] = self.selector
        return d
