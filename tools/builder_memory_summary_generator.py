#!/usr/bin/env python3
"""
Huxley Memory Summary Generator

Creates lightweight summary files for quick access to frequently-needed
builder memory data, reducing token consumption for routing decisions.

Phase 4 of token optimization.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Paths
BUILDEOROS_ROOT = Path(__file__).parent.parent
BUILDER_MEMORY_PATH = Path.home() / ".claude" / "mcp-data" / "builder-memory.json"
SUMMARY_DIR = BUILDEOROS_ROOT / "registry" / "builder-memory-summaries"


def extract_key_preferences(memory_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract {{USER_NAME}}'s key preferences and patterns."""
    preferences = {
        "system_architecture": [],
        "workflow_patterns": [],
        "agent_preferences": [],
        "quality_standards": []
    }

    entities = memory_data.get("entities", {})

    # Extract from specific entities
    if "Huxley" in entities:
        preferences["system_architecture"] = entities["Huxley"].get("observations", [])

    if "operational_patterns" in entities:
        preferences["workflow_patterns"] = entities["operational_patterns"].get("observations", [])

    if "agent_ecosystem" in entities:
        preferences["agent_preferences"] = entities["agent_ecosystem"].get("observations", [])

    if "framework_architecture" in entities:
        preferences["quality_standards"] = entities["framework_architecture"].get("observations", [])

    return preferences


