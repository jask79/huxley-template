"""Frozen dataclasses for TikTok Intelligence data models.

Fields are aligned with the Creative Center internal API response format
(creative_radar_api/v1/*). Human-readable string fields are kept for
backward compatibility with callers that expect formatted counts.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TrendingHashtag:
    """A trending hashtag from Creative Center.

    API source: popular_trend/hashtag/list or popular_trend/hashtag/rank_list
    """

    rank: int
    name: str
    posts: str = ""            # Human-readable count ("1.2M")
    views: str = ""            # Human-readable count
    trend_change: str = ""     # e.g., "+5", "-2", "new"
    country: str = ""
    industry: str = ""
    # API-native fields
    hashtag_id: str = ""
    publish_cnt: int = 0       # Raw post count from API
    video_views: int = 0       # Raw view count from API
    rank_diff: int = 0         # Numeric rank change
    rank_diff_type: int = 0    # 0=unchanged, 1=up, 2=down, 3=new
    is_promoted: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TrendingSong:
    """A trending song from Creative Center.

    API source: popular_trend/sound/rank_list
    Response key: data.sound_list[] or data.list[]
    """

    rank: int
    title: str
    artist: str = ""
    duration: str = ""         # Human-readable duration
    posts: str = ""
    trend_change: str = ""
    country: str = ""
    # API-native fields
    clip_id: str = ""          # Unique sound ID
    cover: str = ""            # Cover image URL
    link: str = ""             # TikTok sound page URL
    duration_seconds: int = 0  # Raw duration in seconds
    rank_diff: int = 0
    rank_diff_type: int = 0
    is_commercial: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TrendingCreator:
    """A trending creator from Creative Center.

    API source: popular_trend/creator/rank_list
    Response key: data.creator_list[] or data.list[]
    """

    rank: int
    username: str
    nickname: str = ""
    followers: str = ""
    likes: str = ""
    posts: str = ""
    trend_change: str = ""
    country: str = ""
    # API-native fields
    creator_id: str = ""
    avatar: str = ""           # Avatar URL
    follower_cnt: int = 0      # Raw follower count
    like_cnt: int = 0          # Raw like count
    rank_diff: int = 0
    rank_diff_type: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TrendingVideo:
    """A trending video from Creative Center.

    API source: popular_trend/video/rank_list or the main videos page
    """

    rank: int
    description: str = ""
    creator: str = ""
    likes: str = ""
    comments: str = ""
    shares: str = ""
    views: str = ""
    url: str = ""
    # API-native fields
    video_id: str = ""
    cover: str = ""
    like_cnt: int = 0
    comment_cnt: int = 0
    share_cnt: int = 0
    view_cnt: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TopAd:
    """A top-performing ad from Creative Center.

    API source: top_ads/v2/list
    Response key: data.materials[]
    """

    rank: int
    brand: str = ""
    description: str = ""
    likes: str = ""
    comments: str = ""
    shares: str = ""
    ctr: str = ""
    reach: str = ""
    objective: str = ""
    region: str = ""
    industry: str = ""
    url: str = ""
    # API-native fields
    ad_id: str = ""            # Material/ad ID
    ad_title: str = ""         # Raw ad title from API
    like_cnt: int = 0          # Raw like count
    ctr_raw: float = 0.0       # Raw CTR as decimal
    cost: int = 0              # Cost tier (1-5)
    video_id: str = ""         # vid from video_info
    industry_key: str = ""     # e.g., "label_23123000000"
    objective_key: str = ""    # e.g., "campaign_objective_video_view"
    is_search: bool = False
    tag: int = 0               # Ad tag identifier

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class HashtagAnalytics:
    """Detailed analytics for a specific hashtag."""

    name: str
    total_views: str = ""
    total_posts: str = ""
    trend_data: List[Dict[str, Any]] = field(default_factory=list)
    related_hashtags: List[str] = field(default_factory=list)
    top_videos: List[Dict[str, str]] = field(default_factory=list)
    country: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SearchVideoResult:
    """A video from tiktok.com search results.

    API source: /api/search/item/full/
    """

    title: str
    creator: str
    views: str = ""
    likes: str = ""
    video_url: str = ""
    video_id: str = ""
    thumbnail: str = ""
    view_cnt: int = 0
    like_cnt: int = 0
    comment_cnt: int = 0
    share_cnt: int = 0
    duration: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SearchUserResult:
    """A user from tiktok.com search results.

    API source: /api/search/user/full/
    """

    username: str
    nickname: str
    bio: str = ""
    followers: str = ""
    likes: str = ""
    avatar: str = ""
    verified: bool = False
    follower_cnt: int = 0
    like_cnt: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CompetitorProfile:
    """Full competitor profile analytics.

    API source: /api/user/detail/ + /api/post/item_list/
    """

    username: str
    nickname: str = ""
    bio: str = ""
    followers: str = ""
    following: str = ""
    likes: str = ""
    videos_count: int = 0
    avatar: str = ""
    verified: bool = False
    avg_views: str = ""
    avg_likes: str = ""
    avg_comments: str = ""
    engagement_rate: str = ""
    follower_cnt: int = 0
    following_cnt: int = 0
    like_cnt: int = 0
    recent_videos: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ShopProduct:
    """A product from TikTok Shop.

    API source: TikTok Shop search/product APIs
    """

    title: str
    price: str = ""
    price_raw: float = 0.0
    rating: str = ""
    reviews: str = ""
    sold: str = ""
    seller: str = ""
    url: str = ""
    thumbnail: str = ""
    product_id: str = ""
    category: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScrapeResult:
    """Wrapper for scraper output with metadata."""

    command: str
    success: bool
    data: List[Any] = field(default_factory=list)
    count: int = 0
    filters: Dict[str, Any] = field(default_factory=dict)
    cached: bool = False
    error: Optional[str] = None
    _cached_at: Optional[str] = None
    scores: Dict[int, float] = field(default_factory=dict)
    velocities: Dict[int, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert nested frozen dataclasses if they have to_dict
        if self.data and hasattr(self.data[0], "to_dict"):
            d["data"] = [item.to_dict() for item in self.data]
        # Exclude transient scoring fields from serialization
        d.pop("scores", None)
        d.pop("velocities", None)
        return d
