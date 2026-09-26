#!/usr/bin/env python3
"""
Session Transcript Manager - Token Optimization
Manages Claude Code session transcripts to prevent token bloat

Features:
- Archives sessions older than retention period
- Compresses archives with gzip
- Maintains active sessions for -c flag
- Preserves debugging capability
- Tracks savings and statistics
"""

import os
import gzip
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import argparse


class SessionTranscriptManager:
    def __init__(self,
                 project_dir: str = None,
                 retention_days: int = 7,
                 compression: bool = True):
        """
        Initialize transcript manager.

        Args:
            project_dir: Claude Code project directory (default: ~/.claude/projects/{{CLAUDE_PROJECT_SLUG}})
            retention_days: Keep active transcripts for N days (default: 7)
            compression: Compress archived files (default: True)
        """
        if project_dir is None:
            home = Path.home()
            project_dir = home / ".claude/projects/{{CLAUDE_PROJECT_SLUG}}"

        self.project_dir = Path(project_dir)
        self.retention_days = retention_days
        self.compression = compression

        # Create archive directory
        self.archive_dir = self.project_dir / "archives"
        self.archive_dir.mkdir(exist_ok=True)

        # Stats tracking
        self.stats = {
            'total_files': 0,
            'archived_files': 0,
            'bytes_before': 0,
            'bytes_after': 0,
            'compression_ratio': 0
        }

    def get_transcript_files(self):
        """Get all session transcript .jsonl files."""
        return list(self.project_dir.glob("*.jsonl"))

    def get_old_transcripts(self):
        """Get transcripts older than retention period."""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        old_files = []

        for transcript in self.get_transcript_files():
            # Skip if already in archives directory
            if 'archives' in str(transcript):
                continue

            # Check modification time
            mtime = datetime.fromtimestamp(transcript.stat().st_mtime)
            if mtime < cutoff_time:
                old_files.append(transcript)

        return old_files

    def archive_file(self, file_path: Path):
        """
        Archive a single transcript file.

        Args:
            file_path: Path to transcript file
        """
        original_size = file_path.stat().st_size

        # Create dated archive subdirectory
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        archive_subdir = self.archive_dir / mtime.strftime("%Y-%m")
        archive_subdir.mkdir(exist_ok=True)

        if self.compression:
            # Compress and move
            archive_path = archive_subdir / f"{file_path.name}.gz"
            with open(file_path, 'rb') as f_in:
                with gzip.open(archive_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            compressed_size = archive_path.stat().st_size
            self.stats['bytes_after'] += compressed_size
        else:
            # Just move
            archive_path = archive_subdir / file_path.name
            shutil.move(str(file_path), str(archive_path))
            self.stats['bytes_after'] += original_size

        # Remove original
        if file_path.exists():
            file_path.unlink()

        self.stats['bytes_before'] += original_size
        self.stats['archived_files'] += 1

        return archive_path

    def archive_old_sessions(self, dry_run: bool = False):
        """
        Archive all sessions older than retention period.

        Args:
            dry_run: If True, show what would be archived without doing it
        """
        old_transcripts = self.get_old_transcripts()
        all_transcripts = self.get_transcript_files()

        self.stats['total_files'] = len(all_transcripts)

        if not old_transcripts:
            print(f"✓ No transcripts older than {self.retention_days} days")
            return

        print(f"\nFound {len(old_transcripts)} transcripts to archive (older than {self.retention_days} days)")

        if dry_run:
            print("\n🔍 DRY RUN - Would archive:")
            total_size = 0
            for transcript in old_transcripts:
                size = transcript.stat().st_size
                total_size += size
                mtime = datetime.fromtimestamp(transcript.stat().st_mtime)
                print(f"  - {transcript.name}: {size/1024/1024:.1f}MB (modified {mtime.strftime('%Y-%m-%d')})")
            print(f"\nTotal size to archive: {total_size/1024/1024:.1f}MB")
            return

        # Archive each file
        print("\n📦 Archiving transcripts...")
        for transcript in old_transcripts:
            archive_path = self.archive_file(transcript)
            original_mb = self.stats['bytes_before'] / 1024 / 1024
            if self.compression:
                compressed_mb = (archive_path.stat().st_size) / 1024 / 1024
                print(f"  ✓ {transcript.name}: {original_mb:.1f}MB → {compressed_mb:.1f}MB")
            else:
                print(f"  ✓ {transcript.name}: {original_mb:.1f}MB")

        # Calculate compression ratio
        if self.stats['bytes_before'] > 0:
            self.stats['compression_ratio'] = (
                1 - (self.stats['bytes_after'] / self.stats['bytes_before'])
            ) * 100

        self.print_stats()

    def print_stats(self):
        """Print archival statistics."""
        print("\n" + "="*50)
        print("📊 Archive Statistics")
        print("="*50)
        print(f"Total transcripts: {self.stats['total_files']}")
        print(f"Archived: {self.stats['archived_files']}")
        print(f"Active (retained): {self.stats['total_files'] - self.stats['archived_files']}")
        print(f"\nOriginal size: {self.stats['bytes_before']/1024/1024:.1f}MB")
        if self.compression:
            print(f"Compressed size: {self.stats['bytes_after']/1024/1024:.1f}MB")
            print(f"Compression ratio: {self.stats['compression_ratio']:.1f}%")
        print(f"\nArchive location: {self.archive_dir}")
        print("="*50)

    def get_current_usage(self):
        """Get current transcript disk usage."""
        all_files = self.get_transcript_files()
        total_size = sum(f.stat().st_size for f in all_files if 'archives' not in str(f))

        print("\n" + "="*50)
        print("💾 Current Transcript Usage")
        print("="*50)
        print(f"Total transcripts: {len(all_files)}")
        print(f"Total size: {total_size/1024/1024:.1f}MB ({total_size/1024/1024/1024:.2f}GB)")
        print(f"Average size: {total_size/len(all_files)/1024/1024:.1f}MB" if all_files else "N/A")

        # Size distribution
        sizes = sorted([f.stat().st_size for f in all_files if 'archives' not in str(f)], reverse=True)
        if sizes:
            print(f"\nTop 5 largest:")
            for i, size in enumerate(sizes[:5]):
                print(f"  {i+1}. {size/1024/1024:.1f}MB")

        # Age distribution
        old_7d = len(self.get_old_transcripts())
        print(f"\nOlder than {self.retention_days} days: {old_7d} files")
        print("="*50)


def main():
    parser = argparse.ArgumentParser(
        description="Manage Claude Code session transcripts for token optimization"
    )
    parser.add_argument(
        '--retention-days',
        type=int,
        default=7,
        help='Keep transcripts for N days (default: 7)'
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
        '--project-dir',
        type=str,
        help='Custom project directory path'
    )

    args = parser.parse_args()

    manager = SessionTranscriptManager(
        project_dir=args.project_dir,
        retention_days=args.retention_days,
        compression=not args.no_compression
    )

    if args.stats:
        manager.get_current_usage()
    else:
        manager.get_current_usage()
        manager.archive_old_sessions(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
