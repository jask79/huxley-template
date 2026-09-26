#!/usr/bin/env python3
"""
Canva Connect API CLI for Huxley

Comprehensive CLI covering the full Canva Connect API surface (12 groups, 43 subcommands):
  - Auth:       OAuth 2.0 with PKCE, token management, introspection
  - Designs:    List, create, get, pages, export formats
  - Editing:    Start/perform/commit/cancel editing transactions
  - Exports:    Create export jobs, poll for completion
  - Imports:    Import from file or URL
  - Assets:     Upload, get, update, delete assets
  - Autofill:   Brand template autofill (Enterprise)
  - Templates:  List/get brand templates and datasets
  - Comments:   Create threads, reply, list replies
  - Folders:    Create, get, update, delete, list items, move
  - Resize:     Create resize jobs (Pro)
  - Users:      Current user info, capabilities, profile

Credentials:
    Loaded from (in priority order):
      1. capsules/example-digital-capsule/.env
      2. Huxley root .env
      3. macOS Keychain (service: canva-client-id / canva-client-secret)
      4. Environment variables (CANVA_CLIENT_ID, CANVA_CLIENT_SECRET)

Dependencies: Python stdlib only (no pip packages).

Version: 0.1.0
"""

import argparse
import base64
import hashlib
import html as html_mod
import http.server
import json
import logging
import os
import re
import secrets
import stat
import sys
import time
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERSION = "0.1.0"
CATALYST_ROOT = Path(__file__).resolve().parent.parent
TOKEN_DIR = Path.home() / ".canva-catalyst"
TOKEN_FILE = TOKEN_DIR / "tokens.json"
OAUTH_CALLBACK_PORT = 3003
OAUTH_REDIRECT_URI = f"http://127.0.0.1:{OAUTH_CALLBACK_PORT}/oauth/redirect"
BASE_URL = "https://api.canva.com/rest/v1"
AUTH_URL = "https://www.canva.com/api/oauth/authorize"
TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
REVOKE_URL = "https://api.canva.com/rest/v1/oauth/revoke"
INTROSPECT_URL = "https://api.canva.com/rest/v1/oauth/introspect"

ALL_SCOPES = [
    "design:content:read", "design:content:write",
    "design:meta:read",
    "asset:read", "asset:write",
    "brandtemplate:meta:read", "brandtemplate:content:read",
    "comment:read", "comment:write",
    "folder:read", "folder:write",
    "profile:read",
]

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

class CanvaError(Exception):
    """Base exception for all Canva errors."""


class CanvaCredentialError(CanvaError):
    """Could not load credentials."""


class CanvaAuthError(CanvaError):
    """Authentication or token error."""


class CanvaAPIError(CanvaError):
    """Canva API returned an error."""

    def __init__(self, message: str, code: str = "", status: int = 0):
        self.code = code
        self.status = status
        super().__init__(message)


class CanvaRateLimitError(CanvaError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: int = 0):
        self.retry_after = retry_after
        super().__init__(message)


class CanvaTokenExpiredError(CanvaAuthError):
    """OAuth token has expired and needs refresh."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DesignSummary:
    id: str
    title: str
    owner: str = ""
    thumbnail_url: str = ""
    created_at: str = ""
    updated_at: str = ""
    urls: Dict[str, str] = field(default_factory=dict)

@dataclass
class DesignDetail:
    id: str
    title: str
    owner: str = ""
    thumbnail_url: str = ""
    created_at: str = ""
    updated_at: str = ""
    urls: Dict[str, str] = field(default_factory=dict)
    page_count: int = 0

@dataclass
class DesignPage:
    index: int
    width: int = 0
    height: int = 0
    thumbnail_url: str = ""

@dataclass
class ExportJob:
    id: str
    status: str
    urls: List[str] = field(default_factory=list)
    error: str = ""

@dataclass
class ImportJob:
    id: str
    status: str
    design_id: str = ""
    error: str = ""

@dataclass
class AssetInfo:
    id: str
    name: str
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    thumbnail_url: str = ""
    mime_type: str = ""

@dataclass
class AssetUploadJob:
    id: str
    status: str
    asset_id: str = ""
    error: str = ""

@dataclass
class AutofillJob:
    id: str
    status: str
    design_id: str = ""
    error: str = ""

@dataclass
class BrandTemplate:
    id: str
    title: str
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    thumbnail_url: str = ""

@dataclass
class CommentThread:
    id: str
    message: str
    author: str = ""
    created_at: str = ""

@dataclass
class CommentReply:
    id: str
    message: str
    author: str = ""
    created_at: str = ""

@dataclass
class FolderInfo:
    id: str
    name: str
    created_at: str = ""
    updated_at: str = ""

@dataclass
class FolderItem:
    id: str
    name: str
    item_type: str = ""
    thumbnail_url: str = ""

@dataclass
class ResizeJob:
    id: str
    status: str
    design_id: str = ""
    error: str = ""

@dataclass
class UserInfo:
    user_id: str
    team_id: str = ""
    display_name: str = ""


# ---------------------------------------------------------------------------
# Display helpers
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


# ---------------------------------------------------------------------------
# Credential Loading
# ---------------------------------------------------------------------------

class CredentialLoader:
    """
    Multi-source credential loader for Canva API credentials.

    Resolution order:
      1. capsules/example-digital-capsule/.env
      2. Huxley root .env
      3. macOS Keychain (service: canva-client-id / canva-client-secret)
      4. Environment variables (CANVA_CLIENT_ID, CANVA_CLIENT_SECRET)
    """

    # Map env var names → Keychain service names
    KEYCHAIN_MAP: Dict[str, str] = {
        "CANVA_CLIENT_ID": "canva-client-id",
        "CANVA_CLIENT_SECRET": "canva-client-secret",
    }

    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._loaded = False

    def _load_env_files(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        # Root .env (lower priority)
        root_env = CATALYST_ROOT / ".env"
        if root_env.is_file():
            self._parse_env(root_env)

        # Capsule .env (higher priority)
        capsule_env = CATALYST_ROOT / "capsules" / "example-digital-capsule" / ".env"
        if capsule_env.is_file():
            self._parse_env(capsule_env)

    def _parse_env(self, path: Path) -> None:
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

    @staticmethod
    def _keychain_get(service: str) -> Optional[str]:
        """Retrieve a password from macOS Keychain by service name."""
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-w"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                logger.debug("Loaded %s from macOS Keychain", service)
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def get(self, env_key: str) -> Optional[str]:
        self._load_env_files()
        # 1-2: .env files
        if env_key in self._cache:
            return self._cache[env_key]
        # 3: macOS Keychain
        keychain_svc = self.KEYCHAIN_MAP.get(env_key)
        if keychain_svc:
            val = self._keychain_get(keychain_svc)
            if val:
                self._cache[env_key] = val  # cache for subsequent calls
                return val
        # 4: Environment variables
        val = os.environ.get(env_key, "").strip()
        return val if val else None

    def require(self, env_key: str, label: str = "") -> str:
        val = self.get(env_key)
        if not val:
            desc = label or env_key
            raise CanvaCredentialError(
                f"Missing credential: {desc}\n"
                f"  Checked: .env files, macOS Keychain, ${env_key}\n"
                f"  Set CANVA_CLIENT_ID and CANVA_CLIENT_SECRET"
            )
        return val


# ---------------------------------------------------------------------------
# Token Storage
# ---------------------------------------------------------------------------

class TokenStore:
    """Manages persistent OAuth token storage at ~/.canva-catalyst/tokens.json."""

    def __init__(self, path: Path = TOKEN_FILE):
        self.path = path

    def _ensure_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)

    def load(self) -> Dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load tokens: %s", e)
            return {}

    def save(self, data: Dict[str, Any]) -> None:
        self._ensure_dir()
        # Open with explicit 0o600 mode to avoid race condition where file
        # is briefly world-readable between creation and chmod.
        fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)

    def clear(self) -> None:
        if self.path.is_file():
            self.path.unlink()

    def get_access_token(self) -> Optional[str]:
        data = self.load()
        return data.get("access_token")

    def get_refresh_token(self) -> Optional[str]:
        data = self.load()
        return data.get("refresh_token")

    def is_expired(self) -> bool:
        data = self.load()
        expires_at = data.get("expires_at", 0)
        if not expires_at:
            return True
        return time.time() >= expires_at - 60  # 60s buffer


# ---------------------------------------------------------------------------
# PKCE Helpers
# ---------------------------------------------------------------------------

def _generate_code_verifier() -> str:
    """Generate a PKCE code verifier (43-128 chars, URL-safe)."""
    return secrets.token_urlsafe(64)[:96]


def _generate_code_challenge(verifier: str) -> str:
    """Generate PKCE code challenge from verifier (SHA-256, base64url)."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# OAuth 2.0 with PKCE
# ---------------------------------------------------------------------------

