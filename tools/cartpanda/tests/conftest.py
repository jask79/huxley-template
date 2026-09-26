"""pytest fixtures shared across the cartpanda test suite."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the cartpanda package is importable without installing
PKG_ROOT = Path(__file__).resolve().parent.parent
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))

import pytest

from cartpanda import CartPandaClient, CartPandaSettings


@pytest.fixture
def settings() -> CartPandaSettings:
    """Hermetic test settings — never read from a real .env."""
    return CartPandaSettings(
        api_key="test_key_abc123",
        base_url="https://cartpanda.test/api/v3",
        shop_slug="test-shop",
        webhook_secret="test_secret",
        max_retries=0,  # don't slow tests down with retry loops
        timeout_seconds=5.0,
    )


@pytest.fixture
def client(settings: CartPandaSettings) -> CartPandaClient:
    """Construct a client wired to the hermetic settings."""
    return CartPandaClient(settings=settings)
