#!/usr/bin/env python3
"""
Meta Unified CLI for Huxley

Covers Instagram Graph API and Facebook Pages API for
multi-brand social media operations using personal access tokens.

Two API surfaces:
  - Instagram: Content publishing (images, videos, carousels, stories, reels),
               media management, insights, account info
  - Facebook:  Page posts (text, images, videos, links), page insights,
               page info, scheduled posts

Credentials:
    Per-brand credentials loaded from:
      1. capsules/ecommerce/brands/{brand}/.env
      2. capsules/ecommerce/.env
      3. Environment variables
      4. macOS Keychain

Dependencies: Python stdlib only (no pip packages).

Auth approach:
    Meta Graph API with User Access Tokens (personal tokens from Meta App Dashboard).
    No OAuth flow required - use long-lived tokens generated via the
    Access Token Debugger or token exchange endpoint.

Version: 0.1.0
"""

import argparse
import json
import logging
import mimetypes
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERSION = "0.1.0"
CATALYST_ROOT = Path(__file__).resolve().parent.parent
ECOMMERCE_DIR = CATALYST_ROOT / "capsules" / "ecommerce"
BRANDS_DIR = ECOMMERCE_DIR / "brands"

# Meta Graph API
GRAPH_API_VERSION = "v24.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
GRAPH_VIDEO_BASE = f"https://graph-video.facebook.com/{GRAPH_API_VERSION}"

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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class MetaError(Exception):
    """Base exception for all Meta API errors."""


class MetaCredentialError(MetaError):
    """Could not load credentials from env, .env, or Keychain."""


class MetaAuthError(MetaError):
    """Authentication or token error."""


class MetaAPIError(MetaError):
    """Meta Graph API returned an error."""

    def __init__(self, message: str, code: int = 0, subcode: int = 0,
                 error_type: str = "", fbtrace_id: str = ""):
        self.code = code
        self.subcode = subcode
        self.error_type = error_type
        self.fbtrace_id = fbtrace_id
        super().__init__(message)


class MetaRateLimitError(MetaError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: int = 0):
        self.retry_after = retry_after
        super().__init__(message)


