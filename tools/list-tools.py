#!/usr/bin/env python3
"""List all Huxley tools — compact one-liner view.

Reads from global/config/tool-registry.yaml and displays tools
grouped by category.

Usage: python3 tools/list-tools.py
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
REGISTRY = os.path.join(ROOT, "global", "config", "tool-registry.yaml")


def load_registry():
    """Load tool registry YAML (minimal parser, no PyYAML dependency)."""
    tools = {}
    current_category = None
    current_tool = None

    if not os.path.exists(REGISTRY):
        print(f"Error: registry not found at {REGISTRY}", file=sys.stderr)
        sys.exit(1)

    with open(REGISTRY, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip()
            if not stripped or stripped.lstrip().startswith("#"):
                continue

            # Top-level category (2-space indent, ends with colon)
            if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
                key = stripped.strip().rstrip(":")
                if key != "tools":
                    current_category = key
                    tools[current_category] = {}
                    current_tool = None
                continue

            # Tool entry (4-space indent, ends with colon) — requires a category
            if line.startswith("    ") and not line.startswith("      ") and stripped.endswith(":"):
                current_tool = stripped.strip().rstrip(":")
                if current_category:
                    tools[current_category][current_tool] = {}
                else:
                    print(f"Warning: tool '{current_tool}' before any category, skipping", file=sys.stderr)
                    current_tool = None
                continue

            # Tool property (6-space indent) — partition then rejoin value to handle colons in values
            if line.startswith("      ") and current_category and current_tool:
                parts = stripped.split(":", 1)
                if len(parts) == 2:
                    prop = parts[0].strip()
                    val = parts[1].strip().strip('"').strip("'")
                    if val == "null":
                        val = None
                    tools[current_category][current_tool][prop] = val

    return tools


CATEGORY_ORDER = [
    "media",
    "social-intel",
    "social-ops",
    "productivity",
    "security",
    "dev-tools",
    "system",
]

CATEGORY_LABELS = {
    "media": "Media & Creative",
    "social-intel": "Social Intelligence",
    "social-ops": "Social Operations",
    "productivity": "Productivity",
    "security": "Security",
    "dev-tools": "Dev Tools",
    "system": "System",
}


def main():
    registry = load_registry()

    total = sum(len(v) for v in registry.values())
    print(f"Huxley tools ({total} registered)")
    print()

    for cat in CATEGORY_ORDER:
        if cat not in registry:
            continue
        entries = registry[cat]
        if not entries:
            continue

        label = CATEGORY_LABELS.get(cat, cat)
        print(f"  {label}:")

        for slug, meta in sorted(entries.items()):
            emoji = meta.get("emoji", "")
            name = meta.get("name", slug)
            path = meta.get("path", "")
            skill = meta.get("skill")
            agents = meta.get("agents", "")

            prefix = f"    {emoji}  " if emoji else "    "
            skill_str = f"  /{skill}" if skill else ""
            print(f"{prefix}{name}{skill_str}")
            print(f"       {path}  [{agents}]")

        print()

    # Show any categories not in CATEGORY_ORDER (same full format)
    for cat in registry:
        if cat not in CATEGORY_ORDER and registry[cat]:
            label = CATEGORY_LABELS.get(cat, cat)
            print(f"  {label}:")
            for slug, meta in sorted(registry[cat].items()):
                emoji = meta.get("emoji", "")
                name = meta.get("name", slug)
                path = meta.get("path", "")
                skill = meta.get("skill")
                agents = meta.get("agents", "")

                prefix = f"    {emoji}  " if emoji else "    "
                skill_str = f"  /{skill}" if skill else ""
                print(f"{prefix}{name}{skill_str}")
                print(f"       {path}  [{agents}]")
            print()


if __name__ == "__main__":
    main()
