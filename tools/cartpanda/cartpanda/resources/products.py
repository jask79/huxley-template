"""Products resource — V3 endpoints.

Endpoint paths below are best-guess from the public CartPanda docs landing
page. Confirm exact paths against https://dev.cartpanda.com/ once {{USER_NAME}} has
account access. The legacy CartX equivalents exist; prefer V3.
"""
from __future__ import annotations

from typing import Any, Optional

from cartpanda.resources._base import BaseResource
from cartpanda.types import Product, ProductCreate, ProductUpdate


class ProductsResource(BaseResource):
    """CRUD operations for catalog products."""

    # TODO: confirm path — may be /shop/{slug}/products instead of /products
    _path = "/products"

    def list(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        status: Optional[str] = None,
        **filters: Any,
    ) -> list[Product]:
        """List products.

        Args:
            page: 1-indexed page number.
            per_page: items per page.
            status: optional status filter ("active", "draft", "archived").
            **filters: additional query params passed through verbatim.
        """
        params: dict[str, Any] = {"page": page, "per_page": per_page, **filters}
        if status is not None:
            params["status"] = status
        data = self._client.get(self._path, params=params)
        items = data.get("products", data) if isinstance(data, dict) else data
        return [Product.model_validate(p) for p in (items or [])]

    def get(self, product_id: int | str) -> Product:
        """Retrieve a single product."""
        data = self._client.get(f"{self._path}/{product_id}")
        payload = data.get("product", data) if isinstance(data, dict) else data
        return Product.model_validate(payload)

    def create(self, product: ProductCreate | dict[str, Any]) -> Product:
        """Create a new product."""
        body = product.model_dump(exclude_none=True) if isinstance(product, ProductCreate) else product
        data = self._client.post(self._path, json={"product": body})
        payload = data.get("product", data) if isinstance(data, dict) else data
        return Product.model_validate(payload)

    def update(self, product_id: int | str, patch: ProductUpdate | dict[str, Any]) -> Product:
        """Update an existing product (partial update)."""
        body = patch.model_dump(exclude_none=True) if isinstance(patch, ProductUpdate) else patch
        # TODO: confirm whether CartPanda uses PUT or PATCH for partial updates
        data = self._client.put(f"{self._path}/{product_id}", json={"product": body})
        payload = data.get("product", data) if isinstance(data, dict) else data
        return Product.model_validate(payload)

    def delete(self, product_id: int | str) -> None:
        """Delete a product."""
        self._client.delete(f"{self._path}/{product_id}")
