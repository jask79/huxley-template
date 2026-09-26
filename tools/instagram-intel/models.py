"""Frozen dataclasses for Instagram Intelligence data models.

Fields align with Meta Graph API response structures.
Human-readable string fields kept for formatted output.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class AccountInfo:
    """Instagram Business Account info.

    API source: GET /{ig-user-id}?fields=id,name,username,...
    """

    account_id: str
    name: str
    username: str = ""
    followers_count: int = 0
    following_count: int = 0
    media_count: int = 0
    profile_picture_url: str = ""
    biography: str = ""
    website: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TokenInfo:
    """Token debug information.

    API source: GET /debug_token?input_token={token}
    """

    app_id: str = ""
    user_id: str = ""
    type: str = ""
    expires_at: int = 0
    is_valid: bool = False
    scopes: List[str] = field(default_factory=list)
    granular_scopes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CompetitorProfile:
    """Competitor profile via Business Discovery.

    API source: GET /{ig-user-id}?fields=business_discovery.fields(...)&username={target}
    """

    username: str
    name: str = ""
    ig_id: str = ""
    biography: str = ""
    followers_count: int = 0
    media_count: int = 0
    profile_picture_url: str = ""
    website: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MediaItem:
    """Instagram media item (post, reel, carousel, story).

    API source: Business Discovery media edge or own media list.
    """

    media_id: str
    media_type: str = ""  # IMAGE, VIDEO, CAROUSEL_ALBUM
    caption: str = ""
    permalink: str = ""
    timestamp: str = ""
    like_count: int = 0
    comments_count: int = 0
    thumbnail_url: str = ""
    media_url: str = ""
    username: str = ""  # populated from Business Discovery

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class HashtagInfo:
    """Hashtag search result.

    API source: GET /ig_hashtag_search?q={name}&user_id={ig_user_id}
    """

    hashtag_id: str
    name: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class InsightMetric:
    """A single insight metric.

    API source: GET /{ig-user-id}/insights or GET /{media-id}/insights
    """

    name: str
    period: str
    title: str = ""
    description: str = ""
    values: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MentionItem:
    """Media where the account is @mentioned.

    API source: GET /{ig-user-id}/tags
    """

    media_id: str
    caption: str = ""
    media_type: str = ""
    timestamp: str = ""
    permalink: str = ""
    username: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EngagementReport:
    """Computed engagement rate from Business Discovery data."""

    username: str
    followers_count: int = 0
    media_count: int = 0
    avg_likes: float = 0.0
    avg_comments: float = 0.0
    engagement_rate: float = 0.0  # (avg_likes + avg_comments) / followers * 100
    media_analyzed: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CommandResult:
    """Wrapper for command output with metadata."""

    command: str
    success: bool
    data: List[Any] = field(default_factory=list)
    count: int = 0
    filters: Dict[str, Any] = field(default_factory=dict)
    cached: bool = False
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert nested frozen dataclasses if they have to_dict
        if self.data:
            d["data"] = [item.to_dict() if hasattr(item, "to_dict") else item for item in self.data]
        return d


# ---------------------------------------------------------------------------
# Phase 2 — Scraping models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrendingReel:
    """A trending reel scraped from instagram.com/reels/.

    Data source: Playwright response interception on /api/v1/ endpoints.
    """

    reel_id: str = ""
    author: str = ""
    caption: str = ""
    likes: int = 0
    comments: int = 0
    views: int = 0
    audio_name: str = ""
    audio_id: str = ""
    permalink: str = ""
    thumbnail_url: str = ""
    likes_fmt: str = ""       # Human-readable "1.2K"
    views_fmt: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TrendingAudio:
    """A trending audio track extracted from Reels.

    Aggregated from reel items by audio_id/audio_name frequency.
    """

    audio_id: str = ""
    name: str = ""
    artist: str = ""
    usage_count: int = 0
    reels_using: List[str] = field(default_factory=list)  # List of reel permalinks

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExploreItem:
    """An item from the Instagram Explore grid.

    Data source: /api/v1/discover/web/explore_grid/ response interception.
    """

    media_id: str = ""
    media_type: str = ""      # IMAGE, VIDEO, CAROUSEL
    author: str = ""
    caption: str = ""
    likes: int = 0
    comments: int = 0
    permalink: str = ""
    thumbnail_url: str = ""
    likes_fmt: str = ""
    comments_fmt: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SearchUser:
    """A user from instagram.com search results.

    Data source: /api/v1/web/search/topsearch/ response interception.
    """

    username: str = ""
    full_name: str = ""
    followers: int = 0
    is_verified: bool = False
    is_private: bool = False
    profile_pic_url: str = ""
    followers_fmt: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SearchHashtag:
    """A hashtag from instagram.com search results.

    Data source: /api/v1/web/search/topsearch/ response interception.
    """

    name: str = ""
    media_count: int = 0
    media_count_fmt: str = ""  # Human-readable "1.2M"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SearchContent:
    """A content item from instagram.com search.

    Data source: /api/v1/web/search/topsearch/ or explore grid interception.
    """

    media_id: str = ""
    media_type: str = ""
    author: str = ""
    caption: str = ""
    likes: int = 0
    comments: int = 0
    permalink: str = ""
    thumbnail_url: str = ""
    likes_fmt: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class UserReel:
    """A reel from a user's profile /reels/ tab.

    Data source: Playwright interception on user's reel media endpoint.
    """

    reel_id: str = ""
    caption: str = ""
    likes: int = 0
    comments: int = 0
    views: int = 0
    permalink: str = ""
    thumbnail_url: str = ""
    audio_name: str = ""
    likes_fmt: str = ""
    views_fmt: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ScrapedUserProfile:
    """A public user profile scraped from instagram.com/{username}/.

    Works for ANY public account, not limited to Business accounts.
    Data source: embedded JSON or API response interception.
    """

    username: str = ""
    full_name: str = ""
    biography: str = ""
    followers: int = 0
    following: int = 0
    media_count: int = 0
    is_verified: bool = False
    is_private: bool = False
    is_business: bool = False
    category: str = ""
    external_url: str = ""
    profile_pic_url: str = ""
    followers_fmt: str = ""
    following_fmt: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class HashtagDeep:
    """Deep hashtag data scraped from instagram.com/explore/tags/{hashtag}/.

    No 30/week API limit. Data source: /api/v1/tags/web_info/ interception.
    """

    name: str = ""
    media_count: int = 0
    media_count_fmt: str = ""
    top_posts: List[Dict[str, Any]] = field(default_factory=list)
    recent_posts: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScrapeResult:
    """Wrapper for Phase 2 scraper output with metadata."""

    command: str
    success: bool
    data: List[Any] = field(default_factory=list)
    count: int = 0
    filters: Dict[str, Any] = field(default_factory=dict)
    cached: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert nested frozen dataclasses if they have to_dict
        if self.data:
            d["data"] = [item.to_dict() if hasattr(item, "to_dict") else item for item in self.data]
        return d
