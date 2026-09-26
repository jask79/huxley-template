"""
JSON bridge for Codex integration.

Usage:
  echo '{"query": "what is the EU AI Act?", "n": 6, "providers": "tavily,brave,ddg", "llm": "auto", "quotes": 5}' \
    | python -m tools.research.bridge --stdin

This prints a single JSON object with answer, sources, quotes, and stats.
"""

import argparse
import json
import sys
from typing import Any, Dict

from .cli import run as research_run


def main() -> None:
    p = argparse.ArgumentParser(description="Research JSON bridge")
    p.add_argument("--stdin", action="store_true", help="Read JSON input from stdin")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = p.parse_args()

    if not args.stdin:
        print(json.dumps({"error": "Use --stdin and provide a JSON payload"}))
        sys.exit(2)

    try:
        payload_in: Dict[str, Any] = json.loads(sys.stdin.read())
    except Exception as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(2)

    query = payload_in.get("query")
    if not query:
        print(json.dumps({"error": "Missing 'query'"}))
        sys.exit(2)

    n = int(payload_in.get("n", 8))
    providers = payload_in.get("providers", "tavily,brave,serpapi,ddg")
    llm = payload_in.get("llm", "auto")
    max_per_domain = int(payload_in.get("max_per_domain", 1))
    recency = float(payload_in.get("recency", 0.35))
    follow = int(payload_in.get("follow", 0))
    quotes_k = int(payload_in.get("quotes", 0))

    out = research_run(
        query=query,
        n=n,
        provider_list=providers,
        llm=(llm if llm != "off" else ""),
        json_out=True,
        max_per_domain=max_per_domain,
        recency_weight=recency,
        follow=follow,
        quotes_k=quotes_k,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()

