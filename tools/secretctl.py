#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path("{{CATALYST_ROOT}}")
REGISTRY = ROOT / "registry"
EVENTS = REGISTRY / "events.jsonl"

def event(event_type: str, name: str, present: bool, note: str = ""):
    REGISTRY.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    data = {
        "timestamp": ts,
        "type": event_type,
        "secret": name,
        "present": present,
        "note": note,
    }
    try:
        with EVENTS.open("a") as f:
            f.write(json.dumps(data) + "\n")
    except Exception:
        pass

def has_secret(name: str) -> bool:
    # Non-destructive: check environment only
    return bool(os.environ.get(name))

def main():
    p = argparse.ArgumentParser(description="Huxley secretctl: has/get/preflight")
    sub = p.add_subparsers(dest="cmd")

    p_has = sub.add_parser("has", help="Check presence of a secret by name")
    p_has.add_argument("name")

    p_get = sub.add_parser("get", help="Get secret (redacted)")
    p_get.add_argument("name")

    p_pf = sub.add_parser("preflight", help="Preflight common secrets or from capsule requirements")
    p_pf.add_argument("capsule", nargs="?", help="Optional capsule path to derive required secrets")

    args = p.parse_args()

    if args.cmd == "has":
        present = has_secret(args.name)
        event("secret.has", args.name, present)
        print(json.dumps({"name": args.name, "present": present}))
        return 0 if present else 1

    if args.cmd == "get":
        present = has_secret(args.name)
        event("secret.get", args.name, present)
        if present:
            print("REDACTED")
            return 0
        else:
            print("NOT_FOUND")
            return 1

    if args.cmd == "preflight":
        names = ["OPENAI_API_KEY"]
        # Try to read secrets from capsule/spec/requirements.yaml (constraints.secrets)
        if args.capsule:
            req = Path(args.capsule) / "spec" / "requirements.yaml"
            if req.exists():
                try:
                    import re
                    text = req.read_text(encoding="utf-8")
                    # naive parse: lines under 'secrets:' list
                    block = re.search(r"secrets:\s*([\s\S]+)", text)
                    if block:
                        found = re.findall(r"-\s*([A-Za-z0-9_]+)", block.group(1))
                        if found:
                            names = list(dict.fromkeys([n.upper() for n in found]))
                except Exception:
                    pass
        results = []
        overall = True
        for n in names:
            present = has_secret(n)
            results.append({"name": n, "present": present})
            event("secret.preflight", n, present)
            overall = overall and present
        print(json.dumps({"results": results}, indent=2))
        return 0 if overall else 1

    p.print_help()
    return 2

if __name__ == "__main__":
    raise SystemExit(main())

