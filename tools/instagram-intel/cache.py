"""File-based JSON cache with TTL invalidation.

Cache lives in /tmp/instagram-intel-cache/ -- cleared on reboot.
Keys are SHA-256 hashes of command:JSON(sorted_filters), truncated to 16 chars.

Cloned from tiktok-intel/cache.py pattern.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from .config import CACHE_DIR, DEFAULT_CACHE_TTL
from .exceptions import CacheError


class FileCache:
    """File-based JSON cache with configurable TTL."""

    def __init__(self, cache_dir: str = CACHE_DIR, ttl: int = DEFAULT_CACHE_TTL):
        self.cache_dir = Path(cache_dir)
        self.ttl = ttl
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise CacheError(f"Cannot create cache directory: {e}") from e

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

    def get(self, command: str, filters: dict, ttl: Optional[int] = None) -> Optional[dict]:
        """Retrieve cached data if it exists and hasn't expired.

        Args:
            command: Command name (used for cache key generation).
            filters: Filter dict (used for cache key generation).
            ttl: Optional TTL override in seconds. If None, uses instance TTL.

        Returns the full cached dict (with _cached_at) or None.
        """
        key = self._make_key(command, filters)
        path = self._key_path(key)

        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            self._remove(path)
            return None

        # Check TTL (use override if provided)
        effective_ttl = ttl if ttl is not None else self.ttl
        cached_at = data.get("_cached_at", 0)
        if time.time() - cached_at > effective_ttl:
            self._remove(path)
            return None

        return data

    def set(self, command: str, filters: dict, data: dict) -> None:
        """Write data to cache with timestamp."""
        key = self._make_key(command, filters)
        path = self._key_path(key)

        entry = dict(data)
        entry["_cached_at"] = time.time()

        try:
            path.write_text(json.dumps(entry, indent=2, default=str))
        except OSError as e:
            raise CacheError(f"Cannot write cache entry: {e}") from e

    def clear(self) -> int:
        """Remove all cache entries. Returns count of files removed."""
        count = 0
        if not self.cache_dir.exists():
            return count

        for f in self.cache_dir.iterdir():
            if f.suffix == ".json":
                self._remove(f)
                count += 1
        return count

    def stats(self) -> dict:
        """Return cache statistics."""
        if not self.cache_dir.exists():
            return {
                "cache_dir": str(self.cache_dir),
                "entries": 0,
                "total_bytes": 0,
                "oldest": None,
                "newest": None,
                "expired": 0,
            }

        entries = list(self.cache_dir.glob("*.json"))
        total_bytes = sum(f.stat().st_size for f in entries)
        now = time.time()

        oldest = None
        newest = None
        expired = 0

        for f in entries:
            try:
                data = json.loads(f.read_text())
                cached_at = data.get("_cached_at", 0)
                if cached_at:
                    if oldest is None or cached_at < oldest:
                        oldest = cached_at
                    if newest is None or cached_at > newest:
                        newest = cached_at
                    if now - cached_at > self.ttl:
                        expired += 1
            except (json.JSONDecodeError, OSError):
                expired += 1

        return {
            "cache_dir": str(self.cache_dir),
            "entries": len(entries),
            "total_bytes": total_bytes,
            "oldest": (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(oldest))
                if oldest
                else None
            ),
            "newest": (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(newest))
                if newest
                else None
            ),
            "expired": expired,
            "ttl_seconds": self.ttl,
        }

    @staticmethod
    def _remove(path: Path) -> None:
        """Silently remove a file."""
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
