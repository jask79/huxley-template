#!/usr/bin/env python3
"""
VirusTotal Scanner CLI for Huxley Security Analyst

Provides file, hash, URL, and directory scanning against VirusTotal's threat
intelligence database. Hash-first approach minimizes uploads and respects free-tier
rate limits (4 req/min).

Architecture (4-layer, mirrors apple_provision.py / color_grader.py):
    Layer 1: argparse CLI parser with subparsers
    Layer 2: Handler functions (one per subcommand)
    Layer 3: VirusTotalClient class (wraps vt-py library)
    Layer 4: Output formatting (JSON + human-readable with terminal colours)

Credential discovery (2-tier fallback):
    1. --api-key CLI argument
    2. VIRUSTOTAL_API_KEY environment variable

Exit codes:
    0 = clean / success
    1 = error (API failure, bad key, etc.)
    2 = malicious detected
    3 = suspicious detected

Dependencies:
    - vt-py (official VirusTotal Python client)

Usage:
    python3 tools/virustotal_scan.py preflight
    python3 tools/virustotal_scan.py scan-file malware.exe
    python3 tools/virustotal_scan.py scan-hash abc123def456...
    python3 tools/virustotal_scan.py scan-url https://example.com
    python3 tools/virustotal_scan.py scan-dir --dir ./release --filter "*.exe"
    python3 tools/virustotal_scan.py report abc123def456...
    python3 tools/virustotal_scan.py quota
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
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

logger = logging.getLogger("virustotal_scan")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT = 300  # seconds
RATE_LIMIT_PER_MINUTE = 4
RATE_LIMIT_WINDOW = 60.0  # seconds
POLL_INTERVAL = 15  # seconds between analysis polls

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class VirusTotalError(Exception):
    """Base exception for VirusTotal scanner errors."""
    pass


class VirusTotalAuthError(VirusTotalError):
    """API key missing, invalid, or rejected."""
    pass


class VirusTotalAPIError(VirusTotalError):
    """Unexpected API response or server error."""
    pass


class VirusTotalRateLimitError(VirusTotalError):
    """Rate limit reached — caller should wait and retry."""
    pass


class VirusTotalTimeoutError(VirusTotalError):
    """Analysis did not complete within the allowed timeout."""
    pass


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ScanResult:
    """Result of scanning a single file, hash, or URL."""
    file_path: str  # or URL string
    identifier: str  # SHA256 hash or URL scan ID
    status: str  # clean, suspicious, malicious, unknown, error
    detections: int
    total_engines: int
    threat_names: List[str] = field(default_factory=list)
    scan_date: str = ""
    permalink: str = ""
    error_message: str = ""


@dataclass
class QuotaInfo:
    """VirusTotal API quota usage."""
    daily_used: int = 0
    daily_limit: int = 0
    hourly_used: int = 0
    hourly_limit: int = 0
    minute_used: int = 0
    minute_limit: int = 0


# ---------------------------------------------------------------------------
# Layer 3: VirusTotalClient
# ---------------------------------------------------------------------------


class VirusTotalClient:
    """Wraps the vt-py library with rate limiting, polling, and error handling."""

    def __init__(self, api_key: str, timeout: int = DEFAULT_TIMEOUT):
        try:
            import vt as _vt
        except ImportError:
            raise VirusTotalError(
                "vt-py library not installed. Run: pip install vt-py"
            )
        self._vt = _vt
        self._api_key = api_key
        self._timeout = timeout
        self._client: Any = None
        self._request_timestamps: List[float] = []

    # -- lifecycle -----------------------------------------------------------

    def _ensure_client(self) -> Any:
        """Lazy-initialise the vt.Client."""
        if self._client is None:
            self._client = self._vt.Client(self._api_key)
        return self._client

    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    # -- rate limiting -------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Block until we are within the 4-req/min budget."""
        now = time.monotonic()
        # Prune timestamps older than the window
        self._request_timestamps = [
            ts for ts in self._request_timestamps
            if now - ts < RATE_LIMIT_WINDOW
        ]
        if len(self._request_timestamps) >= RATE_LIMIT_PER_MINUTE:
            oldest = self._request_timestamps[0]
            wait = RATE_LIMIT_WINDOW - (now - oldest) + 0.5
            if wait > 0:
                logger.info("Rate limit: sleeping %.1fs", wait)
                time.sleep(wait)
        self._request_timestamps.append(time.monotonic())

    # -- API key validation --------------------------------------------------

    def check_api_key(self) -> Tuple[bool, str]:
        """Validate the API key. Returns (valid, message)."""
        client = self._ensure_client()
        self._wait_for_rate_limit()
        try:
            user = client.get_object("/users/{}", self._api_key)
            name = getattr(user, "name", None) or getattr(user, "id", "unknown")
            group = getattr(user, "group_id", "unknown")
            return True, f"Authenticated as {name} (group: {group})"
        except self._vt.error.APIError as exc:
            if "AuthenticationError" in str(type(exc).__name__) or "401" in str(exc):
                return False, f"Invalid API key: {exc}"
            return False, f"API error during validation: {exc}"
        except Exception as exc:
            return False, f"Unexpected error during validation: {exc}"

    # -- file scanning -------------------------------------------------------

    def scan_file(self, file_path: str) -> ScanResult:
        """Upload and scan a file. Polls until analysis completes or timeout."""
        path = Path(file_path)
        if not path.is_file():
            return ScanResult(
                file_path=file_path,
                identifier="",
                status="error",
                detections=0,
                total_engines=0,
                error_message=f"File not found: {file_path}",
            )

        # Compute local hash for the result record
        sha256 = _compute_sha256(path)
        client = self._ensure_client()

        # Upload the file
        self._wait_for_rate_limit()
        try:
            with open(path, "rb") as f:
                analysis = client.scan_file(f)
            logger.info("Upload complete, analysis ID: %s", analysis.id)
        except self._vt.error.APIError as exc:
            raise VirusTotalAPIError(f"File upload failed: {exc}")

        # Poll for completion
        return self._poll_analysis(analysis.id, file_path, sha256)

    # -- hash lookup ---------------------------------------------------------

    def lookup_hash(self, file_hash: str) -> ScanResult:
        """Look up a file by SHA256, SHA1, or MD5 hash (no upload)."""
        client = self._ensure_client()
        self._wait_for_rate_limit()
        try:
            obj = client.get_object("/files/{}", file_hash)
            return self._parse_file_object(obj, file_path=file_hash)
        except Exception as exc:
            exc_str = str(exc)
            if "NotFoundError" in exc_str or "not found" in exc_str.lower() or "404" in exc_str:
                return ScanResult(
                    file_path=file_hash,
                    identifier=file_hash,
                    status="unknown",
                    detections=0,
                    total_engines=0,
                    error_message="Hash not found in VirusTotal database",
                )
            raise VirusTotalAPIError(f"Hash lookup failed: {exc}")

    # -- URL scanning --------------------------------------------------------

    def scan_url(self, url: str) -> ScanResult:
        """Submit a URL for scanning. Polls until analysis completes."""
        client = self._ensure_client()
        self._wait_for_rate_limit()
        try:
            analysis = client.scan_url(url)
            logger.info("URL submitted, analysis ID: %s", analysis.id)
        except self._vt.error.APIError as exc:
            raise VirusTotalAPIError(f"URL scan submission failed: {exc}")

        # The analysis ID format for URLs encodes the URL — extract identifier
        url_id = _url_identifier(url)
        return self._poll_analysis(analysis.id, url, url_id)

    # -- report retrieval ----------------------------------------------------

    def get_report(self, resource_id: str) -> Dict[str, Any]:
        """Get a detailed JSON report for a file hash or URL ID."""
        client = self._ensure_client()
        self._wait_for_rate_limit()

        # Try as file hash first
        try:
            obj = client.get_object("/files/{}", resource_id)
            return self._file_object_to_report(obj)
        except self._vt.error.APIError:
            pass

        # Try as URL
        self._wait_for_rate_limit()
        try:
            obj = client.get_object("/urls/{}", resource_id)
            return self._url_object_to_report(obj)
        except self._vt.error.APIError as exc:
            raise VirusTotalAPIError(
                f"Report not found for '{resource_id}': {exc}"
            )

    # -- quota ---------------------------------------------------------------

    def get_quota(self) -> QuotaInfo:
        """Retrieve API quota usage for the authenticated user."""
        client = self._ensure_client()
        self._wait_for_rate_limit()
        try:
            user = client.get_object("/users/{}", self._api_key)
            quotas = getattr(user, "quotas", {})

            def _extract(quota_dict: dict, key: str) -> Tuple[int, int]:
                bucket = quota_dict.get(key, {})
                if isinstance(bucket, dict):
                    return bucket.get("used", 0), bucket.get("allowed", 0)
                return 0, 0

            api_req = quotas.get("api_requests_daily", {})
            hourly = quotas.get("api_requests_hourly", {})
            minute = quotas.get("api_requests_monthly", {})

            d_used, d_limit = _extract(quotas, "api_requests_daily")
            h_used, h_limit = _extract(quotas, "api_requests_hourly")
            m_used, m_limit = _extract(quotas, "api_requests_monthly")

            return QuotaInfo(
                daily_used=d_used,
                daily_limit=d_limit,
                hourly_used=h_used,
                hourly_limit=h_limit,
                minute_used=m_used,
                minute_limit=m_limit,
            )
        except self._vt.error.APIError as exc:
            raise VirusTotalAPIError(f"Quota lookup failed: {exc}")

    # -- internal helpers ----------------------------------------------------

    def _poll_analysis(
        self, analysis_id: str, file_path: str, identifier: str
    ) -> ScanResult:
        """Poll an analysis until it completes or times out."""
        client = self._ensure_client()
        deadline = time.monotonic() + self._timeout

        while time.monotonic() < deadline:
            self._wait_for_rate_limit()
            try:
                analysis = client.get_object("/analyses/{}", analysis_id)
            except self._vt.error.APIError as exc:
                raise VirusTotalAPIError(f"Analysis poll failed: {exc}")

            status = getattr(analysis, "status", "queued")
            logger.debug("Analysis %s status: %s", analysis_id, status)

            if status == "completed":
                stats = getattr(analysis, "stats", {})
                results = getattr(analysis, "results", {})
                return self._build_result_from_analysis(
                    file_path, identifier, stats, results
                )

            time.sleep(POLL_INTERVAL)

        raise VirusTotalTimeoutError(
            f"Analysis {analysis_id} did not complete within {self._timeout}s"
        )

    def _build_result_from_analysis(
        self,
        file_path: str,
        identifier: str,
        stats: dict,
        results: dict,
    ) -> ScanResult:
        """Build a ScanResult from raw analysis stats and results."""
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        undetected = stats.get("undetected", 0)
        harmless = stats.get("harmless", 0)
        total = malicious + suspicious + undetected + harmless
        detections = malicious + suspicious

        # Collect threat names from engines that flagged it
        threat_names: List[str] = []
        if isinstance(results, dict):
            for engine_name, detail in results.items():
                if isinstance(detail, dict):
                    cat = detail.get("category", "")
                    if cat in ("malicious", "suspicious"):
                        name = detail.get("result") or engine_name
                        if name and name not in threat_names:
                            threat_names.append(name)

        if malicious > 0:
            status = "malicious"
        elif suspicious > 0:
            status = "suspicious"
        else:
            status = "clean"

        permalink = ""
        if len(identifier) in (32, 40, 64):  # MD5, SHA1, SHA256
            permalink = f"https://www.virustotal.com/gui/file/{identifier}"

        return ScanResult(
            file_path=file_path,
            identifier=identifier,
            status=status,
            detections=detections,
            total_engines=total,
            threat_names=threat_names,
            scan_date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            permalink=permalink,
        )

    def _parse_file_object(self, obj: Any, file_path: str = "") -> ScanResult:
        """Parse a vt File object into a ScanResult."""
        stats = getattr(obj, "last_analysis_stats", {})
        results = getattr(obj, "last_analysis_results", {})
        sha256 = getattr(obj, "sha256", "")
        scan_date_raw = getattr(obj, "last_analysis_date", None)
        scan_date = ""
        if scan_date_raw:
            if isinstance(scan_date_raw, datetime):
                scan_date = scan_date_raw.strftime("%Y-%m-%d %H:%M UTC")
            elif isinstance(scan_date_raw, (int, float)):
                scan_date = datetime.fromtimestamp(
                    scan_date_raw, tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M UTC")
            else:
                scan_date = str(scan_date_raw)

        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        undetected = stats.get("undetected", 0)
        harmless = stats.get("harmless", 0)
        total = malicious + suspicious + undetected + harmless
        detections = malicious + suspicious

        threat_names: List[str] = []
        if isinstance(results, dict):
            for engine_name, detail in results.items():
                if isinstance(detail, dict):
                    cat = detail.get("category", "")
                    if cat in ("malicious", "suspicious"):
                        name = detail.get("result") or engine_name
                        if name and name not in threat_names:
                            threat_names.append(name)

        if malicious > 0:
            status = "malicious"
        elif suspicious > 0:
            status = "suspicious"
        else:
            status = "clean"

        permalink = (
            f"https://www.virustotal.com/gui/file/{sha256}" if sha256 else ""
        )

        return ScanResult(
            file_path=file_path,
            identifier=sha256,
            status=status,
            detections=detections,
            total_engines=total,
            threat_names=threat_names,
            scan_date=scan_date,
            permalink=permalink,
        )

    def _file_object_to_report(self, obj: Any) -> Dict[str, Any]:
        """Convert a vt File object to a detailed report dict."""
        stats = getattr(obj, "last_analysis_stats", {})
        results = getattr(obj, "last_analysis_results", {})
        return {
            "type": "file",
            "sha256": getattr(obj, "sha256", ""),
            "sha1": getattr(obj, "sha1", ""),
            "md5": getattr(obj, "md5", ""),
            "size": getattr(obj, "size", 0),
            "type_description": getattr(obj, "type_description", ""),
            "meaningful_name": getattr(obj, "meaningful_name", ""),
            "reputation": getattr(obj, "reputation", 0),
            "times_submitted": getattr(obj, "times_submitted", 0),
            "last_analysis_stats": stats,
            "last_analysis_date": getattr(obj, "last_analysis_date", None),
            "tags": getattr(obj, "tags", []),
            "names": getattr(obj, "names", []),
            "engine_results": {
                k: {
                    "category": v.get("category", "") if isinstance(v, dict) else "",
                    "result": v.get("result", "") if isinstance(v, dict) else "",
                    "engine_version": v.get("engine_version", "")
                    if isinstance(v, dict)
                    else "",
                }
                for k, v in (results if isinstance(results, dict) else {}).items()
            },
            "permalink": (
                f"https://www.virustotal.com/gui/file/{getattr(obj, 'sha256', '')}"
            ),
        }

    def _url_object_to_report(self, obj: Any) -> Dict[str, Any]:
        """Convert a vt URL object to a detailed report dict."""
        stats = getattr(obj, "last_analysis_stats", {})
        return {
            "type": "url",
            "url": getattr(obj, "url", ""),
            "id": getattr(obj, "id", ""),
            "reputation": getattr(obj, "reputation", 0),
            "times_submitted": getattr(obj, "times_submitted", 0),
            "last_analysis_stats": stats,
            "last_analysis_date": getattr(obj, "last_analysis_date", None),
            "categories": getattr(obj, "categories", {}),
            "last_http_response_code": getattr(
                obj, "last_http_response_code", None
            ),
            "permalink": (
                f"https://www.virustotal.com/gui/url/{getattr(obj, 'id', '')}"
            ),
        }


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _compute_sha256(path: Path) -> str:
    """Compute the SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):  # 1 MiB chunks
            h.update(chunk)
    return h.hexdigest()


def _url_identifier(url: str) -> str:
    """Compute the VT-style URL identifier (SHA-256 of canonicalised URL)."""
    import base64

    # VT uses base64url(sha256(url)) but for display we use the raw hash
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _resolve_api_key(cli_key: Optional[str]) -> str:
    """Resolve the API key using the 2-tier fallback chain."""
    # Tier 1: CLI argument
    if cli_key:
        logger.debug("API key source: CLI argument")
        return cli_key

    # Tier 2: Environment variable
    env_key = os.environ.get("VIRUSTOTAL_API_KEY")
    if env_key:
        logger.debug("API key source: VIRUSTOTAL_API_KEY env var")
        return env_key

    raise VirusTotalAuthError(
        "No API key found. Provide via --api-key or VIRUSTOTAL_API_KEY env var."
    )


# ---------------------------------------------------------------------------
# Layer 4: Output formatting
# ---------------------------------------------------------------------------


def _print_json(data: Any) -> None:
    """Print data as formatted JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


def _print_result(result: ScanResult, prefix: str = "") -> None:
    """Print a ScanResult in human-readable format."""
    if result.status == "malicious":
        icon = f"{RED}{BOLD}\u2717 Malicious{RESET}"
        threats = ", ".join(result.threat_names[:5])
        det_str = (
            f"{RED}{result.detections}/{result.total_engines}{RESET}: {threats}"
        )
    elif result.status == "suspicious":
        icon = f"{YELLOW}\u2717 Suspicious{RESET}"
        threats = ", ".join(result.threat_names[:5])
        det_str = (
            f"{YELLOW}{result.detections}/{result.total_engines}{RESET}: "
            f"{threats}"
        )
    elif result.status == "unknown":
        icon = f"{DIM}? Unknown{RESET}"
        det_str = f"{DIM}not in VT database{RESET}"
    elif result.status == "error":
        icon = f"{RED}! Error{RESET}"
        det_str = f"{RED}{result.error_message}{RESET}"
    else:
        icon = f"{GREEN}\u2713 Clean{RESET}"
        det_str = (
            f"{GREEN}{result.detections}/{result.total_engines}{RESET}"
        )

    if prefix:
        print(f"  {prefix} {icon} ({det_str})")
    else:
        print(f"{icon} \u2014 {det_str}")

    if not prefix:
        # Detailed single-result view
        if result.identifier:
            label = "Hash" if len(result.identifier) == 64 else "ID"
            print(f"  {label}: {DIM}{result.identifier}{RESET}")
        if result.scan_date:
            print(f"  Scanned: {DIM}{result.scan_date}{RESET}")
        if result.permalink:
            print(f"  Link: {DIM}{result.permalink}{RESET}")


def _print_quota(quota: QuotaInfo) -> None:
    """Print quota info in human-readable format."""
    def _bar(used: int, limit: int) -> str:
        if limit == 0:
            return f"{DIM}N/A{RESET}"
        pct = used / limit if limit else 0
        if pct > 0.9:
            colour = RED
        elif pct > 0.7:
            colour = YELLOW
        else:
            colour = GREEN
        return f"{colour}{used:,}{RESET} / {limit:,}"

    print(f"{BOLD}VirusTotal API Quota{RESET}")
    print(f"  Daily:   {_bar(quota.daily_used, quota.daily_limit)}")
    print(f"  Hourly:  {_bar(quota.hourly_used, quota.hourly_limit)}")
    print(f"  Monthly: {_bar(quota.minute_used, quota.minute_limit)}")


def _print_dir_summary(
    results: List[ScanResult], dir_path: str
) -> int:
    """Print directory scan summary. Returns appropriate exit code."""
    clean = sum(1 for r in results if r.status == "clean")
    malicious = sum(1 for r in results if r.status == "malicious")
    suspicious = sum(1 for r in results if r.status == "suspicious")
    unknown = sum(1 for r in results if r.status == "unknown")
    errors = sum(1 for r in results if r.status == "error")

    print(f"\n{BOLD}\u2501" * 50 + RESET)
    parts = []
    if clean:
        parts.append(f"{GREEN}{clean} clean{RESET}")
    if malicious:
        parts.append(f"{RED}{malicious} malicious{RESET}")
    if suspicious:
        parts.append(f"{YELLOW}{suspicious} suspicious{RESET}")
    if unknown:
        parts.append(f"{DIM}{unknown} unknown{RESET}")
    if errors:
        parts.append(f"{RED}{errors} errors{RESET}")
    print(f"Results: {', '.join(parts)}")

    if malicious > 0:
        return 2
    elif suspicious > 0:
        return 3
    return 0


# ---------------------------------------------------------------------------
# Layer 2: Command handlers
# ---------------------------------------------------------------------------


def cmd_preflight(client: VirusTotalClient, args: argparse.Namespace) -> int:
    """Validate API key and check basic connectivity."""
    valid, message = client.check_api_key()

    if args.json:
        _print_json({"valid": valid, "message": message})
        return 0 if valid else 1

    if valid:
        print(f"{GREEN}\u2713 {message}{RESET}")
        # Also show quota
        try:
            quota = client.get_quota()
            _print_quota(quota)
        except VirusTotalError:
            pass  # Quota display is best-effort
        return 0
    else:
        print(f"{RED}\u2717 {message}{RESET}")
        return 1


def cmd_scan_file(client: VirusTotalClient, args: argparse.Namespace) -> int:
    """Upload and scan a file."""
    file_path = args.file
    if not Path(file_path).is_file():
        if args.json:
            _print_json({"error": f"File not found: {file_path}"})
        else:
            print(f"{RED}Error: File not found: {file_path}{RESET}", file=sys.stderr)
        return 1

    # Show file info before scanning
    path = Path(file_path)
    sha256 = _compute_sha256(path)
    size_mb = path.stat().st_size / (1024 * 1024)
    if not args.json:
        print(
            f"Scanning {CYAN}{path.name}{RESET} "
            f"({DIM}{size_mb:.1f} MiB, SHA256: {sha256[:16]}...{RESET})"
        )
        print(f"{DIM}Uploading to VirusTotal...{RESET}")

    result = client.scan_file(file_path)

    if args.json:
        _print_json(asdict(result))
    else:
        _print_result(result)

    if result.status == "malicious":
        return 2
    elif result.status == "suspicious":
        return 3
    elif result.status == "error":
        return 1
    return 0


def cmd_scan_hash(client: VirusTotalClient, args: argparse.Namespace) -> int:
    """Look up a file by hash (SHA256, SHA1, or MD5)."""
    file_hash = args.hash.strip()

    if len(file_hash) not in (32, 40, 64):
        msg = (
            f"Invalid hash length ({len(file_hash)}). "
            "Expected MD5 (32), SHA1 (40), or SHA256 (64)."
        )
        if args.json:
            _print_json({"error": msg})
        else:
            print(f"{RED}Error: {msg}{RESET}", file=sys.stderr)
        return 1

    if not args.json:
        print(f"Looking up hash {DIM}{file_hash[:16]}...{RESET}")

    result = client.lookup_hash(file_hash)

    if args.json:
        _print_json(asdict(result))
    else:
        _print_result(result)

    if result.status == "malicious":
        return 2
    elif result.status == "suspicious":
        return 3
    elif result.status == "error":
        return 1
    return 0


def cmd_scan_url(client: VirusTotalClient, args: argparse.Namespace) -> int:
    """Submit a URL for scanning."""
    url = args.url.strip()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not args.json:
        print(f"Scanning URL {CYAN}{url}{RESET}")
        print(f"{DIM}Submitting to VirusTotal...{RESET}")

    result = client.scan_url(url)

    if args.json:
        _print_json(asdict(result))
    else:
        _print_result(result)

    if result.status == "malicious":
        return 2
    elif result.status == "suspicious":
        return 3
    elif result.status == "error":
        return 1
    return 0


def cmd_scan_dir(client: VirusTotalClient, args: argparse.Namespace) -> int:
    """Batch scan a directory using hash-first approach."""
    dir_path = Path(args.dir)
    if not dir_path.is_dir():
        if args.json:
            _print_json({"error": f"Directory not found: {args.dir}"})
        else:
            print(
                f"{RED}Error: Directory not found: {args.dir}{RESET}",
                file=sys.stderr,
            )
        return 1

    # Collect matching files
    pattern = args.filter or "*"
    files = sorted(
        [f for f in dir_path.rglob(pattern) if f.is_file()],
        key=lambda p: p.name,
    )

    if not files:
        if args.json:
            _print_json({"files": 0, "results": []})
        else:
            print(f"{YELLOW}No files match pattern '{pattern}' in {dir_path}{RESET}")
        return 0

    if not args.json:
        print(
            f"Scanning {CYAN}{dir_path}{RESET} "
            f"({BOLD}{len(files)}{RESET} files, pattern: {pattern})"
        )

    results: List[ScanResult] = []
    threshold = args.threshold

    for idx, fpath in enumerate(files, 1):
        if not args.json:
            label = f"[{idx}/{len(files)}] {fpath.name}"

        sha256 = _compute_sha256(fpath)

        # Hash-first: look up by hash before uploading
        result = client.lookup_hash(sha256)
        result.file_path = str(fpath)

        if result.status == "unknown" and not args.skip_known and not getattr(args, "hash_only", False):
            # File not in VT — upload it
            if not args.json:
                print(
                    f"  {DIM}[{idx}/{len(files)}] {fpath.name} \u2014 "
                    f"not in VT, uploading...{RESET}"
                )
            try:
                result = client.scan_file(str(fpath))
            except VirusTotalError as exc:
                result = ScanResult(
                    file_path=str(fpath),
                    identifier=sha256,
                    status="error",
                    detections=0,
                    total_engines=0,
                    error_message=str(exc),
                )
        elif result.status == "clean" and args.skip_known:
            # Known clean, skip
            if not args.json:
                print(
                    f"  {DIM}[{idx}/{len(files)}] {fpath.name} \u2014 "
                    f"known clean, skipped{RESET}"
                )

        results.append(result)

        # Print per-file result (non-JSON mode)
        if not args.json and result.status != "unknown":
            prefix = f"[{idx}/{len(files)}] {fpath.name} \u2014"
            _print_result(result, prefix=prefix)

    if args.json:
        output = {
            "directory": str(dir_path),
            "pattern": pattern,
            "total_files": len(files),
            "results": [asdict(r) for r in results],
            "summary": {
                "clean": sum(1 for r in results if r.status == "clean"),
                "malicious": sum(1 for r in results if r.status == "malicious"),
                "suspicious": sum(
                    1 for r in results if r.status == "suspicious"
                ),
                "unknown": sum(1 for r in results if r.status == "unknown"),
                "errors": sum(1 for r in results if r.status == "error"),
            },
        }
        _print_json(output)
    else:
        return _print_dir_summary(results, str(dir_path))

    # Determine exit code from results
    if any(r.status == "malicious" and r.detections >= threshold for r in results):
        return 2
    elif any(
        r.status == "suspicious" and r.detections >= threshold for r in results
    ):
        return 3
    return 0


def cmd_report(client: VirusTotalClient, args: argparse.Namespace) -> int:
    """Get a detailed report for a hash or URL."""
    resource_id = args.resource.strip()

    if not args.json:
        print(f"Fetching report for {DIM}{resource_id[:32]}...{RESET}")

    report = client.get_report(resource_id)

    if args.json:
        _print_json(report)
        return 0

    # Human-readable report
    rtype = report.get("type", "unknown")
    print(f"\n{BOLD}VirusTotal Report{RESET}")
    print(f"  Type: {CYAN}{rtype}{RESET}")

    if rtype == "file":
        print(f"  Name: {report.get('meaningful_name', 'N/A')}")
        print(f"  SHA256: {DIM}{report.get('sha256', 'N/A')}{RESET}")
        print(f"  MD5: {DIM}{report.get('md5', 'N/A')}{RESET}")
        size = report.get("size", 0)
        print(f"  Size: {size:,} bytes ({size / 1024 / 1024:.1f} MiB)")
        print(f"  Type: {report.get('type_description', 'N/A')}")
        print(f"  Reputation: {report.get('reputation', 'N/A')}")
        print(f"  Submissions: {report.get('times_submitted', 'N/A')}")

        stats = report.get("last_analysis_stats", {})
        mal = stats.get("malicious", 0)
        sus = stats.get("suspicious", 0)
        total = sum(stats.values())
        det = mal + sus
        if mal > 0:
            det_colour = RED
        elif sus > 0:
            det_colour = YELLOW
        else:
            det_colour = GREEN
        print(f"  Detections: {det_colour}{det}/{total}{RESET}")

        # Show flagging engines
        engine_results = report.get("engine_results", {})
        flagged = {
            k: v
            for k, v in engine_results.items()
            if v.get("category") in ("malicious", "suspicious")
        }
        if flagged:
            print(f"\n  {BOLD}Flagged by:{RESET}")
            for engine, detail in sorted(flagged.items()):
                cat = detail.get("category", "")
                result_name = detail.get("result", "")
                colour = RED if cat == "malicious" else YELLOW
                print(f"    {colour}\u2022{RESET} {engine}: {result_name}")

        tags = report.get("tags", [])
        if tags:
            print(f"\n  Tags: {DIM}{', '.join(tags[:10])}{RESET}")

    elif rtype == "url":
        print(f"  URL: {CYAN}{report.get('url', 'N/A')}{RESET}")
        print(f"  Reputation: {report.get('reputation', 'N/A')}")
        http_code = report.get("last_http_response_code")
        if http_code:
            print(f"  HTTP Status: {http_code}")
        cats = report.get("categories", {})
        if cats:
            cat_list = [f"{v} ({k})" for k, v in cats.items()]
            print(f"  Categories: {', '.join(cat_list[:5])}")

    print(f"\n  Link: {DIM}{report.get('permalink', 'N/A')}{RESET}")
    return 0


def cmd_quota(client: VirusTotalClient, args: argparse.Namespace) -> int:
    """Show remaining API quota."""
    quota = client.get_quota()

    if args.json:
        _print_json(asdict(quota))
    else:
        _print_quota(quota)

    return 0


# ---------------------------------------------------------------------------
# Layer 1: argparse CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="virustotal_scan",
        description=(
            "VirusTotal Scanner for Huxley \u2014 "
            "file, hash, URL, and directory scanning"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"{DIM}Exit codes: 0=clean, 1=error, 2=malicious, 3=suspicious{RESET}\n"
            f"{DIM}API key: --api-key > $VIRUSTOTAL_API_KEY{RESET}"
        ),
    )

    # Global flags
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Machine-readable JSON output (stdout only)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Detailed logging to stderr",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="VirusTotal API key (overrides env)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Max seconds to wait for analysis (default: {DEFAULT_TIMEOUT})",
    )

    subs = parser.add_subparsers(dest="command", metavar="COMMAND")

    # -- preflight -----------------------------------------------------------
    subs.add_parser(
        "preflight",
        help="Validate API key and check connectivity",
    )

    # -- scan-file -----------------------------------------------------------
    sf = subs.add_parser(
        "scan-file",
        help="Upload and scan a file",
    )
    sf.add_argument("file", help="Path to file to scan")

    # -- scan-hash -----------------------------------------------------------
    sh = subs.add_parser(
        "scan-hash",
        help="Lookup by SHA256, SHA1, or MD5 (no upload)",
    )
    sh.add_argument("hash", help="File hash to look up")

    # -- scan-url ------------------------------------------------------------
    su = subs.add_parser(
        "scan-url",
        help="Submit URL for analysis",
    )
    su.add_argument("url", help="URL to scan")

    # -- scan-dir ------------------------------------------------------------
    sd = subs.add_parser(
        "scan-dir",
        help="Batch scan directory (hash-first, upload unknowns)",
    )
    sd.add_argument(
        "--dir",
        required=True,
        help="Directory to scan",
    )
    sd.add_argument(
        "--filter",
        default="*",
        help="Glob pattern to match files (default: '*')",
    )
    sd.add_argument(
        "--threshold",
        type=int,
        default=1,
        help="Minimum detection count to flag (default: 1)",
    )
    sd.add_argument(
        "--skip-known",
        action="store_true",
        default=False,
        help="Skip uploading files already known to VT with 0 detections",
    )
    sd.add_argument(
        "--hash-only",
        action="store_true",
        default=False,
        help="Only check hashes, never upload files (fast mode)",
    )

    # -- report --------------------------------------------------------------
    rp = subs.add_parser(
        "report",
        help="Get detailed report for a hash or URL ID",
    )
    rp.add_argument("resource", help="File hash or URL to get report for")

    # -- quota ---------------------------------------------------------------
    subs.add_parser(
        "quota",
        help="Show remaining API quota",
    )

    return parser


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

    # Configure logging (always to stderr, never pollute JSON stdout)
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    # Resolve API key
    try:
        api_key = _resolve_api_key(args.api_key)
    except VirusTotalAuthError as exc:
        if args.json:
            _print_json({"error": str(exc)})
        else:
            print(f"{RED}\u2717 {exc}{RESET}", file=sys.stderr)
        return 1

    # Initialize client
    client = VirusTotalClient(api_key=api_key, timeout=args.timeout)

    # Dispatch to command handler
    commands = {
        "preflight": cmd_preflight,
        "scan-file": cmd_scan_file,
        "scan-hash": cmd_scan_hash,
        "scan-url": cmd_scan_url,
        "scan-dir": cmd_scan_dir,
        "report": cmd_report,
        "quota": cmd_quota,
    }

    handler = commands.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    try:
        return handler(client, args)
    except VirusTotalAuthError as exc:
        if args.json:
            _print_json({"error": f"Authentication error: {exc}"})
        else:
            print(
                f"\n{RED}Authentication error:{RESET} {exc}", file=sys.stderr
            )
        return 1
    except VirusTotalRateLimitError as exc:
        if args.json:
            _print_json({"error": f"Rate limit: {exc}"})
        else:
            print(f"\n{YELLOW}Rate limit:{RESET} {exc}", file=sys.stderr)
        return 1
    except VirusTotalTimeoutError as exc:
        if args.json:
            _print_json({"error": f"Timeout: {exc}"})
        else:
            print(f"\n{YELLOW}Timeout:{RESET} {exc}", file=sys.stderr)
        return 1
    except VirusTotalAPIError as exc:
        if args.json:
            _print_json({"error": f"API error: {exc}"})
        else:
            print(f"\n{RED}API error:{RESET} {exc}", file=sys.stderr)
        return 1
    except VirusTotalError as exc:
        if args.json:
            _print_json({"error": str(exc)})
        else:
            print(f"\n{RED}Error:{RESET} {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        if not args.json:
            print(f"\n{YELLOW}Interrupted.{RESET}", file=sys.stderr)
        return 130
    except Exception as exc:
        logger.exception("Unexpected error")
        if args.json:
            _print_json({"error": f"Unexpected error: {exc}"})
        else:
            print(f"\n{RED}Unexpected error:{RESET} {exc}", file=sys.stderr)
            print(
                f"{DIM}Use --verbose for detailed traceback.{RESET}",
                file=sys.stderr,
            )
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
