#!/usr/bin/env python3
"""
Domain Registry CLI — Centralized domain management across all registrars.

Usage:
    python3 tools/domain-registry/cli.py status
    python3 tools/domain-registry/cli.py list [--registrar X] [--status X]
    python3 tools/domain-registry/cli.py search <query>
    python3 tools/domain-registry/cli.py expiring [--days N]
    python3 tools/domain-registry/cli.py health [--domain X] [--verbose]
    python3 tools/domain-registry/cli.py sync [--registrar X] [--dry-run]
    python3 tools/domain-registry/cli.py registrars
    python3 tools/domain-registry/cli.py test --registrar X
    python3 tools/domain-registry/cli.py dns list <domain>
    python3 tools/domain-registry/cli.py dns set <domain> <type> <name> <value> [--ttl N] [--dry-run]
    python3 tools/domain-registry/cli.py dns delete <domain> <type> <name> [--dry-run]
    python3 tools/domain-registry/cli.py dns vercel <domain> [--dry-run]
"""

import argparse
import json
import os
import ssl
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Resolve paths relative to catalyst root
SCRIPT_DIR = Path(__file__).resolve().parent
CATALYST_ROOT = SCRIPT_DIR.parent.parent
REGISTRY_PATH = CATALYST_ROOT / "global" / "config" / "domain-registry.yaml"

# ---------------------------------------------------------------------------
# YAML loader (stdlib only — no PyYAML dependency)
# ---------------------------------------------------------------------------

def load_registry() -> dict:
    """Load domain registry YAML. Uses PyYAML if available, falls back to basic parser."""
    if not REGISTRY_PATH.exists():
        print(f"ERROR: Registry not found at {REGISTRY_PATH}")
        print("Run ./setup.sh once, or copy global/config/domain-registry.example.yaml into place.")
        sys.exit(1)

    text = REGISTRY_PATH.read_text()

    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return _parse_yaml_basic(text)


def _parse_yaml_basic(text: str) -> dict:
    """Minimal YAML parser for the flat domain-registry format. Handles top-level
    domain keys and their single-level string properties. NOT a general YAML parser."""
    result = {}
    current_domain = None

    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # Skip comments and blanks
        if not stripped or stripped.startswith("#"):
            continue

        # Warn on YAML list items (unsupported)
        if stripped.startswith("- "):
            print(f"WARNING: basic YAML parser cannot handle list item at line {lineno}: {stripped[:60]}")
            continue

        # Top-level key (domain name — no leading whitespace)
        if not line[0].isspace() and stripped.endswith(":"):
            current_domain = stripped.rstrip(":")
            result[current_domain] = {}
        # Nested property
        elif current_domain and ":" in stripped:
            # Detect nested maps deeper than 1 level by checking indentation
            indent = len(line) - len(line.lstrip())
            if indent > 4:
                print(f"WARNING: basic YAML parser cannot handle deep nesting at line {lineno}: {stripped[:60]}")
                continue
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Handle inline comments
            if "  #" in value:
                value = value[: value.index("  #")].strip()
            elif value.startswith("#"):
                value = ""
            result[current_domain][key] = value

    return result


def save_registry(data: dict):
    """Write registry back to YAML. Uses atomic write (tmp + rename) to prevent corruption."""
    try:
        import yaml
        tmp_path = REGISTRY_PATH.with_suffix(".yaml.tmp")
        with open(tmp_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, REGISTRY_PATH)
    except ImportError:
        print("WARNING: PyYAML not installed — cannot write registry. Install with: pip install pyyaml")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Keychain helpers
# ---------------------------------------------------------------------------