class CanvaOAuth:
    """OAuth 2.0 Authorization Code flow with PKCE for Canva Connect API."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_store = TokenStore()

    def _basic_auth_header(self) -> str:
        """Generate Basic auth header value."""
        creds = f"{self.client_id}:{self.client_secret}"
        b64 = base64.b64encode(creds.encode("utf-8")).decode("utf-8")
        return f"Basic {b64}"

    def get_auth_url(self, scopes: Optional[List[str]] = None,
                     code_verifier: Optional[str] = None,
                     state: str = "") -> Tuple[str, str]:
        """
        Build authorization URL with PKCE.

        Returns (auth_url, code_verifier).
        """
        if code_verifier is None:
            code_verifier = _generate_code_verifier()
        code_challenge = _generate_code_challenge(code_verifier)

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "scope": " ".join(scopes or ALL_SCOPES),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if state:
            params["state"] = state

        url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
        return url, code_verifier

    def exchange_code(self, code: str, code_verifier: str) -> Dict[str, Any]:
        """Exchange authorization code + PKCE verifier for tokens."""
        body = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": OAUTH_REDIRECT_URI,
        }).encode("utf-8")

        req = urllib.request.Request(
            TOKEN_URL,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": self._basic_auth_header(),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise CanvaAuthError(f"Token exchange failed (HTTP {e.code}): {err_body}")

        if "access_token" not in data:
            raise CanvaAuthError(f"Token exchange failed: {data}")

        # Persist tokens
        token_data = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_in": data.get("expires_in", 14400),
            "expires_at": time.time() + data.get("expires_in", 14400),
            "scope": data.get("scope", ""),
            "token_type": data.get("token_type", "Bearer"),
        }
        self.token_store.save(token_data)
        return token_data

    def refresh_tokens(self) -> Dict[str, Any]:
        """Refresh access token using stored refresh token."""
        refresh_token = self.token_store.get_refresh_token()
        if not refresh_token:
            raise CanvaAuthError("No refresh token found. Run 'auth login' first.")

        body = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }).encode("utf-8")

        req = urllib.request.Request(
            TOKEN_URL,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": self._basic_auth_header(),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise CanvaAuthError(f"Token refresh failed (HTTP {e.code}): {err_body}")

        if "access_token" not in data:
            raise CanvaAuthError(f"Token refresh failed: {data}")

        token_data = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_in": data.get("expires_in", 14400),
            "expires_at": time.time() + data.get("expires_in", 14400),
            "scope": data.get("scope", ""),
            "token_type": data.get("token_type", "Bearer"),
        }
        self.token_store.save(token_data)
        return token_data

    def revoke_tokens(self) -> bool:
        """Revoke current tokens."""
        token = self.token_store.get_access_token()
        if not token:
            return True

        body = urllib.parse.urlencode({
            "token": token,
        }).encode("utf-8")

        req = urllib.request.Request(
            REVOKE_URL,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": self._basic_auth_header(),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
            self.token_store.clear()
            return True
        except urllib.error.HTTPError:
            self.token_store.clear()
            return True

    def ensure_valid_token(self) -> str:
        """Get a valid access token, refreshing if expired."""
        token = self.token_store.get_access_token()
        if not token:
            raise CanvaAuthError("Not authenticated. Run 'auth login' first.")

        if self.token_store.is_expired():
            logger.info("Token expired, refreshing...")
            data = self.refresh_tokens()
            return data["access_token"]

        return token


# ---------------------------------------------------------------------------
# OAuth Callback Server (for auth login)
# ---------------------------------------------------------------------------

class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback code."""

    auth_code: Optional[str] = None
    error: Optional[str] = None
    expected_state: Optional[str] = None

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/oauth/redirect":
            # C2: Validate OAuth state parameter to prevent CSRF
            returned_state = params.get("state", [None])[0]
            if _OAuthCallbackHandler.expected_state and returned_state != _OAuthCallbackHandler.expected_state:
                self.send_response(403)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h2>Authorization failed</h2>"
                    b"<p>Error: Invalid state parameter (possible CSRF attack).</p>"
                    b"</body></html>"
                )
                _OAuthCallbackHandler.error = "state_mismatch"
                return

            if "code" in params:
                _OAuthCallbackHandler.auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h2>Authorization successful!</h2>"
                    b"<p>You can close this tab and return to the terminal.</p>"
                    b"</body></html>"
                )
            else:
                # C1: Escape error value to prevent XSS
                raw_error = params.get("error", ["unknown"])[0]
                _OAuthCallbackHandler.error = raw_error
                safe_error = html_mod.escape(raw_error)
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    f"<html><body><h2>Authorization failed</h2>"
                    f"<p>Error: {safe_error}</p>"
                    f"</body></html>".encode()
                )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP logging unless verbose."""
        logger.debug(format, *args)


def _run_oauth_flow(oauth: CanvaOAuth, scopes: Optional[List[str]] = None) -> Dict[str, Any]:
    """Run the full OAuth browser flow with local callback server."""
    # Reset handler state
    _OAuthCallbackHandler.auth_code = None
    _OAuthCallbackHandler.error = None

    state = secrets.token_urlsafe(16)
    _OAuthCallbackHandler.expected_state = state
    auth_url, code_verifier = oauth.get_auth_url(scopes=scopes, state=state)

    server = http.server.HTTPServer(("127.0.0.1", OAUTH_CALLBACK_PORT), _OAuthCallbackHandler)
    server.timeout = 120

    print(f"\n{BOLD}Canva OAuth Login{RESET}\n")
    print(f"  Opening browser for authorization...")
    print(f"  {DIM}If it doesn't open, visit:{RESET}")
    print(f"  {CYAN}{auth_url}{RESET}\n")
    print(f"  {DIM}Waiting for callback on port {OAUTH_CALLBACK_PORT}...{RESET}")

    webbrowser.open(auth_url)

    # Wait for callback (with timeout)
    deadline = time.time() + 120
    while time.time() < deadline:
        server.handle_request()
        if _OAuthCallbackHandler.auth_code or _OAuthCallbackHandler.error:
            break

    server.server_close()

    if _OAuthCallbackHandler.error:
        raise CanvaAuthError(f"OAuth error: {_OAuthCallbackHandler.error}")

    if not _OAuthCallbackHandler.auth_code:
        raise CanvaAuthError("OAuth timeout: no authorization code received within 120 seconds")

    # Exchange code for tokens
    return oauth.exchange_code(_OAuthCallbackHandler.auth_code, code_verifier)


# ---------------------------------------------------------------------------
# Canva API Client
# ---------------------------------------------------------------------------

class CanvaClient:
    """
    REST client for the Canva Connect API v1.

    Handles Bearer auth, auto-refresh, rate limiting, retries, and dry-run.
    """

    MIN_REQUEST_INTERVAL = 0.2

    def __init__(self, oauth: CanvaOAuth, dry_run: bool = False):
        self.oauth = oauth
        self.dry_run = dry_run
        self._last_request_time: float = 0.0

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
        raw_body: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated request to the Canva API."""
        access_token = self.oauth.ensure_valid_token()

        url = f"{BASE_URL}{path}"
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"

        for attempt in range(max_retries):
            # Rate limiting
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.MIN_REQUEST_INTERVAL:
                time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)

            if self.dry_run and method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
                logger.info("[DRY RUN] %s %s body=%s", method.upper(), path,
                            json.dumps(body, indent=2) if body else "null")
                return {"dry_run": True, "method": method, "path": path}

            req_headers = {
                "Authorization": f"Bearer {access_token}",
            }
            if headers:
                req_headers.update(headers)

            data_bytes: Optional[bytes] = None
            if raw_body is not None:
                data_bytes = raw_body
            elif body is not None:
                data_bytes = json.dumps(body).encode("utf-8")
                req_headers.setdefault("Content-Type", "application/json")

            req = urllib.request.Request(
                url, data=data_bytes, headers=req_headers, method=method.upper()
            )

            logger.debug("%s %s", method.upper(), url)

            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    self._last_request_time = time.time()
                    resp_body = resp.read().decode("utf-8")
                    if not resp_body:
                        return {}
                    return json.loads(resp_body)

            except urllib.error.HTTPError as e:
                self._last_request_time = time.time()
                status_code = e.code

                try:
                    err_body = e.read().decode("utf-8")
                    err_json = json.loads(err_body)
                except Exception:
                    err_json = {}

                if status_code == 401:
                    # Token may have expired mid-request
                    if attempt == 0:
                        logger.info("401 received, refreshing token...")
                        try:
                            data = self.oauth.refresh_tokens()
                            access_token = data["access_token"]
                            continue
                        except CanvaAuthError:
                            pass
                    raise CanvaTokenExpiredError(
                        "Authentication failed. Run 'auth login' or 'auth refresh'."
                    )

                if status_code == 429:
                    retry_after = int(e.headers.get("Retry-After", 2 ** (attempt + 1)))
                    backoff = min(retry_after, 60)
                    logger.warning("429 Rate limited, backing off %ds (attempt %d/%d)",
                                   backoff, attempt + 1, max_retries)
                    time.sleep(backoff)
                    continue

                if status_code >= 500:
                    backoff = min(2 ** attempt, 30)
                    logger.warning("%d Server error, retrying in %ds (attempt %d/%d)",
                                   status_code, backoff, attempt + 1, max_retries)
                    time.sleep(backoff)
                    continue

                err_code = err_json.get("code", "")
                err_msg = err_json.get("message", str(e))
                raise CanvaAPIError(err_msg, code=err_code, status=status_code)

            except urllib.error.URLError as e:
                logger.error("Network error: %s", e)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise CanvaAPIError(f"Network error: {e}")

        raise CanvaAPIError(f"Max retries ({max_retries}) exhausted for {method} {path}")

    # --- Job Polling ---

    def _poll_job(self, path: str, timeout: int = 120,
                  poll_interval: int = 2) -> Dict[str, Any]:
        """Poll an async job until completion or timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self._request("GET", path)
            job = result.get("job", result)
            status = job.get("status", "")
            if status in ("success", "completed", "failed", "error"):
                return result
            logger.debug("Job status: %s, polling again in %ds", status, poll_interval)
            time.sleep(poll_interval)
        raise CanvaAPIError(f"Job timed out after {timeout}s polling {path}")

    # === Design Methods ===

    def list_designs(self, query: str = "", limit: int = 25,
                     continuation: str = "", ownership: str = "",
                     sort_by: str = "") -> Tuple[List[DesignSummary], str]:
        params: Dict[str, str] = {"limit": str(limit)}
        if query:
            params["query"] = query
        if continuation:
            params["continuation"] = continuation
        if ownership:
            params["ownership"] = ownership
        if sort_by:
            params["sort_by"] = sort_by

        result = self._request("GET", "/designs", params=params)
        items = result.get("items", [])
        designs = []
        for d in items:
            designs.append(DesignSummary(
                id=d.get("id", ""),
                title=d.get("title", ""),
                owner=d.get("owner", {}).get("user_id", "") if isinstance(d.get("owner"), dict) else "",
                thumbnail_url=d.get("thumbnail", {}).get("url", "") if isinstance(d.get("thumbnail"), dict) else "",
                created_at=d.get("created_at", ""),
                updated_at=d.get("updated_at", ""),
                urls=d.get("urls", {}),
            ))
        next_token = result.get("continuation", "")
        return designs, next_token

    def create_design(self, title: str = "", design_type: str = "",
                      width: int = 0, height: int = 0,
                      asset_id: str = "") -> DesignDetail:
        body: Dict[str, Any] = {}
        if title:
            body["title"] = title
        if design_type:
            body["design_type"] = {"type": design_type}
        if width and height:
            body["design_type"] = body.get("design_type", {})
            body["design_type"]["type"] = "custom"
            body["design_type"]["width"] = width
            body["design_type"]["height"] = height
        if asset_id:
            body["asset_id"] = asset_id

        result = self._request("POST", "/designs", body=body)
        d = result.get("design", result)
        return DesignDetail(
            id=d.get("id", ""),
            title=d.get("title", ""),
            owner=d.get("owner", {}).get("user_id", "") if isinstance(d.get("owner"), dict) else "",
            thumbnail_url=d.get("thumbnail", {}).get("url", "") if isinstance(d.get("thumbnail"), dict) else "",
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            urls=d.get("urls", {}),
        )

    def get_design(self, design_id: str) -> DesignDetail:
        result = self._request("GET", f"/designs/{design_id}")
        d = result.get("design", result)
        return DesignDetail(
            id=d.get("id", ""),
            title=d.get("title", ""),
            owner=d.get("owner", {}).get("user_id", "") if isinstance(d.get("owner"), dict) else "",
            thumbnail_url=d.get("thumbnail", {}).get("url", "") if isinstance(d.get("thumbnail"), dict) else "",
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            urls=d.get("urls", {}),
        )

    def get_design_pages(self, design_id: str, offset: int = 1,
                         limit: int = 50) -> List[DesignPage]:
        params = {"offset": str(offset), "limit": str(limit)}
        result = self._request("GET", f"/designs/{design_id}/pages", params=params)
        pages = []
        for p in result.get("items", []):
            pages.append(DesignPage(
                index=p.get("index", 0),
                width=p.get("width", 0),
                height=p.get("height", 0),
                thumbnail_url=p.get("thumbnail", {}).get("url", "") if isinstance(p.get("thumbnail"), dict) else "",
            ))
        return pages

    def get_export_formats(self, design_id: str) -> List[Dict[str, Any]]:
        result = self._request("GET", f"/designs/{design_id}/export-formats")
        return result.get("export_formats", [])

    # === Export Methods ===

    def create_export(self, design_id: str, format_type: str = "pdf",
                      pages: Optional[List[int]] = None,
                      quality: str = "",
                      width: int = 0, height: int = 0) -> ExportJob:
        body: Dict[str, Any] = {
            "design_id": design_id,
            "format": {"type": format_type},
        }
        if pages:
            body["pages"] = pages
        if quality:
            body["format"]["quality"] = quality
        if width:
            body["format"]["width"] = width
        if height:
            body["format"]["height"] = height

        result = self._request("POST", "/exports", body=body)
        job = result.get("job", result)
        return ExportJob(
            id=job.get("id", ""),
            status=job.get("status", "in_progress"),
        )

    def get_export(self, export_id: str) -> ExportJob:
        result = self._request("GET", f"/exports/{export_id}")
        job = result.get("job", result)
        urls = []
        for u in job.get("urls", []):
            if isinstance(u, str):
                urls.append(u)
            elif isinstance(u, dict):
                urls.append(u.get("url", ""))
        return ExportJob(
            id=job.get("id", export_id),
            status=job.get("status", ""),
            urls=urls,
            error=job.get("error", {}).get("message", "") if isinstance(job.get("error"), dict) else "",
        )

    def export_and_wait(self, design_id: str, format_type: str = "pdf",
                        pages: Optional[List[int]] = None,
                        quality: str = "", timeout: int = 120,
                        poll_interval: int = 2) -> ExportJob:
        job = self.create_export(design_id, format_type, pages, quality)
        if job.status in ("success", "completed"):
            return job
        result = self._poll_job(f"/exports/{job.id}", timeout, poll_interval)
        return self.get_export(job.id)

    # === Import Methods ===

    def import_from_url(self, url: str, title: str = "") -> ImportJob:
        body: Dict[str, Any] = {"url": url}
        if title:
            body["title"] = title
        result = self._request("POST", "/url-imports", body=body)
        job = result.get("job", result)
        return ImportJob(
            id=job.get("id", ""),
            status=job.get("status", "in_progress"),
        )

    def get_import_job(self, job_id: str, url_import: bool = False) -> ImportJob:
        path = f"/url-imports/{job_id}" if url_import else f"/imports/{job_id}"
        result = self._request("GET", path)
        job = result.get("job", result)
        design = job.get("design", {}) if isinstance(job.get("design"), dict) else {}
        return ImportJob(
            id=job.get("id", job_id),
            status=job.get("status", ""),
            design_id=design.get("id", ""),
            error=job.get("error", {}).get("message", "") if isinstance(job.get("error"), dict) else "",
        )

    # === Asset Methods ===

    def get_asset(self, asset_id: str) -> AssetInfo:
        result = self._request("GET", f"/assets/{asset_id}")
        a = result.get("asset", result)
        return AssetInfo(
            id=a.get("id", asset_id),
            name=a.get("name", ""),
            tags=a.get("tags", []),
            created_at=a.get("created_at", ""),
            updated_at=a.get("updated_at", ""),
            thumbnail_url=a.get("thumbnail", {}).get("url", "") if isinstance(a.get("thumbnail"), dict) else "",
            mime_type=a.get("mime_type", ""),
        )

    def update_asset(self, asset_id: str, name: str = "",
                     tags: Optional[List[str]] = None) -> AssetInfo:
        body: Dict[str, Any] = {}
        if name:
            body["name"] = name
        if tags is not None:
            body["tags"] = tags
        result = self._request("PATCH", f"/assets/{asset_id}", body=body)
        a = result.get("asset", result)
        return AssetInfo(
            id=a.get("id", asset_id),
            name=a.get("name", ""),
            tags=a.get("tags", []),
        )

    def delete_asset(self, asset_id: str) -> bool:
        self._request("DELETE", f"/assets/{asset_id}")
        return True

    def upload_asset_url(self, url: str, name: str = "") -> AssetUploadJob:
        body: Dict[str, Any] = {"url": url}
        if name:
            body["name"] = name
        result = self._request("POST", "/url-asset-uploads", body=body)
        job = result.get("job", result)
        return AssetUploadJob(
            id=job.get("id", ""),
            status=job.get("status", "in_progress"),
        )

    def get_asset_upload_job(self, job_id: str,
                             url_upload: bool = False) -> AssetUploadJob:
        path = f"/url-asset-uploads/{job_id}" if url_upload else f"/asset-uploads/{job_id}"
        result = self._request("GET", path)
        job = result.get("job", result)
        asset = job.get("asset", {}) if isinstance(job.get("asset"), dict) else {}
        return AssetUploadJob(
            id=job.get("id", job_id),
            status=job.get("status", ""),
            asset_id=asset.get("id", ""),
            error=job.get("error", {}).get("message", "") if isinstance(job.get("error"), dict) else "",
        )

    # === Autofill Methods ===

    def create_autofill(self, brand_template_id: str,
                        data: Dict[str, Any],
                        title: str = "") -> AutofillJob:
        body: Dict[str, Any] = {
            "brand_template_id": brand_template_id,
            "data": data,
        }
        if title:
            body["title"] = title
        result = self._request("POST", "/autofills", body=body)
        job = result.get("job", result)
        return AutofillJob(
            id=job.get("id", ""),
            status=job.get("status", "in_progress"),
        )

    def get_autofill_job(self, job_id: str) -> AutofillJob:
        result = self._request("GET", f"/autofills/{job_id}")
        job = result.get("job", result)
        design = job.get("design", {}) if isinstance(job.get("design"), dict) else {}
        return AutofillJob(
            id=job.get("id", job_id),
            status=job.get("status", ""),
            design_id=design.get("id", ""),
            error=job.get("error", {}).get("message", "") if isinstance(job.get("error"), dict) else "",
        )

    # === Brand Template Methods ===

    def list_templates(self, query: str = "", limit: int = 25,
                       continuation: str = "",
                       ownership: str = "",
                       sort_by: str = "",
                       dataset: str = "") -> Tuple[List[BrandTemplate], str]:
        params: Dict[str, str] = {"limit": str(limit)}
        if query:
            params["query"] = query
        if continuation:
            params["continuation"] = continuation
        if ownership:
            params["ownership"] = ownership
        if sort_by:
            params["sort_by"] = sort_by
        if dataset:
            params["dataset"] = dataset

        result = self._request("GET", "/brand-templates", params=params)
        templates = []
        for t in result.get("items", []):
            templates.append(BrandTemplate(
                id=t.get("id", ""),
                title=t.get("title", ""),
                description=t.get("description", ""),
                created_at=t.get("created_at", ""),
                updated_at=t.get("updated_at", ""),
                thumbnail_url=t.get("thumbnail", {}).get("url", "") if isinstance(t.get("thumbnail"), dict) else "",
            ))
        return templates, result.get("continuation", "")

    def get_template(self, template_id: str) -> BrandTemplate:
        result = self._request("GET", f"/brand-templates/{template_id}")
        t = result.get("brand_template", result)
        return BrandTemplate(
            id=t.get("id", template_id),
            title=t.get("title", ""),
            description=t.get("description", ""),
            created_at=t.get("created_at", ""),
            updated_at=t.get("updated_at", ""),
            thumbnail_url=t.get("thumbnail", {}).get("url", "") if isinstance(t.get("thumbnail"), dict) else "",
        )

    def get_template_dataset(self, template_id: str) -> Dict[str, Any]:
        result = self._request("GET", f"/brand-templates/{template_id}/dataset")
        return result.get("dataset", result)

    # === Comment Methods ===

    def create_comment_thread(self, design_id: str, message: str,
                              page_index: Optional[int] = None,
                              x: Optional[float] = None,
                              y: Optional[float] = None) -> CommentThread:
        body: Dict[str, Any] = {"message": message}
        if page_index is not None:
            anchor: Dict[str, Any] = {"type": "page", "page_index": page_index}
            if x is not None and y is not None:
                anchor["position"] = {"x": x, "y": y}
            body["anchor"] = anchor

        result = self._request("POST", f"/designs/{design_id}/comments", body=body)
        t = result.get("thread", result)
        return CommentThread(
            id=t.get("id", ""),
            message=message,
            author=t.get("author", {}).get("user_id", "") if isinstance(t.get("author"), dict) else "",
            created_at=t.get("created_at", ""),
        )

    def get_comment_thread(self, design_id: str,
                           thread_id: str) -> CommentThread:
        result = self._request("GET", f"/designs/{design_id}/comments/{thread_id}")
        t = result.get("thread", result)
        first_msg = t.get("first_message", {})
        return CommentThread(
            id=t.get("id", thread_id),
            message=first_msg.get("message", "") if isinstance(first_msg, dict) else "",
            author=first_msg.get("author", {}).get("user_id", "") if isinstance(first_msg, dict) and isinstance(first_msg.get("author"), dict) else "",
            created_at=t.get("created_at", ""),
        )

    def reply_to_thread(self, design_id: str, thread_id: str,
                        message: str) -> CommentReply:
        body = {"message": message}
        result = self._request(
            "POST", f"/designs/{design_id}/comments/{thread_id}/replies", body=body
        )
        r = result.get("reply", result)
        return CommentReply(
            id=r.get("id", ""),
            message=message,
            author=r.get("author", {}).get("user_id", "") if isinstance(r.get("author"), dict) else "",
            created_at=r.get("created_at", ""),
        )

    def list_replies(self, design_id: str, thread_id: str,
                     limit: int = 50,
                     continuation: str = "") -> Tuple[List[CommentReply], str]:
        params: Dict[str, str] = {"limit": str(limit)}
        if continuation:
            params["continuation"] = continuation
        result = self._request(
            "GET", f"/designs/{design_id}/comments/{thread_id}/replies", params=params
        )
        replies = []
        for r in result.get("items", []):
            replies.append(CommentReply(
                id=r.get("id", ""),
                message=r.get("message", ""),
                author=r.get("author", {}).get("user_id", "") if isinstance(r.get("author"), dict) else "",
                created_at=r.get("created_at", ""),
            ))
        return replies, result.get("continuation", "")

    # === Folder Methods ===

    def create_folder(self, name: str,
                      parent_folder_id: str = "") -> FolderInfo:
        body: Dict[str, Any] = {"name": name}
        if parent_folder_id:
            body["parent_folder_id"] = parent_folder_id
        result = self._request("POST", "/folders", body=body)
        f = result.get("folder", result)
        return FolderInfo(
            id=f.get("id", ""),
            name=f.get("name", name),
            created_at=f.get("created_at", ""),
            updated_at=f.get("updated_at", ""),
        )

    def get_folder(self, folder_id: str) -> FolderInfo:
        result = self._request("GET", f"/folders/{folder_id}")
        f = result.get("folder", result)
        return FolderInfo(
            id=f.get("id", folder_id),
            name=f.get("name", ""),
            created_at=f.get("created_at", ""),
            updated_at=f.get("updated_at", ""),
        )

    def update_folder(self, folder_id: str, name: str) -> FolderInfo:
        body = {"name": name}
        result = self._request("PATCH", f"/folders/{folder_id}", body=body)
        f = result.get("folder", result)
        return FolderInfo(
            id=f.get("id", folder_id),
            name=f.get("name", name),
        )

    def delete_folder(self, folder_id: str) -> bool:
        self._request("DELETE", f"/folders/{folder_id}")
        return True

    def list_folder_items(self, folder_id: str, limit: int = 50,
                          continuation: str = "",
                          item_types: str = "",
                          sort_by: str = "") -> Tuple[List[FolderItem], str]:
        params: Dict[str, str] = {"limit": str(limit)}
        if continuation:
            params["continuation"] = continuation
        if item_types:
            params["item_types"] = item_types
        if sort_by:
            params["sort_by"] = sort_by

        result = self._request("GET", f"/folders/{folder_id}/items", params=params)
        items = []
        for i in result.get("items", []):
            items.append(FolderItem(
                id=i.get("id", ""),
                name=i.get("name", ""),
                item_type=i.get("type", ""),
                thumbnail_url=i.get("thumbnail", {}).get("url", "") if isinstance(i.get("thumbnail"), dict) else "",
            ))
        return items, result.get("continuation", "")

    def move_to_folder(self, item_id: str, to_folder_id: str) -> bool:
        body = {"item_id": item_id, "to_folder_id": to_folder_id}
        self._request("POST", "/folders/move", body=body)
        return True

    # === Editing Methods ===

    def start_editing(self, design_id: str) -> str:
        """Start an editing transaction. Returns transaction_id."""
        body = {"design_id": design_id}
        result = self._request("POST", "/editing/transactions", body=body)
        return result.get("transaction", {}).get("id", result.get("id", ""))

    def perform_editing(self, transaction_id: str,
                        operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform editing operations within a transaction."""
        body = {"operations": operations}
        return self._request(
            "POST", f"/editing/transactions/{transaction_id}/operations", body=body
        )

    def commit_editing(self, transaction_id: str) -> bool:
        """Commit an editing transaction."""
        self._request("POST", f"/editing/transactions/{transaction_id}/commit")
        return True

    def cancel_editing(self, transaction_id: str) -> bool:
        """Cancel an editing transaction."""
        self._request("POST", f"/editing/transactions/{transaction_id}/cancel")
        return True

    # === Resize Methods ===

    def create_resize(self, design_id: str, width: int = 0,
                      height: int = 0,
                      design_type: str = "") -> ResizeJob:
        body: Dict[str, Any] = {"design_id": design_id}
        if width and height:
            body["width"] = width
            body["height"] = height
        if design_type:
            body["design_type"] = design_type
        result = self._request("POST", "/resizes", body=body)
        job = result.get("job", result)
        return ResizeJob(
            id=job.get("id", ""),
            status=job.get("status", "in_progress"),
        )

    def get_resize_job(self, job_id: str) -> ResizeJob:
        result = self._request("GET", f"/resizes/{job_id}")
        job = result.get("job", result)
        design = job.get("design", {}) if isinstance(job.get("design"), dict) else {}
        return ResizeJob(
            id=job.get("id", job_id),
            status=job.get("status", ""),
            design_id=design.get("id", ""),
            error=job.get("error", {}).get("message", "") if isinstance(job.get("error"), dict) else "",
        )

    # === User Methods ===

    def get_user_me(self) -> UserInfo:
        result = self._request("GET", "/users/me")
        return UserInfo(
            user_id=result.get("user_id", result.get("id", "")),
            team_id=result.get("team_id", ""),
            display_name=result.get("display_name", ""),
        )

    def get_capabilities(self) -> Dict[str, Any]:
        return self._request("GET", "/users/me/capabilities")

    def get_profile(self) -> Dict[str, Any]:
        return self._request("GET", "/users/me/profile")


