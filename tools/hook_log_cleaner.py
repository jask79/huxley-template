#!/usr/bin/env python3
"""
Hook Log Cleaner - Token Optimization
Manages Claude Code hook debug logs to prevent accumulation

Features:
- Cleans hook logs older than retention period
- Compresses archived logs
- Maintains recent logs for debugging
- Tracks cleanup statistics
"""

import os
import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import argparse


class HookLogCleaner:
    def __init__(self,
                 log_dir: str = None,
                 retention_days: int = 7,
                 compression: bool = True):
        """
        Initialize hook log cleaner.

        Args:
            log_dir: Hook log directory (default: logs/claude-hooks)
            retention_days: Keep logs for N days (default: 7)
            compression: Compress archived files (default: True)
        """
        if log_dir is None:
            log_dir = Path.cwd() / "logs/claude-hooks"

        self.log_dir = Path(log_dir)
        self.retention_days = retention_days
        self.compression = compression

        # Create archive directory
        self.archive_dir = Path.cwd() / "logs/archives/hooks"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        # Stats tracking
        self.stats = {
            'total_sessions': 0,
            'archived_sessions': 0,
            'total_files': 0,
            'archived_files': 0,
            'bytes_before': 0,
            'bytes_after': 0,
            'compression_ratio': 0
        }

    def get_session_dirs(self):
        """Get all session directories in hook logs."""
        if not self.log_dir.exists():
            return []

        return [d for d in self.log_dir.iterdir() if d.is_dir()]

    def get_old_sessions(self):
        """Get session directories older than retention period."""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        old_sessions = []

        for session_dir in self.get_session_dirs():
            # Check modification time of directory
            mtime = datetime.fromtimestamp(session_dir.stat().st_mtime)
            if mtime < cutoff_time:
                old_sessions.append(session_dir)

        return old_sessions

    def archive_session(self, session_dir: Path):
        """
        Archive a session's hook logs.

        Args:
            session_dir: Path to session directory
        """
        # Calculate directory size
        dir_size = sum(f.stat().st_size for f in session_dir.rglob('*') if f.is_file())
        self.stats['bytes_before'] += dir_size

        # Get all files in session
        files = list(session_dir.rglob('*.json'))
        self.stats['total_files'] += len(files)

        # Create dated archive subdirectory
        mtime = datetime.fromtimestamp(session_dir.stat().st_mtime)
        archive_subdir = self.archive_dir / mtime.strftime("%Y-%m")
        archive_subdir.mkdir(exist_ok=True)

        if self.compression:
            # Create tarball of session directory
            archive_path = archive_subdir / f"{session_dir.name}.tar.gz"
            shutil.make_archive(
                str(archive_path).replace('.tar.gz', ''),
                'gztar',
                session_dir
            )

            compressed_size = archive_path.stat().st_size
            self.stats['bytes_after'] += compressed_size
            self.stats['archived_files'] += len(files)
        else:
            # Just move the directory
            archive_path = archive_subdir / session_dir.name
            shutil.move(str(session_dir), str(archive_path))
            self.stats['bytes_after'] += dir_size
            self.stats['archived_files'] += len(files)

        # Remove original directory if compression was used
        if self.compression and session_dir.exists():
            shutil.rmtree(session_dir)

        self.stats['archived_sessions'] += 1

        return archive_path

    def clean_old_logs(self, dry_run: bool = False):
        """
        Clean all hook logs older than retention period.

        Args:
            dry_run: If True, show what would be cleaned without doing it
        """
        old_sessions = self.get_old_sessions()
        all_sessions = self.get_session_dirs()

        self.stats['total_sessions'] = len(all_sessions)

        if not old_sessions:
            print(f"✓ No hook logs older than {self.retention_days} days")
            return

        print(f"\nFound {len(old_sessions)} session logs to archive (older than {self.retention_days} days)")

        if dry_run:
            print("\n🔍 DRY RUN - Would archive:")
            total_size = 0
            for session in old_sessions:
                size = sum(f.stat().st_size for f in session.rglob('*') if f.is_file())
                total_size += size
                mtime = datetime.fromtimestamp(session.stat().st_mtime)
                file_count = len(list(session.rglob('*.json')))
                print(f"  - {session.name}: {size/1024:.1f}KB ({file_count} files, modified {mtime.strftime('%Y-%m-%d')})")
            print(f"\nTotal size to archive: {total_size/1024/1024:.1f}MB")
            return

        # Archive each session
        print("\n📦 Archiving session logs...")
        for session in old_sessions:
            archive_path = self.archive_session(session)
            original_kb = sum(f.stat().st_size for f in session.rglob('*') if f.is_file() if session.exists()) / 1024
            if self.compression:
                compressed_kb = archive_path.stat().st_size / 1024
                print(f"  ✓ {session.name}: {original_kb:.1f}KB → {compressed_kb:.1f}KB")
            else:
                print(f"  ✓ {session.name}: {original_kb:.1f}KB")

        # Calculate compression ratio
        if self.stats['bytes_before'] > 0:
            self.stats['compression_ratio'] = (
                1 - (self.stats['bytes_after'] / self.stats['bytes_before'])
            ) * 100

        self.print_stats()

    def print_stats(self):
        """Print cleanup statistics."""
        print("\n" + "="*50)
        print("📊 Hook Log Cleanup Statistics")
        print("="*50)
        print(f"Total sessions: {self.stats['total_sessions']}")
        print(f"Archived sessions: {self.stats['archived_sessions']}")
        print(f"Active sessions: {self.stats['total_sessions'] - self.stats['archived_sessions']}")
        print(f"\nTotal files archived: {self.stats['archived_files']}")
        print(f"Original size: {self.stats['bytes_before']/1024/1024:.1f}MB")
        if self.compression:
            print(f"Compressed size: {self.stats['bytes_after']/1024/1024:.1f}MB")
            print(f"Compression ratio: {self.stats['compression_ratio']:.1f}%")
        print(f"\nArchive location: {self.archive_dir}")
        print("="*50)

    def get_current_usage(self):
        """Get current hook log disk usage."""
        all_sessions = self.get_session_dirs()
        total_size = sum(
            sum(f.stat().st_size for f in session.rglob('*') if f.is_file())
            for session in all_sessions
        )
        total_files = sum(
            len(list(session.rglob('*.json')))
            for session in all_sessions
        )

        print("\n" + "="*50)
        print("💾 Current Hook Log Usage")
        print("="*50)
        print(f"Total sessions: {len(all_sessions)}")
        print(f"Total files: {total_files}")
        print(f"Total size: {total_size/1024/1024:.1f}MB")

        # Age distribution
        old_sessions = self.get_old_sessions()
        print(f"\nOlder than {self.retention_days} days: {len(old_sessions)} sessions")
        print("="*50)


def main():
    parser = argparse.ArgumentParser(
        description="Clean Claude Code hook debug logs for token optimization"
    )
    parser.add_argument(
        '--retention-days',
        type=int,
        default=7,
        help='Keep logs for N days (default: 7)'
    )
    parser.add_argument(
        '--no-compression',
        action='store_true',
        help='Disable gzip compression of archives'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be archived without doing it'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show current usage statistics only'
    )
    parser.add_argument(
        '--log-dir',
        type=str,
        help='Custom log directory path'
    )

    args = parser.parse_args()

    cleaner = HookLogCleaner(
        log_dir=args.log_dir,
        retention_days=args.retention_days,
        compression=not args.no_compression
    )

    if args.stats:
        cleaner.get_current_usage()
    else:
        cleaner.get_current_usage()
        cleaner.clean_old_logs(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
