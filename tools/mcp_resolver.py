#!/usr/bin/env python3
import json, sys, os, pathlib

def load_profile(base_dir, name, seen=None):
    seen = seen or set()
    path = pathlib.Path(base_dir) / f"{name}.json"
    data = json.load(open(path))
    merged = {"servers": []}
    if "extends" in data:
        parent = data["extends"]
        if parent in seen:
            raise RuntimeError("Profile extends cycle detected")
        seen.add(parent)
        parent_data = load_profile(base_dir, parent, seen)
        merged["servers"] = parent_data["servers"]
    # merge servers by unique 'name'
    names = {s["name"] for s in merged["servers"]}
    for s in data.get("servers", []):
        if s["name"] not in names:
            merged["servers"].append(s)
            names.add(s["name"])
    return merged

def main():
    if len(sys.argv) < 3:
        print("Usage: mcp_resolver.py <capsule_dir> <profiles_dir>", file=sys.stderr)
        sys.exit(2)
    capsule_dir = pathlib.Path(sys.argv[1])
    profiles_dir = pathlib.Path(sys.argv[2])
    # read ops/mcp.json if present
    intent = {}
    ops_mcp = capsule_dir / "ops" / "mcp.json"
    if ops_mcp.exists():
        intent = json.load(open(ops_mcp))
    profile_name = intent.get("profile", "default")
    profile = load_profile(profiles_dir, profile_name)
    servers = [s["name"] for s in profile.get("servers", [])]
    # include/exclude
    for add in intent.get("include", []):
        if add not in servers:
            servers.append(add)
    for rem in intent.get("exclude", []):
        servers = [s for s in servers if s != rem]
    # output space-separated list for env
    print(" ".join(sorted(set(servers))))

if __name__ == "__main__":
    main()