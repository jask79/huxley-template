"""Phase 0 — Inventory scan: recursively scan directories, collect metadata, store in DB."""

import json
import os
import sys
import uuid
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

from database import (
    create_scan,
    file_unchanged,
    finish_scan,
    get_connection,
    get_duplicate_count,
    get_extension_stats,
    get_total_stats,
    upsert_file,
)
from utils import (
    SIZE_BUCKET_ORDER,
    ProgressReporter,
    collect_file_info,
    human_size,
    is_hidden,
    is_icloud_stub,
    size_bucket,
)


def scan_directories(
    directories: List[str],
    include_hidden: bool = False,
    json_output: bool = False,
    db_path: Optional[str] = None,
    max_size_mb: Optional[int] = None,
    exclude_dirs: Optional[List[str]] = None,
) -> dict:
    """Scan one or more directories, store results in the database, and return a report.

    Args:
        directories: List of directory paths to scan.
        include_hidden: If True, include hidden directories/files.
        json_output: If True, return machine-readable dict (no printing).
        db_path: Override database path (for testing).

    Returns:
        Report dictionary with scan statistics.
    """
    # Validate directories
    resolved_dirs = []
    for d in directories:
        expanded = os.path.expanduser(d)
        if not os.path.isdir(expanded):
            print(f"Warning: '{d}' is not a directory, skipping.", file=sys.stderr)
            continue
        resolved_dirs.append(os.path.abspath(expanded))

    if not resolved_dirs:
        print("Error: No valid directories to scan.", file=sys.stderr)
        return {"error": "No valid directories"}

    conn = get_connection(db_path) if db_path else get_connection()
    scan_id = str(uuid.uuid4())[:12]
    create_scan(conn, scan_id, resolved_dirs)

    if not json_output:
        print(f"\nScan ID: {scan_id}")
        print(f"Directories: {', '.join(resolved_dirs)}")
        print()

    # Phase 1: Discover all file paths
    if not json_output:
        sys.stderr.write("  Discovering files...\n")

    all_paths = []
    icloud_stubs = 0
    skipped_hidden = 0
    skipped_too_large = 0
    permission_errors = []
    max_size_bytes = max_size_mb * 1024 * 1024 if max_size_mb else None
    exclude_set = set(exclude_dirs) if exclude_dirs else set()

    for root_dir in resolved_dirs:
        resolved_root = os.path.realpath(root_dir)
        for dirpath, dirnames, filenames in os.walk(root_dir, followlinks=False):
            # Filter hidden directories in-place to prevent descending
            if not include_hidden:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]

            # Skip excluded directory names
            if exclude_set:
                dirnames[:] = [d for d in dirnames if d not in exclude_set]

            # Skip symlinked directories to avoid traversal outside intended scope
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]

            for fname in filenames:
                filepath = os.path.join(dirpath, fname)

                # Skip symlinked files (they'd appear as duplicates of their targets)
                if os.path.islink(filepath):
                    continue

                # Skip hidden files
                if not include_hidden and fname.startswith("."):
                    # But still count iCloud stubs
                    if is_icloud_stub(filepath):
                        icloud_stubs += 1
                    else:
                        skipped_hidden += 1
                    continue

                # Count iCloud stubs even when including hidden
                if is_icloud_stub(filepath):
                    icloud_stubs += 1
                    continue

                # Skip files exceeding max size
                if max_size_bytes:
                    try:
                        if os.path.getsize(filepath) > max_size_bytes:
                            skipped_too_large += 1
                            continue
                    except OSError:
                        pass

                all_paths.append(filepath)

    total_discovered = len(all_paths)
    if not json_output:
        sys.stderr.write(f"  Found {total_discovered:,} files to process\n")
        if icloud_stubs:
            sys.stderr.write(f"  Skipped {icloud_stubs:,} iCloud stub files\n")
        if skipped_too_large:
            sys.stderr.write(f"  Skipped {skipped_too_large:,} files exceeding {max_size_mb}MB limit\n")
        sys.stderr.write("\n")

    # Phase 2: Process each file — collect info and hash
    progress = ProgressReporter(total=total_discovered, label="Scanning")
    processed = 0
    skipped_incremental = 0
    errors = 0
    total_size = 0
    extension_counts: dict = defaultdict(lambda: {"count": 0, "size": 0})
    size_buckets: dict = defaultdict(int)

    batch_counter = 0
    for filepath in all_paths:
        try:
            # Incremental: check if file is unchanged
            st = os.stat(filepath, follow_symlinks=True)
            if file_unchanged(conn, os.path.abspath(filepath), st.st_mtime, st.st_size):
                skipped_incremental += 1
                progress.update()
                continue

            info = collect_file_info(filepath, compute_hash=True)
            if info is None:
                errors += 1
                progress.update()
                continue

            upsert_file(conn, info, scan_id)
            processed += 1
            total_size += info["size"]
            extension_counts[info["extension"]]["count"] += 1
            extension_counts[info["extension"]]["size"] += info["size"]
            size_buckets[size_bucket(info["size"])] += 1

            # Commit every 50 files so interrupts don't lose everything
            batch_counter += 1
            if batch_counter >= 50:
                conn.commit()
                batch_counter = 0

        except PermissionError:
            permission_errors.append(filepath)
            errors += 1
        except Exception as e:
            if not json_output:
                sys.stderr.write(f"\n  Error processing {filepath}: {e}\n")
            errors += 1

        progress.update()

    conn.commit()
    progress.finish()

    # Gather final stats from DB (includes previously scanned files)
    db_total_files, db_total_size = get_total_stats(conn)
    db_ext_stats = get_extension_stats(conn)
    duplicate_count = get_duplicate_count(conn)

    # Compute size buckets from DB (in SQL to avoid loading all rows)
    db_size_buckets = defaultdict(int)
    bucket_rows = conn.execute("""
        SELECT
            CASE
                WHEN size < 1024 THEN '<1 KB'
                WHEN size < 102400 THEN '1 KB - 100 KB'
                WHEN size < 1048576 THEN '100 KB - 1 MB'
                WHEN size < 10485760 THEN '1 MB - 10 MB'
                WHEN size < 104857600 THEN '10 MB - 100 MB'
                WHEN size < 1073741824 THEN '100 MB - 1 GB'
                ELSE '>1 GB'
            END AS bucket,
            COUNT(*) AS cnt
        FROM files
        GROUP BY bucket
    """).fetchall()
    for row in bucket_rows:
        db_size_buckets[row["bucket"]] = row["cnt"]

    # Estimate AI processing time (6-9 sec/file for images, 2 sec for others)
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
                  ".webp", ".heic", ".heif", ".avif"}
    image_count = sum(1 for r in conn.execute(
        "SELECT extension FROM files WHERE extension IN ({})".format(
            ",".join("?" for _ in image_exts)
        ),
        list(image_exts),
    ))
    other_count = db_total_files - image_count
    estimated_seconds = (image_count * 7.5) + (other_count * 2)  # avg 7.5s for images
    est_hours = estimated_seconds / 3600

    finish_scan(conn, scan_id, db_total_files, db_total_size)
    conn.close()

    # Build report
    report = {
        "scan_id": scan_id,
        "directories": resolved_dirs,
        "total_files": db_total_files,
        "total_size": db_total_size,
        "total_size_human": human_size(db_total_size),
        "files_processed_this_scan": processed,
        "files_skipped_incremental": skipped_incremental,
        "icloud_stubs_skipped": icloud_stubs,
        "hidden_skipped": skipped_hidden,
        "errors": errors,
        "duplicate_files": duplicate_count,
        "extensions": [
            {"ext": ext, "count": cnt, "size": total, "size_human": human_size(total)}
            for ext, cnt, total in db_ext_stats
        ],
        "size_buckets": [
            {"bucket": b, "count": db_size_buckets.get(b, 0)}
            for b in SIZE_BUCKET_ORDER
        ],
        "estimated_ai_processing": {
            "image_files": image_count,
            "other_files": other_count,
            "estimated_seconds": int(estimated_seconds),
            "estimated_hours": round(est_hours, 1),
        },
    }

    if not json_output:
        _print_report(report)
    else:
        print(json.dumps(report, indent=2))

    return report


