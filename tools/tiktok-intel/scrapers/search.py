"""TikTok search scraper -- videos and users via SSR + API interception.

Primary strategy: extract search results from SSR __DEFAULT_SCOPE__ data
embedded in script tags (works when TikTok serves full SSR content).

Fallback strategy: intercept /api/search/* API calls (may work for some
queries/regions but is blocked by bot detection in headless mode).
"""

import logging
import time
from typing import Any, Dict, List
from urllib.parse import quote_plus

from ..config import TIKTOK_API_PATTERNS, TIKTOK_URLS
from ..exceptions import AntiDetectionError
from ..models import ScrapeResult, SearchUserResult, SearchVideoResult
from .base import BaseScraper

logger = logging.getLogger(__name__)


class SearchScraper(BaseScraper):
    """Scrape TikTok search results via SSR extraction with API interception fallback."""

    name = "search"

    # ------------------------------------------------------------------
    # SSR extraction JavaScript
    # ------------------------------------------------------------------

    _SSR_SEARCH_JS = """() => {
        var scripts = document.querySelectorAll('script');
        for (var i = 0; i < scripts.length; i++) {
            try {
                var d = JSON.parse(scripts[i].textContent);
                if (d && d.__DEFAULT_SCOPE__) {
                    var scope = d.__DEFAULT_SCOPE__;
                    // Try explicit known scope keys first
                    var explicitKeys = [
                        'webapp.searchResult',
                        'webapp.search-detail',
                        'webapp.search-video-detail'
                    ];
                    for (var k = 0; k < explicitKeys.length; k++) {
                        if (scope[explicitKeys[k]]) {
                            return { key: explicitKeys[k], data: scope[explicitKeys[k]] };
                        }
                    }
                    // Fall back to generic search key matching
                    var keys = Object.keys(scope);
                    for (var j = 0; j < keys.length; j++) {
                        if (keys[j].indexOf('search') !== -1 || keys[j].indexOf('Search') !== -1) {
                            return { key: keys[j], data: scope[keys[j]] };
                        }
                    }
                }
            } catch(e) {}
        }
        return null;
    }"""

    def scrape(self, filters: Dict[str, Any], limit: int = 20) -> ScrapeResult:
        """Scrape TikTok search results via SSR extraction with API fallback.

        Filters:
            query: str -- the search term
            search_type: str -- "video" or "user" (default: "video")
        """
        query = (filters.get("query") or "").strip()
        if not query:
            return ScrapeResult(
                command="search",
                success=False,
                error="No search query specified",
                filters=filters,
            )

        search_type = filters.get("search_type", "video")

        # Build the search URL
        # t=0 for video search, t=1 for user search
        type_param = "1" if search_type == "user" else "0"
        page_url = f"{TIKTOK_URLS['search']}?q={quote_plus(query)}&t={type_param}"

        self._log("Searching TikTok for '%s' (type=%s)", query, search_type)

        # Establish cookies / bot-detection tokens before the real request
        self._warmup_navigation()

        # ----- Strategy 1: SSR extraction -----
        ssr_result = self._try_ssr_extraction(page_url, query, search_type, limit, filters)
        if ssr_result is not None:
            return ssr_result

        # ----- Strategy 2: API interception fallback -----
        self._log("SSR extraction found no search data, falling back to API interception")
        api_result = self._try_api_interception(query, search_type, page_url, limit, filters)
        if api_result is not None:
            return api_result

        # ----- Both strategies failed -----
        return ScrapeResult(
            command="search",
            success=False,
            error=(
                f"No search results found for '{query}'. "
                "TikTok may be blocking headless browsers from search results. "
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
        query: str,
        search_type: str,
        limit: int,
        filters: Dict[str, Any],
    ) -> ScrapeResult | None:
        """Try to extract search results from SSR __DEFAULT_SCOPE__ data.

        Returns a ScrapeResult on success, or None if no SSR data was found.
        """
        page = self.bm.new_page()
        try:
            self._tiktok_rate_limit_delay()

            page.goto(page_url, wait_until="networkidle", timeout=30000)
            self._check_anti_detection(page)
            self._dismiss_overlays(page)
            time.sleep(2)

            ssr_data = page.evaluate(self._SSR_SEARCH_JS)

            if not ssr_data or not ssr_data.get("data"):
                self._log("No SSR search data found in __DEFAULT_SCOPE__")
                return None

            scope_key = ssr_data.get("key", "")
            raw_data = ssr_data.get("data", {}) or {}

            self._log("Found SSR search data under key: %s", scope_key)

            # Extract items from SSR data -- the structure varies by scope key
            all_items = self._extract_ssr_search_items(raw_data, search_type)

            if not all_items:
                self._log("SSR data found but contained no result items")
                return None

            # Map to model dataclasses
            if search_type == "user":
                items = self._map_user_results(all_items, limit)
            else:
                items = self._map_video_results(all_items, limit)

            if not items:
                return None

            return ScrapeResult(
                command="search",
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

    def _extract_ssr_search_items(
        self, raw_data: Dict[str, Any], search_type: str
    ) -> List[Dict[str, Any]]:
        """Extract search result items from SSR scope data.

        The SSR data structure may vary; try several known key paths.
        """
        # Check statusCode early -- non-zero means TikTok returned an error
        status_code = raw_data.get("statusCode")
        if status_code is not None and status_code != 0:
            status_msg = raw_data.get("statusMsg", "")
            self._log(
                "SSR search data has error statusCode=%s msg=%s",
                status_code,
                status_msg,
            )
            return []

        items: List[Dict[str, Any]] = []

        # Common item key paths for search results
        item_keys = (
            ["item_list", "itemList", "items", "video_list"]
            if search_type == "video"
            else ["user_list", "userList", "users"]
        )

        # Try to find items directly
        for item_key in item_keys:
            found = raw_data.get(item_key, [])
            if isinstance(found, list) and found:
                items.extend(found)
                return items

        # Try nested under a 'data' key
        nested_data = raw_data.get("data", {})
        if isinstance(nested_data, dict):
            for item_key in item_keys:
                found = nested_data.get(item_key, [])
                if isinstance(found, list) and found:
                    items.extend(found)
                    return items

            # Try double-nested data.data
            double_nested = nested_data.get("data", {})
            if isinstance(double_nested, dict):
                for item_key in item_keys:
                    found = double_nested.get(item_key, [])
                    if isinstance(found, list) and found:
                        items.extend(found)
                        return items

        # Try nested under 'searchResult'
        search_result = raw_data.get("searchResult", {})
        if isinstance(search_result, dict):
            for item_key in item_keys:
                found = search_result.get(item_key, [])
                if isinstance(found, list) and found:
                    items.extend(found)
                    return items

        # Try webapp.search-video-detail style: items under specific nested path
        video_detail = raw_data.get("webapp.search-video-detail", {})
        if isinstance(video_detail, dict):
            for item_key in item_keys:
                found = video_detail.get(item_key, [])
                if isinstance(found, list) and found:
                    items.extend(found)
                    return items

        return items

    # ------------------------------------------------------------------
    # Strategy 2: API interception fallback
    # ------------------------------------------------------------------

    def _try_api_interception(
        self,
        query: str,
        search_type: str,
        page_url: str,
        limit: int,
        filters: Dict[str, Any],
    ) -> ScrapeResult | None:
        """Fall back to API interception for search results.

        Returns a ScrapeResult on success, or None if no API data was captured.
        """
        if search_type == "user":
            api_pattern = TIKTOK_API_PATTERNS["search_user"]
        else:
            api_pattern = TIKTOK_API_PATTERNS["search_video"]

        self._log("Attempting API interception for search '%s'", query)

        responses = self._intercept_api_paginated(
            page_url, api_pattern, max_pages=3,
        )

        if not responses:
            self._log("No API responses intercepted for search query '%s'", query)
            return None

        # Extract items from responses
        all_items: List[Dict[str, Any]] = []
        data_key = "user_list" if search_type == "user" else "item_list"

        for resp in responses:
            ok, raw_items, err_msg = self._extract_api_data(resp, data_key)
            if ok and raw_items:
                if isinstance(raw_items, list):
                    all_items.extend(raw_items)
                continue

            # Fallback: direct access for non-standard envelope
            direct_items = resp.get(data_key, [])
            if direct_items:
                all_items.extend(direct_items)
                continue

            # Try nested "data" key
            data = resp.get("data", {})
            if isinstance(data, dict):
                nested_items = data.get(data_key, [])
                if nested_items:
                    all_items.extend(nested_items)

        if not all_items:
            self._log("No items found in API responses for '%s'", query)
            return None

        # Map to model dataclasses
        if search_type == "user":
            items = self._map_user_results(all_items, limit)
        else:
            items = self._map_video_results(all_items, limit)

        return ScrapeResult(
            command="search",
            success=True,
            data=items,
            count=len(items),
            filters=filters,
        )

    # ------------------------------------------------------------------
    # API -> Model mappers
    # ------------------------------------------------------------------

    def _map_video_results(
        self, raw_items: List[Dict], limit: int
    ) -> List[SearchVideoResult]:
        """Map API search video items to SearchVideoResult models."""
        items: List[SearchVideoResult] = []
        seen_ids: set = set()

        for entry in raw_items:
            if len(items) >= limit:
                break

            # Extract fields with defensive defaults
            title = entry.get("desc", "") or entry.get("title", "")
            author = entry.get("author", {}) or {}
            creator = author.get("uniqueId", "") or author.get("nickname", "")
            video_id = str(entry.get("id", "") or "")

            # Deduplicate by video ID
            if video_id and video_id in seen_ids:
                continue
            if video_id:
                seen_ids.add(video_id)

            # Build video URL
            video_url = ""
            if creator and video_id:
                video_url = f"https://www.tiktok.com/@{creator}/video/{video_id}"

            # Stats (use `or 0` to handle None values)
            stats = entry.get("stats", {}) or {}
            view_cnt = stats.get("playCount", 0) or 0
            like_cnt = stats.get("diggCount", 0) or 0
            comment_cnt = stats.get("commentCount", 0) or 0
            share_cnt = stats.get("shareCount", 0) or 0

            # Duration
            video_info = entry.get("video", {}) or {}
            duration = video_info.get("duration", 0) or 0

            # Thumbnail
            thumbnail = video_info.get("cover", "") or video_info.get("originCover", "") or ""

            items.append(
                SearchVideoResult(
                    title=title,
                    creator=creator,
                    views=self._format_count(view_cnt),
                    likes=self._format_count(like_cnt),
                    video_url=video_url,
                    video_id=video_id,
                    thumbnail=thumbnail,
                    view_cnt=view_cnt,
                    like_cnt=like_cnt,
                    comment_cnt=comment_cnt,
                    share_cnt=share_cnt,
                    duration=duration,
                )
            )

        return items

    def _map_user_results(
        self, raw_items: List[Dict], limit: int
    ) -> List[SearchUserResult]:
        """Map API search user items to SearchUserResult models."""
        items: List[SearchUserResult] = []
        seen_usernames: set = set()

        for entry in raw_items:
            if len(items) >= limit:
                break

            # User search results may nest user data under "user_info"
            user_data = entry.get("user_info", entry) or entry

            username = user_data.get("uniqueId", "") or user_data.get("unique_id", "")
            nickname = user_data.get("nickname", "") or ""

            if not username:
                continue

            # Deduplicate by username
            if username in seen_usernames:
                continue
            seen_usernames.add(username)

            bio = user_data.get("signature", "") or ""
            verified = bool(user_data.get("verified", False))
            avatar = user_data.get("avatarThumb", "") or user_data.get("avatar", "") or ""

            # Follower/like counts — prefer 'heart' over 'heartCount'
            follower_cnt = user_data.get("followerCount", 0) or 0
            like_cnt = user_data.get("heart", 0) or user_data.get("heartCount", 0) or 0

            items.append(
                SearchUserResult(
                    username=username,
                    nickname=nickname,
                    bio=bio,
                    followers=self._format_count(follower_cnt),
                    likes=self._format_count(like_cnt),
                    avatar=avatar,
                    verified=verified,
                    follower_cnt=follower_cnt,
                    like_cnt=like_cnt,
                )
            )

        return items