# ---------------------------------------------------------------------------
# Command Handlers - Auth
# ---------------------------------------------------------------------------

def cmd_auth_login(args: argparse.Namespace) -> int:
    """Run OAuth flow to authenticate."""
    creds = CredentialLoader()
    client_id = creds.require("CANVA_CLIENT_ID", "Canva Client ID")
    client_secret = creds.require("CANVA_CLIENT_SECRET", "Canva Client Secret")
    oauth = CanvaOAuth(client_id, client_secret)

    scopes = args.scopes.split(",") if getattr(args, "scopes", None) else None
    data = _run_oauth_flow(oauth, scopes=scopes)

    if args.json:
        _json_output({
            "success": True,
            "token_prefix": data["access_token"][:12] + "...",
            "expires_in": data.get("expires_in", 0),
            "scope": data.get("scope", ""),
        })
    else:
        print(f"\n{GREEN}Authentication successful!{RESET}")
        print(f"  Token:   {data['access_token'][:12]}...")
        print(f"  Expires: {data.get('expires_in', 0)} seconds")
        print(f"  Scopes:  {data.get('scope', 'N/A')}")
        print(f"  Stored:  {TOKEN_FILE}\n")
    return 0


def cmd_auth_logout(args: argparse.Namespace) -> int:
    """Revoke tokens and clear local store."""
    creds = CredentialLoader()
    client_id = creds.require("CANVA_CLIENT_ID", "Canva Client ID")
    client_secret = creds.require("CANVA_CLIENT_SECRET", "Canva Client Secret")
    oauth = CanvaOAuth(client_id, client_secret)

    if args.dry_run:
        print(f"{YELLOW}[DRY RUN] Would revoke tokens and delete {TOKEN_FILE}{RESET}")
        return 0

    oauth.revoke_tokens()

    if args.json:
        _json_output({"success": True, "message": "Tokens revoked and cleared"})
    else:
        print(f"\n{GREEN}Logged out. Tokens revoked and cleared.{RESET}\n")
    return 0


