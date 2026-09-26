"""Creative Center trends scraper — hashtags, songs, creators, videos.

Uses API response interception instead of DOM parsing. The Creative Center
frontend loads data via internal REST endpoints (creative_radar_api/v1/*)
that return clean JSON. We navigate to the CC page (which establishes
session cookies + user-sign headers), then intercept those API responses.

Fallback: If API interception yields no results, logs a warning and returns
an empty result set rather than crashing.
"""

import logging
from typing import Any, Dict, List

from ..config import API_PATTERNS, URLS
from ..models import (
    ScrapeResult,
    TrendingCreator,
    TrendingHashtag,
    TrendingSong,
    TrendingVideo,
)
from .base import BaseScraper

logger = logging.getLogger(__name__)


class CreativeCenterScraper(BaseScraper):
    """Scrape trending data from TikTok Creative Center via API interception."""

    name = "creative_center"

    # URL map for each trend type (page URLs that trigger API calls)
    _URL_MAP = {
        "hashtags": URLS["trending_hashtags"],
        "songs": URLS["trending_songs"],
        "creators": URLS["trending_creators"],
        "videos": URLS["trending_videos"],
    }

    # API pattern map for response interception
    _API_MAP = {
        "hashtags": API_PATTERNS["hashtags"],
        "songs": API_PATTERNS["songs"],
        "creators": API_PATTERNS["creators"],
        "videos": API_PATTERNS["videos"],
    }

    # API response data key map (key within the "data" object that holds the list)
    _DATA_KEY_MAP = {
        "hashtags": "list",
        "songs": "sound_list",
        "creators": "creator_list",
        "videos": "list",
    }

    # Extractor dispatch
    _EXTRACTORS = None  # initialized in __init__ to bind self

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._EXTRACTORS = {
            "hashtags": self._map_hashtags,
            "songs": self._map_songs,
            "creators": self._map_creators,
            "videos": self._map_videos,
        }

    def scrape(self, filters: Dict[str, Any], limit: int = 20) -> ScrapeResult:
        """Scrape trending data for a given type via API interception.

        Filters:
            type: str — one of hashtags, songs, creators, videos
            country: str — optional country code (e.g., "US")
            industry: str — optional industry filter
            period: str — time period (7, 30, 180)
        """
        trend_type = filters.get("type", "hashtags")
        page_url = self._URL_MAP.get(trend_type)
        api_pattern = self._API_MAP.get(trend_type)

        if not page_url or not api_pattern:
            return ScrapeResult(
                command="trends",
                success=False,
                error=f"Unknown trend type: {trend_type}",
                filters=filters,
            )

        # Build the page URL with filter params (the frontend reads URL params
        # and passes them to its API calls)
        page_url = self._build_url(page_url, filters)

        # Intercept API responses
        responses = self._intercept_api(page_url, api_pattern)

        if not responses:
            self._log("No API responses intercepted for %s", trend_type)
            return ScrapeResult(
                command="trends",
                success=False,
                error=f"No API data intercepted for {trend_type}. "
                       "The page may not have triggered the expected API call.",
                filters=filters,
            )

        # Extract data from the first successful response
        data_key = self._DATA_KEY_MAP.get(trend_type, "list")
        country = filters.get("country", "")

        for resp in responses:
            ok, raw_items, err_msg = self._extract_api_data(resp, data_key)

            if not ok:
                # Handle known TikTok-side errors gracefully
                code = resp.get("code", -1)
                if code == 50004:
                    # "no available es index" — TikTok's Elasticsearch is down
                    self._log(
                        "TikTok API returned code 50004 (ES index unavailable) "
                        "for %s — returning empty result",
                        trend_type,
                    )
                    return ScrapeResult(
                        command="trends",
                        success=True,
                        data=[],
                        count=0,
                        filters=filters,
                        error=f"TikTok API: {err_msg} (non-fatal, their infrastructure issue)",
                    )
                self._log("API response error for %s: %s", trend_type, err_msg)
                continue

            if not raw_items:
                self._log("API response had empty data for %s", trend_type)
                continue

            # Map raw API items to model dataclasses
            mapper = self._EXTRACTORS[trend_type]
            items = mapper(raw_items, country, limit)

            return ScrapeResult(
                command="trends",
                success=True,
                data=items,
                count=len(items),
                filters=filters,
            )

        # All responses failed
        return ScrapeResult(
            command="trends",
            success=False,
            error=f"All {len(responses)} API responses failed for {trend_type}",
            filters=filters,
        )

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------

    def _build_url(self, base_url: str, filters: Dict[str, Any]) -> str:
        """Append query parameters for country/industry filters."""
        params = []
        country = filters.get("country", "")
        if country:
            params.append(f"country_code={country}")
        industry = filters.get("industry", "")
        if industry:
            params.append(f"industry={industry}")
        period = filters.get("period", "7")  # default 7 days
        params.append(f"period={period}")

        if params:
            separator = "&" if "?" in base_url else "?"
            return f"{base_url}{separator}{'&'.join(params)}"
        return base_url

    # ------------------------------------------------------------------
    # API → Model mappers
    # ------------------------------------------------------------------

    def _map_hashtags(
        self, raw_items: List[Dict], country: str, limit: int
    ) -> List[TrendingHashtag]:
        """Map API hashtag items to TrendingHashtag models."""
        items = []
        for i, entry in enumerate(raw_items[:limit]):
            name = entry.get("hashtag_name", "") or entry.get("name", "")
            if not name:
                continue

            rank = entry.get("rank", i + 1)
            rank_diff = entry.get("rank_diff", 0)
            rank_diff_type = entry.get("rank_diff_type", 0)
            publish_cnt = entry.get("publish_cnt", 0)
            video_views = entry.get("video_views", 0)

            items.append(
                TrendingHashtag(
                    rank=rank,
                    name=name,
                    posts=self._format_count(publish_cnt),
                    views=self._format_count(video_views),
                    trend_change=self._rank_diff_to_string(rank_diff, rank_diff_type),
                    country=country,
                    industry=entry.get("industry_key", ""),
                    hashtag_id=str(entry.get("hashtag_id", "") or entry.get("id", "")),
                    publish_cnt=publish_cnt,
                    video_views=video_views,
                    rank_diff=rank_diff,
                    rank_diff_type=rank_diff_type,
                    is_promoted=bool(entry.get("promoted", False)),
                )
            )
        return items

    def _map_songs(
        self, raw_items: List[Dict], country: str, limit: int
    ) -> List[TrendingSong]:
        """Map API sound items to TrendingSong models."""
        items = []
        for i, entry in enumerate(raw_items[:limit]):
            title = (
                entry.get("title", "")
                or entry.get("name", "")
                or entry.get("sound_name", "")
            )
            if not title:
                # Songs sometimes have no title — use clip_id as fallback
                clip_id = entry.get("clip_id", "")
                if clip_id:
                    title = f"Sound {clip_id}"
                else:
                    continue

            rank = entry.get("rank", i + 1)
            rank_diff = entry.get("rank_diff", 0)
            rank_diff_type = entry.get("rank_diff_type", 0)
            duration_sec = entry.get("duration", 0)

            items.append(
                TrendingSong(
                    rank=rank,
                    title=title,
                    artist=entry.get("author", ""),
                    duration=f"{duration_sec}s" if duration_sec else "",
                    posts=self._format_count(entry.get("publish_cnt", 0)),
                    trend_change=self._rank_diff_to_string(rank_diff, rank_diff_type),
                    country=country or entry.get("country_code", ""),
                    clip_id=str(entry.get("clip_id", "")),
                    cover=entry.get("cover", ""),
                    link=entry.get("link", ""),
                    duration_seconds=duration_sec,
                    rank_diff=rank_diff,
                    rank_diff_type=rank_diff_type,
                    is_commercial=bool(entry.get("if_cml", False)),
                )
            )
        return items

    def _map_creators(
        self, raw_items: List[Dict], country: str, limit: int
    ) -> List[TrendingCreator]:
        """Map API creator items to TrendingCreator models."""
        items = []
        for i, entry in enumerate(raw_items[:limit]):
            username = entry.get("tt_unique_id", "") or entry.get("username", "")
            nickname = entry.get("nickname", "") or entry.get("nick_name", "")
            if not username and not nickname:
                continue

            rank = entry.get("rank", i + 1)
            rank_diff = entry.get("rank_diff", 0)
            rank_diff_type = entry.get("rank_diff_type", 0)
            follower_cnt = entry.get("follower_cnt", 0)
            like_cnt = entry.get("like_cnt", 0) or entry.get("likes", 0)

            items.append(
                TrendingCreator(
                    rank=rank,
                    username=username or nickname,
                    nickname=nickname,
                    followers=self._format_count(follower_cnt),
                    likes=self._format_count(like_cnt),
                    trend_change=self._rank_diff_to_string(rank_diff, rank_diff_type),
                    country=country or entry.get("country_code", ""),
                    creator_id=str(entry.get("creator_id", "") or entry.get("id", "")),
                    avatar=entry.get("avatar", "") or entry.get("avatar_url", ""),
                    follower_cnt=follower_cnt,
                    like_cnt=like_cnt,
                    rank_diff=rank_diff,
                    rank_diff_type=rank_diff_type,
                )
            )
        return items

    def _map_videos(
        self, raw_items: List[Dict], country: str, limit: int
    ) -> List[TrendingVideo]:
        """Map API video items to TrendingVideo models."""
        items = []
        for i, entry in enumerate(raw_items[:limit]):
            description = (
                entry.get("title", "")
                or entry.get("desc", "")
                or entry.get("description", "")
            )
            creator = (
                entry.get("author", "")
                or entry.get("nick_name", "")
                or entry.get("creator", "")
            )

            rank = entry.get("rank", i + 1)
            like_cnt = entry.get("like_cnt", 0) or entry.get("digg_count", 0)
            comment_cnt = entry.get("comment_cnt", 0) or entry.get("comment_count", 0)
            share_cnt = entry.get("share_cnt", 0) or entry.get("share_count", 0)
            view_cnt = entry.get("view_cnt", 0) or entry.get("play_count", 0)
            video_id = str(entry.get("item_id", "") or entry.get("id", ""))

            # Build URL from video ID
            url = entry.get("url", "") or entry.get("link", "")
            if not url and video_id:
                url = f"https://www.tiktok.com/video/{video_id}"

            items.append(
                TrendingVideo(
                    rank=rank,
                    description=description,
                    creator=creator,
                    likes=self._format_count(like_cnt),
                    comments=self._format_count(comment_cnt),
                    shares=self._format_count(share_cnt),
                    views=self._format_count(view_cnt),
                    url=url,
                    video_id=video_id,
                    cover=entry.get("cover", ""),
                    like_cnt=like_cnt,
                    comment_cnt=comment_cnt,
                    share_cnt=share_cnt,
                    view_cnt=view_cnt,
                )
            )
        return items
