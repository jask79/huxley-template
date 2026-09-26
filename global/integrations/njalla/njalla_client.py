"""
Njalla API Client for Huxley

Privacy-focused domain registrar API wrapper with automatic
credential loading from macOS Keychain (service: njalla-api, account: huxley).

Usage:
    from global.integrations.njalla.njalla_client import NjallaClient

    client = NjallaClient()
    domains = client.list_domains()
"""

import json
import subprocess
import time
from typing import Any, Optional
import urllib.request
import urllib.error


class NjallaError(Exception):
    """Njalla API error."""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Njalla API Error {code}: {message}")


class NjallaClient:
    """
    Njalla API client with automatic Keychain credential loading.

    API Documentation: https://njal.la/api/
    Protocol: JSON-RPC 2.0
    """

    API_ENDPOINT = "https://njal.la/api/1/"

    def __init__(self, token: Optional[str] = None, verbose: bool = False):
        """
        Initialize Njalla client.

        Args:
            token: API token. If None, loads from Keychain automatically.
            verbose: Print request/response details for debugging.
        """
        self.verbose = verbose
        self._request_id = 0

        if token:
            self.token = token
        else:
            self.token = self._load_token()

    def _load_token(self) -> str:
        """Load API token from macOS Keychain (service: njalla-api, account: huxley)."""
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", "njalla-api", "-a", "huxley", "-w"],
                capture_output=True, text=True, timeout=5
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            raise RuntimeError(f"Failed to invoke `security` to read Keychain: {e}")

        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(
                "Njalla API token not found in Keychain. "
                f"security stderr: {result.stderr.strip() or '(empty)'}\n"
                "Store the token with:\n"
                "  security add-generic-password -s njalla-api -a huxley -w <TOKEN> -U"
            )
        return result.stdout.strip()

    def _call(self, method: str, params: Optional[dict] = None) -> Any:
        """Make JSON-RPC call to Njalla API."""
        self._request_id += 1

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self._request_id
        }

        if params:
            payload["params"] = params

        if self.verbose:
            print(f"→ {method}: {json.dumps(params or {}, indent=2)}")

        data = json.dumps(payload).encode('utf-8')

        req = urllib.request.Request(
            self.API_ENDPOINT,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Njalla {self.token}"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8') if e.fp else ''
            raise NjallaError(e.code, f"HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise NjallaError(0, f"Connection error: {e.reason}")

        if self.verbose:
            print(f"← {json.dumps(result, indent=2)}")

        if "error" in result:
            error = result["error"]
            raise NjallaError(
                error.get("code", -1),
                error.get("message", "Unknown error")
            )

        return result.get("result", {})

    # ========== Domain Operations ==========

    def list_domains(self) -> list:
        """List all registered domains."""
        result = self._call("list-domains")
        return result.get("domains", [])

    def get_domain(self, domain: str) -> dict:
        """Get details for a specific domain."""
        return self._call("get-domain", {"domain": domain})

    def register_domain(self, domain: str, years: int = 1) -> str:
        """
        Register a new domain.

        Returns task ID - use check_task() to monitor progress.
        """
        result = self._call("add-domain", {"domain": domain, "years": years})
        return result.get("task")

    def renew_domain(self, domain: str, years: int = 1) -> str:
        """
        Renew an existing domain.

        Returns task ID - use check_task() to monitor progress.
        """
        result = self._call("renew-domain", {"domain": domain, "years": years})
        return result.get("task")

    def edit_domain(self, domain: str, **settings) -> dict:
        """
        Update domain settings.

        Available settings:
            mailforwarding: bool - Enable/disable mail forwarding
            dnssec: bool - Enable/disable DNSSEC
            lock: bool - Lock domain transfers
            nameservers: list - Custom nameservers (empty = Njalla's)
            contacts: dict - Custom WHOIS contact IDs
        """
        params = {"domain": domain, **settings}
        return self._call("edit-domain", params)

    # ========== DNS Record Operations ==========

    def list_records(self, domain: str) -> list:
        """List all DNS records for a domain."""
        result = self._call("list-records", {"domain": domain})
        return result.get("records", [])

    def add_record(
        self,
        domain: str,
        name: str,
        record_type: str,
        content: str,
        ttl: int = 3600
    ) -> dict:
        """
        Add a DNS record.

        Args:
            domain: Domain name (e.g., "example.com")
            name: Record name (e.g., "www", "@" for root)
            record_type: A, AAAA, CNAME, MX, TXT, NS, SRV, CAA, TLSA, REDIRECT
            content: Record content/value
            ttl: Time to live in seconds (default: 3600)

        Returns:
            Created record object with 'id' field
        """
        return self._call("add-record", {
            "domain": domain,
            "name": name,
            "type": record_type,
            "content": content,
            "ttl": ttl
        })

    def edit_record(self, record_id: int, content: str, ttl: int = 3600) -> dict:
        """Update an existing DNS record."""
        return self._call("edit-record", {
            "id": record_id,
            "content": content,
            "ttl": ttl
        })

    def remove_record(self, domain: str, record_id: int) -> None:
        """Delete a DNS record."""
        self._call("remove-record", {"domain": domain, "id": record_id})

    # ========== Task Operations ==========

    def check_task(self, task_id: str) -> dict:
        """Check status of an async task (registration, renewal, etc.)."""
        return self._call("check-task", {"task": task_id})

    def wait_for_task(self, task_id: str, timeout: int = 300, poll_interval: int = 5) -> dict:
        """
        Wait for an async task to complete.

        Args:
            task_id: Task ID from register_domain, renew_domain, etc.
            timeout: Maximum wait time in seconds (default: 300)
            poll_interval: Seconds between status checks (default: 5)

        Returns:
            Final task status

        Raises:
            TimeoutError: If task doesn't complete within timeout
        """
        start = time.time()

        while time.time() - start < timeout:
            status = self.check_task(task_id)

            if status.get("status") == "completed":
                return status
            elif status.get("status") == "failed":
                raise NjallaError(-1, f"Task failed: {status.get('message', 'Unknown error')}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")


# ========== CLI Interface ==========

if __name__ == "__main__":
    import sys

    client = NjallaClient(verbose="--verbose" in sys.argv)

    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help"]:
        print("""
Njalla CLI - Huxley Domain Management

Usage:
    python njalla_client.py <command> [args...]

Commands:
    list-domains              List all domains
    get-domain <domain>       Get domain details
    list-records <domain>     List DNS records
    add-record <domain> <name> <type> <content> [ttl]
                              Add DNS record

Options:
    --verbose                 Print API request/response details

Examples:
    python njalla_client.py list-domains
    python njalla_client.py list-records example.com
    python njalla_client.py add-record example.com www A 192.168.1.1
""")
        sys.exit(0)

    cmd = sys.argv[1]
    args = [a for a in sys.argv[2:] if not a.startswith("--")]

    try:
        if cmd == "list-domains":
            for d in client.list_domains():
                print(f"{d.get('name', 'unknown'):30} expires: {d.get('expiry', 'N/A')}")

        elif cmd == "get-domain" and args:
            domain = client.get_domain(args[0])
            print(json.dumps(domain, indent=2))

        elif cmd == "list-records" and args:
            for r in client.list_records(args[0]):
                print(f"{r.get('type', '?'):6} {r.get('name', '@'):20} -> {r.get('content', '')}")

        elif cmd == "add-record" and len(args) >= 4:
            domain, name, rtype, content = args[:4]
            ttl = int(args[4]) if len(args) > 4 else 3600
            result = client.add_record(domain, name, rtype, content, ttl)
            print(f"Created record ID: {result.get('id')}")

        else:
            print(f"Unknown command or missing arguments: {cmd}")
            sys.exit(1)

    except NjallaError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
