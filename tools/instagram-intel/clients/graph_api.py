"""Official Instagram Graph API client for intelligence/research.

Uses the Meta Graph API with System User token (never expires).
Credential resolution follows the same chain as meta-api.py:
  1. Brand .env: capsules/ecommerce/brands/{brand}/.env
  2. Capsule .env: capsules/ecommerce/.env
  3. Environment variables
  4. macOS Keychain (security find-generic-password)

No pip dependencies — stdlib only (urllib, json, subprocess).
"""

import json
import logging
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

# Instagram username: 1-30 chars, alphanumeric + periods + underscores
_VALID_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._]{1,30}$")

from ..config import (
    ENV_IG_USER_ID,
    ENV_META_APP_ID,
    ENV_META_APP_SECRET,
    ENV_META_DEFAULT_BRAND,
    ENV_META_TOKEN,
    GRAPH_API_BASE,
    GRAPH_API_VERSION,
    KEYCHAIN_META_APP_ID,
    KEYCHAIN_META_APP_SECRET,
    KEYCHAIN_META_TOKEN,
    MIN_REQUEST_INTERVAL,
)
from ..exceptions import (
    APIError,
    AuthError,
    CredentialError,
    RateLimitError,
    TokenExpiredError,
)
from ..models import (
    AccountInfo,
    CompetitorProfile,
    EngagementReport,
    HashtagInfo,
    InsightMetric,
    MediaItem,
    MentionItem,
    TokenInfo,
)

logger = logging.getLogger("instagram-intel.graph")

# ---------------------------------------------------------------------------
# Huxley root detection
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
# tools/instagram-intel/clients/ -> tools/ -> Huxley root
CATALYST_ROOT = _THIS_DIR.parent.parent.parent
ECOMMERCE_DIR = CATALYST_ROOT / "capsules" / "ecommerce"
BRANDS_DIR = ECOMMERCE_DIR / "brands"
EXAMPLE_DIGITAL_DIR = CATALYST_ROOT / "capsules" / "example-digital-capsule"


# ---------------------------------------------------------------------------
# Credential Loader (same pattern as meta-api.py BrandCredentialLoader)
# ---------------------------------------------------------------------------

class BrandCredentialLoader:
    """Multi-source credential loader for per-brand Meta credentials.

    Resolution order:
      1. Brand .env: capsules/ecommerce/brands/{brand}/.env
      2. Capsule .env: capsules/ecommerce/.env
      3. Environment variables
      4. macOS Keychain via `security find-generic-password`
    """

    def __init__(self, brand: str):
        self.brand = brand
        self._cache: Dict[str, str] = {}
        self._env_loaded = False

    def _load_env_files(self) -> None:
        """Load .env files into cache (brand-specific overrides capsule-level).

        Resolution order (lowest to highest priority):
          1. capsules/example-digital-capsule/.env  (Meta API config lives here)
          2. capsules/ecommerce/.env
          3. capsules/ecommerce/brands/{brand}/.env
        """
        if self._env_loaded:
            return
        self._env_loaded = True

        # Huxley Digital capsule .env (lowest — has META_APP_ID etc.)
        cd_env = EXAMPLE_DIGITAL_DIR / ".env"
        if cd_env.is_file():
            self._parse_env(cd_env)

        # Ecommerce capsule .env
        capsule_env = ECOMMERCE_DIR / ".env"
        if capsule_env.is_file():
            self._parse_env(capsule_env)

        # Brand .env (highest priority, overwrites all)
        brand_env = BRANDS_DIR / self.brand / ".env"
        if brand_env.is_file():
            self._parse_env(brand_env)

    def _parse_env(self, path: Path) -> None:
        """Parse a .env file into the cache."""
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip("'\"")
                        self._cache[key] = value
                        logger.debug("Loaded %s from %s", key, path)
        except Exception as e:
            logger.debug("Failed to parse %s: %s", path, e)

    def _keychain_read(self, service: str) -> Optional[str]:
        """Read a password from macOS Keychain."""
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-w"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                logger.debug("Keychain read OK for service '%s'", service)
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.debug("Keychain lookup failed for '%s': %s", service, e)
        return None

    def get(self, env_key: str, keychain_service: Optional[str] = None) -> Optional[str]:
        """Get a credential value from the resolution chain.

        Args:
            env_key: Environment variable name (also checked in .env files).
            keychain_service: Optional Keychain service name to try last.
        """
        self._load_env_files()

        # 1. Brand/capsule .env
        if env_key in self._cache:
            return self._cache[env_key]

        # 2. Environment variables
        val = os.environ.get(env_key, "").strip()
        if val:
            return val

        # 3. macOS Keychain
        if keychain_service:
            kc_val = self._keychain_read(keychain_service)
            if kc_val:
                return kc_val

        return None

    def require(self, env_key: str, keychain_service: Optional[str] = None,
                label: str = "") -> str:
        """Get a credential or raise CredentialError."""
        val = self.get(env_key, keychain_service)
        if not val:
            desc = label or env_key
            raise CredentialError(
                f"Missing credential: {desc}\n"
                f"  Checked: .env files, ${env_key}, "
                f"{'Keychain ' + repr(keychain_service) if keychain_service else 'no Keychain service'}\n"
                f"  Brand: {self.brand}"
            )
        return val


