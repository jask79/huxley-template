#!/usr/bin/env python3
"""Huxley File Organizer — intelligent file organization with local AI.

Usage:
  organize.py scan <dirs>...       Inventory scan (Phase 0)
  organize.py dedupe [<dirs>...]   Duplicate detection (Phase 1)
  organize.py categorize           AI categorization (Phase 2)
  organize.py tag                  Finder tagging (Phase 3)
  organize.py full <dirs>...       Full pipeline (scan + dedupe + ...)
  organize.py undo                 Reverse last batch of operations
  organize.py stats                Show database statistics
"""

import argparse
import json
import os
import sys

# Add this directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner import scan_directories
from deduper import find_duplicates
from categorizer import categorize
from tagger import tag
from project_tagger import reclassify


def cmd_scan(args):
    """Run inventory scan."""
    scan_directories(
        directories=args.directories,
        include_hidden=args.include_hidden,
        json_output=args.json,
        max_size_mb=args.max_size,
        exclude_dirs=args.exclude_dir if args.exclude_dir else None,
    )


def cmd_dedupe(args):
    """Run duplicate detection."""
    find_duplicates(
        mode=args.mode,
        threshold=args.threshold,
        dry_run=not args.apply,
        json_output=args.json,
    )


def cmd_categorize(args):
    """Run AI categorization (OpenAI GPT-5 or local Ollama)."""
    categorize(
        directories=getattr(args, 'directories', None),
        dry_run=not args.apply,
        json_output=args.json,
        limit=args.limit,
        category_filter=args.filter,
        backend=getattr(args, 'backend', None),
    )


def cmd_tag(args):
    """Write Finder tags based on AI categories."""
    tag(
        directories=getattr(args, 'directories', None),
        dry_run=not args.apply,
        json_output=args.json,
        smart_folders=args.smart_folders,
    )


def cmd_full(args):
    """Run full pipeline: scan -> dedupe -> (future: categorize -> tag)."""
    print("=" * 60)
    print("  FULL PIPELINE")
    print("=" * 60)
    print()

    # Phase 0: Scan
    print("Phase 0: Inventory Scan")
    print("-" * 40)
    scan_directories(
        directories=args.directories,
        include_hidden=args.include_hidden,
        json_output=False,
        max_size_mb=args.max_size,
        exclude_dirs=args.exclude_dir if args.exclude_dir else None,
    )

    # Phase 1: Dedupe
    print("\nPhase 1: Duplicate Detection")
    print("-" * 40)
    find_duplicates(
        mode=args.mode,
        threshold=args.threshold,
        dry_run=not args.apply,
        json_output=False,
    )

    # Phase 2: Categorize
    print("\nPhase 2: AI Categorization")
    print("-" * 40)
    categorize(
        dry_run=not args.apply,
        json_output=False,
        backend=getattr(args, 'backend', None),
    )

    # Phase 3: Tag
    print("\nPhase 3: Finder Tagging")
    print("-" * 40)
    tag(
        dry_run=not args.apply,
        json_output=False,
    )


def cmd_reclassify(args):
    """Reclassify files using custom project taxonomy."""
    taxonomy_path = args.taxonomy
    if not os.path.exists(taxonomy_path):
        # Default to taxonomy.yaml in same directory as this script
        default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxonomy.yaml")
        if os.path.exists(default_path):
            taxonomy_path = default_path
        else:
            print(f"Error: Taxonomy file not found: {taxonomy_path}", file=sys.stderr)
            sys.exit(1)

    backend = getattr(args, 'backend', None) or os.environ.get("FILE_ORGANIZER_BACKEND", "openai")
    reclassify(
        taxonomy_path=taxonomy_path,
        dry_run=not args.apply,
        json_output=args.json,
        limit=args.limit,
        use_ai=not args.no_ai,
        backend=backend,
        directory=getattr(args, 'directory', None),
        categories=getattr(args, 'categories', None),
    )


