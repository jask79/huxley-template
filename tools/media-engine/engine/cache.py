"""
Prompt Cache for the Media Workflow Engine.

Caches generation results keyed by prompt + config hash to prevent
regenerating identical requests. Cache entries are stored as JSON
manifests in cache/prompt-hash/{hash}.json with metadata pointing
to the actual output files.

Cache key is a SHA-256 hash of: prompt + model + resolution + sorted
config subset (excluding volatile fields like output paths).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


# Default cache directory
ENGINE_ROOT = Path("{{CATALYST_ROOT}}/tools/media-engine")
DEFAULT_CACHE_DIR = ENGINE_ROOT / "cache" / "prompt-hash"

# Fields included in the cache key hash (from config)
CACHE_KEY_FIELDS = [
    "model",
    "media_type",
    "auth",
    "auth_provider",
    "generation",
    "refinement",
    "consistency",
]


class PromptCache:
    """
    Caches generation results keyed by prompt + config hash.

    Prevents regenerating identical requests. Cache is stored as a
    JSON manifest in cache/prompt-hash/{hash}.json containing metadata
    and the path to the actual output file.

    Cache hits skip generation entirely and return the cached path.
    """

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        """
        Args:
            cache_dir: Directory for cache manifests. Defaults to
                       cache/prompt-hash/ under the engine root.
        """
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(
        self,
        prompt: str,
        config: dict[str, Any],
        references: list[str] | None = None,
        source_image: str | None = None,
    ) -> str | None:
        """
        Return cached output path if a matching entry exists, None otherwise.

        A cache hit requires:
          1. The manifest file exists for the computed hash
          2. The output file referenced in the manifest still exists
          3. The manifest is not corrupted

        Args:
            prompt: The generation prompt.
            config: Resolved workflow config dict.
            references: Optional list of reference image paths used.
            source_image: Optional source image path (e.g., for image-to-video).

        Returns:
            Absolute path to the cached output file, or None if no cache hit.
        """
        cache_key = self._compute_key(prompt, config, references, source_image)
        manifest_path = self.cache_dir / f"{cache_key}.json"

        if not manifest_path.exists():
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Corrupted manifest -- treat as cache miss
            return None

        output_path = manifest.get("output_path", "")

        # Verify the output file still exists
        if not output_path or not Path(output_path).exists():
            return None

        return output_path

    def put(
        self,
        prompt: str,
        config: dict[str, Any],
        output_path: str,
        references: list[str] | None = None,
        source_image: str | None = None,
    ) -> None:
        """
        Store a generation result in the cache.

        Creates a JSON manifest keyed by the prompt + config hash,
        containing metadata about the generation and the path to
        the output file.

        Args:
            prompt: The generation prompt.
            config: Resolved workflow config dict.
            output_path: Absolute path to the generated output file.
            references: Optional list of reference image paths used.
            source_image: Optional source image path (e.g., for image-to-video).
        """
        cache_key = self._compute_key(prompt, config, references, source_image)
        manifest_path = self.cache_dir / f"{cache_key}.json"

        manifest = {
            "cache_key": cache_key,
            "prompt": prompt,
            "model": config.get("model", "unknown"),
            "media_type": config.get("media_type", "image"),
            "resolution": config.get("generation", {}).get("resolution", "2K"),
            "output_path": output_path,
            "created_at": time.time(),
            "config_subset": self._extract_key_config(config),
            "references": sorted(references) if references else [],
            "source_image": source_image or "",
        }

        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, default=str)
        except OSError as exc:
            # Cache write failure is non-critical
            print(f"Warning: Could not write cache manifest: {exc}")

    def clear(self, max_age_days: int = 30) -> int:
        """
        Remove cache entries older than max_age_days.

        Scans the cache directory for manifest files and removes those
        whose created_at timestamp is older than the cutoff.

        Args:
            max_age_days: Maximum age in days for cache entries.

        Returns:
            Number of cache entries removed.
        """
        if not self.cache_dir.exists():
            return 0

        cutoff = time.time() - (max_age_days * 86400)
        removed = 0

        for entry in self.cache_dir.iterdir():
            if not entry.is_file() or entry.suffix != ".json":
                continue

            # Skip .gitkeep or other non-manifest files
            if entry.name.startswith("."):
                continue

            try:
                with open(entry, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except (json.JSONDecodeError, OSError):
                # Corrupted manifest -- remove it
                entry.unlink(missing_ok=True)
                removed += 1
                continue

            created_at = manifest.get("created_at", 0)
            if created_at < cutoff:
                entry.unlink(missing_ok=True)
                removed += 1

        return removed

    def stats(self) -> dict[str, Any]:
        """
        Return cache statistics.

        Returns:
            Dict with total_entries, valid_entries (output file exists),
            and total_size_bytes of manifests.
        """
        if not self.cache_dir.exists():
            return {"total_entries": 0, "valid_entries": 0, "total_size_bytes": 0}

        total = 0
        valid = 0
        size = 0

        for entry in self.cache_dir.iterdir():
            if not entry.is_file() or entry.suffix != ".json" or entry.name.startswith("."):
                continue

            total += 1
            size += entry.stat().st_size

            try:
                with open(entry, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                output_path = manifest.get("output_path", "")
                if output_path and Path(output_path).exists():
                    valid += 1
            except (json.JSONDecodeError, OSError):
                pass

        return {
            "total_entries": total,
            "valid_entries": valid,
            "total_size_bytes": size,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compute_key(
        self,
        prompt: str,
        config: dict[str, Any],
        references: list[str] | None = None,
        source_image: str | None = None,
    ) -> str:
        """
        Compute the cache key as a SHA-256 hash of prompt + config subset +
        reference paths + source image path.

        The key includes the prompt text plus a deterministic subset of
        the config (model, resolution, refinement settings, etc.) so
        that different configurations produce different cache keys.
        Reference image paths and source_image are sorted and included
        so that different input images produce different cache keys.

        Returns:
            A 16-character hex string (truncated SHA-256).
        """
        key_data = {
            "prompt": prompt,
            "config": self._extract_key_config(config),
            "references": sorted(references) if references else [],
            "source_image": source_image or "",
        }

        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _extract_key_config(config: dict[str, Any]) -> dict[str, Any]:
        """
        Extract the config subset used for cache key computation.

        Includes only fields that affect generation output, excluding
        volatile fields like output paths, provenance settings, etc.
        """
        subset: dict[str, Any] = {}
        for field in CACHE_KEY_FIELDS:
            if field in config:
                subset[field] = config[field]
        return subset
