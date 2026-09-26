"""Shared base for all resource managers."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cartpanda.client import CartPandaClient


class BaseResource:
    """Holds a back-reference to the parent client."""

    def __init__(self, client: "CartPandaClient") -> None:
        self._client = client

    @property
    def shop_slug(self) -> str:
        return self._client.settings.shop_slug
