"""Constants, ANSI colors, Creative Center URLs, and browser configuration."""

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Terminal colours
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
# TikTok Creative Center URLs (all public, no auth required)
# ---------------------------------------------------------------------------
CC_BASE = "https://ads.tiktok.com/business/creativecenter"

URLS = {
    "trending_hashtags": f"{CC_BASE}/inspiration/popular/hashtag/pc/en",
    "trending_songs": f"{CC_BASE}/inspiration/popular/music/pc/en",
    "trending_creators": f"{CC_BASE}/inspiration/popular/creator/pc/en",
    "trending_videos": f"{CC_BASE}/inspiration/popular/pc/en",
    "top_ads": f"{CC_BASE}/inspiration/topads/pc/en",
    "keyword_insights": f"{CC_BASE}/keyword-insights/pc/en",
}

# ---------------------------------------------------------------------------
# Creative Center internal API patterns (for response interception)
# ---------------------------------------------------------------------------
# The CC frontend fetches data from these REST endpoints. We navigate to the
# page (which establishes session cookies and user-sign headers), then
# intercept the API responses instead of parsing the React DOM.

API_PATTERNS = {
    "hashtags": "creative_radar_api/v1/popular_trend/hashtag/",
    "songs": "creative_radar_api/v1/popular_trend/sound/rank_list",
    "creators": "creative_radar_api/v1/popular_trend/creator/",
    "videos": "creative_radar_api/v1/popular_trend/video/",
    "top_ads": "creative_radar_api/v1/top_ads/v2/list",
    "hashtag_filters": "creative_radar_api/v1/popular_trend/hashtag/filters",
}

# Timeout (ms) for waiting on an intercepted API response
API_INTERCEPT_TIMEOUT = 20000

# ---------------------------------------------------------------------------
# Browser configuration
# ---------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

CHROMIUM_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]

# Enhanced launch args for tiktok.com (heavier bot detection)
# Mirrors Bowser's battle-tested Chromium flags.
ENHANCED_CHROMIUM_ARGS = CHROMIUM_ARGS + [
    "--disable-infobars",
    "--disable-extensions",
    "--enable-webgl",
    "--use-gl=swiftshader",
]

VIEWPORT = {"width": 1920, "height": 1080}
LOCALE = "en-US"
TIMEZONE = "America/New_York"

# ---------------------------------------------------------------------------
# Scraping defaults
# ---------------------------------------------------------------------------
DEFAULT_LIMIT = 20
DEFAULT_CACHE_TTL = 3600  # 1 hour in seconds
CACHE_DIR = "/tmp/tiktok-intel-cache"

# Rate limiting
MIN_DELAY = 1.5  # seconds between navigations
MAX_DELAY = 3.5

# Page load
PAGE_LOAD_TIMEOUT = 30000  # ms
SELECTOR_TIMEOUT = 15000  # ms

# ---------------------------------------------------------------------------
# Supported filter values
# ---------------------------------------------------------------------------
TREND_TYPES = ["hashtags", "songs", "creators", "videos"]

COUNTRIES = {
    "US": "United States",
    "GB": "United Kingdom",
    "CA": "Canada",
    "AU": "Australia",
    "DE": "Germany",
    "FR": "France",
    "JP": "Japan",
    "BR": "Brazil",
    "MX": "Mexico",
    "IN": "India",
    "ID": "Indonesia",
    "TH": "Thailand",
    "VN": "Vietnam",
    "PH": "Philippines",
    "MY": "Malaysia",
    "SA": "Saudi Arabia",
    "AE": "UAE",
}

INDUSTRIES = [
    "apparel",
    "beauty",
    "education",
    "electronics",
    "entertainment",
    "finance",
    "food",
    "games",
    "health",
    "home",
    "news",
    "pets",
    "sports",
    "tech",
    "travel",
    "vehicles",
]

AD_SORT_OPTIONS = ["for_you", "reach", "ctr", "like", "comment", "share"]

AD_OBJECTIVES = [
    "Conversions",
    "Traffic",
    "Reach",
    "Video Views",
    "App Install",
    "Lead Generation",
    "Community Interaction",
]

# ---------------------------------------------------------------------------
# Exit codes (matches tiktok.py convention)
# ---------------------------------------------------------------------------
EXIT_SUCCESS = 0
EXIT_EXPECTED_ERROR = 1
EXIT_UNEXPECTED_ERROR = 2

# ---------------------------------------------------------------------------
# Phase 2 — tiktok.com URLs
# ---------------------------------------------------------------------------
TIKTOK_BASE = "https://www.tiktok.com"

TIKTOK_URLS = {
    "search": f"{TIKTOK_BASE}/search",
    "user_profile": f"{TIKTOK_BASE}/@{{username}}",
}

# Phase 2 — tiktok.com internal API patterns for interception
TIKTOK_API_PATTERNS = {
    "search_video": "/api/search/item/full/",
    "search_user": "/api/search/user/full/",
    "search_general": "/api/search/general/full/",
    "user_detail": "/api/user/detail/",
    "user_posts": "/api/post/item_list/",
}

# TikTok Shop
SHOP_BASE = "https://www.tiktok.com/shop"
SHOP_ALT_BASE = "https://shop.tiktok.com"
SHOP_API_PATTERNS = {
    "search": "/api/v1/search/product",
    "product_detail": "/api/v1/product/detail",
}

# Enhanced stealth config (for tiktok.com — heavier bot detection)
ENHANCED_USER_AGENTS = [
    # macOS + Chrome (recent versions)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    # Windows + Chrome (recent versions)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    # Windows 11 + Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # macOS + slightly older Chrome (still common)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Linux + Chrome (adds OS diversity)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

# Browser-like HTTP headers for enhanced mode (matches real Chrome traffic)
ENHANCED_HTTP_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

# Geolocation for enhanced mode (NYC — common US origin)
ENHANCED_GEOLOCATION = {"longitude": -74.006, "latitude": 40.7128}

# Phase 2 rate limiting (wider delays for tiktok.com)
TIKTOK_MIN_DELAY = 3.0
TIKTOK_MAX_DELAY = 6.0

# Search types for the search command
SEARCH_TYPES = ["video", "user"]
