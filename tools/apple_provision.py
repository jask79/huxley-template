#!/usr/bin/env python3
"""
Apple Developer Provisioning Tool for Huxley

Automates Apple Developer portal provisioning via App Store Connect REST API:
- Register Bundle IDs and enable capabilities
- Create/reuse signing certificates
- Create provisioning profiles (development + distribution)
- Register devices
- Download and install profiles locally

No Fastlane. No browser automation. Direct REST API calls.

Environment variables required:
    ASC_KEY_ID      - API Key ID from App Store Connect
    ASC_ISSUER_ID   - Issuer ID from App Store Connect
    ASC_KEY_PATH    - Path to .p8 private key file (or ASC_KEY_CONTENT)
    ASC_KEY_CONTENT - Raw key content (alternative to ASC_KEY_PATH)

Setup:
    1. Go to App Store Connect > Users and Access > Integrations > Team Keys
    2. Generate an API key with Admin or Developer role
    3. Download the .p8 file (only available once!)
    4. Note the Key ID and Issuer ID
    5. Set environment variables or pass via CLI
"""

import argparse
import base64
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
# Structured result types
# ---------------------------------------------------------------------------

@dataclass
class BundleIdInfo:
    resource_id: str
    identifier: str
    name: str
    platform: str

@dataclass
class CertificateInfo:
    resource_id: str
    name: str
    cert_type: str
    expiration_date: str
    serial_number: str = ""

@dataclass
class DeviceInfo:
    resource_id: str
    name: str
    udid: str
    platform: str
    status: str

@dataclass
class ProfileInfo:
    resource_id: str
    name: str
    profile_type: str
    profile_state: str
    expiration_date: str
    uuid: str = ""

@dataclass
class ProvisioningResult:
    success: bool
    bundle_id: Optional[BundleIdInfo] = None
    capabilities_enabled: List[str] = field(default_factory=list)
    certificate: Optional[CertificateInfo] = None
    dev_profile: Optional[ProfileInfo] = None
    dist_profile: Optional[ProfileInfo] = None
    installed_profiles: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ASCAuth - JWT authentication for App Store Connect API
# ---------------------------------------------------------------------------

class ASCAuth:
    """
    Generates and caches ES256 JWT tokens for App Store Connect API.

    Tries PyJWT first for signing; falls back to openssl CLI if unavailable.
    Tokens are cached and refreshed after 18 minutes (Apple max is 20).
    """

    TOKEN_LIFETIME_SECONDS = 1140       # 19 minutes
    REFRESH_THRESHOLD_SECONDS = 1080    # 18 minutes - refresh before expiry

    def __init__(
        self,
        key_id: Optional[str] = None,
        issuer_id: Optional[str] = None,
        key_path: Optional[str] = None,
        key_content: Optional[str] = None,
    ):
        self.key_id = key_id or os.environ.get("ASC_KEY_ID", "")
        self.issuer_id = issuer_id or os.environ.get("ASC_ISSUER_ID", "")
        self.key_path = key_path or os.environ.get("ASC_KEY_PATH", "")
        self.key_content = key_content or os.environ.get("ASC_KEY_CONTENT", "")

        self._jwt_token: Optional[str] = None
        self._jwt_created_at: float = 0.0
        self._use_pyjwt: Optional[bool] = None

    def validate(self) -> Tuple[bool, List[str]]:
        """Check that all required credentials are present."""
        errors: List[str] = []
        if not self.key_id:
            errors.append("ASC_KEY_ID is not set")
        if not self.issuer_id:
            errors.append("ASC_ISSUER_ID is not set")
        if not self.key_path and not self.key_content:
            errors.append("Neither ASC_KEY_PATH nor ASC_KEY_CONTENT is set")
        if self.key_path and not os.path.isfile(self.key_path):
            errors.append(f"ASC_KEY_PATH file not found: {self.key_path}")
        return (len(errors) == 0, errors)

    def _load_private_key(self) -> str:
        """Load the raw PEM private key content."""
        if self.key_content:
            content = self.key_content
            # Handle escaped newlines from env vars
            if "\\n" in content and "\n" not in content:
                content = content.replace("\\n", "\n")
            # Ensure PEM headers are present
            if ("-----BEGIN " + "PRIVATE KEY-----") not in content:  # split literal: keeps secret scanners quiet
                content = (
                    "-----BEGIN " + "PRIVATE KEY-----\n"
                    + content.strip()
                    + "\n-----END PRIVATE KEY-----\n"
                )
            return content

        with open(self.key_path, "r") as f:
            return f.read()

    def _check_pyjwt(self) -> bool:
        """Determine whether PyJWT with ES256 support is available."""
        if self._use_pyjwt is not None:
            return self._use_pyjwt
        try:
            import jwt as _jwt  # noqa: F401
            from jwt.algorithms import ECAlgorithm  # noqa: F401
            self._use_pyjwt = True
        except (ImportError, AttributeError):
            self._use_pyjwt = False
            logger.info("PyJWT not available, using openssl CLI fallback for JWT signing")
        return self._use_pyjwt

    def _generate_jwt_pyjwt(self, private_key: str) -> str:
        """Generate JWT using PyJWT library."""
        import jwt as pyjwt

        now = int(time.time())
        headers = {
            "alg": "ES256",
            "kid": self.key_id,
            "typ": "JWT",
        }
        payload = {
            "iss": self.issuer_id,
            "iat": now,
            "exp": now + self.TOKEN_LIFETIME_SECONDS,
            "aud": "appstoreconnect-v1",
        }
        token = pyjwt.encode(payload, private_key, algorithm="ES256", headers=headers)
        # PyJWT >= 2.0 returns str; older versions return bytes
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return token

    def _generate_jwt_openssl(self, private_key: str) -> str:
        """Generate JWT using openssl CLI as fallback."""
        import tempfile

        now = int(time.time())

        # Build header and payload
        header = {"alg": "ES256", "kid": self.key_id, "typ": "JWT"}
        payload = {
            "iss": self.issuer_id,
            "iat": now,
            "exp": now + self.TOKEN_LIFETIME_SECONDS,
            "aud": "appstoreconnect-v1",
        }

        def _b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

        header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
        payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
        signing_input = f"{header_b64}.{payload_b64}"

        # Write key to temp file for openssl
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as kf:
            kf.write(private_key)
            key_file = kf.name

        try:
            # Sign with openssl dgst -sha256 -sign
            proc = subprocess.run(
                ["openssl", "dgst", "-sha256", "-sign", key_file],
                input=signing_input.encode(),
                capture_output=True,
                check=True,
            )
            der_sig = proc.stdout

            # Convert DER signature to raw r||s format for JWT
            raw_sig = self._der_to_raw_signature(der_sig)
            sig_b64 = _b64url(raw_sig)
            return f"{signing_input}.{sig_b64}"
        finally:
            os.unlink(key_file)

    @staticmethod
    def _der_to_raw_signature(der_sig: bytes) -> bytes:
        """
        Convert a DER-encoded ECDSA signature to the raw r||s format
        that JWT ES256 requires (64 bytes total: 32 for r, 32 for s).
        """
        # DER structure: 0x30 <len> 0x02 <rlen> <r> 0x02 <slen> <s>
        if der_sig[0] != 0x30:
            raise ValueError("Invalid DER signature: missing SEQUENCE tag")

        idx = 2  # skip SEQUENCE tag and length
        if der_sig[1] & 0x80:
            # Long form length
            num_len_bytes = der_sig[1] & 0x7F
            idx = 2 + num_len_bytes

        # Read r
        if der_sig[idx] != 0x02:
            raise ValueError("Invalid DER signature: missing INTEGER tag for r")
        idx += 1
        r_len = der_sig[idx]
        idx += 1
        r_bytes = der_sig[idx : idx + r_len]
        idx += r_len

        # Read s
        if der_sig[idx] != 0x02:
            raise ValueError("Invalid DER signature: missing INTEGER tag for s")
        idx += 1
        s_len = der_sig[idx]
        idx += 1
        s_bytes = der_sig[idx : idx + s_len]

        # Strip leading zero bytes (DER uses signed integers)
        r_bytes = r_bytes.lstrip(b"\x00")
        s_bytes = s_bytes.lstrip(b"\x00")

        # Pad to 32 bytes each
        r_padded = r_bytes.rjust(32, b"\x00")
        s_padded = s_bytes.rjust(32, b"\x00")

        return r_padded + s_padded

    def generate_token(self) -> str:
        """
        Generate or return cached JWT token.

        Tokens are cached and automatically refreshed after 18 minutes.
        """
        now = time.time()

        # Return cached token if still fresh
        if (
            self._jwt_token
            and (now - self._jwt_created_at) < self.REFRESH_THRESHOLD_SECONDS
        ):
            return self._jwt_token

        private_key = self._load_private_key()

        if self._check_pyjwt():
            token = self._generate_jwt_pyjwt(private_key)
        else:
            token = self._generate_jwt_openssl(private_key)

        self._jwt_token = token
        self._jwt_created_at = now
        logger.debug("Generated new ASC JWT token (kid=%s)", self.key_id)
        return token

    def invalidate(self) -> None:
        """Force token refresh on next call."""
        self._jwt_token = None
        self._jwt_created_at = 0.0