def _print_report(report: dict) -> None:
    """Print a human-readable scan report."""
    print("\n" + "=" * 60)
    print("  SCAN REPORT")
    print("=" * 60)
    print(f"  Scan ID:       {report['scan_id']}")
    print(f"  Total files:   {report['total_files']:,}")
    print(f"  Total size:    {report['total_size_human']}")
    print(f"  Duplicates:    {report['duplicate_files']:,} files (exact hash)")
    print()

    if report["files_skipped_incremental"]:
        print(f"  Incremental:   {report['files_skipped_incremental']:,} files unchanged, skipped")
    if report["icloud_stubs_skipped"]:
        print(f"  iCloud stubs:  {report['icloud_stubs_skipped']:,} skipped")
    if report["errors"]:
        print(f"  Errors:        {report['errors']:,} files could not be read")
    print()

    # Extension breakdown (top 20)
    exts = report["extensions"]
    if exts:
        print("  File Types (top 20):")
        print("  " + "-" * 50)
        for item in exts[:20]:
            print(f"    {item['ext']:>12s}  {item['count']:>7,} files  {item['size_human']:>10s}")
        if len(exts) > 20:
            print(f"    {'...':>12s}  {len(exts) - 20:>7,} more types")
        print()

    # Size buckets
    buckets = report["size_buckets"]
    if buckets:
        print("  Size Distribution:")
        print("  " + "-" * 50)
        for item in buckets:
            if item["count"] > 0:
                bar = "#" * min(item["count"], 40)
                print(f"    {item['bucket']:>15s}  {item['count']:>7,}  {bar}")
        print()

    # AI estimate
    ai = report["estimated_ai_processing"]
    print("  Estimated AI Processing Time:")
    print(f"    Images:  {ai['image_files']:,} files (~7.5 sec each)")
    print(f"    Other:   {ai['other_files']:,} files (~2 sec each)")
    print(f"    Total:   ~{ai['estimated_hours']} hours")
    print()
    print("=" * 60)
