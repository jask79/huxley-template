"""Phase 1 — Duplicate detection: exact hash and perceptual hash deduplication."""

import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from database import (
    DEFAULT_DB_DIR,
    append_undo_log,
    get_connection,
    get_duplicate_groups_exact,
    record_dedupe_group,
    update_phash,
)
from utils import (
    IMAGE_EXTENSIONS,
    ProgressReporter,
    human_size,
    is_image_file,
)

STAGING_DIR = os.path.join(DEFAULT_DB_DIR, "staging")


def find_duplicates(
    mode: str = "both",
    threshold: int = 10,
    dry_run: bool = True,
    json_output: bool = False,
    db_path: Optional[str] = None,
) -> dict:
    """Find and optionally stage duplicate files.

    Args:
        mode: Detection mode — "exact", "perceptual", or "both".
        threshold: Hamming distance threshold for perceptual hashing (lower = stricter).
        dry_run: If True (default), only report duplicates. If False, move to staging.
        json_output: If True, output machine-readable JSON.
        db_path: Override database path.

    Returns:
        Report dictionary with duplicate groups and actions taken.
    """
    conn = get_connection(db_path) if db_path else get_connection()

    exact_groups: List[List[dict]] = []
    perceptual_groups: List[List[dict]] = []

    # --- Exact duplicates (SHA-256) ---
    if mode in ("exact", "both"):
        if not json_output:
            sys.stderr.write("  Finding exact duplicates (SHA-256)...\n")
        exact_groups = get_duplicate_groups_exact(conn)
        if not json_output:
            sys.stderr.write(f"  Found {len(exact_groups)} exact duplicate groups\n\n")

    # --- Perceptual duplicates (pHash, images only) ---
    if mode in ("perceptual", "both"):
        if not json_output:
            sys.stderr.write("  Finding perceptual duplicates (pHash)...\n")
        perceptual_groups = _find_perceptual_duplicates(conn, threshold, json_output)
        if not json_output:
            sys.stderr.write(f"  Found {len(perceptual_groups)} perceptual duplicate groups\n\n")

    # Merge groups, removing perceptual groups that are subsets of exact groups
    exact_hashes = set()
    for group in exact_groups:
        for f in group:
            exact_hashes.add(f["path"])

    unique_perceptual = []
    for group in perceptual_groups:
        paths = {f["path"] for f in group}
        # Only include if at least one file is NOT already in an exact group
        if not paths.issubset(exact_hashes):
            unique_perceptual.append(group)

    # Decide what to keep vs stage in each group
    exact_actions = [_decide_group_action(g, "exact") for g in exact_groups]
    perceptual_actions = [_decide_group_action(g, "perceptual") for g in unique_perceptual]
    all_actions = exact_actions + perceptual_actions

    # Calculate savings
    total_reclaimable = sum(a["reclaimable_size"] for a in all_actions)
    total_staged_count = sum(len(a["stage"]) for a in all_actions)

    report = {
        "mode": mode,
        "threshold": threshold if mode != "exact" else None,
        "dry_run": dry_run,
        "exact_groups": len(exact_groups),
        "perceptual_groups": len(unique_perceptual),
        "total_groups": len(all_actions),
        "total_duplicate_files": total_staged_count,
        "reclaimable_size": total_reclaimable,
        "reclaimable_size_human": human_size(total_reclaimable),
        "groups": [],
        "staged_files": 0,
        "errors": [],
    }

    # Process each group
    for action in all_actions:
        group_info = {
            "mode": action["mode"],
            "hash": action["hash"],
            "keep": {
                "path": action["keep"]["path"],
                "size": action["keep"]["size"],
                "size_human": human_size(action["keep"]["size"]),
                "modified": action["keep"]["modified"],
            },
            "duplicates": [
                {
                    "path": f["path"],
                    "size": f["size"],
                    "size_human": human_size(f["size"]),
                    "modified": f["modified"],
                }
                for f in action["stage"]
            ],
            "reclaimable_size": action["reclaimable_size"],
            "reclaimable_size_human": human_size(action["reclaimable_size"]),
        }

        if not dry_run:
            # Actually move files to staging
            staged, errors = _stage_files(action, conn)
            group_info["staged"] = staged
            report["staged_files"] += len(staged)
            report["errors"].extend(errors)

            # Record in DB
            record_dedupe_group(
                conn,
                group_hash=action["hash"],
                mode=action["mode"],
                kept_path=action["keep"]["path"],
                staged_paths=[f["path"] for f in action["stage"]],
            )

        report["groups"].append(group_info)

    conn.commit()
    conn.close()

    if not json_output:
        _print_report(report, dry_run)
    else:
        print(json.dumps(report, indent=2))

    return report