# ---------------------------------------------------------------------------
# ASCClient - App Store Connect REST API wrapper
# ---------------------------------------------------------------------------

class ASCClient:
    """
    REST client for the App Store Connect API v1.

    Handles authentication, rate limiting, retries, and pagination.
    """

    BASE_URL = "https://api.appstoreconnect.apple.com/v1"
    MIN_REQUEST_INTERVAL = 1.0  # seconds between requests

    def __init__(self, auth: ASCAuth, dry_run: bool = False):
        self.auth = auth
        self.dry_run = dry_run
        self._last_request_time: float = 0.0

    def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """
        Make an authenticated request to the ASC API.

        Handles:
        - Rate limiting (1s minimum between requests)
        - 401: token refresh and retry
        - 409: resource already exists (returns None with log)
        - 429: exponential backoff
        - 204: successful deletion (returns empty dict)
        """
        import urllib.request
        import urllib.error

        url = f"{self.BASE_URL}{path}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            if query:
                url = f"{url}?{query}"

        for attempt in range(max_retries):
            # Rate limiting
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.MIN_REQUEST_INTERVAL:
                time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)

            token = self.auth.generate_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            body = None
            if data is not None:
                body = json.dumps(data).encode("utf-8")

            if self.dry_run and method.upper() in ("POST", "DELETE", "PATCH"):
                logger.info(
                    "[DRY RUN] %s %s%s",
                    method.upper(),
                    path,
                    f" body={json.dumps(data, indent=2)}" if data else "",
                )
                return {"dry_run": True, "method": method, "path": path}

            req = urllib.request.Request(
                url, data=body, headers=headers, method=method.upper()
            )

            logger.debug("%s %s", method.upper(), url)

            try:
                with urllib.request.urlopen(req) as resp:
                    self._last_request_time = time.time()
                    status = resp.status
                    if status == 204:
                        return {}
                    resp_body = resp.read().decode("utf-8")
                    if resp_body:
                        return json.loads(resp_body)
                    return {}

            except urllib.error.HTTPError as e:
                self._last_request_time = time.time()
                status = e.code
                try:
                    err_body = e.read().decode("utf-8")
                    err_json = json.loads(err_body)
                except Exception:
                    err_body = str(e)
                    err_json = {}

                if status == 401:
                    logger.warning(
                        "401 Unauthorized (attempt %d/%d), refreshing token",
                        attempt + 1,
                        max_retries,
                    )
                    self.auth.invalidate()
                    continue

                if status == 409:
                    # Resource already exists - this is often fine
                    errors = err_json.get("errors", [])
                    detail = errors[0].get("detail", "") if errors else err_body
                    logger.info("409 Conflict (resource likely exists): %s", detail)
                    return None

                if status == 429:
                    backoff = min(2 ** (attempt + 1), 60)
                    logger.warning(
                        "429 Rate limited, backing off %ds (attempt %d/%d)",
                        backoff,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(backoff)
                    continue

                if status == 403:
                    errors = err_json.get("errors", [])
                    detail = errors[0].get("detail", "") if errors else err_body
                    logger.error(
                        "403 Forbidden: %s\n"
                        "Your API key may lack provisioning access. "
                        "Ensure the key has Admin or Developer role in "
                        "App Store Connect > Users and Access > Integrations.",
                        detail,
                    )
                    return None

                # Other errors
                errors = err_json.get("errors", [])
                detail = errors[0].get("detail", "") if errors else err_body
                logger.error(
                    "API error %d on %s %s: %s",
                    status,
                    method.upper(),
                    path,
                    detail,
                )
                return None

            except urllib.error.URLError as e:
                logger.error("Network error on %s %s: %s", method.upper(), path, e)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None

        logger.error("Max retries (%d) exhausted for %s %s", max_retries, method, path)
        return None

    # --- Bundle IDs ---

    def list_bundle_ids(
        self, identifier: Optional[str] = None
    ) -> List[BundleIdInfo]:
        """List registered bundle IDs, optionally filtered by identifier."""
        params: Dict[str, Any] = {"limit": 200}
        if identifier:
            params["filter[identifier]"] = identifier

        resp = self._request("GET", "/bundleIds", params=params)
        if not resp or "data" not in resp:
            return []

        results: List[BundleIdInfo] = []
        for item in resp["data"]:
            attrs = item.get("attributes", {})
            results.append(
                BundleIdInfo(
                    resource_id=item["id"],
                    identifier=attrs.get("identifier", ""),
                    name=attrs.get("name", ""),
                    platform=attrs.get("platform", ""),
                )
            )
        return results

    def create_bundle_id(
        self, identifier: str, name: str, platform: str = "IOS"
    ) -> Optional[BundleIdInfo]:
        """Register a new bundle ID. Returns existing one on 409 conflict."""
        platform_upper = platform.upper()
        if platform_upper == "MACOS":
            platform_upper = "MAC_OS"

        data = {
            "data": {
                "type": "bundleIds",
                "attributes": {
                    "identifier": identifier,
                    "name": name,
                    "platform": platform_upper,
                },
            }
        }

        resp = self._request("POST", "/bundleIds", data=data)

        # 409 conflict - fetch existing
        if resp is None:
            existing = self.list_bundle_ids(identifier=identifier)
            if existing:
                logger.info("Bundle ID %s already exists, using existing", identifier)
                return existing[0]
            return None

        if resp.get("dry_run"):
            return BundleIdInfo(
                resource_id="dry-run",
                identifier=identifier,
                name=name,
                platform=platform_upper,
            )

        item = resp.get("data", {})
        attrs = item.get("attributes", {})
        return BundleIdInfo(
            resource_id=item.get("id", ""),
            identifier=attrs.get("identifier", identifier),
            name=attrs.get("name", name),
            platform=attrs.get("platform", platform_upper),
        )

    # --- Capabilities ---

    def list_capabilities(self, bundle_id_resource_id: str) -> List[Dict[str, Any]]:
        """List capabilities enabled on a bundle ID."""
        resp = self._request(
            "GET", f"/bundleIds/{bundle_id_resource_id}/bundleIdCapabilities"
        )
        if not resp or "data" not in resp:
            return []
        return resp["data"]

    def enable_capability(
        self, bundle_id_resource_id: str, capability_type: str
    ) -> bool:
        """Enable a capability on a bundle ID. Idempotent (409 = already enabled)."""
        data = {
            "data": {
                "type": "bundleIdCapabilities",
                "attributes": {
                    "capabilityType": capability_type,
                },
                "relationships": {
                    "bundleId": {
                        "data": {
                            "type": "bundleIds",
                            "id": bundle_id_resource_id,
                        }
                    }
                },
            }
        }

        resp = self._request("POST", "/bundleIdCapabilities", data=data)

        # None = 409 conflict (already enabled) — that is fine
        if resp is None:
            logger.info(
                "Capability %s already enabled on bundle ID %s",
                capability_type,
                bundle_id_resource_id,
            )
            return True

        return resp is not None

    # --- Certificates ---

    def list_certificates(
        self, cert_type: Optional[str] = None
    ) -> List[CertificateInfo]:
        """List certificates, optionally filtered by type."""
        params: Dict[str, Any] = {"limit": 200}
        if cert_type:
            params["filter[certificateType]"] = cert_type

        resp = self._request("GET", "/certificates", params=params)
        if not resp or "data" not in resp:
            return []

        results: List[CertificateInfo] = []
        for item in resp["data"]:
            attrs = item.get("attributes", {})
            results.append(
                CertificateInfo(
                    resource_id=item["id"],
                    name=attrs.get("name", ""),
                    cert_type=attrs.get("certificateType", ""),
                    expiration_date=attrs.get("expirationDate", ""),
                    serial_number=attrs.get("serialNumber", ""),
                )
            )
        return results

    def create_certificate(
        self, csr_content: str, cert_type: str
    ) -> Optional[CertificateInfo]:
        """Create a signing certificate from a CSR."""
        data = {
            "data": {
                "type": "certificates",
                "attributes": {
                    "csrContent": csr_content,
                    "certificateType": cert_type,
                },
            }
        }

        resp = self._request("POST", "/certificates", data=data)
        if not resp or "data" not in resp:
            return None

        item = resp["data"]
        attrs = item.get("attributes", {})
        return CertificateInfo(
            resource_id=item["id"],
            name=attrs.get("name", ""),
            cert_type=attrs.get("certificateType", ""),
            expiration_date=attrs.get("expirationDate", ""),
            serial_number=attrs.get("serialNumber", ""),
        )

    def download_certificate(self, cert_id: str) -> Optional[str]:
        """Download certificate content (base64-encoded DER)."""
        resp = self._request("GET", f"/certificates/{cert_id}")
        if not resp or "data" not in resp:
            return None
        return resp["data"].get("attributes", {}).get("certificateContent", None)

    # --- Devices ---

    def list_devices(self, platform: Optional[str] = None) -> List[DeviceInfo]:
        """List registered devices, optionally filtered by platform."""
        params: Dict[str, Any] = {"limit": 200}
        if platform:
            plat = platform.upper()
            if plat == "MACOS":
                plat = "MAC_OS"
            params["filter[platform]"] = plat

        resp = self._request("GET", "/devices", params=params)
        if not resp or "data" not in resp:
            return []

        results: List[DeviceInfo] = []
        for item in resp["data"]:
            attrs = item.get("attributes", {})
            results.append(
                DeviceInfo(
                    resource_id=item["id"],
                    name=attrs.get("name", ""),
                    udid=attrs.get("udid", ""),
                    platform=attrs.get("platform", ""),
                    status=attrs.get("status", ""),
                )
            )
        return results

    def register_device(
        self, name: str, udid: str, platform: str = "IOS"
    ) -> Optional[DeviceInfo]:
        """Register a new device. Returns existing on 409 conflict."""
        platform_upper = platform.upper()
        if platform_upper == "MACOS":
            platform_upper = "MAC_OS"

        data = {
            "data": {
                "type": "devices",
                "attributes": {
                    "name": name,
                    "udid": udid,
                    "platform": platform_upper,
                },
            }
        }

        resp = self._request("POST", "/devices", data=data)

        if resp is None:
            # 409 - device may already exist, find it
            devices = self.list_devices(platform=platform)
            for d in devices:
                if d.udid.lower() == udid.lower():
                    logger.info("Device %s already registered", udid)
                    return d
            return None

        if resp.get("dry_run"):
            return DeviceInfo(
                resource_id="dry-run",
                name=name,
                udid=udid,
                platform=platform_upper,
                status="ENABLED",
            )

        item = resp.get("data", {})
        attrs = item.get("attributes", {})
        return DeviceInfo(
            resource_id=item.get("id", ""),
            name=attrs.get("name", name),
            udid=attrs.get("udid", udid),
            platform=attrs.get("platform", platform_upper),
            status=attrs.get("status", "ENABLED"),
        )

    # --- Profiles ---

    def list_profiles(
        self,
        name: Optional[str] = None,
        profile_type: Optional[str] = None,
    ) -> List[ProfileInfo]:
        """List provisioning profiles, optionally filtered."""
        params: Dict[str, Any] = {"limit": 200}
        if name:
            params["filter[name]"] = name
        if profile_type:
            params["filter[profileType]"] = profile_type

        resp = self._request("GET", "/profiles", params=params)
        if not resp or "data" not in resp:
            return []

        results: List[ProfileInfo] = []
        for item in resp["data"]:
            attrs = item.get("attributes", {})
            results.append(
                ProfileInfo(
                    resource_id=item["id"],
                    name=attrs.get("name", ""),
                    profile_type=attrs.get("profileType", ""),
                    profile_state=attrs.get("profileState", ""),
                    expiration_date=attrs.get("expirationDate", ""),
                    uuid=attrs.get("uuid", ""),
                )
            )
        return results

    def create_profile(
        self,
        name: str,
        profile_type: str,
        bundle_id_resource_id: str,
        certificate_ids: List[str],
        device_ids: Optional[List[str]] = None,
    ) -> Optional[ProfileInfo]:
        """Create a provisioning profile."""
        relationships: Dict[str, Any] = {
            "bundleId": {
                "data": {"type": "bundleIds", "id": bundle_id_resource_id}
            },
            "certificates": {
                "data": [
                    {"type": "certificates", "id": cid} for cid in certificate_ids
                ]
            },
        }

        if device_ids:
            relationships["devices"] = {
                "data": [{"type": "devices", "id": did} for did in device_ids]
            }

        data = {
            "data": {
                "type": "profiles",
                "attributes": {
                    "name": name,
                    "profileType": profile_type,
                },
                "relationships": relationships,
            }
        }

        resp = self._request("POST", "/profiles", data=data)

        if resp is None:
            # 409 conflict - profile with this name may exist
            existing = self.list_profiles(name=name, profile_type=profile_type)
            if existing:
                logger.info("Profile %s already exists, using existing", name)
                return existing[0]
            return None

        if resp.get("dry_run"):
            return ProfileInfo(
                resource_id="dry-run",
                name=name,
                profile_type=profile_type,
                profile_state="ACTIVE",
                expiration_date="",
                uuid="dry-run-uuid",
            )

        item = resp.get("data", {})
        attrs = item.get("attributes", {})
        return ProfileInfo(
            resource_id=item.get("id", ""),
            name=attrs.get("name", name),
            profile_type=attrs.get("profileType", profile_type),
            profile_state=attrs.get("profileState", ""),
            expiration_date=attrs.get("expirationDate", ""),
            uuid=attrs.get("uuid", ""),
        )

    def download_profile(self, profile_id: str) -> Optional[str]:
        """Download profile content (base64-encoded mobileprovision)."""
        resp = self._request("GET", f"/profiles/{profile_id}")
        if not resp or "data" not in resp:
            return None
        return resp["data"].get("attributes", {}).get("profileContent", None)

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a provisioning profile."""
        resp = self._request("DELETE", f"/profiles/{profile_id}")
        return resp is not None


# ---------------------------------------------------------------------------
# CSRGenerator - Certificate Signing Request generation via openssl
# ---------------------------------------------------------------------------

class CSRGenerator:
    """
    Generate RSA 2048 private keys and Certificate Signing Requests via openssl CLI.

    Keys are stored in ~/.apple-provision/keys/ with timestamp-based names.
    """

    DEFAULT_KEY_DIR = Path.home() / ".apple-provision" / "keys"

    def __init__(self, key_dir: Optional[Path] = None):
        self.key_dir = key_dir or self.DEFAULT_KEY_DIR
        self.key_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        common_name: str = "Huxley Apple Provision",
        email: Optional[str] = None,
    ) -> Tuple[Path, str]:
        """
        Generate a new private key and CSR.

        Returns:
            Tuple of (private_key_path, csr_content_without_headers)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        key_path = self.key_dir / f"cert_key_{timestamp}.pem"
        csr_path = self.key_dir / f"cert_csr_{timestamp}.pem"

        # Build subject string
        subject = f"/CN={common_name}"
        if email:
            subject += f"/emailAddress={email}"

        # Generate RSA 2048 private key
        logger.info("Generating RSA 2048 private key: %s", key_path)
        subprocess.run(
            ["openssl", "genrsa", "-out", str(key_path), "2048"],
            capture_output=True,
            check=True,
        )
        os.chmod(key_path, 0o600)

        # Generate CSR
        logger.info("Generating CSR: %s", csr_path)
        subprocess.run(
            [
                "openssl",
                "req",
                "-new",
                "-key",
                str(key_path),
                "-out",
                str(csr_path),
                "-subj",
                subject,
            ],
            capture_output=True,
            check=True,
        )

        # Read CSR and strip PEM headers for API submission
        with open(csr_path, "r") as f:
            csr_full = f.read()

        csr_content = (
            csr_full.replace("-----BEGIN CERTIFICATE REQUEST-----", "")
            .replace("-----END CERTIFICATE REQUEST-----", "")
            .strip()
        )

        logger.info("CSR generated. Private key saved to %s", key_path)
        return (key_path, csr_content)


# ---------------------------------------------------------------------------
# ProvisioningOrchestrator - Full provisioning workflow
# ---------------------------------------------------------------------------

class ProvisioningOrchestrator:
    """
    High-level orchestrator that ties together all provisioning operations.

    The `provision()` method executes the full idempotent workflow:
    1. Register or find existing Bundle ID
    2. Enable requested capabilities
    3. Find or create signing certificates
    4. Collect device list (for development profiles)
    5. Create development and distribution profiles
    6. Download and install profiles locally
    """

    CAPABILITY_MAP = {
        "push": "PUSH_NOTIFICATIONS",
        "siwa": "SIGN_IN_WITH_APPLE",
        "app-groups": "APP_GROUPS",
        "icloud": "ICLOUD",
        "healthkit": "HEALTHKIT",
        "homekit": "HOMEKIT",
        "wallet": "WALLET",
        "siri": "SIRI",
        "maps": "MAPS",
        "game-center": "GAME_CENTER",
        "in-app-purchase": "IN_APP_PURCHASE",
        "associated-domains": "ASSOCIATED_DOMAINS",
        "nfc": "NFC_TAG_READING",
        "data-protection": "DATA_PROTECTION",
        "network-extensions": "NETWORK_EXTENSIONS",
        "personal-vpn": "PERSONAL_VPN",
        "access-wifi": "ACCESS_WIFI_INFORMATION",
        "autofill-credential": "AUTOFILL_CREDENTIAL_PROVIDER",
        "hotspot": "HOTSPOT",
        "multipath": "MULTIPATH",
        "classkit": "CLASSKIT",
        "inter-app-audio": "INTER_APP_AUDIO",
    }

    # Map platform shorthand to certificate and profile types
    PLATFORM_TYPES = {
        "IOS": {
            "dev_cert": "IOS_DEVELOPMENT",
            "dist_cert": "IOS_DISTRIBUTION",
            "dev_profile": "IOS_APP_DEVELOPMENT",
            "dist_profile": "IOS_APP_STORE",
        },
        "MAC_OS": {
            "dev_cert": "MAC_APP_DEVELOPMENT",
            "dist_cert": "MAC_APP_DISTRIBUTION",
            "dev_profile": "MAC_APP_DEVELOPMENT",
            "dist_profile": "MAC_APP_STORE",
        },
    }

    PROFILES_DIR = Path.home() / "Library" / "MobileDevice" / "Provisioning Profiles"

    def __init__(self, client: ASCClient):
        self.client = client

    def resolve_capability(self, friendly_name: str) -> Optional[str]:
        """Convert a friendly capability name to its Apple API identifier."""
        canonical = friendly_name.lower().strip()
        if canonical in self.CAPABILITY_MAP:
            return self.CAPABILITY_MAP[canonical]
        # Allow passing the raw Apple identifier directly
        upper = canonical.upper().replace("-", "_")
        if upper in self.CAPABILITY_MAP.values():
            return upper
        return None

    def _find_valid_certificate(
        self, cert_type: str
    ) -> Optional[CertificateInfo]:
        """Find an existing valid (non-expired) certificate of the given type."""
        certs = self.client.list_certificates(cert_type=cert_type)
        now_iso = datetime.now(timezone.utc).isoformat()

        for cert in certs:
            if cert.expiration_date and cert.expiration_date > now_iso:
                logger.info(
                    "Found valid %s certificate: %s (expires %s)",
                    cert_type,
                    cert.name,
                    cert.expiration_date,
                )
                return cert

        return None

    def _ensure_certificate(
        self, cert_type: str, csr_generator: CSRGenerator
    ) -> Optional[CertificateInfo]:
        """Find existing or create a new certificate."""
        existing = self._find_valid_certificate(cert_type)
        if existing:
            return existing

        logger.info(
            "No valid %s certificate found, creating new one...", cert_type
        )

        # Check certificate limits for distribution certs
        if "DISTRIBUTION" in cert_type:
            all_dist = self.client.list_certificates(cert_type=cert_type)
            if len(all_dist) >= 3:
                logger.error(
                    "Certificate limit reached! You have %d %s certificates "
                    "(Apple allows max 3).",
                    len(all_dist),
                    cert_type,
                )
                print(f"\n{RED}Certificate limit reached for {cert_type}.{RESET}")
                print(f"Existing certificates:")
                for c in all_dist:
                    exp_str = c.expiration_date[:10] if c.expiration_date else "unknown"
                    print(f"  - {c.name} (expires {exp_str}, id={c.resource_id})")
                print(
                    f"\n{YELLOW}Consider revoking an expired certificate in "
                    f"App Store Connect, or reuse an existing one.{RESET}"
                )
                return None

        # Generate CSR and create certificate
        _key_path, csr_content = csr_generator.generate()
        cert = self.client.create_certificate(csr_content, cert_type)
        if cert:
            logger.info("Created new %s certificate: %s", cert_type, cert.name)
        return cert

    def _install_profile(
        self, profile_id: str, profile_name: str
    ) -> Optional[str]:
        """Download and install a provisioning profile to the system location."""
        content = self.client.download_profile(profile_id)
        if not content:
            logger.error("Failed to download profile %s", profile_name)
            return None

        self.PROFILES_DIR.mkdir(parents=True, exist_ok=True)

        # Profile files are named by their UUID, but we use a readable name
        safe_name = profile_name.replace(" ", "_").replace("/", "_")
        dest = self.PROFILES_DIR / f"{safe_name}.mobileprovision"

        profile_bytes = base64.b64decode(content)
        dest.write_bytes(profile_bytes)

        logger.info("Installed profile to %s", dest)
        return str(dest)

    def _cleanup_invalid_profiles(
        self, name: str, profile_type: str
    ) -> None:
        """Delete any INVALID profiles matching the given name and type."""
        existing = self.client.list_profiles(name=name, profile_type=profile_type)
        for prof in existing:
            if prof.profile_state == "INVALID":
                logger.warning(
                    "Deleting INVALID profile: %s (%s)", prof.name, prof.resource_id
                )
                self.client.delete_profile(prof.resource_id)

    def provision(
        self,
        app_name: str,
        bundle_id: str,
        capabilities: Optional[List[str]] = None,
        platform: str = "IOS",
    ) -> ProvisioningResult:
        """
        Execute the full provisioning workflow.

        This is idempotent - safe to run multiple times. Existing resources are
        reused, and only missing pieces are created.
        """
        result = ProvisioningResult(success=False)
        platform_upper = platform.upper()
        if platform_upper == "MACOS":
            platform_upper = "MAC_OS"

        types = self.PLATFORM_TYPES.get(platform_upper)
        if not types:
            result.errors.append(f"Unsupported platform: {platform}")
            return result

        print(f"\n{BOLD}{CYAN}Provisioning {app_name} ({bundle_id}){RESET}")
        print(f"{DIM}Platform: {platform_upper} | Capabilities: "
              f"{', '.join(capabilities or ['none'])}{RESET}\n")

        # --- Step 1: Bundle ID ---
        print(f"  {BOLD}[1/6]{RESET} Registering Bundle ID...")
        bid = self.client.create_bundle_id(bundle_id, app_name, platform)
        if not bid:
            result.errors.append(f"Failed to register bundle ID: {bundle_id}")
            print(f"  {RED}Failed to register bundle ID{RESET}")
            return result
        result.bundle_id = bid
        print(f"  {GREEN}Bundle ID: {bid.identifier} (id={bid.resource_id}){RESET}")

        # --- Step 2: Capabilities ---
        print(f"  {BOLD}[2/6]{RESET} Enabling capabilities...")
        if capabilities:
            for cap_name in capabilities:
                apple_cap = self.resolve_capability(cap_name)
                if not apple_cap:
                    msg = (
                        f"Unknown capability: '{cap_name}'. "
                        f"Valid names: {', '.join(sorted(self.CAPABILITY_MAP.keys()))}"
                    )
                    result.warnings.append(msg)
                    print(f"  {YELLOW}Skipping unknown capability: {cap_name}{RESET}")
                    continue

                ok = self.client.enable_capability(bid.resource_id, apple_cap)
                if ok:
                    result.capabilities_enabled.append(cap_name)
                    print(f"  {GREEN}{cap_name} -> {apple_cap}{RESET}")
                else:
                    result.warnings.append(f"Failed to enable capability: {cap_name}")
                    print(f"  {YELLOW}Failed to enable: {cap_name}{RESET}")
        else:
            print(f"  {DIM}No capabilities requested{RESET}")

        # --- Step 3: Certificates ---
        print(f"  {BOLD}[3/6]{RESET} Ensuring signing certificates...")
        csr_gen = CSRGenerator()

        dev_cert = self._ensure_certificate(types["dev_cert"], csr_gen)
        if not dev_cert:
            result.errors.append(f"Failed to get {types['dev_cert']} certificate")
            print(f"  {RED}Failed to get development certificate{RESET}")
            return result
        print(f"  {GREEN}Dev cert: {dev_cert.name} "
              f"(expires {dev_cert.expiration_date[:10] if dev_cert.expiration_date else 'N/A'}){RESET}")

        dist_cert = self._ensure_certificate(types["dist_cert"], csr_gen)
        if not dist_cert:
            result.warnings.append(
                f"No distribution certificate available. "
                f"Development profile will still be created."
            )
            print(f"  {YELLOW}No distribution certificate available{RESET}")
        else:
            print(f"  {GREEN}Dist cert: {dist_cert.name} "
                  f"(expires {dist_cert.expiration_date[:10] if dist_cert.expiration_date else 'N/A'}){RESET}")

        result.certificate = dev_cert

        # --- Step 4: Devices ---
        print(f"  {BOLD}[4/6]{RESET} Fetching device list...")
        devices = self.client.list_devices(platform=platform)
        device_ids = [d.resource_id for d in devices if d.status == "ENABLED"]
        print(f"  {GREEN}{len(device_ids)} active devices found{RESET}")

        if not device_ids:
            result.warnings.append(
                "No registered devices found. Development profile requires "
                "at least one device. Register one with: "
                "apple_provision.py register-device --name 'My iPhone' --udid 'xxx'"
            )
            print(f"  {YELLOW}No devices registered - dev profile may fail{RESET}")

        # --- Step 5: Profiles ---
        print(f"  {BOLD}[5/6]{RESET} Creating provisioning profiles...")

        dev_profile_name = f"{app_name} Development"
        dist_profile_name = f"{app_name} Distribution"

        # Clean up any INVALID profiles first
        self._cleanup_invalid_profiles(dev_profile_name, types["dev_profile"])
        self._cleanup_invalid_profiles(dist_profile_name, types["dist_profile"])

        # Development profile
        dev_profile = self.client.create_profile(
            name=dev_profile_name,
            profile_type=types["dev_profile"],
            bundle_id_resource_id=bid.resource_id,
            certificate_ids=[dev_cert.resource_id],
            device_ids=device_ids if device_ids else None,
        )
        if dev_profile:
            result.dev_profile = dev_profile
            state_color = GREEN if dev_profile.profile_state == "ACTIVE" else YELLOW
            print(f"  {state_color}Dev profile: {dev_profile.name} "
                  f"({dev_profile.profile_state}){RESET}")
        else:
            result.warnings.append("Failed to create development profile")
            print(f"  {YELLOW}Failed to create development profile{RESET}")

        # Distribution profile (no devices required)
        if dist_cert:
            dist_profile = self.client.create_profile(
                name=dist_profile_name,
                profile_type=types["dist_profile"],
                bundle_id_resource_id=bid.resource_id,
                certificate_ids=[dist_cert.resource_id],
            )
            if dist_profile:
                result.dist_profile = dist_profile
                state_color = GREEN if dist_profile.profile_state == "ACTIVE" else YELLOW
                print(f"  {state_color}Dist profile: {dist_profile.name} "
                      f"({dist_profile.profile_state}){RESET}")
            else:
                result.warnings.append("Failed to create distribution profile")
                print(f"  {YELLOW}Failed to create distribution profile{RESET}")

        # --- Step 6: Install profiles locally ---
        print(f"  {BOLD}[6/6]{RESET} Installing profiles locally...")
        if dev_profile:
            path = self._install_profile(dev_profile.resource_id, dev_profile_name)
            if path:
                result.installed_profiles.append(path)
                print(f"  {GREEN}Installed: {path}{RESET}")

        if result.dist_profile:
            path = self._install_profile(
                result.dist_profile.resource_id, dist_profile_name
            )
            if path:
                result.installed_profiles.append(path)
                print(f"  {GREEN}Installed: {path}{RESET}")

        # --- Summary ---
        result.success = bool(result.bundle_id and (result.dev_profile or result.dist_profile))

        print(f"\n{BOLD}{'=' * 60}{RESET}")
        if result.success:
            print(f"{GREEN}{BOLD}Provisioning complete for {bundle_id}{RESET}")
        else:
            print(f"{RED}{BOLD}Provisioning finished with issues{RESET}")

        if result.warnings:
            print(f"\n{YELLOW}Warnings:{RESET}")
            for w in result.warnings:
                print(f"  - {w}")
        if result.errors:
            print(f"\n{RED}Errors:{RESET}")
            for e in result.errors:
                print(f"  - {e}")

        return result


# ---------------------------------------------------------------------------
# CLI Interface
# ---------------------------------------------------------------------------

def _format_table(headers: List[str], rows: List[List[str]]) -> str:
    """Format a simple text table."""
    if not rows:
        return "  (no results)"

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(cell))

    # Header
    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    separator = "  ".join("-" * w for w in col_widths)

    lines = [f"  {header_line}", f"  {separator}"]
    for row in rows:
        line = "  ".join(
            (row[i] if i < len(row) else "").ljust(col_widths[i])
            for i in range(len(headers))
        )
        lines.append(f"  {line}")

    return "\n".join(lines)


