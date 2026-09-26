"""
YouTube API client for YouTube Intel.

Reuses the same Keychain credential pattern and OAuth2 flow from
capsules/example-digital-capsule/tools/youtube-api.py — same service names,
same token refresh logic, zero duplicate credential stores.

Dependencies: None (stdlib only)
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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — must match youtube-api.py exactly
# ---------------------------------------------------------------------------

# Keychain service names — OAuth (for Analytics API)
KC_CLIENT_ID = "google-oauth-client-id"
KC_CLIENT_SECRET = "google-oauth-client-secret"
KC_REFRESH_TOKEN = "google-youtube-refresh-token"
KC_ACCESS_TOKEN = "google-youtube-access-token"
KC_TOKEN_EXPIRY = "google-youtube-token-expiry"

# Keychain service names — Service Account (for Data API)
KC_SA_EMAIL = "google-service-account-client-email"
KC_SA_PRIVATE_KEY = "google-service-account-private-key"
KC_SA_TOKEN = "google-service-account-access-token"
KC_SA_TOKEN_EXPIRY = "google-service-account-token-expiry"

# Google OAuth endpoints
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_TOKEN_INFO_URI = "https://oauth2.googleapis.com/tokeninfo"

# YouTube Data API scopes for service account
SA_SCOPES = "https://www.googleapis.com/auth/youtube.readonly"

# YouTube API
YOUTUBE_BASE_URL = "https://www.googleapis.com/youtube/v3"
YOUTUBE_ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2"

# ---------------------------------------------------------------------------
# Terminal colours
# ---------------------------------------------------------------------------
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class YouTubeIntelError(Exception):
    """Base exception."""


class CredentialError(YouTubeIntelError):
    """Missing or invalid credentials."""


class AuthError(YouTubeIntelError):
    """Authentication failure."""


class APIError(YouTubeIntelError):
    """YouTube API returned an error."""

    def __init__(self, message: str, code: int = 0, reason: str = ""):
        self.code = code
        self.reason = reason
        super().__init__(message)


# ---------------------------------------------------------------------------
# Keychain helpers — identical to youtube-api.py
# ---------------------------------------------------------------------------

def _keychain_read(service: str) -> Optional[str]:
    """Read a password from macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _keychain_write(service: str, account: str, password: str) -> bool:
    """Write or update a password in macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "add-generic-password",
             "-s", service, "-a", account, "-w", password, "-U"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# ---------------------------------------------------------------------------
# Auth — reuses tokens from youtube-api.py
# ---------------------------------------------------------------------------

def _get_client_credentials() -> Tuple[str, str]:
    """Load OAuth client ID and secret from Keychain or env."""
    client_id = (
        _keychain_read(KC_CLIENT_ID)
        or os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    )
    client_secret = (
        _keychain_read(KC_CLIENT_SECRET)
        or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    )
    if not client_id or not client_secret:
        raise CredentialError(
            "Missing OAuth credentials.\n"
            f"  Checked Keychain: '{KC_CLIENT_ID}', '{KC_CLIENT_SECRET}'\n"
            "  Run 'youtube-api.py auth login' first to set up credentials."
        )
    return client_id, client_secret


def _refresh_access_token(refresh_token: str) -> str:
    """Use refresh token to get a new access token."""
    client_id, client_secret = _get_client_credentials()
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()

    req = urllib.request.Request(GOOGLE_TOKEN_URI, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise AuthError(
            f"Failed to refresh access token (HTTP {e.code}).\n"
            "  Run 'youtube-api.py auth login' to re-authorize."
        )
    except Exception as e:
        raise AuthError(f"Token refresh network error: {e}")

    access_token = result.get("access_token")
    if not access_token:
        raise AuthError("Token refresh response missing access_token.")

    _keychain_write(KC_ACCESS_TOKEN, "huxley", access_token)
    expires_in = int(result.get("expires_in", 3600))
    _keychain_write(KC_TOKEN_EXPIRY, "huxley", str(time.time() + expires_in))

    return access_token


def get_access_token() -> str:
    """
    Get a valid access token, refreshing if expired.

    Checks local expiry cache first (no network call), then refreshes.
    Shares the same Keychain tokens as youtube-api.py.
    """
    access_token = _keychain_read(KC_ACCESS_TOKEN)
    if access_token:
        expiry_str = _keychain_read(KC_TOKEN_EXPIRY)
        if expiry_str:
            try:
                if time.time() < float(expiry_str) - 60:
                    return access_token
            except (ValueError, TypeError):
                pass

    # Need refresh
    refresh_token = _keychain_read(KC_REFRESH_TOKEN)
    if not refresh_token:
        raise AuthError(
            "No refresh token found.\n"
            "  Run 'youtube-api.py auth login' first."
        )
    return _refresh_access_token(refresh_token)


# ---------------------------------------------------------------------------
# Service Account JWT Auth (for Data API — no browser login required)
# ---------------------------------------------------------------------------

def _create_service_account_jwt() -> str:
    """Create a signed JWT for Google Service Account authentication.

    Uses openssl (ships with macOS) to sign the JWT with RS256.
    """
    import base64
    import tempfile

    sa_email_raw = _keychain_read(KC_SA_EMAIL)
    sa_private_key_raw = _keychain_read(KC_SA_PRIVATE_KEY)

    if not sa_email_raw or not sa_private_key_raw:
        raise CredentialError("Service account credentials not found in Keychain.")

    # Keychain values may be hex-encoded — detect and decode
    def _maybe_hex_decode(val: str) -> str:
        """Decode hex-encoded Keychain values to their original string."""
        try:
            decoded = bytes.fromhex(val).decode("utf-8")
            # Sanity check: if it decodes to printable text, it was hex
            if decoded.isprintable() or "\n" in decoded:
                return decoded
        except (ValueError, UnicodeDecodeError):
            pass
        return val

    sa_email = _maybe_hex_decode(sa_email_raw)
    sa_private_key = _maybe_hex_decode(sa_private_key_raw)

    # JWT Header
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    # JWT Claims
    now = int(time.time())
    claims = base64.urlsafe_b64encode(json.dumps({
        "iss": sa_email,
        "scope": SA_SCOPES,
        "aud": GOOGLE_TOKEN_URI,
        "iat": now,
        "exp": now + 3600,
    }).encode()).rstrip(b"=").decode()

    unsigned = f"{header}.{claims}"

    # Sign with openssl via subprocess (macOS ships with LibreSSL)
    fd, key_path = tempfile.mkstemp(suffix=".pem")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(sa_private_key)

        result = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", key_path],
            input=unsigned.encode(),
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise AuthError(f"JWT signing failed: {result.stderr.decode()}")

        signature = base64.urlsafe_b64encode(result.stdout).rstrip(b"=").decode()
    finally:
        os.unlink(key_path)

    return f"{unsigned}.{signature}"


def get_service_account_token() -> str:
    """Get a valid service account access token, refreshing via JWT if expired.

    This is fully programmatic — no browser login needed.
    """
    # Check cached token
    cached_token = _keychain_read(KC_SA_TOKEN)
    if cached_token:
        expiry_str = _keychain_read(KC_SA_TOKEN_EXPIRY)
        if expiry_str:
            try:
                if time.time() < float(expiry_str) - 60:
                    return cached_token
            except (ValueError, TypeError):
                pass

    # Exchange JWT for access token
    jwt_token = _create_service_account_jwt()
    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token,
    }).encode()

    req = urllib.request.Request(GOOGLE_TOKEN_URI, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise AuthError(f"Service account token exchange failed (HTTP {e.code}).")
    except Exception as e:
        raise AuthError(f"Service account token exchange error: {e}")

    access_token = result.get("access_token")
    if not access_token:
        raise AuthError("Service account token response missing access_token.")

    # Cache the token
    expires_in = int(result.get("expires_in", 3600))
    _keychain_write(KC_SA_TOKEN, "huxley", access_token)
    _keychain_write(KC_SA_TOKEN_EXPIRY, "huxley", str(time.time() + expires_in))

    return access_token


# ---------------------------------------------------------------------------
# YouTube API Client
# ---------------------------------------------------------------------------

class YouTubeIntelClient:
    """
    Lightweight YouTube Data API v3 + Analytics API client.

    Dual auth:
      - Service Account (JWT) for Data API — fully programmatic, no browser
      - OAuth 2.0 for Analytics API — requires one-time browser login

    Most commands work with just the service account. Analytics-dependent
    commands (audit, besttime) need OAuth.
    """

    def __init__(self, access_token: Optional[str] = None):
        self._oauth_token: Optional[str] = None
        self._sa_token: Optional[str] = None
        self._last_request_time: float = 0.0

        if access_token:
            # Explicit token provided — use for everything
            self._sa_token = access_token
            self._oauth_token = access_token
        else:
            # Try service account first (always available)
            try:
                self._sa_token = get_service_account_token()
            except (CredentialError, AuthError) as e:
                logger.debug("Service account unavailable: %s", e)

            # Try OAuth (may not be set up yet)
            try:
                self._oauth_token = get_access_token()
            except (CredentialError, AuthError) as e:
                logger.debug("OAuth unavailable: %s", e)

            if not self._sa_token and not self._oauth_token:
                raise CredentialError(
                    "No credentials available.\n"
                    "  Service account: check Keychain entries 'google-service-account-*'\n"
                    "  OAuth: run 'youtube-api.py auth login'"
                )

        # Primary token for Data API (prefer service account)
        self.access_token = self._sa_token or self._oauth_token

    @property
    def has_oauth(self) -> bool:
        """Whether OAuth credentials are available (needed for Analytics API)."""
        return self._oauth_token is not None

    @property
    def analytics_token(self) -> str:
        """Get OAuth token for Analytics API, raising if unavailable."""
        if not self._oauth_token:
            raise AuthError(
                "Analytics API requires OAuth authentication.\n"
                "  Run 'youtube-api.py auth login' to authorize.\n"
                "  (Most other commands work without it.)"
            )
        return self._oauth_token

    def _request(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Make an authenticated GET request to the YouTube API."""
        # Minimal politeness delay
        elapsed = time.time() - self._last_request_time
        if elapsed < 0.1:
            time.sleep(0.1 - elapsed)
        self._last_request_time = time.time()

        if params:
            query = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None and v != ""}
            )
            url = f"{url}?{query}" if "?" not in url else f"{url}&{query}"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

        last_error = None
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, method="GET", headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = resp.read().decode()
                    return json.loads(body) if body else {}

            except urllib.error.HTTPError as e:
                error_body = e.read().decode()
                logger.debug("HTTP %d: %s", e.code, error_body)

                if e.code == 401:
                    # Try refreshing the correct token type
                    if attempt == 0:
                        try:
                            if self.access_token == self._sa_token:
                                self._sa_token = get_service_account_token()
                                self.access_token = self._sa_token
                            else:
                                self._oauth_token = get_access_token()
                                self.access_token = self._oauth_token
                            continue
                        except (AuthError, CredentialError):
                            pass
                    raise AuthError(
                        "Access token expired and refresh failed."
                    )

                if e.code == 403:
                    try:
                        err_data = json.loads(error_body)
                        reason = (
                            err_data.get("error", {})
                            .get("errors", [{}])[0]
                            .get("reason", "")
                        )
                    except (json.JSONDecodeError, IndexError, KeyError):
                        reason = ""
                    if reason in ("quotaExceeded", "rateLimitExceeded"):
                        raise APIError(
                            "YouTube API quota exceeded. Wait and retry.",
                            code=403,
                            reason=reason,
                        )

                if e.code in (500, 502, 503) and attempt < max_retries - 1:
                    time.sleep(2 ** attempt + 0.5)
                    last_error = e
                    continue

                try:
                    err_msg = json.loads(error_body).get("error", {}).get("message", error_body)
                except (json.JSONDecodeError, KeyError):
                    err_msg = error_body
                raise APIError(err_msg, code=e.code)

            except urllib.error.URLError as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    last_error = e
                    continue
                raise YouTubeIntelError(f"Network error: {e.reason}")

        raise YouTubeIntelError(f"All {max_retries} retries failed: {last_error}")

    # --- Channel ---

    def get_channel(
        self, channel_id: Optional[str] = None, handle: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get channel info by ID, handle, or 'mine'.
        Returns raw API item dict.
        """
        params: Dict[str, str] = {
            "part": "snippet,statistics,contentDetails,brandingSettings",
        }
        if channel_id:
            params["id"] = channel_id
        elif handle:
            # forHandle works for @handles
            params["forHandle"] = handle.lstrip("@")
        else:
            params["mine"] = "true"

        data = self._request(f"{YOUTUBE_BASE_URL}/channels", params=params)
        items = data.get("items", [])
        if not items:
            raise APIError("Channel not found.", code=404)
        return items[0]

    def resolve_channel_id(self, identifier: str) -> Tuple[str, str]:
        """
        Resolve a channel identifier (URL, handle, or ID) to (channel_id, channel_name).
        """
        identifier = identifier.strip()

        # URL patterns
        url_patterns = [
            r"(?:https?://)?(?:www\.)?youtube\.com/channel/([A-Za-z0-9_-]+)",
            r"(?:https?://)?(?:www\.)?youtube\.com/@([A-Za-z0-9_.-]+)",
            r"(?:https?://)?(?:www\.)?youtube\.com/c/([A-Za-z0-9_.-]+)",
        ]

        for pattern in url_patterns:
            match = re.match(pattern, identifier)
            if match:
                value = match.group(1)
                if "/channel/" in identifier:
                    ch = self.get_channel(channel_id=value)
                else:
                    ch = self.get_channel(handle=value)
                return ch["id"], ch["snippet"]["title"]

        # @handle
        if identifier.startswith("@"):
            ch = self.get_channel(handle=identifier)
            return ch["id"], ch["snippet"]["title"]

        # Bare channel ID (starts with UC)
        if identifier.startswith("UC") and len(identifier) == 24:
            ch = self.get_channel(channel_id=identifier)
            return ch["id"], ch["snippet"]["title"]

        # Try as handle fallback
        try:
            ch = self.get_channel(handle=identifier)
            return ch["id"], ch["snippet"]["title"]
        except APIError:
            pass

        # Try as channel ID fallback
        try:
            ch = self.get_channel(channel_id=identifier)
            return ch["id"], ch["snippet"]["title"]
        except APIError:
            pass

        raise APIError(
            f"Could not resolve '{identifier}' to a YouTube channel.\n"
            "  Try: channel ID (UCxxxx), @handle, or full URL."
        )

    # --- Videos ---

    def get_video(self, video_id: str) -> Dict[str, Any]:
        """Get detailed info for a single video."""
        data = self._request(
            f"{YOUTUBE_BASE_URL}/videos",
            params={
                "part": "snippet,statistics,contentDetails,topicDetails,status",
                "id": video_id,
            },
        )
        items = data.get("items", [])
        if not items:
            raise APIError(f"Video '{video_id}' not found.", code=404)
        return items[0]

    def get_videos_batch(self, video_ids: List[str]) -> List[Dict[str, Any]]:
        """Get details for multiple videos (up to 50 per call)."""
        all_items = []
        # API supports max 50 IDs per request
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            data = self._request(
                f"{YOUTUBE_BASE_URL}/videos",
                params={
                    "part": "snippet,statistics,contentDetails",
                    "id": ",".join(batch),
                },
            )
            all_items.extend(data.get("items", []))
        return all_items

    def list_channel_videos(
        self,
        channel_id: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List videos from a channel (via uploads playlist).
        Returns video items with full statistics.
        """
        # Get uploads playlist
        ch_params: Dict[str, str] = {"part": "contentDetails"}
        if channel_id:
            ch_params["id"] = channel_id
        else:
            ch_params["mine"] = "true"

        ch_data = self._request(f"{YOUTUBE_BASE_URL}/channels", params=ch_params)
        ch_items = ch_data.get("items", [])
        if not ch_items:
            raise APIError("Channel not found.", code=404)

        uploads_id = (
            ch_items[0]
            .get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )
        if not uploads_id:
            return []

        # Fetch playlist items
        video_ids = []
        next_page = None
        while len(video_ids) < max_results:
            pl_params: Dict[str, str] = {
                "part": "snippet",
                "playlistId": uploads_id,
                "maxResults": str(min(max_results - len(video_ids), 50)),
            }
            if next_page:
                pl_params["pageToken"] = next_page

            pl_data = self._request(
                f"{YOUTUBE_BASE_URL}/playlistItems", params=pl_params
            )
            for item in pl_data.get("items", []):
                vid = item.get("snippet", {}).get("resourceId", {}).get("videoId")
                if vid:
                    video_ids.append(vid)

            next_page = pl_data.get("nextPageToken")
            if not next_page:
                break

        if not video_ids:
            return []

        # Get full video details
        return self.get_videos_batch(video_ids)

    def search_videos(
        self,
        query: str,
        max_results: int = 20,
        order: str = "relevance",
        channel_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search YouTube for videos.
        Returns video items with statistics.
        """
        params: Dict[str, str] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": str(min(max_results, 50)),
            "order": order,
        }
        if channel_id:
            params["channelId"] = channel_id

        data = self._request(f"{YOUTUBE_BASE_URL}/search", params=params)

        video_ids = []
        for item in data.get("items", []):
            vid = item.get("id", {}).get("videoId")
            if vid:
                video_ids.append(vid)

        if not video_ids:
            return []

        return self.get_videos_batch(video_ids)

    # --- Analytics (requires OAuth) ---

    def _analytics_request(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make an Analytics API request using the OAuth token."""
        # Temporarily swap to OAuth token for this request
        original_token = self.access_token
        self.access_token = self.analytics_token
        try:
            return self._request(url, params=params)
        finally:
            self.access_token = original_token

    def get_analytics_report(
        self,
        start_date: str,
        end_date: str,
        metrics: str = "views,estimatedMinutesWatched,subscribersGained,likes",
        dimensions: str = "",
        filters: str = "",
        sort: str = "",
        max_results: int = 200,
    ) -> Dict[str, Any]:
        """
        Query YouTube Analytics API (requires OAuth).

        Dates: YYYY-MM-DD format.
        Metrics: comma-separated (views, estimatedMinutesWatched, etc.)
        Dimensions: comma-separated (day, video, country, etc.)
        """
        params: Dict[str, str] = {
            "ids": "channel==MINE",
            "startDate": start_date,
            "endDate": end_date,
            "metrics": metrics,
        }
        if dimensions:
            params["dimensions"] = dimensions
        if filters:
            params["filters"] = filters
        if sort:
            params["sort"] = sort
        if max_results:
            params["maxResults"] = str(max_results)

        return self._analytics_request(
            f"{YOUTUBE_ANALYTICS_URL}/reports", params=params
        )

    def get_channel_analytics(
        self, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Get channel-level analytics for a date range."""
        return self.get_analytics_report(
            start_date=start_date,
            end_date=end_date,
            metrics="views,estimatedMinutesWatched,subscribersGained,subscribersLost,likes,dislikes,comments,shares,averageViewDuration,impressions,impressionClickThroughRate",
        )

    def get_daily_analytics(
        self, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Get day-by-day analytics."""
        return self.get_analytics_report(
            start_date=start_date,
            end_date=end_date,
            metrics="views,estimatedMinutesWatched,subscribersGained,likes",
            dimensions="day",
            sort="day",
        )

    def get_hourly_viewer_data(
        self, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Get viewer activity by day-of-week and hour for best-time analysis."""
        return self.get_analytics_report(
            start_date=start_date,
            end_date=end_date,
            metrics="views,estimatedMinutesWatched",
            dimensions="day",
            sort="day",
        )

    def get_top_videos_analytics(
        self, start_date: str, end_date: str, max_results: int = 50
    ) -> Dict[str, Any]:
        """Get top videos by views for a date range."""
        return self.get_analytics_report(
            start_date=start_date,
            end_date=end_date,
            metrics="views,estimatedMinutesWatched,likes,subscribersGained,averageViewDuration",
            dimensions="video",
            sort="-views",
            max_results=max_results,
        )


# ---------------------------------------------------------------------------
# YouTube Autocomplete (no auth needed)
# ---------------------------------------------------------------------------

def youtube_autocomplete(query: str) -> List[str]:
    """
    Get YouTube search autocomplete suggestions.

    Uses Google's suggest API (no auth, no quota).
    Returns a list of suggestion strings.
    """
    params = urllib.parse.urlencode({
        "client": "youtube",
        "ds": "yt",
        "q": query,
    })
    url = f"https://suggestqueries.google.com/complete/search?{params}"

    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("latin-1")

        # Response is JSONP: window.google.ac.h(["query", [...], ...])
        # Extract the JSON array inside the callback parentheses
        paren_start = raw.index("(")
        paren_end = raw.rindex(")")
        data = json.loads(raw[paren_start + 1 : paren_end])
        if len(data) >= 2 and isinstance(data[1], list):
            return [item[0] if isinstance(item, list) else str(item) for item in data[1]]
        return []
    except Exception as e:
        logger.debug("Autocomplete failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def extract_video_id(identifier: str) -> str:
    """
    Extract a video ID from a URL or return the identifier as-is.

    Handles:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://www.youtube.com/shorts/VIDEO_ID
      - Plain VIDEO_ID
    """
    identifier = identifier.strip()
    patterns = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([A-Za-z0-9_-]{11})",
        r"(?:https?://)?youtu\.be/([A-Za-z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, identifier)
        if match:
            return match.group(1)

    # Looks like a bare video ID (11 chars, alphanumeric + _ -)
    if re.match(r"^[A-Za-z0-9_-]{11}$", identifier):
        return identifier

    return identifier  # Pass through, let API decide


def format_count(n: int) -> str:
    """Format large numbers with K/M suffixes."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_duration(iso_duration: str) -> str:
    """Convert ISO 8601 duration (PT1H2M3S) to human-readable."""
    if not iso_duration:
        return ""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not match:
        return iso_duration
    h, m, s = match.groups()
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s:
        parts.append(f"{s}s")
    return " ".join(parts) if parts else "0s"


def visible_len(s: str) -> int:
    """Length of string excluding ANSI escape codes."""
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def format_table(
    headers: List[str], rows: List[List[str]], separator: str = "\u2502"
) -> str:
    """Format a table with box-drawing separators."""
    if not rows:
        return "  (no results)"

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], visible_len(str(cell)))

    def _pad(text: str, width: int) -> str:
        pad = width - visible_len(text)
        return text + " " * max(0, pad)

    header_parts = [_pad(h, col_widths[i]) for i, h in enumerate(headers)]
    header_line = f" {separator} ".join(header_parts)

    sep_parts = ["\u2500" * (w + 1) for w in col_widths]
    sep_line = f"\u2500{separator}\u2500".join(sep_parts)

    lines = [f"  {header_line}", f"  {sep_line}"]
    for row in rows:
        parts = []
        for i in range(len(headers)):
            cell = str(row[i] if i < len(row) else "")
            parts.append(_pad(cell, col_widths[i]))
        lines.append(f"  {f' {separator} '.join(parts)}")

    return "\n".join(lines)
