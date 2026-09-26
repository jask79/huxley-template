#!/usr/bin/env python3
"""
Knowledge Graph Summary Generator

Creates lightweight summary and index files for the knowledge graph
to reduce token consumption during routing decisions.

Phase 3 of token optimization.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Paths
BUILDEOROS_ROOT = Path(__file__).parent.parent
KG_PATH = BUILDEOROS_ROOT / "registry" / "knowledge_graph.json"
KG_SUMMARY_PATH = BUILDEOROS_ROOT / "registry" / "knowledge_graph.summary.json"
KG_INDEX_PATH = BUILDEOROS_ROOT / "registry" / "knowledge_graph.index.json"


def generate_summary(kg_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a lightweight summary of the knowledge graph."""
    nodes = kg_data.get("nodes", {})
    edges = kg_data.get("edges", [])

    # Count nodes by type
    type_counts = {}
    for node in nodes.values():
        node_type = node.get("type", "unknown")
        type_counts[node_type] = type_counts.get(node_type, 0) + 1

    # Extract key nodes (root nodes, frequently referenced, etc.)
    key_nodes = {}
    for node_id, node in nodes.items():
        if node.get("data", {}).get("root"):
            key_nodes[node_id] = {
                "id": node_id,
                "type": node.get("type"),
                "name": node.get("name"),
                "tags": node.get("tags", [])
            }

    # Build capsule index (for navigation routing)
    capsules = {}
    for node_id, node in nodes.items():
        if node.get("type") == "capsule":
            capsules[node_id] = {
                "name": node.get("name"),
                "tags": node.get("tags", []),
                "data": node.get("data", {})
            }

    # Build pattern index (for workflow routing)
    patterns = {}
    for node_id, node in nodes.items():
        if node.get("type") == "pattern":
            patterns[node_id] = {
                "name": node.get("name"),
                "tags": node.get("tags", [])
            }

    # Build decision history index (for learning)
    decisions = []
    for node_id, node in nodes.items():
        if node.get("type") == "decision":
            data = node.get("data", {})
            timestamp = data.get("timestamp")
            decisions.append({
                "id": node_id,
                "title": data.get("title", node.get("name", "")),
                "timestamp": timestamp if timestamp else "",
                "tags": node.get("tags", [])
            })

    # Edge statistics
    edge_types = {}
    for edge in edges:
        edge_type = edge.get("type", "unknown")
        edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

    return {
        "generated_at": datetime.now().isoformat(),
        "source_file": str(KG_PATH),
        "source_size_bytes": os.path.getsize(KG_PATH),
        "statistics": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "node_types": type_counts,
            "edge_types": edge_types
        },
        "key_nodes": key_nodes,
        "capsules": capsules,
        "patterns": patterns,
        "recent_decisions": sorted(decisions, key=lambda d: d.get("timestamp", ""), reverse=True)[:10],
        "version": "1.0.0"
    }


def generate_index(kg_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a simple index mapping node IDs to their types and names."""
    nodes = kg_data.get("nodes", {})

    index = {
        "generated_at": datetime.now().isoformat(),
        "total_nodes": len(nodes),
        "nodes": {}
    }

    for node_id, node in nodes.items():
        index["nodes"][node_id] = {
            "type": node.get("type"),
            "name": node.get("name"),
            "tags": node.get("tags", [])
        }

    return index


def main():
    """Generate summary and index files."""
    print("Knowledge Graph Summary Generator")
    print("=" * 50)

    # Load full knowledge graph
    print(f"\n1. Loading knowledge graph from: {KG_PATH}")
    with open(KG_PATH, 'r') as f:
        kg_data = json.load(f)

    original_size = os.path.getsize(KG_PATH)
    print(f"   Original size: {original_size:,} bytes ({original_size / 1024:.1f} KB)")

    # Generate summary
    print(f"\n2. Generating summary...")
    summary = generate_summary(kg_data)

    with open(KG_SUMMARY_PATH, 'w') as f:
        json.dump(summary, f, indent=2)

    summary_size = os.path.getsize(KG_SUMMARY_PATH)
    print(f"   Summary saved to: {KG_SUMMARY_PATH}")
    print(f"   Summary size: {summary_size:,} bytes ({summary_size / 1024:.1f} KB)")
    print(f"   Reduction: {((original_size - summary_size) / original_size * 100):.1f}%")

    # Generate index
    print(f"\n3. Generating index...")
    index = generate_index(kg_data)

    with open(KG_INDEX_PATH, 'w') as f:
        json.dump(index, f, indent=2)

    index_size = os.path.getsize(KG_INDEX_PATH)
    print(f"   Index saved to: {KG_INDEX_PATH}")
    print(f"   Index size: {index_size:,} bytes ({index_size / 1024:.1f} KB)")
    print(f"   Reduction: {((original_size - index_size) / original_size * 100):.1f}%")

    # Summary statistics
    print(f"\n4. Summary Statistics:")
    print(f"   Total nodes: {summary['statistics']['total_nodes']}")
    print(f"   Total edges: {summary['statistics']['total_edges']}")
    print(f"   Node types: {dict(summary['statistics']['node_types'])}")
    print(f"   Capsules indexed: {len(summary['capsules'])}")
    print(f"   Recent decisions: {len(summary['recent_decisions'])}")

    print(f"\n✅ Summary and index generated successfully!")
    print(f"\nToken savings per routing decision:")
    print(f"   Before: {original_size / 1024:.1f} KB (full graph)")
    print(f"   After: {summary_size / 1024:.1f} KB (summary)")
    print(f"   Savings: ~{original_size - summary_size:,} bytes ({(original_size - summary_size) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
