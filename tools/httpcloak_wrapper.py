#!/usr/bin/env python3
"""
HTTPCloak Wrapper for Bowser Agent
==================================

Provides TLS-fingerprint-aware HTTP requests that complement Playwright automation.

Use cases:
- Pre-flight bot detection checks
- API requests needing browser fingerprints
- Session keepalive without full browser
- Escalation to Playwright when needed

HTTPCloak mimics browser TLS/HTTP fingerprints (JA3/JA4) to bypass bot detection
without the overhead of launching a full browser.

Usage:
    from tools.httpcloak_wrapper import HTTPCloakClient

    # Simple API request with browser fingerprint
    client = HTTPCloakClient(preset="chrome-143")
    response = client.get("https://api.example.com/data")

    # Pre-flight check before launching Playwright
    needs_browser, reason = client.check_bot_detection("https://site.com")
    if needs_browser:
        # Escalate to Playwright
        pass
    else:
        # Continue with httpcloak
        pass

Author: Huxley
License: MIT
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

# Configure logging
logger = logging.getLogger(__name__)

# Try to import httpcloak, gracefully handle if not installed
try:
    import httpcloak
    HTTPCLOAK_AVAILABLE = True
except ImportError:
    HTTPCLOAK_AVAILABLE = False
    logger.warning(
        "httpcloak not installed. Install with: pip install httpcloak\n"
        "HTTPCloakClient will raise ImportError when instantiated."
    )


# Bot detection markers - patterns that indicate we need a full browser
BOT_DETECTION_MARKERS = {
    # Cloudflare
    "cloudflare_challenge": [
        "Checking your browser",
        "Please wait while we verify",
        "cf-browser-verification",
        "cf_chl_opt",
        "__cf_chl_",
        "challenge-platform",
    ],
    # Cloudflare Turnstile
    "cloudflare_turnstile": [
        "challenges.cloudflare.com",
        "turnstile",
    ],
    # Generic JavaScript challenges
    "js_challenge": [
        "Please enable JavaScript",
        "JavaScript is required",
        "enable-javascript",
        "Your browser does not support JavaScript",
    ],
    # CAPTCHA markers
    "captcha": [
        "g-recaptcha",
        "h-captcha",
        "hcaptcha",
        "recaptcha",
        "captcha",
        "challenge-form",
    ],
    # Bot detection services
    "bot_detection": [
        "PerimeterX",
        "px-captcha",
        "Distil",
        "datadome",
        "imperva",
        "incapsula",
        "akamai",
        "_abck",  # Akamai bot manager cookie pattern
    ],
    # Access denied patterns
    "access_denied": [
        "Access Denied",
        "403 Forbidden",
        "Request blocked",
        "Your access to this site has been limited",
        "Sorry, you have been blocked",
    ],
}

# HTTP status codes that suggest bot detection
BOT_DETECTION_STATUS_CODES = {
    403,  # Forbidden - common for bot blocks
    429,  # Too Many Requests - rate limiting
    503,  # Service Unavailable - often Cloudflare challenge
}


@dataclass
class HTTPCloakResponse:
    """Wrapper for httpcloak response with additional metadata."""

    status_code: int
    headers: Dict[str, str]
    text: str
    content: bytes
    url: str
    protocol: Optional[str] = None
    cookies: Dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Return True if status code is 2xx."""
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        """Parse response body as JSON."""
        return json.loads(self.text)

    @classmethod
    def from_httpcloak_response(cls, response: Any) -> "HTTPCloakResponse":
        """Create HTTPCloakResponse from raw httpcloak response."""
        # Handle cookies - httpcloak returns a list of Cookie objects
        cookies = {}
        if hasattr(response, 'cookies') and response.cookies:
            for cookie in response.cookies:
                if hasattr(cookie, 'name') and hasattr(cookie, 'value'):
                    cookies[cookie.name] = cookie.value

        # Handle headers - httpcloak returns dict with list values
        headers = {}
        if hasattr(response, 'headers') and response.headers:
            for key, value in response.headers.items():
                # httpcloak stores header values as lists, join them
                if isinstance(value, list):
                    headers[key] = ', '.join(value)
                else:
                    headers[key] = str(value)

        return cls(
            status_code=response.status_code,
            headers=headers,
            text=response.text if hasattr(response, 'text') else "",
            content=response.content if hasattr(response, 'content') else b"",
            url=str(response.url) if hasattr(response, 'url') else "",
            protocol=getattr(response, 'protocol', None),
            cookies=cookies,
        )


