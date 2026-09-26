"""Tests for the FastAPI webhook receiver."""
from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient

from cartpanda import webhook_receiver as wr


@pytest.fixture(autouse=True)
def _set_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CARTPANDA_WEBHOOK_SECRET", "test_secret")


@pytest.fixture
def http_client() -> TestClient:
    return TestClient(wr.app)


def _sign(body: bytes, secret: str = "test_secret") -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_health(http_client: TestClient) -> None:
    r = http_client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_missing_signature_returns_401(http_client: TestClient) -> None:
    r = http_client.post(
        "/webhooks/cartpanda",
        content=b"{}",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 401


def test_bad_signature_returns_401(http_client: TestClient) -> None:
    r = http_client.post(
        "/webhooks/cartpanda",
        content=b'{"id":1}',
        headers={
            "Content-Type": "application/json",
            "X-CartPanda-Signature": "deadbeef",
            "X-CartPanda-Topic": "order.paid",
        },
    )
    assert r.status_code == 401


def test_good_signature_dispatches(http_client: TestClient) -> None:
    body = json.dumps({"id": 12345, "email": "buyer@example.com"}).encode()
    sig = _sign(body)
    r = http_client.post(
        "/webhooks/cartpanda",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-CartPanda-Signature": sig,
            "X-CartPanda-Topic": "order.paid",
        },
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["received"] is True
    assert j["topic"] == "order.paid"
    assert j["handled"] is True


def test_custom_handler_runs(http_client: TestClient) -> None:
    seen: dict[str, dict] = {}

    @wr.on_event("order.refunded")
    async def handler(payload: dict) -> None:
        seen["payload"] = payload

    body = json.dumps({"id": 9, "refund": True}).encode()
    sig = _sign(body)
    r = http_client.post(
        "/webhooks/cartpanda",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-CartPanda-Signature": sig,
            "X-CartPanda-Topic": "order.refunded",
        },
    )
    assert r.status_code == 200
    assert seen["payload"]["id"] == 9


def test_invalid_json_returns_400(http_client: TestClient) -> None:
    body = b"not-json"
    sig = _sign(body)
    r = http_client.post(
        "/webhooks/cartpanda",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-CartPanda-Signature": sig,
            "X-CartPanda-Topic": "order.paid",
        },
    )
    assert r.status_code == 400


def test_oversized_body_returns_413(http_client: TestClient) -> None:
    # 2MB + 1 byte
    body = b"x" * (wr.MAX_PAYLOAD_BYTES + 1)
    sig = _sign(body)
    r = http_client.post(
        "/webhooks/cartpanda",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-CartPanda-Signature": sig,
            "X-CartPanda-Topic": "order.paid",
        },
    )
    assert r.status_code == 413


def test_unknown_topic_returns_200_unhandled(http_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Remove the default handler for this topic to simulate "no handler"
    monkeypatch.setitem(wr._handlers, "order.created", None)  # type: ignore[arg-type]
    wr._handlers.pop("order.created", None)

    body = json.dumps({"id": 1}).encode()
    sig = _sign(body)
    r = http_client.post(
        "/webhooks/cartpanda",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-CartPanda-Signature": sig,
            "X-CartPanda-Topic": "order.created",
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["handled"] is False


def test_signature_skipped_when_secret_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty secret → verification is a warning, not a failure (dev convenience)."""
    monkeypatch.setenv("CARTPANDA_WEBHOOK_SECRET", "")
    c = TestClient(wr.app)
    body = json.dumps({"id": 5}).encode()
    r = c.post(
        "/webhooks/cartpanda",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-CartPanda-Topic": "order.paid",
        },
    )
    assert r.status_code == 200
