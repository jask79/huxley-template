"""
Reference Image Library Manager for the Media Workflow Engine.

Manages per-capsule and shared reference image libraries. Handles loading,
indexing, selecting, and tracking reference images used during generation
for style and character consistency.

Reference image directories:
  - references/_shared/        Global shared refs for all workflows
  - capsules/{name}/references/ Capsule-specific refs (overrides)
  - Explicit paths via config   consistency.reference_paths
"""

from __future__ import annotations

import json
import os
import random
import shutil
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Engine root for reference directory resolution
ENGINE_ROOT = Path("{{CATALYST_ROOT}}/tools/media-engine")
SHARED_REFS_DIR = ENGINE_ROOT / "references" / "_shared"
CONSISTENCY_LOG_DIR = ENGINE_ROOT / "eval" / "consistency-log"

# Supported image formats
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class ReferenceManager:
    """
    Manages reference image libraries for style/character consistency.

    Loads reference images from shared, capsule-specific, and explicit
    directories. Supports multiple selection strategies and tracks which
    references were used for each generation session.
    """

    def __init__(self, engine_root: str | Path | None = None) -> None:
        self.engine_root = Path(engine_root) if engine_root else ENGINE_ROOT
        self.shared_dir = self.engine_root / "references" / "_shared"
        self.log_dir = self.engine_root / "eval" / "consistency-log"

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_references(
        self,
        config: dict[str, Any],
        capsule_path: str | None = None,
    ) -> list[str]:
        """
        Load reference image paths based on config and capsule context.

        Resolution order:
          1. Explicit paths from config consistency.reference_paths
          2. Capsule-specific references (capsules/{name}/references/)
          3. Shared references (references/_shared/)

        The total count is limited by config consistency.reference_images.
        When more images exist than the limit, the most recent N are returned.

        Args:
            config: Resolved workflow config dict.
            capsule_path: Optional path to the capsule directory.

        Returns:
            List of absolute paths to reference images.
        """
        consistency = config.get("consistency", {})
        max_count = consistency.get("reference_images", 0)

        if max_count <= 0:
            return []

        all_refs: list[str] = []

        # Source 1: explicit reference_paths from config
        explicit_paths = consistency.get("reference_paths", [])
        if isinstance(explicit_paths, list):
            for ref_path in explicit_paths:
                ref_path = str(ref_path)
                if not os.path.isabs(ref_path):
                    ref_path = str(self.engine_root / ref_path)
                if os.path.isdir(ref_path):
                    all_refs.extend(self._scan_directory(ref_path))
                elif os.path.isfile(ref_path) and _is_image(ref_path):
                    all_refs.append(ref_path)

        # Source 2: capsule-specific references
        if capsule_path:
            capsule_refs_dir = Path(capsule_path) / "references"
            if capsule_refs_dir.is_dir():
                all_refs.extend(self._scan_directory(str(capsule_refs_dir)))

        # Source 3: shared references
        if self.shared_dir.is_dir():
            all_refs.extend(self._scan_directory(str(self.shared_dir)))

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_refs: list[str] = []
        for ref in all_refs:
            real = os.path.realpath(ref)
            if real not in seen:
                seen.add(real)
                unique_refs.append(ref)

        # Select the right number using the configured or default strategy
        strategy = consistency.get("reference_strategy", "recent")
        return self.select_references(unique_refs, max_count, strategy)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_references(self, directory: str) -> dict[str, dict[str, Any]]:
        """
        Index all reference images in a directory.

        Args:
            directory: Path to scan for images.

        Returns:
            Dict mapping filename to metadata:
              - path: absolute path
              - size: file size in bytes
              - dimensions: (width, height) tuple or None
              - date: last modified datetime ISO string
        """
        result: dict[str, dict[str, Any]] = {}
        dir_path = Path(directory)

        if not dir_path.is_dir():
            return result

        for entry in sorted(dir_path.iterdir()):
            if not entry.is_file() or not _is_image(str(entry)):
                continue

            stat = entry.stat()
            dims = _read_image_dimensions_safe(entry)

            result[entry.name] = {
                "path": str(entry.resolve()),
                "size": stat.st_size,
                "dimensions": dims,
                "date": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            }

        return result

    # ------------------------------------------------------------------
    # Selection strategies
    # ------------------------------------------------------------------

    def select_references(
        self,
        all_refs: list[str],
        count: int,
        strategy: str = "recent",
    ) -> list[str]:
        """
        Select a subset of reference images using the specified strategy.

        Args:
            all_refs: All available reference image paths.
            count: Maximum number of references to select.
            strategy: Selection strategy:
                - "recent": newest files first (by mtime)
                - "diverse": spread across modification dates
                - "random": random sample

        Returns:
            Selected subset of reference paths.
        """
        if not all_refs or count <= 0:
            return []

        if len(all_refs) <= count:
            return list(all_refs)

        if strategy == "recent":
            return self._select_recent(all_refs, count)
        elif strategy == "diverse":
            return self._select_diverse(all_refs, count)
        elif strategy == "random":
            return self._select_random(all_refs, count)
        else:
            # Default to recent for unknown strategies
            return self._select_recent(all_refs, count)

    # ------------------------------------------------------------------
    # Adding references
    # ------------------------------------------------------------------

    def add_reference(self, directory: str, image_path: str) -> str:
        """
        Copy or link an image into a reference library directory.

        Args:
            directory: Target reference library directory.
            image_path: Path to the image to add.

        Returns:
            Path to the copied/linked image in the library.

        Raises:
            FileNotFoundError: If the source image doesn't exist.
            ValueError: If the file isn't a supported image format.
        """
        src = Path(image_path)
        if not src.exists():
            raise FileNotFoundError(f"Source image not found: {image_path}")

        if not _is_image(str(src)):
            raise ValueError(
                f"Not a supported image format: {src.suffix}. "
                f"Supported: {sorted(IMAGE_EXTENSIONS)}"
            )

        dest_dir = Path(directory)
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest = dest_dir / src.name

        # If destination already exists, add a numeric suffix
        if dest.exists():
            stem = src.stem
            suffix = src.suffix
            counter = 1
            while dest.exists():
                dest = dest_dir / f"{stem}_{counter:03d}{suffix}"
                counter += 1

        shutil.copy2(str(src), str(dest))
        return str(dest)

    # ------------------------------------------------------------------
    # Generation tracking
    # ------------------------------------------------------------------

    def track_generation(
        self,
        session_id: str,
        output_path: str,
        refs_used: list[str],
    ) -> dict[str, Any]:
        """
        Record which reference images were used for a generation.

        Writes a JSONL entry to eval/consistency-log/ for cross-generation
        tracking and consistency analysis.

        Args:
            session_id: Unique identifier for this generation session.
            output_path: Path to the generated output image.
            refs_used: List of reference image paths that were used.

        Returns:
            The tracking record dict.
        """
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "output_path": output_path,
            "references_used": refs_used,
            "reference_count": len(refs_used),
        }

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        log_path = self.log_dir / "consistency.jsonl"
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except OSError as exc:
            print(f"Warning: Could not write consistency log: {exc}")

        return record

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _scan_directory(directory: str) -> list[str]:
        """Scan a directory for image files, returning absolute paths."""
        results: list[str] = []
        dir_path = Path(directory)

        if not dir_path.is_dir():
            return results

        for entry in sorted(dir_path.iterdir()):
            if entry.is_file() and _is_image(str(entry)):
                results.append(str(entry.resolve()))

        return results

    @staticmethod
    def _select_recent(refs: list[str], count: int) -> list[str]:
        """Select the N most recently modified images."""
        with_mtime = []
        for ref in refs:
            try:
                mtime = os.path.getmtime(ref)
            except OSError:
                mtime = 0.0
            with_mtime.append((ref, mtime))

        with_mtime.sort(key=lambda x: x[1], reverse=True)
        return [ref for ref, _ in with_mtime[:count]]

    @staticmethod
    def _select_diverse(refs: list[str], count: int) -> list[str]:
        """Select images spread across modification dates (evenly spaced)."""
        with_mtime = []
        for ref in refs:
            try:
                mtime = os.path.getmtime(ref)
            except OSError:
                mtime = 0.0
            with_mtime.append((ref, mtime))

        with_mtime.sort(key=lambda x: x[1])
        total = len(with_mtime)

        # Pick evenly spaced indices
        if count >= total:
            return [ref for ref, _ in with_mtime]

        step = total / count
        selected: list[str] = []
        for i in range(count):
            idx = int(i * step)
            selected.append(with_mtime[idx][0])

        return selected

    @staticmethod
    def _select_random(refs: list[str], count: int) -> list[str]:
        """Select a random sample of images."""
        return random.sample(refs, min(count, len(refs)))


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _is_image(path: str) -> bool:
    """Check if a file path has a supported image extension."""
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def _read_image_dimensions_safe(path: Path) -> tuple[int, int] | None:
    """
    Read image dimensions from file header. Returns None on failure.

    Supports PNG and JPEG only (stdlib, no Pillow).
    """
    suffix = path.suffix.lower()

    try:
        with open(path, "rb") as f:
            if suffix == ".png":
                header = f.read(24)
                if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
                    return None
                width = struct.unpack(">I", header[16:20])[0]
                height = struct.unpack(">I", header[20:24])[0]
                return width, height

            elif suffix in (".jpg", ".jpeg"):
                data = f.read(65536)
                i = 0
                while i < len(data) - 9:
                    if data[i] == 0xFF:
                        marker = data[i + 1]
                        if marker in (0xC0, 0xC2):
                            height = struct.unpack(">H", data[i + 5 : i + 7])[0]
                            width = struct.unpack(">H", data[i + 7 : i + 9])[0]
                            return width, height
                        elif marker == 0xD8:
                            i += 2
                        elif marker == 0xFF:
                            i += 1
                        else:
                            if i + 3 < len(data):
                                seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
                                i += 2 + seg_len
                            else:
                                break
                    else:
                        i += 1
    except OSError:
        pass

    return None
