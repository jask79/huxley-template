"""
Inkscape CLI Wrapper for the Media Workflow Engine.

Provides a Python interface to Inkscape's headless CLI for operations that
svgwrite can't do natively:
  - Text-to-path conversion (font portability)
  - EPS export (legacy print workflows)
  - CMYK PDF export (print production)
  - Print bleed/crop mark generation

All operations are OPTIONAL. If Inkscape is not installed, the engine still
works -- Phase 1+2 features never require Inkscape. Every method returns a
clear error when Inkscape is unavailable rather than crashing.

Minimum supported version: Inkscape 1.3
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from lxml import etree


class InkscapeError(Exception):
    """Raised when an Inkscape CLI operation fails."""


class InkscapeNotFoundError(InkscapeError):
    """Raised when Inkscape binary cannot be located or does not meet version requirements."""


class InkscapeCLI:
    """Wrapper for Inkscape headless CLI with version pinning."""

    MINIMUM_VERSION = "1.3"

    # Search paths for the Inkscape binary, in order of preference
    _SEARCH_PATHS = [
        "/Applications/Inkscape.app/Contents/MacOS/inkscape",
        "/opt/homebrew/bin/inkscape",
        "/usr/local/bin/inkscape",
    ]

    # Default timeout for Inkscape operations (seconds)
    DEFAULT_TIMEOUT = 30

    def __init__(self, inkscape_path: str | None = None) -> None:
        """
        Discover Inkscape binary and verify version.

        Args:
            inkscape_path: Explicit path to Inkscape binary. If None,
                searches standard macOS locations then PATH.
        """
        self._binary_path: str | None = None
        self._version: str | None = None
        self._available: bool = False

        if inkscape_path:
            self._binary_path = inkscape_path
        else:
            self._binary_path = self._discover_binary()

        if self._binary_path:
            try:
                self._version = self._check_version()
                self._available = True
            except InkscapeError:
                self._available = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if Inkscape is installed and meets version requirements."""
        return self._available

    def get_version(self) -> str:
        """Return Inkscape version string, or empty string if unavailable."""
        return self._version or ""

    def get_binary_path(self) -> str:
        """Return the resolved binary path, or empty string if unavailable."""
        return self._binary_path or ""

    def text_to_path(self, input_svg: str, output_svg: str | None = None) -> str:
        """
        Convert all <text> elements to <path> for font portability.

        This is the primary use case. Produces an SVG where text is rendered
        as paths, eliminating font dependencies. The original SVG with
        editable text is preserved; this creates a separate "outlined" version.

        Args:
            input_svg: Path to the source SVG file.
            output_svg: Path for the outlined output. If None, generates
                an *-outlined.svg alongside the original.

        Returns:
            Absolute path to the outlined SVG file.

        Raises:
            InkscapeNotFoundError: If Inkscape is not available.
            InkscapeError: If the operation fails.
        """
        self._require_available()
        input_svg = os.path.abspath(input_svg)
        self._require_file(input_svg)
        self._sanitize_path(input_svg)

        if output_svg is None:
            stem = Path(input_svg).stem
            parent = Path(input_svg).parent
            output_svg = str(parent / f"{stem}-outlined.svg")

        output_svg = os.path.abspath(output_svg)
        self._sanitize_path(output_svg)

        # Inkscape actions: select all objects, convert to paths, save as
        actions = [
            f"file-open:{input_svg}",
            "select-all",
            "object-to-path",
            f"export-filename:{output_svg}",
            "export-type:svg",
            "export-do",
        ]

        self._run_actions(actions, timeout=self.DEFAULT_TIMEOUT)

        if not Path(output_svg).exists():
            raise InkscapeError(
                f"Text-to-path conversion failed: output not created at {output_svg}"
            )

        return output_svg

    def export_eps(self, input_svg: str, output_eps: str | None = None) -> str:
        """
        Export SVG to EPS format for legacy print workflows.

        Args:
            input_svg: Path to the source SVG file.
            output_eps: Path for the EPS output. If None, uses the SVG
                path with .eps extension.

        Returns:
            Absolute path to the EPS file.

        Raises:
            InkscapeNotFoundError: If Inkscape is not available.
            InkscapeError: If the export fails.
        """
        self._require_available()
        input_svg = os.path.abspath(input_svg)
        self._require_file(input_svg)
        self._sanitize_path(input_svg)

        if output_eps is None:
            output_eps = str(Path(input_svg).with_suffix(".eps"))

        output_eps = os.path.abspath(output_eps)
        self._sanitize_path(output_eps)

        actions = [
            f"file-open:{input_svg}",
            f"export-filename:{output_eps}",
            "export-type:eps",
            "export-do",
        ]

        self._run_actions(actions, timeout=self.DEFAULT_TIMEOUT)

        if not Path(output_eps).exists():
            raise InkscapeError(
                f"EPS export failed: output not created at {output_eps}"
            )

        return output_eps

    def export_cmyk_pdf(
        self,
        input_svg: str,
        output_pdf: str | None = None,
        color_profile: str | None = None,
    ) -> str:
        """
        Export SVG to PDF suitable for print production.

        Uses Inkscape's PDF export which produces better print-quality
        output than cairosvg. If a color_profile ICC path is provided,
        it is applied for CMYK conversion.

        Args:
            input_svg: Path to the source SVG file.
            output_pdf: Path for the PDF output. If None, uses
                *-cmyk.pdf alongside the original.
            color_profile: Optional path to an ICC color profile file
                for CMYK conversion.

        Returns:
            Absolute path to the PDF file.

        Raises:
            InkscapeNotFoundError: If Inkscape is not available.
            InkscapeError: If the export fails.
        """
        self._require_available()
        input_svg = os.path.abspath(input_svg)
        self._require_file(input_svg)
        self._sanitize_path(input_svg)

        if output_pdf is None:
            stem = Path(input_svg).stem
            parent = Path(input_svg).parent
            output_pdf = str(parent / f"{stem}-cmyk.pdf")

        output_pdf = os.path.abspath(output_pdf)
        self._sanitize_path(output_pdf)

        # If a color profile is specified, inject it into the SVG first
        svg_to_export = input_svg
        if color_profile and Path(color_profile).exists():
            svg_to_export = self._apply_color_profile(input_svg, color_profile)

        actions = [
            f"file-open:{svg_to_export}",
            f"export-filename:{output_pdf}",
            "export-type:pdf",
            "export-do",
        ]

        self._run_actions(actions, timeout=self.DEFAULT_TIMEOUT)

        # Clean up temporary profile-injected SVG
        if svg_to_export != input_svg and Path(svg_to_export).exists():
            try:
                os.remove(svg_to_export)
            except OSError:
                pass

        if not Path(output_pdf).exists():
            raise InkscapeError(
                f"CMYK PDF export failed: output not created at {output_pdf}"
            )

        return output_pdf

    def add_bleed(
        self,
        input_svg: str,
        output_svg: str | None = None,
        bleed_mm: float = 3.0,
    ) -> str:
        """
        Add print bleed area to SVG.

        Extends the document by bleed_mm on all sides and adds crop marks
        at the original document boundaries. Uses lxml for precise SVG
        manipulation rather than Inkscape actions.

        Args:
            input_svg: Path to the source SVG file.
            output_svg: Path for the output. If None, generates
                *-bleed.svg alongside the original.
            bleed_mm: Bleed area in millimeters (default: 3.0mm).

        Returns:
            Absolute path to the SVG with bleed.

        Raises:
            InkscapeError: If the operation fails.
        """
        # Bleed is done via lxml -- does NOT require Inkscape
        input_svg = os.path.abspath(input_svg)
        self._require_file(input_svg)

        if output_svg is None:
            stem = Path(input_svg).stem
            parent = Path(input_svg).parent
            output_svg = str(parent / f"{stem}-bleed.svg")

        output_svg = os.path.abspath(output_svg)

        try:
            tree = etree.parse(input_svg)
            root = tree.getroot()
        except etree.XMLSyntaxError as exc:
            raise InkscapeError(f"Cannot parse SVG for bleed: {exc}") from exc

        # Parse current viewBox and dimensions
        viewbox_str = root.get("viewBox") or root.get("viewbox")
        if not viewbox_str:
            raise InkscapeError(
                "SVG has no viewBox attribute. Cannot add bleed without "
                "knowing document dimensions."
            )

        parts = viewbox_str.strip().replace(",", " ").split()
        if len(parts) != 4:
            raise InkscapeError(f"Invalid viewBox: {viewbox_str}")

        vb_x, vb_y, vb_w, vb_h = [float(p) for p in parts]

        # Convert bleed from mm to SVG user units
        # SVG default is 1 user unit = 1px at 96 DPI
        # 1mm = 3.7795275591 px at 96 DPI
        MM_TO_PX = 3.7795275591
        bleed_px = bleed_mm * MM_TO_PX

        # Expand viewBox
        new_vb_x = vb_x - bleed_px
        new_vb_y = vb_y - bleed_px
        new_vb_w = vb_w + 2 * bleed_px
        new_vb_h = vb_h + 2 * bleed_px

        root.set("viewBox", f"{new_vb_x} {new_vb_y} {new_vb_w} {new_vb_h}")

        # Update width/height if present
        width = root.get("width")
        height = root.get("height")
        if width:
            w_val, w_unit = self._parse_dimension(width)
            if w_unit == "mm":
                root.set("width", f"{w_val + 2 * bleed_mm}mm")
            else:
                root.set("width", f"{w_val + 2 * bleed_px}{w_unit}")
        if height:
            h_val, h_unit = self._parse_dimension(height)
            if h_unit == "mm":
                root.set("height", f"{h_val + 2 * bleed_mm}mm")
            else:
                root.set("height", f"{h_val + 2 * bleed_px}{h_unit}")

        # Shift existing content to account for the bleed offset by wrapping
        # everything in a translate group
        SVG_NS = "http://www.w3.org/2000/svg"
        wrapper = etree.SubElement(
            root, f"{{{SVG_NS}}}g" if SVG_NS in root.tag else "g"
        )
        wrapper.set("id", "bleed-content-wrapper")
        wrapper.set("transform", f"translate({bleed_px}, {bleed_px})")

        # Move all existing children into the wrapper
        children = list(root)
        for child in children:
            if child is not wrapper:
                root.remove(child)
                wrapper.append(child)

        # Add crop marks at original document boundaries
        self._add_crop_marks_to_tree(
            root, vb_x, vb_y, vb_w, vb_h, bleed_px, SVG_NS
        )

        # Write output
        tree.write(
            output_svg,
            xml_declaration=True,
            encoding="utf-8",
            pretty_print=True,
        )

        return output_svg

    def add_crop_marks(
        self,
        input_svg: str,
        output_svg: str | None = None,
    ) -> str:
        """
        Add crop/registration marks for print production.

        Adds corner crop marks and center registration marks on a
        separate layer so marks don't interfere with the design.
        Uses lxml -- does NOT require Inkscape binary.

        Args:
            input_svg: Path to the source SVG file.
            output_svg: Path for the output. If None, generates
                *-cropmarks.svg alongside the original.

        Returns:
            Absolute path to the SVG with crop marks.

        Raises:
            InkscapeError: If the operation fails.
        """
        input_svg = os.path.abspath(input_svg)
        self._require_file(input_svg)

        if output_svg is None:
            stem = Path(input_svg).stem
            parent = Path(input_svg).parent
            output_svg = str(parent / f"{stem}-cropmarks.svg")

        output_svg = os.path.abspath(output_svg)

        try:
            tree = etree.parse(input_svg)
            root = tree.getroot()
        except etree.XMLSyntaxError as exc:
            raise InkscapeError(f"Cannot parse SVG for crop marks: {exc}") from exc

        viewbox_str = root.get("viewBox") or root.get("viewbox")
        if not viewbox_str:
            raise InkscapeError(
                "SVG has no viewBox. Cannot add crop marks without dimensions."
            )

        parts = viewbox_str.strip().replace(",", " ").split()
        if len(parts) != 4:
            raise InkscapeError(f"Invalid viewBox: {viewbox_str}")

        vb_x, vb_y, vb_w, vb_h = [float(p) for p in parts]

        SVG_NS = "http://www.w3.org/2000/svg"

        # Crop mark dimensions (in user units / px)
        MARK_LENGTH = 10.0  # Length of each crop mark line
        MARK_OFFSET = 3.0   # Gap between mark and document edge
        MARK_STROKE = 0.5   # Stroke width of marks

        # Extend viewBox to accommodate marks
        ext = MARK_LENGTH + MARK_OFFSET + 2
        new_vb_x = vb_x - ext
        new_vb_y = vb_y - ext
        new_vb_w = vb_w + 2 * ext
        new_vb_h = vb_h + 2 * ext

        root.set("viewBox", f"{new_vb_x} {new_vb_y} {new_vb_w} {new_vb_h}")

        # Update width/height if present
        width = root.get("width")
        height = root.get("height")
        if width:
            w_val, w_unit = self._parse_dimension(width)
            root.set("width", f"{w_val + 2 * ext}{w_unit}")
        if height:
            h_val, h_unit = self._parse_dimension(height)
            root.set("height", f"{h_val + 2 * ext}{h_unit}")

        # Create crop marks layer
        ns_prefix = f"{{{SVG_NS}}}" if SVG_NS in root.tag else ""
        marks_group = etree.SubElement(root, f"{ns_prefix}g")
        marks_group.set("id", "crop-marks")
        marks_group.set("style", f"stroke:#000000;stroke-width:{MARK_STROKE};fill:none")

        # Corner crop marks (4 corners, 2 lines each)
        corners = [
            (vb_x, vb_y),                       # top-left
            (vb_x + vb_w, vb_y),                # top-right
            (vb_x, vb_y + vb_h),                # bottom-left
            (vb_x + vb_w, vb_y + vb_h),         # bottom-right
        ]

        for cx, cy in corners:
            # Horizontal mark
            hx_start = cx - MARK_OFFSET - MARK_LENGTH if cx == vb_x else cx + MARK_OFFSET
            hx_end = hx_start + MARK_LENGTH
            line_h = etree.SubElement(marks_group, f"{ns_prefix}line")
            line_h.set("x1", f"{hx_start}")
            line_h.set("y1", f"{cy}")
            line_h.set("x2", f"{hx_end}")
            line_h.set("y2", f"{cy}")

            # Vertical mark
            vy_start = cy - MARK_OFFSET - MARK_LENGTH if cy == vb_y else cy + MARK_OFFSET
            vy_end = vy_start + MARK_LENGTH
            line_v = etree.SubElement(marks_group, f"{ns_prefix}line")
            line_v.set("x1", f"{cx}")
            line_v.set("y1", f"{vy_start}")
            line_v.set("x2", f"{cx}")
            line_v.set("y2", f"{vy_end}")

        # Center registration marks (top, bottom, left, right midpoints)
        center_x = vb_x + vb_w / 2
        center_y = vb_y + vb_h / 2
        reg_size = 4.0

        midpoints = [
            (center_x, vb_y, True),                    # top center
            (center_x, vb_y + vb_h, True),             # bottom center
            (vb_x, center_y, False),                    # left center
            (vb_x + vb_w, center_y, False),             # right center
        ]

        for mx, my, is_vertical_edge in midpoints:
            # Cross mark
            if is_vertical_edge:
                offset = -MARK_OFFSET - reg_size if my == vb_y else MARK_OFFSET
                # Vertical line of cross
                line = etree.SubElement(marks_group, f"{ns_prefix}line")
                line.set("x1", f"{mx}")
                line.set("y1", f"{my + offset}")
                line.set("x2", f"{mx}")
                line.set("y2", f"{my + offset + reg_size}")
                # Horizontal line of cross
                line = etree.SubElement(marks_group, f"{ns_prefix}line")
                line.set("x1", f"{mx - reg_size / 2}")
                line.set("y1", f"{my + offset + reg_size / 2}")
                line.set("x2", f"{mx + reg_size / 2}")
                line.set("y2", f"{my + offset + reg_size / 2}")
            else:
                offset = -MARK_OFFSET - reg_size if mx == vb_x else MARK_OFFSET
                # Horizontal line of cross
                line = etree.SubElement(marks_group, f"{ns_prefix}line")
                line.set("x1", f"{mx + offset}")
                line.set("y1", f"{my}")
                line.set("x2", f"{mx + offset + reg_size}")
                line.set("y2", f"{my}")
                # Vertical line of cross
                line = etree.SubElement(marks_group, f"{ns_prefix}line")
                line.set("x1", f"{mx + offset + reg_size / 2}")
                line.set("y1", f"{my - reg_size / 2}")
                line.set("x2", f"{mx + offset + reg_size / 2}")
                line.set("y2", f"{my + reg_size / 2}")

        # Write output
        tree.write(
            output_svg,
            xml_declaration=True,
            encoding="utf-8",
            pretty_print=True,
        )

        return output_svg

    def apply_filter(
        self,
        input_svg: str,
        output_svg: str | None = None,
        filter_name: str = "blur",
    ) -> str:
        """
        Apply an Inkscape filter effect.

        Common filters: blur, drop-shadow, bevel, emboss.

        Args:
            input_svg: Path to the source SVG.
            output_svg: Path for the output. If None, generates
                *-filtered.svg alongside the original.
            filter_name: Name of the filter to apply.

        Returns:
            Absolute path to the filtered SVG.

        Raises:
            InkscapeNotFoundError: If Inkscape is not available.
            InkscapeError: If the operation fails.
        """
        self._require_available()
        input_svg = os.path.abspath(input_svg)
        self._require_file(input_svg)
        self._sanitize_path(input_svg)

        if output_svg is None:
            stem = Path(input_svg).stem
            parent = Path(input_svg).parent
            output_svg = str(parent / f"{stem}-filtered.svg")

        output_svg = os.path.abspath(output_svg)
        self._sanitize_path(output_svg)

        # Map friendly filter names to Inkscape filter IDs
        filter_map = {
            "blur": "org.inkscape.blurs.basic.gaussianblur",
            "drop-shadow": "org.inkscape.drop-shadow",
            "bevel": "org.inkscape.bevel.bevel",
            "emboss": "org.inkscape.bevel.emboss",
        }

        filter_id = filter_map.get(filter_name, filter_name)
        # Sanitize filter_id since it's injected into the action string
        self._sanitize_path(filter_id)

        actions = [
            f"file-open:{input_svg}",
            "select-all",
            f"object-set-attribute:style, filter:url(#{filter_id})",
            f"export-filename:{output_svg}",
            "export-type:svg",
            "export-do",
        ]

        self._run_actions(actions, timeout=self.DEFAULT_TIMEOUT)

        if not Path(output_svg).exists():
            raise InkscapeError(
                f"Filter application failed: output not created at {output_svg}"
            )

        return output_svg

    # ------------------------------------------------------------------
    # Convenience: combined print-ready export
    # ------------------------------------------------------------------

    def export_print_ready(
        self,
        input_svg: str,
        output_dir: str | None = None,
        bleed_mm: float = 3.0,
        text_to_path: bool = True,
        cmyk: bool = True,
        export_eps: bool = False,
        color_profile: str | None = None,
    ) -> dict[str, str]:
        """
        Produce a full set of print-ready outputs from a source SVG.

        Performs the following steps (each conditional):
        1. Add bleed and crop marks (lxml, no Inkscape needed)
        2. Convert text to paths (requires Inkscape)
        3. Export CMYK PDF (requires Inkscape)
        4. Export EPS (requires Inkscape)

        Args:
            input_svg: Path to the source SVG.
            output_dir: Directory for outputs. If None, uses same directory
                as the input SVG.
            bleed_mm: Bleed area in mm. Set to 0 to skip bleed.
            text_to_path: If True, create an outlined SVG version.
            cmyk: If True, export a CMYK PDF.
            export_eps: If True, export EPS.
            color_profile: Optional ICC profile path for CMYK conversion.

        Returns:
            Dict mapping output type to file path:
                - "bleed_svg": path to SVG with bleed (if bleed_mm > 0)
                - "outlined_svg": path to text-to-path SVG (if text_to_path)
                - "cmyk_pdf": path to CMYK PDF (if cmyk)
                - "eps": path to EPS file (if export_eps)

        Raises:
            InkscapeError: If a required operation fails.
        """
        input_svg = os.path.abspath(input_svg)
        self._require_file(input_svg)

        if output_dir is None:
            output_dir = str(Path(input_svg).parent)
        os.makedirs(output_dir, exist_ok=True)

        stem = Path(input_svg).stem
        results: dict[str, str] = {}

        # The SVG we'll use for subsequent operations (may have bleed added)
        working_svg = input_svg

        # Step 1: Bleed and crop marks (lxml-based, no Inkscape needed)
        if bleed_mm > 0:
            bleed_path = os.path.join(output_dir, f"{stem}-bleed.svg")
            working_svg = self.add_bleed(input_svg, bleed_path, bleed_mm)
            results["bleed_svg"] = working_svg

        # Steps 2-4 require Inkscape
        if not self._available:
            missing_ops = []
            if text_to_path:
                missing_ops.append("text-to-path")
            if cmyk:
                missing_ops.append("CMYK PDF")
            if export_eps:
                missing_ops.append("EPS")
            if missing_ops:
                print(
                    f"Warning: Inkscape not available. Skipping: "
                    f"{', '.join(missing_ops)}. "
                    f"Install via: brew install --cask inkscape"
                )
            return results

        # Step 2: Text to path
        if text_to_path:
            try:
                outlined_path = os.path.join(output_dir, f"{stem}-outlined.svg")
                results["outlined_svg"] = self.text_to_path(
                    working_svg, outlined_path
                )
            except InkscapeError as exc:
                print(f"Warning: text-to-path failed: {exc}")

        # Step 3: CMYK PDF
        if cmyk:
            try:
                pdf_path = os.path.join(output_dir, f"{stem}-cmyk.pdf")
                results["cmyk_pdf"] = self.export_cmyk_pdf(
                    working_svg, pdf_path, color_profile
                )
            except InkscapeError as exc:
                print(f"Warning: CMYK PDF export failed: {exc}")

        # Step 4: EPS
        if export_eps:
            try:
                eps_path = os.path.join(output_dir, f"{stem}.eps")
                results["eps"] = self.export_eps(working_svg, eps_path)
            except InkscapeError as exc:
                print(f"Warning: EPS export failed: {exc}")

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _discover_binary(self) -> str | None:
        """Search for the Inkscape binary in standard locations."""
        # Check known macOS paths first
        for path in self._SEARCH_PATHS:
            if Path(path).exists() and os.access(path, os.X_OK):
                return path

        # Fall back to PATH lookup
        found = shutil.which("inkscape")
        return found

    def _check_version(self) -> str:
        """
        Verify that the discovered Inkscape meets the minimum version.

        Returns:
            Version string (e.g., "1.4.3").

        Raises:
            InkscapeNotFoundError: If version check fails or version is too old.
        """
        if not self._binary_path:
            raise InkscapeNotFoundError(
                "Inkscape binary not found. Install via: brew install --cask inkscape"
            )

        try:
            result = subprocess.run(
                [self._binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            raise InkscapeNotFoundError(
                f"Cannot run Inkscape version check: {exc}. "
                "Install via: brew install --cask inkscape"
            ) from exc

        # Parse version from output like "Inkscape 1.4.3 (0d15f75, 2025-12-25)"
        version_match = re.search(r"Inkscape\s+(\d+\.\d+(?:\.\d+)?)", result.stdout)
        if not version_match:
            raise InkscapeNotFoundError(
                f"Cannot parse Inkscape version from: {result.stdout.strip()}"
            )

        version = version_match.group(1)

        # Compare versions
        if not self._version_gte(version, self.MINIMUM_VERSION):
            raise InkscapeNotFoundError(
                f"Inkscape version {version} is below minimum {self.MINIMUM_VERSION}. "
                f"Update via: brew upgrade --cask inkscape"
            )

        return version

    def _run_actions(
        self,
        actions: list[str],
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """
        Execute Inkscape with --actions parameter.

        Args:
            actions: List of Inkscape action strings.
            timeout: Timeout in seconds (default: DEFAULT_TIMEOUT).

        Returns:
            The completed process.

        Raises:
            InkscapeNotFoundError: If Inkscape is not available.
            InkscapeError: If the command fails or times out.
        """
        self._require_available()

        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT

        actions_str = ";".join(actions)
        cmd = [self._binary_path, "--batch-process", f"--actions={actions_str}"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise InkscapeError(
                f"Inkscape timed out after {timeout}s. The SVG may be too "
                f"complex or Inkscape may be hung. Actions: {actions_str[:200]}"
            ) from exc
        except FileNotFoundError as exc:
            raise InkscapeNotFoundError(
                f"Inkscape binary not found at {self._binary_path}. "
                "Install via: brew install --cask inkscape"
            ) from exc
        except OSError as exc:
            raise InkscapeError(
                f"Failed to execute Inkscape: {exc}"
            ) from exc

        if result.returncode != 0:
            stderr = result.stderr.strip()
            # Inkscape often writes warnings to stderr that aren't fatal
            # Only fail on actual errors
            if stderr and any(
                keyword in stderr.lower()
                for keyword in ["error", "failed", "cannot", "unable"]
            ):
                raise InkscapeError(
                    f"Inkscape returned error (exit {result.returncode}): {stderr[:500]}"
                )

        return result

    def _require_available(self) -> None:
        """Raise InkscapeNotFoundError if Inkscape is not available."""
        if not self._available:
            raise InkscapeNotFoundError(
                "Inkscape is not available. This operation requires Inkscape >= "
                f"{self.MINIMUM_VERSION}. Install via: brew install --cask inkscape"
            )

    @staticmethod
    def _require_file(path: str) -> None:
        """Raise InkscapeError if the file does not exist."""
        if not Path(path).exists():
            raise InkscapeError(f"Input file not found: {path}")

    @staticmethod
    def _sanitize_path(path: str) -> str:
        """
        Sanitize a file path for use in Inkscape action strings.

        Inkscape uses semicolons as action separators in --actions mode.
        A filename containing a semicolon would inject arbitrary Inkscape
        actions. This method rejects paths with dangerous characters.

        Raises:
            InkscapeError: If the path contains characters unsafe for
                Inkscape action strings.
        """
        dangerous_chars = {";", "|", "`", "$", "\n", "\r"}
        for ch in dangerous_chars:
            if ch in path:
                raise InkscapeError(
                    f"File path contains unsafe character {ch!r} which would "
                    f"be interpreted as an Inkscape action separator. "
                    f"Rename the file to remove special characters: {path}"
                )
        return path

    @staticmethod
    def _version_gte(version: str, minimum: str) -> bool:
        """Check if version >= minimum using tuple comparison."""
        def to_tuple(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.split("."))
        return to_tuple(version) >= to_tuple(minimum)

    @staticmethod
    def _parse_dimension(dim_str: str) -> tuple[float, str]:
        """
        Parse a CSS dimension string like '100mm' or '500px' into (value, unit).

        Returns (value, unit) where unit defaults to 'px' if not specified.
        """
        match = re.match(r"^([\d.]+)\s*([a-z%]*)$", dim_str.strip())
        if not match:
            return 0.0, "px"
        value = float(match.group(1))
        unit = match.group(2) or "px"
        return value, unit

    def _apply_color_profile(self, svg_path: str, profile_path: str) -> str:
        """
        Create a temporary SVG with the ICC color profile embedded.

        Adds a color-profile declaration to the SVG defs so Inkscape
        can use it for CMYK conversion.

        Returns:
            Path to the temporary SVG with the profile applied.
        """
        try:
            tree = etree.parse(svg_path)
            root = tree.getroot()
        except etree.XMLSyntaxError as exc:
            raise InkscapeError(
                f"Cannot parse SVG for color profile injection: {exc}"
            ) from exc

        SVG_NS = "http://www.w3.org/2000/svg"
        ns_prefix = f"{{{SVG_NS}}}" if SVG_NS in root.tag else ""

        # Find or create <defs>
        defs = root.find(f"{ns_prefix}defs")
        if defs is None:
            defs = etree.SubElement(root, f"{ns_prefix}defs")
            root.insert(0, defs)

        # Add color-profile element
        cp = etree.SubElement(defs, f"{ns_prefix}color-profile")
        cp.set("name", "CMYK")
        cp.set(f"{{{SVG_NS}}}rendering-intent", "perceptual")
        cp.set(
            f"{{http://www.w3.org/1999/xlink}}href",
            f"file://{os.path.abspath(profile_path)}",
        )

        # Write to temp file
        temp_path = svg_path.replace(".svg", "-cmyk-temp.svg")
        tree.write(temp_path, xml_declaration=True, encoding="utf-8")

        return temp_path

    @staticmethod
    def _add_crop_marks_to_tree(
        root: etree._Element,
        vb_x: float,
        vb_y: float,
        vb_w: float,
        vb_h: float,
        bleed_px: float,
        svg_ns: str,
    ) -> None:
        """Add crop marks to an SVG tree at the original document boundaries."""
        ns_prefix = f"{{{svg_ns}}}" if svg_ns in root.tag else ""

        MARK_LENGTH = 8.0
        MARK_GAP = 2.0
        MARK_STROKE = 0.5

        marks_group = etree.SubElement(root, f"{ns_prefix}g")
        marks_group.set("id", "bleed-crop-marks")
        marks_group.set(
            "style",
            f"stroke:#000000;stroke-width:{MARK_STROKE};fill:none"
        )
        # Offset marks to account for the bleed wrapper translate
        marks_group.set("transform", f"translate({bleed_px}, {bleed_px})")

        # Corners of the original document
        corners = [
            (vb_x, vb_y),
            (vb_x + vb_w, vb_y),
            (vb_x, vb_y + vb_h),
            (vb_x + vb_w, vb_y + vb_h),
        ]

        for cx, cy in corners:
            # Horizontal crop mark
            if cx == vb_x:
                hx1 = cx - MARK_GAP - MARK_LENGTH
                hx2 = cx - MARK_GAP
            else:
                hx1 = cx + MARK_GAP
                hx2 = cx + MARK_GAP + MARK_LENGTH

            line = etree.SubElement(marks_group, f"{ns_prefix}line")
            line.set("x1", f"{hx1}")
            line.set("y1", f"{cy}")
            line.set("x2", f"{hx2}")
            line.set("y2", f"{cy}")

            # Vertical crop mark
            if cy == vb_y:
                vy1 = cy - MARK_GAP - MARK_LENGTH
                vy2 = cy - MARK_GAP
            else:
                vy1 = cy + MARK_GAP
                vy2 = cy + MARK_GAP + MARK_LENGTH

            line = etree.SubElement(marks_group, f"{ns_prefix}line")
            line.set("x1", f"{cx}")
            line.set("y1", f"{vy1}")
            line.set("x2", f"{cx}")
            line.set("y2", f"{vy2}")


# ---------------------------------------------------------------------------
# Module-level convenience: singleton instance
# ---------------------------------------------------------------------------

_default_instance: InkscapeCLI | None = None


def get_inkscape() -> InkscapeCLI:
    """
    Get or create the module-level InkscapeCLI singleton.

    Returns:
        An InkscapeCLI instance (may or may not be available depending
        on whether Inkscape is installed).
    """
    global _default_instance
    if _default_instance is None:
        _default_instance = InkscapeCLI()
    return _default_instance
