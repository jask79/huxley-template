"""mitmproxy addon: capture TikTok API responses for endpoint discovery."""

import json
import pathlib
import time

from mitmproxy import http

OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "data" / "shop_captures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SHOP_PATHS = [
    "/api/shop/product",
    "/api/v1/item",
    "/aweme/v1/item",
    "/api/shop/product_detail",
    "/ec/api/v1/item",
    "/api/v1/search",
    "/aweme/v1/search",
    "/api/v2/search",
    "/oec/api/",
]

captured_count = 0


def response(flow: http.HTTPFlow) -> None:
    global captured_count
    url = flow.request.url

    if not any(
        d in url
        for d in ["tiktok", "musical", "byteoversea", "byteimg", "tiktokv", "bytedance", "ttlive"]
    ):
        return

    content_type = flow.response.headers.get("content-type", "")
    if "json" not in content_type and "protobuf" not in content_type:
        return

    is_shop = any(p in url for p in SHOP_PATHS)

    try:
        data = flow.response.json()
    except Exception:
        data = {"_raw": "non-json", "_url": url}

    prefix = "shop" if is_shop else "api"
    fname = OUTPUT_DIR / f"{prefix}_{int(time.time() * 1000)}_{captured_count}.json"

    output = {
        "_meta": {
            "url": url,
            "method": flow.request.method,
            "status_code": flow.response.status_code,
            "timestamp": time.time(),
            "is_shop_endpoint": is_shop,
        },
        "data": data,
    }
    fname.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    captured_count += 1

    tag = "[SHOP]" if is_shop else "[API] "
    print(f"{tag} {flow.request.method} {url[:120]} -> {fname.name}")
