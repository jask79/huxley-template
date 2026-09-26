#!/usr/bin/env python3
"""Skill Curator — Restore tool.

Reverses an archive operation by moving an archived skill back to
`.claude/skills/<name>/`. Refuses if a skill with the same name already
exists in the live directory.

Usage:
    python3 restore.py <archived-name>           # most recent archive of <name>
    python3 restore.py --list                    # list all archived skills
    python3 restore.py --archive-dir PATH NAME   # override archive root
"""

from __future__ import annotations

import argparse
import datetime
import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Tuple

CATALYST_ROOT = Path(
    os.environ.get(
        "CATALYST_ROOT", str(Path(__file__).resolve().parent.parent.parent)
    )
)
SKILLS_DIR = CATALYST_ROOT / ".claude" / "skills"
ARCHIVE_DIR = SKILLS_DIR / ".archive"
RESTORE_LOG = SKILLS_DIR / ".curator" / "restore.log"


def find_archive_candidates(archive_dir: Path, skill_name: str) -> List[Path]:
    """Return all archived dirs matching `skill_name`, newest first.

    Archive layout: `.archive/<YYYY-MM-DD-HHMM>/<skill-name>/`. We walk
    every dated subdirectory and look for the skill name.
    """
    if not archive_dir.exists():
        return []
    candidates: List[Tuple[Path, float]] = []
    for date_dir in archive_dir.iterdir():
        if not date_dir.is_dir():
            continue
        for entry in date_dir.iterdir():
            if not entry.is_dir():
                continue
            # Match exact name OR `<name>-N` collision form
            if entry.name == skill_name or entry.name.startswith(f"{skill_name}-"):
                try:
                    candidates.append((entry, entry.stat().st_mtime))
                except OSError:
                    continue
    candidates.sort(key=lambda t: -t[1])
    return [p for p, _ in candidates]


def list_archives(archive_dir: Path) -> List[Tuple[str, Path]]:
    """List all archived skills as (skill_name, archived_path)."""
    if not archive_dir.exists():
        return []
    out: List[Tuple[str, Path]] = []
    for date_dir in sorted(archive_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for entry in sorted(date_dir.iterdir()):
            if not entry.is_dir():
                continue
            out.append((entry.name, entry))
    return out


def log_restore(skill_name: str, src: Path, dest: Path) -> None:
    """Append a restore line to the log. Best-effort."""
    try:
        RESTORE_LOG.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        line = f"{ts} | {skill_name} | {src} -> {dest}\n"
        with open(RESTORE_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def restore(skill_name: str, archive_dir: Path, skills_dir: Path) -> Tuple[bool, str]:
    """Restore the most recent archive of `skill_name` to `<skills_dir>/<skill_name>/`."""
    candidates = find_archive_candidates(archive_dir, skill_name)
    if not candidates:
        return False, f"no archived skill matching '{skill_name}' found in {archive_dir}"

    src = candidates[0]
    dest = skills_dir / skill_name
    if dest.exists():
        return False, (
            f"refusing to restore: {dest} already exists. "
            f"Move/delete the live copy first, then re-run."
        )

    try:
        shutil.move(str(src), str(dest))
    except OSError as e:
        return False, f"move failed: {e}"

    # Remove the archive manifest from inside the restored dir (cleanup)
    manifest = dest / "_archive_manifest.json"
    if manifest.exists():
        try:
            manifest.unlink()
        except OSError:
            pass

    log_restore(skill_name, src, dest)
    return True, f"restored from {src} to {dest}"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Restore an archived skill")
    parser.add_argument("name", nargs="?", help="Skill name to restore (kebab-case)")
    parser.add_argument("--list", action="store_true", help="List archived skills")
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=ARCHIVE_DIR,
        help="Override the archive root",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=SKILLS_DIR,
        help="Override the live skills dir",
    )
    args = parser.parse_args(argv)

    if args.list:
        rows = list_archives(args.archive_dir)
        if not rows:
            print(f"No archives in {args.archive_dir}")
            return 0
        print(f"Archives in {args.archive_dir}:")
        for name, path in rows:
            print(f"  {name}\t{path.parent.name}")
        return 0

    if not args.name:
        parser.error("must provide a skill name (or use --list)")

    ok, msg = restore(args.name, args.archive_dir, args.skills_dir)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
