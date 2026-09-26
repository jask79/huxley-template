"""Pydantic models for CartPanda request/response shapes.

WARNING: These are best-guess placeholders. CartPanda's API docs at
https://dev.cartpanda.com/ are Stoplight-rendered SPAs that don't expose a
public OpenAPI spec, and {{USER_NAME}} doesn't have account access yet. Field types
and names should be confirmed against real API responses once {{USER_NAME}} has a
live account.

All models use `model_config = ConfigDict(extra="allow")` so unexpected
fields from the API don't blow up parsing — we'd rather receive extra data
than fail. Mark fields with `# TODO: confirm` where shapes are inferred.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ──────────────────────────────────────────────────────────────────────
# Base model
# ──────────────────────────────────────────────────────────────────────
class CartPandaModel(BaseModel):
    """Base model — permissive parsing so unexpected fields don't error."""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        str_strip_whitespace=True,
    )


# ──────────────────────────────────────────────────────────────────────
# Products
# ──────────────────────────────────────────────────────────────────────
class ProductVariant(CartPandaModel):
    """A single SKU/variant of a product."""

    id: Optional[int | str] = None  # TODO: confirm int vs uuid
    sku: Optional[str] = None
    title: Optional[str] = None
    price: Optional[Decimal] = None
    compare_at_price: Optional[Decimal] = None
    inventory_quantity: Optional[int] = None
    weight: Optional[float] = None
    weight_unit: Optional[Literal["kg", "g", "lb", "oz"]] = None  # TODO: confirm


class ProductCreate(CartPandaModel):
    """Payload for POST /products."""

    title: str
    description: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    status: Optional[Literal["active", "draft", "archived"]] = "draft"  # TODO: confirm enum
    tags: Optional[list[str]] = None
    variants: Optional[list[ProductVariant]] = None
    images: Optional[list[dict[str, Any]]] = None  # TODO: confirm image shape


class ProductUpdate(CartPandaModel):
    """Payload for PUT/PATCH /products/{id} — all fields optional."""

    title: Optional[str] = None
    description: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None
    variants: Optional[list[ProductVariant]] = None


class Product(CartPandaModel):
    """A CartPanda product as returned by GET /products/{id}."""

    id: int | str
    title: str
    description: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None
    variants: Optional[list[ProductVariant]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ──────────────────────────────────────────────────────────────────────
# Carts
# ──────────────────────────────────────────────────────────────────────
class CartLineItem(CartPandaModel):
    """A line item inside a cart."""

    variant_id: int | str
    quantity: int = Field(ge=1)
    price: Optional[Decimal] = None  # usually set server-side
    properties: Optional[dict[str, Any]] = None


class CartCreate(CartPandaModel):
    """Payload for POST /carts."""

    line_items: list[CartLineItem]
    customer_id: Optional[int | str] = None
    email: Optional[str] = None
    note: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None


class Cart(CartPandaModel):
    """A CartPanda cart."""

    id: int | str
    token: Optional[str] = None
    line_items: list[CartLineItem] = []
    subtotal: Optional[Decimal] = None
    total: Optional[Decimal] = None
    currency: Optional[str] = None
    customer_id: Optional[int | str] = None
    checkout_url: Optional[str] = None  # TODO: confirm field name
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ──────────────────────────────────────────────────────────────────────
# Orders
# ──────────────────────────────────────────────────────────────────────
class OrderLineItem(CartPandaModel):
    """A line item inside an order."""

    id: Optional[int | str] = None
    variant_id: Optional[int | str] = None
    product_id: Optional[int | str] = None
    title: Optional[str] = None
    sku: Optional[str] = None
    quantity: int
    price: Decimal
    total: Optional[Decimal] = None


class PaymentGateway(CartPandaModel):
    """Payment gateway info — usually nested on Order."""

    name: Optional[str] = None  # e.g. "stripe", "paypal", "credit_card"
    transaction_id: Optional[str] = None
    transaction_token: Optional[str] = None  # TODO: confirm — DR/upsell flows
    authorization_code: Optional[str] = None
    status: Optional[str] = None


class Order(CartPandaModel):
    """A CartPanda order."""

    id: int | str
    order_number: Optional[str] = None
    email: Optional[str] = None
    customer_id: Optional[int | str] = None
    line_items: list[OrderLineItem] = []
    subtotal: Optional[Decimal] = None
    total: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    shipping: Optional[Decimal] = None
    currency: Optional[str] = None
    financial_status: Optional[str] = None  # e.g. "paid", "pending", "refunded"
    fulfillment_status: Optional[str] = None  # e.g. "fulfilled", "partial", "unfulfilled"
    payment_gateway: Optional[PaymentGateway] = None
    shipping_address: Optional[dict[str, Any]] = None  # TODO: build typed Address model
    billing_address: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OrderListResponse(CartPandaModel):
    """Paginated order list response."""

    orders: list[Order] = []
    page: Optional[int] = None
    per_page: Optional[int] = None
    total: Optional[int] = None
    has_more: Optional[bool] = None  # TODO: confirm pagination shape


# ──────────────────────────────────────────────────────────────────────
# Customers
# ──────────────────────────────────────────────────────────────────────
class CustomerCreate(CartPandaModel):
    """Payload for POST /customers."""

    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    accepts_marketing: Optional[bool] = None
    addresses: Optional[list[dict[str, Any]]] = None
    tags: Optional[list[str]] = None


class Customer(CartPandaModel):
    """A CartPanda customer."""

    id: int | str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    accepts_marketing: Optional[bool] = None
    orders_count: Optional[int] = None
    total_spent: Optional[Decimal] = None
    tags: Optional[list[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ──────────────────────────────────────────────────────────────────────
# Fulfillment
# ──────────────────────────────────────────────────────────────────────
class FulfillmentCreate(CartPandaModel):
    """Payload for POST /orders/{id}/fulfillments."""

    tracking_number: str
    tracking_company: Optional[str] = None  # e.g. "USPS", "FedEx", "UPS"
    tracking_url: Optional[str] = None
    notify_customer: bool = True
    line_items: Optional[list[dict[str, Any]]] = None  # partial fulfillment
    # TODO: confirm field name(s) — some platforms use "items" instead


class Fulfillment(CartPandaModel):
    """A CartPanda fulfillment record."""

    id: int | str
    order_id: int | str
    status: Optional[str] = None  # e.g. "success", "pending", "cancelled"
    tracking_number: Optional[str] = None
    tracking_company: Optional[str] = None
    tracking_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ──────────────────────────────────────────────────────────────────────
# Webhooks
# ──────────────────────────────────────────────────────────────────────
WebhookEvent = Literal[
    "product.created",
    "product.updated",
    "product.deleted",
    "order.created",
    "order.paid",
    "order.updated",
    "order.refunded",
]


class WebhookCreate(CartPandaModel):
    """Payload for POST /webhooks (subscribe to events)."""

    topic: WebhookEvent
    address: str  # the URL CartPanda will POST to
    format: Literal["json"] = "json"


class WebhookSubscription(CartPandaModel):
    """A registered webhook subscription."""

    id: int | str
    topic: WebhookEvent
    address: str
    format: Optional[str] = "json"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WebhookEnvelope(CartPandaModel):
    """The outer shape of an incoming webhook POST body.

    TODO: confirm — CartPanda may send the resource object directly without an
    outer envelope. Adjust webhook_receiver.py routing if so.
    """

    topic: Optional[WebhookEvent] = None
    shop: Optional[str] = None
    created_at: Optional[datetime] = None
    data: Optional[dict[str, Any]] = None
