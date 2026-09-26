"""
Google Gemini OAuth Client for the Media Workflow Engine.

Provides OAuth-based authentication with Google's Gemini API for image
generation, using personal Google account credentials instead of API keys.
Uses the Gemini CLI's embedded OAuth client (Google-sanctioned for installed
apps) so no GCP project or billing setup is required.

Token lifecycle:
  - login()  — Opens browser for OAuth consent, saves tokens to disk.
  - status() — Returns token validity info (valid, email, expiry).
  - logout() — Deletes the stored token file.

Image operations:
  - generate_image() — Text-to-image generation via Gemini.
  - edit_image()     — Edit an existing image with a text prompt.

Auth resolution:
  1. Stored OAuth token at ~/.catalyst/gemini-oauth-token.json
  2. Auto-refresh if token is expired but refresh_token is available
  3. If no token, raises GeminiOAuthError with login instructions
"""

from __future__ import annotations

import base64
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from google import genai
from google.genai import types


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Gemini CLI's embedded OAuth client credentials.
# These are public, Google-sanctioned for installed (desktop) apps.
CLIENT_ID = os.environ.get("GEMINI_OAUTH_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GEMINI_OAUTH_CLIENT_SECRET", "")

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
]

TOKEN_PATH = Path.home() / ".catalyst" / "gemini-oauth-token.json"

DEFAULT_MODEL = "gemini-3-pro-image-preview"

