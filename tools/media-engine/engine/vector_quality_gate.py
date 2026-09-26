"""
Vector Quality Gate for AI-to-Vector Traced Output.

Evaluates whether VTracer output meets quality thresholds. Prevents
messy, over-complex traces from being accepted as final output.

The quality gate checks:
  - Path count: too many paths = over-complex trace
  - File size: oversized SVGs are impractical
  - Estimated color count: sanity check
  - Simplification ratio: compares trace complexity to source image

If a trace fails the gate, it recommends parameter adjustments.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import Any

from lxml import etree


class QualityGateError(Exception):
    """Raised when quality gate operations encounter errors."""


class VectorQualityGate:
    """
    Quality gate for AI-to-vector traced output.

    Evaluates trace quality and provides recommendations:
      - "accept": trace meets all thresholds
      - "retry_simpler": trace is too complex, suggest simpler parameters
      - "reject": trace is fundamentally unsuitable
    """

    def __init__(
        self,
        max_paths: int = 500,
        max_file_size_kb: int = 500,
        min_simplification_ratio: float = 0.3,
        max_colors: int = 64,
    ) -> None:
        """
        Initialize quality gate with thresholds.

        Args:
            max_paths: Maximum acceptable number of <path> elements.
            max_file_size_kb: Maximum SVG file size in kilobytes.
            min_simplification_ratio: Not used as a ratio per se --
                this is a soft threshold. If path_count/1000 exceeds
                this value, the trace is considered too complex.
            max_colors: Maximum acceptable distinct colors.
        """
        self.max_paths = max_paths
        self.max_file_size_kb = max_file_size_kb
        self.min_simplification_ratio = min_simplification_ratio
        self.max_colors = max_colors

    def evaluate(
        self,
        traced_svg: str,
        source_image: str | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate trace quality against thresholds.

        Args:
            traced_svg: Path to the traced SVG file.
            source_image: Optional path to the source raster image
                (used for dimension-based analysis).

        Returns:
            Dict with keys:
              - passed: bool, whether the trace passes the gate
              - path_count: int, number of <path> elements
              - file_size_kb: float, SVG file size in KB
              - estimated_colors: int, distinct colors found
              - source_dimensions: tuple or None, (width, height) of source
              - issues: list[str], reasons for failure
              - recommendation: str, one of "accept", "retry_simpler", "reject"
              - suggested_adjustments: dict, parameter adjustments if retry
        """
        result: dict[str, Any] = {
            "passed": False,
            "path_count": 0,
            "file_size_kb": 0.0,
            "estimated_colors": 0,
            "source_dimensions": None,
            "issues": [],
            "recommendation": "accept",
            "suggested_adjustments": {},
        }

        svg_path = Path(traced_svg)
        if not svg_path.exists():
            result["issues"].append(f"Traced SVG not found: {traced_svg}")
            result["recommendation"] = "reject"
            return result

        # File size check
        file_size = svg_path.stat().st_size
        file_size_kb = file_size / 1024
        result["file_size_kb"] = round(file_size_kb, 1)

        if file_size_kb > self.max_file_size_kb:
            result["issues"].append(
                f"File size {file_size_kb:.1f}KB exceeds limit of {self.max_file_size_kb}KB"
            )

        # Parse SVG and analyze paths/colors
        try:
            tree = etree.parse(str(svg_path))
            root = tree.getroot()
        except etree.XMLSyntaxError as exc:
            result["issues"].append(f"Invalid SVG XML: {exc}")
            result["recommendation"] = "reject"
            return result

        # Count paths
        path_elements = root.xpath("//*[local-name()='path']")
        path_count = len(path_elements)
        result["path_count"] = path_count

        if path_count > self.max_paths:
            result["issues"].append(
                f"Path count {path_count} exceeds limit of {self.max_paths}"
            )

        # Estimate colors
        colors: set[str] = set()
        for path_el in path_elements:
            fill = path_el.get("fill")
            if fill and fill != "none":
                colors.add(fill.lower())
            stroke = path_el.get("stroke")
            if stroke and stroke != "none":
                colors.add(stroke.lower())
        # Check style attributes too
        for el in root.iter():
            style = el.get("style", "")
            if "fill:" in style:
                parts = style.split("fill:")
                if len(parts) > 1:
                    color_val = parts[1].split(";")[0].strip()
                    if color_val and color_val != "none":
                        colors.add(color_val.lower())

        estimated_colors = len(colors) if colors else 1
        result["estimated_colors"] = estimated_colors

        if estimated_colors > self.max_colors:
            result["issues"].append(
                f"Color count {estimated_colors} exceeds limit of {self.max_colors}"
            )

        # Source image analysis (optional)
        if source_image:
            dims = self._read_image_dimensions(source_image)
            if dims:
                result["source_dimensions"] = dims

        # Determine recommendation
        issues = result["issues"]
        if not issues:
            result["passed"] = True
            result["recommendation"] = "accept"
        elif len(issues) == 1 and "File size" in issues[0]:
            # Only file size issue -- might be fixable with simpler params
            result["recommendation"] = "retry_simpler"
            result["suggested_adjustments"] = self._suggest_simpler_params(
                path_count, file_size_kb, estimated_colors
            )
        elif path_count > self.max_paths * 2 or file_size_kb > self.max_file_size_kb * 3:
            # Way over limits -- fundamentally unsuitable
            result["recommendation"] = "reject"
        else:
            result["recommendation"] = "retry_simpler"
            result["suggested_adjustments"] = self._suggest_simpler_params(
                path_count, file_size_kb, estimated_colors
            )

        return result

    def suggest_params(self, source_image: str) -> dict[str, Any]:
        """
        Analyze a source image and suggest optimal VTracer parameters.

        Examines image dimensions and estimates complexity to recommend
        appropriate tracing parameters.

        Args:
            source_image: Path to the source raster image.

        Returns:
            Dict of recommended VTracer parameters.
        """
        dims = self._read_image_dimensions(source_image)
        params: dict[str, Any] = {
            "mode": "polygon",
            "color_precision": 6,
            "filter_speckle": 4,
            "corner_threshold": 60,
            "length_threshold": 4.0,
            "max_iterations": 10,
            "splice_threshold": 45,
            "path_precision": 3,
        }

        if dims:
            width, height = dims
            total_pixels = width * height

            if total_pixels > 4_000_000:
                # Large image -- use simpler settings to keep output manageable
                params["color_precision"] = 4
                params["filter_speckle"] = 8
                params["length_threshold"] = 6.0
                params["path_precision"] = 2
            elif total_pixels < 250_000:
                # Small image (icon-sized) -- geometric preset
                params["mode"] = "polygon"
                params["color_precision"] = 4
                params["filter_speckle"] = 6
                params["corner_threshold"] = 90
                params["length_threshold"] = 6.0
            else:
                # Medium image -- balanced preset
                params["color_precision"] = 6
                params["filter_speckle"] = 4

        # Check file size for format hints
        file_path = Path(source_image)
        if file_path.exists():
            file_size_kb = file_path.stat().st_size / 1024
            if file_size_kb < 50:
                # Small file likely a simple image -- geometric
                params["color_precision"] = min(params["color_precision"], 4)
                params["filter_speckle"] = max(params["filter_speckle"], 6)

        return params

    @staticmethod
    def _suggest_simpler_params(
        path_count: int,
        file_size_kb: float,
        color_count: int,
    ) -> dict[str, Any]:
        """
        Suggest simpler VTracer parameters based on what exceeded limits.

        Returns a dict of parameter adjustments to try.
        """
        adjustments: dict[str, Any] = {}

        if path_count > 500:
            # Too many paths -- reduce color precision and increase speckle filter
            adjustments["color_precision"] = max(2, 4)
            adjustments["filter_speckle"] = 8
            adjustments["length_threshold"] = 6.0

        if file_size_kb > 500:
            # File too large -- reduce precision
            adjustments["path_precision"] = 2
            if "color_precision" not in adjustments:
                adjustments["color_precision"] = 4
            adjustments["filter_speckle"] = max(
                adjustments.get("filter_speckle", 4), 6
            )

        if color_count > 32:
            # Too many colors
            adjustments["color_precision"] = max(2, min(
                adjustments.get("color_precision", 6), 3
            ))

        return adjustments

    @staticmethod
    def _read_image_dimensions(image_path: str) -> tuple[int, int] | None:
        """
        Read image dimensions from file header (PNG or JPEG).

        Uses stdlib only -- no Pillow dependency.

        Args:
            image_path: Path to the image file.

        Returns:
            (width, height) tuple, or None if unreadable.
        """
        path = Path(image_path)
        if not path.exists():
            return None

        try:
            with open(path, "rb") as f:
                header = f.read(32)
        except OSError:
            return None

        # PNG: IHDR chunk at offset 16-24
        if header[:8] == b"\x89PNG\r\n\x1a\n" and len(header) >= 24:
            width = struct.unpack(">I", header[16:20])[0]
            height = struct.unpack(">I", header[20:24])[0]
            return width, height

        # JPEG: scan for SOF0/SOF2 markers
        if header[:2] in (b"\xff\xd8",):
            try:
                with open(path, "rb") as f:
                    f.read(2)  # Skip SOI
                    while True:
                        marker = f.read(2)
                        if len(marker) < 2:
                            break
                        if marker[0] != 0xFF:
                            break
                        # SOF0 or SOF2
                        if marker[1] in (0xC0, 0xC2):
                            length_data = f.read(2)
                            f.read(1)  # precision
                            height_data = f.read(2)
                            width_data = f.read(2)
                            if len(width_data) == 2 and len(height_data) == 2:
                                h = struct.unpack(">H", height_data)[0]
                                w = struct.unpack(">H", width_data)[0]
                                return w, h
                            break
                        else:
                            # Skip this segment
                            length_data = f.read(2)
                            if len(length_data) < 2:
                                break
                            seg_len = struct.unpack(">H", length_data)[0]
                            f.seek(seg_len - 2, 1)
            except OSError:
                return None

        return None
