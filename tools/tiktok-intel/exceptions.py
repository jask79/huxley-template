"""Custom exception hierarchy for TikTok Intelligence tool.

Hierarchy:
    TikTokIntelError (base)
    +-- BrowserLaunchError    — Playwright/Chromium failed to start
    +-- CacheError            — Cache read/write/clear failure
    +-- RateLimitError        — Detected rate limiting or CAPTCHA challenge
    +-- ScraperError          — General scraping failure
        +-- AntiDetectionError    — Bot detection triggered
        +-- SelectorTimeoutError  — Expected DOM element not found in time
"""


class TikTokIntelError(Exception):
    """Base exception for all tiktok-intel errors."""

    error_type: str = "tiktok_intel_error"

    def to_dict(self) -> dict:
        """Serialize for JSON error output."""
        return {"error": str(self), "type": self.error_type}


class BrowserLaunchError(TikTokIntelError):
    """Playwright or Chromium failed to start."""

    error_type = "browser_launch_error"


class CacheError(TikTokIntelError):
    """Cache read, write, or clear failure."""

    error_type = "cache_error"


class RateLimitError(TikTokIntelError):
    """Detected rate limiting, CAPTCHA challenge, or access block."""

    error_type = "rate_limit_error"

    def __init__(self, message: str = "Rate limited by TikTok", retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.retry_after:
            d["retry_after"] = self.retry_after
        return d


class ScraperError(TikTokIntelError):
    """General scraping failure — page structure changed, unexpected response, etc."""

    error_type = "scraper_error"


class AntiDetectionError(ScraperError):
    """Bot detection was triggered (e.g., Cloudflare challenge, CAPTCHA wall)."""

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
