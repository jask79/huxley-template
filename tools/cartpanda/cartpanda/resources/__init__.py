"""CartPanda resource managers.

Each module exposes a thin wrapper around a CartPanda REST resource.
All resource classes accept a CartPandaClient on construction and use it
for HTTP I/O — they own no state of their own.
"""
from cartpanda.resources.carts import CartsResource
from cartpanda.resources.customers import CustomersResource
from cartpanda.resources.fulfillment import FulfillmentResource
from cartpanda.resources.orders import OrdersResource
from cartpanda.resources.products import ProductsResource
from cartpanda.resources.webhooks import WebhooksResource

__all__ = [
    "CartsResource",
    "CustomersResource",
    "FulfillmentResource",
    "OrdersResource",
    "ProductsResource",
    "WebhooksResource",
]