class MetaTokenExpiredError(MetaAuthError):
    """Access token has expired and needs refresh."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AccountInfo:
    """Instagram Business Account or Facebook Page info."""
    account_id: str
    name: str
    username: str = ""
    followers_count: int = 0
    media_count: int = 0
    profile_picture_url: str = ""
    biography: str = ""
    website: str = ""


@dataclass
class MediaItem:
    """Instagram or Facebook media item."""
    media_id: str
    media_type: str
    caption: str = ""
    permalink: str = ""
    timestamp: str = ""
    like_count: int = 0
    comments_count: int = 0
    thumbnail_url: str = ""
    media_url: str = ""


@dataclass
class InsightMetric:
    """A single insight metric."""
    name: str
    period: str
    title: str = ""
    description: str = ""
    values: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PublishResult:
    """Result from a content publish operation."""
    post_id: str
    platform: str  # "instagram" or "facebook"
    status: str = "published"
    permalink: str = ""
    created_time: str = ""


@dataclass
class PageInfo:
    """Facebook Page info."""
    page_id: str
    name: str
    category: str = ""
    fan_count: int = 0
    link: str = ""
    verification_status: str = ""
    about: str = ""


@dataclass
class PagePost:
    """Facebook Page post."""
    post_id: str
    message: str = ""
    created_time: str = ""
    permalink_url: str = ""
    full_picture: str = ""
    shares_count: int = 0
    reactions_count: int = 0
    comments_count: int = 0


@dataclass
class TokenInfo:
    """Token debug info."""
    app_id: str = ""
    user_id: str = ""
    type: str = ""
    expires_at: int = 0
    is_valid: bool = False
    scopes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Display helpers (from tiktok.py pattern)
# ---------------------------------------------------------------------------

def _visible_len(s: str) -> int:
    """Length of string excluding ANSI escape codes."""
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def _format_table(headers: List[str], rows: List[List[str]], separator: str = "\u2502") -> str:
    """Format a table with box-drawing separators."""
    if not rows:
        return "  (no results)"

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], _visible_len(str(cell)))

    def _pad(text: str, width: int) -> str:
        pad = width - _visible_len(text)
        return text + " " * max(0, pad)

    header_parts = [_pad(h, col_widths[i]) for i, h in enumerate(headers)]
    header_line = f" {separator} ".join(header_parts)

    sep_parts = ["\u2500" * (w + 1) for w in col_widths]
    sep_line = f"\u2500{separator}\u2500".join(sep_parts)

    lines = [f" {header_line}", f" {sep_line}"]

    for row in rows:
        parts = []
        for i in range(len(headers)):
            cell = str(row[i] if i < len(row) else "")
            parts.append(_pad(cell, col_widths[i]))
        lines.append(f" {f' {separator} '.join(parts)}")

    return "\n".join(lines)


def _json_output(data: Any) -> None:
    """Print JSON-formatted output."""
    print(json.dumps(data, indent=2, default=str))


def _dc_to_dict(obj) -> dict:
    """Convert a dataclass to a dict for JSON output."""
    return asdict(obj)


def _truncate(s: str, max_len: int) -> str:
    """Truncate string with ellipsis if too long."""
    if _visible_len(s) <= max_len:
        return s
    return s[:max_len - 1] + "\u2026"


def _ts_to_str(ts: str) -> str:
    """Convert ISO 8601 timestamp to readable local time string."""
    if not ts:
        return ""
    try:
        # Handle ISO format: 2026-02-10T12:00:00+0000
        dt = datetime.fromisoformat(ts.replace("+0000", "+00:00").replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts


# ---------------------------------------------------------------------------
# Credential Loading (same pattern as tiktok.py)
# ---------------------------------------------------------------------------

class BrandCredentialLoader:
    """
    Multi-source credential loader for per-brand Meta credentials.

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
        """Load .env files into cache (brand-specific overrides capsule-level)."""
        if self._env_loaded:
            return
        self._env_loaded = True

        # Capsule .env (lower priority)
        capsule_env = ECOMMERCE_DIR / ".env"
        if capsule_env.is_file():
            self._parse_env(capsule_env)

        # Brand .env (higher priority, overwrites capsule)
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

    @staticmethod
    def keychain_write(service: str, account: str, password: str) -> bool:
        """Write or update a password in macOS Keychain."""
        try:
            result = subprocess.run(
                ["security", "add-generic-password",
                 "-s", service, "-a", account, "-w", password, "-U"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.debug("Keychain write failed for '%s': %s", service, e)
            return False

    def get(self, env_key: str, keychain_service: Optional[str] = None) -> Optional[str]:
        """
        Get a credential value from the resolution chain.

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
        """Get a credential or raise MetaCredentialError."""
        val = self.get(env_key, keychain_service)
        if not val:
            desc = label or env_key
            raise MetaCredentialError(
                f"Missing credential: {desc}\n"
                f"  Checked: .env files, ${env_key}, "
                f"{'Keychain ' + repr(keychain_service) if keychain_service else 'no Keychain service'}\n"
                f"  Brand: {self.brand}"
            )
        return val


def _resolve_brand(brand_arg: Optional[str]) -> str:
    """
    Resolve brand name from arg, env, or auto-detect.

    Priority:
      1. --brand flag
      2. META_DEFAULT_BRAND env
      3. First brand with meta.enabled: true in brand.yaml
    """
    if brand_arg:
        return brand_arg

    env_brand = os.environ.get("META_DEFAULT_BRAND", "").strip()
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
                    # Simple YAML check without PyYAML
                    if "meta" in content and "enabled: true" in content:
                        logger.debug("Auto-detected brand: %s", brand_dir.name)
                        return brand_dir.name
                except Exception:
                    pass

    raise MetaCredentialError(
        "No brand specified.\n"
        "  Use --brand <name>, set META_DEFAULT_BRAND env,\n"
        "  or add meta.enabled: true to a brand.yaml."
    )


# ---------------------------------------------------------------------------
# Meta Graph API Base Client
# ---------------------------------------------------------------------------

class MetaGraphClient:
    """
    Base REST client for Meta Graph API.

    Handles authentication, rate limiting, retries, and dry-run.
    All Instagram and Facebook API calls go through the Graph API.
    """

    MIN_REQUEST_INTERVAL = 0.3  # 200 calls/user/hour = ~3.3/s, conservative

    def __init__(self, access_token: str, dry_run: bool = False):
        self.access_token = access_token
        self.dry_run = dry_run
        self._last_request_time: float = 0.0

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Tuple[str, bytes, str]]] = None,
        use_video_host: bool = False,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the Graph API.

        Args:
            method: HTTP method (GET, POST, DELETE).
            endpoint: API endpoint path (e.g., /me/accounts).
            params: Query parameters.
            body: JSON body for POST requests.
            files: Multipart file uploads {field_name: (filename, data, mime_type)}.
            use_video_host: Use graph-video.facebook.com for video uploads.
            max_retries: Number of retries on transient errors.
        """
        base = GRAPH_VIDEO_BASE if use_video_host else GRAPH_API_BASE
        url = f"{base}{endpoint}"

        all_params = dict(params or {})
        all_params["access_token"] = self.access_token

        for attempt in range(max_retries):
            # Rate limiting
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.MIN_REQUEST_INTERVAL:
                time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)

            if self.dry_run and method.upper() in ("POST", "PUT", "DELETE"):
                logger.info("[DRY RUN] %s %s params=%s body=%s",
                            method.upper(), endpoint,
                            json.dumps(params, indent=2) if params else "null",
                            json.dumps(body, indent=2) if body else "null")
                return {"dry_run": True, "method": method, "endpoint": endpoint,
                        "id": "dry_run_placeholder"}

            if files:
                return self._multipart_request(method, url, all_params, body or {},
                                               files, max_retries, attempt)

            query = urllib.parse.urlencode(all_params)
            full_url = f"{url}?{query}"

            headers = {}
            data_bytes = None

            if body and method.upper() in ("POST", "PUT"):
                # For Graph API, POST params can be sent as form-urlencoded
                form_data = dict(body)
                form_encoded = urllib.parse.urlencode(form_data).encode("utf-8")
                data_bytes = form_encoded
                headers["Content-Type"] = "application/x-www-form-urlencoded"

            req = urllib.request.Request(full_url, data=data_bytes,
                                        headers=headers, method=method.upper())

            logger.debug("%s %s", method.upper(), full_url.replace(self.access_token, "***"))

            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    self._last_request_time = time.time()
                    resp_body = resp.read().decode("utf-8")
                    result = json.loads(resp_body) if resp_body else {}

                # Check for API-level errors
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
                    logger.warning("Rate limited, backing off %ds (attempt %d/%d)",
                                   backoff, attempt + 1, max_retries)
                    time.sleep(backoff)
                    continue

                # Token expired
                if error_data.get("code") == 190:
                    raise MetaTokenExpiredError(
                        error_data.get("message", "Access token expired"))

                # Server errors
                if status >= 500:
                    backoff = min(2 ** attempt, 30)
                    logger.warning("%d Server error, retrying in %ds (attempt %d/%d)",
                                   status, backoff, attempt + 1, max_retries)
                    time.sleep(backoff)
                    continue

                self._raise_api_error(error_data or {"message": str(e), "code": status})

            except urllib.error.URLError as e:
                logger.error("Network error: %s", e)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise MetaAPIError(f"Network error: {e}")

        raise MetaAPIError(f"Max retries ({max_retries}) exhausted for {method} {endpoint}")

    def _multipart_request(
        self,
        method: str,
        url: str,
        params: Dict[str, str],
        fields: Dict[str, Any],
        files: Dict[str, Tuple[str, bytes, str]],
        max_retries: int,
        attempt: int,
    ) -> Dict[str, Any]:
        """Handle multipart/form-data file uploads."""
        boundary = f"----MetaAPIBoundary{int(time.time() * 1000)}"
        body_parts: List[bytes] = []

        # Add access_token and other params as form fields
        for key, value in params.items():
            body_parts.append(f"--{boundary}\r\n".encode())
            body_parts.append(
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            body_parts.append(f"{value}\r\n".encode())

        # Add other body fields
        for key, value in fields.items():
            body_parts.append(f"--{boundary}\r\n".encode())
            body_parts.append(
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            body_parts.append(f"{value}\r\n".encode())

        # Add file fields
        for field_name, (filename, data, mime_type) in files.items():
            body_parts.append(f"--{boundary}\r\n".encode())
            body_parts.append(
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{filename}"\r\n'.encode())
            body_parts.append(f"Content-Type: {mime_type}\r\n\r\n".encode())
            body_parts.append(data)
            body_parts.append(b"\r\n")

        body_parts.append(f"--{boundary}--\r\n".encode())
        body_bytes = b"".join(body_parts)

        # Remove access_token from URL params since it's in the multipart body
        clean_url = url
        req = urllib.request.Request(
            clean_url,
            data=body_bytes,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method=method.upper(),
        )

        logger.debug("MULTIPART %s %s (%d bytes)", method.upper(), url, len(body_bytes))

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                self._last_request_time = time.time()
                resp_body = resp.read().decode("utf-8")
                result = json.loads(resp_body) if resp_body else {}

            if "error" in result:
                self._raise_api_error(result["error"])

            return result

        except urllib.error.HTTPError as e:
            self._last_request_time = time.time()
            try:
                err_body = e.read().decode("utf-8")
                err_json = json.loads(err_body)
            except Exception:
                err_json = {}
            error_data = err_json.get("error", {})
            self._raise_api_error(error_data or {"message": str(e), "code": e.code})
            return {}  # unreachable

    @staticmethod
    def _raise_api_error(error: Dict[str, Any]) -> None:
        """Raise appropriate exception from API error response."""
        message = error.get("message", "Unknown API error")
        code = error.get("code", 0)
        subcode = error.get("error_subcode", 0)
        error_type = error.get("type", "")
        fbtrace_id = error.get("fbtrace_id", "")

        if code == 190:
            raise MetaTokenExpiredError(message)
        if code == 4 or code == 32:
            raise MetaRateLimitError(message)
        if code == 200 or code == 10:
            raise MetaAuthError(f"Permission error: {message}")

        raise MetaAPIError(
            message, code=code, subcode=subcode,
            error_type=error_type, fbtrace_id=fbtrace_id
        )


# ---------------------------------------------------------------------------
# Instagram Graph API Client
# ---------------------------------------------------------------------------

class InstagramClient:
    """
    Client for Instagram Graph API.

    Supports content publishing (images, videos, carousels, stories, reels),
    media management, insights, and account information.

    Instagram content publishing uses a two-step process:
      1. Create a media container (POST /{ig-user-id}/media)
      2. Publish the container (POST /{ig-user-id}/media_publish)

    For videos and reels, there is an intermediate polling step to wait
    for the container to finish processing.
    """

    def __init__(self, graph: MetaGraphClient, ig_user_id: str):
        self.graph = graph
        self.ig_user_id = ig_user_id

    # --- Account Info ---

    def get_account_info(self) -> AccountInfo:
        """Get Instagram Business Account info."""
        fields = "id,name,username,followers_count,media_count,profile_picture_url,biography,website"
        result = self.graph._request("GET", f"/{self.ig_user_id}",
                                     params={"fields": fields})
        return AccountInfo(
            account_id=result.get("id", self.ig_user_id),
            name=result.get("name", ""),
            username=result.get("username", ""),
            followers_count=result.get("followers_count", 0),
            media_count=result.get("media_count", 0),
            profile_picture_url=result.get("profile_picture_url", ""),
            biography=result.get("biography", ""),
            website=result.get("website", ""),
        )

    # --- Media Listing ---

    def list_media(self, limit: int = 25) -> List[MediaItem]:
        """List recent media from the Instagram account."""
        fields = "id,media_type,caption,permalink,timestamp,like_count,comments_count,thumbnail_url,media_url"
        result = self.graph._request("GET", f"/{self.ig_user_id}/media",
                                     params={"fields": fields, "limit": str(limit)})
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

    def get_media(self, media_id: str) -> MediaItem:
        """Get details of a specific media item."""
        fields = "id,media_type,caption,permalink,timestamp,like_count,comments_count,thumbnail_url,media_url"
        result = self.graph._request("GET", f"/{media_id}",
                                     params={"fields": fields})
        return MediaItem(
            media_id=result.get("id", media_id),
            media_type=result.get("media_type", ""),
            caption=result.get("caption", ""),
            permalink=result.get("permalink", ""),
            timestamp=result.get("timestamp", ""),
            like_count=result.get("like_count", 0),
            comments_count=result.get("comments_count", 0),
            thumbnail_url=result.get("thumbnail_url", ""),
            media_url=result.get("media_url", ""),
        )

    # --- Content Publishing ---

    def _create_container(self, **kwargs) -> str:
        """Create a media container. Returns container ID."""
        result = self.graph._request("POST", f"/{self.ig_user_id}/media",
                                     body=kwargs)
        container_id = result.get("id", "")
        if not container_id and result.get("dry_run"):
            return "dry_run_container"
        return container_id

    def _publish_container(self, container_id: str) -> str:
        """Publish a media container. Returns media ID."""
        result = self.graph._request("POST", f"/{self.ig_user_id}/media_publish",
                                     body={"creation_id": container_id})
        media_id = result.get("id", "")
        if not media_id and result.get("dry_run"):
            return "dry_run_media"
        return media_id

    def _wait_for_container(self, container_id: str, timeout: int = 300,
                            poll_interval: int = 5) -> bool:
        """
        Poll container status until it's ready for publishing.
        Used for video/reel uploads that require server-side processing.
        Returns True when ready, raises MetaAPIError on failure.
        """
        if self.graph.dry_run:
            return True

        start = time.time()
        while time.time() - start < timeout:
            result = self.graph._request("GET", f"/{container_id}",
                                         params={"fields": "status_code,status"})
            status_code = result.get("status_code", "")

            if status_code == "FINISHED":
                return True
            elif status_code == "ERROR":
                error_msg = result.get("status", "Container processing failed")
                raise MetaAPIError(f"Media container error: {error_msg}")
            elif status_code == "EXPIRED":
                raise MetaAPIError("Media container expired before publishing")

            logger.debug("Container %s status: %s, waiting %ds...",
                         container_id, status_code, poll_interval)
            time.sleep(poll_interval)

        raise MetaAPIError(f"Container {container_id} processing timed out after {timeout}s")

    def publish_image(self, image_url: str, caption: str = "",
                      location_id: str = "") -> PublishResult:
        """
        Publish a single image to Instagram feed.

        Args:
            image_url: Public URL of the image (JPEG required, 8MB max).
            caption: Post caption (max 2200 chars, 30 hashtags).
            location_id: Optional Facebook Place ID for location tag.
        """
        params: Dict[str, Any] = {"image_url": image_url}
        if caption:
            params["caption"] = caption
        if location_id:
            params["location_id"] = location_id

        container_id = self._create_container(**params)
        media_id = self._publish_container(container_id)

        return PublishResult(
            post_id=media_id,
            platform="instagram",
            status="published",
        )

    def publish_video(self, video_url: str, caption: str = "",
                      thumb_offset: int = 0, location_id: str = "",
                      share_to_feed: bool = True) -> PublishResult:
        """
        Publish a video to Instagram feed.

        Args:
            video_url: Public URL of the video (MP4, H.264, max 100MB, max 60min).
            caption: Post caption.
            thumb_offset: Thumbnail offset in milliseconds.
            location_id: Optional Facebook Place ID.
            share_to_feed: Whether to share to feed (for reels).
        """
        params: Dict[str, Any] = {
            "video_url": video_url,
            "media_type": "VIDEO",
        }
        if caption:
            params["caption"] = caption
        if thumb_offset:
            params["thumb_offset"] = str(thumb_offset)
        if location_id:
            params["location_id"] = location_id

        container_id = self._create_container(**params)
        self._wait_for_container(container_id)
        media_id = self._publish_container(container_id)

        return PublishResult(
            post_id=media_id,
            platform="instagram",
            status="published",
        )

    def publish_reel(self, video_url: str, caption: str = "",
                     share_to_feed: bool = True,
                     thumb_offset: int = 0,
                     cover_url: str = "",
                     location_id: str = "") -> PublishResult:
        """
        Publish a Reel to Instagram.

        Args:
            video_url: Public URL of the video (MP4, 3-90s, 9:16 recommended).
            caption: Reel caption.
            share_to_feed: Also share to the regular feed.
            thumb_offset: Thumbnail offset in ms.
            cover_url: Public URL for custom cover image.
            location_id: Optional Facebook Place ID.
        """
        params: Dict[str, Any] = {
            "video_url": video_url,
            "media_type": "REELS",
            "share_to_feed": "true" if share_to_feed else "false",
        }
        if caption:
            params["caption"] = caption
        if thumb_offset:
            params["thumb_offset"] = str(thumb_offset)
        if cover_url:
            params["cover_url"] = cover_url
        if location_id:
            params["location_id"] = location_id

        container_id = self._create_container(**params)
        self._wait_for_container(container_id)
        media_id = self._publish_container(container_id)

        return PublishResult(
            post_id=media_id,
            platform="instagram",
            status="published",
        )

    def publish_carousel(self, items: List[Dict[str, str]],
                         caption: str = "",
                         location_id: str = "") -> PublishResult:
        """
        Publish a carousel (album) to Instagram.

        Args:
            items: List of dicts, each with 'image_url' or 'video_url' key.
                   Videos require 'media_type': 'VIDEO'.
            caption: Post caption.
            location_id: Optional Facebook Place ID.
        """
        # Step 1: Create child containers for each item
        child_ids = []
        for item in items:
            child_params: Dict[str, Any] = {"is_carousel_item": "true"}
            if "video_url" in item:
                child_params["video_url"] = item["video_url"]
                child_params["media_type"] = "VIDEO"
            elif "image_url" in item:
                child_params["image_url"] = item["image_url"]
            else:
                raise MetaError("Each carousel item must have 'image_url' or 'video_url'")

            child_id = self._create_container(**child_params)
            child_ids.append(child_id)

        # Step 2: Wait for any video containers to process
        for i, item in enumerate(items):
            if "video_url" in item:
                self._wait_for_container(child_ids[i])

        # Step 3: Create carousel container
        carousel_params: Dict[str, Any] = {
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
        }
        if caption:
            carousel_params["caption"] = caption
        if location_id:
            carousel_params["location_id"] = location_id

        carousel_id = self._create_container(**carousel_params)
        media_id = self._publish_container(carousel_id)

        return PublishResult(
            post_id=media_id,
            platform="instagram",
            status="published",
        )

    def publish_story(self, image_url: str = "", video_url: str = "") -> PublishResult:
        """
        Publish a Story to Instagram.

        Args:
            image_url: Public URL of the image (JPEG).
            video_url: Public URL of the video (MP4, 1-60s).
            Provide exactly one of image_url or video_url.
        """
        if not image_url and not video_url:
            raise MetaError("Either image_url or video_url is required for stories")
        if image_url and video_url:
            raise MetaError("Provide only one of image_url or video_url for stories")

        params: Dict[str, Any] = {"media_type": "STORIES"}
        if image_url:
            params["image_url"] = image_url
        else:
            params["video_url"] = video_url

        container_id = self._create_container(**params)

        # Video stories need processing time
        if video_url:
            self._wait_for_container(container_id)

        media_id = self._publish_container(container_id)

        return PublishResult(
            post_id=media_id,
            platform="instagram",
            status="published",
        )

    # --- Insights ---

    def get_account_insights(self, metrics: List[str],
                             period: str = "day",
                             since: str = "",
                             until: str = "") -> List[InsightMetric]:
        """
        Get account-level insights.

        Args:
            metrics: List of metric names (e.g., impressions, reach, follower_count).
            period: day, week, days_28, month, lifetime.
            since: Start date (Unix timestamp or ISO 8601).
            until: End date (Unix timestamp or ISO 8601).
        """
        params: Dict[str, str] = {
            "metric": ",".join(metrics),
            "period": period,
        }
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        result = self.graph._request("GET", f"/{self.ig_user_id}/insights",
                                     params=params)
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

    def get_media_insights(self, media_id: str,
                           metrics: Optional[List[str]] = None) -> List[InsightMetric]:
        """
        Get insights for a specific media item.

        Default metrics: impressions, reach, engagement, saved.
        Video metrics also include: video_views, plays.
        """
        if metrics is None:
            metrics = ["impressions", "reach", "engagement", "saved"]

        params = {"metric": ",".join(metrics)}
        result = self.graph._request("GET", f"/{media_id}/insights", params=params)

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

    # --- Content Discovery ---

    def get_hashtag_id(self, hashtag_name: str) -> str:
        """Get the hashtag ID for searching. Requires ig_hashtag_search permission."""
        result = self.graph._request("GET", "/ig_hashtag_search",
                                     params={"q": hashtag_name,
                                             "user_id": self.ig_user_id})
        data = result.get("data", [])
        return data[0].get("id", "") if data else ""

    # --- Comment Management ---

    def get_comments(self, media_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Get comments on a media item."""
        result = self.graph._request(
            "GET", f"/{media_id}/comments",
            params={"fields": "id,text,username,timestamp,like_count",
                    "limit": str(limit)})
        return result.get("data", [])

    def reply_to_comment(self, comment_id: str, message: str) -> str:
        """Reply to a comment. Returns reply ID."""
        result = self.graph._request("POST", f"/{comment_id}/replies",
                                     body={"message": message})
        return result.get("id", "")

    def delete_comment(self, comment_id: str) -> bool:
        """Delete a comment."""
        result = self.graph._request("DELETE", f"/{comment_id}")
        return result.get("success", False) or result.get("dry_run", False)


# ---------------------------------------------------------------------------
# Facebook Pages API Client
# ---------------------------------------------------------------------------

class FacebookPagesClient:
    """
    Client for Facebook Pages API.

    Supports page posts (text, images, videos, links), page insights,
    page info, and scheduled posts.

    Note: Page operations require a Page Access Token, which is obtained
    from the User Access Token via GET /me/accounts.
    """

    def __init__(self, graph: MetaGraphClient, page_id: str,
                 page_access_token: str = ""):
        self.graph = graph
        self.page_id = page_id
        # Page-level access token (may differ from user token)
        if page_access_token:
            self._page_graph = MetaGraphClient(page_access_token,
                                               dry_run=graph.dry_run)
        else:
            self._page_graph = graph

    # --- Page Info ---

    def get_page_info(self) -> PageInfo:
        """Get Facebook Page information."""
        fields = "id,name,category,fan_count,link,verification_status,about"
        result = self._page_graph._request("GET", f"/{self.page_id}",
                                           params={"fields": fields})
        return PageInfo(
            page_id=result.get("id", self.page_id),
            name=result.get("name", ""),
            category=result.get("category", ""),
            fan_count=result.get("fan_count", 0),
            link=result.get("link", ""),
            verification_status=result.get("verification_status", ""),
            about=result.get("about", ""),
        )

    # --- Post Listing ---

    def list_posts(self, limit: int = 25) -> List[PagePost]:
        """List recent posts from the Facebook Page."""
        fields = "id,message,created_time,permalink_url,full_picture,shares,reactions.summary(true),comments.summary(true)"
        result = self._page_graph._request("GET", f"/{self.page_id}/posts",
                                           params={"fields": fields,
                                                   "limit": str(limit)})
        posts = []
        for p in result.get("data", []):
            shares = p.get("shares", {})
            reactions = p.get("reactions", {}).get("summary", {})
            comments = p.get("comments", {}).get("summary", {})
            posts.append(PagePost(
                post_id=p.get("id", ""),
                message=p.get("message", ""),
                created_time=p.get("created_time", ""),
                permalink_url=p.get("permalink_url", ""),
                full_picture=p.get("full_picture", ""),
                shares_count=shares.get("count", 0),
                reactions_count=reactions.get("total_count", 0),
                comments_count=comments.get("total_count", 0),
            ))
        return posts

    def get_post(self, post_id: str) -> PagePost:
        """Get details of a specific post."""
        fields = "id,message,created_time,permalink_url,full_picture,shares,reactions.summary(true),comments.summary(true)"
        result = self._page_graph._request("GET", f"/{post_id}",
                                           params={"fields": fields})
        shares = result.get("shares", {})
        reactions = result.get("reactions", {}).get("summary", {})
        comments = result.get("comments", {}).get("summary", {})
        return PagePost(
            post_id=result.get("id", post_id),
            message=result.get("message", ""),
            created_time=result.get("created_time", ""),
            permalink_url=result.get("permalink_url", ""),
            full_picture=result.get("full_picture", ""),
            shares_count=shares.get("count", 0),
            reactions_count=reactions.get("total_count", 0),
            comments_count=comments.get("total_count", 0),
        )

    # --- Publishing ---

    def publish_text(self, message: str,
                     scheduled_publish_time: int = 0) -> PublishResult:
        """
        Publish a text post to the Page feed.

        Args:
            message: Post message.
            scheduled_publish_time: Unix timestamp for scheduled publishing.
                                   Must be 10min-75 days in the future.
        """
        body: Dict[str, Any] = {"message": message}
        if scheduled_publish_time:
            body["published"] = "false"
            body["scheduled_publish_time"] = str(scheduled_publish_time)

        result = self._page_graph._request("POST", f"/{self.page_id}/feed",
                                           body=body)
        return PublishResult(
            post_id=result.get("id", ""),
            platform="facebook",
            status="scheduled" if scheduled_publish_time else "published",
            created_time=datetime.now(timezone.utc).isoformat(),
        )

    def publish_link(self, link: str, message: str = "",
                     scheduled_publish_time: int = 0) -> PublishResult:
        """Publish a link post to the Page feed."""
        body: Dict[str, Any] = {"link": link}
        if message:
            body["message"] = message
        if scheduled_publish_time:
            body["published"] = "false"
            body["scheduled_publish_time"] = str(scheduled_publish_time)

        result = self._page_graph._request("POST", f"/{self.page_id}/feed",
                                           body=body)
        return PublishResult(
            post_id=result.get("id", ""),
            platform="facebook",
            status="scheduled" if scheduled_publish_time else "published",
        )

    def publish_image(self, image_url: str = "", image_path: str = "",
                      message: str = "",
                      scheduled_publish_time: int = 0) -> PublishResult:
        """
        Publish a photo post to the Page.

        Args:
            image_url: Public URL of the image.
            image_path: Local path to image file (alternative to URL).
            message: Post message/caption.
            scheduled_publish_time: Unix timestamp for scheduling.
        """
        body: Dict[str, Any] = {}
        if message:
            body["message"] = message
        if scheduled_publish_time:
            body["published"] = "false"
            body["scheduled_publish_time"] = str(scheduled_publish_time)

        if image_url:
            body["url"] = image_url
            result = self._page_graph._request("POST", f"/{self.page_id}/photos",
                                               body=body)
        elif image_path:
            path = Path(image_path)
            if not path.is_file():
                raise MetaError(f"Image file not found: {image_path}")
            mime_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
            with open(path, "rb") as f:
                file_data = f.read()
            result = self._page_graph._request(
                "POST", f"/{self.page_id}/photos",
                body=body,
                files={"source": (path.name, file_data, mime_type)},
            )
        else:
            raise MetaError("Either image_url or image_path is required")

        return PublishResult(
            post_id=result.get("id", result.get("post_id", "")),
            platform="facebook",
            status="scheduled" if scheduled_publish_time else "published",
        )

    def publish_video(self, video_url: str = "", video_path: str = "",
                      title: str = "", description: str = "",
                      scheduled_publish_time: int = 0) -> PublishResult:
        """
        Publish a video to the Page.

        Args:
            video_url: Public URL of the video.
            video_path: Local path to video file.
            title: Video title.
            description: Video description.
            scheduled_publish_time: Unix timestamp for scheduling.
        """
        body: Dict[str, Any] = {}
        if title:
            body["title"] = title
        if description:
            body["description"] = description
        if scheduled_publish_time:
            body["published"] = "false"
            body["scheduled_publish_time"] = str(scheduled_publish_time)

        if video_url:
            body["file_url"] = video_url
            result = self._page_graph._request(
                "POST", f"/{self.page_id}/videos",
                body=body,
                use_video_host=True,
            )
        elif video_path:
            path = Path(video_path)
            if not path.is_file():
                raise MetaError(f"Video file not found: {video_path}")
            mime_type = mimetypes.guess_type(str(path))[0] or "video/mp4"
            with open(path, "rb") as f:
                file_data = f.read()
            result = self._page_graph._request(
                "POST", f"/{self.page_id}/videos",
                body=body,
                files={"source": (path.name, file_data, mime_type)},
                use_video_host=True,
            )
        else:
            raise MetaError("Either video_url or video_path is required")

        return PublishResult(
            post_id=result.get("id", ""),
            platform="facebook",
            status="scheduled" if scheduled_publish_time else "published",
        )

    def publish_reel(self, video_url: str = "", video_path: str = "",
                     description: str = "") -> PublishResult:
        """
        Publish a Reel to the Facebook Page.

        Args:
            video_url: Public URL of the video.
            video_path: Local path to video file.
            description: Reel description (supports hashtags).
        """
        body: Dict[str, Any] = {}
        if description:
            body["description"] = description

        if video_url:
            body["file_url"] = video_url
            result = self._page_graph._request(
                "POST", f"/{self.page_id}/video_reels",
                body=body,
                use_video_host=True,
            )
        elif video_path:
            path = Path(video_path)
            if not path.is_file():
                raise MetaError(f"Video file not found: {video_path}")
            mime_type = mimetypes.guess_type(str(path))[0] or "video/mp4"
            with open(path, "rb") as f:
                file_data = f.read()
            result = self._page_graph._request(
                "POST", f"/{self.page_id}/video_reels",
                body=body,
                files={"source": (path.name, file_data, mime_type)},
                use_video_host=True,
            )
        else:
            raise MetaError("Either video_url or video_path is required")

        return PublishResult(
            post_id=result.get("id", ""),
            platform="facebook",
            status="published",
        )

    def delete_post(self, post_id: str) -> bool:
        """Delete a post from the Page."""
        result = self._page_graph._request("DELETE", f"/{post_id}")
        return result.get("success", False) or result.get("dry_run", False)

    # --- Insights ---

    def get_page_insights(self, metrics: List[str],
                          period: str = "day",
                          since: str = "",
                          until: str = "") -> List[InsightMetric]:
        """
        Get page-level insights.

        Args:
            metrics: Metric names (e.g., page_impressions, page_engaged_users).
            period: day, week, days_28.
            since: Start date (Unix timestamp or YYYY-MM-DD).
            until: End date (Unix timestamp or YYYY-MM-DD).
        """
        params: Dict[str, str] = {
            "metric": ",".join(metrics),
            "period": period,
        }
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        result = self._page_graph._request("GET", f"/{self.page_id}/insights",
                                           params=params)
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


# ---------------------------------------------------------------------------
# Clients container (lazy init, same pattern as TikTokClients)
# ---------------------------------------------------------------------------

@dataclass
class MetaClients:
    """Container for lazily-initialized Meta API clients."""
    brand: str = ""
    dry_run: bool = False
    graph: Optional[MetaGraphClient] = None
    instagram: Optional[InstagramClient] = None
    facebook: Optional[FacebookPagesClient] = None


# ---------------------------------------------------------------------------
# Token Management
# ---------------------------------------------------------------------------

def cmd_token_info(clients: MetaClients, args: argparse.Namespace) -> int:
    """Debug token to show permissions and expiry."""
    assert clients.graph is not None
    result = clients.graph._request(
        "GET", "/debug_token",
        params={"input_token": clients.graph.access_token})
    data = result.get("data", {})

    info = TokenInfo(
        app_id=data.get("app_id", ""),
        user_id=data.get("user_id", ""),
        type=data.get("type", ""),
        expires_at=data.get("expires_at", 0),
        is_valid=data.get("is_valid", False),
        scopes=data.get("scopes", []),
    )

    if args.json:
        _json_output(_dc_to_dict(info))
        return 0

    valid_str = f"{GREEN}valid{RESET}" if info.is_valid else f"{RED}INVALID{RESET}"
    expires_str = ""
    if info.expires_at == 0:
        expires_str = f"{GREEN}Never (long-lived){RESET}"
    elif info.expires_at > 0:
        exp_dt = datetime.fromtimestamp(info.expires_at)
        if exp_dt > datetime.now():
            expires_str = f"{GREEN}{exp_dt.strftime('%Y-%m-%d %H:%M')}{RESET}"
        else:
            expires_str = f"{RED}{exp_dt.strftime('%Y-%m-%d %H:%M')} (EXPIRED){RESET}"

    print(f"\n{BOLD}Meta Access Token Info{RESET}")
    print(f"  Status:    {valid_str}")
    print(f"  Type:      {info.type}")
    print(f"  App ID:    {info.app_id}")
    print(f"  User ID:   {info.user_id}")
    print(f"  Expires:   {expires_str}")
    print(f"  Scopes:    {', '.join(info.scopes)}")
    print()
    return 0


def cmd_exchange_token(clients: MetaClients, args: argparse.Namespace) -> int:
    """Exchange a short-lived token for a long-lived token."""
    creds = BrandCredentialLoader(clients.brand)
    app_id = creds.require("META_APP_ID",
                           f"ecommerce/{clients.brand}/meta-app",
                           "Meta App ID")
    app_secret = creds.require("META_APP_SECRET",
                               f"ecommerce/{clients.brand}/meta-app-secret",
                               "Meta App Secret")
    short_token = args.token or clients.graph.access_token  # type: ignore[union-attr]

    assert clients.graph is not None
    result = clients.graph._request(
        "GET", "/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        })

    long_token = result.get("access_token", "")
    expires_in = result.get("expires_in", 0)

    if not long_token:
        print(f"{RED}Failed to exchange token{RESET}")
        return 1

    if args.json:
        _json_output({"access_token": long_token, "expires_in": expires_in})
        return 0

    print(f"\n{GREEN}Long-lived token obtained!{RESET}")
    print(f"  Token:      {long_token[:20]}...{long_token[-10:]}")
    if expires_in:
        days = expires_in // 86400
        print(f"  Expires in: {days} days ({expires_in}s)")
    else:
        print(f"  Expires:    {GREEN}Never{RESET}")
    print(f"\n{YELLOW}Save this to your brand .env as META_ACCESS_TOKEN{RESET}")
    print(f"  Or store in Keychain: security add-generic-password "
          f"-s 'ecommerce/{clients.brand}/meta-token' "
          f"-a '{clients.brand}' -w '<token>' -U")
    print()
    return 0


def cmd_pages(clients: MetaClients, args: argparse.Namespace) -> int:
    """List Facebook Pages accessible with the current token."""
    assert clients.graph is not None
    result = clients.graph._request(
        "GET", "/me/accounts",
        params={"fields": "id,name,category,access_token,fan_count"})

    pages = result.get("data", [])

    if args.json:
        # Redact page tokens unless verbose
        if not args.verbose:
            for p in pages:
                if "access_token" in p:
                    p["access_token"] = p["access_token"][:20] + "..."
        _json_output(pages)
        return 0

    if not pages:
        print(f"\n{YELLOW}No Pages found.{RESET}")
        print("  Ensure your token has pages_show_list, pages_manage_posts permissions.")
        return 0

    print(f"\n{BOLD}Facebook Pages ({len(pages)}){RESET}\n")
    rows = []
    for p in pages:
        rows.append([
            p.get("id", ""),
            p.get("name", ""),
            p.get("category", ""),
            str(p.get("fan_count", 0)),
            p.get("access_token", "")[:20] + "..." if p.get("access_token") else "",
        ])

    print(_format_table(["Page ID", "Name", "Category", "Fans", "Token (prefix)"], rows))
    print()
    return 0


# ---------------------------------------------------------------------------
# Instagram Command Handlers
# ---------------------------------------------------------------------------

def cmd_ig_account(clients: MetaClients, args: argparse.Namespace) -> int:
    """Show Instagram Business Account info."""
    assert clients.instagram is not None
    info = clients.instagram.get_account_info()

    if args.json:
        _json_output(_dc_to_dict(info))
        return 0

    print(f"\n{BOLD}Instagram Account{RESET}\n")
    print(f"  ID:          {info.account_id}")
    print(f"  Username:    {CYAN}@{info.username}{RESET}")
    print(f"  Name:        {info.name}")
    print(f"  Followers:   {info.followers_count:,}")
    print(f"  Media Count: {info.media_count:,}")
    if info.biography:
        print(f"  Bio:         {_truncate(info.biography, 60)}")
    if info.website:
        print(f"  Website:     {info.website}")
    print()
    return 0


def cmd_ig_media(clients: MetaClients, args: argparse.Namespace) -> int:
    """List recent Instagram media."""
    assert clients.instagram is not None
    limit = getattr(args, "limit", 25)
    items = clients.instagram.list_media(limit=limit)

    if args.json:
        _json_output([_dc_to_dict(m) for m in items])
        return 0

    if not items:
        print(f"\n{YELLOW}No media found.{RESET}")
        return 0

    print(f"\n{BOLD}Instagram Media ({len(items)} items){RESET}\n")
    rows = []
    for m in items:
        rows.append([
            m.media_id,
            m.media_type,
            _truncate(m.caption.replace("\n", " "), 40),
            _ts_to_str(m.timestamp),
            f"{GREEN}{m.like_count}{RESET}",
            str(m.comments_count),
        ])

    print(_format_table(["ID", "Type", "Caption", "Date", "Likes", "Comments"], rows))
    print()
    return 0


def cmd_ig_post_image(clients: MetaClients, args: argparse.Namespace) -> int:
    """Post an image to Instagram."""
    assert clients.instagram is not None

    # Instagram requires a public URL for the image
    image_url = getattr(args, "image_url", "") or getattr(args, "image", "")
    caption = getattr(args, "caption", "") or ""
    location_id = getattr(args, "location", "") or ""

    if not image_url:
        print(f"{RED}Error: --image-url is required for Instagram posts.{RESET}")
        print("  Instagram Graph API requires a publicly accessible image URL.")
        return 1

    result = clients.instagram.publish_image(
        image_url=image_url, caption=caption, location_id=location_id)

    if args.json:
        _json_output(_dc_to_dict(result))
        return 0

    print(f"\n{GREEN}Image posted to Instagram!{RESET}")
    print(f"  Post ID: {result.post_id}")
    print()
    return 0


def cmd_ig_post_video(clients: MetaClients, args: argparse.Namespace) -> int:
    """Post a video to Instagram."""
    assert clients.instagram is not None

    video_url = getattr(args, "video_url", "") or getattr(args, "video", "")
    caption = getattr(args, "caption", "") or ""

    if not video_url:
        print(f"{RED}Error: --video-url is required for Instagram video posts.{RESET}")
        return 1

    result = clients.instagram.publish_video(video_url=video_url, caption=caption)

    if args.json:
        _json_output(_dc_to_dict(result))
        return 0

    print(f"\n{GREEN}Video posted to Instagram!{RESET}")
    print(f"  Post ID: {result.post_id}")
    print()
    return 0


def cmd_ig_post_reel(clients: MetaClients, args: argparse.Namespace) -> int:
    """Post a Reel to Instagram."""
    assert clients.instagram is not None

    video_url = getattr(args, "video_url", "") or getattr(args, "video", "")
    caption = getattr(args, "caption", "") or ""
    share_to_feed = not getattr(args, "no_feed", False)
    cover_url = getattr(args, "cover_url", "") or ""

    if not video_url:
        print(f"{RED}Error: --video-url is required for Instagram Reels.{RESET}")
        return 1

    result = clients.instagram.publish_reel(
        video_url=video_url, caption=caption,
        share_to_feed=share_to_feed, cover_url=cover_url)

    if args.json:
        _json_output(_dc_to_dict(result))
        return 0

    print(f"\n{GREEN}Reel posted to Instagram!{RESET}")
    print(f"  Post ID: {result.post_id}")
    print()
    return 0


def cmd_ig_post_carousel(clients: MetaClients, args: argparse.Namespace) -> int:
    """Post a carousel to Instagram."""
    assert clients.instagram is not None

    items_str = getattr(args, "items", "") or ""
    caption = getattr(args, "caption", "") or ""

    if not items_str:
        print(f"{RED}Error: --items is required (JSON array or comma-separated URLs).{RESET}")
        return 1

    # Parse items: either JSON array or comma-separated image URLs
    try:
        items = json.loads(items_str)
    except json.JSONDecodeError:
        # Treat as comma-separated image URLs
        urls = [u.strip() for u in items_str.split(",") if u.strip()]
        items = [{"image_url": u} for u in urls]

    if not items:
        print(f"{RED}Error: No carousel items provided.{RESET}")
        return 1

    if len(items) < 2:
        print(f"{RED}Error: Carousel requires at least 2 items.{RESET}")
        return 1

    if len(items) > 10:
        print(f"{RED}Error: Carousel supports maximum 10 items.{RESET}")
        return 1

    result = clients.instagram.publish_carousel(items=items, caption=caption)

    if args.json:
        _json_output(_dc_to_dict(result))
        return 0

    print(f"\n{GREEN}Carousel posted to Instagram!{RESET}")
    print(f"  Post ID: {result.post_id}")
    print(f"  Items:   {len(items)}")
    print()
    return 0


def cmd_ig_post_story(clients: MetaClients, args: argparse.Namespace) -> int:
    """Post a Story to Instagram."""
    assert clients.instagram is not None

    image_url = getattr(args, "image_url", "") or ""
    video_url = getattr(args, "video_url", "") or ""

    if not image_url and not video_url:
        print(f"{RED}Error: --image-url or --video-url is required for Stories.{RESET}")
        return 1

    result = clients.instagram.publish_story(
        image_url=image_url, video_url=video_url)

    if args.json:
        _json_output(_dc_to_dict(result))
        return 0

    print(f"\n{GREEN}Story posted to Instagram!{RESET}")
    print(f"  Post ID: {result.post_id}")
    print()
    return 0


def cmd_ig_insights(clients: MetaClients, args: argparse.Namespace) -> int:
    """Get Instagram account insights."""
    assert clients.instagram is not None

    metric_str = getattr(args, "metric", "impressions,reach,profile_views")
    metrics = [m.strip() for m in metric_str.split(",")]
    period = getattr(args, "period", "day")
    since = getattr(args, "since", "") or ""
    until = getattr(args, "until", "") or ""

    insights = clients.instagram.get_account_insights(
        metrics=metrics, period=period, since=since, until=until)

    if args.json:
        _json_output([_dc_to_dict(i) for i in insights])
        return 0

    if not insights:
        print(f"\n{YELLOW}No insights data returned.{RESET}")
        return 0

    print(f"\n{BOLD}Instagram Insights{RESET}\n")
    for insight in insights:
        print(f"  {CYAN}{insight.name}{RESET} ({insight.period})")
        if insight.title:
            print(f"    {insight.title}")
        for val in insight.values:
            value = val.get("value", "N/A")
            end_time = val.get("end_time", "")
            if end_time:
                print(f"    {_ts_to_str(end_time)}: {value}")
            else:
                print(f"    Value: {value}")
        print()
    return 0


def cmd_ig_media_insights(clients: MetaClients, args: argparse.Namespace) -> int:
    """Get insights for a specific Instagram media item."""
    assert clients.instagram is not None

    media_id = args.media_id
    metric_str = getattr(args, "metric", "") or "impressions,reach,engagement,saved"
    metrics = [m.strip() for m in metric_str.split(",")]

    insights = clients.instagram.get_media_insights(media_id=media_id, metrics=metrics)

    if args.json:
        _json_output([_dc_to_dict(i) for i in insights])
        return 0

    if not insights:
        print(f"\n{YELLOW}No insights data for media {media_id}.{RESET}")
        return 0

    print(f"\n{BOLD}Media Insights ({media_id}){RESET}\n")
    for insight in insights:
        values = insight.values
        if values:
            val = values[0].get("value", "N/A")
            print(f"  {insight.name}: {CYAN}{val}{RESET}")
        else:
            print(f"  {insight.name}: N/A")
    print()
    return 0


def cmd_ig_comments(clients: MetaClients, args: argparse.Namespace) -> int:
    """Get comments on an Instagram media item."""
    assert clients.instagram is not None

    media_id = args.media_id
    limit = getattr(args, "limit", 25)
    comments = clients.instagram.get_comments(media_id=media_id, limit=limit)

    if args.json:
        _json_output(comments)
        return 0

    if not comments:
        print(f"\n{YELLOW}No comments on media {media_id}.{RESET}")
        return 0

    print(f"\n{BOLD}Comments on {media_id}{RESET}\n")
    rows = []
    for c in comments:
        rows.append([
            c.get("id", ""),
            c.get("username", ""),
            _truncate(c.get("text", "").replace("\n", " "), 50),
            _ts_to_str(c.get("timestamp", "")),
            str(c.get("like_count", 0)),
        ])

    print(_format_table(["ID", "User", "Text", "Date", "Likes"], rows))
    print()
    return 0


# ---------------------------------------------------------------------------
# Facebook Command Handlers
# ---------------------------------------------------------------------------

def cmd_fb_page_info(clients: MetaClients, args: argparse.Namespace) -> int:
    """Show Facebook Page info."""
    assert clients.facebook is not None
    info = clients.facebook.get_page_info()

    if args.json:
        _json_output(_dc_to_dict(info))
        return 0

    print(f"\n{BOLD}Facebook Page{RESET}\n")
    print(f"  ID:           {info.page_id}")
    print(f"  Name:         {info.name}")
    print(f"  Category:     {info.category}")
    print(f"  Fans:         {info.fan_count:,}")
    if info.link:
        print(f"  Link:         {info.link}")
    if info.verification_status:
        print(f"  Verified:     {info.verification_status}")
    if info.about:
        print(f"  About:        {_truncate(info.about, 60)}")
    print()
    return 0


def cmd_fb_posts(clients: MetaClients, args: argparse.Namespace) -> int:
    """List recent Facebook Page posts."""
    assert clients.facebook is not None
    limit = getattr(args, "limit", 25)
    posts = clients.facebook.list_posts(limit=limit)

    if args.json:
        _json_output([_dc_to_dict(p) for p in posts])
        return 0

    if not posts:
        print(f"\n{YELLOW}No posts found.{RESET}")
        return 0

    print(f"\n{BOLD}Facebook Page Posts ({len(posts)}){RESET}\n")
    rows = []
    for p in posts:
        rows.append([
            p.post_id,
            _truncate(p.message.replace("\n", " "), 40),
            _ts_to_str(p.created_time),
            f"{GREEN}{p.reactions_count}{RESET}",
            str(p.comments_count),
            str(p.shares_count),
        ])

    print(_format_table(
        ["Post ID", "Message", "Date", "Reactions", "Comments", "Shares"], rows))
    print()
    return 0


def cmd_fb_post_text(clients: MetaClients, args: argparse.Namespace) -> int:
    """Post text to Facebook Page."""
    assert clients.facebook is not None

    message = args.message
    schedule_time = _parse_schedule_time(getattr(args, "schedule", "") or "")

    result = clients.facebook.publish_text(
        message=message, scheduled_publish_time=schedule_time)

    if args.json:
        _json_output(_dc_to_dict(result))
        return 0

    status = f"{YELLOW}scheduled{RESET}" if schedule_time else f"{GREEN}published{RESET}"
    print(f"\n{GREEN}Text post {status} to Facebook!{RESET}")
    print(f"  Post ID: {result.post_id}")
    print()
    return 0


def cmd_fb_post_image(clients: MetaClients, args: argparse.Namespace) -> int:
    """Post an image to Facebook Page."""
    assert clients.facebook is not None

    image_url = getattr(args, "image_url", "") or ""
    image_path = getattr(args, "image", "") or ""
    message = getattr(args, "message", "") or ""
    schedule_time = _parse_schedule_time(getattr(args, "schedule", "") or "")

    if not image_url and not image_path:
        print(f"{RED}Error: --image-url or --image is required.{RESET}")
        return 1

    result = clients.facebook.publish_image(
        image_url=image_url, image_path=image_path,
        message=message, scheduled_publish_time=schedule_time)

    if args.json:
        _json_output(_dc_to_dict(result))
        return 0

    status = f"{YELLOW}scheduled{RESET}" if schedule_time else f"{GREEN}published{RESET}"
    print(f"\nImage {status} to Facebook!")
    print(f"  Post ID: {result.post_id}")
    print()
    return 0


def cmd_fb_post_video(clients: MetaClients, args: argparse.Namespace) -> int:
    """Post a video to Facebook Page."""
    assert clients.facebook is not None

    video_url = getattr(args, "video_url", "") or ""
    video_path = getattr(args, "video", "") or ""
    title = getattr(args, "title", "") or ""
    description = getattr(args, "description", "") or ""
    schedule_time = _parse_schedule_time(getattr(args, "schedule", "") or "")

    if not video_url and not video_path:
        print(f"{RED}Error: --video-url or --video is required.{RESET}")
        return 1

    result = clients.facebook.publish_video(
        video_url=video_url, video_path=video_path,
        title=title, description=description,
        scheduled_publish_time=schedule_time)

    if args.json:
        _json_output(_dc_to_dict(result))
        return 0

    status = f"{YELLOW}scheduled{RESET}" if schedule_time else f"{GREEN}published{RESET}"
    print(f"\nVideo {status} to Facebook!")
    print(f"  Post ID: {result.post_id}")
    print()
    return 0


def cmd_fb_post_link(clients: MetaClients, args: argparse.Namespace) -> int:
    """Post a link to Facebook Page."""
    assert clients.facebook is not None

    link = args.link
    message = getattr(args, "message", "") or ""
    schedule_time = _parse_schedule_time(getattr(args, "schedule", "") or "")

    result = clients.facebook.publish_link(
        link=link, message=message, scheduled_publish_time=schedule_time)

    if args.json:
        _json_output(_dc_to_dict(result))
        return 0

    status = f"{YELLOW}scheduled{RESET}" if schedule_time else f"{GREEN}published{RESET}"
    print(f"\nLink {status} to Facebook!")
    print(f"  Post ID: {result.post_id}")
    print()
    return 0


def cmd_fb_post_reel(clients: MetaClients, args: argparse.Namespace) -> int:
    """Post a Reel to Facebook Page."""
    assert clients.facebook is not None

    video_url = getattr(args, "video_url", "") or ""
    video_path = getattr(args, "video", "") or ""
    description = getattr(args, "description", "") or ""

    if not video_url and not video_path:
        print(f"{RED}Error: --video-url or --video is required.{RESET}")
        return 1

    result = clients.facebook.publish_reel(
        video_url=video_url, video_path=video_path, description=description)

    if args.json:
        _json_output(_dc_to_dict(result))
        return 0

    print(f"\n{GREEN}Reel posted to Facebook!{RESET}")
    print(f"  Post ID: {result.post_id}")
    print()
    return 0


def cmd_fb_delete_post(clients: MetaClients, args: argparse.Namespace) -> int:
    """Delete a Facebook Page post."""
    assert clients.facebook is not None

    post_id = args.post_id
    success = clients.facebook.delete_post(post_id)

    if args.json:
        _json_output({"success": success, "post_id": post_id})
        return 0

    if success:
        print(f"\n{GREEN}Post {post_id} deleted.{RESET}")
    else:
        print(f"\n{RED}Failed to delete post {post_id}.{RESET}")
    print()
    return 0 if success else 1


def cmd_fb_insights(clients: MetaClients, args: argparse.Namespace) -> int:
    """Get Facebook Page insights."""
    assert clients.facebook is not None

    metric_str = getattr(args, "metric",
                         "page_impressions,page_engaged_users,page_fan_adds")
    metrics = [m.strip() for m in metric_str.split(",")]
    period = getattr(args, "period", "day")
    since = getattr(args, "since", "") or ""
    until = getattr(args, "until", "") or ""

    insights = clients.facebook.get_page_insights(
        metrics=metrics, period=period, since=since, until=until)

    if args.json:
        _json_output([_dc_to_dict(i) for i in insights])
        return 0

    if not insights:
        print(f"\n{YELLOW}No insights data returned.{RESET}")
        return 0

    print(f"\n{BOLD}Facebook Page Insights{RESET}\n")
    for insight in insights:
        print(f"  {CYAN}{insight.name}{RESET} ({insight.period})")
        if insight.title:
            print(f"    {insight.title}")
        for val in insight.values:
            value = val.get("value", "N/A")
            end_time = val.get("end_time", "")
            if end_time:
                print(f"    {_ts_to_str(end_time)}: {value}")
            else:
                print(f"    Value: {value}")
        print()
    return 0


# ---------------------------------------------------------------------------
# Utility Helpers
# ---------------------------------------------------------------------------

def _parse_schedule_time(schedule_str: str) -> int:
    """
    Parse a schedule time string into a Unix timestamp.
    Accepts: Unix timestamp, or "YYYY-MM-DD HH:MM" format.
    Returns 0 if empty/invalid.
    """
    if not schedule_str:
        return 0

    # Try as Unix timestamp
    try:
        ts = int(schedule_str)
        return ts
    except ValueError:
        pass

    # Try as datetime string
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S"]:
        try:
            dt = datetime.strptime(schedule_str, fmt)
            return int(dt.replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue

    logger.warning("Could not parse schedule time: %s", schedule_str)
    return 0


# ---------------------------------------------------------------------------
# CLI Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="meta-api",
        description=f"Meta Unified CLI (Instagram + Facebook Pages) v{VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Token management
  %(prog)s token-info --brand myshop
  %(prog)s exchange-token --brand myshop --token SHORT_LIVED_TOKEN
  %(prog)s pages --brand myshop

  # Instagram
  %(prog)s ig-account --brand myshop
  %(prog)s ig-media --brand myshop --limit 10
  %(prog)s ig-post-image --brand myshop --image-url https://... --caption "Hello!"
  %(prog)s ig-post-video --brand myshop --video-url https://... --caption "Check this out"
  %(prog)s ig-post-reel --brand myshop --video-url https://... --caption "New reel!"
  %(prog)s ig-post-carousel --brand myshop --items "url1,url2,url3" --caption "Album"
  %(prog)s ig-post-story --brand myshop --image-url https://...
  %(prog)s ig-insights --brand myshop --metric impressions,reach --period day
  %(prog)s ig-media-insights --brand myshop MEDIA_ID

  # Facebook Page
  %(prog)s fb-page-info --brand myshop
  %(prog)s fb-posts --brand myshop --limit 10
  %(prog)s fb-post-text --brand myshop --message "Hello from CLI!"
  %(prog)s fb-post-image --brand myshop --image-url https://... --message "Photo"
  %(prog)s fb-post-image --brand myshop --image /path/to/photo.jpg --message "Local"
  %(prog)s fb-post-video --brand myshop --video-url https://... --title "My Video"
  %(prog)s fb-post-link --brand myshop --link https://example.com --message "Check this"
  %(prog)s fb-post-reel --brand myshop --video-url https://... --description "Reel!"
  %(prog)s fb-insights --brand myshop --metric page_impressions --period day

  # Scheduling (Facebook)
  %(prog)s fb-post-text --brand myshop --message "Future post" --schedule "2026-02-15 10:00"
  %(prog)s fb-post-image --brand myshop --image-url https://... --schedule 1739577600
""",
    )

    # Shared arguments
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--brand", help="Brand name for credential isolation")
    shared.add_argument("--json", action="store_true", help="JSON output for scripting")
    shared.add_argument("--dry-run", action="store_true", help="Preview mutations without executing")
    shared.add_argument("--verbose", action="store_true", help="Enable debug logging")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # === Token Management ===

    sub.add_parser("token-info", parents=[shared],
                   help="Show access token info (permissions, expiry)")

    p = sub.add_parser("exchange-token", parents=[shared],
                       help="Exchange short-lived token for long-lived token")
    p.add_argument("--token", help="Short-lived token to exchange (defaults to configured token)")

    sub.add_parser("pages", parents=[shared],
                   help="List Facebook Pages accessible with current token")

    # === Instagram Commands ===

    sub.add_parser("ig-account", parents=[shared],
                   help="Show Instagram Business Account info")

    p = sub.add_parser("ig-media", parents=[shared],
                       help="List recent Instagram media")
    p.add_argument("--limit", type=int, default=25, help="Max items to return")

    p = sub.add_parser("ig-post-image", parents=[shared],
                       help="Post an image to Instagram")
    p.add_argument("--image-url", required=True,
                   help="Public URL of the image (JPEG, 8MB max)")
    p.add_argument("--caption", default="", help="Post caption (max 2200 chars)")
    p.add_argument("--location", default="", help="Facebook Place ID for location tag")

    p = sub.add_parser("ig-post-video", parents=[shared],
                       help="Post a video to Instagram feed")
    p.add_argument("--video-url", required=True,
                   help="Public URL of the video (MP4, H.264)")
    p.add_argument("--caption", default="", help="Post caption")

    p = sub.add_parser("ig-post-reel", parents=[shared],
                       help="Post a Reel to Instagram")
    p.add_argument("--video-url", required=True,
                   help="Public URL of the video (MP4, 3-90s)")
    p.add_argument("--caption", default="", help="Reel caption")
    p.add_argument("--cover-url", default="", help="Custom cover image URL")
    p.add_argument("--no-feed", action="store_true",
                   help="Don't share to main feed")

    p = sub.add_parser("ig-post-carousel", parents=[shared],
                       help="Post a carousel (album) to Instagram")
    p.add_argument("--items", required=True,
                   help="JSON array of items or comma-separated image URLs (2-10 items)")
    p.add_argument("--caption", default="", help="Post caption")

    p = sub.add_parser("ig-post-story", parents=[shared],
                       help="Post a Story to Instagram")
    p.add_argument("--image-url", default="", help="Public URL of story image")
    p.add_argument("--video-url", default="", help="Public URL of story video (1-60s)")

    p = sub.add_parser("ig-insights", parents=[shared],
                       help="Get Instagram account insights")
    p.add_argument("--metric", default="impressions,reach,profile_views",
                   help="Comma-separated metrics")
    p.add_argument("--period", default="day",
                   choices=["day", "week", "days_28", "month", "lifetime"],
                   help="Aggregation period")
    p.add_argument("--since", default="", help="Start date (YYYY-MM-DD or Unix timestamp)")
    p.add_argument("--until", default="", help="End date (YYYY-MM-DD or Unix timestamp)")

    p = sub.add_parser("ig-media-insights", parents=[shared],
                       help="Get insights for a specific media item")
    p.add_argument("media_id", help="Instagram media ID")
    p.add_argument("--metric", default="impressions,reach,engagement,saved",
                   help="Comma-separated metrics")

    p = sub.add_parser("ig-comments", parents=[shared],
                       help="Get comments on an Instagram media item")
    p.add_argument("media_id", help="Instagram media ID")
    p.add_argument("--limit", type=int, default=25, help="Max comments to return")

    # === Facebook Commands ===

    sub.add_parser("fb-page-info", parents=[shared],
                   help="Show Facebook Page info")

    p = sub.add_parser("fb-posts", parents=[shared],
                       help="List recent Facebook Page posts")
    p.add_argument("--limit", type=int, default=25, help="Max posts to return")

    p = sub.add_parser("fb-post-text", parents=[shared],
                       help="Post text to Facebook Page")
    p.add_argument("--message", required=True, help="Post message")
    p.add_argument("--schedule", default="",
                   help="Schedule time (YYYY-MM-DD HH:MM or Unix timestamp)")

    p = sub.add_parser("fb-post-image", parents=[shared],
                       help="Post an image to Facebook Page")
    p.add_argument("--image-url", default="", help="Public URL of the image")
    p.add_argument("--image", default="", help="Local path to image file")
    p.add_argument("--message", default="", help="Post message/caption")
    p.add_argument("--schedule", default="",
                   help="Schedule time (YYYY-MM-DD HH:MM or Unix timestamp)")

    p = sub.add_parser("fb-post-video", parents=[shared],
                       help="Post a video to Facebook Page")
    p.add_argument("--video-url", default="", help="Public URL of the video")
    p.add_argument("--video", default="", help="Local path to video file")
    p.add_argument("--title", default="", help="Video title")
    p.add_argument("--description", default="", help="Video description")
    p.add_argument("--schedule", default="",
                   help="Schedule time (YYYY-MM-DD HH:MM or Unix timestamp)")

    p = sub.add_parser("fb-post-link", parents=[shared],
                       help="Post a link to Facebook Page")
    p.add_argument("--link", required=True, help="URL to share")
    p.add_argument("--message", default="", help="Accompanying message")
    p.add_argument("--schedule", default="",
                   help="Schedule time (YYYY-MM-DD HH:MM or Unix timestamp)")

    p = sub.add_parser("fb-post-reel", parents=[shared],
                       help="Post a Reel to Facebook Page")
    p.add_argument("--video-url", default="", help="Public URL of the video")
    p.add_argument("--video", default="", help="Local path to video file")
    p.add_argument("--description", default="", help="Reel description (supports hashtags)")

    p = sub.add_parser("fb-delete-post", parents=[shared],
                       help="Delete a Facebook Page post")
    p.add_argument("post_id", help="Post ID to delete")

    p = sub.add_parser("fb-insights", parents=[shared],
                       help="Get Facebook Page insights")
    p.add_argument("--metric",
                   default="page_impressions,page_engaged_users,page_fan_adds",
                   help="Comma-separated metrics")
    p.add_argument("--period", default="day",
                   choices=["day", "week", "days_28"],
                   help="Aggregation period")
    p.add_argument("--since", default="", help="Start date")
    p.add_argument("--until", default="", help="End date")

    return parser


# ---------------------------------------------------------------------------
# Command Dispatch
# ---------------------------------------------------------------------------

TOKEN_COMMANDS = {
    "token-info": cmd_token_info,
    "exchange-token": cmd_exchange_token,
    "pages": cmd_pages,
}

INSTAGRAM_COMMANDS = {
    "ig-account": cmd_ig_account,
    "ig-media": cmd_ig_media,
    "ig-post-image": cmd_ig_post_image,
    "ig-post-video": cmd_ig_post_video,
    "ig-post-reel": cmd_ig_post_reel,
    "ig-post-carousel": cmd_ig_post_carousel,
    "ig-post-story": cmd_ig_post_story,
    "ig-insights": cmd_ig_insights,
    "ig-media-insights": cmd_ig_media_insights,
    "ig-comments": cmd_ig_comments,
}

FACEBOOK_COMMANDS = {
    "fb-page-info": cmd_fb_page_info,
    "fb-posts": cmd_fb_posts,
    "fb-post-text": cmd_fb_post_text,
    "fb-post-image": cmd_fb_post_image,
    "fb-post-video": cmd_fb_post_video,
    "fb-post-link": cmd_fb_post_link,
    "fb-post-reel": cmd_fb_post_reel,
    "fb-delete-post": cmd_fb_delete_post,
    "fb-insights": cmd_fb_insights,
}

ALL_COMMANDS = {**TOKEN_COMMANDS, **INSTAGRAM_COMMANDS, **FACEBOOK_COMMANDS}


# ---------------------------------------------------------------------------
# Client initialization (lazy)
# ---------------------------------------------------------------------------

def _init_graph_client(brand: str, dry_run: bool) -> MetaGraphClient:
    """Initialize the Meta Graph API base client with brand credentials."""
    creds = BrandCredentialLoader(brand)
    access_token = creds.require("META_ACCESS_TOKEN",
                                 f"ecommerce/{brand}/meta-token",
                                 "Meta Access Token")
    return MetaGraphClient(access_token, dry_run=dry_run)


def _init_instagram_client(graph: MetaGraphClient, brand: str) -> InstagramClient:
    """
    Initialize Instagram client.

    Requires META_IG_USER_ID or auto-discovers from /me/accounts.
    """
    creds = BrandCredentialLoader(brand)
    ig_user_id = creds.get("META_IG_USER_ID",
                           f"ecommerce/{brand}/meta-ig-user-id")

    if not ig_user_id:
        # Auto-discover: get Pages, find one with instagram_business_account
        logger.debug("Auto-discovering Instagram Business Account ID...")
        result = graph._request(
            "GET", "/me/accounts",
            params={"fields": "id,name,instagram_business_account"})

        for page in result.get("data", []):
            ig_account = page.get("instagram_business_account", {})
            if ig_account.get("id"):
                ig_user_id = ig_account["id"]
                logger.debug("Found Instagram Business Account: %s (from page %s)",
                             ig_user_id, page.get("name"))
                break

    if not ig_user_id:
        raise MetaCredentialError(
            "Could not find Instagram Business Account ID.\n"
            "  Set META_IG_USER_ID in your brand .env, or ensure your\n"
            "  Facebook Page has a connected Instagram Business Account.\n"
            f"  Brand: {brand}"
        )

    return InstagramClient(graph, ig_user_id)


def _init_facebook_client(graph: MetaGraphClient, brand: str) -> FacebookPagesClient:
    """
    Initialize Facebook Pages client.

    Requires META_PAGE_ID or auto-discovers from /me/accounts.
    Uses the Page Access Token from /me/accounts for page operations.
    """
    creds = BrandCredentialLoader(brand)
    page_id = creds.get("META_PAGE_ID",
                        f"ecommerce/{brand}/meta-page-id")
    page_token = ""

    # Fetch pages to get page access token
    result = graph._request(
        "GET", "/me/accounts",
        params={"fields": "id,name,access_token"})

    pages = result.get("data", [])

    if page_id:
        # Find matching page and its token
        for page in pages:
            if page.get("id") == page_id:
                page_token = page.get("access_token", "")
                break
    elif pages:
        # Auto-select first page
        first_page = pages[0]
        page_id = first_page.get("id", "")
        page_token = first_page.get("access_token", "")
        logger.debug("Auto-selected Facebook Page: %s (%s)",
                     first_page.get("name"), page_id)

    if not page_id:
        raise MetaCredentialError(
            "Could not find Facebook Page ID.\n"
            "  Set META_PAGE_ID in your brand .env, or ensure your\n"
            "  token has access to at least one Facebook Page.\n"
            f"  Brand: {brand}"
        )

    return FacebookPagesClient(graph, page_id, page_access_token=page_token)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    command = args.command
    handler = ALL_COMMANDS.get(command)
    if not handler:
        parser.print_help()
        return 1

    try:
        # Resolve brand
        brand = _resolve_brand(getattr(args, "brand", None))
        dry_run = getattr(args, "dry_run", False)

        # Build clients container with lazy init
        clients = MetaClients(brand=brand, dry_run=dry_run)

        # Init the base Graph client (always needed)
        graph = _init_graph_client(brand, dry_run)
        clients.graph = graph

        # Init platform-specific clients based on command
        if command in INSTAGRAM_COMMANDS:
            clients.instagram = _init_instagram_client(graph, brand)
        elif command in FACEBOOK_COMMANDS:
            clients.facebook = _init_facebook_client(graph, brand)

        return handler(clients, args)

    except MetaCredentialError as e:
        if args.json:
            _json_output({"error": str(e), "type": "credential_error"})
        else:
            print(f"\n{RED}Credential error.{RESET}\n")
            print(f"{e}")
            print(f"\n{YELLOW}Set credentials in brand .env or macOS Keychain.{RESET}")
            print(f"\nRequired env vars:")
            print(f"  META_ACCESS_TOKEN  - User/Page access token from Meta App Dashboard")
            print(f"  META_IG_USER_ID    - (optional) Instagram Business Account ID")
            print(f"  META_PAGE_ID       - (optional) Facebook Page ID")
            print(f"  META_APP_ID        - (for token exchange) Meta App ID")
            print(f"  META_APP_SECRET    - (for token exchange) Meta App Secret")
        return 1

    except MetaTokenExpiredError as e:
        if args.json:
            _json_output({"error": str(e), "type": "token_expired"})
        else:
            print(f"\n{RED}Token expired.{RESET}\n")
            print(f"{e}")
            print(f"\n{YELLOW}Generate a new token at:  https://developers.facebook.com/tools/explorer/{RESET}")
            print(f"{YELLOW}Or exchange a short-lived token:  meta-api exchange-token --brand <brand> --token <short>{RESET}")
        return 1

    except MetaAuthError as e:
        if args.json:
            _json_output({"error": str(e), "type": "auth_error"})
        else:
            print(f"\n{RED}Authentication error.{RESET}\n")
            print(f"{e}")
        return 1

    except MetaRateLimitError as e:
        if args.json:
            _json_output({"error": str(e), "type": "rate_limit",
                          "retry_after": e.retry_after})
        else:
            print(f"\n{YELLOW}Rate limited.{RESET}")
            print(f"{e}")
            if e.retry_after:
                print(f"Retry after {e.retry_after}s")
        return 1

    except MetaAPIError as e:
        if args.json:
            _json_output({"error": str(e), "type": "api_error",
                          "code": e.code, "subcode": e.subcode,
                          "error_type": e.error_type,
                          "fbtrace_id": e.fbtrace_id})
        else:
            print(f"\n{RED}Meta API error (code={e.code}).{RESET}")
            print(f"{e}")
            if e.fbtrace_id:
                print(f"{DIM}Trace ID: {e.fbtrace_id}{RESET}")
        return 1

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted{RESET}")
        return 130

    except Exception as e:
        logger.debug("Unhandled exception", exc_info=True)
        if args.json:
            _json_output({"error": str(e), "type": "unexpected_error"})
        else:
            print(f"\n{RED}Error: {e}{RESET}")
            if args.verbose:
                import traceback
                traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