class _BKTreeNode:
    """Node in a BK-tree for Hamming distance metric space."""

    __slots__ = ("hash_val", "path", "children")

    def __init__(self, hash_val: int, path: str):
        self.hash_val = hash_val  # pHash as integer
        self.path = path          # File path (key into info_by_path)
        self.children: Dict[int, "_BKTreeNode"] = {}


class _BKTree:
    """BK-tree for near-duplicate detection in Hamming space.

    Build: O(N log N) expected
    Query: O(N^alpha) where alpha < 1 for small thresholds

    This replaces the previous O(N^2) brute-force comparison and removes
    the 20K image cap, comfortably handling 100K+ images.
    """

    def __init__(self):
        self.root: Optional[_BKTreeNode] = None
        self.size: int = 0

    @staticmethod
    def _hamming(a: int, b: int) -> int:
        """Hamming distance between two integers (count of differing bits)."""
        return bin(a ^ b).count("1")

    def insert(self, hash_val: int, path: str) -> None:
        """Insert a hash into the tree. Exact duplicates (distance 0) are skipped."""
        if self.root is None:
            self.root = _BKTreeNode(hash_val, path)
            self.size = 1
            return

        node = self.root
        while True:
            d = self._hamming(hash_val, node.hash_val)
            if d == 0:
                # Exact pHash duplicate — still record it for grouping.
                # We store the first occurrence in the tree; the caller's
                # Union-Find will link them via the query pass.
                return
            if d in node.children:
                node = node.children[d]
            else:
                node.children[d] = _BKTreeNode(hash_val, path)
                self.size += 1
                return

    def query(self, hash_val: int, threshold: int) -> List[Tuple[str, int]]:
        """Find all entries within *threshold* Hamming distance.

        Returns list of (path, distance) tuples.
        """
        if self.root is None:
            return []

        results: List[Tuple[str, int]] = []
        stack = [self.root]

        while stack:
            node = stack.pop()
            d = self._hamming(hash_val, node.hash_val)
            if d <= threshold:
                results.append((node.path, d))
            # Triangle inequality pruning: only visit children whose
            # edge distance is in [d - threshold, d + threshold].
            lo = max(0, d - threshold)
            hi = d + threshold
            for child_dist, child_node in node.children.items():
                if lo <= child_dist <= hi:
                    stack.append(child_node)

        return results


# -- Union-Find helpers (module-private) ------------------------------------

def _uf_find(parent: Dict[str, str], x: str) -> str:
    """Find root with path compression."""
    while parent.get(x, x) != x:
        parent[x] = parent.get(parent[x], parent[x])  # path halving
        x = parent[x]
    return x


def _uf_union(parent: Dict[str, str], a: str, b: str) -> None:
    """Union two elements by root."""
    ra, rb = _uf_find(parent, a), _uf_find(parent, b)
    if ra != rb:
        parent[ra] = rb