def cmd_undo(args):
    """Reverse operations from the undo log."""
    from database import DEFAULT_UNDO_PATH
    import shutil

    if not os.path.exists(DEFAULT_UNDO_PATH):
        print("No undo log found. Nothing to undo.")
        return

    entries = []
    with open(DEFAULT_UNDO_PATH, 'r') as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"  Warning: skipping malformed undo entry at line {lineno}", file=sys.stderr)

    if not entries:
        print("Undo log is empty.")
        return

    # Reverse in order (newest first)
    entries.reverse()

    restored = 0
    errors = 0
    for entry in entries:
        if entry.get('action') == 'stage_duplicate':
            src = entry.get('staged_path', '')
            dst = entry.get('original_path', '')
            if not src or not dst:
                continue
            if not os.path.exists(src):
                if not args.dry_run:
                    print(f"  Staged file not found: {src}", file=sys.stderr)
                    errors += 1
                continue
            if args.dry_run:
                print(f"  Would restore: {dst}")
                restored += 1
            else:
                try:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.move(src, dst)
                    restored += 1
                except Exception as e:
                    print(f"  Error restoring {dst}: {e}", file=sys.stderr)
                    errors += 1

    # Clear undo log after applying
    if restored > 0 and not args.dry_run:
        os.remove(DEFAULT_UNDO_PATH)

    print(f"{'Would restore' if args.dry_run else 'Restored'} {restored} files. Errors: {errors}.")
    if args.dry_run:
        print("(Dry run — no files were moved. Run without --dry-run to apply.)")


