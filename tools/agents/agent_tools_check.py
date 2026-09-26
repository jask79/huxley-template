#!/usr/bin/env python3
import os, sys, pathlib, re, json

def parse_frontmatter(path):
    txt = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n", txt, flags=re.S)
    if not m: return {}
    try:
        import yaml
    except ImportError:
        print("WARNING: PyYAML not installed; skipping agent frontmatter check", file=sys.stderr)
        return {}
    return yaml.safe_load(m.group(1)) or {}

def collect_agents(capsule_dir):
    # search precedence: capsule → project → user (return highest priority only)
    agents = {}
    search_dirs = [
        pathlib.Path(capsule_dir) / ".claude" / "agents",
        pathlib.Path(os.path.expanduser("{{CATALYST_ROOT}}/.claude/agents")),
        pathlib.Path(os.path.expanduser("~/.claude/agents")),
    ]
    
    for d in search_dirs:
        if d.exists():
            for p in d.glob("*.md"):
                agent_name = p.name
                # Only add if we haven't seen this agent yet (precedence)
                if agent_name not in agents:
                    agents[agent_name] = p
    
    return list(agents.values())

def main():
    if len(sys.argv) < 3:
        print("Usage: agent_tools_check.py <capsule_dir> <granted_list_space_separated>", file=sys.stderr); sys.exit(2)
    capsule_dir = sys.argv[1]
    granted = set(sys.argv[2].split())
    problems = []
    for p in collect_agents(capsule_dir):
        fm = parse_frontmatter(p)
        tools = fm.get("tools") or []
        wants = {t.split("mcp:",1)[1] for t in tools if isinstance(t,str) and t.startswith("mcp:")}
        missing = wants - granted
        if missing:
            problems.append({"agent": str(p), "missing": sorted(missing)})
    print(json.dumps(problems))
    return 0

if __name__ == "__main__":
    main()