def cmd_auth_status(args: argparse.Namespace) -> int:
    """Show authentication status."""
    store = TokenStore()
    data = store.load()

    if args.json:
        status = {
            "authenticated": bool(data.get("access_token")),
            "expired": store.is_expired(),
            "token_file": str(TOKEN_FILE),
            "expires_at": data.get("expires_at", 0),
            "scope": data.get("scope", ""),
        }
        _json_output(status)
        return 0

    if not data.get("access_token"):
        print(f"\n{YELLOW}Not authenticated.{RESET}")
        print(f"  Run: canva_api.py auth login\n")
        return 1

    expired = store.is_expired()
    status_str = f"{RED}EXPIRED{RESET}" if expired else f"{GREEN}ACTIVE{RESET}"
    expires_at = data.get("expires_at", 0)
    expires_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if expires_at else "unknown"

    print(f"\n{BOLD}Canva Auth Status{RESET}\n")
    print(f"  Status:     {status_str}")
    print(f"  Token:      {data['access_token'][:12]}...")
    print(f"  Expires at: {expires_dt}")
    print(f"  Scopes:     {data.get('scope', 'N/A')}")
    print(f"  Token file: {TOKEN_FILE}")
    if data.get("refresh_token"):
        print(f"  Refresh:    {data['refresh_token'][:12]}...")
    print()
    return 0


def cmd_auth_refresh(args: argparse.Namespace) -> int:
    """Force token refresh."""
    creds = CredentialLoader()
    client_id = creds.require("CANVA_CLIENT_ID", "Canva Client ID")
    client_secret = creds.require("CANVA_CLIENT_SECRET", "Canva Client Secret")
    oauth = CanvaOAuth(client_id, client_secret)

    data = oauth.refresh_tokens()

    if args.json:
        _json_output({
            "success": True,
            "token_prefix": data["access_token"][:12] + "...",
            "expires_in": data.get("expires_in", 0),
        })
    else:
        print(f"\n{GREEN}Token refreshed successfully!{RESET}")
        print(f"  Token:   {data['access_token'][:12]}...")
        print(f"  Expires: {data.get('expires_in', 0)} seconds\n")
    return 0


