"""Orders resource.

Read-side focus: list, retrieve, payment gateway info, transaction tokens,
line items. Order creation is normally driven by the checkout/upsell flow,
not the API — but a create() stub is included for completeness.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from cartpanda.resources._base import BaseResource
from cartpanda.types import Order, OrderLineItem, OrderListResponse, PaymentGateway


class OrdersResource(BaseResource):
    """Read orders, drill into payment + line item details."""

    _path = "/orders"

    # ── Listing & retrieval ───────────────────────────────────────────
    def list(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        status: Optional[str] = None,
        financial_status: Optional[str] = None,
        fulfillment_status: Optional[str] = None,
        created_at_min: Optional[datetime] = None,
        created_at_max: Optional[datetime] = None,
        **filters: Any,
    ) -> OrderListResponse:
        """List orders with common filters."""
        params: dict[str, Any] = {"page": page, "per_page": per_page, **filters}
        if status:
            params["status"] = status
        if financial_status:
            params["financial_status"] = financial_status
        if fulfillment_status:
            params["fulfillment_status"] = fulfillment_status
        if created_at_min:
            params["created_at_min"] = created_at_min.isoformat()
        if created_at_max:
            params["created_at_max"] = created_at_max.isoformat()
        data = self._client.get(self._path, params=params)

        if isinstance(data, dict) and "orders" in data:
            return OrderListResponse.model_validate(data)
        # API may return a bare list
        return OrderListResponse(orders=[Order.model_validate(o) for o in (data or [])])

    def get(self, order_id: int | str) -> Order:
        """Retrieve a single order."""
        data = self._client.get(f"{self._path}/{order_id}")
        payload = data.get("order", data) if isinstance(data, dict) else data
        return Order.model_validate(payload)

    # ── Sub-resource accessors ────────────────────────────────────────
    def line_items(self, order_id: int | str) -> list[OrderLineItem]:
        """Return the line items for an order.

        Falls back to the order's nested line_items if there's no dedicated
        endpoint. TODO: confirm whether CartPanda exposes a separate path.
        """
        # TODO: confirm endpoint — may be /orders/{id}/line_items
        try:
            data = self._client.get(f"{self._path}/{order_id}/line_items")
            items = data.get("line_items", data) if isinstance(data, dict) else data
            return [OrderLineItem.model_validate(li) for li in (items or [])]
        except Exception:
            return self.get(order_id).line_items or []

    def payment_gateway(self, order_id: int | str) -> Optional[PaymentGateway]:
        """Return the payment gateway info for an order."""
        # TODO: confirm — may be inline on the order or at /orders/{id}/payment
        order = self.get(order_id)
        return order.payment_gateway

    def transaction_tokens(self, order_id: int | str) -> dict[str, Any]:
        """Fetch transaction tokens for an order.

        CartPanda's DR/upsell flow uses transaction tokens to chain post-purchase
        upsells onto the original payment method without re-authorizing the buyer.
        TODO: confirm exact endpoint path.
        """
        return self._client.get(f"{self._path}/{order_id}/transaction_tokens")

    # ── Mutations (optional) ──────────────────────────────────────────
    def create(self, order_payload: dict[str, Any]) -> Order:
        """Create an order programmatically (rarely used)."""
        data = self._client.post(self._path, json={"order": order_payload})
        payload = data.get("order", data) if isinstance(data, dict) else data
        return Order.model_validate(payload)

    def cancel(self, order_id: int | str, *, reason: Optional[str] = None) -> Order:
        """Cancel an order."""
        body: dict[str, Any] = {}
        if reason:
            body["reason"] = reason
        # TODO: confirm — may be POST /orders/{id}/cancel
        data = self._client.post(f"{self._path}/{order_id}/cancel", json=body)
        payload = data.get("order", data) if isinstance(data, dict) else data
        return Order.model_validate(payload)