def resolve_brand(brand_arg: Optional[str]) -> str:
    """Resolve brand name from arg, env, or auto-detect.

    Priority:
      1. --brand flag
      2. META_DEFAULT_BRAND env
      3. First brand with meta.enabled: true in brand.yaml
    """
    if brand_arg:
        return brand_arg

    env_brand = os.environ.get(ENV_META_DEFAULT_BRAND, "").strip()
    if env_brand:
        return env_brand

    # Scan brands dir for first with Meta enabled
    if BRANDS_DIR.is_dir():
        for brand_dir in sorted(BRANDS_DIR.iterdir()):
            if not brand_dir.is_dir():
                continue
            brand_yaml = brand_dir / "brand.yaml"
            if brand_yaml.is_file():
                try:
                    with open(brand_yaml, "r") as f:
                        content = f.read()
                    if "meta" in content and "enabled: true" in content:
                        logger.debug("Auto-detected brand: %s", brand_dir.name)
                        return brand_dir.name
                except Exception:
                    pass

    raise CredentialError(
        "No brand specified.\n"
        "  Use --brand <name>, set META_DEFAULT_BRAND env,\n"
        "  or add meta.enabled: true to a brand.yaml."
    )


# ---------------------------------------------------------------------------
# Instagram Graph API Client
# ---------------------------------------------------------------------------

