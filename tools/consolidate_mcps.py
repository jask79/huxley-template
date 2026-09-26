#\!/usr/bin/env python3
import json, os, sys, hashlib
from pathlib import Path
ROOT = Path("{{CATALYST_ROOT}}")
CAPS = ROOT/"capsules"
CLAUDE_MCP = Path.home()/".claude"/"mcp_servers.json"

def load_json(p: Path):
    try: return json.loads(p.read_text())
    except: return {}

def save_json(obj, p: Path):
    p.write_text(json.dumps(obj, indent=2)+"\n")

def get_servers(obj):
    if "mcpServers" in obj:
        return obj["mcpServers"]  # Claude Code format
    return (((obj or {}).get("clients") or {}).get("default") or {}).get("mcpServers") or {}

def sig(cfg: dict)->str:
    cmd = cfg.get("command","")
    args = " ".join(cfg.get("args",[]))
    envk = ",".join(sorted((cfg.get("env") or {}).keys()))
    return hashlib.sha1(f"{cmd}|{args}|{envk}".encode()).hexdigest()

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Consolidate capsule MCPs into Claude Code global config")
    ap.add_argument("--apply-remove-local", action="store_true",
                    help="Remove duplicate local servers from capsules")
    args = ap.parse_args()

    # Load existing Claude Code global MCPs
    claude_mcps = load_json(CLAUDE_MCP)
    global_servers = claude_mcps.get("mcpServers", {})
    original_count = len(global_servers)
    
    # Collect from capsules
    collisions = []
    caps = [d for d in CAPS.iterdir() if d.is_dir()]
    
    for cap in sorted(caps, key=lambda p: p.name):
        local = cap/".mcp.json"
        if not local.exists():
            local = cap/".mcp.json.template"
            if not local.exists(): 
                continue
        data = load_json(local)
        srv = get_servers(data)
        if not isinstance(srv, dict): 
            continue
        
        for name, cfg in srv.items():
            if not isinstance(cfg, dict): 
                continue
            signature = sig(cfg)
            
            # If name exists with different signature, rename to avoid clash
            if name in global_servers and sig(global_servers[name]) != signature:
                new_name = f"{name}-{signature[:6]}"
                collisions.append((name, new_name, cap.name))
                name = new_name
            
            # Add to global if not already there
            if name not in global_servers:
                global_servers[name] = cfg

    # Save updated Claude Code global config
    claude_mcps["mcpServers"] = global_servers
    save_json(claude_mcps, CLAUDE_MCP)
    
    added_count = len(global_servers) - original_count
    print(f"[consolidate] Capsules scanned: {len(caps)}")
    print(f"[consolidate] MCPs added to Claude Code global: {added_count}")
    print(f"[consolidate] Total global MCPs: {len(global_servers)}")
    print(f"[consolidate] Updated: {CLAUDE_MCP}")
    
    if collisions:
        print("[consolidate] Name collisions resolved:")
        for old,new,slug in collisions:
            print(f"  - {old} in {slug} => {new}")

    # Optionally remove duplicates from capsules
    if args.apply_remove_local:
        for cap in caps:
            local = cap/".mcp.json"
            if not local.exists():
                continue
                
            data = load_json(local)
            lmap = get_servers(data)
            changed = False
            
            for name in list(lmap.keys()):
                cfg = lmap[name]
                # Remove if exists globally with same signature
                if name in global_servers and sig(global_servers[name]) == sig(cfg):
                    del lmap[name]
                    changed = True
            
            if changed:
                # Update capsule config to reference globals only
                if "clients" in data:
                    data["clients"]["default"]["mcpServers"] = lmap
                else:
                    data = {"version": 1, "clients": {"default": {"mcpServers": lmap}}}
                
                bak = local.with_suffix(".json.backup")
                if local.exists():
                    bak.write_text(local.read_text())
                save_json(data, local)
                print(f"[prune] Removed duplicate MCPs from {cap.name}")
    
    print("[done]")

if __name__ == "__main__":
    main()
