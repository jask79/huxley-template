"""Top Ads scraper — scrapes top performing ads from Creative Center.

Uses API response interception instead of DOM parsing. Navigates to the
Top Ads page and intercepts the `top_ads/v2/list` API response which
returns `data.materials[]` with structured ad data.

Supports filtering by sort order, region, objective, and industry.
"""

import logging
from typing import Any, Dict, List

from ..config import API_PATTERNS, URLS
from ..models import ScrapeResult, TopAd
from .base import BaseScraper

logger = logging.getLogger(__name__)


class TopAdsScraper(BaseScraper):
    """Scrape top-performing ads from TikTok Creative Center via API interception."""

    name = "top_ads"

    def scrape(self, filters: Dict[str, Any], limit: int = 20) -> ScrapeResult:
        """Scrape top ads via API interception.

        Filters:
            sort: str — for_you, reach, ctr, like, comment, share
            region: str — country code (e.g., "US")
            objective: str — ad objective key (e.g., "campaign_objective_video_view")
            industry: str — optional industry filter
            period: str — time period (7, 30, 180)
        """
        page_url = self._build_url(filters)
        api_pattern = API_PATTERNS["top_ads"]

        # Intercept API responses
        responses = self._intercept_api(page_url, api_pattern)

        if not responses:
            self._log("No API responses intercepted for top_ads")
            return ScrapeResult(
                command="top-ads",
                success=False,
                error="No API data intercepted for top ads. "
                      "The page may not have triggered the expected API call.",
                filters=filters,
            )

        # Extract data from the first successful response
        for resp in responses:
            ok, raw_items, err_msg = self._extract_api_data(resp, "materials")

            if not ok:
                self._log("API response error for top_ads: %s", err_msg)
                continue

            if not raw_items:
                self._log("API response had empty materials list")
                continue

            items = self._map_ads(raw_items, filters, limit)

            return ScrapeResult(
                command="top-ads",
                success=True,
                data=items,
                count=len(items),
                filters=filters,
            )

        # All responses failed
        return ScrapeResult(
            command="top-ads",
            success=False,
            error=f"All {len(responses)} API responses failed for top_ads",
            filters=filters,
        )

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------

    def _build_url(self, filters: Dict[str, Any]) -> str:
        """Build Top Ads page URL with query parameters.

        The frontend reads URL params and passes them to its API call.
        """
        base = URLS["top_ads"]
        params = []

        sort = filters.get("sort", "")
        if sort:
            params.append(f"sort_by={sort}")

        region = filters.get("region", "")
        if region:
            params.append(f"country_code={region}")

        industry = filters.get("industry", "")
        if industry:
            params.append(f"industry={industry}")

        objective = filters.get("objective", "")
        if objective:
            params.append(f"objective={objective}")

        period = filters.get("period", "30")
        params.append(f"period={period}")

        if params:
            separator = "&" if "?" in base else "?"
            return f"{base}{separator}{'&'.join(params)}"
        return base

    # ------------------------------------------------------------------
    # API → Model mapper
    # ------------------------------------------------------------------

    def _map_ads(
        self, raw_items: List[Dict], filters: Dict[str, Any], limit: int
    ) -> List[TopAd]:
        """Map API material items to TopAd models."""
        items = []
        region = filters.get("region", "")
        industry_filter = filters.get("industry", "")
        objective_filter = filters.get("objective", "")

        for i, entry in enumerate(raw_items[:limit]):
            ad_title = entry.get("ad_title", "")
            brand = entry.get("brand_name", "")
            ad_id = str(entry.get("id", ""))

            # Extract video info
            video_info = entry.get("video_info", {}) or {}
            video_id = video_info.get("vid", "")

            # CTR comes as a float (e.g., 0.89 meaning 0.89%)
            ctr_raw = entry.get("ctr", 0.0)
            ctr_display = f"{ctr_raw:.2f}%" if isinstance(ctr_raw, (int, float)) and ctr_raw > 0 else ""

            like_cnt = entry.get("like", 0)
            cost = entry.get("cost", 0)
            industry_key = entry.get("industry_key", "")
            objective_key = entry.get("objective_key", "")

            items.append(
                TopAd(
                    rank=i + 1,
                    brand=brand,
                    description=ad_title,
                    likes=self._format_count(like_cnt),
                    comments="",           # Not in this API response
                    shares="",             # Not in this API response
                    ctr=ctr_display,
                    reach="",              # Not directly available
                    objective=objective_filter or objective_key,
                    region=region,
                    industry=industry_filter or industry_key,
                    url="",                # No direct ad URL in API
                    ad_id=ad_id,
                    ad_title=ad_title,
                    like_cnt=like_cnt,
                    ctr_raw=ctr_raw if isinstance(ctr_raw, (int, float)) else 0.0,
                    cost=cost,
                    video_id=video_id,
                    industry_key=industry_key,
                    objective_key=objective_key,
                    is_search=bool(entry.get("is_search", False)),
                    tag=entry.get("tag", 0),
                )
            )
        return items