def _json_output(data: Any) -> None:
    """Print JSON-formatted output."""
    print(json.dumps(data, indent=2, default=str))


def cmd_preflight(client: ASCClient, args: argparse.Namespace) -> int:
    """Validate credentials and API connectivity."""
    print(f"{BOLD}Preflight Check{RESET}\n")

    # 1. Validate credentials
    valid, errors = client.auth.validate()
    if not valid:
        print(f"{RED}Credential errors:{RESET}")
        for e in errors:
            print(f"  - {e}")
        print(f"\n{BOLD}Setup instructions:{RESET}")
        print("  1. Go to App Store Connect > Users and Access > Integrations > Team Keys")
        print("  2. Generate a new API key with Admin or Developer role")
        print("  3. Download the .p8 file")
        print("  4. Set environment variables:")
        print("     export ASC_KEY_ID='your-key-id'")
        print("     export ASC_ISSUER_ID='your-issuer-id'")
        print("     export ASC_KEY_PATH='/path/to/AuthKey_XXXXXX.p8'")
        return 1
    print(f"  {GREEN}Credentials configured{RESET}")

    # 2. Test JWT generation
    try:
        token = client.auth.generate_token()
        print(f"  {GREEN}JWT token generated (length={len(token)}){RESET}")
    except Exception as e:
        print(f"  {RED}JWT generation failed: {e}{RESET}")
        return 1

    # 3. Test API connectivity
    bundle_ids = client.list_bundle_ids()
    if bundle_ids is not None:
        print(f"  {GREEN}API connection successful ({len(bundle_ids)} bundle IDs found){RESET}")
    else:
        print(f"  {RED}API request failed - check key permissions{RESET}")
        return 1

    # 4. Check openssl
    try:
        proc = subprocess.run(
            ["openssl", "version"], capture_output=True, check=True
        )
        openssl_ver = proc.stdout.decode().strip()
        print(f"  {GREEN}openssl available: {openssl_ver}{RESET}")
    except Exception:
        print(f"  {YELLOW}openssl not found - CSR generation will fail{RESET}")

    print(f"\n{GREEN}{BOLD}All preflight checks passed{RESET}")
    return 0


