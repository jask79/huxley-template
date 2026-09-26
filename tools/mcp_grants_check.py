#!/usr/bin/env python3
"""
MCP Grants Check - Validates that capsule doesn't grant more MCPs than any agent needs
Implements least privilege sanity check for MCP access control
"""
import os, sys, pathlib, re, json

def parse_frontmatter(path):
    """Extract YAML frontmatter from agent file"""
    try:
        txt = open(path, encoding="utf-8").read()
        m = re.match(r"^---\n(.*?)\n---\n", txt, flags=re.S)
        if not m: 
            return {}
        try:
            import yaml
        except ImportError:
            return {}
        return yaml.safe_load(m.group(1)) or {}
    except:
        return {}

def collect_agents(capsule_dir):
    """Collect agents following precedence: capsule → project → user"""
    agents = {}
    search_dirs = [
        pathlib.Path(capsule_dir) / ".claude" / "agents",
        pathlib.Path(os.environ.get("CATALYST_ROOT", pathlib.Path(__file__).resolve().parent.parent)) / ".claude" / "agents",
        pathlib.Path(os.path.expanduser("~/.claude/agents")),
    ]
    
    for d in search_dirs:
        if d.exists():
            for p in d.glob("*.md"):
                agent_name = p.name
                if agent_name not in agents:
                    agents[agent_name] = p
    
    return list(agents.values())

def get_agent_mcp_needs(agents):
    """Extract all MCP servers that agents declare they need"""
    all_needs = set()
    agent_details = []
    
    for agent_path in agents:
        fm = parse_frontmatter(agent_path)
        tools = fm.get("tools") or []
        mcps = {t.split("mcp:",1)[1] for t in tools if isinstance(t,str) and t.startswith("mcp:")}
        
        if mcps:
            agent_details.append({
                "agent": os.path.basename(agent_path),
                "mcps": sorted(mcps)
            })
            all_needs.update(mcps)
    
    return all_needs, agent_details

def main():
    if len(sys.argv) < 3:
        print("Usage: mcp_grants_check.py <capsule_dir> <granted_mcps_space_separated>", file=sys.stderr)
        sys.exit(2)
    
    capsule_dir = sys.argv[1]
    granted = set(sys.argv[2].split())
    
    # Remove standard filesystem tools - these aren't MCPs in the least-privilege sense
    standard_tools = {"filesystem", "git", "http", "keychain-presence", "ccmem"}
    granted_mcps = granted - standard_tools
    
    # Get what agents actually need
    agents = collect_agents(capsule_dir)
    agent_needs, agent_details = get_agent_mcp_needs(agents)
    
    # Find excessive grants
    excessive = granted_mcps - agent_needs
    
    result = {
        "capsule": os.path.basename(capsule_dir),
        "granted_mcps": sorted(granted_mcps),
        "agent_needs": sorted(agent_needs),
        "excessive_grants": sorted(excessive),
        "agent_details": agent_details,
        "has_issues": len(excessive) > 0
    }
    
    print(json.dumps(result))
    return 0

if __name__ == "__main__":
    main()