# CartPanda Integration Tool

Reusable Python client + FastAPI webhook receiver for the [CartPanda](https://cartpanda.com/) checkout/upsell API. Lives at Huxley root (`tools/cartpanda/`) — **not** inside a capsule — because it's shared across any DR / dropship capsule that uses CartPanda as the Merchant of Record (e.g. `capsules/acme-store/`).

> **Status:** Scaffold. No live API key yet — your CartPanda account isn't activated. Endpoint paths, header names, and the webhook signing mechanism are best-guesses based on the public docs landing at <https://dev.cartpanda.com/>. Files marked with `# TODO: confirm` need a quick pass once the account is live.

---

## Layout

```
tools/cartpanda/
├── README.md                          ← you are here
├── requirements.txt
├── .env.example                       ← copy to .env, fill in real values
├── .gitignore
├── cartpanda/
│   ├── __init__.py                    ← public exports
│   ├── client.py                      ← httpx client + settings + retry/auth
│   ├── types.py                       ← Pydantic v2 models (mark TBD where inferred)
│   ├── exceptions.py                  ← typed error hierarchy
│   ├── webhook_receiver.py            ← FastAPI app, signature verification, event dispatch
│   └── resources/
│       ├── products.py
│       ├── carts.py
│       ├── orders.py
│       ├── customers.py
│       ├── fulfillment.py
│       └── webhooks.py
├── scripts/
│   ├── test_connection.py             ← `python tools/cartpanda/scripts/test_connection.py`
│   └── list_orders.py                 ← `python tools/cartpanda/scripts/list_orders.py`
└── tests/
    ├── test_client.py                 ← respx-mocked HTTP tests
    └── test_webhook_receiver.py       ← FastAPI TestClient
```

---

## Install

Uses the existing Huxley root virtualenv (`.venv/`). From Huxley root:

```bash
.venv/bin/pip install -r tools/cartpanda/requirements.txt
```

Copy the env template and fill in real values once you have account access:

```bash
cp tools/cartpanda/.env.example tools/cartpanda/.env
$EDITOR tools/cartpanda/.env
```

Required vars:

| Var | What | Where to get it |
|---|---|---|
| `CARTPANDA_API_KEY` | API token | Dashboard → Settings → API once account is live |
| `CARTPANDA_BASE_URL` | API base URL | Default points at V3 best-guess; confirm in dashboard |
| `CARTPANDA_SHOP_SLUG` | Store slug | Visible in dashboard URL |
| `CARTPANDA_WEBHOOK_SECRET` | HMAC secret for webhooks | Webhook settings at <https://accounts.cartpanda.com/settings/webhooks> |
| `CARTPANDA_WEBHOOK_PORT` | Local port for receiver | Defaults to `3201` (see port registry) |

---

## Verify the connection

```bash
.venv/bin/python tools/cartpanda/scripts/test_connection.py
```

The script probes a couple of read endpoints and reports whether the API key + base URL combo is healthy. Exit code is non-zero on failure so it's CI-friendly.

---

## List recent orders

```bash
.venv/bin/python tools/cartpanda/scripts/list_orders.py
.venv/bin/python tools/cartpanda/scripts/list_orders.py --per-page 10 --status paid
```

---

## Webhook receiver

A FastAPI app at `cartpanda/webhook_receiver.py` routes inbound webhooks to per-event handlers. It handles the seven topics in scope:

```
product.created   product.updated   product.deleted
order.created     order.paid        order.updated     order.refunded
```

### Run locally

```bash
.venv/bin/uvicorn cartpanda.webhook_receiver:app \
    --app-dir tools/cartpanda \
    --host 127.0.0.1 --port 3201 --reload
```

Port `3201` is reserved in `global/config/port-registry.yaml` under `apis.cartpanda-webhook`.

### Expose publicly (for dev)

Pick one:

```bash
# ngrok
ngrok http 3201

# cloudflared (if you have a tunnel)
cloudflared tunnel --url http://127.0.0.1:3201
```

Copy the public HTTPS URL.

### Subscribe to webhooks

```python
from cartpanda import CartPandaClient
from cartpanda.types import WebhookCreate

with CartPandaClient() as c:
    for topic in [
        "product.created", "product.updated", "product.deleted",
        "order.created", "order.paid", "order.updated", "order.refunded",
    ]:
        c.webhooks.create(WebhookCreate(
            topic=topic,
            address="https://your-ngrok.example/webhooks/cartpanda",
        ))
```

Or use the dashboard at <https://accounts.cartpanda.com/settings/webhooks>.

### Register your own handler

Drop this in a capsule module that gets imported before uvicorn starts the app:

```python
from cartpanda.webhook_receiver import on_event

@on_event("order.paid")
async def handle_order_paid(payload: dict) -> None:
    order_id = payload["id"]
    # Persist to Supabase, trigger fulfillment, ping Slack, etc.
```

Multiple registrations for the same topic overwrite — last one wins.

### Signature verification (TODO)

The receiver verifies `X-CartPanda-Signature` as HMAC-SHA256(secret, raw_body), hex-encoded. **CartPanda's exact mechanism isn't publicly documented** at scaffold time — see the long `TODO` block in `cartpanda/webhook_receiver.py::verify_signature`. Confirm against the dashboard once the account is live (header name, algorithm, encoding, signed-payload format) and swap the implementation. The default is the Shopify pattern, which CartPanda mirrors.

If `CARTPANDA_WEBHOOK_SECRET` is empty, verification is **skipped** with a warning — dev convenience only, never run that way in production.

---

## Wire into a capsule (e.g. `acme-store`)

Two patterns work — pick based on whether the capsule is Python (uses the receiver directly) or TS/Next.js (calls the client via a small Python script or shells out).

### Pattern A: Python capsule / Python automation

```python
# capsules/acme-store/scripts/sync_products.py
import sys
from pathlib import Path

# Add the tool to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "cartpanda"))

from cartpanda import CartPandaClient
from cartpanda.types import ProductCreate

with CartPandaClient() as c:
    c.products.create(ProductCreate(
        title="Example Co — Liver Support",
        vendor="Example Co LLC",
        product_type="supplement",
        status="active",
    ))
```

### Pattern B: Next.js capsule receives webhooks via this tool

Run the receiver as a sidecar process (uvicorn). The handler persists events into the capsule's Supabase, and the Next.js app reads from Supabase normally. This keeps webhook plumbing language-agnostic.

Deployment story (Cloudflare Workers vs always-on FastAPI on a home server) is **out of scope** for this scaffold — deferred until you wire this into a specific capsule.

---

## Tests

```bash
.venv/bin/pytest tools/cartpanda/tests/ -v
```

Mocks all HTTP via `respx` and `fastapi.testclient` — never hits the real API.

---

## What's intentionally NOT here

- **No live API calls** (no account yet).
- **No real webhook signature verification** — the mechanism isn't publicly documented. The skeleton is in place; finish it once you have dashboard access.
- **No database persistence** — webhooks log + dispatch but don't write anywhere. Hook into Supabase per capsule.
- **No deployment config** — local FastAPI only for now. Cloudflare Workers / Vercel / Railway decision is deferred.

---

## When you activate your CartPanda account

1. Fill in `tools/cartpanda/.env`.
2. Run `tools/cartpanda/scripts/test_connection.py` — fix the base URL or auth header if it fails.
3. Open `cartpanda/client.py::_default_headers` — confirm `Authorization: Bearer` vs `X-API-Key`.
4. Open `cartpanda/webhook_receiver.py::verify_signature` — confirm header name + HMAC encoding against CartPanda's actual webhook docs.
5. Audit `cartpanda/types.py` against real API responses — fix any `# TODO: confirm` fields.
6. Audit each `cartpanda/resources/*.py` — confirm endpoint paths (V3 vs `/shop/{slug}/...`).

The whole pass should take an hour once the account is live.
