"""Carts resource.

TODO: confirm endpoint shape — CartPanda's cart endpoints may differ between
the storefront flow and the API. Adjust once docs are accessible.
"""
from __future__ import annotations

from typing import Any

from cartpanda.resources._base import BaseResource
from cartpanda.types import Cart, CartCreate, CartLineItem


class CartsResource(BaseResource):
    """Create / retrieve / update checkout carts."""

    _path = "/carts"

    def create(self, cart: CartCreate | dict[str, Any]) -> Cart:
        """Create a new cart and return the server-side representation."""
        body = cart.model_dump(exclude_none=True) if isinstance(cart, CartCreate) else cart
        data = self._client.post(self._path, json={"cart": body})
        payload = data.get("cart", data) if isinstance(data, dict) else data
        return Cart.model_validate(payload)

    def get(self, cart_id: int | str) -> Cart:
        """Retrieve a cart by id (or token — TODO confirm)."""
        data = self._client.get(f"{self._path}/{cart_id}")
        payload = data.get("cart", data) if isinstance(data, dict) else data
        return Cart.model_validate(payload)

    def update(self, cart_id: int | str, patch: dict[str, Any]) -> Cart:
        """Update a cart (line items, email, attributes, etc.)."""
        # TODO: confirm PUT vs PATCH
        data = self._client.put(f"{self._path}/{cart_id}", json={"cart": patch})
        payload = data.get("cart", data) if isinstance(data, dict) else data
        return Cart.model_validate(payload)

    def add_line_item(self, cart_id: int | str, item: CartLineItem | dict[str, Any]) -> Cart:
        """Convenience: append a single line item to an existing cart."""
        existing = self.get(cart_id)
        line_items = [li.model_dump(exclude_none=True) for li in (existing.line_items or [])]
        new_item = item.model_dump(exclude_none=True) if isinstance(item, CartLineItem) else item
        line_items.append(new_item)
        return self.update(cart_id, {"line_items": line_items})
