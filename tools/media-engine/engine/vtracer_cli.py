"""
VTracer Wrapper for Raster-to-Vector Conversion.

Provides a Python interface for VTracer's raster-to-vector tracing with
quality presets and parameter tuning. VTracer (Rust, Python bindings) is
an optional dependency -- the rest of the engine works without it.

Install: pip3 install vtracer

Parameters Reference:
  - mode: "polygon" (sharp edges) or "spline" (smooth curves)
  - color_precision: Number of colors (1-12). Higher = more detail, more paths.
  - filter_speckle: Remove small blobs under N pixels. Higher = cleaner, less detail.
  - corner_threshold: Angle in degrees for corner detection (0-180).
  - length_threshold: Min segment length before simplification.
  - max_iterations: Color clustering iterations (more = better colors, slower).
  - splice_threshold: Angle for path splicing (0-180).
  - path_precision: Decimal places for path coordinates (1-8).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from lxml import etree


class VTracerError(Exception):
    """Raised when VTracer operations fail."""


# Quality presets mapping quality name to VTracer parameters
QUALITY_PRESETS: dict[str, dict[str, Any]] = {
    "fast": {
        "mode": "polygon",
        "color_precision": 3,
        "filter_speckle": 8,
        "corner_threshold": 60,
        "length_threshold": 4.0,
        "max_iterations": 5,
        "splice_threshold": 45,
        "path_precision": 2,
    },
    "balanced": {
        "mode": "polygon",
        "color_precision": 6,
        "filter_speckle": 4,
        "corner_threshold": 60,
        "length_threshold": 4.0,
        "max_iterations": 10,
        "splice_threshold": 45,
        "path_precision": 3,
    },
    "detailed": {
        "mode": "spline",
        "color_precision": 10,
        "filter_speckle": 2,
        "corner_threshold": 45,
        "length_threshold": 2.0,
        "max_iterations": 15,
        "splice_threshold": 30,
        "path_precision": 4,
    },
    "geometric": {
        "mode": "polygon",
        "color_precision": 4,
        "filter_speckle": 6,
        "corner_threshold": 90,
        "length_threshold": 6.0,
        "max_iterations": 10,
        "splice_threshold": 60,
        "path_precision": 2,
    },
}


class VTracerWrapper:
    """
    Wrapper for VTracer raster-to-vector conversion.

    VTracer is an optional dependency. If not installed, is_available()
    returns False and trace operations raise VTracerError with install
    instructions.
    """

    def __init__(self) -> None:
        """Initialize and check if vtracer is available."""
        self._available: bool | None = None

    def is_available(self) -> bool:
        """
        Check if the vtracer Python package is installed.

        Returns:
            True if vtracer can be imported, False otherwise.
        """
        if self._available is None:
            try:
                import vtracer  # noqa: F401
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def _require_available(self) -> None:
        """Raise VTracerError if vtracer is not installed."""
        if not self.is_available():
            raise VTracerError(
                "vtracer is not installed. Install via: pip3 install vtracer\n"
                "VTracer is an optional dependency for raster-to-vector tracing."
            )

    def trace(
        self,
        input_image: str,
        output_svg: str,
        mode: str = "polygon",
        color_precision: int = 6,
        filter_speckle: int = 4,
        corner_threshold: int = 60,
        length_threshold: float = 4.0,
        max_iterations: int = 10,
        splice_threshold: int = 45,
        path_precision: int = 3,
    ) -> dict[str, Any]:
        """
        Trace a raster image to SVG vectors.

        Args:
            input_image: Path to PNG/JPG input.
            output_svg: Path for SVG output.
            mode: "polygon" (sharp edges) or "spline" (smooth curves).
            color_precision: Number of colors (1-12, higher = more detail).
            filter_speckle: Remove small blobs under N pixels.
            corner_threshold: Corner detection angle in degrees.
            length_threshold: Minimum path segment length.
            max_iterations: Color clustering iterations.
            splice_threshold: Angle threshold for path splicing.
            path_precision: Decimal precision for path coordinates.

        Returns:
            Dict with keys:
              - svg_path: str, absolute path to the output SVG
              - path_count: int, number of <path> elements in the SVG
              - file_size: int, SVG file size in bytes
              - colors_used: int, estimated number of distinct colors
              - trace_time_ms: int, time taken for tracing in milliseconds
              - mode: str, the tracing mode used
              - params: dict, the parameters used for tracing

        Raises:
            VTracerError: If vtracer is not installed or tracing fails.
        """
        self._require_available()
        import vtracer

        input_path = Path(input_image)
        if not input_path.exists():
            raise VTracerError(f"Input image not found: {input_image}")

        if not input_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
            raise VTracerError(
                f"Unsupported image format: {input_path.suffix}. "
                "VTracer supports: PNG, JPG, BMP, GIF."
            )

        # Validate parameters
        if mode not in ("polygon", "spline"):
            raise VTracerError(f"mode must be 'polygon' or 'spline', got '{mode}'")
        if not 1 <= color_precision <= 12:
            raise VTracerError(f"color_precision must be 1-12, got {color_precision}")
        if filter_speckle < 0:
            raise VTracerError(f"filter_speckle must be >= 0, got {filter_speckle}")

        # Ensure output directory exists
        output_path = Path(output_svg)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        start_time = time.monotonic()

        try:
            # Use positional arguments to avoid a segfault in the PyO3 bindings
            # on Python 3.14+ where keyword arguments to convert_image_to_svg_py
            # cause a crash. The positional arg order is:
            #   image_path, out_path, colormode, hierarchical, mode,
            #   filter_speckle, color_precision, layer_difference,
            #   corner_threshold, length_threshold, max_iterations,
            #   splice_threshold, path_precision
            vtracer.convert_image_to_svg_py(
                str(input_path),        # image_path
                str(output_path),       # out_path
                "color",                # colormode (always "color")
                "stacked",              # hierarchical (always "stacked")
                mode,                   # mode: "polygon" or "spline"
                filter_speckle,         # filter_speckle
                color_precision,        # color_precision
                16,                     # layer_difference (default)
                corner_threshold,       # corner_threshold
                length_threshold,       # length_threshold
                max_iterations,         # max_iterations
                splice_threshold,       # splice_threshold
                path_precision,         # path_precision
            )
        except Exception as exc:
            raise VTracerError(f"VTracer tracing failed: {exc}") from exc

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        if not output_path.exists():
            raise VTracerError(
                f"VTracer produced no output file at: {output_svg}"
            )

        # Analyze the output SVG
        file_size = output_path.stat().st_size
        path_count, colors_used = self._analyze_svg(str(output_path))

        params = {
            "mode": mode,
            "color_precision": color_precision,
            "filter_speckle": filter_speckle,
            "corner_threshold": corner_threshold,
            "length_threshold": length_threshold,
            "max_iterations": max_iterations,
            "splice_threshold": splice_threshold,
            "path_precision": path_precision,
        }

        return {
            "svg_path": os.path.abspath(str(output_path)),
            "path_count": path_count,
            "file_size": file_size,
            "colors_used": colors_used,
            "trace_time_ms": elapsed_ms,
            "mode": mode,
            "params": params,
        }

    def trace_and_simplify(
        self,
        input_image: str,
        output_svg: str,
        quality: str = "balanced",
    ) -> dict[str, Any]:
        """
        Trace with a preset quality level.

        Quality presets:
          - "fast": Low detail, small files. Good for quick drafts.
          - "balanced": Good detail/size trade-off. Default.
          - "detailed": Max detail, larger files. For high-fidelity work.
          - "geometric": Optimized for geometric/icon source images
            (sharp corners, low colors, clean edges).

        Args:
            input_image: Path to PNG/JPG input.
            output_svg: Path for SVG output.
            quality: Preset name ("fast", "balanced", "detailed", "geometric").

        Returns:
            Same as trace() plus a "quality_preset" key.

        Raises:
            VTracerError: If the quality preset is unknown or tracing fails.
        """
        if quality not in QUALITY_PRESETS:
            raise VTracerError(
                f"Unknown quality preset: '{quality}'. "
                f"Valid presets: {', '.join(sorted(QUALITY_PRESETS.keys()))}"
            )

        params = QUALITY_PRESETS[quality]
        result = self.trace(input_image, output_svg, **params)
        result["quality_preset"] = quality
        return result

    @staticmethod
    def _analyze_svg(svg_path: str) -> tuple[int, int]:
        """
        Count paths and estimate distinct colors in a traced SVG.

        Args:
            svg_path: Path to the SVG file.

        Returns:
            Tuple of (path_count, estimated_colors).
        """
        try:
            tree = etree.parse(svg_path)
            root = tree.getroot()

            # Count <path> elements (with or without namespace)
            path_elements = root.xpath("//*[local-name()='path']")
            path_count = len(path_elements)

            # Estimate colors by collecting unique fill values
            colors: set[str] = set()
            for path_el in path_elements:
                fill = path_el.get("fill")
                if fill and fill != "none":
                    colors.add(fill.lower())
                stroke = path_el.get("stroke")
                if stroke and stroke != "none":
                    colors.add(stroke.lower())

            # Also check style attributes for fill/stroke
            for el in root.iter():
                style = el.get("style", "")
                if "fill:" in style:
                    parts = style.split("fill:")
                    if len(parts) > 1:
                        color_val = parts[1].split(";")[0].strip()
                        if color_val and color_val != "none":
                            colors.add(color_val.lower())

            return path_count, len(colors) if colors else 1

        except (etree.XMLSyntaxError, OSError):
            return 0, 0

    @staticmethod
    def get_available_presets() -> dict[str, dict[str, Any]]:
        """Return all available quality presets and their parameters."""
        return dict(QUALITY_PRESETS)