@dataclass
class BotDetectionResult:
    """Result of bot detection analysis."""

    needs_browser: bool
    reason: str
    detection_type: Optional[str] = None
    confidence: float = 0.0  # 0.0 to 1.0
    markers_found: List[str] = field(default_factory=list)

    def __iter__(self):
        """Allow unpacking as tuple: needs_browser, reason = result."""
        return iter((self.needs_browser, self.reason))


class HTTPCloakClient:
    """
    HTTP client with browser TLS/HTTP fingerprints for anti-detection.

    Uses httpcloak library to mimic browser fingerprints at the TLS and HTTP/2
    protocol levels. This allows making API requests that appear to come from
    a real browser without the overhead of launching Playwright.

    Attributes:
        preset: Browser fingerprint preset (e.g., "chrome-143")
        proxy: Optional proxy URL (http://, socks5://)
        http_version: Force specific HTTP version ("h1", "h2", "h3", or "auto")
        session: Persistent httpcloak session for cookie/state management
    """

    DEFAULT_PRESET = "chrome-143"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        preset: str = DEFAULT_PRESET,
        proxy: Optional[str] = None,
        http_version: str = "auto",
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """
        Initialize HTTPCloak client.

        Args:
            preset: Browser fingerprint preset (e.g., "chrome-143")
            proxy: Optional proxy URL (supports http://, socks5://)
            http_version: HTTP protocol version ("h1", "h2", "h3", or "auto")
            timeout: Request timeout in seconds

        Raises:
            ImportError: If httpcloak is not installed
        """
        if not HTTPCLOAK_AVAILABLE:
            raise ImportError(
                "httpcloak is not installed. Install with: pip install httpcloak"
            )

        self.preset = preset
        self.proxy = proxy
        self.http_version = http_version
        self.timeout = timeout
        self._session: Optional[httpcloak.Session] = None

    @property
    def session(self) -> httpcloak.Session:
        """Get or create the httpcloak session."""
        if self._session is None:
            session_kwargs = {"preset": self.preset}

            if self.proxy:
                session_kwargs["proxy"] = self.proxy

            if self.http_version != "auto":
                session_kwargs["http_version"] = self.http_version

            self._session = httpcloak.Session(**session_kwargs)

        return self._session

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> HTTPCloakResponse:
        """
        Make a GET request with browser fingerprint.

        Uses the session (which has the preset configured) to ensure
        proper TLS fingerprinting.

        Args:
            url: Target URL
            headers: Optional custom headers (merged with fingerprint headers)
            **kwargs: Additional arguments passed to httpcloak

        Returns:
            HTTPCloakResponse with status, headers, body, etc.
        """
        try:
            response = self.session.get(url, headers=headers, **kwargs)
            return HTTPCloakResponse.from_httpcloak_response(response)
        except Exception as e:
            logger.error(f"HTTPCloak GET request failed: {e}")
            raise

    def post(
        self,
        url: str,
        data: Optional[Union[Dict, str, bytes]] = None,
        json: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> HTTPCloakResponse:
        """
        Make a POST request with browser fingerprint.

        Uses the session (which has the preset configured) to ensure
        proper TLS fingerprinting.

        Args:
            url: Target URL
            data: Form data or raw body
            json: JSON data (auto-serialized)
            headers: Optional custom headers
            **kwargs: Additional arguments passed to httpcloak

        Returns:
            HTTPCloakResponse with status, headers, body, etc.
        """
        try:
            response = self.session.post(
                url,
                data=data,
                json=json,
                headers=headers,
                **kwargs,
            )
            return HTTPCloakResponse.from_httpcloak_response(response)
        except Exception as e:
            logger.error(f"HTTPCloak POST request failed: {e}")
            raise

    def session_get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> HTTPCloakResponse:
        """
        Make a GET request using persistent session (maintains cookies/state).

        Note: All requests in HTTPCloakClient use the session for proper
        fingerprinting. This method is an alias for get() for API compatibility.

        Args:
            url: Target URL
            headers: Optional custom headers
            **kwargs: Additional arguments

        Returns:
            HTTPCloakResponse with status, headers, body, etc.
        """
        return self.get(url, headers=headers, **kwargs)

    def session_post(
        self,
        url: str,
        data: Optional[Union[Dict, str, bytes]] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> HTTPCloakResponse:
        """
        Make a POST request using persistent session.

        Note: All requests in HTTPCloakClient use the session for proper
        fingerprinting. This method is an alias for post() for API compatibility.

        Args:
            url: Target URL
            data: Form data or raw body
            json_data: JSON data (auto-serialized)
            headers: Optional custom headers
            **kwargs: Additional arguments

        Returns:
            HTTPCloakResponse with status, headers, body, etc.
        """
        return self.post(url, data=data, json_data=json_data, headers=headers, **kwargs)

    def check_bot_detection(self, url: str) -> BotDetectionResult:
        """
        Pre-flight check to determine if a URL requires full browser automation.

        Makes a lightweight request and analyzes the response for bot detection
        markers (Cloudflare challenge, CAPTCHA, JavaScript requirements, etc.)

        Args:
            url: URL to check for bot detection

        Returns:
            BotDetectionResult with:
                - needs_browser: True if Playwright should be used instead
                - reason: Human-readable explanation
                - detection_type: Category of detection (e.g., "cloudflare_challenge")
                - confidence: 0.0-1.0 confidence score
                - markers_found: List of specific markers detected
        """
        try:
            response = self.get(url)
            return self._analyze_response_for_bot_detection(response)
        except Exception as e:
            # Connection error might indicate IP block or aggressive bot detection
            return BotDetectionResult(
                needs_browser=True,
                reason=f"Connection failed: {e}. May indicate bot detection.",
                detection_type="connection_error",
                confidence=0.7,
            )

    def _analyze_response_for_bot_detection(
        self,
        response: HTTPCloakResponse,
    ) -> BotDetectionResult:
        """
        Analyze HTTP response for bot detection markers.

        Args:
            response: HTTPCloakResponse to analyze

        Returns:
            BotDetectionResult with analysis results
        """
        markers_found = []
        detection_types = []

        # Check status code
        if response.status_code in BOT_DETECTION_STATUS_CODES:
            markers_found.append(f"status_code_{response.status_code}")
            detection_types.append("status_code")

        # Check response body for markers
        body_lower = response.text.lower()

        for detection_type, markers in BOT_DETECTION_MARKERS.items():
            for marker in markers:
                if marker.lower() in body_lower:
                    markers_found.append(marker)
                    if detection_type not in detection_types:
                        detection_types.append(detection_type)

        # Check for minimal/suspicious response
        if len(response.text) < 500 and response.status_code == 200:
            # Very short successful response might be a challenge page
            if any(tag in body_lower for tag in ["<script", "window.location", "redirect"]):
                markers_found.append("suspicious_redirect")
                detection_types.append("js_redirect")

        # Calculate confidence and determine result
        if not markers_found:
            return BotDetectionResult(
                needs_browser=False,
                reason="No bot detection markers found",
                detection_type=None,
                confidence=0.9,
                markers_found=[],
            )

        # Calculate confidence based on markers found
        confidence = min(0.5 + (len(markers_found) * 0.15), 1.0)
        primary_detection = detection_types[0] if detection_types else "unknown"

        # Generate human-readable reason
        reason_parts = []
        if "cloudflare_challenge" in detection_types:
            reason_parts.append("Cloudflare challenge detected")
        if "captcha" in detection_types:
            reason_parts.append("CAPTCHA required")
        if "js_challenge" in detection_types:
            reason_parts.append("JavaScript execution required")
        if "bot_detection" in detection_types:
            reason_parts.append("Bot detection service active")
        if "access_denied" in detection_types:
            reason_parts.append("Access denied/blocked")
        if "status_code" in detection_types and not reason_parts:
            reason_parts.append(f"Suspicious status code: {response.status_code}")

        reason = "; ".join(reason_parts) if reason_parts else f"Bot detection markers: {', '.join(markers_found[:3])}"

        return BotDetectionResult(
            needs_browser=True,
            reason=reason,
            detection_type=primary_detection,
            confidence=confidence,
            markers_found=markers_found,
        )

    def needs_browser(self, response: HTTPCloakResponse) -> Tuple[bool, str]:
        """
        Analyze a response to determine if full browser automation is needed.

        This is a convenience method that wraps _analyze_response_for_bot_detection
        and returns a simple tuple for easy unpacking.

        Args:
            response: HTTPCloakResponse to analyze

        Returns:
            Tuple of (needs_browser: bool, reason: str)
        """
        result = self._analyze_response_for_bot_detection(response)
        return result.needs_browser, result.reason

    def create_session_from_cookies(
        self,
        cookies: Dict[str, str],
        domain: Optional[str] = None,
    ) -> None:
        """
        Initialize session with existing cookies.

        Useful for importing cookies from Playwright or other sources.

        Args:
            cookies: Dictionary of cookie name -> value
            domain: Optional domain to associate cookies with
        """
        # Create fresh session
        self._session = None
        session = self.session

        # Note: httpcloak may have different cookie handling
        # This is a best-effort implementation
        for name, value in cookies.items():
            try:
                # Attempt to set cookies via session
                # Actual implementation depends on httpcloak internals
                if hasattr(session, 'cookies'):
                    session.cookies[name] = value
            except Exception as e:
                logger.warning(f"Failed to set cookie {name}: {e}")

    def export_session_cookies(self) -> Dict[str, str]:
        """
        Export current session cookies for use with Playwright.

        Returns:
            Dictionary of cookie name -> value
        """
        if self._session is None:
            return {}

        try:
            if hasattr(self._session, 'cookies'):
                return dict(self._session.cookies)
        except Exception as e:
            logger.warning(f"Failed to export cookies: {e}")

        return {}

    def save_session(self, filepath: str) -> None:
        """
        Save session state to file for later restoration.

        Args:
            filepath: Path to save session state (JSON format)
        """
        try:
            self.session.save(filepath)
            logger.info(f"Session saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            raise

    def load_session(self, filepath: str) -> None:
        """
        Load session state from file.

        Args:
            filepath: Path to session state file
        """
        try:
            self._session = httpcloak.Session.load(filepath)
            logger.info(f"Session loaded from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            raise

    def set_proxy(self, proxy: str) -> None:
        """
        Change proxy at runtime without creating new session.

        Args:
            proxy: Proxy URL (http://, socks5://)
        """
        self.proxy = proxy
        if self._session is not None:
            try:
                self._session.set_proxy(proxy)
            except Exception as e:
                logger.warning(f"Failed to set proxy on existing session: {e}")
                # Recreate session with new proxy
                self._session = None

    def close(self) -> None:
        """Close the session and release resources."""
        if self._session is not None:
            try:
                if hasattr(self._session, 'close'):
                    self._session.close()
            except Exception:
                pass
            self._session = None


def check_fingerprint(url: str = "https://tls.browserleaks.com/json") -> Dict[str, Any]:
    """
    Utility function to check the TLS fingerprint of HTTPCloak.

    Makes a request to a fingerprint-checking service and returns the results.
    Useful for verifying that HTTPCloak is properly mimicking browser fingerprints.

    Args:
        url: Fingerprint checking service URL

    Returns:
        Dictionary with fingerprint information
    """
    if not HTTPCLOAK_AVAILABLE:
        return {"error": "httpcloak not installed"}

    try:
        client = HTTPCloakClient()
        response = client.get(url)

        if response.ok:
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"raw_response": response.text[:1000]}
        else:
            return {"error": f"Request failed with status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# Convenience functions for quick one-off requests
def get(url: str, preset: str = "chrome-143", **kwargs) -> HTTPCloakResponse:
    """Quick GET request with browser fingerprint."""
    client = HTTPCloakClient(preset=preset)
    try:
        return client.get(url, **kwargs)
    finally:
        client.close()


def post(url: str, preset: str = "chrome-143", **kwargs) -> HTTPCloakResponse:
    """Quick POST request with browser fingerprint."""
    client = HTTPCloakClient(preset=preset)
    try:
        return client.post(url, **kwargs)
    finally:
        client.close()


def check_bot_detection(url: str, preset: str = "chrome-143") -> BotDetectionResult:
    """Quick bot detection check for a URL."""
    client = HTTPCloakClient(preset=preset)
    return client.check_bot_detection(url)


if __name__ == "__main__":
    # Simple test when run directly
    import sys

    if not HTTPCLOAK_AVAILABLE:
        print("ERROR: httpcloak is not installed")
        print("Install with: pip install httpcloak")
        sys.exit(1)

    print("HTTPCloak Wrapper Test")
    print("=" * 50)

    # Test basic functionality
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://httpbin.org/headers"

    print(f"\nTesting URL: {test_url}")

    client = HTTPCloakClient()

    # Test bot detection check
    print("\n1. Bot Detection Check:")
    result = client.check_bot_detection(test_url)
    print(f"   Needs Browser: {result.needs_browser}")
    print(f"   Reason: {result.reason}")
    print(f"   Confidence: {result.confidence:.2f}")

    if not result.needs_browser:
        # Test GET request
        print("\n2. GET Request:")
        response = client.get(test_url)
        print(f"   Status: {response.status_code}")
        print(f"   Protocol: {response.protocol}")
        print(f"   Response length: {len(response.text)} bytes")

    print("\n" + "=" * 50)
    print("Test complete!")