def cmd_provision(client: ASCClient, args: argparse.Namespace) -> int:
    """Full provisioning workflow."""
    capabilities = []
    if args.capabilities:
        capabilities = [c.strip() for c in args.capabilities.split(",") if c.strip()]

    platform = (args.platform or "ios").upper()
    if platform == "MACOS":
        platform = "MAC_OS"

    orchestrator = ProvisioningOrchestrator(client)
    result = orchestrator.provision(
        app_name=args.app_name,
        bundle_id=args.bundle_id,
        capabilities=capabilities or None,
        platform=platform,
    )

    if args.json:
        _json_output({
            "success": result.success,
            "bundle_id": {
                "identifier": result.bundle_id.identifier,
                "resource_id": result.bundle_id.resource_id,
            } if result.bundle_id else None,
            "capabilities_enabled": result.capabilities_enabled,
            "dev_profile": {
                "name": result.dev_profile.name,
                "state": result.dev_profile.profile_state,
            } if result.dev_profile else None,
            "dist_profile": {
                "name": result.dist_profile.name,
                "state": result.dist_profile.profile_state,
            } if result.dist_profile else None,
            "installed_profiles": result.installed_profiles,
            "warnings": result.warnings,
            "errors": result.errors,
        })

    return 0 if result.success else 1


