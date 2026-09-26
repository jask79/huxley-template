"""CartPanda exception hierarchy.

All errors raised by the client inherit from CartPandaAPIError so callers can
catch broadly or narrowly. HTTP status codes map to specific subclasses.
"""
from __future__ import annotations

from typing import Any


class CartPandaError(Exception):
    """Base class for all CartPanda integration errors (client + webhook)."""


class CartPandaAPIError(CartPandaError):
    """Raised when the CartPanda API returns a non-success response.

    Attributes:
        status_code: HTTP status code from the response.
        body: Parsed JSON body (dict) or raw text if not JSON.
        method: HTTP method used.
        url: Full request URL.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: Any = None,
        method: str | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.method = method
        self.url = url

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.method and self.url:
            parts.append(f"{self.method} {self.url}")
        return " | ".join(parts)


class CartPandaAuthError(CartPandaAPIError):
    """401 / 403 — API key missing, invalid, or insufficient scope."""


class CartPandaNotFoundError(CartPandaAPIError):
    """404 — resource does not exist."""


class CartPandaRateLimitError(CartPandaAPIError):
    """429 — rate limit exceeded. Check `retry_after` if provided."""

    def __init__(self, message: str, *, retry_after: float | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class CartPandaServerError(CartPandaAPIError):
    """5xx — server-side failure. Safe to retry with backoff."""


class CartPandaWebhookSignatureError(CartPandaError):
    """Raised when a webhook payload fails signature verification."""