# OAuth client config in the format InstalledAppFlow expects.
_CLIENT_CONFIG = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://127.0.0.1"],
    }
}


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class GeminiOAuthError(Exception):
    """Raised when Gemini OAuth authentication or API calls fail."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def login() -> dict[str, Any]:
    """
    Run the OAuth browser flow and save credentials to disk.

    Opens the default browser to Google's consent screen. After the user
    approves, the tokens are saved to TOKEN_PATH with 0600 permissions.

    Returns:
        Dict with keys: email (str or None), expiry (str), token_path (str).

    Raises:
        GeminiOAuthError: If the OAuth flow fails.
    """
    try:
        flow = InstalledAppFlow.from_client_config(_CLIENT_CONFIG, scopes=SCOPES)
        creds = flow.run_local_server(port=0)
    except Exception as exc:
        raise GeminiOAuthError(f"OAuth flow failed: {exc}") from exc

    _save_credentials(creds)

    email = _get_email_from_token(creds)
    expiry = creds.expiry.isoformat() if creds.expiry else "unknown"

    return {
        "email": email,
        "expiry": expiry,
        "token_path": str(TOKEN_PATH),
    }


def status() -> dict[str, Any]:
    """
    Check the current OAuth token status.

    Returns:
        Dict with keys:
          - valid (bool): Whether a usable token exists.
          - email (str or None): Google account email if available.
          - expiry (str or None): Token expiry ISO timestamp.
          - token_path (str): Where the token file would be stored.
          - needs_login (bool): True if login() is required.
    """
    result: dict[str, Any] = {
        "valid": False,
        "email": None,
        "expiry": None,
        "token_path": str(TOKEN_PATH),
        "needs_login": True,
    }

    if not TOKEN_PATH.exists():
        return result

    try:
        creds = _load_credentials()
        # Check for expired token with no refresh capability
        if creds.expiry and creds.expired and not creds.refresh_token:
            result["valid"] = False
            result["needs_login"] = True
        else:
            result["valid"] = True
            result["needs_login"] = False
        result["email"] = _get_email_from_token(creds)
        if creds.expiry:
            result["expiry"] = creds.expiry.isoformat()
    except GeminiOAuthError:
        # Token file exists but is corrupt or refresh failed
        result["valid"] = False
        result["needs_login"] = True

    return result


def logout() -> bool:
    """
    Delete the stored OAuth token file.

    Returns:
        True if a token file was deleted, False if none existed.
    """
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
        return True
    return False


def generate_image(
    prompt: str,
    model: str = DEFAULT_MODEL,
    output_path: str = "output.png",
    aspect_ratio: str = "1:1",
    image_size: str = "2K",
) -> str:
    """
    Generate an image from a text prompt using OAuth-authenticated Gemini.

    Args:
        prompt: The image generation prompt.
        model: Gemini model identifier.
        output_path: Destination file path for the generated PNG.
        aspect_ratio: Image aspect ratio (e.g., "1:1", "16:9", "9:16").
        image_size: Unused by current API but reserved for future use.

    Returns:
        Absolute path to the saved image file.

    Raises:
        GeminiOAuthError: If not authenticated, token refresh fails,
            or image generation fails.
    """
    client = _build_client()

    config = types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
        image_config=types.ImageConfig(
            aspect_ratio=aspect_ratio,
        ),
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
    except Exception as exc:
        raise GeminiOAuthError(f"Image generation failed: {exc}") from exc

    image_bytes = _extract_image_bytes(response)
    return _save_image(image_bytes, output_path)


def edit_image(
    input_path: str,
    prompt: str,
    model: str = DEFAULT_MODEL,
    output_path: str = "output.png",
) -> str:
    """
    Edit an existing image using a text prompt via OAuth-authenticated Gemini.

    Sends the input image alongside the edit prompt so the model uses
    it as the visual context for the edit operation.

    Args:
        input_path: Path to the source image to edit.
        prompt: The edit instruction (e.g., "Remove the background").
        model: Gemini model identifier.
        output_path: Destination file path for the edited PNG.

    Returns:
        Absolute path to the saved image file.

    Raises:
        GeminiOAuthError: If not authenticated or the edit fails.
        FileNotFoundError: If the input image doesn't exist.
    """
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    # Read and encode the input image
    image_data = input_file.read_bytes()
    mime_type = _guess_mime_type(input_file)

    client = _build_client()

    config = types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
    )

    # Build content with inline image + text prompt
    contents = [
        types.Part.from_bytes(data=image_data, mime_type=mime_type),
        prompt,
    ]

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
    except Exception as exc:
        raise GeminiOAuthError(f"Image editing failed: {exc}") from exc

    image_bytes = _extract_image_bytes(response)
    return _save_image(image_bytes, output_path)


# ---------------------------------------------------------------------------
# Internals — credential management
# ---------------------------------------------------------------------------

def _load_credentials() -> Credentials:
    """
    Load OAuth credentials from the token file, auto-refreshing if expired.

    Returns:
        Valid google.oauth2.credentials.Credentials object.

    Raises:
        GeminiOAuthError: If no token file exists, file is corrupt,
            or token refresh fails.
    """
    if not TOKEN_PATH.exists():
        raise GeminiOAuthError(
            "Not authenticated. Run: "
            "python3 tools/media-engine/cli.py gemini-auth login"
        )

    try:
        data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise GeminiOAuthError(
            f"Corrupt token file at {TOKEN_PATH}: {exc}. "
            "Delete it and re-login: "
            "python3 tools/media-engine/cli.py gemini-auth login"
        ) from exc

    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id", CLIENT_ID),
        client_secret=data.get("client_secret", CLIENT_SECRET),
        scopes=data.get("scopes", SCOPES),
    )

    # Restore expiry if present (strip timezone for google-auth compat)
    expiry_str = data.get("expiry")
    if expiry_str:
        try:
            clean = expiry_str.replace("+00:00", "").replace("Z", "")
            creds.expiry = datetime.fromisoformat(clean)
        except (ValueError, TypeError):
            pass

    # Auto-refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_credentials(creds)
        except Exception as exc:
            raise GeminiOAuthError(
                f"Token refresh failed: {exc}. Re-login: "
                "python3 tools/media-engine/cli.py gemini-auth login"
            ) from exc

    if not creds.token:
        raise GeminiOAuthError(
            "No valid access token. Re-login: "
            "python3 tools/media-engine/cli.py gemini-auth login"
        )

    return creds


def _save_credentials(creds: Credentials) -> None:
    """
    Save OAuth credentials to the token file with restricted permissions.

    Creates the ~/.catalyst/ directory if needed. Sets file permissions
    to 0600 (owner read/write only).
    """
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }

    if creds.expiry:
        data["expiry"] = creds.expiry.isoformat()

    TOKEN_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    TOKEN_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600


def _get_email_from_token(creds: Credentials) -> str | None:
    """
    Extract the user's email from the OAuth token info endpoint.

    Makes a lightweight GET to Google's tokeninfo endpoint. Returns None
    on any failure (non-critical — email is informational only).
    """
    if not creds.token:
        return None

    import urllib.request
    import urllib.error

    req = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v1/tokeninfo",
        headers={"Authorization": f"Bearer {creds.token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            info = json.loads(resp.read().decode("utf-8"))
            return info.get("email")
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


# ---------------------------------------------------------------------------
# Internals — client and response handling
# ---------------------------------------------------------------------------

def _build_client() -> genai.Client:
    """
    Build a google.genai.Client using OAuth credentials.

    The google-genai SDK's non-Vertex path requires an api_key to pass
    validation. We provide a placeholder key and inject the real OAuth
    Bearer token via http_options headers. The Authorization header is
    honored by the Gemini API server over the x-goog-api-key header.

    Returns:
        Configured genai.Client ready for API calls.

    Raises:
        GeminiOAuthError: If credentials cannot be loaded.
    """
    creds = _load_credentials()

    client = genai.Client(
        api_key="OAUTH",
        http_options=types.HttpOptions(
            headers={"Authorization": f"Bearer {creds.token}"},
        ),
    )
    return client


def _extract_image_bytes(response: Any) -> bytes:
    """
    Extract raw image bytes from a Gemini generate_content response.

    Iterates over response candidate parts looking for inline_data
    with an image MIME type.

    Returns:
        Raw image bytes (PNG/JPEG).

    Raises:
        GeminiOAuthError: If no image data is found in the response.
    """
    if not response.candidates:
        raise GeminiOAuthError(
            "No candidates in Gemini response. The model may not support "
            "image generation via OAuth, or the prompt was rejected."
        )

    for candidate in response.candidates:
        if not candidate.content or not candidate.content.parts:
            continue
        for part in candidate.content.parts:
            if part.inline_data is not None:
                data = part.inline_data.data
                if isinstance(data, str):
                    # base64-encoded string
                    return base64.b64decode(data)
                elif isinstance(data, bytes):
                    return data

    # Collect any text parts for diagnostic info
    text_parts = []
    for candidate in response.candidates:
        if not candidate.content or not candidate.content.parts:
            continue
        for part in candidate.content.parts:
            if part.text:
                text_parts.append(part.text)

    detail = ""
    if text_parts:
        detail = f" Model responded with text: {text_parts[0][:200]}"

    raise GeminiOAuthError(
        f"No image data found in Gemini response.{detail}"
    )


def _save_image(image_bytes: bytes, output_path: str) -> str:
    """
    Write raw image bytes to disk.

    Creates parent directories as needed.

    Args:
        image_bytes: Raw PNG/JPEG data.
        output_path: Destination file path.

    Returns:
        Absolute path to the saved file.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, "wb") as f:
        f.write(image_bytes)

    return str(out.resolve())


def _guess_mime_type(path: Path) -> str:
    """
    Determine MIME type from file extension.

    Args:
        path: File path to check.

    Returns:
        MIME type string (defaults to image/png for unknown extensions).
    """
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mime_map.get(path.suffix.lower(), "image/png")