def cmd_list_bundle_ids(client: ASCClient, args: argparse.Namespace) -> int:
    """List registered bundle IDs."""
    bundle_ids = client.list_bundle_ids(
        identifier=getattr(args, "filter", None)
    )

    if args.json:
        _json_output([
            {"id": b.resource_id, "identifier": b.identifier,
             "name": b.name, "platform": b.platform}
            for b in bundle_ids
        ])
        return 0

    print(f"\n{BOLD}Bundle IDs ({len(bundle_ids)}){RESET}\n")
    print(_format_table(
        ["ID", "Identifier", "Name", "Platform"],
        [[b.resource_id, b.identifier, b.name, b.platform] for b in bundle_ids],
    ))
    return 0


def cmd_register_bundle_id(client: ASCClient, args: argparse.Namespace) -> int:
    """Register a new bundle ID."""
    platform = (args.platform or "ios").upper()
    bid = client.create_bundle_id(args.identifier, args.name, platform)
    if bid:
        print(f"{GREEN}Bundle ID registered: {bid.identifier} (id={bid.resource_id}){RESET}")
        if args.json:
            _json_output({"id": bid.resource_id, "identifier": bid.identifier,
                          "name": bid.name, "platform": bid.platform})
        return 0
    else:
        print(f"{RED}Failed to register bundle ID{RESET}")
        return 1


