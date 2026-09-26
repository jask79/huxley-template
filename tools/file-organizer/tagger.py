"""Phase 3 — Finder tagging: write macOS Finder tags and Spotlight metadata."""

import json
import os
import plistlib
import subprocess
import sys
from collections import defaultdict
from typing import List, Optional

from database import get_connection
from utils import ProgressReporter

# ---------------------------------------------------------------------------
# Finder tag colors (macOS standard)
# ---------------------------------------------------------------------------

# macOS Finder supports 7 color tags (1-7) plus custom text tags
FINDER_COLOR_TAGS = {
    "Screenshots": 6,   # Purple
    "Photos": 4,        # Blue
    "Documents": 7,     # Gray
    "Design": 3,        # Yellow
    "Development": 2,   # Green
    "Finance": 1,       # Red
    "Downloads": 0,     # None (text tag only)
    "Media": 5,         # Orange
    "Reference": 4,     # Blue
    "Unsorted": 0,      # None
}

# Category → Finder color name (for display)
FINDER_COLOR_NAMES = {
    0: "None", 1: "Red", 2: "Green", 3: "Yellow",
    4: "Blue", 5: "Orange", 6: "Purple", 7: "Gray",
}


# ---------------------------------------------------------------------------
# macOS xattr operations
# ---------------------------------------------------------------------------

