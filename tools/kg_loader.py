#!/usr/bin/env python3
"""
Knowledge Graph Loader with Smart Caching

Provides intelligent loading of knowledge graph data with automatic
summary/full detection and caching for token optimization.

Phase 3 of token optimization.

Usage:
    from tools.kg_loader import load_kg, load_kg_summary, load_kg_index

    # For routing decisions (lightweight)
    summary = load_kg_summary()

    # For detailed analysis (full graph)
    kg = load_kg()

    # For quick lookups (minimal)
    index = load_kg_index()
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Paths
BUILDEOROS_ROOT = Path(__file__).parent.parent
KG_PATH = BUILDEOROS_ROOT / "registry" / "knowledge_graph.json"
KG_SUMMARY_PATH = BUILDEOROS_ROOT / "registry" / "knowledge_graph.summary.json"
KG_INDEX_PATH = BUILDEOROS_ROOT / "registry" / "knowledge_graph.index.json"

# In-memory cache with TTL and mtime tracking
_cache = {
    "full": {"data": None, "mtime": None, "loaded_at": None},
    "summary": {"data": None, "mtime": None, "loaded_at": None},
    "index": {"data": None, "mtime": None, "loaded_at": None}
}
_cache_ttl_seconds = 1800  # 30 minutes


def _should_reload(cache_key: str, file_path: Path) -> bool:
    """Check if file needs to be reloaded from disk."""
    cache_entry = _cache[cache_key]

    # Not cached yet
    if cache_entry["data"] is None:
        return True

    # File doesn't exist
    if not file_path.exists():
        return False

    # File modified since last load
    current_mtime = os.path.getmtime(file_path)
    if cache_entry["mtime"] != current_mtime:
        return True

    # TTL expired
    if cache_entry["loaded_at"] is not None:
        age = datetime.now().timestamp() - cache_entry["loaded_at"]
        if age > _cache_ttl_seconds:
            return True

    return False


def load_kg_index(force_reload: bool = False) -> Optional[Dict[str, Any]]:
    """
    Load the knowledge graph index (minimal, ~4KB).

    Use this for quick node type/name lookups.

    Args:
        force_reload: Force reload from disk, bypassing cache

    Returns:
        Index data or None if index file doesn't exist
    """
    if not KG_INDEX_PATH.exists():
        return None

    if force_reload or _should_reload("index", KG_INDEX_PATH):
        with open(KG_INDEX_PATH, 'r') as f:
            data = json.load(f)

        _cache["index"]["data"] = data
        _cache["index"]["mtime"] = os.path.getmtime(KG_INDEX_PATH)
        _cache["index"]["loaded_at"] = datetime.now().timestamp()

    return _cache["index"]["data"]


def load_kg_summary(force_reload: bool = False) -> Optional[Dict[str, Any]]:
    """
    Load the knowledge graph summary (~12KB).

    Use this for routing decisions and quick context assembly.
    Contains capsule index, pattern index, key nodes, and statistics.

    Args:
        force_reload: Force reload from disk, bypassing cache

    Returns:
        Summary data or None if summary file doesn't exist
    """
    if not KG_SUMMARY_PATH.exists():
        return None

    if force_reload or _should_reload("summary", KG_SUMMARY_PATH):
        with open(KG_SUMMARY_PATH, 'r') as f:
            data = json.load(f)

        _cache["summary"]["data"] = data
        _cache["summary"]["mtime"] = os.path.getmtime(KG_SUMMARY_PATH)
        _cache["summary"]["loaded_at"] = datetime.now().timestamp()

    return _cache["summary"]["data"]


def load_kg(force_reload: bool = False) -> Dict[str, Any]:
    """
    Load the full knowledge graph (~80KB).

    Use this only when you need complete graph details,
    all edges, or specific node data not in the summary.

    Args:
        force_reload: Force reload from disk, bypassing cache

    Returns:
        Full knowledge graph data
    """
    if force_reload or _should_reload("full", KG_PATH):
        with open(KG_PATH, 'r') as f:
            data = json.load(f)

        _cache["full"]["data"] = data
        _cache["full"]["mtime"] = os.path.getmtime(KG_PATH)
        _cache["full"]["loaded_at"] = datetime.now().timestamp()

    return _cache["full"]["data"]


def get_node_by_id(node_id: str, use_summary: bool = True) -> Optional[Dict[str, Any]]:
    """
    Get a specific node by ID.

    Args:
        node_id: The node ID to retrieve
        use_summary: Try summary first before loading full graph

    Returns:
        Node data or None if not found
    """
    if use_summary:
        # Try index first (smallest)
        index = load_kg_index()
        if index and node_id in index.get("nodes", {}):
            return index["nodes"][node_id]

        # Try summary next
        summary = load_kg_summary()
        if summary:
            # Check key nodes
            if node_id in summary.get("key_nodes", {}):
                return summary["key_nodes"][node_id]

            # Check capsules
            if node_id in summary.get("capsules", {}):
                return summary["capsules"][node_id]

    # Fall back to full graph
    kg = load_kg()
    return kg.get("nodes", {}).get(node_id)


def get_capsules(use_summary: bool = True) -> Dict[str, Any]:
    """
    Get all capsule nodes.

    Args:
        use_summary: Use summary (lightweight) vs full graph

    Returns:
        Dictionary of capsule nodes
    """
    if use_summary:
        summary = load_kg_summary()
        if summary:
            return summary.get("capsules", {})

    # Fall back to full graph
    kg = load_kg()
    return {
        node_id: node
        for node_id, node in kg.get("nodes", {}).items()
        if node.get("type") == "capsule"
    }


def clear_cache():
    """Clear all cached knowledge graph data."""
    for key in _cache:
        _cache[key]["data"] = None
        _cache[key]["mtime"] = None
        _cache[key]["loaded_at"] = None


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    stats = {}

    for cache_key, entry in _cache.items():
        if entry["data"] is None:
            stats[cache_key] = "not cached"
        else:
            age = datetime.now().timestamp() - entry["loaded_at"]
            stats[cache_key] = {
                "cached": True,
                "age_seconds": int(age),
                "age_minutes": round(age / 60, 1),
                "ttl_remaining_seconds": int(_cache_ttl_seconds - age)
            }

    return stats


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        print("Cache Statistics:")
        print(json.dumps(get_cache_stats(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--clear":
        clear_cache()
        print("Cache cleared")
    else:
        print("Knowledge Graph Loader - Testing")
        print("=" * 50)

        # Test index load
        print("\n1. Loading index...")
        index = load_kg_index()
        if index:
            index_size = len(json.dumps(index))
            print(f"   ✓ Index loaded: {index['total_nodes']} nodes, {index_size:,} bytes")
        else:
            print("   ✗ Index not found")

        # Test summary load
        print("\n2. Loading summary...")
        summary = load_kg_summary()
        if summary:
            summary_size = len(json.dumps(summary))
            print(f"   ✓ Summary loaded: {summary['statistics']['total_nodes']} nodes, {summary_size:,} bytes")
            print(f"   ✓ Capsules: {len(summary['capsules'])}")
            print(f"   ✓ Recent decisions: {len(summary['recent_decisions'])}")
        else:
            print("   ✗ Summary not found (run kg_summary_generator.py first)")

        # Test full load
        print("\n3. Loading full graph...")
        kg = load_kg()
        kg_size = len(json.dumps(kg))
        print(f"   ✓ Full graph loaded: {len(kg['nodes'])} nodes, {kg_size:,} bytes")

        # Show comparison
        print(f"\n4. Size Comparison:")
        if index:
            print(f"   Index:   {index_size:>8,} bytes ({index_size / 1024:.1f} KB)")
        if summary:
            print(f"   Summary: {summary_size:>8,} bytes ({summary_size / 1024:.1f} KB)")
        print(f"   Full:    {kg_size:>8,} bytes ({kg_size / 1024:.1f} KB)")

        if summary:
            savings = kg_size - summary_size
            print(f"\n   Summary saves: ~{savings:,} bytes ({savings / 1024:.1f} KB, {savings / kg_size * 100:.1f}%)")

        print("\n5. Cache Statistics:")
        print(json.dumps(get_cache_stats(), indent=2))
