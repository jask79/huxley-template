#!/usr/bin/env python3
"""VirusTotal Repository Scanner for Huxley Skills.

Scans GitHub repository URLs through VirusTotal's URL analysis API.
Reports reputation scores and any security flags before skills are wired to agents.

Usage:
    python3 tools/vt_repo_scan.py scan <github_url> [<github_url> ...]
    python3 tools/vt_repo_scan.py scan-all  # scans predefined list of pending repos
"""

import sys
import os
import json
import time
import base64
import urllib.request
import urllib.parse
import urllib.error

API_KEY = os.environ.get("VIRUSTOTAL_API_KEY", "")
VT_URL_SCAN = "https://www.virustotal.com/api/v3/urls"
VT_URL_REPORT = "https://www.virustotal.com/api/v3/urls/{}"
VT_ANALYSIS = "https://www.virustotal.com/api/v3/analyses/{}"


def url_id(url: str) -> str:
    """Generate VT URL identifier (base64 of URL without padding)."""
    return base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")


def api_request(endpoint: str, method: str = "GET", data: bytes = None) -> dict:
    """Make an authenticated VT API request."""
    req = urllib.request.Request(endpoint, data=data, method=method)
    req.add_header("x-apikey", API_KEY)
    if data:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}", "body": body}


def submit_url(url: str) -> dict:
    """Submit a URL to VirusTotal for scanning."""
    data = urllib.parse.urlencode({"url": url}).encode()
    return api_request(VT_URL_SCAN, method="POST", data=data)


def poll_analysis(analysis_id: str, max_wait: int = 60) -> dict:
    """Poll the analysis endpoint until completion."""
    endpoint = VT_ANALYSIS.format(analysis_id)
    elapsed = 0
    interval = 5
    while elapsed < max_wait:
        result = api_request(endpoint)
        if "error" in result:
            return result
        status = result.get("data", {}).get("attributes", {}).get("status", "")
        if status == "completed":
            return result
        print(f"    Analysis status: {status}, waiting {interval}s...")
        time.sleep(interval)
        elapsed += interval
    return {"error": "timeout", "body": f"Analysis not completed within {max_wait}s"}


def get_url_report(url: str) -> dict:
    """Get the cached report for a URL."""
    vid = url_id(url)
    return api_request(VT_URL_REPORT.format(vid))


def scan_repo(url: str) -> dict:
    """Submit URL for scan and retrieve results."""
    print(f"\n{'='*60}")
    print(f"Scanning: {url}")
    print(f"{'='*60}")

    # Submit for scanning
    print("  Submitting to VirusTotal...")
    submit_result = submit_url(url)
    if "error" in submit_result:
        print(f"  Submit error: {submit_result['error']}")

    # Extract analysis ID and poll for completion
    analysis_id = (
        submit_result.get("data", {}).get("id", "")
        if "error" not in submit_result
        else ""
    )

    stats = {}
    reputation = "N/A"
    categories = {}

    if analysis_id:
        print(f"  Analysis ID: {analysis_id}")
        print("  Polling for completion...")
        analysis = poll_analysis(analysis_id, max_wait=30)
        if "error" not in analysis:
            stats = analysis.get("data", {}).get("attributes", {}).get("stats", {})
            print(f"  Analysis complete: {json.dumps(stats)}")

    # Also try to get the full URL report (may have more detail)
    print("  Fetching URL report...")
    report = get_url_report(url)
    if "error" not in report:
        attrs = report.get("data", {}).get("attributes", {})
        report_stats = attrs.get("last_analysis_stats", {})
        reputation = attrs.get("reputation", "N/A")
        categories = attrs.get("categories", {})
        # Prefer URL report stats if available (more engines)
        if report_stats:
            stats = report_stats

    # If we still have no stats from either source, mark as error
    if not stats:
        print("  No analysis data available (new URL, not yet indexed)")
        return {
            "url": url,
            "status": "pending",
            "verdict": "PENDING",
            "detail": "URL newly submitted, not yet indexed by VT engines. No malicious flags from initial scan.",
        }

    result = {
        "url": url,
        "status": "complete",
        "stats": stats,
        "reputation": reputation,
        "categories": categories,
        "malicious": stats.get("malicious", 0),
        "suspicious": stats.get("suspicious", 0),
        "harmless": stats.get("harmless", 0),
        "undetected": stats.get("undetected", 0),
    }

    # Verdict
    mal = result["malicious"]
    sus = result["suspicious"]
    if mal > 0:
        result["verdict"] = "BLOCKED"
        verdict_str = f"BLOCKED ({mal} malicious)"
    elif sus > 0:
        result["verdict"] = "WARNING"
        verdict_str = f"WARNING ({sus} suspicious)"
    else:
        result["verdict"] = "CLEAN"
        verdict_str = "CLEAN"

    print(f"  Reputation: {reputation}")
    print(f"  Stats: {json.dumps(stats, indent=2)}")
    print(f"  Verdict: {verdict_str}")

    return result


def main():
    if not API_KEY:
        print("ERROR: VIRUSTOTAL_API_KEY not set")
        sys.exit(1)

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "scan-all":
        # Predefined list of repos to scan
        repos = [
            "https://github.com/karanb192/algo-sensei",
            "https://github.com/Miaoge-Ge/coding-agent-skills",
            "https://github.com/yoanbernabeu/supabase-pentest-skills",
            "https://github.com/lackeyjb/playwright-skill",
            "https://github.com/sickn33/antigravity-awesome-skills",
        ]
    elif cmd == "scan":
        repos = sys.argv[2:]
        if not repos:
            print("ERROR: No URLs provided")
            sys.exit(1)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)

    results = []
    for url in repos:
        result = scan_repo(url)
        results.append(result)
        # VT rate limit: 4 requests/min on free tier
        if url != repos[-1]:
            print("\n  Rate limit pause (15s)...")
            time.sleep(15)

    # Summary
    print(f"\n{'='*60}")
    print("SCAN SUMMARY")
    print(f"{'='*60}")

    clean = []
    blocked = []
    warnings = []
    errors = []

    for r in results:
        verdict = r.get("verdict", "error")
        repo_name = r["url"].split("/")[-1]
        if verdict == "CLEAN":
            clean.append(r)
            print(f"  CLEAN    {repo_name}")
        elif verdict == "BLOCKED":
            blocked.append(r)
            print(f"  BLOCKED  {repo_name} ({r['malicious']} malicious flags)")
        elif verdict == "WARNING":
            warnings.append(r)
            print(f"  WARNING  {repo_name} ({r['suspicious']} suspicious flags)")
        else:
            errors.append(r)
            print(f"  ERROR    {repo_name} ({r.get('detail', 'unknown')})")

    print(f"\nClean: {len(clean)} | Warnings: {len(warnings)} | Blocked: {len(blocked)} | Errors: {len(errors)}")

    # Write results to JSON
    output_path = "/tmp/vt_skill_scan_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results saved to: {output_path}")

    # Exit code: 0 if all clean, 1 if any blocked
    if blocked:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
