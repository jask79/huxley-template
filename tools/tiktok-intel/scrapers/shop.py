"""TikTok Shop product scraper -- SSR extraction + API interception fallback.

Primary strategy: extract product data from SSR __DEFAULT_SCOPE__ data
embedded in script tags.

Fallback strategy: intercept TikTok Shop API calls (may be blocked by
bot detection in headless mode).
"""

import logging
import time
from typing import Any, Dict, List
from urllib.parse import quote_plus

from ..config import SHOP_ALT_BASE, SHOP_API_PATTERNS, SHOP_BASE
from ..exceptions import AntiDetectionError
from ..models import ScrapeResult, ShopProduct
from .base import BaseScraper

logger = logging.getLogger(__name__)


class ShopScraper(BaseScraper):
    """Scrape TikTok Shop products via SSR extraction with API interception fallback."""

    name = "shop"

    # ------------------------------------------------------------------
    # SSR extraction JavaScript
    # ------------------------------------------------------------------

    _SSR_SHOP_JS = """() => {
        var scripts = document.querySelectorAll('script');
        for (var i = 0; i < scripts.length; i++) {
            try {
                var d = JSON.parse(scripts[i].textContent);
                if (d && d.__DEFAULT_SCOPE__) {
                    var scope = d.__DEFAULT_SCOPE__;
                    var keys = Object.keys(scope);
                    for (var j = 0; j < keys.length; j++) {
                        if (keys[j].indexOf('shop') !== -1 || keys[j].indexOf('Shop') !== -1
                            || keys[j].indexOf('product') !== -1 || keys[j].indexOf('Product') !== -1) {
                            return { key: keys[j], data: scope[keys[j]] };
                        }
                    }
                }
            } catch(e) {}
        }
        return null;
    }"""

    def scrape(self, filters: Dict[str, Any], limit: int = 20) -> ScrapeResult:
        """Scrape TikTok Shop products via SSR extraction with API fallback.

        Filters:
            query: str -- search term for products
            shop_id: str -- optional specific shop ID
        """
        query = (filters.get("query") or "").strip()
        shop_id = (filters.get("shop_id") or "").strip()

        if not query and not shop_id:
            return ScrapeResult(
                command="shop",
                success=False,
                error="No search query or shop_id specified",
                filters=filters,
            )

        # Build URL
        if query:
            page_url = f"{SHOP_BASE}/search?q={quote_plus(query)}"
        else:
            page_url = f"{SHOP_BASE}/{shop_id}"

        search_term = query or shop_id
        self._log("Searching TikTok Shop for '%s'", search_term)

        # Establish cookies / bot-detection tokens before the real request
        self._warmup_navigation()

        # ----- Strategy 1: SSR extraction (primary domain) -----
        ssr_result = self._try_ssr_extraction(page_url, search_term, limit, filters)
        if ssr_result is not None:
            return ssr_result

        # ----- Strategy 1b: SSR extraction (alternate shop domain) -----
        if query:
            alt_url = f"{SHOP_ALT_BASE}/search?q={quote_plus(query)}"
        else:
            alt_url = f"{SHOP_ALT_BASE}/{shop_id}"
        self._log("Primary shop SSR empty, trying alternate domain: %s", alt_url)
        alt_ssr_result = self._try_ssr_extraction(alt_url, search_term, limit, filters)
        if alt_ssr_result is not None:
            return alt_ssr_result

        # ----- Strategy 2: API interception fallback -----
        self._log("SSR extraction found no shop data, falling back to API interception")
        api_result = self._try_api_interception(page_url, search_term, limit, filters)
        if api_result is not None:
            return api_result

        # ----- Both strategies failed -----
        return ScrapeResult(
            command="shop",
            success=False,
            error=(
                f"No shop results found for '{search_term}'. "
                "TikTok may be blocking headless browsers from shop data. "
                "Try --no-headless for a visible browser, or use the 'trends' command "
                "for Creative Center data which works in headless mode."
            ),
            filters=filters,
        )

    # ------------------------------------------------------------------
    # Strategy 1: SSR extraction
    # ------------------------------------------------------------------

    def _try_ssr_extraction(
        self,
        page_url: str,
        search_term: str,
        limit: int,
        filters: Dict[str, Any],
    ) -> ScrapeResult | None:
        """Try to extract shop data from SSR __DEFAULT_SCOPE__ data.

        Returns a ScrapeResult on success, or None if no SSR data was found.
        """
        page = self.bm.new_page()
        try:
            self._tiktok_rate_limit_delay()

            page.goto(page_url, wait_until="networkidle", timeout=30000)
            self._check_anti_detection(page)
            self._dismiss_overlays(page)
            time.sleep(2)

            ssr_data = page.evaluate(self._SSR_SHOP_JS)

            if not ssr_data or not ssr_data.get("data"):
                self._log("No SSR shop data found in __DEFAULT_SCOPE__")
                return None

            scope_key = ssr_data.get("key", "")
            raw_data = ssr_data.get("data", {}) or {}

            self._log("Found SSR shop data under key: %s", scope_key)

            # Extract product items from SSR data
            all_items = self._extract_ssr_shop_items(raw_data)

            if not all_items:
                self._log("SSR data found but contained no product items")
                return None

            # Map to model dataclasses
            items = self._map_products(all_items, limit)

            if not items:
                return None

            return ScrapeResult(
                command="shop",
                success=True,
                data=items,
                count=len(items),
                filters=filters,
            )

        except AntiDetectionError:
            raise  # surface bot detection to caller
        except Exception as e:
            self._log("SSR extraction error: %s", e)
            return None
        finally:
            page.close()

    def _extract_ssr_shop_items(
        self, raw_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract product items from SSR scope data.

        The SSR data structure may vary; try several known key paths.
        """
        items: List[Dict[str, Any]] = []

        # Common key paths for shop/product results
        product_keys = [
            "products", "product_list", "items", "list",
            "productList", "itemList", "data",
        ]

        # Try to find items directly in the raw data
        for key in product_keys:
            found = raw_data.get(key, [])
            if isinstance(found, list) and found:
                items.extend(found)
                return items

        # Try nested under a 'data' key
        nested_data = raw_data.get("data", {})
        if isinstance(nested_data, dict):
            for key in product_keys:
                found = nested_data.get(key, [])
                if isinstance(found, list) and found:
                    items.extend(found)
                    return items

        # Try nested under 'searchResult'
        search_result = raw_data.get("searchResult", {})
        if isinstance(search_result, dict):
            for key in product_keys:
                found = search_result.get(key, [])
                if isinstance(found, list) and found:
                    items.extend(found)
                    return items

        return items

    # ------------------------------------------------------------------
    # Strategy 2: API interception fallback
    # ------------------------------------------------------------------

    def _try_api_interception(
        self,
        page_url: str,
        search_term: str,
        limit: int,
        filters: Dict[str, Any],
    ) -> ScrapeResult | None:
        """Fall back to API interception for shop data.

        Returns a ScrapeResult on success, or None if no API data was captured.
        """
        api_pattern = SHOP_API_PATTERNS["search"]

        self._log("Attempting API interception for shop '%s'", search_term)

        responses = self._intercept_api_paginated(
            page_url, api_pattern, max_pages=3,
        )

        if not responses:
            self._log("No API responses intercepted for shop search '%s'", search_term)
            return None

        # Extract product items from responses
        all_items: List[Dict[str, Any]] = []

        for resp in responses:
            found_in_resp = False

            # Try standard API envelope extraction with common keys
            for data_key in ("data", "products", "product_list", "items"):
                ok, raw_items, _ = self._extract_api_data(resp, data_key)
                if ok and raw_items and isinstance(raw_items, list):
                    all_items.extend(raw_items)
                    found_in_resp = True
                    break

            if found_in_resp:
                continue

            # Fallback: direct key access for non-standard envelope
            for key in ("data", "products", "product_list", "items"):
                direct_items = resp.get(key, [])
                if isinstance(direct_items, list) and direct_items:
                    all_items.extend(direct_items)
                    found_in_resp = True
                    break

            if found_in_resp:
                continue

            # Nested data fallback
            data = resp.get("data", {})
            if isinstance(data, dict):
                for key in ("products", "product_list", "items", "list"):
                    nested_items = data.get(key, [])
                    if isinstance(nested_items, list) and nested_items:
                        all_items.extend(nested_items)
                        break

        if not all_items:
            self._log("No product items found in API responses")
            return None

        # Map to model dataclasses
        items = self._map_products(all_items, limit)

        return ScrapeResult(
            command="shop",
            success=True,
            data=items,
            count=len(items),
            filters=filters,
        )

    # ------------------------------------------------------------------
    # API -> Model mapper
    # ------------------------------------------------------------------

    def _map_products(
        self, raw_items: List[Dict], limit: int
    ) -> List[ShopProduct]:
        """Map API product items to ShopProduct models."""
        items: List[ShopProduct] = []
        seen_ids: set = set()

        for entry in raw_items:
            if len(items) >= limit:
                break

            # Title
            title = entry.get("title", "") or entry.get("name", "")
            if not title:
                continue

            # Product ID
            product_id = str(
                entry.get("product_id", "")
                or entry.get("id", "")
                or ""
            )

            # Deduplicate by product ID
            if product_id and product_id in seen_ids:
                continue
            if product_id:
                seen_ids.add(product_id)

            # Price -- various shapes in the API
            price_data = entry.get("price", {})
            if isinstance(price_data, dict):
                price_str = price_data.get("original_price", "") or price_data.get("price", "")
                try:
                    price_raw = float(
                        str(price_data.get("original_price", 0) or price_data.get("price", 0))
                        .replace("$", "")
                        .replace(",", "")
                        .strip()
                        or "0"
                    )
                except (ValueError, TypeError):
                    price_raw = 0.0
            elif isinstance(price_data, (int, float)):
                price_str = str(price_data)
                price_raw = float(price_data)
            elif isinstance(price_data, str):
                price_str = price_data
                try:
                    price_raw = float(price_data.replace("$", "").replace(",", "").strip() or "0")
                except (ValueError, TypeError):
                    price_raw = 0.0
            else:
                price_str = ""
                price_raw = 0.0

            # Format price with $ if it's a bare number
            if price_str and not price_str.startswith("$"):
                try:
                    float(price_str.replace(",", ""))
                    price_str = f"${price_str}"
                except ValueError:
                    pass

            # Rating
            rating_val = entry.get("star", "") or entry.get("rating", "")
            rating = str(rating_val) if rating_val else ""

            # Reviews
            reviews_val = entry.get("review_count", 0) or entry.get("reviews", 0)
            reviews = self._format_count(reviews_val) if reviews_val else ""

            # Sold count
            sold_val = entry.get("sold_count", 0) or entry.get("sold", 0)
            sold = self._format_count(sold_val) if sold_val else ""

            # Seller
            seller = (
                entry.get("seller_name", "")
                or entry.get("shop_name", "")
                or entry.get("seller", "")
                or ""
            )

            # URL
            url = entry.get("url", "") or entry.get("product_url", "")
            if not url and product_id:
                url = f"https://www.tiktok.com/shop/product/{product_id}"

            # Thumbnail
            thumbnail = entry.get("cover", "") or ""
            if not thumbnail:
                images = entry.get("images", [])
                if isinstance(images, list) and images:
                    first_img = images[0]
                    if isinstance(first_img, str):
                        thumbnail = first_img
                    elif isinstance(first_img, dict):
                        thumbnail = first_img.get("url", "") or first_img.get("thumb_url", "") or ""

            # Category
            category = entry.get("category", "") or entry.get("category_name", "") or ""

            items.append(
                ShopProduct(
                    title=title,
                    price=price_str,
                    price_raw=price_raw,
                    rating=rating,
                    reviews=reviews,
                    sold=sold,
                    seller=seller,
                    url=url,
                    thumbnail=thumbnail,
                    product_id=product_id,
                    category=category,
                )
            )

        return items
