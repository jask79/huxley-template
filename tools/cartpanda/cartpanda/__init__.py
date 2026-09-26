"""CartPanda API integration tool.

Reusable client + webhook receiver for CartPanda's REST API.
Used by Huxley capsules that need paid-traffic checkout/upsell (e.g. acme-store).
"""
from cartpanda.client import CartPandaClient, CartPandaSettings
from cartpanda.exceptions import (
    CartPandaAPIError,
    CartPandaAuthError,
    CartPandaNotFoundError,
    CartPandaRateLimitError,
    CartPandaServerError,
    CartPandaWebhookSignatureError,
)

__version__ = "0.1.0"

__all__ = [
    "CartPandaClient",
    "CartPandaSettings",
    "CartPandaAPIError",
    "CartPandaAuthError",
    "CartPandaNotFoundError",
    "CartPandaRateLimitError",
    "CartPandaServerError",
    "CartPandaWebhookSignatureError",
]
