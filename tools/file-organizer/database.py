"""SQLite database operations for file-organizer."""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_DB_DIR = os.path.expanduser("~/.cache/catalyst-file-organizer")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "organizer.db")
DEFAULT_UNDO_PATH = os.path.join(DEFAULT_DB_DIR, "undo.jsonl")


def ensure_db_dir() -> None:
    """Create the database directory if it does not exist."""
    os.makedirs(DEFAULT_DB_DIR, exist_ok=True)


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open (or create) the SQLite database and ensure schema exists."""
    ensure_db_dir()
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    _create_schema(conn)
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't already exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            path        TEXT    NOT NULL UNIQUE,
            size        INTEGER NOT NULL,
            extension   TEXT    NOT NULL,
            modified    TEXT    NOT NULL,
            mtime       REAL   NOT NULL,
            hash        TEXT    NOT NULL DEFAULT '',
            phash       TEXT    NOT NULL DEFAULT '',
            scan_id     TEXT    NOT NULL DEFAULT '',
            scanned_at  TEXT    NOT NULL DEFAULT '',
            category    TEXT    NOT NULL DEFAULT '',
            tags        TEXT    NOT NULL DEFAULT '[]',
            description TEXT    NOT NULL DEFAULT '',
            status      TEXT    NOT NULL DEFAULT 'scanned'
        );

        CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash);
        CREATE INDEX IF NOT EXISTS idx_files_phash ON files(phash);
        CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);
        CREATE INDEX IF NOT EXISTS idx_files_scan_id ON files(scan_id);
        CREATE INDEX IF NOT EXISTS idx_files_category ON files(category);

        CREATE TABLE IF NOT EXISTS scans (
            id          TEXT    PRIMARY KEY,
            directories TEXT    NOT NULL,
            started_at  TEXT    NOT NULL,
            finished_at TEXT    NOT NULL DEFAULT '',
            total_files INTEGER NOT NULL DEFAULT 0,
            total_size  INTEGER NOT NULL DEFAULT 0,
            status      TEXT    NOT NULL DEFAULT 'running'
        );

        CREATE TABLE IF NOT EXISTS dedupe_groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_hash  TEXT    NOT NULL,
            mode        TEXT    NOT NULL,
            kept_path   TEXT    NOT NULL,
            staged_paths TEXT   NOT NULL DEFAULT '[]',
            created_at  TEXT    NOT NULL
        );
    """)
    conn.commit()
    _migrate_schema(conn)


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Add columns that may be missing in older databases."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(files)").fetchall()}
    if "description" not in existing:
        conn.execute("ALTER TABLE files ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        conn.commit()


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

def upsert_file(conn: sqlite3.Connection, info: dict, scan_id: str) -> None:
    """Insert or update a file record.

    If the file hash changed (content modified), resets category/tags/description
    so the file gets re-categorized on next run.
    """
    params = {
        **info,
        "scan_id": scan_id,
        "scanned_at": datetime.now().isoformat(),
    }
    conn.execute("""
        INSERT INTO files (path, size, extension, modified, mtime, hash, scan_id, scanned_at)
        VALUES (:path, :size, :extension, :modified, :mtime, :hash, :scan_id, :scanned_at)
        ON CONFLICT(path) DO UPDATE SET
            size = excluded.size,
            extension = excluded.extension,
            modified = excluded.modified,
            mtime = excluded.mtime,
            hash = excluded.hash,
            scan_id = excluded.scan_id,
            scanned_at = excluded.scanned_at,
            -- Reset categorization when file content changed
            category = CASE WHEN files.hash != excluded.hash AND files.hash != '' THEN '' ELSE files.category END,
            tags = CASE WHEN files.hash != excluded.hash AND files.hash != '' THEN '[]' ELSE files.tags END,
            description = CASE WHEN files.hash != excluded.hash AND files.hash != '' THEN '' ELSE files.description END,
            status = CASE WHEN files.hash != excluded.hash AND files.hash != '' THEN 'scanned' ELSE files.status END
    """, params)


def file_unchanged(conn: sqlite3.Connection, path: str, mtime: float, size: int) -> bool:
    """Check if a file record exists with the same mtime and size (skip re-hashing)."""
    row = conn.execute(
        "SELECT 1 FROM files WHERE path = ? AND mtime = ? AND size = ?",
        (path, mtime, size),
    ).fetchone()
    return row is not None


def get_duplicate_groups_exact(conn: sqlite3.Connection) -> List[List[dict]]:
    """Find groups of files with identical SHA-256 hashes."""
    rows = conn.execute("""
        SELECT path, size, extension, modified, hash
        FROM files
        WHERE hash != '' AND hash IS NOT NULL
        AND hash IN (
            SELECT hash FROM files
            WHERE hash != ''
            GROUP BY hash
            HAVING COUNT(*) > 1
        )
        ORDER BY hash, modified DESC
    """).fetchall()

    groups: Dict[str, list] = {}
    for row in rows:
        h = row["hash"]
        groups.setdefault(h, []).append(dict(row))

    return list(groups.values())


def update_phash(conn: sqlite3.Connection, path: str, phash: str) -> None:
    """Set the perceptual hash for a file."""
    conn.execute("UPDATE files SET phash = ? WHERE path = ?", (phash, path))


def get_image_files(conn: sqlite3.Connection) -> List[dict]:
    """Get all image files from the database."""
    from utils import IMAGE_EXTENSIONS

    placeholders = ",".join("?" for _ in IMAGE_EXTENSIONS)
    rows = conn.execute(
        f"SELECT path, size, modified, hash, phash FROM files WHERE extension IN ({placeholders})",
        list(IMAGE_EXTENSIONS),
    ).fetchall()
    return [dict(r) for r in rows]


def record_dedupe_group(
    conn: sqlite3.Connection,
    group_hash: str,
    mode: str,
    kept_path: str,
    staged_paths: List[str],
) -> None:
    """Record a deduplicate group decision."""
    conn.execute("""
        INSERT INTO dedupe_groups (group_hash, mode, kept_path, staged_paths, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (group_hash, mode, kept_path, json.dumps(staged_paths), datetime.now().isoformat()))


# ---------------------------------------------------------------------------
# Scan tracking
# ---------------------------------------------------------------------------

def create_scan(conn: sqlite3.Connection, scan_id: str, directories: List[str]) -> None:
    """Create a scan record."""
    conn.execute(
        "INSERT INTO scans (id, directories, started_at) VALUES (?, ?, ?)",
        (scan_id, json.dumps(directories), datetime.now().isoformat()),
    )
    conn.commit()


def finish_scan(
    conn: sqlite3.Connection,
    scan_id: str,
    total_files: int,
    total_size: int,
) -> None:
    """Mark a scan as completed."""
    conn.execute("""
        UPDATE scans SET finished_at = ?, total_files = ?, total_size = ?, status = 'completed'
        WHERE id = ?
    """, (datetime.now().isoformat(), total_files, total_size, scan_id))
    conn.commit()


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def get_extension_stats(conn: sqlite3.Connection) -> List[Tuple[str, int, int]]:
    """Return (extension, count, total_size) ordered by count descending."""
    rows = conn.execute("""
        SELECT extension, COUNT(*) as cnt, SUM(size) as total
        FROM files
        GROUP BY extension
        ORDER BY cnt DESC
    """).fetchall()
    return [(r["extension"], r["cnt"], r["total"]) for r in rows]


def get_total_stats(conn: sqlite3.Connection) -> Tuple[int, int]:
    """Return (total_files, total_size)."""
    row = conn.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(size), 0) as total FROM files").fetchone()
    return (row["cnt"], row["total"])


def get_duplicate_count(conn: sqlite3.Connection) -> int:
    """Count files that are exact duplicates (have matching hashes with other files)."""
    row = conn.execute("""
        SELECT COUNT(*) as cnt FROM files
        WHERE hash != '' AND hash IN (
            SELECT hash FROM files WHERE hash != '' GROUP BY hash HAVING COUNT(*) > 1
        )
    """).fetchone()
    return row["cnt"]


# ---------------------------------------------------------------------------
# Undo log
# ---------------------------------------------------------------------------

def append_undo_log(entry: dict, undo_path: str = DEFAULT_UNDO_PATH) -> None:
    """Append a JSON-lines entry to the undo log."""
    ensure_db_dir()
    with open(undo_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
