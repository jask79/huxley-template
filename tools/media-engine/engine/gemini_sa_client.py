"""
Google AI Studio Service Account Client for the Media Workflow Engine.

Provides service-account-based authentication with Google's Gemini API for
image generation. Uses a GCP service account JSON key file — no browser flow,
no token refresh hassle, no personal account coupling.

This is one of three Gemini auth backends:
  - openrouter      — Proxied via OpenRouter (default, paid per-request)
  - gemini_oauth    — Personal Google account OAuth (browser flow)
  - google_ai_studio — GCP Service Account (this module, server-to-server)

Auth resolution:
  1. GOOGLE_APPLICATION_CREDENTIALS env var (standard GCP convention)
  2. Keychain: google-service-account-json-path → file path
  3. Default path: {{HOME_DIR}}/.catalyst/google-service-account.json

Uses direct REST calls with SA bearer tokens against the Generative Language
API. The google-genai SDK requires either an API key or Vertex AI setup; this
module bypasses both by using the REST endpoint directly with OAuth2 bearer
token auth, which the API fully supports.

Image operations:
  - generate_image() — Text-to-image generation via Gemini.
  - edit_image()     — Edit an existing image with a text prompt.
  - status()         — Check service account validity.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2 import service_account


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/generative-language",
]

API_BASE = "https://generativelanguage.googleapis.com/v1beta"

DEFAULT_SA_PATH = Path.home() / ".catalyst" / "google-service-account.json"
DEFAULT_MODEL = "gemini-2.0-flash-exp-image-generation"


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class GeminiServiceAccountError(Exception):
    """Raised when Gemini service account authentication or API calls fail."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def status() -> dict[str, Any]:
    """
    Check the current service account status.

    Returns:
        Dict with keys:
          - valid (bool): Whether a usable service account exists.
          - email (str or None): Service account email.
          - project_id (str or None): GCP project ID.
          - key_path (str or None): Path to the key file.
          - needs_setup (bool): True if no key file found.
    """
    result: dict[str, Any] = {
        "valid": False,
        "email": None,
        "project_id": None,
        "key_path": None,
        "needs_setup": True,
    }

    key_path = _resolve_key_path()
    if not key_path:
        return result

    result["key_path"] = str(key_path)

    try:
        data = json.loads(key_path.read_text(encoding="utf-8"))
        result["email"] = data.get("client_email")
        result["project_id"] = data.get("project_id")
        result["valid"] = True
        result["needs_setup"] = False
    except (json.JSONDecodeError, OSError):
        result["valid"] = False

    return result


def generate_image(
    prompt: str,
    model: str = DEFAULT_MODEL,
    output_path: str = "output.png",
    aspect_ratio: str = "1:1",
    image_size: str = "2K",
) -> str:
    """
    Generate an image from a text prompt using service-account-authenticated Gemini.

    Uses direct REST calls to generativelanguage.googleapis.com with SA bearer
    token auth — bypasses the google-genai SDK's API key requirement.

    Args:
        prompt: The image generation prompt.
        model: Gemini model identifier (without models/ prefix).
        output_path: Destination file path for the generated PNG.
        aspect_ratio: Image aspect ratio (e.g., "1:1", "16:9", "9:16").
        image_size: Unused by current API but reserved for future use.

    Returns:
        Absolute path to the saved image file.

    Raises:
        GeminiServiceAccountError: If not configured, auth fails,
            or image generation fails.
    """
    creds = _load_credentials()

    # Strip models/ prefix if present
    model_name = model.replace("models/", "").replace("google/", "")

    url = f"{API_BASE}/models/{model_name}:generateContent"

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }).encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {creds.token}")
    req.add_header("Content-Type", "application/json")

    try:
        resp = urllib.request.urlopen(req, timeout=120)
        data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode()[:500]
        raise GeminiServiceAccountError(
            f"Image generation failed (HTTP {exc.code}): {error_body}"
        ) from exc
    except Exception as exc:
        raise GeminiServiceAccountError(
            f"Image generation request failed: {exc}"
        ) from exc

    image_bytes = _extract_image_bytes_from_dict(data)
    return _save_image(image_bytes, output_path)