def cmd_list_certs(client: ASCClient, args: argparse.Namespace) -> int:
    """List certificates."""
    certs = client.list_certificates(cert_type=getattr(args, "type", None))

    if args.json:
        _json_output([
            {"id": c.resource_id, "name": c.name, "type": c.cert_type,
             "expires": c.expiration_date, "serial": c.serial_number}
            for c in certs
        ])
        return 0

    print(f"\n{BOLD}Certificates ({len(certs)}){RESET}\n")
    print(_format_table(
        ["ID", "Name", "Type", "Expires", "Serial"],
        [
            [c.resource_id, c.name, c.cert_type,
             c.expiration_date[:10] if c.expiration_date else "N/A",
             c.serial_number[:12] if c.serial_number else ""]
            for c in certs
        ],
    ))
    return 0


def cmd_create_cert(client: ASCClient, args: argparse.Namespace) -> int:
    """Create a new signing certificate."""
    csr_gen = CSRGenerator()
    key_path, csr_content = csr_gen.generate()
    print(f"  Private key saved to: {key_path}")

    cert = client.create_certificate(csr_content, args.type)
    if cert:
        print(f"{GREEN}Certificate created: {cert.name} "
              f"(type={cert.cert_type}, id={cert.resource_id}){RESET}")
        if args.json:
            _json_output({"id": cert.resource_id, "name": cert.name,
                          "type": cert.cert_type, "expires": cert.expiration_date})
        return 0
    else:
        print(f"{RED}Failed to create certificate{RESET}")
        return 1


