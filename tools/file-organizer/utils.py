"""Shared utilities for file-organizer: hashing, file info, progress reporting."""

import hashlib
import os
import stat
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Size formatting
# ---------------------------------------------------------------------------

_SIZE_UNITS = ["B", "KB", "MB", "GB", "TB"]


def human_size(nbytes: int) -> str:
    """Return a human-readable file size string."""
    value = float(nbytes)
    for unit in _SIZE_UNITS[:-1]:
        if abs(value) < 1024.0:
            return f"{value:,.1f} {unit}"
        value /= 1024.0
    return f"{value:,.1f} {_SIZE_UNITS[-1]}"


def size_bucket(nbytes: int) -> str:
    """Classify a file into a size bucket label."""
    if nbytes < 1024:
        return "<1 KB"
    elif nbytes < 100 * 1024:
        return "1 KB - 100 KB"
    elif nbytes < 1024 * 1024:
        return "100 KB - 1 MB"
    elif nbytes < 10 * 1024 * 1024:
        return "1 MB - 10 MB"
    elif nbytes < 100 * 1024 * 1024:
        return "10 MB - 100 MB"
    elif nbytes < 1024 * 1024 * 1024:
        return "100 MB - 1 GB"
    else:
        return ">1 GB"


# Ordered for display
SIZE_BUCKET_ORDER = [
    "<1 KB",
    "1 KB - 100 KB",
    "100 KB - 1 MB",
    "1 MB - 10 MB",
    "10 MB - 100 MB",
    "100 MB - 1 GB",
    ">1 GB",
]


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def sha256_file(filepath: str, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file. Returns hex digest string."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# File info collection
# ---------------------------------------------------------------------------

def is_icloud_stub(filepath: str) -> bool:
    """Check if a file is an iCloud stub (.icloud placeholder)."""
    name = os.path.basename(filepath)
    return name.startswith(".") and name.endswith(".icloud")


def is_hidden(filepath: str) -> bool:
    """Check if any component of the path is hidden (starts with dot)."""
    parts = Path(filepath).parts
    # Skip the root (e.g., "/") when checking
    for part in parts:
        if part.startswith(".") and part not in (".", ".."):
            return True
    return False


def collect_file_info(filepath: str, compute_hash: bool = True) -> Optional[dict]:
    """Collect metadata for a single file.

    Returns dict with keys: path, size, extension, modified, hash (or None on error).
    Returns None if the file cannot be read.
    """
    try:
        st = os.stat(filepath, follow_symlinks=True)
        if not stat.S_ISREG(st.st_mode):
            return None

        info = {
            "path": os.path.abspath(filepath),
            "size": st.st_size,
            "extension": Path(filepath).suffix.lower() or "(none)",
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
            "mtime": st.st_mtime,
        }

        if compute_hash and st.st_size > 0:
            info["hash"] = sha256_file(filepath)
        else:
            info["hash"] = ""

        return info
    except (PermissionError, OSError):
        return None


# ---------------------------------------------------------------------------
# Progress reporting (stderr, no tqdm)
# ---------------------------------------------------------------------------

class ProgressReporter:
    """Simple progress reporter that prints to stderr."""

    def __init__(self, total: int = 0, label: str = "Processing"):
        self.total = total
        self.label = label
        self.current = 0
        self.start_time = time.time()
        self._last_print = 0.0

    def update(self, n: int = 1) -> None:
        self.current += n
        now = time.time()
        # Throttle updates to at most every 0.25 seconds
        if now - self._last_print < 0.25 and self.current < self.total:
            return
        self._last_print = now
        self._print()

    def _print(self) -> None:
        elapsed = time.time() - self.start_time
        rate = self.current / elapsed if elapsed > 0 else 0

        if self.total > 0:
            pct = self.current / self.total * 100
            sys.stderr.write(
                f"\r  {self.label}: {self.current:,}/{self.total:,} "
                f"({pct:.0f}%) — {rate:.0f} files/sec"
            )
        else:
            sys.stderr.write(
                f"\r  {self.label}: {self.current:,} — {rate:.0f} files/sec"
            )
        sys.stderr.flush()

    def finish(self) -> None:
        elapsed = time.time() - self.start_time
        sys.stderr.write(
            f"\r  {self.label}: {self.current:,} files in {elapsed:.1f}s"
            + " " * 20
            + "\n"
        )
        sys.stderr.flush()


# ---------------------------------------------------------------------------
# Image detection
# ---------------------------------------------------------------------------

IMAGE_EXTENSIONS = frozenset([
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
    ".webp", ".heic", ".heif", ".avif", ".svg", ".ico", ".raw",
    ".cr2", ".nef", ".arw", ".dng", ".orf", ".rw2",
])


def is_image_file(filepath: str) -> bool:
    """Check if a file has an image extension."""
    return Path(filepath).suffix.lower() in IMAGE_EXTENSIONS