def cmd_auth_introspect(args: argparse.Namespace) -> int:
    """Introspect the current token to validate it and show metadata."""
    creds = CredentialLoader()
    client_id = creds.require("CANVA_CLIENT_ID", "Canva Client ID")
    client_secret = creds.require("CANVA_CLIENT_SECRET", "Canva Client Secret")

    store = TokenStore()
    token = store.get_access_token()
    if not token:
        if args.json:
            _json_output({"error": "Not authenticated", "type": "auth_error"})
        else:
            print(f"\n{YELLOW}Not authenticated. Run: canva_api.py auth login{RESET}\n")
        return 1

    # Build Basic auth header
    creds_str = f"{client_id}:{client_secret}"
    b64 = base64.b64encode(creds_str.encode("utf-8")).decode("utf-8")

    body = urllib.parse.urlencode({"token": token}).encode("utf-8")
    req = urllib.request.Request(
        INTROSPECT_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {b64}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        if args.json:
            _json_output({"error": f"Introspect failed (HTTP {e.code})", "details": err_body})
        else:
            print(f"\n{RED}Introspect failed (HTTP {e.code}): {err_body}{RESET}\n")
        return 1

    if args.json:
        _json_output(data)
    else:
        active = data.get("active", False)
        status_str = f"{GREEN}ACTIVE{RESET}" if active else f"{RED}INACTIVE{RESET}"
        print(f"\n{BOLD}Token Introspection{RESET}\n")
        print(f"  Active: {status_str}")
        if data.get("scope"):
            print(f"  Scopes: {data['scope']}")
        if data.get("client_id"):
            print(f"  Client: {data['client_id']}")
        if data.get("exp"):
            exp_dt = datetime.fromtimestamp(data["exp"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"  Expires: {exp_dt}")
        # Print any additional fields
        skip_keys = {"active", "scope", "client_id", "exp", "token_type"}
        for k, v in sorted(data.items()):
            if k not in skip_keys:
                print(f"  {k}: {v}")
        print()
    return 0


# ---------------------------------------------------------------------------
# Command Handlers - Designs
# ---------------------------------------------------------------------------

def cmd_designs_list(client: CanvaClient, args: argparse.Namespace) -> int:
    query = getattr(args, "query", "")
    limit = getattr(args, "limit", 25)
    continuation = getattr(args, "continuation", "")
    ownership = getattr(args, "ownership", "")
    sort_by = getattr(args, "sort_by", "")

    all_designs: List[DesignSummary] = []
    fetch_all = getattr(args, "all", False)

    while True:
        designs, next_token = client.list_designs(
            query=query, limit=limit, continuation=continuation,
            ownership=ownership, sort_by=sort_by,
        )
        all_designs.extend(designs)
        if not fetch_all or not next_token:
            break
        continuation = next_token

    if args.json:
        _json_output({
            "designs": [_dc_to_dict(d) for d in all_designs],
            "count": len(all_designs),
            "continuation": next_token if not fetch_all else "",
        })
        return 0

    if not all_designs:
        print(f"\n  {DIM}No designs found{RESET}\n")
        return 0

    print(f"\n{BOLD}Designs{RESET} ({len(all_designs)} shown)\n")
    rows = []
    for d in all_designs:
        rows.append([
            d.id,
            _truncate(d.title or "(untitled)", 35),
            str(d.created_at)[:10] if d.created_at else "",
            str(d.updated_at)[:10] if d.updated_at else "",
        ])
    print(_format_table(["ID", "Title", "Created", "Updated"], rows))
    if not fetch_all and next_token:
        print(f"\n  {DIM}More results available. Use --continuation {next_token}{RESET}")
    print()
    return 0


def cmd_designs_create(client: CanvaClient, args: argparse.Namespace) -> int:
    design = client.create_design(
        title=getattr(args, "title", ""),
        design_type=getattr(args, "design_type", ""),
        width=getattr(args, "width", 0),
        height=getattr(args, "height", 0),
    )

    if args.json:
        _json_output(_dc_to_dict(design))
    else:
        print(f"\n{GREEN}Design created!{RESET}")
        print(f"  ID:    {design.id}")
        print(f"  Title: {design.title or '(untitled)'}")
        if design.urls:
            for k, v in design.urls.items():
                print(f"  {k}: {v}")
        print()
    return 0


def cmd_designs_get(client: CanvaClient, args: argparse.Namespace) -> int:
    design = client.get_design(args.design_id)

    if args.json:
        _json_output(_dc_to_dict(design))
    else:
        print(f"\n{BOLD}Design: {design.title or '(untitled)'}{RESET}\n")
        print(f"  ID:        {design.id}")
        print(f"  Owner:     {design.owner}")
        print(f"  Created:   {design.created_at}")
        print(f"  Updated:   {design.updated_at}")
        if design.thumbnail_url:
            print(f"  Thumbnail: {design.thumbnail_url}")
        if design.urls:
            for k, v in design.urls.items():
                print(f"  {k}: {v}")
        print()
    return 0


def cmd_designs_pages(client: CanvaClient, args: argparse.Namespace) -> int:
    pages = client.get_design_pages(args.design_id)

    if args.json:
        _json_output({"pages": [_dc_to_dict(p) for p in pages]})
        return 0

    if not pages:
        print(f"\n  {DIM}No pages found{RESET}\n")
        return 0

    print(f"\n{BOLD}Pages for design {args.design_id}{RESET}\n")
    rows = []
    for p in pages:
        rows.append([str(p.index), f"{p.width}x{p.height}"])
    print(_format_table(["Page", "Dimensions"], rows))
    print()
    return 0


def cmd_designs_export_formats(client: CanvaClient, args: argparse.Namespace) -> int:
    formats = client.get_export_formats(args.design_id)

    if args.json:
        _json_output({"export_formats": formats})
        return 0

    if not formats:
        print(f"\n  {DIM}No export formats available{RESET}\n")
        return 0

    print(f"\n{BOLD}Export Formats for {args.design_id}{RESET}\n")
    for fmt in formats:
        if isinstance(fmt, dict):
            print(f"  - {fmt.get('type', 'unknown')}")
        else:
            print(f"  - {fmt}")
    print()
    return 0


# ---------------------------------------------------------------------------
# Command Handlers - Editing
# ---------------------------------------------------------------------------

def cmd_edit_start(client: CanvaClient, args: argparse.Namespace) -> int:
    tx_id = client.start_editing(args.design_id)

    if args.json:
        _json_output({"transaction_id": tx_id, "design_id": args.design_id})
    else:
        print(f"\n{GREEN}Editing transaction started{RESET}")
        print(f"  Transaction ID: {tx_id}")
        print(f"  Design ID:      {args.design_id}\n")
    return 0


def cmd_edit_perform(client: CanvaClient, args: argparse.Namespace) -> int:
    ops_file = getattr(args, "ops_file", None)
    if ops_file:
        with open(ops_file, "r") as f:
            operations = json.load(f)
    else:
        print(f"{DIM}Reading operations JSON from stdin...{RESET}")
        operations = json.load(sys.stdin)

    if not isinstance(operations, list):
        operations = [operations]

    result = client.perform_editing(args.transaction_id, operations)

    if args.json:
        _json_output(result)
    else:
        print(f"\n{GREEN}Operations performed on transaction {args.transaction_id}{RESET}\n")
    return 0


def cmd_edit_commit(client: CanvaClient, args: argparse.Namespace) -> int:
    ok = client.commit_editing(args.transaction_id)

    if args.json:
        _json_output({"success": ok, "transaction_id": args.transaction_id})
    else:
        print(f"\n{GREEN}Transaction {args.transaction_id} committed{RESET}\n")
    return 0


def cmd_edit_cancel(client: CanvaClient, args: argparse.Namespace) -> int:
    ok = client.cancel_editing(args.transaction_id)

    if args.json:
        _json_output({"success": ok, "transaction_id": args.transaction_id})
    else:
        print(f"\n{YELLOW}Transaction {args.transaction_id} cancelled{RESET}\n")
    return 0


# ---------------------------------------------------------------------------
# Command Handlers - Exports
# ---------------------------------------------------------------------------

def cmd_exports_create(client: CanvaClient, args: argparse.Namespace) -> int:
    pages = None
    if getattr(args, "pages", None):
        pages = [int(p.strip()) for p in args.pages.split(",")]

    wait = getattr(args, "wait", False)
    fmt = getattr(args, "format", "pdf")
    quality = getattr(args, "quality", "")

    if wait:
        timeout = getattr(args, "timeout", 120)
        poll_interval = getattr(args, "poll_interval", 2)
        job = client.export_and_wait(
            args.design_id, format_type=fmt, pages=pages,
            quality=quality, timeout=timeout, poll_interval=poll_interval,
        )
    else:
        job = client.create_export(args.design_id, format_type=fmt,
                                   pages=pages, quality=quality)

    if args.json:
        _json_output(_dc_to_dict(job))
    else:
        status_color = GREEN if job.status in ("success", "completed") else YELLOW
        print(f"\n{BOLD}Export Job{RESET}")
        print(f"  ID:     {job.id}")
        print(f"  Status: {status_color}{job.status}{RESET}")
        if job.urls:
            print(f"  URLs:")
            for u in job.urls:
                print(f"    {CYAN}{u}{RESET}")
        if job.error:
            print(f"  Error:  {RED}{job.error}{RESET}")
        print()
    return 0


def cmd_exports_get(client: CanvaClient, args: argparse.Namespace) -> int:
    wait = getattr(args, "wait", False)
    if wait:
        timeout = getattr(args, "timeout", 120)
        poll_interval = getattr(args, "poll_interval", 2)
        client._poll_job(f"/exports/{args.export_id}", timeout, poll_interval)

    job = client.get_export(args.export_id)

    if args.json:
        _json_output(_dc_to_dict(job))
    else:
        status_color = GREEN if job.status in ("success", "completed") else YELLOW
        print(f"\n{BOLD}Export: {args.export_id}{RESET}")
        print(f"  Status: {status_color}{job.status}{RESET}")
        if job.urls:
            print(f"  Download URLs:")
            for u in job.urls:
                print(f"    {CYAN}{u}{RESET}")
        if job.error:
            print(f"  Error: {RED}{job.error}{RESET}")
        print()
    return 0


# ---------------------------------------------------------------------------
# Command Handlers - Imports
# ---------------------------------------------------------------------------

def cmd_imports_url(client: CanvaClient, args: argparse.Namespace) -> int:
    job = client.import_from_url(args.url, title=getattr(args, "title", ""))

    wait = getattr(args, "wait", False)
    if wait:
        timeout = getattr(args, "timeout", 120)
        poll_interval = getattr(args, "poll_interval", 2)
        client._poll_job(f"/url-imports/{job.id}", timeout, poll_interval)
        job = client.get_import_job(job.id, url_import=True)

    if args.json:
        _json_output(_dc_to_dict(job))
    else:
        status_color = GREEN if job.status in ("success", "completed") else YELLOW
        print(f"\n{BOLD}Import Job{RESET}")
        print(f"  ID:     {job.id}")
        print(f"  Status: {status_color}{job.status}{RESET}")
        if job.design_id:
            print(f"  Design: {job.design_id}")
        if job.error:
            print(f"  Error:  {RED}{job.error}{RESET}")
        print()
    return 0


def cmd_imports_get(client: CanvaClient, args: argparse.Namespace) -> int:
    url_import = getattr(args, "url_import", False)

    wait = getattr(args, "wait", False)
    if wait:
        timeout = getattr(args, "timeout", 120)
        poll_interval = getattr(args, "poll_interval", 2)
        path = f"/url-imports/{args.job_id}" if url_import else f"/imports/{args.job_id}"
        client._poll_job(path, timeout, poll_interval)

    job = client.get_import_job(args.job_id, url_import=url_import)

    if args.json:
        _json_output(_dc_to_dict(job))
    else:
        status_color = GREEN if job.status in ("success", "completed") else YELLOW
        print(f"\n{BOLD}Import: {args.job_id}{RESET}")
        print(f"  Status:    {status_color}{job.status}{RESET}")
        if job.design_id:
            print(f"  Design ID: {job.design_id}")
        if job.error:
            print(f"  Error:     {RED}{job.error}{RESET}")
        print()
    return 0


# ---------------------------------------------------------------------------
# Command Handlers - Assets
# ---------------------------------------------------------------------------

def cmd_assets_get(client: CanvaClient, args: argparse.Namespace) -> int:
    asset = client.get_asset(args.asset_id)

    if args.json:
        _json_output(_dc_to_dict(asset))
    else:
        print(f"\n{BOLD}Asset: {asset.name or '(unnamed)'}{RESET}\n")
        print(f"  ID:        {asset.id}")
        print(f"  MIME:      {asset.mime_type}")
        print(f"  Tags:      {', '.join(asset.tags) if asset.tags else '(none)'}")
        print(f"  Created:   {asset.created_at}")
        print(f"  Updated:   {asset.updated_at}")
        if asset.thumbnail_url:
            print(f"  Thumbnail: {asset.thumbnail_url}")
        print()
    return 0


def cmd_assets_update(client: CanvaClient, args: argparse.Namespace) -> int:
    tags = args.tags.split(",") if getattr(args, "tags", None) else None
    asset = client.update_asset(
        args.asset_id,
        name=getattr(args, "name", ""),
        tags=tags,
    )

    if args.json:
        _json_output(_dc_to_dict(asset))
    else:
        print(f"\n{GREEN}Asset {args.asset_id} updated{RESET}\n")
    return 0


def cmd_assets_delete(client: CanvaClient, args: argparse.Namespace) -> int:
    if args.dry_run:
        print(f"{YELLOW}[DRY RUN] Would delete asset {args.asset_id}{RESET}")
        return 0

    client.delete_asset(args.asset_id)

    if args.json:
        _json_output({"success": True, "asset_id": args.asset_id})
    else:
        print(f"\n{GREEN}Asset {args.asset_id} deleted (moved to trash){RESET}\n")
    return 0


def cmd_assets_upload_url(client: CanvaClient, args: argparse.Namespace) -> int:
    job = client.upload_asset_url(
        args.url,
        name=getattr(args, "name", ""),
    )

    wait = getattr(args, "wait", False)
    if wait:
        timeout = getattr(args, "timeout", 120)
        poll_interval = getattr(args, "poll_interval", 2)
        client._poll_job(f"/url-asset-uploads/{job.id}", timeout, poll_interval)
        job = client.get_asset_upload_job(job.id, url_upload=True)

    if args.json:
        _json_output(_dc_to_dict(job))
    else:
        status_color = GREEN if job.status in ("success", "completed") else YELLOW
        print(f"\n{BOLD}Asset Upload{RESET}")
        print(f"  Job ID:   {job.id}")
        print(f"  Status:   {status_color}{job.status}{RESET}")
        if job.asset_id:
            print(f"  Asset ID: {job.asset_id}")
        if job.error:
            print(f"  Error:    {RED}{job.error}{RESET}")
        print()
    return 0


def cmd_assets_upload_status(client: CanvaClient, args: argparse.Namespace) -> int:
    url_upload = getattr(args, "url_upload", False)
    job = client.get_asset_upload_job(args.job_id, url_upload=url_upload)

    if args.json:
        _json_output(_dc_to_dict(job))
    else:
        status_color = GREEN if job.status in ("success", "completed") else YELLOW
        print(f"\n{BOLD}Upload Job: {args.job_id}{RESET}")
        print(f"  Status:   {status_color}{job.status}{RESET}")
        if job.asset_id:
            print(f"  Asset ID: {job.asset_id}")
        if job.error:
            print(f"  Error:    {RED}{job.error}{RESET}")
        print()
    return 0


# ---------------------------------------------------------------------------
# Command Handlers - Autofill
# ---------------------------------------------------------------------------

def cmd_autofill_create(client: CanvaClient, args: argparse.Namespace) -> int:
    data_file = getattr(args, "data_file", None)
    if data_file:
        with open(data_file, "r") as f:
            autofill_data = json.load(f)
    else:
        print(f"{DIM}Reading autofill data JSON from stdin...{RESET}")
        autofill_data = json.load(sys.stdin)

    job = client.create_autofill(
        args.brand_template_id,
        data=autofill_data,
        title=getattr(args, "title", ""),
    )

    wait = getattr(args, "wait", False)
    if wait:
        timeout = getattr(args, "timeout", 120)
        poll_interval = getattr(args, "poll_interval", 2)
        client._poll_job(f"/autofills/{job.id}", timeout, poll_interval)
        job = client.get_autofill_job(job.id)

    if args.json:
        _json_output(_dc_to_dict(job))
    else:
        status_color = GREEN if job.status in ("success", "completed") else YELLOW
        print(f"\n{BOLD}Autofill Job{RESET}")
        print(f"  ID:     {job.id}")
        print(f"  Status: {status_color}{job.status}{RESET}")
        if job.design_id:
            print(f"  Design: {job.design_id}")
        if job.error:
            print(f"  Error:  {RED}{job.error}{RESET}")
        print()
    return 0


def cmd_autofill_get(client: CanvaClient, args: argparse.Namespace) -> int:
    job = client.get_autofill_job(args.job_id)

    if args.json:
        _json_output(_dc_to_dict(job))
    else:
        status_color = GREEN if job.status in ("success", "completed") else YELLOW
        print(f"\n{BOLD}Autofill: {args.job_id}{RESET}")
        print(f"  Status:    {status_color}{job.status}{RESET}")
        if job.design_id:
            print(f"  Design ID: {job.design_id}")
        if job.error:
            print(f"  Error:     {RED}{job.error}{RESET}")
        print()
    return 0


# ---------------------------------------------------------------------------
# Command Handlers - Brand Templates
# ---------------------------------------------------------------------------

def cmd_templates_list(client: CanvaClient, args: argparse.Namespace) -> int:
    all_templates: List[BrandTemplate] = []
    continuation = getattr(args, "continuation", "")
    fetch_all = getattr(args, "all", False)
    limit = getattr(args, "limit", 25)

    while True:
        templates, next_token = client.list_templates(
            query=getattr(args, "query", ""),
            limit=limit,
            continuation=continuation,
        )
        all_templates.extend(templates)
        if not fetch_all or not next_token:
            break
        continuation = next_token

    if args.json:
        _json_output({
            "templates": [_dc_to_dict(t) for t in all_templates],
            "count": len(all_templates),
        })
        return 0

    if not all_templates:
        print(f"\n  {DIM}No brand templates found{RESET}\n")
        return 0

    print(f"\n{BOLD}Brand Templates{RESET} ({len(all_templates)} shown)\n")
    rows = []
    for t in all_templates:
        rows.append([t.id, _truncate(t.title, 40), t.created_at[:10] if t.created_at else ""])
    print(_format_table(["ID", "Title", "Created"], rows))
    print()
    return 0


def cmd_templates_get(client: CanvaClient, args: argparse.Namespace) -> int:
    tmpl = client.get_template(args.template_id)

    if args.json:
        _json_output(_dc_to_dict(tmpl))
    else:
        print(f"\n{BOLD}Template: {tmpl.title or '(untitled)'}{RESET}\n")
        print(f"  ID:          {tmpl.id}")
        print(f"  Description: {tmpl.description or '(none)'}")
        print(f"  Created:     {tmpl.created_at}")
        print(f"  Updated:     {tmpl.updated_at}")
        if tmpl.thumbnail_url:
            print(f"  Thumbnail:   {tmpl.thumbnail_url}")
        print()
    return 0


def cmd_templates_dataset(client: CanvaClient, args: argparse.Namespace) -> int:
    dataset = client.get_template_dataset(args.template_id)

    if args.json:
        _json_output(dataset)
    else:
        print(f"\n{BOLD}Dataset for template {args.template_id}{RESET}\n")
        if isinstance(dataset, dict):
            for key, val in dataset.items():
                print(f"  {CYAN}{key}{RESET}: {json.dumps(val, indent=4)}")
        else:
            print(f"  {json.dumps(dataset, indent=2)}")
        print()
    return 0


# ---------------------------------------------------------------------------
# Command Handlers - Comments
# ---------------------------------------------------------------------------

def cmd_comments_create(client: CanvaClient, args: argparse.Namespace) -> int:
    page = getattr(args, "page", None)
    x = getattr(args, "x", None)
    y = getattr(args, "y", None)
    page_int = int(page) if page is not None else None
    x_float = float(x) if x is not None else None
    y_float = float(y) if y is not None else None

    thread = client.create_comment_thread(
        args.design_id, args.message,
        page_index=page_int, x=x_float, y=y_float,
    )

    if args.json:
        _json_output(_dc_to_dict(thread))
    else:
        print(f"\n{GREEN}Comment created{RESET}")
        print(f"  Thread ID: {thread.id}")
        print(f"  Message:   {_truncate(thread.message, 60)}\n")
    return 0


def cmd_comments_get(client: CanvaClient, args: argparse.Namespace) -> int:
    thread = client.get_comment_thread(args.design_id, args.thread_id)

    if args.json:
        _json_output(_dc_to_dict(thread))
    else:
        print(f"\n{BOLD}Comment Thread: {args.thread_id}{RESET}\n")
        print(f"  Message:  {thread.message}")
        print(f"  Author:   {thread.author}")
        print(f"  Created:  {thread.created_at}\n")
    return 0


def cmd_comments_reply(client: CanvaClient, args: argparse.Namespace) -> int:
    reply = client.reply_to_thread(args.design_id, args.thread_id, args.message)

    if args.json:
        _json_output(_dc_to_dict(reply))
    else:
        print(f"\n{GREEN}Reply posted{RESET}")
        print(f"  Reply ID: {reply.id}")
        print(f"  Message:  {_truncate(reply.message, 60)}\n")
    return 0


def cmd_comments_list_replies(client: CanvaClient, args: argparse.Namespace) -> int:
    replies, next_token = client.list_replies(
        args.design_id, args.thread_id,
        limit=getattr(args, "limit", 50),
    )

    if args.json:
        _json_output({
            "replies": [_dc_to_dict(r) for r in replies],
            "count": len(replies),
        })
        return 0

    if not replies:
        print(f"\n  {DIM}No replies{RESET}\n")
        return 0

    print(f"\n{BOLD}Replies for thread {args.thread_id}{RESET}\n")
    for r in replies:
        print(f"  [{r.id}] {r.author}: {r.message}")
    print()
    return 0


# ---------------------------------------------------------------------------
# Command Handlers - Folders
# ---------------------------------------------------------------------------

def cmd_folders_create(client: CanvaClient, args: argparse.Namespace) -> int:
    folder = client.create_folder(
        args.name,
        parent_folder_id=getattr(args, "parent_id", ""),
    )

    if args.json:
        _json_output(_dc_to_dict(folder))
    else:
        print(f"\n{GREEN}Folder created{RESET}")
        print(f"  ID:   {folder.id}")
        print(f"  Name: {folder.name}\n")
    return 0


def cmd_folders_get(client: CanvaClient, args: argparse.Namespace) -> int:
    folder = client.get_folder(args.folder_id)

    if args.json:
        _json_output(_dc_to_dict(folder))
    else:
        print(f"\n{BOLD}Folder: {folder.name}{RESET}\n")
        print(f"  ID:      {folder.id}")
        print(f"  Created: {folder.created_at}")
        print(f"  Updated: {folder.updated_at}\n")
    return 0


def cmd_folders_update(client: CanvaClient, args: argparse.Namespace) -> int:
    folder = client.update_folder(args.folder_id, args.name)

    if args.json:
        _json_output(_dc_to_dict(folder))
    else:
        print(f"\n{GREEN}Folder {args.folder_id} renamed to '{folder.name}'{RESET}\n")
    return 0


def cmd_folders_delete(client: CanvaClient, args: argparse.Namespace) -> int:
    if args.dry_run:
        print(f"{YELLOW}[DRY RUN] Would delete folder {args.folder_id}{RESET}")
        return 0

    client.delete_folder(args.folder_id)

    if args.json:
        _json_output({"success": True, "folder_id": args.folder_id})
    else:
        print(f"\n{GREEN}Folder {args.folder_id} deleted{RESET}\n")
    return 0


def cmd_folders_items(client: CanvaClient, args: argparse.Namespace) -> int:
    all_items: List[FolderItem] = []
    continuation = ""
    fetch_all = getattr(args, "all", False)
    limit = getattr(args, "limit", 50)

    while True:
        items, next_token = client.list_folder_items(
            args.folder_id, limit=limit, continuation=continuation,
        )
        all_items.extend(items)
        if not fetch_all or not next_token:
            break
        continuation = next_token

    if args.json:
        _json_output({
            "items": [_dc_to_dict(i) for i in all_items],
            "count": len(all_items),
        })
        return 0

    if not all_items:
        print(f"\n  {DIM}Folder is empty{RESET}\n")
        return 0

    print(f"\n{BOLD}Folder items{RESET} ({len(all_items)} shown)\n")
    rows = []
    for i in all_items:
        rows.append([i.id, _truncate(i.name, 35), i.item_type])
    print(_format_table(["ID", "Name", "Type"], rows))
    print()
    return 0


def cmd_folders_move(client: CanvaClient, args: argparse.Namespace) -> int:
    if args.dry_run:
        print(f"{YELLOW}[DRY RUN] Would move {args.item_id} to folder {args.to_folder_id}{RESET}")
        return 0

    client.move_to_folder(args.item_id, args.to_folder_id)

    if args.json:
        _json_output({"success": True, "item_id": args.item_id, "to_folder_id": args.to_folder_id})
    else:
        print(f"\n{GREEN}Moved {args.item_id} to folder {args.to_folder_id}{RESET}\n")
    return 0


# ---------------------------------------------------------------------------
# Command Handlers - Resize
# ---------------------------------------------------------------------------

def cmd_resize_create(client: CanvaClient, args: argparse.Namespace) -> int:
    job = client.create_resize(
        args.design_id,
        width=getattr(args, "width", 0),
        height=getattr(args, "height", 0),
        design_type=getattr(args, "design_type", ""),
    )

    wait = getattr(args, "wait", False)
    if wait:
        timeout = getattr(args, "timeout", 120)
        poll_interval = getattr(args, "poll_interval", 2)
        client._poll_job(f"/resizes/{job.id}", timeout, poll_interval)
        job = client.get_resize_job(job.id)

    if args.json:
        _json_output(_dc_to_dict(job))
    else:
        status_color = GREEN if job.status in ("success", "completed") else YELLOW
        print(f"\n{BOLD}Resize Job{RESET}")
        print(f"  ID:     {job.id}")
        print(f"  Status: {status_color}{job.status}{RESET}")
        if job.design_id:
            print(f"  Design: {job.design_id}")
        if job.error:
            print(f"  Error:  {RED}{job.error}{RESET}")
        print()
    return 0


def cmd_resize_get(client: CanvaClient, args: argparse.Namespace) -> int:
    job = client.get_resize_job(args.job_id)

    if args.json:
        _json_output(_dc_to_dict(job))
    else:
        status_color = GREEN if job.status in ("success", "completed") else YELLOW
        print(f"\n{BOLD}Resize: {args.job_id}{RESET}")
        print(f"  Status:    {status_color}{job.status}{RESET}")
        if job.design_id:
            print(f"  Design ID: {job.design_id}")
        if job.error:
            print(f"  Error:     {RED}{job.error}{RESET}")
        print()
    return 0


# ---------------------------------------------------------------------------
# Command Handlers - Users
# ---------------------------------------------------------------------------

def cmd_users_me(client: CanvaClient, args: argparse.Namespace) -> int:
    user = client.get_user_me()

    if args.json:
        _json_output(_dc_to_dict(user))
    else:
        print(f"\n{BOLD}Current User{RESET}\n")
        print(f"  User ID:      {user.user_id}")
        print(f"  Team ID:      {user.team_id or '(none)'}")
        print(f"  Display Name: {user.display_name or '(not set)'}\n")
    return 0


def cmd_users_capabilities(client: CanvaClient, args: argparse.Namespace) -> int:
    caps = client.get_capabilities()

    if args.json:
        _json_output(caps)
    else:
        print(f"\n{BOLD}User Capabilities{RESET}\n")
        if isinstance(caps, dict):
            for k, v in sorted(caps.items()):
                print(f"  {k}: {v}")
        else:
            print(f"  {caps}")
        print()
    return 0


def cmd_users_profile(client: CanvaClient, args: argparse.Namespace) -> int:
    profile = client.get_profile()

    if args.json:
        _json_output(profile)
    else:
        print(f"\n{BOLD}User Profile{RESET}\n")
        if isinstance(profile, dict):
            for k, v in sorted(profile.items()):
                print(f"  {k}: {v}")
        else:
            print(f"  {profile}")
        print()
    return 0


# ---------------------------------------------------------------------------
# Argument Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    # Shared parent parser for global flags -- inherited by ALL leaf subparsers
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--json", action="store_true", help="Output as JSON")
    shared.add_argument("--verbose", "-v", action="store_true", help="Verbose debug output")
    shared.add_argument("--dry-run", action="store_true", help="Show what would be done")

    parser = argparse.ArgumentParser(
        prog="canva_api.py",
        description=f"{BOLD}Canva Connect API CLI for Huxley{RESET}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Auth examples:\n"
            "  %(prog)s auth login\n"
            "  %(prog)s auth status\n"
            "  %(prog)s auth refresh\n"
            "  %(prog)s auth logout\n"
            "\n"
            "Design examples:\n"
            "  %(prog)s designs list --limit 10\n"
            "  %(prog)s designs create --title 'My Design' --width 1080 --height 1080\n"
            "  %(prog)s designs get <DESIGN_ID>\n"
            "  %(prog)s designs pages <DESIGN_ID>\n"
            "\n"
            "Export examples:\n"
            "  %(prog)s exports create <DESIGN_ID> --format png --wait\n"
            "  %(prog)s exports get <EXPORT_ID>\n"
            "\n"
            "Asset examples:\n"
            "  %(prog)s assets get <ASSET_ID>\n"
            "  %(prog)s assets upload-url --url https://example.com/image.png --name 'Logo'\n"
            "\n"
            "Folder examples:\n"
            "  %(prog)s folders create --name 'Campaign Assets'\n"
            "  %(prog)s folders items <FOLDER_ID>\n"
            "\n"
            "Credentials loaded from capsules/example-digital-capsule/.env, root .env, macOS Keychain, or env vars.\n"
        ),
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    sub = parser.add_subparsers(dest="group", help="Command groups")

    # ── Auth ──
    auth_parser = sub.add_parser("auth", help="OAuth authentication management")
    auth_sub = auth_parser.add_subparsers(dest="command")

    p = auth_sub.add_parser("login", parents=[shared], help="Run OAuth flow to authenticate")
    p.add_argument("--scopes", help="Comma-separated scopes (default: all)")

    auth_sub.add_parser("logout", parents=[shared], help="Revoke tokens and clear local store")
    auth_sub.add_parser("status", parents=[shared], help="Show current auth status")
    auth_sub.add_parser("refresh", parents=[shared], help="Force token refresh")
    auth_sub.add_parser("introspect", parents=[shared], help="Introspect (validate) current token")

    # ── Designs ──
    designs_parser = sub.add_parser("designs", help="Design management")
    designs_sub = designs_parser.add_subparsers(dest="command")

    p = designs_sub.add_parser("list", parents=[shared], help="List user designs")
    p.add_argument("--query", "-q", default="", help="Search query")
    p.add_argument("--limit", type=int, default=25, help="Results per page (default: 25)")
    p.add_argument("--continuation", default="", help="Pagination token")
    p.add_argument("--all", action="store_true", help="Fetch all pages")
    p.add_argument("--ownership", default="", help="Filter by ownership (any, owned, shared)")
    p.add_argument("--sort-by", default="", help="Sort order (relevance, modified_descending, modified_ascending, title_ascending, title_descending)")

    p = designs_sub.add_parser("create", parents=[shared], help="Create a new design")
    p.add_argument("--title", default="", help="Design title")
    p.add_argument("--design-type", default="", help="Design type preset")
    p.add_argument("--width", type=int, default=0, help="Custom width (px)")
    p.add_argument("--height", type=int, default=0, help="Custom height (px)")

    p = designs_sub.add_parser("get", parents=[shared], help="Get design metadata")
    p.add_argument("design_id", help="Design ID")

    p = designs_sub.add_parser("pages", parents=[shared], help="List pages in a design")
    p.add_argument("design_id", help="Design ID")

    p = designs_sub.add_parser("export-formats", parents=[shared], help="List available export formats")
    p.add_argument("design_id", help="Design ID")

    # ── Editing ──
    edit_parser = sub.add_parser("edit", help="Design editing transactions")
    edit_sub = edit_parser.add_subparsers(dest="command")

    p = edit_sub.add_parser("start", parents=[shared], help="Start editing transaction")
    p.add_argument("design_id", help="Design ID")

    p = edit_sub.add_parser("perform", parents=[shared], help="Perform editing operations")
    p.add_argument("transaction_id", help="Transaction ID")
    p.add_argument("--ops-file", help="JSON file with operations (else reads stdin)")

    p = edit_sub.add_parser("commit", parents=[shared], help="Commit editing transaction")
    p.add_argument("transaction_id", help="Transaction ID")

    p = edit_sub.add_parser("cancel", parents=[shared], help="Cancel editing transaction")
    p.add_argument("transaction_id", help="Transaction ID")

    # ── Exports ──
    exports_parser = sub.add_parser("exports", help="Design export jobs")
    exports_sub = exports_parser.add_subparsers(dest="command")

    p = exports_sub.add_parser("create", parents=[shared], help="Create export job")
    p.add_argument("design_id", help="Design ID to export")
    p.add_argument("--format", default="pdf", choices=["pdf", "png", "jpg", "gif", "pptx", "mp4"],
                   help="Export format (default: pdf)")
    p.add_argument("--pages", default="", help="Comma-separated page indices")
    p.add_argument("--quality", default="", help="Export quality")
    p.add_argument("--wait", action="store_true", help="Wait for completion")
    p.add_argument("--timeout", type=int, default=120, help="Wait timeout in seconds")
    p.add_argument("--poll-interval", type=int, default=2, help="Poll interval in seconds")

    p = exports_sub.add_parser("get", parents=[shared], help="Get export job status")
    p.add_argument("export_id", help="Export job ID")
    p.add_argument("--wait", action="store_true", help="Wait for completion")
    p.add_argument("--timeout", type=int, default=120, help="Wait timeout in seconds")
    p.add_argument("--poll-interval", type=int, default=2, help="Poll interval in seconds")

    # ── Imports ──
    imports_parser = sub.add_parser("imports", help="Design import jobs")
    imports_sub = imports_parser.add_subparsers(dest="command")

    p = imports_sub.add_parser("url", parents=[shared], help="Import design from URL")
    p.add_argument("--url", required=True, help="URL to import from")
    p.add_argument("--title", default="", help="Title for imported design")
    p.add_argument("--wait", action="store_true", help="Wait for completion")
    p.add_argument("--timeout", type=int, default=120, help="Wait timeout in seconds")
    p.add_argument("--poll-interval", type=int, default=2, help="Poll interval in seconds")

    p = imports_sub.add_parser("get", parents=[shared], help="Get import job status")
    p.add_argument("job_id", help="Import job ID")
    p.add_argument("--url-import", action="store_true", help="Job was a URL import")
    p.add_argument("--wait", action="store_true", help="Wait for completion")
    p.add_argument("--timeout", type=int, default=120, help="Wait timeout in seconds")
    p.add_argument("--poll-interval", type=int, default=2, help="Poll interval in seconds")

    # ── Assets ──
    assets_parser = sub.add_parser("assets", help="Asset management")
    assets_sub = assets_parser.add_subparsers(dest="command")

    p = assets_sub.add_parser("get", parents=[shared], help="Get asset metadata")
    p.add_argument("asset_id", help="Asset ID")

    p = assets_sub.add_parser("update", parents=[shared], help="Update asset name/tags")
    p.add_argument("asset_id", help="Asset ID")
    p.add_argument("--name", default="", help="New name")
    p.add_argument("--tags", default="", help="Comma-separated tags")

    p = assets_sub.add_parser("delete", parents=[shared], help="Delete asset (moves to trash)")
    p.add_argument("asset_id", help="Asset ID")

    p = assets_sub.add_parser("upload-url", parents=[shared], help="Upload asset from URL")
    p.add_argument("--url", required=True, help="URL of asset to upload")
    p.add_argument("--name", default="", help="Asset name")
    p.add_argument("--wait", action="store_true", help="Wait for completion")
    p.add_argument("--timeout", type=int, default=120, help="Wait timeout in seconds")
    p.add_argument("--poll-interval", type=int, default=2, help="Poll interval in seconds")

    p = assets_sub.add_parser("upload-status", parents=[shared], help="Get upload job status")
    p.add_argument("job_id", help="Upload job ID")
    p.add_argument("--url-upload", action="store_true", help="Job was a URL upload")

    # ── Autofill ──
    autofill_parser = sub.add_parser("autofill", help="Brand template autofill (Enterprise)")
    autofill_sub = autofill_parser.add_subparsers(dest="command")

    p = autofill_sub.add_parser("create", parents=[shared], help="Create autofill job")
    p.add_argument("brand_template_id", help="Brand template ID")
    p.add_argument("--data-file", help="JSON file with autofill data (else reads stdin)")
    p.add_argument("--title", default="", help="Title for autofilled design")
    p.add_argument("--wait", action="store_true", help="Wait for completion")
    p.add_argument("--timeout", type=int, default=120, help="Wait timeout in seconds")
    p.add_argument("--poll-interval", type=int, default=2, help="Poll interval in seconds")

    p = autofill_sub.add_parser("get", parents=[shared], help="Get autofill job status")
    p.add_argument("job_id", help="Autofill job ID")

    # ── Templates ──
    templates_parser = sub.add_parser("templates", help="Brand templates (Enterprise)")
    templates_sub = templates_parser.add_subparsers(dest="command")

    p = templates_sub.add_parser("list", parents=[shared], help="List brand templates")
    p.add_argument("--query", "-q", default="", help="Search query")
    p.add_argument("--limit", type=int, default=25, help="Results per page")
    p.add_argument("--continuation", default="", help="Pagination token")
    p.add_argument("--all", action="store_true", help="Fetch all pages")

    p = templates_sub.add_parser("get", parents=[shared], help="Get brand template metadata")
    p.add_argument("template_id", help="Brand template ID")

    p = templates_sub.add_parser("dataset", parents=[shared], help="Get template dataset (autofill fields)")
    p.add_argument("template_id", help="Brand template ID")

    # ── Comments ──
    comments_parser = sub.add_parser("comments", help="Design comments and threads")
    comments_sub = comments_parser.add_subparsers(dest="command")

    p = comments_sub.add_parser("create", parents=[shared], help="Create comment thread")
    p.add_argument("design_id", help="Design ID")
    p.add_argument("--message", "-m", required=True, help="Comment message")
    p.add_argument("--page", type=int, default=None, help="Page index for anchor")
    p.add_argument("--x", type=float, default=None, help="X position for anchor")
    p.add_argument("--y", type=float, default=None, help="Y position for anchor")

    p = comments_sub.add_parser("get", parents=[shared], help="Get comment thread")
    p.add_argument("design_id", help="Design ID")
    p.add_argument("thread_id", help="Thread ID")

    p = comments_sub.add_parser("reply", parents=[shared], help="Reply to comment thread")
    p.add_argument("design_id", help="Design ID")
    p.add_argument("thread_id", help="Thread ID")
    p.add_argument("--message", "-m", required=True, help="Reply message")

    p = comments_sub.add_parser("list-replies", parents=[shared], help="List replies in a thread")
    p.add_argument("design_id", help="Design ID")
    p.add_argument("thread_id", help="Thread ID")
    p.add_argument("--limit", type=int, default=50, help="Max replies")

    # ── Folders ──
    folders_parser = sub.add_parser("folders", help="Folder management")
    folders_sub = folders_parser.add_subparsers(dest="command")

    p = folders_sub.add_parser("create", parents=[shared], help="Create folder")
    p.add_argument("--name", required=True, help="Folder name")
    p.add_argument("--parent-id", default="", help="Parent folder ID")

    p = folders_sub.add_parser("get", parents=[shared], help="Get folder details")
    p.add_argument("folder_id", help="Folder ID")

    p = folders_sub.add_parser("update", parents=[shared], help="Update folder name")
    p.add_argument("folder_id", help="Folder ID")
    p.add_argument("--name", required=True, help="New folder name")

    p = folders_sub.add_parser("delete", parents=[shared], help="Delete folder")
    p.add_argument("folder_id", help="Folder ID")

    p = folders_sub.add_parser("items", parents=[shared], help="List folder items")
    p.add_argument("folder_id", help="Folder ID")
    p.add_argument("--limit", type=int, default=50, help="Results per page")
    p.add_argument("--all", action="store_true", help="Fetch all pages")

    p = folders_sub.add_parser("move", parents=[shared], help="Move item to folder")
    p.add_argument("--item-id", required=True, help="Item ID to move")
    p.add_argument("--to-folder-id", required=True, help="Target folder ID")

    # ── Resize ──
    resize_parser = sub.add_parser("resize", help="Design resize (Pro)")
    resize_sub = resize_parser.add_subparsers(dest="command")

    p = resize_sub.add_parser("create", parents=[shared], help="Create resize job")
    p.add_argument("design_id", help="Design ID to resize")
    p.add_argument("--width", type=int, default=0, help="New width (px)")
    p.add_argument("--height", type=int, default=0, help="New height (px)")
    p.add_argument("--design-type", default="", help="Preset design type")
    p.add_argument("--wait", action="store_true", help="Wait for completion")
    p.add_argument("--timeout", type=int, default=120, help="Wait timeout in seconds")
    p.add_argument("--poll-interval", type=int, default=2, help="Poll interval in seconds")

    p = resize_sub.add_parser("get", parents=[shared], help="Get resize job status")
    p.add_argument("job_id", help="Resize job ID")

    # ── Users ──
    users_parser = sub.add_parser("users", help="User information")
    users_sub = users_parser.add_subparsers(dest="command")

    users_sub.add_parser("me", parents=[shared], help="Get current user info")
    users_sub.add_parser("capabilities", parents=[shared], help="List user capabilities")
    users_sub.add_parser("profile", parents=[shared], help="Get user profile")

    return parser


# ---------------------------------------------------------------------------
# Command Dispatch
# ---------------------------------------------------------------------------

# Auth commands do not require API client
AUTH_HANDLERS = {
    ("auth", "login"): cmd_auth_login,
    ("auth", "logout"): cmd_auth_logout,
    ("auth", "status"): cmd_auth_status,
    ("auth", "refresh"): cmd_auth_refresh,
    ("auth", "introspect"): cmd_auth_introspect,
}

# All other commands require an authenticated CanvaClient
CLIENT_HANDLERS: Dict[Tuple[str, str], Callable] = {
    ("designs", "list"): cmd_designs_list,
    ("designs", "create"): cmd_designs_create,
    ("designs", "get"): cmd_designs_get,
    ("designs", "pages"): cmd_designs_pages,
    ("designs", "export-formats"): cmd_designs_export_formats,
    ("edit", "start"): cmd_edit_start,
    ("edit", "perform"): cmd_edit_perform,
    ("edit", "commit"): cmd_edit_commit,
    ("edit", "cancel"): cmd_edit_cancel,
    ("exports", "create"): cmd_exports_create,
    ("exports", "get"): cmd_exports_get,
    ("imports", "url"): cmd_imports_url,
    ("imports", "get"): cmd_imports_get,
    ("assets", "get"): cmd_assets_get,
    ("assets", "update"): cmd_assets_update,
    ("assets", "delete"): cmd_assets_delete,
    ("assets", "upload-url"): cmd_assets_upload_url,
    ("assets", "upload-status"): cmd_assets_upload_status,
    ("autofill", "create"): cmd_autofill_create,
    ("autofill", "get"): cmd_autofill_get,
    ("templates", "list"): cmd_templates_list,
    ("templates", "get"): cmd_templates_get,
    ("templates", "dataset"): cmd_templates_dataset,
    ("comments", "create"): cmd_comments_create,
    ("comments", "get"): cmd_comments_get,
    ("comments", "reply"): cmd_comments_reply,
    ("comments", "list-replies"): cmd_comments_list_replies,
    ("folders", "create"): cmd_folders_create,
    ("folders", "get"): cmd_folders_get,
    ("folders", "update"): cmd_folders_update,
    ("folders", "delete"): cmd_folders_delete,
    ("folders", "items"): cmd_folders_items,
    ("folders", "move"): cmd_folders_move,
    ("resize", "create"): cmd_resize_create,
    ("resize", "get"): cmd_resize_get,
    ("users", "me"): cmd_users_me,
    ("users", "capabilities"): cmd_users_capabilities,
    ("users", "profile"): cmd_users_profile,
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    group = args.group
    command = getattr(args, "command", None)

    if not group:
        parser.print_help()
        return 1

    if not command:
        # Print the group's help
        # Re-parse to get the subparser
        parser.parse_args([group, "--help"])
        return 1

    # Configure logging
    log_level = logging.DEBUG if getattr(args, "verbose", False) else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    key = (group, command)

    try:
        # Auth commands (no client needed)
        if key in AUTH_HANDLERS:
            return AUTH_HANDLERS[key](args)

        # Client commands
        handler = CLIENT_HANDLERS.get(key)
        if not handler:
            print(f"{RED}Unknown command: {group} {command}{RESET}")
            return 1

        # Initialize client
        creds = CredentialLoader()
        client_id = creds.require("CANVA_CLIENT_ID", "Canva Client ID")
        client_secret = creds.require("CANVA_CLIENT_SECRET", "Canva Client Secret")
        oauth = CanvaOAuth(client_id, client_secret)
        client = CanvaClient(oauth, dry_run=getattr(args, "dry_run", False))

        return handler(client, args)

    except CanvaCredentialError as e:
        if getattr(args, "json", False):
            _json_output({"error": str(e), "type": "credential_error"})
        else:
            print(f"\n{RED}Credential error.{RESET}\n")
            print(f"{e}")
            print(f"\n{YELLOW}Set CANVA_CLIENT_ID and CANVA_CLIENT_SECRET in .env, Keychain, or environment.{RESET}")
        return 1

    except CanvaTokenExpiredError as e:
        if getattr(args, "json", False):
            _json_output({"error": str(e), "type": "token_expired"})
        else:
            print(f"\n{RED}Token expired.{RESET}\n")
            print(f"{e}")
            print(f"\n{YELLOW}Refresh with: canva_api.py auth refresh{RESET}")
        return 1

    except CanvaAuthError as e:
        if getattr(args, "json", False):
            _json_output({"error": str(e), "type": "auth_error"})
        else:
            print(f"\n{RED}Auth error: {e}{RESET}\n")
        return 1

    except CanvaAPIError as e:
        if getattr(args, "json", False):
            _json_output({"error": str(e), "code": e.code, "status": e.status, "type": "api_error"})
        else:
            print(f"\n{RED}API error: {e}{RESET}")
            if e.code:
                print(f"  Code:   {e.code}")
            if e.status:
                print(f"  Status: {e.status}")
            print()
        return 1

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted.{RESET}")
        return 130

    except Exception as e:
        if getattr(args, "json", False):
            _json_output({"error": str(e), "type": "unexpected_error"})
        else:
            print(f"\n{RED}Unexpected error: {e}{RESET}")
            if getattr(args, "verbose", False):
                import traceback
                traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
