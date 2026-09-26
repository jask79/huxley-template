"""Client smoke tests using respx to mock httpx."""
from __future__ import annotations

import httpx
import pytest
import respx

from cartpanda import CartPandaClient
from cartpanda.exceptions import (
    CartPandaAPIError,
    CartPandaAuthError,
    CartPandaNotFoundError,
    CartPandaRateLimitError,
    CartPandaServerError,
)


@respx.mock
def test_default_auth_header(client: CartPandaClient) -> None:
    """Bearer token is attached to outbound requests."""
    route = respx.get("https://cartpanda.test/api/v3/products").mock(
        return_value=httpx.Response(200, json={"products": []})
    )
    client.get("/products")
    assert route.called
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer test_key_abc123"
    assert sent.headers["Accept"] == "application/json"


@respx.mock
def test_get_parses_json(client: CartPandaClient) -> None:
    respx.get("https://cartpanda.test/api/v3/orders/42").mock(
        return_value=httpx.Response(200, json={"order": {"id": 42, "email": "a@b.c"}})
    )
    order = client.orders.get(42)
    assert order.id == 42
    assert order.email == "a@b.c"


@respx.mock
def test_401_raises_auth_error(client: CartPandaClient) -> None:
    respx.get("https://cartpanda.test/api/v3/products").mock(
        return_value=httpx.Response(401, json={"message": "Bad token"})
    )
    with pytest.raises(CartPandaAuthError) as exc:
        client.get("/products")
    assert exc.value.status_code == 401


@respx.mock
def test_404_raises_not_found(client: CartPandaClient) -> None:
    respx.get("https://cartpanda.test/api/v3/orders/999").mock(
        return_value=httpx.Response(404, json={"message": "Not found"})
    )
    with pytest.raises(CartPandaNotFoundError):
        client.orders.get(999)


@respx.mock
def test_429_raises_rate_limit(client: CartPandaClient) -> None:
    respx.get("https://cartpanda.test/api/v3/products").mock(
        return_value=httpx.Response(
            429, json={"message": "Slow down"}, headers={"Retry-After": "2"}
        )
    )
    with pytest.raises(CartPandaRateLimitError) as exc:
        client.get("/products")
    assert exc.value.retry_after == 2.0


@respx.mock
def test_500_raises_server_error(client: CartPandaClient) -> None:
    respx.get("https://cartpanda.test/api/v3/products").mock(
        return_value=httpx.Response(500, text="Boom")
    )
    with pytest.raises(CartPandaServerError):
        client.get("/products")


@respx.mock
def test_204_returns_none(client: CartPandaClient) -> None:
    respx.delete("https://cartpanda.test/api/v3/products/1").mock(
        return_value=httpx.Response(204)
    )
    assert client.delete("/products/1") is None


@respx.mock
def test_products_create_serializes_pydantic(client: CartPandaClient) -> None:
    from cartpanda.types import ProductCreate

    route = respx.post("https://cartpanda.test/api/v3/products").mock(
        return_value=httpx.Response(
            201,
            json={"product": {"id": 1, "title": "Liver Support", "status": "draft"}},
        )
    )
    product = client.products.create(ProductCreate(title="Liver Support", vendor="Example Co"))
    assert route.called
    sent = route.calls.last.request
    import json as _json

    body = _json.loads(sent.content)
    assert body == {"product": {"title": "Liver Support", "vendor": "Example Co", "status": "draft"}}
    assert product.id == 1


@respx.mock
def test_generic_4xx_raises_api_error(client: CartPandaClient) -> None:
    respx.post("https://cartpanda.test/api/v3/orders").mock(
        return_value=httpx.Response(422, json={"errors": ["bad email"]})
    )
    with pytest.raises(CartPandaAPIError) as exc:
        client.post("/orders", json={"order": {}})
    assert exc.value.status_code == 422
