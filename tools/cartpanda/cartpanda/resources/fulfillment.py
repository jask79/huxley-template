"""Fulfillment resource — push tracking numbers, mark orders fulfilled."""
from __future__ import annotations

from typing import Any

from cartpanda.resources._base import BaseResource
from cartpanda.types import Fulfillment, FulfillmentCreate


class FulfillmentResource(BaseResource):
    """Create fulfillment records against orders."""

    def create(
        self,
        order_id: int | str,
        fulfillment: FulfillmentCreate | dict[str, Any],
    ) -> Fulfillment:
        """Create a fulfillment for an order (typically with a tracking number)."""
        body = (
            fulfillment.model_dump(exclude_none=True)
            if isinstance(fulfillment, FulfillmentCreate)
            else fulfillment
        )
        # TODO: confirm path — may be /orders/{id}/fulfillments or /fulfillments
        data = self._client.post(
            f"/orders/{order_id}/fulfillments", json={"fulfillment": body}
        )
        payload = data.get("fulfillment", data) if isinstance(data, dict) else data
        return Fulfillment.model_validate(payload)

    def get(self, order_id: int | str, fulfillment_id: int | str) -> Fulfillment:
        """Retrieve a single fulfillment record."""
        data = self._client.get(
            f"/orders/{order_id}/fulfillments/{fulfillment_id}"
        )
        payload = data.get("fulfillment", data) if isinstance(data, dict) else data
        return Fulfillment.model_validate(payload)

    def list(self, order_id: int | str) -> list[Fulfillment]:
        """List all fulfillments for an order."""
        data = self._client.get(f"/orders/{order_id}/fulfillments")
        items = data.get("fulfillments", data) if isinstance(data, dict) else data
        return [Fulfillment.model_validate(f) for f in (items or [])]

    def update_tracking(
        self,
        order_id: int | str,
        fulfillment_id: int | str,
        *,
        tracking_number: str,
        tracking_company: str | None = None,
        tracking_url: str | None = None,
    ) -> Fulfillment:
        """Update tracking info on an existing fulfillment."""
        body: dict[str, Any] = {"tracking_number": tracking_number}
        if tracking_company:
            body["tracking_company"] = tracking_company
        if tracking_url:
            body["tracking_url"] = tracking_url
        data = self._client.put(
            f"/orders/{order_id}/fulfillments/{fulfillment_id}",
            json={"fulfillment": body},
        )
        payload = data.get("fulfillment", data) if isinstance(data, dict) else data
        return Fulfillment.model_validate(payload)
