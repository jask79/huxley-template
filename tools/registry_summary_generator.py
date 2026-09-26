#!/usr/bin/env python3
"""
Registry Summary Generator

Creates lightweight summary files for large registry data files
to reduce token consumption during background monitoring and analytics.

Phase 4 of token optimization.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Paths
BUILDEOROS_ROOT = Path(__file__).parent.parent
REGISTRY_DIR = BUILDEOROS_ROOT / "registry"
SUMMARY_DIR = REGISTRY_DIR / "summaries"

# Files to summarize
REGISTRY_FILES = {
    "remediation_skills.json": {
        "description": "Remediation skills and capabilities",
        "summary_fields": ["skill_id", "name", "category", "tags"],
        "max_entries": 50  # Top 50 skills
    },
    "claude_agents.json": {
        "description": "Claude agent capabilities and routing",
        "summary_fields": ["name", "type", "capabilities", "domain"],
        "max_entries": None  # Keep all
    },
    "dependency-graph.json": {
        "description": "System dependency mapping",
        "summary_fields": ["node", "type", "dependencies"],
        "max_entries": 30  # Top 30 nodes
    },
    "agent_usage.jsonl": {
        "description": "Agent usage analytics",
        "is_jsonl": True,
        "max_entries": 20  # Recent 20 entries
    }
}


def load_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL file."""
    entries = []
    if file_path.exists():
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    return entries