def _find_perceptual_duplicates(
    conn,
    threshold: int,
    json_output: bool,
) -> List[List[dict]]:
    """Find perceptually similar images using pHash + BK-tree.

    Complexity
    ----------
    - Hash computation : O(N) (one pass, cached in DB)
    - BK-tree build    : O(N log N) expected
    - BK-tree queries  : O(N * N^alpha), alpha < 1 for small thresholds
    - Union-Find merge : nearly O(N) with path compression

    Overall this is dramatically faster than the previous O(N^2) pairwise
    approach and can handle 100K+ images without an artificial cap.
    """
    try:
        import imagehash
        from PIL import Image
    except ImportError:
        msg = (
            "imagehash and Pillow are required for perceptual deduplication.\n"
            "Install with: pip install imagehash Pillow"
        )
        if not json_output:
            print(f"  Warning: {msg}", file=sys.stderr)
        return []

    # Get all image files from DB
    placeholders = ",".join("?" for _ in IMAGE_EXTENSIONS)
    rows = conn.execute(
        f"SELECT path, size, modified, hash, phash FROM files WHERE extension IN ({placeholders})",
        list(IMAGE_EXTENSIONS),
    ).fetchall()
    image_files = [dict(r) for r in rows]

    if not image_files:
        return []

    if not json_output:
        sys.stderr.write(f"  Computing perceptual hashes for {len(image_files):,} images...\n")

    progress = ProgressReporter(total=len(image_files), label="pHash")

    # ------------------------------------------------------------------
    # Phase 1: Compute / load pHash for each image
    # ------------------------------------------------------------------
    phash_map: Dict[str, str] = {}  # path -> hex phash
    for finfo in image_files:
        path = finfo["path"]

        # Use cached pHash if available
        if finfo.get("phash") and finfo["phash"]:
            phash_map[path] = finfo["phash"]
            progress.update()
            continue

        try:
            img = Image.open(path)
            h = str(imagehash.phash(img))
            phash_map[path] = h
            update_phash(conn, path, h)
        except Exception:
            pass  # Skip files that can't be opened as images
        progress.update()

    conn.commit()
    progress.finish()

    if len(phash_map) < 2:
        return []

    # Build lookup: path -> file info
    info_by_path = {f["path"]: f for f in image_files}
    paths = list(phash_map.keys())

    # ------------------------------------------------------------------
    # Phase 2: Build BK-tree (O(N log N) expected)
    # ------------------------------------------------------------------
    if not json_output:
        sys.stderr.write(f"  Building BK-tree for {len(paths):,} images...\n")

    tree = _BKTree()

    # Also collect exact-pHash duplicates (distance 0) that the tree
    # insertion silently skips.  Map: hash_int -> first path seen.
    first_seen: Dict[int, str] = {}

    for path in paths:
        hash_int = int(phash_map[path], 16)
        if hash_int in first_seen:
            # Exact pHash duplicate — record relationship directly
            pass  # Union-Find will handle it in query pass
        else:
            first_seen[hash_int] = path
        tree.insert(hash_int, path)

    # ------------------------------------------------------------------
    # Phase 3: Query each image and union neighbors (O(N * N^alpha))
    # ------------------------------------------------------------------
    if not json_output:
        sys.stderr.write("  Clustering similar images...\n")

    parent: Dict[str, str] = {}

    # First, union exact pHash duplicates that were skipped during insert
    hash_to_paths: Dict[int, List[str]] = defaultdict(list)
    for path in paths:
        hash_to_paths[int(phash_map[path], 16)].append(path)

    for _hash_int, grouped_paths in hash_to_paths.items():
        for i in range(1, len(grouped_paths)):
            _uf_union(parent, grouped_paths[0], grouped_paths[i])

    # Now query the tree for each path to find near-duplicates
    for path in paths:
        hash_int = int(phash_map[path], 16)
        neighbors = tree.query(hash_int, threshold)
        for neighbor_path, _dist in neighbors:
            if neighbor_path != path:
                _uf_union(parent, path, neighbor_path)

    # ------------------------------------------------------------------
    # Phase 4: Collect groups from Union-Find
    # ------------------------------------------------------------------
    groups_map: Dict[str, List[dict]] = defaultdict(list)
    for path in paths:
        root = _uf_find(parent, path)
        groups_map[root].append(info_by_path[path])

    groups = [g for g in groups_map.values() if len(g) > 1]

    if not json_output:
        sys.stderr.write(f"  Found {len(groups)} perceptual duplicate groups\n")

    return groups