def edit_image(
    input_path: str,
    prompt: str,
    model: str = DEFAULT_MODEL,
    output_path: str = "output.png",
) -> str:
    """
    Edit an existing image using a text prompt via service-account-authenticated Gemini.

    Args:
        input_path: Path to the source image to edit.
        prompt: The edit instruction (e.g., "Remove the background").
        model: Gemini model identifier.
        output_path: Destination file path for the edited PNG.

    Returns:
        Absolute path to the saved image file.

    Raises:
        GeminiServiceAccountError: If not configured or the edit fails.
        FileNotFoundError: If the input image doesn't exist.
    """
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    image_data = base64.b64encode(input_file.read_bytes()).decode()
    mime_type = _guess_mime_type(input_file)
    creds = _load_credentials()

    model_name = model.replace("models/", "").replace("google/", "")
    url = f"{API_BASE}/models/{model_name}:generateContent"

    body = json.dumps({
        "contents": [{
            "parts": [
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": image_data,
                    }
                },
                {"text": prompt},
            ]
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }).encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {creds.token}")
    req.add_header("Content-Type", "application/json")

    try:
        resp = urllib.request.urlopen(req, timeout=120)
        data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode()[:500]
        raise GeminiServiceAccountError(
            f"Image editing failed (HTTP {exc.code}): {error_body}"
        ) from exc
    except Exception as exc:
        raise GeminiServiceAccountError(
            f"Image editing request failed: {exc}"
        ) from exc

    image_bytes = _extract_image_bytes_from_dict(data)
    return _save_image(image_bytes, output_path)


# ---------------------------------------------------------------------------
# Internals — credential management
# ---------------------------------------------------------------------------

def _resolve_key_path() -> Path | None:
    """
    Resolve the service account JSON key file path.

    Resolution order:
      1. GOOGLE_APPLICATION_CREDENTIALS env var
      2. Keychain: google-service-account-json-path
      3. Default: {{HOME_DIR}}/.catalyst/google-service-account.json

    Returns:
        Path to the key file, or None if not found.
    """
    # 1. Environment variable (standard GCP convention)
    env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    # 2. Keychain lookup
    try:
        result = subprocess.run(
            ["security", "find-generic-password",
             "-a", "huxley",
             "-s", "google-service-account-json-path", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            p = Path(result.stdout.strip())
            if p.exists():
                return p
    except Exception:
        pass

    # 3. Default path
    if DEFAULT_SA_PATH.exists():
        return DEFAULT_SA_PATH

    return None


def _load_credentials() -> service_account.Credentials:
    """
    Load service account credentials from the JSON key file.

    Returns:
        Scoped google.oauth2.service_account.Credentials with a valid token.

    Raises:
        GeminiServiceAccountError: If no key file found or credentials invalid.
    """
    key_path = _resolve_key_path()
    if not key_path:
        raise GeminiServiceAccountError(
            "No service account key found. Place your key at:\n"
            f"  {DEFAULT_SA_PATH}\n"
            "  (or {{HOME_DIR}}/.catalyst/google-service-account.json)\n"
            "Or set GOOGLE_APPLICATION_CREDENTIALS env var.\n"
            "Or store the path in Keychain:\n"
            "  security add-generic-password -a huxley "
            "-s google-service-account-json-path -w /path/to/key.json"
        )

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(key_path),
            scopes=SCOPES,
        )
    except Exception as exc:
        raise GeminiServiceAccountError(
            f"Failed to load service account from {key_path}: {exc}"
        ) from exc

    # Request an access token
    try:
        creds.refresh(Request())
    except Exception as exc:
        raise GeminiServiceAccountError(
            f"Failed to obtain access token: {exc}. "
            "Ensure the Generative Language API is enabled in your GCP project "
            "and the service account has appropriate IAM permissions."
        ) from exc

    return creds


# ---------------------------------------------------------------------------
# Internals — response handling
# ---------------------------------------------------------------------------

def _extract_image_bytes_from_dict(data: dict) -> bytes:
    """
    Extract raw image bytes from a Gemini REST API response dict.

    Iterates over response candidate parts looking for inlineData
    with an image MIME type.

    Returns:
        Raw image bytes (PNG/JPEG).

    Raises:
        GeminiServiceAccountError: If no image data is found in the response.
    """
    candidates = data.get("candidates", [])
    if not candidates:
        raise GeminiServiceAccountError(
            "No candidates in Gemini response. The model may not support "
            "image generation, or the prompt was rejected."
        )

    for candidate in candidates:
        parts = candidate.get("content", {}).get("parts", [])
        for part in parts:
            if "inlineData" in part:
                inline = part["inlineData"]
                raw = inline.get("data", "")
                if isinstance(raw, str):
                    return base64.b64decode(raw)
                elif isinstance(raw, bytes):
                    return raw

    # Collect text parts for error context
    text_parts = []
    for candidate in candidates:
        parts = candidate.get("content", {}).get("parts", [])
        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])

    detail = ""
    if text_parts:
        detail = f" Model responded with text: {text_parts[0][:200]}"

    raise GeminiServiceAccountError(
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