def summarize_remediation_skills(data: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize remediation skills."""
    # Count by category
    categories = {}
    skills = data.get("skills", [])

    for skill in skills:
        category = skill.get("category", "uncategorized")
        if category not in categories:
            categories[category] = 0
        categories[category] += 1

    # Extract top skills (by usage or priority)
    top_skills = []
    for skill in skills[:50]:  # Top 50
        top_skills.append({
            "id": skill.get("skill_id", skill.get("id")),
            "name": skill.get("name"),
            "category": skill.get("category"),
            "tags": skill.get("tags", [])[:5]  # First 5 tags
        })

    return {
        "generated_at": datetime.now().isoformat(),
        "total_skills": len(skills),
        "categories": categories,
        "top_skills": top_skills,
        "version": data.get("version", "unknown")
    }


def summarize_claude_agents(data: Any) -> Dict[str, Any]:
    """Summarize Claude agents."""
    if isinstance(data, list):
        agents = data
    elif isinstance(data, dict):
        agents_dict = data.get("agents", {})
        if isinstance(agents_dict, dict):
            agents = list(agents_dict.values())
        else:
            agents = agents_dict
    else:
        agents = []

    # Categorize by scope and specialization
    scopes = {}
    specializations = {}
    agent_list = []

    for agent in agents:
        scope = agent.get("scope", "unknown")
        specialization = agent.get("specialization") or agent.get("domain", "general")

        scopes[scope] = scopes.get(scope, 0) + 1
        specializations[specialization] = specializations.get(specialization, 0) + 1

        # Extract MCP tools if available
        mcp_tools = []
        metadata = agent.get("metadata", {})
        tools = metadata.get("tools", "")
        if "mcp:" in tools:
            mcp_tools = [t.strip() for t in tools.split(",") if "mcp:" in t]

        agent_list.append({
            "id": agent.get("id"),
            "name": agent.get("name"),
            "display_name": agent.get("display_name"),
            "scope": scope,
            "specialization": specialization,
            "mcp_tools": mcp_tools[:3]  # First 3 MCP tools
        })

    return {
        "generated_at": datetime.now().isoformat(),
        "total_agents": len(agents),
        "scopes": scopes,
        "specializations": specializations,
        "agents": agent_list,
        "version": data.get("version", "unknown") if isinstance(data, dict) else "unknown"
    }


def summarize_dependency_graph(data: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize dependency graph."""
    nodes_data = data.get("nodes", {})
    edges_data = data.get("edges", {})

    # Handle both dict and list formats
    if isinstance(nodes_data, dict):
        nodes = list(nodes_data.values())
    else:
        nodes = nodes_data

    if isinstance(edges_data, dict):
        edges = list(edges_data.values())
    else:
        edges = edges_data

    # Count by type
    node_types = {}
    for node in nodes:
        node_type = node.get("type", "unknown")
        node_types[node_type] = node_types.get(node_type, 0) + 1

    # Extract key nodes (most connected)
    node_connections = {}
    for edge in edges:
        source = edge.get("source") or edge.get("from") or edge.get("from_node")
        target = edge.get("target") or edge.get("to") or edge.get("to_node")
        if source:
            node_connections[source] = node_connections.get(source, 0) + 1
        if target:
            node_connections[target] = node_connections.get(target, 0) + 1

    # Top 30 most connected nodes
    top_nodes = sorted(node_connections.items(), key=lambda x: x[1], reverse=True)[:30]

    return {
        "generated_at": datetime.now().isoformat(),
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "node_types": node_types,
        "most_connected": [{"node": n, "connections": c} for n, c in top_nodes]
    }


def summarize_agent_usage(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize agent usage analytics."""
    # Count by agent
    agent_counts = {}
    agent_success = {}

    for entry in entries:
        agent = entry.get("agent", "unknown")
        success = entry.get("success", True)

        agent_counts[agent] = agent_counts.get(agent, 0) + 1

        if agent not in agent_success:
            agent_success[agent] = {"success": 0, "total": 0}

        agent_success[agent]["total"] += 1
        if success:
            agent_success[agent]["success"] += 1

    # Calculate success rates
    agent_stats = []
    for agent, counts in agent_counts.items():
        success_rate = 0
        if agent in agent_success:
            stats = agent_success[agent]
            if stats["total"] > 0:
                success_rate = stats["success"] / stats["total"]

        agent_stats.append({
            "agent": agent,
            "total_uses": counts,
            "success_rate": round(success_rate * 100, 1)
        })

    # Sort by usage
    agent_stats = sorted(agent_stats, key=lambda x: x["total_uses"], reverse=True)

    return {
        "generated_at": datetime.now().isoformat(),
        "total_entries": len(entries),
        "unique_agents": len(agent_counts),
        "agent_statistics": agent_stats[:20],  # Top 20
        "recent_entries": entries[-10:]  # Last 10
    }


def generate_summaries():
    """Generate all registry summaries."""
    print("Registry Summary Generator")
    print("=" * 80)

    # Create summary directory
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n1. Summary directory: {SUMMARY_DIR}")

    print(f"\n2. Generating summaries for {len(REGISTRY_FILES)} registry files...")

    total_original = 0
    total_summary = 0
    summaries_created = 0

    for filename, config in REGISTRY_FILES.items():
        file_path = REGISTRY_DIR / filename

        if not file_path.exists():
            print(f"\n   ⚠️  {filename}: File not found, skipping")
            continue

        print(f"\n   Processing: {filename}")
        print(f"   Description: {config['description']}")

        original_size = os.path.getsize(file_path)
        total_original += original_size

        # Load data
        if config.get("is_jsonl"):
            data = load_jsonl(file_path)
        else:
            with open(file_path, 'r') as f:
                data = json.load(f)

        # Generate summary
        summary = None
        if filename == "remediation_skills.json":
            summary = summarize_remediation_skills(data)
        elif filename == "claude_agents.json":
            summary = summarize_claude_agents(data)
        elif filename == "dependency-graph.json":
            summary = summarize_dependency_graph(data)
        elif filename == "agent_usage.jsonl":
            summary = summarize_agent_usage(data)

        if summary:
            # Save summary
            if filename.endswith(".jsonl"):
                summary_filename = filename.replace(".jsonl", ".summary.json")
            else:
                summary_filename = filename.replace(".json", ".summary.json")
            summary_path = SUMMARY_DIR / summary_filename

            with open(summary_path, 'w') as f:
                json.dump(summary, f, indent=2)

            summary_size = os.path.getsize(summary_path)
            total_summary += summary_size
            summaries_created += 1

            reduction = ((original_size - summary_size) / original_size * 100) if original_size > 0 else 0

            print(f"   Original: {original_size / 1024:.1f} KB")
            print(f"   Summary: {summary_size / 1024:.1f} KB")
            print(f"   Reduction: {reduction:.1f}%")
            print(f"   ✓ Saved to: {summary_filename}")

    # Overall summary
    print(f"\n3. Overall Summary:")
    print(f"   Files processed: {summaries_created}")
    print(f"   Original total: {total_original / 1024:.1f} KB")
    print(f"   Summary total: {total_summary / 1024:.1f} KB")

    if total_original > 0:
        overall_reduction = ((total_original - total_summary) / total_original * 100)
        print(f"   Overall reduction: {overall_reduction:.1f}%")
        print(f"   Token savings: ~{(total_original - total_summary) / 1024:.1f} KB per access")

    print(f"\n✅ Registry summaries generated successfully!")
    print(f"\nUsage:")
    print(f"   - Load summary files from registry/summaries/ for quick access")
    print(f"   - Fall back to full files when detailed data needed")
    print(f"   - Regenerate summaries after registry updates")

    # Create index
    print(f"\n4. Creating summary index...")
    index = {
        "generated_at": datetime.now().isoformat(),
        "summaries": {},
        "total_original_size": total_original,
        "total_summary_size": total_summary,
        "reduction_percentage": round((total_original - total_summary) / total_original * 100, 1) if total_original > 0 else 0
    }

    for filename in REGISTRY_FILES.keys():
        if filename.endswith(".jsonl"):
            summary_filename = filename.replace(".jsonl", ".summary.json")
        else:
            summary_filename = filename.replace(".json", ".summary.json")
        summary_path = SUMMARY_DIR / summary_filename

        if summary_path.exists():
            index["summaries"][filename] = {
                "summary_file": summary_filename,
                "summary_path": str(summary_path.relative_to(BUILDEOROS_ROOT)),
                "size_kb": round(os.path.getsize(summary_path) / 1024, 1)
            }

    index_path = SUMMARY_DIR / "index.json"
    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)

    print(f"   ✓ Index saved to: index.json")


if __name__ == "__main__":
    generate_summaries()
