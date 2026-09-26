"""FastAPI webhook receiver for CartPanda events.

Run locally:
    .venv/bin/uvicorn cartpanda.webhook_receiver:app \
        --host 127.0.0.1 --port 3201 --reload

Expose publicly (for local dev) with ngrok / cloudflared:
    ngrok http 3201

Then subscribe via the API:
    .venv/bin/python tools/cartpanda/scripts/test_connection.py
    (or use client.webhooks.create(...))

Topics handled (from the task brief):
    product.created, product.updated, product.deleted
    order.created, order.paid, order.updated, order.refunded

Payloads can be up to 2MB — FastAPI handles that fine but the underlying
ASGI server's default body size limits should be verified before deployment.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from cartpanda.exceptions import CartPandaWebhookSignatureError
from cartpanda.types import WebhookEnvelope

logger = logging.getLogger("cartpanda.webhook")
logging.basicConfig(level=os.getenv("CARTPANDA_LOG_LEVEL", "INFO"))

# Max payload size — CartPanda documents up to 2MB. Reject larger up front.
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024


# ──────────────────────────────────────────────────────────────────────
# Signature verification
# ──────────────────────────────────────────────────────────────────────
def verify_signature(
    *,
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
) -> None:
    """Verify a CartPanda webhook signature.

    !!! TODO !!!
    CartPanda's exact webhook signing mechanism is NOT publicly documented at
    scaffold time. Once you have account access, confirm:
      1. Header name (likely X-CartPanda-Signature or X-Webhook-Signature)
      2. Algorithm (HMAC-SHA256 is the industry default)
      3. Encoding (hex vs base64)
      4. Whether the signed payload is the raw body, body+timestamp, or body+secret

    The implementation below assumes HMAC-SHA256(secret, raw_body) returned
    as hex — this is the Shopify pattern (CartPanda's spiritual model).
    See: https://shopify.dev/docs/apps/webhooks/configuration/https#verify-webhook

    Once confirmed, swap the algorithm/encoding here. Until then, signature
    verification is a NO-OP if `secret` is empty (dev convenience) — set
    CARTPANDA_WEBHOOK_SECRET in .env to enforce.

    Raises:
        CartPandaWebhookSignatureError: signature missing or invalid.
    """
    if not secret:
        logger.warning(
            "CARTPANDA_WEBHOOK_SECRET is empty — skipping signature verification. "
            "DO NOT run like this in production."
        )
        return

    if not signature_header:
        raise CartPandaWebhookSignatureError("Missing signature header")

    # TODO: confirm encoding (hex below; some platforms use base64)
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature_header.strip()):
        raise CartPandaWebhookSignatureError("Webhook signature mismatch")


# ──────────────────────────────────────────────────────────────────────
# Event handler registry
# ──────────────────────────────────────────────────────────────────────
EventHandler = Callable[[dict[str, Any]], Awaitable[None]]
_handlers: dict[str, EventHandler] = {}


def on_event(topic: str) -> Callable[[EventHandler], EventHandler]:
    """Decorator to register a handler for a webhook topic.

    Usage in your capsule code:
        from cartpanda.webhook_receiver import on_event

        @on_event("order.paid")
        async def handle_order_paid(payload: dict) -> None:
            order_id = payload.get("id")
            ...  # persist to Supabase, trigger fulfillment, etc.
    """
    def decorator(fn: EventHandler) -> EventHandler:
        _handlers[topic] = fn
        logger.info("Registered handler for %s", topic)
        return fn
    return decorator


# ──────────────────────────────────────────────────────────────────────
# Default handlers (no-op stubs — override per capsule)
# ──────────────────────────────────────────────────────────────────────
async def _default_handler(topic: str, payload: dict[str, Any]) -> None:
    """Fallback when no handler is registered for a topic."""
    logger.info("[%s] received — no handler registered. Keys: %s", topic, list(payload.keys()))


# Pre-register all expected topics with the default handler so unhandled
# events still log cleanly rather than 404.
EXPECTED_TOPICS = [
    "product.created",
    "product.updated",
    "product.deleted",
    "order.created",
    "order.paid",
    "order.updated",
    "order.refunded",
]
for _topic in EXPECTED_TOPICS:
    _handlers.setdefault(
        _topic,
        lambda payload, _t=_topic: _default_handler(_t, payload),  # type: ignore[misc]
    )


# ──────────────────────────────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="CartPanda Webhook Receiver",
    version="0.1.0",
    description="Huxley-side receiver for CartPanda webhook events.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "cartpanda-webhook-receiver"}


@app.post("/webhooks/cartpanda")
async def receive_webhook(
    request: Request,
    x_cartpanda_signature: str | None = Header(default=None, alias="X-CartPanda-Signature"),
    x_cartpanda_topic: str | None = Header(default=None, alias="X-CartPanda-Topic"),
) -> JSONResponse:
    """Single entry point for all CartPanda webhook events.

    Dispatches to per-topic handlers registered via @on_event(...).

    Headers (TODO: confirm exact names with CartPanda once account is live):
        X-CartPanda-Signature: HMAC of body
        X-CartPanda-Topic:     event name (e.g. "order.paid")
    """
    # 1. Read raw body for signature verification (must be raw bytes, NOT parsed JSON)
    raw_body = await request.body()
    if len(raw_body) > MAX_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Payload exceeds {MAX_PAYLOAD_BYTES} bytes",
        )

    secret = os.getenv("CARTPANDA_WEBHOOK_SECRET", "")
    try:
        verify_signature(
            raw_body=raw_body,
            signature_header=x_cartpanda_signature,
            secret=secret,
        )
    except CartPandaWebhookSignatureError as exc:
        logger.warning("Signature verification failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    # 2. Parse JSON
    try:
        payload: dict[str, Any] = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid JSON: {exc}")

    # 3. Determine topic — header first, fall back to envelope field
    topic = x_cartpanda_topic
    if not topic:
        try:
            envelope = WebhookEnvelope.model_validate(payload)
            topic = envelope.topic
        except Exception:  # noqa: BLE001 — best-effort
            topic = None
    if not topic:
        logger.warning("Webhook received with no resolvable topic. Body keys: %s", list(payload.keys()))
        return JSONResponse({"received": True, "topic": None})

    # 4. Dispatch
    handler = _handlers.get(topic)
    if handler is None:
        logger.info("No handler for topic %s — ignoring.", topic)
        return JSONResponse({"received": True, "topic": topic, "handled": False})

    try:
        await handler(payload)
    except Exception as exc:  # noqa: BLE001 — return 500 but log full trace
        logger.exception("Handler for %s raised: %s", topic, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Handler error: {exc}",
        )

    return JSONResponse({"received": True, "topic": topic, "handled": True})
