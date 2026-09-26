"""Hashtag analytics scraper — detailed data for a specific hashtag.

Navigates to the Creative Center hashtag detail page and extracts
total views, total posts, trend data, related hashtags, and top videos.
"""

import logging
from typing import Any, Dict, List

from ..config import CC_BASE
from ..models import HashtagAnalytics, ScrapeResult
from .base import BaseScraper

logger = logging.getLogger(__name__)


class HashtagScraper(BaseScraper):
    """Scrape detailed analytics for a specific TikTok hashtag."""

    name = "hashtags"

    def scrape(self, filters: Dict[str, Any], limit: int = 20) -> ScrapeResult:
        """Scrape detailed analytics for a hashtag.

        Filters:
            hashtag: str — the hashtag name (without #)
            country: str — optional country code
        """
        hashtag = filters.get("hashtag", "").strip().lstrip("#")
        if not hashtag:
            return ScrapeResult(
                command="hashtags",
                success=False,
                error="No hashtag specified",
                filters=filters,
            )

        url = self._build_url(hashtag, filters)

        page = self.bm.new_page()
        try:
            self._navigate(page, url)

            # Wait for hashtag data to render
            self._random_delay(2.0, 3.5)
            self._gentle_scroll(page, scrolls=3)
            self._random_delay(1.0, 2.0)

            analytics = self._extract_analytics(page, hashtag, filters)

            return ScrapeResult(
                command="hashtags",
                success=True,
                data=[analytics],
                count=1,
                filters=filters,
            )
        finally:
            page.close()

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------

    def _build_url(self, hashtag: str, filters: Dict[str, Any]) -> str:
        """Build the hashtag analytics URL."""
        # Creative Center hashtag detail URL pattern
        base = f"{CC_BASE}/hashtag/{hashtag}/pc/en"
        params = []

        country = filters.get("country", "")
        if country:
            params.append(f"country_code={country}")

        if params:
            return f"{base}?{'&'.join(params)}"
        return base

    # ------------------------------------------------------------------
    # Analytics extraction
    # ------------------------------------------------------------------

    def _extract_analytics(
        self, page, hashtag: str, filters: Dict[str, Any]
    ) -> HashtagAnalytics:
        """Extract detailed hashtag analytics from the page."""
        raw = page.evaluate(
            """
            () => {
                const result = {
                    total_views: '',
                    total_posts: '',
                    trend_data: [],
                    related_hashtags: [],
                    top_videos: [],
                };

                // --- Total views/posts ---
                // Look for large stat numbers near the top of the page
                const statSelectors = [
                    '[class*="stat"], [class*="Stat"]',
                    '[class*="overview"], [class*="Overview"]',
                    '[class*="summary"], [class*="Summary"]',
                    '[class*="total"], [class*="Total"]',
                    '[class*="count"], [class*="Count"]',
                    '[class*="number"], [class*="Number"]',
                ];

                for (const sel of statSelectors) {
                    const els = document.querySelectorAll(sel);
                    for (const el of els) {
                        const text = el.textContent.trim();
                        const parent = el.closest('[class*="item"], [class*="card"], [class*="block"]');
                        const parentText = parent ? parent.textContent.toLowerCase() : '';

                        if ((parentText.includes('view') || parentText.includes('play'))
                            && !result.total_views) {
                            // Extract the number part
                            const match = text.match(/[\\d,.]+[KMBkmb]?/);
                            if (match) result.total_views = match[0];
                        }
                        if ((parentText.includes('post') || parentText.includes('video'))
                            && !result.total_posts) {
                            const match = text.match(/[\\d,.]+[KMBkmb]?/);
                            if (match) result.total_posts = match[0];
                        }
                    }
                }

                // --- Related hashtags ---
                const relatedSelectors = [
                    '[class*="related"] a',
                    '[class*="Related"] a',
                    '[class*="suggest"] a',
                    '[class*="recommend"] a',
                    '[class*="tag-item"] a',
                ];
                for (const sel of relatedSelectors) {
                    const els = document.querySelectorAll(sel);
                    if (els.length > 0) {
                        for (const el of els) {
                            const tag = el.textContent.trim();
                            if (tag && tag.length < 100) {
                                result.related_hashtags.push(tag);
                            }
                        }
                        break;
                    }
                }

                // --- Top videos ---
                const videoCards = document.querySelectorAll(
                    '[class*="VideoCard"], [class*="video-card"], [class*="video-item"]'
                );
                for (let i = 0; i < Math.min(videoCards.length, 10); i++) {
                    const card = videoCards[i];
                    const descEl = card.querySelector('[class*="desc"], [class*="title"], [class*="caption"]');
                    const viewsEl = card.querySelector('[class*="view"], [class*="play"]');
                    const linkEl = card.querySelector('a[href]');
                    result.top_videos.push({
                        description: descEl ? descEl.textContent.trim() : '',
                        views: viewsEl ? viewsEl.textContent.trim() : '',
                        url: linkEl ? linkEl.href : '',
                    });
                }

                // --- Trend data (chart data points if available) ---
                // Try to read from any visible chart/graph data
                const chartPoints = document.querySelectorAll(
                    '[class*="chart"] [class*="point"], [class*="graph"] [class*="dot"], ' +
                    'svg circle, [class*="trend-item"]'
                );
                // Chart data extraction is unreliable via DOM — skip gracefully

                return result;
            }
            """
        )

        self._log("Extracted hashtag analytics for #%s", hashtag)

        return HashtagAnalytics(
            name=hashtag,
            total_views=raw.get("total_views", ""),
            total_posts=raw.get("total_posts", ""),
            trend_data=raw.get("trend_data", []),
            related_hashtags=raw.get("related_hashtags", []),
            top_videos=raw.get("top_videos", []),
            country=filters.get("country", ""),
        )