def keychain_get(service: str, account: str = "huxley") -> str | None:
    """Retrieve a password from macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    return None


# ---------------------------------------------------------------------------
# Registrar API adapters
# ---------------------------------------------------------------------------

REGISTRAR_ADAPTERS = {}


def _register_adapter(name: str):
    def decorator(cls):
        REGISTRAR_ADAPTERS[name] = cls
        return cls
    return decorator


class RegistrarAdapter:
    """Base class for registrar API adapters."""
    name: str = "unknown"

    def test_connection(self) -> tuple[bool, str]:
        """Test API connectivity. Returns (success, message)."""
        return False, "Not implemented"

    def list_domains(self) -> list[dict]:
        """Fetch all domains from this registrar. Returns list of domain dicts."""
        return []

    # --- DNS management (override in subclasses that support it) ---

    def get_dns(self, domain: str) -> list[dict]:
        """Return current DNS records as list of dicts:
        {type, name, address, ttl, mx_pref?}
        Subclasses must override; default raises NotImplementedError."""
        raise NotImplementedError(
            f"DNS read not implemented for registrar '{self.name}'"
        )

    def set_dns_record(self, domain: str, record: dict, mode: str = "upsert",
                       dry_run: bool = False) -> dict:
        """Add or update a single DNS record.

        mode: 'upsert' (replace existing record matching name+type, default)
              'append' (allow duplicates — multiple records with same name+type)

        Returns: {ok, before, after, changed, dry_run?}
        Subclasses must override; default raises NotImplementedError."""
        raise NotImplementedError(
            f"DNS write not implemented for registrar '{self.name}'"
        )

    def delete_dns_record(self, domain: str, name: str, record_type: str,
                          dry_run: bool = False) -> dict:
        """Remove records matching name+type.

        Returns: {ok, before, after, changed, dry_run?}
        Subclasses must override; default raises NotImplementedError."""
        raise NotImplementedError(
            f"DNS delete not implemented for registrar '{self.name}'"
        )

    def set_dns_records(self, domain: str, records: list[dict],
                        replace_all: bool = False, mode: str = "upsert",
                        dry_run: bool = False) -> dict:
        """Bulk set records.

        replace_all=True  → wipe existing zone, write only `records`
        replace_all=False → merge by (name, type) — passed records upsert,
                            untouched records preserved.

        mode: 'upsert' (default) — replaces existing record only when there's
                                   exactly one match for (name, type). Raises
                                   if multiple existing matches exist.
              'replace' — collapses any number of existing matches into the
                          single new record.

        Returns: {ok, before, after, changed, dry_run?}
        Subclasses must override; default raises NotImplementedError."""
        raise NotImplementedError(
            f"DNS bulk write not implemented for registrar '{self.name}'"
        )


@_register_adapter("godaddy")
class GoDaddyAdapter(RegistrarAdapter):
    name = "godaddy"

    def __init__(self):
        self.api_key = keychain_get("godaddy-api-key") or keychain_get("godaddy-api")
        self.api_secret = keychain_get("godaddy-api-secret")

    def test_connection(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "No API key found in Keychain (godaddy-api-key)"
        try:
            import urllib.request
            import urllib.error
            ssl_ctx = ssl.create_default_context()
            req = urllib.request.Request(
                "https://api.godaddy.com/v1/domains?limit=1",
                headers={
                    "Authorization": f"sso-key {self.api_key}:{self.api_secret or ''}",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                if resp.status == 200:
                    return True, "Connected OK"
                return False, f"HTTP {resp.status}"
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            return False, f"{type(e).__name__}: request failed"

    def list_domains(self) -> list[dict]:
        if not self.api_key:
            return []
        try:
            import urllib.request
            ssl_ctx = ssl.create_default_context()
            req = urllib.request.Request(
                "https://api.godaddy.com/v1/domains?limit=500&statuses=ACTIVE",
                headers={
                    "Authorization": f"sso-key {self.api_key}:{self.api_secret or ''}",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
                domains = json.loads(resp.read())
                results = []
                for d in domains:
                    results.append({
                        "domain": d.get("domain", ""),
                        "registrar": "godaddy",
                        "expires": d.get("expires", "unknown")[:10] if d.get("expires") else "unknown",
                        "status": "active" if d.get("status") == "ACTIVE" else d.get("status", "unknown").lower(),
                        "auto_renew": d.get("renewAuto", False),
                        "privacy": d.get("privacy", False),
                        "locked": d.get("locked", False),
                    })
                return results
        except Exception as e:
            print(f"  ERROR fetching GoDaddy domains: {type(e).__name__}: request failed")
            return []


@_register_adapter("namecheap")
class NamecheapAdapter(RegistrarAdapter):
    name = "namecheap"

    def __init__(self):
        self.api_key = keychain_get("namecheap-api")
        self.api_user = keychain_get("namecheap-api-user")
        self._client_ip = None

    def _get_client_ip(self) -> str:
        """Get public IP for Namecheap API (they require it in every request).

        Tries sources in order: NAMECHEAP_CLIENT_IP env var, api.ipify.org,
        icanhazip.com, ifconfig.me/ip. Each with a 5s timeout. Only raises
        RuntimeError if all sources fail.
        """
        if self._client_ip:
            return self._client_ip

        # 1) Environment override
        env_ip = os.environ.get("NAMECHEAP_CLIENT_IP")
        if env_ip and env_ip.strip():
            self._client_ip = env_ip.strip()
            return self._client_ip

        # 2) HTTP fallback chain
        import urllib.request
        ssl_ctx = ssl.create_default_context()
        sources = [
            "https://api.ipify.org",
            "https://icanhazip.com",
            "https://ifconfig.me/ip",
        ]
        for url in sources:
            try:
                with urllib.request.urlopen(url, timeout=5, context=ssl_ctx) as resp:
                    ip = resp.read().decode().strip()
                    if ip:
                        self._client_ip = ip
                        return self._client_ip
            except Exception:
                continue

        raise RuntimeError(
            "Could not determine public IP for Namecheap API "
            "(tried NAMECHEAP_CLIENT_IP env var and 3 public IP services)"
        )

    def _api_call(self, command: str, extra_params: dict = None) -> dict:
        """Make a Namecheap API call. Returns parsed XML as a dict-like structure."""
        import urllib.request
        import urllib.error
        import urllib.parse
        import xml.etree.ElementTree as ET

        client_ip = self._get_client_ip()
        # WARNING: This dict contains the API key. Never log or print params.
        # If you add error logging, exclude or redact ApiKey/ApiUser/UserName fields.
        params = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.api_user,
            "ClientIp": client_ip,
            "Command": command,
        }
        if extra_params:
            params.update(extra_params)

        url = "https://api.namecheap.com/xml.response"
        ssl_ctx = ssl.create_default_context()
        req = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(params).encode(),
            headers={"Accept": "application/xml"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
                return ET.fromstring(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.reason}")

    def test_connection(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "No API key found in Keychain (namecheap-api)"
        if not self.api_user:
            return False, "No API user found in Keychain (namecheap-api-user)"
        try:
            root = self._api_call("namecheap.domains.getList", {"PageSize": "10"})
            status = root.attrib.get("Status", "")
            if status == "OK":
                return True, "Connected OK"
            # Check for error message
            errors = root.findall(".//{http://api.namecheap.com/xml.response}Error")
            if not errors:
                errors = root.findall(".//Error")
            if errors:
                return False, f"API error: {errors[0].text}"
            return False, f"Unexpected status: {status}"
        except Exception as e:
            return False, f"{type(e).__name__}: request failed"

    def list_domains(self) -> list[dict]:
        if not self.api_key or not self.api_user:
            return []
        try:
            ns = "{http://api.namecheap.com/xml.response}"
            results = []
            page = 1
            MAX_PAGES = 50

            while True:
                if page > MAX_PAGES:
                    break
                root = self._api_call("namecheap.domains.getList", {
                    "PageSize": "100",
                    "Page": str(page),
                })
                if root.attrib.get("Status") != "OK":
                    break

                # Find domain entries — try with and without namespace
                domains = root.findall(f".//{ns}Domain")
                if not domains:
                    domains = root.findall(".//Domain")
                if not domains:
                    # Try DomainGetListResult
                    domains = root.findall(f".//{ns}DomainGetListResult/{ns}Domain")
                if not domains:
                    domains = root.findall(".//DomainGetListResult/Domain")

                for d in domains:
                    expires_raw = d.attrib.get("Expires", "")
                    # Namecheap returns dates like "04/20/2027"
                    try:
                        exp_date = datetime.strptime(expires_raw, "%m/%d/%Y")
                        expires = exp_date.strftime("%Y-%m-%d")
                    except ValueError:
                        expires = "unknown"

                    results.append({
                        "domain": d.attrib.get("Name", ""),
                        "registrar": "namecheap",
                        "expires": expires,
                        "status": "active" if d.attrib.get("IsExpired", "false") == "false" else "expired",
                        "auto_renew": d.attrib.get("AutoRenew", "false").lower() == "true",
                        "uses_registrar_dns": d.attrib.get("IsOurDNS", "false").lower() == "true",
                    })

                # Check pagination
                paging = root.find(f".//{ns}Paging")
                if paging is None:
                    paging = root.find(".//Paging")
                if paging is not None:
                    total_items_el = paging.find(f"{ns}TotalItems")
                    if total_items_el is None:
                        total_items_el = paging.find("TotalItems")
                    if total_items_el is not None:
                        try:
                            total_items = int(total_items_el.text)
                        except (TypeError, ValueError):
                            total_items = 0
                    else:
                        total_items = 0
                    if page * 100 >= total_items:
                        break
                else:
                    break
                page += 1

            return results
        except Exception as e:
            print(f"  ERROR fetching Namecheap domains: {type(e).__name__}: request failed")
            return []

    # ------------------------------------------------------------------
    # DNS management
    # ------------------------------------------------------------------

    @staticmethod
    def _split_domain(domain: str) -> tuple[str, str]:
        """Split a domain into (SLD, TLD) for Namecheap's API.

        Namecheap's API uses a simple 2-label split. Multi-label TLDs
        (e.g., co.uk, com.au) are NOT supported — refuses to guess.
        """
        parts = domain.strip().lower().rstrip(".").split(".")
        if len(parts) < 2:
            raise ValueError(f"Invalid domain: {domain!r}")
        if len(parts) > 2:
            raise ValueError(
                f"Domain '{domain}' has {len(parts)} labels. Multi-label TLDs "
                f"(e.g. co.uk, com.au) are not supported by automatic SLD/TLD "
                f"splitting — guessing SLD='{parts[-2]}', TLD='{parts[-1]}' "
                f"would be incorrect (the real TLD may be '{'.'.join(parts[-2:])}'). "
                f"Pass explicit --sld/--tld overrides to handle this domain."
            )
        sld = parts[-2]
        tld = parts[-1]
        return sld, tld

    # Namecheap's accepted record types. Any other value will be rejected.
    _VALID_TYPES = (
        "A", "AAAA", "CNAME", "MX", "MXE", "TXT",
        "URL", "URL301", "FRAME", "NS", "CAA", "ALIAS",
    )

    @staticmethod
    def _normalize_record(rec: dict) -> dict:
        """Normalize a record dict for comparison/output. Uppercases type,
        strips whitespace, defaults ttl=1800, name='@'.

        Note: TTL=0 is preserved (conventional "use server default") rather
        than being overwritten by 1800.
        """
        rtype = (rec.get("type") or "").upper().strip()
        if rtype and rtype not in NamecheapAdapter._VALID_TYPES:
            raise ValueError(
                f"Invalid record type {rtype!r}. "
                f"Namecheap accepts: {', '.join(NamecheapAdapter._VALID_TYPES)}"
            )
        address = (rec.get("address") or rec.get("value") or "").strip()
        # M9: Namecheap uses values as FQDNs by default — trailing dot is
        # unnecessary and not accepted. Strip it for target-style records.
        if rtype in ("CNAME", "ALIAS", "MX") and address.endswith("."):
            address = address.rstrip(".")
        out = {
            "type": rtype,
            "name": (rec.get("name") or "@").strip() or "@",
            "address": address,
            # TTL=0 is conventional for "use server default" — preserve it
            # (do NOT collapse to the 1800 default).
            "ttl": int(rec["ttl"] if rec.get("ttl") is not None else 1800),
        }
        if "mx_pref" in rec and rec["mx_pref"] is not None:
            out["mx_pref"] = int(rec["mx_pref"])
        elif out["type"] == "MX":
            # Default MX preference when caller didn't supply one.
            out["mx_pref"] = 10
        return out

    def get_dns(self, domain: str) -> list[dict]:
        """Read current DNS host records for a domain via getHosts API."""
        sld, tld = self._split_domain(domain)
        ns = "{http://api.namecheap.com/xml.response}"
        root = self._api_call(
            "namecheap.domains.dns.getHosts",
            {"SLD": sld, "TLD": tld},
        )
        if root.attrib.get("Status") != "OK":
            errs = root.findall(f".//{ns}Error") or root.findall(".//Error")
            msg = errs[0].text if errs else "unknown error"
            raise RuntimeError(f"getHosts failed: {msg}")

        # Locate <host> elements (try with and without namespace)
        hosts = root.findall(f".//{ns}host")
        if not hosts:
            hosts = root.findall(".//host")

        records = []
        for h in hosts:
            attrs = h.attrib
            rec = {
                "type": attrs.get("Type", "").upper(),
                "name": attrs.get("Name", "@") or "@",
                "address": attrs.get("Address", ""),
                "ttl": int(attrs.get("TTL", "1800") or 1800),
            }
            # MXPref is returned for ALL records by Namecheap — only keep
            # it for MX records where it actually has meaning.
            if rec["type"] == "MX":
                mx_pref = attrs.get("MXPref")
                if mx_pref:
                    try:
                        rec["mx_pref"] = int(mx_pref)
                    except ValueError:
                        pass
            records.append(rec)
        return records

    def _write_hosts(self, domain: str, records: list[dict]) -> None:
        """Write the full set of host records via setHosts. Atomic — replaces all."""
        sld, tld = self._split_domain(domain)
        ns = "{http://api.namecheap.com/xml.response}"

        params = {"SLD": sld, "TLD": tld}
        for i, rec in enumerate(records, start=1):
            r = self._normalize_record(rec)
            params[f"HostName{i}"] = r["name"]
            params[f"RecordType{i}"] = r["type"]
            params[f"Address{i}"] = r["address"]
            params[f"TTL{i}"] = str(r["ttl"])
            if r["type"] == "MX":
                params[f"MXPref{i}"] = str(r.get("mx_pref", 10))
                # EmailType is required when any MX records present
                params["EmailType"] = "MX"

        root = self._api_call("namecheap.domains.dns.setHosts", params)
        if root.attrib.get("Status") != "OK":
            errs = root.findall(f".//{ns}Error") or root.findall(".//Error")
            msg = errs[0].text if errs else "unknown error"
            raise RuntimeError(f"setHosts failed: {msg}")

        # Verify IsSuccess flag on the result element
        result_el = (
            root.find(f".//{ns}DomainDNSSetHostsResult")
            or root.find(".//DomainDNSSetHostsResult")
        )
        if result_el is not None and result_el.attrib.get("IsSuccess", "true").lower() == "false":
            raise RuntimeError("setHosts returned IsSuccess=false")

    @staticmethod
    def _records_match(a: dict, b: dict) -> bool:
        """Two normalized records match on (name, type)."""
        return (
            a.get("name", "@") == b.get("name", "@")
            and a.get("type", "").upper() == b.get("type", "").upper()
        )

    @staticmethod
    def _records_equal(a: dict, b: dict) -> bool:
        """Two records are fully equal (used for changed detection)."""
        keys = ("type", "name", "address", "ttl", "mx_pref")
        for k in keys:
            if a.get(k) != b.get(k):
                return False
        return True

    def set_dns_record(self, domain: str, record: dict, mode: str = "upsert",
                       dry_run: bool = False) -> dict:
        """Add/update a single DNS record (read-merge-write)."""
        if mode not in ("upsert", "append"):
            raise ValueError(f"Invalid mode: {mode!r} (use 'upsert' or 'append')")

        before = self.get_dns(domain)
        new_rec = self._normalize_record(record)

        # Build new record set
        if mode == "append":
            after = [self._normalize_record(r) for r in before] + [new_rec]
        else:  # upsert
            after = []
            replaced = False
            for r in before:
                rn = self._normalize_record(r)
                if self._records_match(rn, new_rec):
                    if not replaced:
                        after.append(new_rec)
                        replaced = True
                    # drop additional dupes (collapse to single upserted)
                else:
                    after.append(rn)
            if not replaced:
                after.append(new_rec)

        changed = self._diff_records(before, after)
        result = {
            "ok": True,
            "before": before,
            "after": after,
            "changed": changed,
            "dry_run": dry_run,
        }
        if changed and not dry_run:
            self._write_hosts(domain, after)
        return result

    def delete_dns_record(self, domain: str, name: str, record_type: str,
                          dry_run: bool = False) -> dict:
        """Remove records matching name+type."""
        before = self.get_dns(domain)
        target = {"name": (name or "@").strip() or "@", "type": record_type.upper().strip()}
        after = [
            self._normalize_record(r) for r in before
            if not self._records_match(self._normalize_record(r), target)
        ]
        changed = self._diff_records(before, after)
        result = {
            "ok": True,
            "before": before,
            "after": after,
            "changed": changed,
            "dry_run": dry_run,
        }
        if changed and not dry_run:
            self._write_hosts(domain, after)
        return result

    def set_dns_records(self, domain: str, records: list[dict],
                        replace_all: bool = False, mode: str = "upsert",
                        dry_run: bool = False) -> dict:
        """Bulk set records — replace all or merge by (name, type).

        mode: 'upsert' (default) — only replaces existing records when there
                                   is exactly ONE existing match for a given
                                   (name, type). If multiple existing records
                                   match (e.g. multiple TXT @ for SPF/DKIM),
                                   raises RuntimeError to prevent silent data
                                   loss.
              'replace' — collapses any number of existing matches into the
                          single new record. Caller must opt in explicitly.
        """
        if mode not in ("upsert", "replace"):
            raise ValueError(f"Invalid mode: {mode!r} (use 'upsert' or 'replace')")

        before = self.get_dns(domain)
        before_n = [self._normalize_record(r) for r in before]
        new_recs = [self._normalize_record(r) for r in records]

        if replace_all:
            after = new_recs
        else:
            # In upsert mode, refuse to silently collapse multiple existing
            # records into a single new one — that's data loss (e.g., a zone
            # with 3 TXT @ records for SPF/DKIM/ownership getting clobbered).
            if mode == "upsert":
                for nr in new_recs:
                    matches = [b for b in before_n if self._records_match(b, nr)]
                    if len(matches) > 1:
                        raise RuntimeError(
                            f"Refusing to upsert {nr['type']} record at "
                            f"name='{nr['name']}': {len(matches)} existing "
                            f"records match (name+type). Upserting would "
                            f"silently delete the others. Pass mode='replace' "
                            f"to collapse them, or use set_dns_record per-record."
                        )

            # Merge: incoming records replace existing matches (name+type),
            # everything else preserved.
            after = []
            for rn in before_n:
                # Skip if a new record matches it (will be replaced)
                if any(self._records_match(rn, nr) for nr in new_recs):
                    continue
                after.append(rn)
            after.extend(new_recs)

        changed = self._diff_records(before, after)
        result = {
            "ok": True,
            "before": before,
            "after": after,
            "changed": changed,
            "dry_run": dry_run,
        }
        if changed and not dry_run:
            self._write_hosts(domain, after)
        return result

    @classmethod
    def _diff_records(cls, before: list[dict], after: list[dict]) -> list[dict]:
        """Return list of {action, record} entries describing the diff."""
        before_n = [cls._normalize_record(r) for r in before]
        after_n = [cls._normalize_record(r) for r in after]
        changes = []

        # Records added or modified
        for a in after_n:
            match = next(
                (b for b in before_n if cls._records_match(a, b)),
                None,
            )
            if match is None:
                changes.append({"action": "add", "record": a})
            elif not cls._records_equal(a, match):
                changes.append({"action": "modify", "before": match, "record": a})

        # Records removed
        for b in before_n:
            if not any(cls._records_match(a, b) for a in after_n):
                changes.append({"action": "delete", "record": b})

        return changes


@_register_adapter("cloudflare")
class CloudflareAdapter(RegistrarAdapter):
    name = "cloudflare"

    # Multi-account support: set CLOUDFLARE_ACCOUNT_LABELS (comma-separated,
    # read at import time — export it before python imports this module) and
    # store a cloudflare-api-<label> keychain entry for each label
    ACCOUNTS = [a.strip() for a in os.environ.get("CLOUDFLARE_ACCOUNT_LABELS", "").split(",") if a.strip()]

    def __init__(self):
        self.tokens: dict[str, str] = {}
        # Try legacy single-token first
        legacy = keychain_get("cloudflare-api")
        if legacy:
            self.tokens["default"] = legacy
        # Then try each named account
        for acct in self.ACCOUNTS:
            tok = keychain_get(f"cloudflare-api-{acct}")
            if tok:
                self.tokens[acct] = tok

    def test_connection(self) -> tuple[bool, str]:
        if not self.tokens:
            return False, "No API tokens found in Keychain (cloudflare-api or cloudflare-api-<account>)"
        import urllib.request
        ssl_ctx = ssl.create_default_context()
        ok_accounts = []
        for acct, token in self.tokens.items():
            try:
                req = urllib.request.Request(
                    "https://api.cloudflare.com/client/v4/user/tokens/verify",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                    data = json.loads(resp.read())
                    if data.get("success"):
                        ok_accounts.append(acct)
            except Exception:
                pass
        if ok_accounts:
            return True, f"Connected OK — {len(ok_accounts)} account(s): {', '.join(ok_accounts)}"
        return False, "All tokens failed verification"

    def list_domains(self) -> list[dict]:
        if not self.tokens:
            return []
        import urllib.request
        ssl_ctx = ssl.create_default_context()
        results = []
        for acct, token in self.tokens.items():
            try:
                req = urllib.request.Request(
                    "https://api.cloudflare.com/client/v4/zones?per_page=50",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
                    data = json.loads(resp.read())
                    if not data.get("success"):
                        continue
                    for z in data.get("result", []):
                        results.append({
                            "domain": z.get("name", ""),
                            "registrar": "cloudflare",
                            "status": z.get("status", "unknown"),
                            "dns": "cloudflare",
                            "cloudflare_account": acct,
                        })
            except Exception as e:
                print(f"  ERROR fetching Cloudflare zones ({acct}): {type(e).__name__}: request failed")
        return results


@_register_adapter("njalla")
class NjallaAdapter(RegistrarAdapter):
    name = "njalla"

    def __init__(self):
        self.api_token = keychain_get("njalla-api")

    def test_connection(self) -> tuple[bool, str]:
        if not self.api_token:
            return False, "No API token found in Keychain (njalla-api)"
        try:
            import urllib.request
            ssl_ctx = ssl.create_default_context()
            data = json.dumps({"method": "list-domains", "params": {}}).encode()
            req = urllib.request.Request(
                "https://njal.la/api/1/",
                data=data,
                headers={
                    "Authorization": f"Njalla {self.api_token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                result = json.loads(resp.read())
                if "result" in result:
                    return True, f"Connected OK — {len(result['result'].get('domains', []))} domains"
                return False, f"API error: {result.get('error', 'unknown')}"
        except Exception as e:
            return False, f"{type(e).__name__}: request failed"

    def list_domains(self) -> list[dict]:
        if not self.api_token:
            return []
        try:
            import urllib.request
            ssl_ctx = ssl.create_default_context()
            data = json.dumps({"method": "list-domains", "params": {}}).encode()
            req = urllib.request.Request(
                "https://njal.la/api/1/",
                data=data,
                headers={
                    "Authorization": f"Njalla {self.api_token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
                result = json.loads(resp.read())
                domains = result.get("result", {}).get("domains", [])
                results = []
                for d in domains:
                    results.append({
                        "domain": d.get("name", ""),
                        "registrar": "njalla",
                        "expires": d.get("expiry", "unknown")[:10] if d.get("expiry") else "unknown",
                        "status": "active" if d.get("status") == "active" else d.get("status", "unknown"),
                        "locked": d.get("locked", False),
                    })
                return results
        except Exception as e:
            print(f"  ERROR fetching Njalla domains: {type(e).__name__}: request failed")
            return []


# ---------------------------------------------------------------------------
# DNS health checker (stdlib — uses subprocess dig/nslookup)
# ---------------------------------------------------------------------------

def check_dns_health(domain: str, verbose: bool = False) -> dict:
    """Check DNS resolution for a domain."""
    result = {"domain": domain, "resolves": False, "records": {}}
    try:
        import socket
        addrs = socket.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
        if addrs:
            result["resolves"] = True
            result["ip"] = addrs[0][4][0]
    except socket.gaierror:
        result["resolves"] = False

    if verbose:
        # Get NS records
        try:
            ns_out = subprocess.run(
                ["dig", "+short", "NS", domain], capture_output=True, text=True, timeout=5,
            )
            result["records"]["NS"] = [l.strip() for l in ns_out.stdout.strip().splitlines() if l.strip()]
        except Exception:
            pass
        # Get A records
        try:
            a_out = subprocess.run(
                ["dig", "+short", "A", domain], capture_output=True, text=True, timeout=5,
            )
            result["records"]["A"] = [l.strip() for l in a_out.stdout.strip().splitlines() if l.strip()]
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_status(args):
    """Full registry overview grouped by status."""
    registry = load_registry()
    if not registry:
        print("Registry is empty.")
        return

    by_status = {}
    for domain, info in registry.items():
        if not isinstance(info, dict):
            continue
        s = info.get("status", "unknown")
        by_status.setdefault(s, []).append((domain, info))

    total = sum(len(v) for v in by_status.values())
    print(f"\n{'='*60}")
    print(f"  DOMAIN REGISTRY — {total} domains across all registrars")
    print(f"{'='*60}\n")

    status_order = ["active", "redirect", "reserved", "parked", "for-sale", "unknown"]
    status_icons = {
        "active": "🟢", "redirect": "↪️ ", "reserved": "🔒",
        "parked": "🅿️ ", "for-sale": "💰", "unknown": "❓",
    }

    for status in status_order:
        domains = by_status.pop(status, [])
        if not domains:
            continue
        icon = status_icons.get(status, "•")
        print(f"  {icon} {status.upper()} ({len(domains)})")
        print(f"  {'─'*50}")
        for domain, info in sorted(domains):
            registrar = info.get("registrar", "?")
            capsule = info.get("capsule", "n/a")
            expires = info.get("expires", "?")
            line = f"    {domain:<30} {registrar:<12} exp: {expires}"
            if capsule and capsule != "n/a":
                line += f"  [{capsule}]"
            print(line)
        print()

    # Any remaining statuses not in our order
    for status, domains in by_status.items():
        icon = "•"
        print(f"  {icon} {status.upper()} ({len(domains)})")
        print(f"  {'─'*50}")
        for domain, info in sorted(domains):
            print(f"    {domain:<30} {info.get('registrar', '?')}")
        print()

    # Registrar summary
    by_reg = {}
    for domain, info in registry.items():
        if isinstance(info, dict):
            r = info.get("registrar", "unknown")
            by_reg[r] = by_reg.get(r, 0) + 1
    print(f"  📊 By registrar: {', '.join(f'{r}: {c}' for r, c in sorted(by_reg.items()))}")
    print()


def cmd_list(args):
    """List domains with optional filters."""
    registry = load_registry()
    results = []

    for domain, info in registry.items():
        if not isinstance(info, dict):
            continue
        if args.registrar and info.get("registrar") != args.registrar:
            continue
        if args.status and info.get("status") != args.status:
            continue
        results.append((domain, info))

    if not results:
        print("No domains match your filters.")
        return

    print(f"\n{'Domain':<30} {'Registrar':<12} {'DNS':<12} {'Status':<10} {'Expires':<12} {'Capsule'}")
    print("─" * 90)
    for domain, info in sorted(results):
        print(
            f"{domain:<30} {info.get('registrar', '?'):<12} "
            f"{info.get('dns', '?'):<12} {info.get('status', '?'):<10} "
            f"{info.get('expires', '?'):<12} {info.get('capsule', 'n/a')}"
        )
    print(f"\n{len(results)} domain(s)")


def cmd_search(args):
    """Search domains by name."""
    registry = load_registry()
    query = args.query.lower()
    results = [
        (d, info) for d, info in registry.items()
        if isinstance(info, dict) and query in d.lower()
    ]
    if not results:
        print(f"No domains matching '{args.query}'")
        return

    for domain, info in sorted(results):
        print(f"\n  {domain}")
        for k, v in info.items():
            print(f"    {k}: {v}")


def cmd_expiring(args):
    """Show domains expiring within N days."""
    registry = load_registry()
    days = args.days
    cutoff = datetime.now() + timedelta(days=days)
    expiring = []

    for domain, info in registry.items():
        if not isinstance(info, dict):
            continue
        exp = info.get("expires", "unknown")
        if exp == "unknown" or not exp:
            expiring.append((domain, info, None, "UNKNOWN"))
            continue
        try:
            exp_date = datetime.strptime(str(exp)[:10], "%Y-%m-%d")
            if exp_date <= cutoff:
                days_left = (exp_date - datetime.now()).days
                expiring.append((domain, info, exp_date, f"{days_left}d"))
        except ValueError:
            pass

    if not expiring:
        print(f"No domains expiring within {days} days.")
        return

    # Sort: unknown first, then by days remaining
    expiring.sort(key=lambda x: (x[2] is not None, x[2] or datetime.max))

    print(f"\n⚠️  Domains expiring within {days} days (or unknown expiry):\n")
    print(f"{'Domain':<30} {'Registrar':<12} {'Expires':<12} {'Remaining'}")
    print("─" * 70)
    for domain, info, exp_date, remaining in expiring:
        exp_str = exp_date.strftime("%Y-%m-%d") if exp_date else "unknown"
        print(f"{domain:<30} {info.get('registrar', '?'):<12} {exp_str:<12} {remaining}")
    print(f"\n{len(expiring)} domain(s)")


def cmd_health(args):
    """Check DNS health for domains."""
    registry = load_registry()

    if args.domain:
        domains = [(args.domain, registry.get(args.domain, {}))]
    else:
        domains = [
            (d, info) for d, info in registry.items()
            if isinstance(info, dict) and info.get("status") in ("active", "redirect")
        ]

    print(f"\n🏥 DNS Health Check — {len(domains)} domain(s)\n")
    healthy = 0
    unhealthy = 0

    for domain, info in sorted(domains):
        result = check_dns_health(domain, verbose=args.verbose)
        if result["resolves"]:
            status = f"✅ {result.get('ip', 'OK')}"
            healthy += 1
        else:
            status = "❌ NOT RESOLVING"
            unhealthy += 1

        print(f"  {domain:<30} {status}")
        if args.verbose and result.get("records"):
            for rtype, records in result["records"].items():
                print(f"    {rtype}: {', '.join(records)}")

    print(f"\n  ✅ {healthy} healthy / ❌ {unhealthy} unhealthy")


def cmd_sync(args):
    """Sync domains from registrar APIs into the YAML registry."""
    registry = load_registry()
    target_registrars = [args.registrar] if args.registrar else list(REGISTRAR_ADAPTERS.keys())

    print(f"\n🔄 Syncing from: {', '.join(target_registrars)}\n")

    new_count = 0
    updated_count = 0

    for reg_name in target_registrars:
        adapter_cls = REGISTRAR_ADAPTERS.get(reg_name)
        if not adapter_cls:
            print(f"  ⚠️  No adapter for '{reg_name}' — skipping")
            continue

        adapter = adapter_cls()
        ok, msg = adapter.test_connection()
        if not ok:
            print(f"  ❌ {reg_name}: {msg}")
            continue

        print(f"  🔗 {reg_name}: {msg}")
        api_domains = adapter.list_domains()
        print(f"     Found {len(api_domains)} domains from API")

        for d in api_domains:
            domain_name = d.pop("domain", "")
            if not domain_name:
                continue

            if domain_name in registry and isinstance(registry[domain_name], dict):
                # Update existing — merge API data without overwriting manual fields
                existing = registry[domain_name]
                changed = False
                for key in ("expires", "auto_renew", "privacy", "locked"):
                    if key in d and d[key] != existing.get(key):
                        if not args.dry_run:
                            existing[key] = d[key]
                        changed = True
                if changed:
                    updated_count += 1
                    if args.dry_run:
                        print(f"     [DRY RUN] Would update: {domain_name}")
                    else:
                        print(f"     ✏️  Updated: {domain_name}")
            else:
                # New domain not in registry
                new_count += 1
                if args.dry_run:
                    print(f"     [DRY RUN] Would add: {domain_name}")
                else:
                    new_entry = {
                        "registrar": reg_name,
                        "dns": "unknown",
                        "hosting": "none",
                        "capsule": "n/a",
                        "purpose": "Synced from API — needs classification",
                        "status": d.get("status", "unknown"),
                    }
                    for wl_key in ("expires", "auto_renew", "privacy", "locked"):
                        if wl_key in d:
                            new_entry[wl_key] = d[wl_key]
                    registry[domain_name] = new_entry
                    print(f"     ➕ Added: {domain_name}")

    if not args.dry_run and (new_count > 0 or updated_count > 0):
        save_registry(registry)
        print(f"\n  💾 Registry saved — {new_count} new, {updated_count} updated")
    elif args.dry_run:
        print(f"\n  [DRY RUN] Would add {new_count}, update {updated_count}")
    else:
        print(f"\n  ✅ Registry is up to date — no changes needed")


def cmd_registrars(args):
    """Show configured registrars and their API status."""
    print("\n📋 Configured Registrars\n")
    print(f"{'Registrar':<15} {'API Key':<15} {'Connection'}")
    print("─" * 50)

    for name, adapter_cls in sorted(REGISTRAR_ADAPTERS.items()):
        adapter = adapter_cls()
        ok, msg = adapter.test_connection()
        conn_status = f"✅ {msg}" if ok else f"❌ {msg}"
        if ok:
            key_status = "✅ Found"
        elif "not yet implemented" in msg.lower():
            # Adapter not built yet — check keychain directly
            key_status = "❌ Missing"
            for suffix in ["api", "api-key"]:
                if keychain_get(f"{name}-{suffix}"):
                    key_status = "✅ Found"
                    break
        else:
            # Real connection error — check keychain to distinguish key missing vs other failure
            key_status = "❌ Missing"
            for suffix in ["api", "api-key"]:
                if keychain_get(f"{name}-{suffix}"):
                    key_status = "✅ Found"
                    break
        print(f"{name:<15} {key_status:<15} {conn_status}")


def _adapter_for_domain(domain: str, override_registrar: str | None = None):
    """Resolve which adapter to use for a domain. Uses registry lookup unless overridden."""
    if override_registrar:
        reg_name = override_registrar
    else:
        registry = load_registry()
        info = registry.get(domain)
        if not isinstance(info, dict):
            raise RuntimeError(
                f"Domain '{domain}' not found in registry. "
                f"Use --registrar to override or add it to the registry first."
            )
        reg_name = info.get("registrar")
        if not reg_name:
            raise RuntimeError(f"No registrar set for '{domain}' in registry")

    adapter_cls = REGISTRAR_ADAPTERS.get(reg_name)
    if not adapter_cls:
        raise RuntimeError(
            f"No adapter registered for '{reg_name}'. "
            f"Available: {', '.join(REGISTRAR_ADAPTERS.keys())}"
        )
    return reg_name, adapter_cls()


def _print_records_table(records: list[dict], title: str | None = None) -> None:
    if title:
        print(f"\n  {title}")
    if not records:
        print("    (no records)")
        return
    print(f"    {'Type':<8} {'Name':<25} {'Address':<45} {'TTL':<8} {'MX'}")
    print(f"    {'─'*4:<8} {'─'*4:<25} {'─'*7:<45} {'─'*3:<8} {'─'*2}")
    # Sort: by name then type for stable display
    for r in sorted(records, key=lambda x: (x.get("name", ""), x.get("type", ""))):
        mx = str(r.get("mx_pref", "")) if r.get("type") == "MX" else ""
        print(
            f"    {r.get('type', ''):<8} "
            f"{(r.get('name') or '@'):<25} "
            f"{r.get('address', ''):<45} "
            f"{r.get('ttl', ''):<8} {mx}"
        )


def _print_diff(result: dict) -> None:
    """Pretty-print a DNS write result with before/after/changed."""
    changed = result.get("changed") or []
    if not changed:
        print("\n  ✅ No changes — record set already matches.")
        return

    print(f"\n  📝 {len(changed)} change(s):")
    for c in changed:
        action = c["action"]
        rec = c["record"]
        name = rec.get("name", "@")
        rtype = rec.get("type", "")
        addr = rec.get("address", "")
        ttl = rec.get("ttl", "")
        if action == "add":
            print(f"    ➕ ADD    {rtype:<6} {name:<25} → {addr}  (ttl {ttl})")
        elif action == "delete":
            print(f"    ➖ DELETE {rtype:<6} {name:<25} → {addr}")
        elif action == "modify":
            old = c.get("before", {})
            mx_suffix = ""
            if rtype == "MX":
                old_pref = old.get("mx_pref")
                new_pref = rec.get("mx_pref")
                if old_pref != new_pref:
                    mx_suffix = f"  [pref {old_pref} → {new_pref}]"
            print(
                f"    ✏️  MODIFY {rtype:<6} {name:<25} "
                f"{old.get('address', '')} (ttl {old.get('ttl', '')}) "
                f"→ {addr} (ttl {ttl}){mx_suffix}"
            )

    if result.get("dry_run"):
        print("\n  🔍 DRY RUN — no changes written.")
    else:
        print("\n  💾 Changes written to registrar.")


def cmd_dns(args):
    """DNS management subcommands."""
    action = args.dns_action
    if not action:
        print("Usage: dns {list|set|delete|vercel} <domain> ...")
        sys.exit(1)

    try:
        reg_name, adapter = _adapter_for_domain(args.domain, args.registrar)
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"\n🌐 {args.domain} (registrar: {reg_name})")

    try:
        if action == "list":
            records = adapter.get_dns(args.domain)
            _print_records_table(records, title=f"Current DNS records ({len(records)})")
            print()

        elif action == "set":
            # m6: validate value is non-empty before proceeding
            if not args.value or not args.value.strip():
                print("❌ Record value cannot be empty.")
                sys.exit(1)
            record = {
                "type": args.type,
                "name": args.name,
                "address": args.value,
                "ttl": args.ttl,
            }
            if args.mx_pref is not None:
                record["mx_pref"] = args.mx_pref
            mode = "append" if args.append else "upsert"
            result = adapter.set_dns_record(
                args.domain, record, mode=mode, dry_run=args.dry_run
            )
            _print_records_table(result["before"], title="Before")
            _print_records_table(result["after"], title="After")
            _print_diff(result)

        elif action == "delete":
            result = adapter.delete_dns_record(
                args.domain, args.name, record_type=args.type, dry_run=args.dry_run
            )
            _print_records_table(result["before"], title="Before")
            _print_records_table(result["after"], title="After")
            _print_diff(result)

        elif action == "vercel":
            # Vercel hosting recipe: apex A → 76.76.21.21, www CNAME → cname.vercel-dns.com.
            records = [
                {"type": "A", "name": "@", "address": "76.76.21.21", "ttl": 1800},
                # Namecheap treats CNAME values as FQDNs; trailing dot is
                # unnecessary and is stripped during normalization.
                {"type": "CNAME", "name": "www", "address": "cname.vercel-dns.com", "ttl": 1800},
            ]
            try:
                result = adapter.set_dns_records(
                    args.domain, records, replace_all=False, dry_run=args.dry_run
                )
            except RuntimeError as e:
                # M4: set_dns_records now refuses to collapse multiple existing
                # records at the same (name, type). Surface a clear actionable
                # message rather than auto-collapsing.
                msg = str(e)
                if "existing records match" in msg or "Refusing to upsert" in msg:
                    print(
                        f"\n  ❌ Existing zone has multiple records at the apex/www slot. "
                        f"Inspect with `dns list {args.domain}` and resolve manually "
                        f"before re-running `dns vercel`."
                    )
                    print(f"     ({msg})")
                    sys.exit(1)
                raise
            print("\n  🚀 Vercel hosting recipe:")
            print("     A     @     → 76.76.21.21")
            print("     CNAME www   → cname.vercel-dns.com")
            _print_records_table(result["before"], title="Before")
            _print_records_table(result["after"], title="After")
            _print_diff(result)

        else:
            print(f"Unknown DNS action: {action}")
            sys.exit(1)

    except NotImplementedError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")
        sys.exit(1)


def cmd_test(args):
    """Test API connectivity for a specific registrar."""
    adapter_cls = REGISTRAR_ADAPTERS.get(args.registrar)
    if not adapter_cls:
        print(f"Unknown registrar: {args.registrar}")
        print(f"Available: {', '.join(REGISTRAR_ADAPTERS.keys())}")
        sys.exit(1)

    adapter = adapter_cls()
    ok, msg = adapter.test_connection()
    if ok:
        print(f"✅ {args.registrar}: {msg}")
    else:
        print(f"❌ {args.registrar}: {msg}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Domain Registry CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Full registry overview")

    p_list = sub.add_parser("list", help="List domains")
    p_list.add_argument("--registrar", help="Filter by registrar")
    p_list.add_argument("--status", help="Filter by status")

    p_search = sub.add_parser("search", help="Search domains by name")
    p_search.add_argument("query", help="Search query")

    p_exp = sub.add_parser("expiring", help="Show expiring domains")
    p_exp.add_argument("--days", type=int, default=60, help="Days until expiry (default: 60)")

    p_health = sub.add_parser("health", help="DNS health check")
    p_health.add_argument("--domain", help="Check specific domain")
    p_health.add_argument("--verbose", "-v", action="store_true", help="Show DNS records")

    p_sync = sub.add_parser("sync", help="Sync from registrar APIs")
    p_sync.add_argument("--registrar", help="Sync specific registrar")
    p_sync.add_argument("--dry-run", action="store_true", help="Preview without writing")

    sub.add_parser("registrars", help="Show configured registrars")

    p_test = sub.add_parser("test", help="Test registrar API connectivity")
    p_test.add_argument("--registrar", required=True, help="Registrar to test")

    # DNS management subcommands
    p_dns = sub.add_parser("dns", help="DNS record management (read/set/delete)")
    dns_sub = p_dns.add_subparsers(dest="dns_action")

    # m8: --registrar placed on EACH action subparser (parent subparser
    # options aren't accepted after the action keyword in argparse).
    _registrar_help = "Override registrar (defaults to registry lookup)"

    p_dns_list = dns_sub.add_parser("list", help="Show current DNS records")
    p_dns_list.add_argument("domain", help="Domain to query")
    p_dns_list.add_argument("--registrar", help=_registrar_help)

    p_dns_set = dns_sub.add_parser("set", help="Add or update a DNS record (upsert by name+type)")
    p_dns_set.add_argument("domain", help="Domain")
    p_dns_set.add_argument("type", help="Record type (A, CNAME, TXT, MX, AAAA, ...)")
    p_dns_set.add_argument("name", help="Hostname (e.g., '@', 'www', 'mail')")
    p_dns_set.add_argument("value", help="Record value/address")
    p_dns_set.add_argument("--ttl", type=int, default=1800, help="TTL in seconds (default 1800)")
    p_dns_set.add_argument("--mx-pref", type=int, default=None, help="MX preference (for MX records)")
    p_dns_set.add_argument("--append", action="store_true",
                           help="Append even if a record with same name+type exists (allow duplicates)")
    p_dns_set.add_argument("--dry-run", action="store_true", help="Show planned diff without writing")
    p_dns_set.add_argument("--registrar", help=_registrar_help)

    p_dns_del = dns_sub.add_parser("delete", help="Remove records matching name+type")
    p_dns_del.add_argument("domain", help="Domain")
    p_dns_del.add_argument("type", help="Record type")
    p_dns_del.add_argument("name", help="Hostname")
    p_dns_del.add_argument("--dry-run", action="store_true", help="Show planned diff without writing")
    p_dns_del.add_argument("--registrar", help=_registrar_help)

    p_dns_vercel = dns_sub.add_parser("vercel", help="Configure domain for Vercel hosting (apex A + www CNAME)")
    p_dns_vercel.add_argument("domain", help="Domain to point at Vercel")
    p_dns_vercel.add_argument("--dry-run", action="store_true", help="Show planned diff without writing")
    p_dns_vercel.add_argument("--registrar", help=_registrar_help)

    args = parser.parse_args()

    commands = {
        "status": cmd_status,
        "list": cmd_list,
        "search": cmd_search,
        "expiring": cmd_expiring,
        "health": cmd_health,
        "sync": cmd_sync,
        "registrars": cmd_registrars,
        "test": cmd_test,
        "dns": cmd_dns,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