def cmd_list_profiles(client: ASCClient, args: argparse.Namespace) -> int:
    """List provisioning profiles."""
    profiles = client.list_profiles(
        name=getattr(args, "name", None),
        profile_type=getattr(args, "type", None),
    )

    if args.json:
        _json_output([
            {"id": p.resource_id, "name": p.name, "type": p.profile_type,
             "state": p.profile_state, "expires": p.expiration_date,
             "uuid": p.uuid}
            for p in profiles
        ])
        return 0

    print(f"\n{BOLD}Profiles ({len(profiles)}){RESET}\n")
    rows = []
    for p in profiles:
        state = p.profile_state
        if state == "ACTIVE":
            state_str = f"{GREEN}{state}{RESET}"
        elif state == "INVALID":
            state_str = f"{RED}{state}{RESET}"
        else:
            state_str = state
        rows.append([
            p.resource_id,
            p.name,
            p.profile_type,
            state_str,
            p.expiration_date[:10] if p.expiration_date else "N/A",
        ])
    print(_format_table(["ID", "Name", "Type", "State", "Expires"], rows))
    return 0


def cmd_create_profile(client: ASCClient, args: argparse.Namespace) -> int:
    """Create a provisioning profile."""
    cert_ids = [c.strip() for c in args.cert_ids.split(",")]
    device_ids = None
    if hasattr(args, "device_ids") and args.device_ids:
        device_ids = [d.strip() for d in args.device_ids.split(",")]

    profile = client.create_profile(
        name=args.name,
        profile_type=args.type,
        bundle_id_resource_id=args.bundle_id_id,
        certificate_ids=cert_ids,
        device_ids=device_ids,
    )
    if profile:
        print(f"{GREEN}Profile created: {profile.name} "
              f"(state={profile.profile_state}, id={profile.resource_id}){RESET}")
        if args.json:
            _json_output({"id": profile.resource_id, "name": profile.name,
                          "type": profile.profile_type, "state": profile.profile_state})
        return 0
    else:
        print(f"{RED}Failed to create profile{RESET}")
        return 1


def cmd_list_devices(client: ASCClient, args: argparse.Namespace) -> int:
    """List registered devices."""
    devices = client.list_devices(platform=getattr(args, "platform", None))

    if args.json:
        _json_output([
            {"id": d.resource_id, "name": d.name, "udid": d.udid,
             "platform": d.platform, "status": d.status}
            for d in devices
        ])
        return 0

    print(f"\n{BOLD}Devices ({len(devices)}){RESET}\n")
    print(_format_table(
        ["ID", "Name", "UDID", "Platform", "Status"],
        [[d.resource_id, d.name, d.udid, d.platform, d.status] for d in devices],
    ))
    return 0


def cmd_register_device(client: ASCClient, args: argparse.Namespace) -> int:
    """Register a new device."""
    platform = (args.platform or "ios").upper()
    device = client.register_device(args.name, args.udid, platform)
    if device:
        print(f"{GREEN}Device registered: {device.name} "
              f"(udid={device.udid}, id={device.resource_id}){RESET}")
        if args.json:
            _json_output({"id": device.resource_id, "name": device.name,
                          "udid": device.udid, "platform": device.platform})
        return 0
    else:
        print(f"{RED}Failed to register device{RESET}")
        return 1


def cmd_list_capabilities(client: ASCClient, args: argparse.Namespace) -> int:
    """List capabilities for a bundle ID."""
    # Resolve bundle_id: it can be a resource ID or an identifier
    bundle_resource_id = args.bundle_id

    # If it looks like a bundle identifier (has dots), look it up
    if "." in bundle_resource_id:
        bids = client.list_bundle_ids(identifier=bundle_resource_id)
        if not bids:
            print(f"{RED}Bundle ID not found: {bundle_resource_id}{RESET}")
            return 1
        bundle_resource_id = bids[0].resource_id

    caps = client.list_capabilities(bundle_resource_id)

    if args.json:
        _json_output([
            {"id": c.get("id", ""), "type": c.get("attributes", {}).get("capabilityType", "")}
            for c in caps
        ])
        return 0

    print(f"\n{BOLD}Capabilities ({len(caps)}){RESET}\n")
    rows = []
    for c in caps:
        attrs = c.get("attributes", {})
        rows.append([c.get("id", ""), attrs.get("capabilityType", "")])
    print(_format_table(["ID", "Capability Type"], rows))

    # Also show available friendly names
    orchestrator = ProvisioningOrchestrator(client)
    print(f"\n{DIM}Available capability names for --capability flag:{RESET}")
    for name, apple_id in sorted(orchestrator.CAPABILITY_MAP.items()):
        print(f"  {DIM}{name:25s} -> {apple_id}{RESET}")

    return 0


