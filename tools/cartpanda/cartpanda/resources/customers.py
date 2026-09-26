"""Customers resource."""
from __future__ import annotations

from typing import Any

from cartpanda.resources._base import BaseResource
from cartpanda.types import Customer, CustomerCreate


class CustomersResource(BaseResource):
    """Create + retrieve customers."""

    _path = "/customers"

    def create(self, customer: CustomerCreate | dict[str, Any]) -> Customer:
        """Create a new customer record."""
        body = (
            customer.model_dump(exclude_none=True)
            if isinstance(customer, CustomerCreate)
            else customer
        )
        data = self._client.post(self._path, json={"customer": body})
        payload = data.get("customer", data) if isinstance(data, dict) else data
        return Customer.model_validate(payload)

    def get(self, customer_id: int | str) -> Customer:
        """Retrieve a customer by id."""
        data = self._client.get(f"{self._path}/{customer_id}")
        payload = data.get("customer", data) if isinstance(data, dict) else data
        return Customer.model_validate(payload)

    def search(self, query: str, *, limit: int = 20) -> list[Customer]:
        """Search customers by email/name/phone."""
        # TODO: confirm — may be GET /customers/search?query=...
        data = self._client.get(f"{self._path}/search", params={"query": query, "limit": limit})
        items = data.get("customers", data) if isinstance(data, dict) else data
        return [Customer.model_validate(c) for c in (items or [])]