def extract_pattern_summary(memory_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract learned patterns summary."""
    patterns = memory_data.get("patterns", {})

    summary = {
        "total_patterns": len(patterns),
        "pattern_categories": {},
        "top_patterns": []
    }

    # Categorize patterns
    for pattern_id, pattern_data in patterns.items():
        category = pattern_data.get("category", "uncategorized")
        if category not in summary["pattern_categories"]:
            summary["pattern_categories"][category] = 0
        summary["pattern_categories"][category] += 1

        # Extract key pattern info
        summary["top_patterns"].append({
            "id": pattern_id,
            "name": pattern_data.get("name", pattern_id),
            "category": category,
            "confidence": pattern_data.get("confidence", 0)
        })

    # Sort by confidence and take top 10
    summary["top_patterns"] = sorted(
        summary["top_patterns"],
        key=lambda p: p.get("confidence", 0),
        reverse=True
    )[:10]

    return summary


def extract_knowledge_index(memory_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract knowledge base index."""
    knowledge = memory_data.get("knowledge_base", {})

    index = {
        "total_documents": len(knowledge),
        "categories": {},
        "key_documents": []
    }

    for doc_id, doc_data in knowledge.items():
        category = doc_data.get("category", "uncategorized")
        if category not in index["categories"]:
            index["categories"][category] = 0
        index["categories"][category] += 1

        # Extract key document info
        index["key_documents"].append({
            "id": doc_id,
            "title": doc_data.get("title", doc_id),
            "category": category,
            "tags": doc_data.get("tags", [])
        })

    # Limit to 20 most recent/relevant
    index["key_documents"] = index["key_documents"][:20]

    return index


def extract_agent_routing_context(memory_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract context relevant for agent routing decisions."""
    context = {
        "system_overview": [],
        "agent_capabilities": [],
        "workflow_preferences": [],
        "quality_gates": []
    }

    entities = memory_data.get("entities", {})

    # System overview
    if "Huxley" in entities:
        obs = entities["Huxley"].get("observations", [])
        context["system_overview"] = obs[:5]  # Top 5 most important

    # Agent capabilities
    if "agent_ecosystem" in entities:
        context["agent_capabilities"] = entities["agent_ecosystem"].get("observations", [])

    # Workflow preferences
    if "operational_patterns" in entities:
        obs = entities["operational_patterns"].get("observations", [])
        context["workflow_preferences"] = obs

    # Quality gates
    if "framework_architecture" in entities:
        obs = entities["framework_architecture"].get("observations", [])
        context["quality_gates"] = obs[:3]  # Top 3 standards

    return context


def generate_quick_reference(memory_data: Dict[str, Any]) -> str:
    """Generate a human-readable quick reference guide."""
    entities = memory_data.get("entities", {})

    ref = "# Huxley Memory Quick Reference\n\n"
    ref += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    ref += "## System Architecture\n\n"
    if "Huxley" in entities:
        for obs in entities["Huxley"].get("observations", [])[:5]:
            ref += f"- {obs}\n"
    ref += "\n"

    ref += "## Agent Ecosystem\n\n"
    if "agent_ecosystem" in entities:
        for obs in entities["agent_ecosystem"].get("observations", []):
            ref += f"- {obs}\n"
    ref += "\n"

    ref += "## Framework Standards\n\n"
    if "framework_architecture" in entities:
        for obs in entities["framework_architecture"].get("observations", []):
            ref += f"- {obs}\n"
    ref += "\n"

    ref += "## Operational Patterns\n\n"
    if "operational_patterns" in entities:
        for obs in entities["operational_patterns"].get("observations", []):
            ref += f"- {obs}\n"
    ref += "\n"

    return ref


def generate_summaries():
    """Generate all summary files."""
    print("Huxley Memory Summary Generator")
    print("=" * 80)

    # Check if builder-memory.json exists
    if not BUILDER_MEMORY_PATH.exists():
        print(f"\n❌ Error: Huxley memory file not found at {BUILDER_MEMORY_PATH}")
        return

    # Create summary directory
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n1. Summary directory: {SUMMARY_DIR}")

    # Load builder memory
    print(f"\n2. Loading builder memory from: {BUILDER_MEMORY_PATH}")
    with open(BUILDER_MEMORY_PATH, 'r') as f:
        memory_data = json.load(f)

    original_size = os.path.getsize(BUILDER_MEMORY_PATH)
    print(f"   Original size: {original_size:,} bytes ({original_size / 1024:.1f} KB)")

    # Generate summaries
    print(f"\n3. Generating summaries...")

    # 1. Key preferences
    preferences = extract_key_preferences(memory_data)
    pref_path = SUMMARY_DIR / "preferences.json"
    with open(pref_path, 'w') as f:
        json.dump(preferences, f, indent=2)
    pref_size = os.path.getsize(pref_path)
    print(f"   ✓ Preferences: {pref_size:,} bytes ({pref_size / 1024:.1f} KB)")

    # 2. Pattern summary
    patterns = extract_pattern_summary(memory_data)
    pattern_path = SUMMARY_DIR / "patterns.json"
    with open(pattern_path, 'w') as f:
        json.dump(patterns, f, indent=2)
    pattern_size = os.path.getsize(pattern_path)
    print(f"   ✓ Patterns: {pattern_size:,} bytes ({pattern_size / 1024:.1f} KB)")

    # 3. Knowledge index
    knowledge = extract_knowledge_index(memory_data)
    knowledge_path = SUMMARY_DIR / "knowledge-index.json"
    with open(knowledge_path, 'w') as f:
        json.dump(knowledge, f, indent=2)
    knowledge_size = os.path.getsize(knowledge_path)
    print(f"   ✓ Knowledge index: {knowledge_size:,} bytes ({knowledge_size / 1024:.1f} KB)")

    # 4. Agent routing context
    routing = extract_agent_routing_context(memory_data)
    routing_path = SUMMARY_DIR / "routing-context.json"
    with open(routing_path, 'w') as f:
        json.dump(routing, f, indent=2)
    routing_size = os.path.getsize(routing_path)
    print(f"   ✓ Routing context: {routing_size:,} bytes ({routing_size / 1024:.1f} KB)")

    # 5. Quick reference (markdown)
    quick_ref = generate_quick_reference(memory_data)
    ref_path = SUMMARY_DIR / "quick-reference.md"
    with open(ref_path, 'w') as f:
        f.write(quick_ref)
    ref_size = os.path.getsize(ref_path)
    print(f"   ✓ Quick reference: {ref_size:,} bytes ({ref_size / 1024:.1f} KB)")

    # Summary
    total_summary_size = pref_size + pattern_size + knowledge_size + routing_size + ref_size
    print(f"\n4. Summary:")
    print(f"   Original size: {original_size / 1024:.1f} KB")
    print(f"   Total summaries: {total_summary_size / 1024:.1f} KB")
    print(f"   Most useful for routing: {routing_size / 1024:.1f} KB")
    print(f"   Reduction: {((original_size - routing_size) / original_size * 100):.1f}%")

    print(f"\n✅ Summaries generated successfully!")
    print(f"\nUsage:")
    print(f"   - Load routing-context.json (~{routing_size / 1024:.1f} KB) for routing decisions")
    print(f"   - Load preferences.json for {{USER_NAME}}'s preferences")
    print(f"   - Load quick-reference.md for human-readable overview")
    print(f"   - Fall back to full MCP query when detailed data needed")


if __name__ == "__main__":
    generate_summaries()