def cmd_stats(args):
    """Show database statistics."""
    from database import get_connection, get_total_stats, get_extension_stats, get_duplicate_count
    from utils import human_size

    conn = get_connection()
    total_files, total_size = get_total_stats(conn)
    dup_count = get_duplicate_count(conn)

    # Status breakdown
    status_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM files GROUP BY status ORDER BY cnt DESC"
    ).fetchall()

    # Category breakdown
    cat_rows = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM files WHERE category <> '' GROUP BY category ORDER BY cnt DESC"
    ).fetchall()

    if args.json:
        ext_stats = get_extension_stats(conn)
        print(json.dumps({
            'total_files': total_files,
            'total_size': total_size,
            'total_size_human': human_size(total_size),
            'duplicate_files': dup_count,
            'status': {r['status']: r['cnt'] for r in status_rows},
            'categories': {r['category']: r['cnt'] for r in cat_rows},
            'extensions': [
                {'ext': e, 'count': c, 'size': s, 'size_human': human_size(s)}
                for e, c, s in ext_stats
            ],
        }, indent=2))
    else:
        print(f"\nDatabase Statistics:")
        print(f"  Total files:  {total_files:,}")
        print(f"  Total size:   {human_size(total_size)}")
        print(f"  Duplicates:   {dup_count:,} files")
        print()
        if status_rows:
            print("  Pipeline Status:")
            for r in status_rows:
                print(f"    {r['status']:>15s}: {r['cnt']:>6,}")
            print()
        if cat_rows:
            print("  Categories:")
            for r in cat_rows:
                print(f"    {r['category']:>15s}: {r['cnt']:>6,}")
            print()

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        prog='organize',
        description='Huxley File Organizer — intelligent file organization with local AI',
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # scan
    p_scan = subparsers.add_parser('scan', help='Inventory scan of directories')
    p_scan.add_argument('directories', nargs='+', help='Directories to scan')
    p_scan.add_argument('--include-hidden', action='store_true', help='Include hidden files/dirs')
    p_scan.add_argument('--max-size', type=int, default=None, metavar='MB',
                         help='Skip files larger than N megabytes (speeds up hashing)')
    p_scan.add_argument('--exclude-dir', action='append', default=[], metavar='NAME',
                         help='Skip directories with this name (repeatable, e.g. --exclude-dir .git)')
    p_scan.add_argument('--json', action='store_true', help='Machine-readable JSON output')
    p_scan.set_defaults(func=cmd_scan)

    # dedupe
    p_dedupe = subparsers.add_parser('dedupe', help='Find and stage duplicate files')
    p_dedupe.add_argument('--mode', choices=['exact', 'perceptual', 'both'], default='both',
                          help='Detection mode (default: both)')
    p_dedupe.add_argument('--threshold', type=int, default=10,
                          help='pHash distance threshold (default: 10, lower = stricter)')
    p_dedupe.add_argument('--apply', action='store_true',
                          help='Actually move duplicates to staging (default: dry-run)')
    p_dedupe.add_argument('--json', action='store_true', help='Machine-readable JSON output')
    p_dedupe.set_defaults(func=cmd_dedupe)

    # categorize
    p_cat = subparsers.add_parser('categorize', help='AI categorization (OpenAI GPT-5 or local Ollama)')
    p_cat.add_argument('directories', nargs='*', help='(unused, reads from DB)')
    p_cat.add_argument('--apply', action='store_true',
                        help='Update database with categories (default: dry-run)')
    p_cat.add_argument('--limit', type=int, default=0,
                        help='Max files to process (0 = all)')
    p_cat.add_argument('--filter', choices=['images', 'pdfs', 'text', 'all'], default='all',
                        help='Only process this file type (default: all)')
    p_cat.add_argument('--backend', choices=['openai', 'ollama'], default=None,
                        help='AI backend: openai (GPT-5, default) or ollama (local LLMs). '
                             'Also settable via FILE_ORGANIZER_BACKEND env var.')
    p_cat.add_argument('--json', action='store_true', help='Machine-readable JSON output')
    p_cat.set_defaults(func=cmd_categorize)

    # tag
    p_tag = subparsers.add_parser('tag', help='Write Finder tags from AI categories')
    p_tag.add_argument('directories', nargs='*', help='(unused, reads from DB)')
    p_tag.add_argument('--apply', action='store_true',
                        help='Write Finder tags (default: dry-run)')
    p_tag.add_argument('--smart-folders', action='store_true',
                        help='Also generate Smart Folders in ~/Library/Saved Searches')
    p_tag.add_argument('--json', action='store_true', help='Machine-readable JSON output')
    p_tag.set_defaults(func=cmd_tag)

    # full
    p_full = subparsers.add_parser('full', help='Run full pipeline (scan + dedupe + ...)')
    p_full.add_argument('directories', nargs='+', help='Directories to process')
    p_full.add_argument('--include-hidden', action='store_true')
    p_full.add_argument('--max-size', type=int, default=None, metavar='MB',
                         help='Skip files larger than N megabytes')
    p_full.add_argument('--exclude-dir', action='append', default=[], metavar='NAME',
                         help='Skip directories with this name (repeatable)')
    p_full.add_argument('--mode', choices=['exact', 'perceptual', 'both'], default='both')
    p_full.add_argument('--threshold', type=int, default=10)
    p_full.add_argument('--apply', action='store_true',
                        help='Apply changes (move duplicates to staging)')
    p_full.add_argument('--backend', choices=['openai', 'ollama'], default=None,
                        help='AI backend for categorization phase')
    p_full.add_argument('--json', action='store_true')
    p_full.set_defaults(func=cmd_full)

    # reclassify
    p_reclass = subparsers.add_parser('reclassify',
                                       help='Reclassify files using custom project taxonomy')
    p_reclass.add_argument('--taxonomy', default='taxonomy.yaml',
                            help='Path to taxonomy YAML (default: taxonomy.yaml in tool dir)')
    p_reclass.add_argument('--apply', action='store_true',
                            help='Update database with new classifications (default: dry-run)')
    p_reclass.add_argument('--limit', type=int, default=0,
                            help='Max files to process (0 = all)')
    p_reclass.add_argument('--directory', '-d',
                            help='Only reclassify files under this directory path')
    p_reclass.add_argument('--categories', '-c', nargs='+',
                            help='Only reclassify files currently in these categories '
                                 '(e.g., --categories Reference Unsorted)')
    p_reclass.add_argument('--no-ai', action='store_true',
                            help='Skip AI vision (faster, path/content/filename only)')
    p_reclass.add_argument('--backend', choices=['openai', 'ollama'],
                            help='AI backend: openai (GPT-5, default) or ollama (local LLMs). '
                                 'Also settable via FILE_ORGANIZER_BACKEND env var.')
    p_reclass.add_argument('--json', action='store_true', help='Machine-readable JSON output')
    p_reclass.set_defaults(func=cmd_reclassify)

    # undo
    p_undo = subparsers.add_parser('undo', help='Reverse staged operations')
    p_undo.add_argument('--dry-run', action='store_true',
                        help='Show what would be undone without doing it')
    p_undo.set_defaults(func=cmd_undo)

    # stats
    p_stats = subparsers.add_parser('stats', help='Show database statistics')
    p_stats.add_argument('--json', action='store_true')
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == '__main__':
    main()
