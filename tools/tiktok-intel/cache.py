"""File-based JSON cache with TTL invalidation and LRU eviction.

Cache lives in /tmp/tiktok-intel-cache/ — cleared on reboot.
Keys are SHA-256 hashes of command:JSON(sorted_filters), truncated to 16 chars.

LRU eviction keeps the cache bounded to max_entries. An in-memory index
tracks (filepath, last_access_time, size_bytes) per key hash, avoiding
per-read filesystem scans. The index is persisted to _index.json so it
survives process restarts.
"""

import atexit
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config import CACHE_DIR, DEFAULT_CACHE_TTL
from .exceptions import CacheError

# Default maximum number of cached entries before LRU eviction kicks in.
DEFAULT_MAX_ENTRIES = 1000

# When evicting, remove this fraction of max_entries in one pass (10%).
_EVICT_FRACTION = 0.10


class FileCache:
    """File-based JSON cache with configurable TTL and LRU eviction."""

    def __init__(
        self,
        cache_dir: str = CACHE_DIR,
        ttl: int = DEFAULT_CACHE_TTL,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ):
        self.cache_dir = Path(cache_dir)
        self.ttl = ttl
        self.max_entries = max_entries
        self._ensure_dir()

        # In-memory index: key_hash -> (filepath_str, last_access_time, size_bytes)
        self._index: Dict[str, Tuple[str, float, int]] = {}
        self._lock = threading.Lock()
        self._load_index()

        # Persist index on interpreter shutdown
        atexit.register(self._persist_index)

    # ------------------------------------------------------------------
    # Directory & index management
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise CacheError(f"Cannot create cache directory: {e}") from e

    @property
    def _index_path(self) -> Path:
        """Path to the persisted LRU index file."""
        return self.cache_dir / "_index.json"

    def _load_index(self) -> None:
        """Load persisted index, falling back to a filesystem scan."""
        loaded = False

        # Try persisted index first
        if self._index_path.exists():
            try:
                raw = json.loads(self._index_path.read_text())
                if isinstance(raw, dict):
                    self._index = {
                        k: (v[0], float(v[1]), int(v[2]))
                        for k, v in raw.items()
                        if isinstance(v, (list, tuple)) and len(v) == 3
                    }
                    loaded = True
            except (json.JSONDecodeError, OSError, ValueError):
                pass

        if not loaded:
            self._rebuild_index_from_fs()

        # Reconcile: prune index entries whose files disappeared
        stale_keys = [
            k for k, (p, _, _) in self._index.items()
            if not Path(p).exists()
        ]
        for k in stale_keys:
            del self._index[k]

    def _rebuild_index_from_fs(self) -> None:
        """Rebuild the in-memory index by scanning cache files."""
        self._index.clear()
        if not self.cache_dir.exists():
            return

        for f in self.cache_dir.iterdir():
            if f.suffix != ".json" or f.name == "_index.json":
                continue
            key_hash = f.stem
            try:
                stat = f.stat()
                data = json.loads(f.read_text())
                cached_at = data.get("_cached_at", stat.st_mtime)
                self._index[key_hash] = (str(f), float(cached_at), stat.st_size)
            except (json.JSONDecodeError, OSError):
                # Corrupted entry — count it but use mtime as access time
                try:
                    stat = f.stat()
                    self._index[key_hash] = (str(f), stat.st_mtime, stat.st_size)
                except OSError:
                    pass

    def _persist_index(self) -> None:
        """Write the in-memory index to disk."""
        try:
            with self._lock:
                serializable = {
                    k: [p, t, s] for k, (p, t, s) in self._index.items()
                }
            self._index_path.write_text(
                json.dumps(serializable, separators=(",", ":"))
            )
        except OSError:
            pass  # Best-effort; cache dir may be gone on shutdown

    # ------------------------------------------------------------------
    # Key helpers (unchanged signatures)
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(command: str, filters: dict) -> str:
        """Generate a cache key from command name and filter dict.

        Key = SHA-256 of "command:JSON(sorted_filters)" truncated to 16 chars.
        """
        canonical = json.dumps(filters, sort_keys=True, default=str)
        raw = f"{command}:{canonical}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _key_path(self, key: str) -> Path:
        """Full filesystem path for a cache key."""
        return self.cache_dir / f"{key}.json"

    # ------------------------------------------------------------------
    # Public API (signatures preserved)
    # ------------------------------------------------------------------

    def get(self, command: str, filters: dict) -> Optional[dict]:
        """Retrieve cached data if it exists and hasn't expired.

        Returns the full cached dict (with _cached_at) or None.
        """
        key = self._make_key(command, filters)
        path = self._key_path(key)

        if not path.exists():
            # Clean stale index entry if present
            with self._lock:
                self._index.pop(key, None)
            return None

        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            # Corrupted cache entry — remove it
            self._remove(path)
            with self._lock:
                self._index.pop(key, None)
            return None

        # Check TTL
        cached_at = data.get("_cached_at", 0)
        if time.time() - cached_at > self.ttl:
            self._remove(path)
            with self._lock:
                self._index.pop(key, None)
            return None

        # Update last-access time in the index (LRU tracking)
        now = time.time()
        try:
            size = path.stat().st_size
        except OSError:
            size = self._index.get(key, ("", 0, 0))[2]
        with self._lock:
            self._index[key] = (str(path), now, size)

        return data

    def set(self, command: str, filters: dict, data: dict) -> None:
        """Write data to cache with timestamp."""
        key = self._make_key(command, filters)
        path = self._key_path(key)

        entry = dict(data)
        now = time.time()
        entry["_cached_at"] = now

        try:
            payload = json.dumps(entry, indent=2, default=str)
            path.write_text(payload)
        except OSError as e:
            raise CacheError(f"Cannot write cache entry: {e}") from e

        # Update index
        with self._lock:
            self._index[key] = (str(path), now, len(payload.encode()))

        # Evict if over capacity
        self._maybe_evict()

    def clear(self) -> int:
        """Remove all cache entries. Returns count of files removed."""
        count = 0
        if not self.cache_dir.exists():
            with self._lock:
                self._index.clear()
            return count

        for f in self.cache_dir.iterdir():
            if f.suffix == ".json" and f.name != "_index.json":
                self._remove(f)
                count += 1

        with self._lock:
            self._index.clear()
        # Remove persisted index too
        self._remove(self._index_path)
        return count

    def stats(self) -> dict:
        """Return cache statistics using the in-memory index.

        Much faster than the previous implementation which read and parsed
        every cache file on disk.
        """
        if not self.cache_dir.exists():
            return {
                "cache_dir": str(self.cache_dir),
                "entries": 0,
                "total_bytes": 0,
                "oldest": None,
                "newest": None,
                "expired": 0,
            }

        now = time.time()
        total_bytes = 0
        oldest: Optional[float] = None
        newest: Optional[float] = None
        expired = 0

        for _key_hash, (filepath, last_access, size) in self._index.items():
            total_bytes += size
            if oldest is None or last_access < oldest:
                oldest = last_access
            if newest is None or last_access > newest:
                newest = last_access
            if now - last_access > self.ttl:
                expired += 1

        return {
            "cache_dir": str(self.cache_dir),
            "entries": len(self._index),
            "total_bytes": total_bytes,
            "oldest": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(oldest)) if oldest else None,
            "newest": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(newest)) if newest else None,
            "expired": expired,
            "ttl_seconds": self.ttl,
            "max_entries": self.max_entries,
        }

    # ------------------------------------------------------------------
    # LRU eviction
    # ------------------------------------------------------------------

    def _maybe_evict(self) -> None:
        """Evict oldest-accessed entries if count exceeds max_entries."""
        with self._lock:
            if len(self._index) <= self.max_entries:
                return

            evict_count = max(1, int(self.max_entries * _EVICT_FRACTION))

            # Sort by last_access_time ascending (oldest first)
            by_access = sorted(self._index.items(), key=lambda x: x[1][1])
            to_evict = by_access[:evict_count]

            for key_hash, (filepath, _, _) in to_evict:
                del self._index[key_hash]

        # File I/O outside the lock
        for _key_hash, (filepath, _, _) in to_evict:
            self._remove(Path(filepath))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _remove(path: Path) -> None:
        """Silently remove a file."""
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