def cmd_enable_capability(client: ASCClient, args: argparse.Namespace) -> int:
    """Enable a capability on a bundle ID."""
    orchestrator = ProvisioningOrchestrator(client)

    # Resolve bundle ID
    bundle_resource_id = args.bundle_id
    if "." in bundle_resource_id:
        bids = client.list_bundle_ids(identifier=bundle_resource_id)
        if not bids:
            print(f"{RED}Bundle ID not found: {bundle_resource_id}{RESET}")
            return 1
        bundle_resource_id = bids[0].resource_id

    # Resolve capability name
    apple_cap = orchestrator.resolve_capability(args.capability)
    if not apple_cap:
        print(f"{RED}Unknown capability: {args.capability}{RESET}")
        print(f"Valid names: {', '.join(sorted(orchestrator.CAPABILITY_MAP.keys()))}")
        return 1

    ok = client.enable_capability(bundle_resource_id, apple_cap)
    if ok:
        print(f"{GREEN}Capability enabled: {args.capability} -> {apple_cap}{RESET}")
        return 0
    else:
        print(f"{RED}Failed to enable capability{RESET}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="apple_provision",
        description=(
            "Apple Developer Provisioning Tool\n"
            "Automates Bundle IDs, capabilities, certificates, "
            "profiles, and devices via the App Store Connect API."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s preflight\n"
            "  %(prog)s provision --app-name 'My App' "
            "--bundle-id com.example.myapp --capabilities push,siwa\n"
            "  %(prog)s list-certs --type IOS_DISTRIBUTION\n"
            "  %(prog)s register-device --name '{{USER_NAME}} iPhone' --udid 00008101-...\n"
        ),
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without making changes",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- preflight ---
    subparsers.add_parser("preflight", help="Validate credentials and API connectivity")

    # --- provision ---
    p_provision = subparsers.add_parser(
        "provision", help="Full provisioning workflow (idempotent)"
    )
    p_provision.add_argument("--app-name", required=True, help="Display name for the app")
    p_provision.add_argument("--bundle-id", required=True, help="Bundle identifier (e.g. com.example.myapp)")
    p_provision.add_argument(
        "--capabilities", default="",
        help="Comma-separated capabilities (e.g. push,siwa,app-groups)",
    )
    p_provision.add_argument(
        "--platform", default="ios", choices=["ios", "macos"],
        help="Target platform (default: ios)",
    )

    # --- list-bundle-ids ---
    p_lbi = subparsers.add_parser("list-bundle-ids", help="List registered bundle IDs")
    p_lbi.add_argument("--filter", help="Filter by identifier substring")

    # --- register-bundle-id ---
    p_rbi = subparsers.add_parser("register-bundle-id", help="Register a new bundle ID")
    p_rbi.add_argument("--identifier", required=True, help="Bundle identifier (e.g. com.example.myapp)")
    p_rbi.add_argument("--name", required=True, help="Display name")
    p_rbi.add_argument("--platform", default="ios", choices=["ios", "macos"])

    # --- list-certs ---
    p_lc = subparsers.add_parser("list-certs", help="List signing certificates")
    p_lc.add_argument(
        "--type",
        help="Filter by type (IOS_DEVELOPMENT, IOS_DISTRIBUTION, etc.)",
    )

    # --- create-cert ---
    p_cc = subparsers.add_parser("create-cert", help="Create a new signing certificate")
    p_cc.add_argument(
        "--type", required=True,
        help="Certificate type (IOS_DEVELOPMENT, IOS_DISTRIBUTION, "
             "MAC_APP_DEVELOPMENT, MAC_APP_DISTRIBUTION, DEVELOPER_ID_APPLICATION)",
    )

    # --- list-profiles ---
    p_lp = subparsers.add_parser("list-profiles", help="List provisioning profiles")
    p_lp.add_argument("--type", help="Filter by profile type")
    p_lp.add_argument("--name", help="Filter by profile name")

    # --- create-profile ---
    p_cp = subparsers.add_parser("create-profile", help="Create a provisioning profile")
    p_cp.add_argument("--name", required=True, help="Profile name")
    p_cp.add_argument(
        "--type", required=True,
        help="Profile type (IOS_APP_DEVELOPMENT, IOS_APP_STORE, "
             "MAC_APP_DEVELOPMENT, MAC_APP_STORE, etc.)",
    )
    p_cp.add_argument("--bundle-id-id", required=True, help="Bundle ID resource ID")
    p_cp.add_argument("--cert-ids", required=True, help="Comma-separated certificate resource IDs")
    p_cp.add_argument("--device-ids", help="Comma-separated device resource IDs")

    # --- list-devices ---
    p_ld = subparsers.add_parser("list-devices", help="List registered devices")
    p_ld.add_argument("--platform", choices=["ios", "macos"], help="Filter by platform")

    # --- register-device ---
    p_rd = subparsers.add_parser("register-device", help="Register a new device")
    p_rd.add_argument("--name", required=True, help="Device name")
    p_rd.add_argument("--udid", required=True, help="Device UDID")
    p_rd.add_argument("--platform", default="ios", choices=["ios", "macos"])

    # --- list-capabilities ---
    p_lcap = subparsers.add_parser(
        "list-capabilities", help="List capabilities for a bundle ID"
    )
    p_lcap.add_argument(
        "--bundle-id", required=True,
        help="Bundle ID (identifier like com.example.app or resource ID)",
    )

    # --- enable-capability ---
    p_ec = subparsers.add_parser(
        "enable-capability", help="Enable a capability on a bundle ID"
    )
    p_ec.add_argument(
        "--bundle-id", required=True,
        help="Bundle ID (identifier like com.example.app or resource ID)",
    )
    p_ec.add_argument(
        "--capability", required=True,
        help="Capability name (e.g. push, siwa) or Apple identifier",
    )

    return parser


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

    # Initialize auth and client
    auth = ASCAuth()
    client = ASCClient(auth, dry_run=args.dry_run)

    # Dispatch to command handler
    commands = {
        "preflight": cmd_preflight,
        "provision": cmd_provision,
        "list-bundle-ids": cmd_list_bundle_ids,
        "register-bundle-id": cmd_register_bundle_id,
        "list-certs": cmd_list_certs,
        "create-cert": cmd_create_cert,
        "list-profiles": cmd_list_profiles,
        "create-profile": cmd_create_profile,
        "list-devices": cmd_list_devices,
        "register-device": cmd_register_device,
        "list-capabilities": cmd_list_capabilities,
        "enable-capability": cmd_enable_capability,
    }

    handler = commands.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    try:
        return handler(client, args)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted{RESET}")
        return 130
    except Exception as e:
        logger.debug("Unhandled exception", exc_info=True)
        print(f"\n{RED}Error: {e}{RESET}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