def _get_finder_tags(filepath: str) -> List[str]:
    """Read existing Finder tags from a file."""
    try:
        result = subprocess.run(
            ["mdls", "-name", "kMDItemUserTags", "-raw", filepath],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or "(null)" in result.stdout:
            return []
        # Parse plist-style output
        # mdls returns something like: (tag1, tag2)
        text = result.stdout.strip()
        if text.startswith("(") and text.endswith(")"):
            inner = text[1:-1].strip()
            if not inner:
                return []
            return [t.strip().strip('"').rstrip(",") for t in inner.split("\n") if t.strip()]
        return []
    except Exception:
        return []


def _sanitize_tag(tag: str) -> str:
    """Remove control characters from a tag name to prevent plist corruption."""
    return "".join(c for c in tag if c >= " " and c != "\n").strip()


def _set_finder_tags(filepath: str, tags: List[str], category_color: int = 0, category_name: str = "") -> bool:
    """Set Finder tags on a file using xattr.

    Tags are stored in com.apple.metadata:_kMDItemUserTags as a plist.
    Each tag is "tagname\\nN" where N is a color code (0=none, 1-7=colors).
    The category tag gets the color; AI sub-tags get color 0 (text-only).
    """
    try:
        tag_entries = []
        for t in tags:
            sanitized = _sanitize_tag(t)
            if not sanitized:
                continue
            # Category tag gets the color, sub-tags are text-only
            if sanitized == category_name:
                tag_entries.append(f"{sanitized}\n{category_color}")
            else:
                tag_entries.append(f"{sanitized}\n0")

        # Encode as binary plist
        plist_data = plistlib.dumps(tag_entries, fmt=plistlib.FMT_BINARY)

        # Write via xattr (space-separated hex for macOS compatibility)
        hex_str = plist_data.hex(" ")
        result = subprocess.run(
            ["xattr", "-wx", "com.apple.metadata:_kMDItemUserTags",
             hex_str, filepath],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _set_spotlight_comment(filepath: str, comment: str) -> bool:
    """Set Spotlight/Finder comment on a file."""
    try:
        plist_data = plistlib.dumps(comment, fmt=plistlib.FMT_BINARY)
        hex_str = plist_data.hex(" ")
        result = subprocess.run(
            ["xattr", "-wx", "com.apple.metadata:kMDItemFinderComment",
             hex_str, filepath],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Smart Folder generation
# ---------------------------------------------------------------------------

def _generate_smart_folder(category: str, output_dir: str) -> Optional[str]:
    """Generate a macOS Smart Folder (.savedSearch) for a category."""
    plist = {
        "CompatibleVersion": 1,
        "RawQuery": f'(kMDItemUserTags == "{category}"cd)',
        "SearchCriteria": {
            "CurrentFolderPath": [os.path.expanduser("~")],
            "FXScopeArrayOfSearchScopes": [
                os.path.expanduser("~"),
            ],
        },
    }

    filename = f"{category} Files.savedSearch"
    filepath = os.path.join(output_dir, filename)

    try:
        with open(filepath, "wb") as f:
            plistlib.dump(plist, f, fmt=plistlib.FMT_XML)
        return filepath
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main tag function
# ---------------------------------------------------------------------------

def tag(
    directories: Optional[List[str]] = None,
    dry_run: bool = True,
    json_output: bool = False,
    db_path: Optional[str] = None,
    smart_folders: bool = False,
) -> dict:
    """Write Finder tags to categorized files.

    Args:
        directories: Not used (reads from database). Kept for CLI compat.
        dry_run: If True (default), only preview. If False, write tags.
        json_output: If True, output machine-readable JSON.
        db_path: Override database path.
        smart_folders: If True, also generate Smart Folders.

    Returns:
        Report dictionary.
    """
    conn = get_connection(db_path) if db_path else get_connection()

    # Get categorized files that haven't been tagged yet
    rows = conn.execute("""
        SELECT path, category, tags, description
        FROM files
        WHERE category <> '' AND status = 'categorized'
        ORDER BY category, path
    """).fetchall()

    total_files = len(rows)

    if total_files == 0:
        if not json_output:
            print("\nNo categorized files pending tagging.")
            print("Run 'categorize --apply' first.\n")
        conn.close()
        return {"total_files": 0, "tagged": 0}

    if not json_output:
        sys.stderr.write(f"\n  Found {total_files:,} categorized files to tag\n")
        sys.stderr.write(f"  Mode: {'dry-run (preview)' if dry_run else 'APPLY (writing Finder tags)'}\n\n")

    # Process files
    progress = ProgressReporter(total=total_files, label="Tagging")
    tagged = 0
    errors = 0
    category_counts = defaultdict(int)
    results = []

    for row in rows:
        filepath = row["path"]
        category = row["category"]
        ai_tags = json.loads(row["tags"]) if row["tags"] else []
        description = row["description"] or ""

        # Check file still exists
        if not os.path.exists(filepath):
            errors += 1
            progress.update()
            continue

        # Merge with existing Finder tags (preserve user's manual tags)
        existing_tags = _get_finder_tags(filepath) if not dry_run else []

        # Build tag list: existing + category + AI sub-tags
        finder_tags = existing_tags + [category] + ai_tags
        # Deduplicate and clean
        seen = set()
        clean_tags = []
        for t in finder_tags:
            t_lower = t.lower().strip()
            if t_lower and t_lower not in seen:
                seen.add(t_lower)
                clean_tags.append(t)

        color = FINDER_COLOR_TAGS.get(category, 0)

        file_result = {
            "path": filepath,
            "category": category,
            "tags": clean_tags,
            "color": FINDER_COLOR_NAMES.get(color, "None"),
            "description": description[:80],
        }

        if not dry_run:
            # Write Finder tags (merges existing + new, category gets color)
            tag_ok = _set_finder_tags(filepath, clean_tags, category_color=color, category_name=category)

            # Write Spotlight comment (AI description)
            comment_ok = True
            if description:
                comment_ok = _set_spotlight_comment(filepath, description)

            if tag_ok:
                tagged += 1
                category_counts[category] += 1
                # Update status in DB
                conn.execute(
                    "UPDATE files SET status = 'tagged' WHERE path = ?",
                    (filepath,),
                )
                if tagged % 50 == 0:
                    conn.commit()
            else:
                errors += 1
                file_result["error"] = "Failed to write tags"
        else:
            tagged += 1
            category_counts[category] += 1

        results.append(file_result)
        progress.update()

    if not dry_run:
        conn.commit()

    progress.finish()

    # Generate Smart Folders if requested
    smart_folder_paths = []
    if smart_folders and not dry_run:
        sf_dir = os.path.expanduser("~/Library/Saved Searches")
        os.makedirs(sf_dir, exist_ok=True)
        for cat in category_counts:
            path = _generate_smart_folder(cat, sf_dir)
            if path:
                smart_folder_paths.append(path)

    conn.close()

    # Build report
    report = {
        "dry_run": dry_run,
        "total_files": total_files,
        "tagged": tagged,
        "errors": errors,
        "categories": [
            {
                "category": cat,
                "count": category_counts.get(cat, 0),
                "color": FINDER_COLOR_NAMES.get(FINDER_COLOR_TAGS.get(cat, 0), "None"),
            }
            for cat in sorted(category_counts.keys())
        ],
        "smart_folders": smart_folder_paths,
        "results": results[:100],
    }

    if not json_output:
        _print_report(report, dry_run)
    else:
        output = {k: v for k, v in report.items() if k != "results"}
        output["sample_results"] = results[:20]
        print(json.dumps(output, indent=2))

    return report


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

def _print_report(report: dict, dry_run: bool) -> None:
    """Print a human-readable tagging report."""
    print("\n" + "=" * 60)
    print("  FINDER TAGGING REPORT")
    print("=" * 60)
    print(f"  Mode:     {'Dry-run (preview)' if dry_run else 'Applied'}")
    print(f"  Tagged:   {report['tagged']:,} files")
    if report["errors"]:
        print(f"  Errors:   {report['errors']:,}")
    print()

    # Category/color breakdown
    cats = report["categories"]
    if cats:
        print("  Tag Colors:")
        print("  " + "-" * 45)
        for item in cats:
            bar = "#" * min(item["count"], 35)
            print(f"    {item['category']:>13s}  ({item['color']:>6s})  {item['count']:>5,}  {bar}")
        print()

    # Smart Folders
    if report["smart_folders"]:
        print(f"  Smart Folders created ({len(report['smart_folders'])}):")
        for sf in report["smart_folders"]:
            print(f"    {sf}")
        print()

    # Sample results
    results = report.get("results", [])
    if results:
        shown = min(len(results), 15)
        print(f"  Sample ({shown} of {report['tagged']:,}):")
        print("  " + "-" * 50)
        for r in results[:shown]:
            fname = os.path.basename(r["path"])
            if len(fname) > 30:
                fname = fname[:27] + "..."
            tags_str = ", ".join(r.get("tags", []))
            print(f"    {fname:<30s} [{r['color']:>6s}] {tags_str}")
        if report["tagged"] > shown:
            print(f"    ... {report['tagged'] - shown:,} more files")
        print()

    if dry_run:
        print("  This was a DRY RUN — no tags were written.")
        print("  Run with --apply to write Finder tags.")

    print("=" * 60)
