"""
HTTP clients for Sourcerer external APIs.

Provides Easyship (HS code lookup, duty calculation), Freightos (freight
estimates), and exchange rate clients. All HTTP via stdlib urllib — zero
external dependencies.

Auth: Keychain for API tokens (macOS `security find-generic-password`).
"""

import json
import logging
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

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
# Constants
# ---------------------------------------------------------------------------
EASYSHIP_BASE_URL = "https://api.easyship.com"
FREIGHTOS_BASE_URL = "https://www.freightos.com"
EXCHANGE_RATE_BASE_URL = "https://open.er-api.com/v6"

USER_AGENT = "CatalystProductSourcing/0.1.0"
REQUEST_TIMEOUT = 10  # seconds

# Exchange rate cache TTL (seconds)
EXCHANGE_RATE_TTL = 4 * 60 * 60  # 4 hours


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ProductSourcingError(Exception):
    """Base exception."""


class CredentialError(ProductSourcingError):
    """Missing or invalid credentials."""


class APIError(ProductSourcingError):
    """External API returned an error."""

    def __init__(self, message: str, code: int = 0):
        self.code = code
        super().__init__(message)


# ---------------------------------------------------------------------------
# Keychain helper
# ---------------------------------------------------------------------------

def _keychain_get(service: str) -> Optional[str]:
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
# Generic HTTP helper
# ---------------------------------------------------------------------------

def _http_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
    timeout: int = REQUEST_TIMEOUT,
) -> Dict[str, Any]:
    """Make an HTTP request and return parsed JSON response."""
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()
        except Exception:
            pass
        logger.debug("HTTP %d from %s: %s", e.code, url, error_body)
        raise APIError(f"HTTP {e.code}: {error_body[:200]}", code=e.code)
    except urllib.error.URLError as e:
        raise APIError(f"Network error: {e.reason}")
    except Exception as e:
        raise APIError(f"Request failed: {e}")


# ---------------------------------------------------------------------------
# Easyship Client
# ---------------------------------------------------------------------------

class EasyshipClient:
    """
    Client for Easyship API — HS code lookup and duty/tax calculations.

    Auth: Bearer token from Keychain service 'product-sourcing-easyship-token'.
    API docs: https://developers.easyship.com/
    """

    KC_SERVICE = "product-sourcing-easyship-token"

    def __init__(self, token: Optional[str] = None):
        self._token = token or _keychain_get(self.KC_SERVICE)
        if not self._token:
            raise CredentialError(
                f"Easyship API token not found.\n"
                f"  Add to Keychain: security add-generic-password "
                f"-s '{self.KC_SERVICE}' -a huxley -w '<token>' -U"
            )

    def _headers(self) -> Dict[str, str]:
        """Authorization headers for Easyship API."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def lookup_hs_code(self, query: str) -> List[Dict[str, Any]]:
        """
        Look up HS codes by product description.

        Args:
            query: Product description (e.g. 'silicone phone case').

        Returns:
            List of HS code matches with descriptions and duty info.
        """
        params = urllib.parse.urlencode({"query": query})
        url = f"{EASYSHIP_BASE_URL}/2023-01/hs_codes?{params}"
        data = _http_request(url, headers=self._headers())
        return data.get("hs_codes", [])

    def calculate_duties(
        self,
        origin_country: str,
        dest_country: str,
        hs_code: str,
        value: float,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        """
        Calculate import duties and taxes.

        Args:
            origin_country: ISO 3166-1 alpha-2 origin (e.g. 'CN').
            dest_country: ISO 3166-1 alpha-2 destination (e.g. 'US').
            hs_code: Harmonized System code.
            value: Declared value of the goods.
            currency: Currency of the value (default: USD).

        Returns:
            Dict with duty rates, amounts, and tax breakdown.
        """
        url = f"{EASYSHIP_BASE_URL}/2023-01/taxes_and_duties"
        payload = json.dumps({
            "origin_country_alpha2": origin_country,
            "destination_country_alpha2": dest_country,
            "hs_code": hs_code,
            "incoterms": "DDU",
            "insurance": {"is_insured": False},
            "items": [{
                "description": "Product",
                "declared_currency": currency,
                "declared_customs_value": value,
            }],
        }).encode()
        return _http_request(url, method="POST", data=payload, headers=self._headers())


# ---------------------------------------------------------------------------
# Freightos Client
# ---------------------------------------------------------------------------

class FreightosClient:
    """
    Client for Freightos shipping calculator — basic freight estimates.

    No authentication required for public calculator estimates.
    """

    def estimate_freight(
        self,
        origin: str,
        dest: str,
        weight_kg: float,
        dims: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Estimate freight cost between two locations.

        Args:
            origin: Origin location (city, country, or port code).
            dest: Destination location.
            weight_kg: Total weight in kilograms.
            dims: Optional dimensions dict with 'length_cm', 'width_cm', 'height_cm'.

        Returns:
            Dict with estimated freight costs by mode (sea, air, express).
        """
        params: Dict[str, str] = {
            "origin": origin,
            "destination": dest,
            "weight": str(weight_kg),
            "weight_unit": "kg",
        }
        if dims:
            params["length"] = str(dims.get("length_cm", 0))
            params["width"] = str(dims.get("width_cm", 0))
            params["height"] = str(dims.get("height_cm", 0))
            params["dimension_unit"] = "cm"

        query = urllib.parse.urlencode(params)
        url = f"{FREIGHTOS_BASE_URL}/api/shippingCalculator?{query}"
        return _http_request(url)


# ---------------------------------------------------------------------------
# Exchange Rate Client
# ---------------------------------------------------------------------------

class ExchangeRateClient:
    """
    Client for open.er-api.com — free exchange rate data.

    Caches results in SQLite (exchange_rates table) with a 4-hour TTL.
    No authentication required.
    """

    def __init__(self) -> None:
        # Lazy import to avoid circular dependency at module level
        self._db = None

    def _get_db(self):
        """Lazy-load db module."""
        if self._db is None:
            from db import get_connection, get_exchange_rate, set_exchange_rate
            self._db = {
                "get_rate": get_exchange_rate,
                "set_rate": set_exchange_rate,
            }
        return self._db

    def get_rate(self, from_currency: str, to_currency: str) -> float:
        """
        Get exchange rate from one currency to another.

        Checks SQLite cache first (4-hour TTL), then fetches from API.

        Args:
            from_currency: Source currency code (e.g. 'CNY').
            to_currency: Target currency code (e.g. 'USD').

        Returns:
            Exchange rate as a float (e.g. 0.138 for CNY->USD).
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return 1.0

        pair = f"{from_currency}_{to_currency}"

        # Check cache
        db = self._get_db()
        cached = db["get_rate"](pair)
        if cached:
            fetched_at = datetime.fromisoformat(
                cached["fetched_at"].replace("Z", "+00:00")
            )
            age_seconds = (
                datetime.now(timezone.utc) - fetched_at
            ).total_seconds()
            if age_seconds < EXCHANGE_RATE_TTL:
                return cached["rate"]

        # Fetch from API
        url = f"{EXCHANGE_RATE_BASE_URL}/latest/{from_currency}"
        data = _http_request(url)

        rates = data.get("rates", {})
        rate = rates.get(to_currency)
        if rate is None:
            raise APIError(
                f"Exchange rate not found for {from_currency} -> {to_currency}"
            )

        # Cache the result
        db["set_rate"](pair, float(rate))

        return float(rate)
