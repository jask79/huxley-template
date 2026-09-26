#\!/usr/bin/env python3
import json, os, sys
from pathlib import Path

def load(p):
    try:
        with open(p) as f: return json.load(f)
    except: return {}
def save(obj, p):
    p = Path(p)
    temp = p.parent / (p.stem + ".tmp" + p.suffix)
    temp.write_text(json.dumps(obj, indent=2)+"\n")
    temp.replace(p)
def make_abs(x, base):
    if isinstance(x, str) and "/" in x and not os.path.isabs(x): return str(Path(base, x))
    return x
def normalize(m, base):
    servers = (((m or {}).get("clients") or {}).get("default") or {}).get("mcpServers") or {}
    for cfg in servers.values():
        if isinstance(cfg, dict):
            if "command" in cfg: cfg["command"] = make_abs(cfg["command"], base)
            if "args" in cfg and isinstance(cfg["args"], list): cfg["args"] = [make_abs(a, base) for a in cfg["args"]]
    return m
def merge(a,b):
    if not isinstance(a,dict): return b
    out=dict(a)
    for k,v in (b or {}).items():
        out[k]=merge(out[k],v) if k in out and isinstance(out[k],dict) and isinstance(v,dict) else v
    return out
def main():
    if len(sys.argv)<4: sys.exit("usage: merge_mcp.py <gen> <local> <out> [base]")
    gen,loc,out=sys.argv[1:4]; base=sys.argv[4] if len(sys.argv)>4 else str(Path(loc).parent)
    g=load(gen); l=normalize(load(loc), base)
    m=merge(g,l) if l else g
    m.setdefault("version",1); m.setdefault("clients",{}).setdefault("default",{}).setdefault("mcpServers",{})
    save(m,out)
if __name__=="__main__": main()
