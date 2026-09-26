"""
Shared AI helper for YouTube Intel — Claude API integration.

Provides a minimal Claude API client using only stdlib (urllib).
API key is read from macOS Keychain (service: anthropic-api-key).

Usage:
    from ai_helper import call_claude

    response = call_claude("Your prompt here", system="You are an expert.")
    if response is None:
        # Fallback to heuristic mode
        ...
"""

import json
import logging
import subprocess
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_API_VERSION = "2023-06-01"
KC_ANTHROPIC_KEY = "anthropic-api-key"


# ---------------------------------------------------------------------------
# Keychain helper (same pattern as client.py)
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_claude(
    prompt: str,
    system: str = "",
    max_tokens: int = 1024,
) -> Optional[str]:
    """
    Call the Anthropic Messages API and return the text response.

    Parameters
    ----------
    prompt : str
        The user message to send.
    system : str
        Optional system prompt.
    max_tokens : int
        Maximum tokens in the response.

    Returns
    -------
    str or None
        The assistant's text response, or None if the call failed
        (missing API key, network error, rate limit, etc.).
    """
    api_key = _keychain_read(KC_ANTHROPIC_KEY)
    if not api_key:
        logger.debug("Anthropic API key not found in Keychain (service: %s)", KC_ANTHROPIC_KEY)
        return None

    # Build the request payload
    payload: dict = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "user", "content": prompt},
        ],
    }
    if system:
        payload["system"] = system

    body = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_API_VERSION,
    }

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=body,
        method="POST",
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # Extract text from the response content blocks
        content_blocks = result.get("content", [])
        text_parts = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        response_text = "\n".join(text_parts).strip()
        if response_text:
            return response_text

        logger.debug("Claude response had no text content: %s", result)
        return None

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass

        if e.code == 401:
            logger.warning("Anthropic API key is invalid (401 Unauthorized)")
        elif e.code == 429:
            logger.warning("Anthropic API rate limited (429)")
        elif e.code == 529:
            logger.warning("Anthropic API overloaded (529)")
        else:
            logger.warning("Anthropic API error (HTTP %d): %s", e.code, error_body[:200])

        return None

    except urllib.error.URLError as e:
        logger.warning("Network error calling Anthropic API: %s", e.reason)
        return None

    except Exception as e:
        logger.warning("Unexpected error calling Anthropic API: %s", e)
        return None