def _decide_group_action(group: List[dict], mode: str) -> dict:
    """Decide which file to keep (newest) and which to stage."""
    # Sort by modified date descending — keep the newest
    sorted_group = sorted(group, key=lambda f: f["modified"], reverse=True)
    keep = sorted_group[0]
    stage = sorted_group[1:]

    reclaimable = sum(f["size"] for f in stage)

    return {
        "mode": mode,
        "hash": keep.get("hash", "phash-group"),
        "keep": keep,
        "stage": stage,
        "reclaimable_size": reclaimable,
    }


def _stage_files(action: dict, conn) -> Tuple[List[str], List[str]]:
    """Move duplicate files to staging directory. Returns (staged_paths, errors)."""
    staged = []
    errors = []

    for finfo in action["stage"]:
        src = finfo["path"]
        # Preserve relative path structure under staging
        # Use path relative to root (/) so we get a unique staging path
        rel = src.lstrip("/")
        dst = os.path.join(STAGING_DIR, rel)

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            staged.append(dst)

            # Log to undo file
            append_undo_log({
                "action": "stage_duplicate",
                "mode": action["mode"],
                "original_path": src,
                "staged_path": dst,
                "kept_path": action["keep"]["path"],
                "group_hash": action["hash"],
                "timestamp": datetime.now().isoformat(),
            })

            # Update file status in DB
            conn.execute(
                "UPDATE files SET status = 'staged' WHERE path = ?",
                (src,),
            )
        except Exception as e:
            errors.append(f"Failed to stage {src}: {e}")

    return staged, errors


def _print_report(report: dict, dry_run: bool) -> None:
    """Print a human-readable dedupe report."""
    print("\n" + "=" * 60)
    print("  DUPLICATE DETECTION REPORT")
    print("=" * 60)
    print(f"  Mode:          {report['mode']}")
    if report["threshold"] is not None:
        print(f"  Threshold:     {report['threshold']} (pHash distance)")
    print(f"  Dry run:       {'Yes' if dry_run else 'No (files moved to staging)'}")
    print()
    print(f"  Exact groups:      {report['exact_groups']}")
    print(f"  Perceptual groups: {report['perceptual_groups']}")
    print(f"  Total groups:      {report['total_groups']}")
    print(f"  Duplicate files:   {report['total_duplicate_files']:,}")
    print(f"  Reclaimable:       {report['reclaimable_size_human']}")
    print()

    if not dry_run and report["staged_files"]:
        print(f"  Files staged:  {report['staged_files']:,}")
        print(f"  Staging dir:   {STAGING_DIR}")
        print()

    if report["errors"]:
        print(f"  Errors ({len(report['errors'])}):")
        for err in report["errors"][:10]:
            print(f"    - {err}")
        if len(report["errors"]) > 10:
            print(f"    ... and {len(report['errors']) - 10} more")
        print()

    # Show groups (limit to first 20)
    groups = report["groups"]
    if groups:
        shown = min(len(groups), 20)
        print(f"  Duplicate Groups (showing {shown} of {len(groups)}):")
        print("  " + "-" * 50)

        for i, g in enumerate(groups[:shown]):
            mode_tag = f"[{g['mode']}]"
            print(f"\n  Group {i + 1} {mode_tag} — {g['reclaimable_size_human']} reclaimable")
            print(f"    KEEP: {g['keep']['path']}")
            print(f"          {g['keep']['size_human']}  {g['keep']['modified']}")
            for dup in g["duplicates"]:
                print(f"    DUP:  {dup['path']}")
                print(f"          {dup['size_human']}  {dup['modified']}")

        if len(groups) > shown:
            print(f"\n  ... {len(groups) - shown} more groups not shown")

    print()

    if dry_run and report["total_duplicate_files"] > 0:
        print("  To apply changes, run with --apply flag.")
        print(f"  This will move {report['total_duplicate_files']:,} duplicate files to staging.")

    print("=" * 60)
