"""CartPanda REST client.

Thin wrapper over httpx that handles:
- Auth header injection (TODO: confirm header name once you have account access)
- Retries with exponential backoff for transient errors (5xx, 429)
- Status-code → exception mapping
- Consistent JSON parsing

Usage:
    from cartpanda import CartPandaClient

    with CartPandaClient() as client:
        order = client.orders.get(12345)

Or async:
    async with CartPandaClient.async_client() as client:
        order = await client.orders.aget(12345)

Resource methods are organized under client.products, client.carts, etc.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cartpanda.exceptions import (
    CartPandaAPIError,
    CartPandaAuthError,
    CartPandaNotFoundError,
    CartPandaRateLimitError,
    CartPandaServerError,
)

logger = logging.getLogger("cartpanda.client")


# ──────────────────────────────────────────────────────────────────────
# Settings
# ──────────────────────────────────────────────────────────────────────
class CartPandaSettings(BaseSettings):
    """Loaded from environment / .env file.

    Env var prefix: CARTPANDA_  (e.g. CARTPANDA_API_KEY).
    """

    model_config = SettingsConfigDict(
        env_prefix="CARTPANDA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str = Field(default="", description="API key / bearer token")
    base_url: str = Field(
        default="https://accounts.cartpanda.com/api/v3",
        description="Base URL for the V3 API. TODO: confirm once account is live.",
    )
    shop_slug: str = Field(default="", description="Shop slug for shop-scoped endpoints")
    webhook_secret: str = Field(default="", description="Webhook signing secret")

    timeout_seconds: float = 30.0
    max_retries: int = 3
    log_level: str = "INFO"


# ──────────────────────────────────────────────────────────────────────
# Status → exception mapping
# ──────────────────────────────────────────────────────────────────────
def _raise_for_status(response: httpx.Response, *, method: str, url: str) -> None:
    """Map an httpx response status to the appropriate CartPanda exception."""
    if response.is_success:
        return

    try:
        body: Any = response.json()
    except (ValueError, httpx.DecodingError):
        body = response.text

    message = _extract_error_message(body) or response.reason_phrase or "CartPanda API error"
    status = response.status_code
    common_kwargs = {"status_code": status, "body": body, "method": method, "url": url}

    if status in (401, 403):
        raise CartPandaAuthError(message, **common_kwargs)
    if status == 404:
        raise CartPandaNotFoundError(message, **common_kwargs)
    if status == 429:
        retry_after_hdr = response.headers.get("Retry-After")
        retry_after = float(retry_after_hdr) if retry_after_hdr else None
        raise CartPandaRateLimitError(message, retry_after=retry_after, **common_kwargs)
    if 500 <= status < 600:
        raise CartPandaServerError(message, **common_kwargs)
    raise CartPandaAPIError(message, **common_kwargs)


def _extract_error_message(body: Any) -> Optional[str]:
    """Best-effort extraction of a human-readable error from a response body."""
    if isinstance(body, dict):
        for key in ("message", "error", "detail", "error_description"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
        if "errors" in body:
            errs = body["errors"]
            if isinstance(errs, list) and errs:
                return str(errs[0])
            if isinstance(errs, dict) and errs:
                first_key = next(iter(errs))
                return f"{first_key}: {errs[first_key]}"
    if isinstance(body, str) and body:
        return body[:500]
    return None


# ──────────────────────────────────────────────────────────────────────
# Client
# ──────────────────────────────────────────────────────────────────────
class CartPandaClient:
    """Synchronous CartPanda REST client.

    Lazily attaches resource managers (products, carts, orders, customers,
    fulfillment, webhooks) on first access. Use as a context manager so the
    underlying httpx.Client is closed cleanly.
    """

    def __init__(
        self,
        settings: Optional[CartPandaSettings] = None,
        *,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.settings = settings or CartPandaSettings()
        if not self.settings.api_key:
            logger.warning(
                "CartPanda API key is empty — calls will fail. "
                "Set CARTPANDA_API_KEY in .env or environment."
            )
        self._http = http_client or httpx.Client(
            base_url=self.settings.base_url,
            timeout=self.settings.timeout_seconds,
            headers=self._default_headers(),
        )
        self._owns_http = http_client is None

        # Resource managers — imported here to avoid circular import at module load
        from cartpanda.resources.carts import CartsResource
        from cartpanda.resources.customers import CustomersResource
        from cartpanda.resources.fulfillment import FulfillmentResource
        from cartpanda.resources.orders import OrdersResource
        from cartpanda.resources.products import ProductsResource
        from cartpanda.resources.webhooks import WebhooksResource

        self.products = ProductsResource(self)
        self.carts = CartsResource(self)
        self.orders = OrdersResource(self)
        self.customers = CustomersResource(self)
        self.fulfillment = FulfillmentResource(self)
        self.webhooks = WebhooksResource(self)

    # ── Header construction ───────────────────────────────────────────
    def _default_headers(self) -> dict[str, str]:
        """Build default headers.

        TODO: Confirm CartPanda's exact auth scheme once you have account
        access. The two most common patterns are:
            Authorization: Bearer <token>
            X-API-Key: <token>
        We default to Bearer; swap below if docs say otherwise.
        """
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "catalyst-cartpanda/0.1.0",
        }
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        return headers

    # ── Context manager ───────────────────────────────────────────────
    def __enter__(self) -> "CartPandaClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    # ── Core request method with retry ────────────────────────────────
    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """Issue a request and return parsed JSON.

        Retries on 429 and 5xx with exponential backoff up to
        settings.max_retries. Non-retryable errors raise immediately.
        """
        url = path if path.startswith("http") else path
        attempt = 0
        backoff = 1.0

        while True:
            attempt += 1
            logger.debug("CartPanda %s %s (attempt %d)", method, url, attempt)
            try:
                response = self._http.request(
                    method, url, params=params, json=json, headers=headers
                )
            except httpx.RequestError as exc:
                if attempt > self.settings.max_retries:
                    raise CartPandaAPIError(
                        f"Network error after {attempt} attempts: {exc}",
                        method=method,
                        url=url,
                    ) from exc
                time.sleep(backoff)
                backoff *= 2
                continue

            # Decide retry vs raise vs return
            if response.status_code == 429 and attempt <= self.settings.max_retries:
                retry_after = float(response.headers.get("Retry-After", backoff))
                logger.warning("CartPanda rate limited — sleeping %.1fs", retry_after)
                time.sleep(retry_after)
                backoff *= 2
                continue
            if 500 <= response.status_code < 600 and attempt <= self.settings.max_retries:
                logger.warning(
                    "CartPanda server error %d — retrying in %.1fs", response.status_code, backoff
                )
                time.sleep(backoff)
                backoff *= 2
                continue

            _raise_for_status(response, method=method, url=url)
            if response.status_code == 204 or not response.content:
                return None
            try:
                return response.json()
            except ValueError as exc:
                raise CartPandaAPIError(
                    f"Failed to decode JSON response: {exc}",
                    status_code=response.status_code,
                    body=response.text,
                    method=method,
                    url=url,
                ) from exc

    # ── Convenience shortcuts ─────────────────────────────────────────
    def get(self, path: str, **kw: Any) -> Any:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw: Any) -> Any:
        return self.request("POST", path, **kw)

    def put(self, path: str, **kw: Any) -> Any:
        return self.request("PUT", path, **kw)

    def patch(self, path: str, **kw: Any) -> Any:
        return self.request("PATCH", path, **kw)

    def delete(self, path: str, **kw: Any) -> Any:
        return self.request("DELETE", path, **kw)
