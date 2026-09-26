"""Webhooks resource — subscribe / list / delete webhook subscriptions.

CartPanda also lets you configure webhooks via the dashboard at
https://accounts.cartpanda.com/settings/webhooks. The API gives you the
same control programmatically.
"""
from __future__ import annotations

from typing import Any

from cartpanda.resources._base import BaseResource
from cartpanda.types import WebhookCreate, WebhookEvent, WebhookSubscription


class WebhooksResource(BaseResource):
    """Manage webhook subscriptions."""

    _path = "/webhooks"

    def create(self, webhook: WebhookCreate | dict[str, Any]) -> WebhookSubscription:
        """Subscribe to a webhook topic.

        Example:
            client.webhooks.create(WebhookCreate(
                topic="order.paid",
                address="https://example.com/cartpanda/webhook",
            ))
        """
        body = (
            webhook.model_dump(exclude_none=True)
            if isinstance(webhook, WebhookCreate)
            else webhook
        )
        data = self._client.post(self._path, json={"webhook": body})
        payload = data.get("webhook", data) if isinstance(data, dict) else data
        return WebhookSubscription.model_validate(payload)

    def list(self, *, topic: WebhookEvent | None = None) -> list[WebhookSubscription]:
        """List all webhook subscriptions, optionally filtered by topic."""
        params: dict[str, Any] = {}
        if topic:
            params["topic"] = topic
        data = self._client.get(self._path, params=params or None)
        items = data.get("webhooks", data) if isinstance(data, dict) else data
        return [WebhookSubscription.model_validate(w) for w in (items or [])]

    def get(self, webhook_id: int | str) -> WebhookSubscription:
        """Retrieve a single webhook subscription."""
        data = self._client.get(f"{self._path}/{webhook_id}")
        payload = data.get("webhook", data) if isinstance(data, dict) else data
        return WebhookSubscription.model_validate(payload)

    def delete(self, webhook_id: int | str) -> None:
        """Delete a webhook subscription."""
        self._client.delete(f"{self._path}/{webhook_id}")
