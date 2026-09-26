"""Constants, ANSI colors, API config, and credential defaults."""

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Terminal colours (matches tiktok-intel/config.py)
# ---------------------------------------------------------------------------
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# ---------------------------------------------------------------------------
# Meta Graph API
# ---------------------------------------------------------------------------
GRAPH_API_VERSION = "v24.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# ---------------------------------------------------------------------------
# Credential resolution defaults
# ---------------------------------------------------------------------------
# Paths relative to Huxley root (resolved at runtime)
ECOMMERCE_SUBPATH = "capsules/ecommerce"
BRANDS_SUBPATH = f"{ECOMMERCE_SUBPATH}/brands"

# Keychain service names (already provisioned)
KEYCHAIN_META_TOKEN = "meta-access-token"
KEYCHAIN_META_APP_ID = "META_APP_ID"
KEYCHAIN_META_APP_SECRET = "meta-app-secret"

# Environment variable names
ENV_META_TOKEN = "META_ACCESS_TOKEN"
ENV_META_APP_ID = "META_APP_ID"
ENV_META_APP_SECRET = "META_APP_SECRET"
ENV_META_DEFAULT_BRAND = "META_DEFAULT_BRAND"
ENV_IG_USER_ID = "META_IG_USER_ID"

# Additional .env search path (meta-api.py's own capsule .env)
EXAMPLE_DIGITAL_SUBPATH = "capsules/example-digital-capsule"

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
DEFAULT_CACHE_TTL = 3600  # 1 hour in seconds
CACHE_DIR = "/tmp/instagram-intel-cache"

# ---------------------------------------------------------------------------
# Adaptive Cache TTL per command (#8)
# Trending data goes stale faster than profile data.
# ---------------------------------------------------------------------------
COMMAND_TTL = {
    # Phase 2 — trending/volatile data (short TTL)
    "trending-reels": 900,       # 15 minutes
    "trending-audio": 900,       # 15 minutes
    "explore": 1800,             # 30 minutes
    "search-users": 3600,        # 1 hour
    "search-hashtags": 3600,     # 1 hour
    "search-content": 1800,      # 30 minutes
    # Phase 2 — profile/stable data (longer TTL)
    "user-profile": 86400,       # 24 hours
    "user-reels": 7200,          # 2 hours
    "hashtag-deep": 3600,        # 1 hour
    # Phase 1 — Graph API commands
    "account": 86400,            # 24 hours
    "competitor": 86400,         # 24 hours
    "competitor-media": 7200,    # 2 hours
    "competitor-compare": 7200,  # 2 hours
    "engagement-rate": 7200,     # 2 hours
    "hashtag-top": 3600,         # 1 hour
    "hashtag-recent": 1800,      # 30 minutes
    "own-insights": 3600,        # 1 hour
    "media-insights": 3600,      # 1 hour
    "mentions": 3600,            # 1 hour
}

# ---------------------------------------------------------------------------
# Rate limiting (Graph API)
# ---------------------------------------------------------------------------
MIN_REQUEST_INTERVAL = 0.3  # 200 calls/user/hour = ~3.3/s, conservative

# ---------------------------------------------------------------------------
# Scraping defaults (Phase 2)
# ---------------------------------------------------------------------------
SCRAPE_MIN_DELAY = 2.0  # seconds between navigations
SCRAPE_MAX_DELAY = 4.0

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

CHROMIUM_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-infobars",
    "--disable-extensions",
    "--enable-webgl",
    "--use-gl=swiftshader",
]

VIEWPORT = {"width": 1920, "height": 1080}
LOCALE = "en-US"
TIMEZONE = "America/New_York"

PAGE_LOAD_TIMEOUT = 30000  # ms
SELECTOR_TIMEOUT = 15000  # ms

# ---------------------------------------------------------------------------
# Instagram account insights — valid metrics by period
# ---------------------------------------------------------------------------
# v24.0 account metrics — split by metric_type
# Some metrics need metric_type=total_value, "reach" works with period=day
ACCOUNT_METRICS_TIME_SERIES = [
    "reach",
]

ACCOUNT_METRICS_TOTAL_VALUE = [
    "profile_views",
    "website_clicks",
    "accounts_engaged",
    "total_interactions",
    "likes",
    "comments",
    "shares",
    "saves",
    "profile_links_taps",
]

ACCOUNT_METRICS_LIFETIME = [
    "follower_count",
    "online_followers",
    "follower_demographics",
]

# v24.0 media metrics — varies by media type
# IMAGE/CAROUSEL: impressions, reach, saved, total_interactions, likes, comments, shares
# VIDEO (feed): impressions, reach, saved, total_interactions, likes, comments, shares, video_views
# REEL: reach, saved, total_interactions, likes, comments, shares, ig_reels_avg_watch_time, ig_reels_video_view_total_time
MEDIA_METRICS_DEFAULT = [
    "reach",
    "saved",
    "total_interactions",
    "likes",
    "comments",
    "shares",
]

MEDIA_METRICS_VIDEO = [
    "reach",
    "saved",
    "total_interactions",
    "likes",
    "comments",
    "shares",
    "video_views",
]

MEDIA_METRICS_REEL = [
    "reach",
    "saved",
    "total_interactions",
    "likes",
    "comments",
    "shares",
    "ig_reels_avg_watch_time",
    "ig_reels_video_view_total_time",
]

# ---------------------------------------------------------------------------
# Exit codes (matches tiktok-intel convention)
# ---------------------------------------------------------------------------
EXIT_SUCCESS = 0
EXIT_EXPECTED_ERROR = 1
EXIT_UNEXPECTED_ERROR = 2

# ---------------------------------------------------------------------------
# Hashtag API limit
# ---------------------------------------------------------------------------
HASHTAG_WEEKLY_LIMIT = 30  # Max unique hashtags per 7 days via Graph API
