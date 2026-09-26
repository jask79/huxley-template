#!/usr/bin/env python3
"""List all Huxley capsules — compact one-liner view.

Reads from global/config/capsule-registry.yaml and cross-references
with the capsules/ directory.

Usage: python3 tools/list-capsules.py
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
REGISTRY = os.path.join(ROOT, "global", "config", "capsule-registry.yaml")
REGISTRY_EXAMPLE = os.path.join(ROOT, "global", "config", "capsule-registry.example.yaml")
CAPSULES_DIR = os.path.join(ROOT, "capsules")


# NOTE: Hand-rolled YAML parser — assumes 2-space top-level keys and 4-space props. Use PyYAML if format changes.
def load_registry():
    """Load capsule registry YAML (minimal parser, no PyYAML dependency)."""
    capsules = {}
    current = None

    registry_path = REGISTRY if os.path.exists(REGISTRY) else REGISTRY_EXAMPLE
    with open(registry_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip()
            if not stripped or stripped.lstrip().startswith("#"):
                continue

            if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
                key = stripped.strip().rstrip(":")
                if key != "capsules":
                    current = key
                    capsules[current] = {}
                continue

            if line.startswith("    ") and current and ":" in stripped:
                prop, _, val = stripped.partition(":")
                prop = prop.strip()
                val = val.strip().strip('"').strip("'")
                if val == "null":
                    val = None
                capsules[current][prop] = val

    return capsules


STATUS_ORDER = {"active": 0, "planning": 1, "dormant": 2, "production": 0}


def is_revenue(meta):
    """True if the capsule is flagged as actively generating revenue.

    Contract: only the literal value ``true`` (case-insensitive, whitespace-trimmed)
    is recognized, matching what the hand-rolled YAML parser produces. Other YAML
    truthy forms like ``yes`` or ``1`` are intentionally NOT accepted.
    """
    return str(meta.get("revenue", "")).strip().lower() == "true"


def scan_capsules_dir():
    """Return set of capsule slugs (subdirectory names) actually on disk."""
    if not os.path.isdir(CAPSULES_DIR):
        return set()
    return {
        name for name in os.listdir(CAPSULES_DIR)
        if os.path.isdir(os.path.join(CAPSULES_DIR, name))
        and not name.startswith(".") and not name.startswith("_")
    }


def main():
    registry = load_registry()
    on_disk = scan_capsules_dir()
    registered = set(registry.keys())

    print(f"Huxley capsules ({CAPSULES_DIR})")

    # Revenue-generating capsules pin to the top; then status group (active → planning → dormant), then alphabetical.
    # Note: STATUS_ORDER treats "production" as an alias for "active" (both rank 0), so it sorts alongside active capsules.
    entries = sorted(
        registry.items(),
        key=lambda x: (
            0 if is_revenue(x[1]) else 1,
            STATUS_ORDER.get(x[1].get("status", "active"), 9),
            x[0],
        ),
    )

    def group_of(meta):
        return "revenue" if is_revenue(meta) else meta.get("status", "active")

    current_group = None
    for slug, meta in entries:
        status = meta.get("status", "active")
        group = group_of(meta)

        # Print group separator (and a header for the revenue group) on group change
        if group != current_group:
            if current_group is not None:
                print()
            current_group = group
            if group == "revenue":
                print("  💵 Generating revenue")

        emoji = meta.get("emoji", " ")
        name = meta.get("name", slug)
        shortcut = meta.get("shortcut")

        shortcut_str = f" ({shortcut})" if shortcut else ""
        # Revenue capsules with status "active" intentionally print with no status suffix;
        # the "💵 Generating revenue" group header (above) is the intended signal that they
        # were specially sorted. This is by design — not a missing per-line [revenue] suffix.
        suffix = "" if status == "active" else f" [{status}]"

        # Mark registered capsules that no longer exist on disk
        missing_marker = "  ⚠️  [missing on disk]" if slug not in on_disk else ""

        print(f"  {emoji}  {name}{shortcut_str}{suffix}{missing_marker}")

    # Show capsules on disk that aren't in the registry
    unregistered = sorted(on_disk - registered)
    if unregistered:
        print()
        print(f"  ⚠️  Unregistered ({len(unregistered)} on disk, not in registry):")
        for slug in unregistered:
            print(f"     • {slug}")
        print()
        print("  Fix: add entries to global/config/capsule-registry.yaml")


if __name__ == "__main__":
    main()
