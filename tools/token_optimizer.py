#!/usr/bin/env python3
"""
Token Optimizer - Master Cleanup Orchestrator
Runs all token optimization cleanup tasks

Coordinates:
- Session transcript archival
- Hook log cleanup
- Reporting and statistics
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent))

from session_transcript_manager import SessionTranscriptManager
from hook_log_cleaner import HookLogCleaner


class TokenOptimizer:
    def __init__(self, retention_days: int = 7, dry_run: bool = False):
        """
        Initialize token optimizer.

        Args:
            retention_days: Keep active files for N days
            dry_run: Show what would be done without doing it
        """
        self.retention_days = retention_days
        self.dry_run = dry_run

        # Initialize managers
        self.transcript_manager = SessionTranscriptManager(
            retention_days=retention_days,
            compression=True
        )
        self.hook_cleaner = HookLogCleaner(
            retention_days=retention_days,
            compression=True
        )

    def run_full_optimization(self):
        """Run complete token optimization cleanup."""
        print("="*60)
        print("🚀 Token Optimization - Full Cleanup")
        print("="*60)
        print(f"Retention period: {self.retention_days} days")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

        # Phase 1: Session Transcripts
        print("\n" + "─"*60)
        print("📄 Phase 1: Session Transcript Cleanup")
        print("─"*60)
        self.transcript_manager.archive_old_sessions(dry_run=self.dry_run)

        # Phase 2: Hook Logs
        print("\n" + "─"*60)
        print("🪝 Phase 2: Hook Log Cleanup")
        print("─"*60)
        self.hook_cleaner.clean_old_logs(dry_run=self.dry_run)

        # Summary
        self.print_summary()

    def print_summary(self):
        """Print overall summary."""
        print("\n" + "="*60)
        print("📊 Overall Summary")
        print("="*60)

        # Transcript stats
        t_stats = self.transcript_manager.stats
        h_stats = self.hook_cleaner.stats

        total_saved_mb = (t_stats['bytes_before'] + h_stats['bytes_before']) / 1024 / 1024
        total_archived_mb = (t_stats['bytes_after'] + h_stats['bytes_after']) / 1024 / 1024

        print(f"Transcripts archived: {t_stats['archived_files']} files")
        print(f"Hook sessions archived: {h_stats['archived_sessions']} sessions ({h_stats['archived_files']} files)")
        print(f"\nTotal original size: {total_saved_mb:.1f}MB")
        if not self.dry_run:
            print(f"Total compressed size: {total_archived_mb:.1f}MB")
            if total_saved_mb > 0:
                compression_ratio = (1 - (total_archived_mb / total_saved_mb)) * 100
                print(f"Overall compression: {compression_ratio:.1f}%")
                print(f"Space saved: {total_saved_mb - total_archived_mb:.1f}MB")

        print("\n✅ Optimization complete!")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Token Optimizer - Master cleanup orchestrator for Claude Code"
    )
    parser.add_argument(
        '--retention-days',
        type=int,
        default=7,
        help='Keep files for N days (default: 7)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without doing it'
    )
    parser.add_argument(
        '--transcripts-only',
        action='store_true',
        help='Only clean session transcripts'
    )
    parser.add_argument(
        '--hooks-only',
        action='store_true',
        help='Only clean hook logs'
    )

    args = parser.parse_args()

    if args.transcripts_only:
        print("Running transcript cleanup only...")
        manager = SessionTranscriptManager(
            retention_days=args.retention_days,
            compression=True
        )
        manager.get_current_usage()
        manager.archive_old_sessions(dry_run=args.dry_run)
    elif args.hooks_only:
        print("Running hook log cleanup only...")
        cleaner = HookLogCleaner(
            retention_days=args.retention_days,
            compression=True
        )
        cleaner.get_current_usage()
        cleaner.clean_old_logs(dry_run=args.dry_run)
    else:
        # Run full optimization
        optimizer = TokenOptimizer(
            retention_days=args.retention_days,
            dry_run=args.dry_run
        )
        optimizer.run_full_optimization()


if __name__ == '__main__':
    main()