class InstagramGraphClient:
    """Official Instagram Graph API client for intelligence/research.

    Provides read-only intelligence methods:
      - Business Discovery (competitor profiling)
      - Hashtag search + top/recent media
      - Own account info, insights, media, mentions
      - Token validation

    Does NOT include publishing methods (those live in meta-api.py).
    """

    def __init__(self, access_token: str, ig_user_id: str,
                 app_id: str = "", app_secret: str = "",
                 dry_run: bool = False):
        self.access_token = access_token
        self.ig_user_id = ig_user_id
        self.app_id = app_id
        self.app_secret = app_secret
        self.dry_run = dry_run
        self._last_request_time: float = 0.0

    # -------------------------------------------------------------------
    # HTTP layer
    # -------------------------------------------------------------------

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Make an authenticated request to the Graph API."""
        url = f"{GRAPH_API_BASE}{endpoint}"

        all_params = dict(params or {})
        all_params["access_token"] = self.access_token

        for attempt in range(max_retries):
            # Rate limiting
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < MIN_REQUEST_INTERVAL:
                time.sleep(MIN_REQUEST_INTERVAL - elapsed)

            if self.dry_run and method.upper() in ("POST", "PUT", "DELETE"):
                logger.info(
                    "[DRY RUN] %s %s params=%s body=%s",
                    method.upper(), endpoint,
                    json.dumps(params, indent=2) if params else "null",
                    json.dumps(body, indent=2) if body else "null",
                )
                return {"dry_run": True, "method": method, "endpoint": endpoint}

            query = urllib.parse.urlencode(all_params)
            full_url = f"{url}?{query}"

            headers = {}
            data_bytes = None

            if body and method.upper() in ("POST", "PUT"):
                form_encoded = urllib.parse.urlencode(body).encode("utf-8")
                data_bytes = form_encoded
                headers["Content-Type"] = "application/x-www-form-urlencoded"

            req = urllib.request.Request(
                full_url, data=data_bytes,
                headers=headers, method=method.upper(),
            )

            logger.debug(
                "%s %s", method.upper(),
                full_url.replace(self.access_token, "***"),
            )

            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    self._last_request_time = time.time()
                    resp_body = resp.read().decode("utf-8")
                    result = json.loads(resp_body) if resp_body else {}

                if "error" in result:
                    self._raise_api_error(result["error"])

                return result

            except urllib.error.HTTPError as e:
                self._last_request_time = time.time()
                status = e.code
                try:
                    err_body = e.read().decode("utf-8")
                    err_json = json.loads(err_body)
                except Exception:
                    err_json = {}

                error_data = err_json.get("error", {})

                # Rate limited
                if status == 429 or error_data.get("code") == 4:
                    backoff = min(2 ** (attempt + 1), 120)
                    logger.warning(
                        "Rate limited, backing off %ds (attempt %d/%d)",
                        backoff, attempt + 1, max_retries,
                    )
                    time.sleep(backoff)
                    continue

                # Token expired
                if error_data.get("code") == 190:
                    raise TokenExpiredError(
                        error_data.get("message", "Access token expired")
                    )

                # Server errors — retry
                if status >= 500:
                    backoff = min(2 ** attempt, 30)
                    logger.warning(
                        "%d Server error, retrying in %ds (attempt %d/%d)",
                        status, backoff, attempt + 1, max_retries,
                    )
                    time.sleep(backoff)
                    continue

                self._raise_api_error(
                    error_data or {"message": str(e), "code": status}
                )

            except urllib.error.URLError as e:
                logger.error("Network error: %s", e)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise APIError(f"Network error: {e}")

        raise APIError(
            f"Max retries ({max_retries}) exhausted for {method} {endpoint}"
        )

    @staticmethod
    def _raise_api_error(error: Dict[str, Any]) -> None:
        """Raise appropriate exception from API error response."""
        message = error.get("message", "Unknown API error")
        code = error.get("code", 0)
        subcode = error.get("error_subcode", 0)
        error_type = error.get("type", "")
        fbtrace_id = error.get("fbtrace_id", "")

        if code == 190:
            raise TokenExpiredError(message)
        if code == 4 or code == 32:
            raise RateLimitError(message)
        if code == 200 or code == 10:
            raise AuthError(f"Permission error: {message}")

        raise APIError(
            message, code=code, subcode=subcode,
            error_type=error_type, fbtrace_id=fbtrace_id,
        )

    # -------------------------------------------------------------------
    # Auto-discovery
    # -------------------------------------------------------------------

    def discover_ig_user_id(self) -> str:
        """Auto-discover Instagram Business Account ID from /me/accounts.

        Iterates connected Facebook Pages and finds the first one with
        an instagram_business_account edge. Returns the IG user ID.
        """
        logger.debug("Auto-discovering Instagram Business Account ID...")
        result = self._request(
            "GET", "/me/accounts",
            params={"fields": "id,name,instagram_business_account"},
        )
        for page in result.get("data", []):
            ig_account = page.get("instagram_business_account", {})
            if ig_account.get("id"):
                ig_id = ig_account["id"]
                logger.debug(
                    "Found Instagram Business Account: %s (from page %s)",
                    ig_id, page.get("name"),
                )
                return ig_id
        return ""

    # -------------------------------------------------------------------
    # Token validation
    # -------------------------------------------------------------------

    def debug_token(self) -> TokenInfo:
        """Validate the access token and return debug info.

        Uses the app token (app_id|app_secret) to inspect the user token.
        Falls back to self-inspection if app credentials are unavailable.
        """
        if self.app_id and self.app_secret:
            # Use app token for inspection (more reliable)
            app_token = f"{self.app_id}|{self.app_secret}"
            params = {
                "input_token": self.access_token,
                "access_token": app_token,
            }
            url = f"{GRAPH_API_BASE}/debug_token?{urllib.parse.urlencode(params)}"
        else:
            # Self-inspect
            params = {
                "input_token": self.access_token,
                "access_token": self.access_token,
            }
            url = f"{GRAPH_API_BASE}/debug_token?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            raise APIError(f"Token debug failed: {e}")

        data = result.get("data", {})
        return TokenInfo(
            app_id=str(data.get("app_id", "")),
            user_id=str(data.get("user_id", "")),
            type=data.get("type", ""),
            expires_at=data.get("expires_at", 0),
            is_valid=data.get("is_valid", False),
            scopes=data.get("scopes", []),
            granular_scopes=data.get("granular_scopes", []),
        )

    # -------------------------------------------------------------------
    # Own account
    # -------------------------------------------------------------------

    def get_account_info(self) -> AccountInfo:
        """Get connected Instagram Business Account info."""
        fields = (
            "id,name,username,followers_count,follows_count,"
            "media_count,profile_picture_url,biography,website"
        )
        result = self._request(
            "GET", f"/{self.ig_user_id}", params={"fields": fields},
        )
        return AccountInfo(
            account_id=result.get("id", self.ig_user_id),
            name=result.get("name", ""),
            username=result.get("username", ""),
            followers_count=result.get("followers_count", 0),
            following_count=result.get("follows_count", 0),
            media_count=result.get("media_count", 0),
            profile_picture_url=result.get("profile_picture_url", ""),
            biography=result.get("biography", ""),
            website=result.get("website", ""),
        )

    def get_media_list(self, limit: int = 25) -> List[MediaItem]:
        """List recent media from the connected account."""
        fields = (
            "id,media_type,caption,permalink,timestamp,"
            "like_count,comments_count,thumbnail_url,media_url"
        )
        result = self._request(
            "GET", f"/{self.ig_user_id}/media",
            params={"fields": fields, "limit": str(limit)},
        )
        items = []
        for m in result.get("data", []):
            items.append(MediaItem(
                media_id=m.get("id", ""),
                media_type=m.get("media_type", ""),
                caption=m.get("caption", ""),
                permalink=m.get("permalink", ""),
                timestamp=m.get("timestamp", ""),
                like_count=m.get("like_count", 0),
                comments_count=m.get("comments_count", 0),
                thumbnail_url=m.get("thumbnail_url", ""),
                media_url=m.get("media_url", ""),
            ))
        return items

    # -------------------------------------------------------------------
    # Account insights
    # -------------------------------------------------------------------

    def get_account_insights(
        self, metrics: List[str], period: str = "day",
        since: str = "", until: str = "",
        metric_type: str = "",
    ) -> List[InsightMetric]:
        """Get account-level insights.

        Args:
            metrics: Metric names (e.g., reach, follower_count).
            period: day, week, days_28, month, lifetime.
            since/until: Date boundaries (Unix timestamp or ISO 8601).
            metric_type: "total_value" for aggregate metrics (v24.0+).
        """
        params: Dict[str, str] = {
            "metric": ",".join(metrics),
            "period": period,
        }
        if metric_type:
            params["metric_type"] = metric_type
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        result = self._request(
            "GET", f"/{self.ig_user_id}/insights", params=params,
        )
        insights = []
        for item in result.get("data", []):
            # v24.0 returns total_value as a dict with "value" key
            values = item.get("values", [])
            total_value = item.get("total_value", {})
            if total_value and not values:
                values = [{"value": total_value.get("value", 0)}]
            insights.append(InsightMetric(
                name=item.get("name", ""),
                period=item.get("period", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                values=values,
            ))
        return insights

    def get_media_insights(
        self, media_id: str, metrics: Optional[List[str]] = None,
    ) -> List[InsightMetric]:
        """Get insights for a specific media item.

        Default metrics: impressions, reach, engagement, saved.
        """
        if metrics is None:
            metrics = ["impressions", "reach", "engagement", "saved"]

        params = {"metric": ",".join(metrics)}
        result = self._request(
            "GET", f"/{media_id}/insights", params=params,
        )
        insights = []
        for item in result.get("data", []):
            insights.append(InsightMetric(
                name=item.get("name", ""),
                period=item.get("period", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                values=item.get("values", []),
            ))
        return insights

    # -------------------------------------------------------------------
    # Business Discovery (competitor intelligence)
    # -------------------------------------------------------------------

    def business_discovery(
        self, username: str, media_limit: int = 25,
    ) -> Dict[str, Any]:
        """Query any public Business/Creator account via Business Discovery.

        This is the key intelligence endpoint -- retrieves profile info and
        recent media for any public IG Business or Creator account without
        them knowing.

        NOTE: The username is embedded in the fields parameter using dot
        notation: business_discovery.fields(...).username(target_user)
        This is NOT a separate query parameter.

        Args:
            username: Target Instagram username (without @).
            media_limit: Number of recent media items to fetch.

        Raises:
            ValueError: If username contains invalid characters.

        Returns:
            Raw dict with profile + media data.
        """
        username = username.lstrip("@")
        if not _VALID_USERNAME_RE.match(username):
            raise ValueError(
                f"Invalid Instagram username: {username!r}. "
                "Usernames must be 1-30 chars: letters, digits, periods, underscores."
            )
        media_fields = (
            "id,caption,media_type,like_count,comments_count,"
            "timestamp,permalink,media_url,thumbnail_url"
        )
        fields = (
            f"business_discovery.fields("
            f"username,name,ig_id,media_count,followers_count,"
            f"biography,profile_picture_url,website,"
            f"media.limit({media_limit}){{{media_fields}}}"
            f").username({username})"
        )
        result = self._request(
            "GET", f"/{self.ig_user_id}",
            params={"fields": fields},
        )
        return result.get("business_discovery", {})

    def get_competitor_profile(self, username: str) -> CompetitorProfile:
        """Get competitor profile info (no media)."""
        username = username.lstrip("@")
        if not _VALID_USERNAME_RE.match(username):
            raise ValueError(
                f"Invalid Instagram username: {username!r}. "
                "Usernames must be 1-30 chars: letters, digits, periods, underscores."
            )
        fields = (
            "business_discovery.fields("
            "username,name,ig_id,media_count,followers_count,"
            "biography,profile_picture_url,website"
            f").username({username})"
        )
        result = self._request(
            "GET", f"/{self.ig_user_id}",
            params={"fields": fields},
        )
        bd = result.get("business_discovery", {})
        return CompetitorProfile(
            username=bd.get("username", username),
            name=bd.get("name", ""),
            ig_id=str(bd.get("ig_id", "")),
            biography=bd.get("biography", ""),
            followers_count=bd.get("followers_count", 0),
            media_count=bd.get("media_count", 0),
            profile_picture_url=bd.get("profile_picture_url", ""),
            website=bd.get("website", ""),
        )

    def get_competitor_media(
        self, username: str, limit: int = 25,
    ) -> List[MediaItem]:
        """Get recent media for a competitor via Business Discovery."""
        raw = self.business_discovery(username, media_limit=limit)
        media_data = raw.get("media", {}).get("data", [])
        items = []
        for m in media_data:
            items.append(MediaItem(
                media_id=m.get("id", ""),
                media_type=m.get("media_type", ""),
                caption=m.get("caption", ""),
                permalink=m.get("permalink", ""),
                timestamp=m.get("timestamp", ""),
                like_count=m.get("like_count", 0),
                comments_count=m.get("comments_count", 0),
                thumbnail_url=m.get("thumbnail_url", ""),
                media_url=m.get("media_url", ""),
                username=raw.get("username", username),
            ))
        return items

    def compute_engagement_rate(
        self, username: str, media_limit: int = 25,
    ) -> EngagementReport:
        """Compute engagement rate from Business Discovery data.

        Formula: ((avg_likes + avg_comments) / followers_count) * 100
        """
        raw = self.business_discovery(username, media_limit=media_limit)
        followers = raw.get("followers_count", 0)
        media_data = raw.get("media", {}).get("data", [])

        if not media_data:
            return EngagementReport(
                username=raw.get("username", username),
                followers_count=followers,
                media_count=raw.get("media_count", 0),
            )

        total_likes = sum(m.get("like_count", 0) for m in media_data)
        total_comments = sum(m.get("comments_count", 0) for m in media_data)
        count = len(media_data)

        avg_likes = total_likes / count if count else 0
        avg_comments = total_comments / count if count else 0
        rate = ((avg_likes + avg_comments) / followers * 100) if followers > 0 else 0

        return EngagementReport(
            username=raw.get("username", username),
            followers_count=followers,
            media_count=raw.get("media_count", 0),
            avg_likes=round(avg_likes, 1),
            avg_comments=round(avg_comments, 1),
            engagement_rate=round(rate, 3),
            media_analyzed=count,
        )

    # -------------------------------------------------------------------
    # Hashtag search + media
    # -------------------------------------------------------------------

    def hashtag_search(self, hashtag: str) -> str:
        """Search for a hashtag ID by name.

        NOTE: The Graph API allows only 30 unique hashtags per 7-day
        rolling window. Each call to this endpoint with a new hashtag
        counts against that quota.

        Returns: hashtag_id string.
        """
        result = self._request(
            "GET", "/ig_hashtag_search",
            params={"q": hashtag.lstrip("#"), "user_id": self.ig_user_id},
        )
        data = result.get("data", [])
        if not data:
            return ""
        return str(data[0].get("id", ""))

    def hashtag_top_media(
        self, hashtag_id: str, limit: int = 25,
    ) -> List[MediaItem]:
        """Get top media for a hashtag by ID."""
        fields = (
            "id,caption,media_type,like_count,comments_count,"
            "timestamp,permalink"
        )
        result = self._request(
            "GET", f"/{hashtag_id}/top_media",
            params={
                "user_id": self.ig_user_id,
                "fields": fields,
                "limit": str(min(limit, 50)),  # API max is 50
            },
        )
        items = []
        for m in result.get("data", []):
            items.append(MediaItem(
                media_id=m.get("id", ""),
                media_type=m.get("media_type", ""),
                caption=m.get("caption", ""),
                permalink=m.get("permalink", ""),
                timestamp=m.get("timestamp", ""),
                like_count=m.get("like_count", 0),
                comments_count=m.get("comments_count", 0),
            ))
        return items

    def hashtag_recent_media(
        self, hashtag_id: str, limit: int = 25,
    ) -> List[MediaItem]:
        """Get recent media for a hashtag by ID."""
        fields = (
            "id,caption,media_type,like_count,comments_count,"
            "timestamp,permalink"
        )
        result = self._request(
            "GET", f"/{hashtag_id}/recent_media",
            params={
                "user_id": self.ig_user_id,
                "fields": fields,
                "limit": str(min(limit, 50)),
            },
        )
        items = []
        for m in result.get("data", []):
            items.append(MediaItem(
                media_id=m.get("id", ""),
                media_type=m.get("media_type", ""),
                caption=m.get("caption", ""),
                permalink=m.get("permalink", ""),
                timestamp=m.get("timestamp", ""),
                like_count=m.get("like_count", 0),
                comments_count=m.get("comments_count", 0),
            ))
        return items

    # -------------------------------------------------------------------
    # Mentions
    # -------------------------------------------------------------------

    def get_mentions(self, limit: int = 25) -> List[MentionItem]:
        """Get media where the account is @mentioned."""
        fields = "id,caption,media_type,timestamp,permalink,username"
        result = self._request(
            "GET", f"/{self.ig_user_id}/tags",
            params={"fields": fields, "limit": str(limit)},
        )
        items = []
        for m in result.get("data", []):
            items.append(MentionItem(
                media_id=m.get("id", ""),
                caption=m.get("caption", ""),
                media_type=m.get("media_type", ""),
                timestamp=m.get("timestamp", ""),
                permalink=m.get("permalink", ""),
                username=m.get("username", ""),
            ))
        return items

    # -------------------------------------------------------------------
    # Comments
    # -------------------------------------------------------------------

    def get_comments(
        self, media_id: str, limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Get comments on a media item."""
        result = self._request(
            "GET", f"/{media_id}/comments",
            params={
                "fields": "id,text,username,timestamp,like_count",
                "limit": str(limit),
            },
        )
        return result.get("data", [])
