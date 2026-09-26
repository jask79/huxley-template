"""TikTok competitor profile scraper via SSR data extraction.

Navigates to tiktok.com/@username and extracts profile data from the
server-side rendered __DEFAULT_SCOPE__['webapp.user-detail'] JSON embedded
in script tags. This is more reliable than API interception in headless mode.
"""

import logging
import sys
import time
from typing import Any, Dict, List

from ..config import TIKTOK_URLS
from ..models import CompetitorProfile, ScrapeResult
from .base import BaseScraper

logger = logging.getLogger(__name__)


class CompetitorScraper(BaseScraper):
    """Scrape competitor profile analytics from TikTok via SSR data extraction."""

    name = "competitor"

    # ------------------------------------------------------------------
    # SSR extraction JavaScript
    # ------------------------------------------------------------------

    _SSR_EXTRACT_JS = """() => {
        var scripts = document.querySelectorAll('script');
        for (var i = 0; i < scripts.length; i++) {
            try {
                var d = JSON.parse(scripts[i].textContent);
                if (d && d.__DEFAULT_SCOPE__ && d.__DEFAULT_SCOPE__['webapp.user-detail']) {
                    return d.__DEFAULT_SCOPE__['webapp.user-detail'];
                }
            } catch(e) {}
        }
        return null;
    }"""

    def scrape(self, filters: Dict[str, Any], limit: int = 20) -> ScrapeResult:
        """Scrape a competitor's TikTok profile via SSR data extraction.

        Filters:
            username: str -- target TikTok username (without @)
            include_videos: bool -- noted but not yet supported via SSR
        """
        username = (filters.get("username") or "").strip().lstrip("@")
        if not username:
            return ScrapeResult(
                command="competitor",
                success=False,
                error="No username specified",
                filters=filters,
            )

        if filters.get("include_videos") and self.bm.headless:
            print(
                "Warning: --videos flag has limited data in headless mode. "
                "Recent video details require --no-headless for full results.",
                file=sys.stderr,
            )

        url = TIKTOK_URLS["user_profile"].format(username=username)
        self._log("Fetching competitor profile via SSR: @%s", username)

        page = self.bm.new_page()
        try:
            self._tiktok_rate_limit_delay()

            page.goto(url, wait_until="networkidle", timeout=30000)
            self._check_anti_detection(page)
            self._dismiss_overlays(page)

            # Give SSR data a moment to settle in the DOM
            time.sleep(2)

            # Extract profile from SSR __DEFAULT_SCOPE__ data
            user_data = page.evaluate(self._SSR_EXTRACT_JS)

            if not user_data or user_data.get("statusCode") != 0:
                status = user_data.get("statusCode", "unknown") if user_data else "no data"
                status_msg = user_data.get("statusMsg", "") if user_data else ""
                return ScrapeResult(
                    command="competitor",
                    success=False,
                    error=(
                        f"Could not load profile for @{username}. "
                        f"Status: {status}"
                        + (f" ({status_msg})" if status_msg else "")
                        + ". The profile may be private or does not exist."
                    ),
                    filters=filters,
                )

            # Build profile from SSR data
            profile = self._build_profile_from_ssr(username, user_data)

            return ScrapeResult(
                command="competitor",
                success=True,
                data=[profile],
                count=1,
                filters=filters,
            )

        except Exception as e:
            self._log("Competitor scrape error: %s", e)
            return ScrapeResult(
                command="competitor",
                success=False,
                error=str(e),
                filters=filters,
            )
        finally:
            page.close()

    # ------------------------------------------------------------------
    # Profile building from SSR data
    # ------------------------------------------------------------------

    def _build_profile_from_ssr(
        self,
        username: str,
        user_data: Dict[str, Any],
    ) -> CompetitorProfile:
        """Build a CompetitorProfile from SSR __DEFAULT_SCOPE__ data."""
        user_info = user_data.get("userInfo", {}) or {}
        user = user_info.get("user", {}) or {}
        stats = user_info.get("stats", {}) or {}

        # Core profile fields
        nickname = user.get("nickname", "") or ""
        bio = user.get("signature", "") or ""
        avatar = user.get("avatarLarger", "") or user.get("avatarMedium", "") or ""
        verified = bool(user.get("verified", False))

        # Stats — use 'heart' not 'heartCount' (heartCount has int overflow
        # for large accounts)
        follower_cnt = stats.get("followerCount", 0) or 0
        following_cnt = stats.get("followingCount", 0) or 0
        like_cnt = stats.get("heart", 0) or stats.get("heartCount", 0) or 0
        videos_count = stats.get("videoCount", 0) or 0

        # Video engagement metrics are not available in SSR data.
        # The video list API (/api/post/item_list/) does not fire reliably
        # in headless mode, so we leave these as empty defaults for now.
        return CompetitorProfile(
            username=user.get("uniqueId", username),
            nickname=nickname,
            bio=bio,
            followers=self._format_count(follower_cnt),
            following=self._format_count(following_cnt),
            likes=self._format_count(like_cnt),
            videos_count=videos_count,
            avatar=avatar,
            verified=verified,
            avg_views="",
            avg_likes="",
            avg_comments="",
            engagement_rate="",
            follower_cnt=follower_cnt,
            following_cnt=following_cnt,
            like_cnt=like_cnt,
            recent_videos=[],
        )
