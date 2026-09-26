"""
Deterministic SVG Validator for the Media Workflow Engine.

Performs pass/fail quality checks on generated SVG files to ensure they
meet the deliverable specification:
  - Valid XML/SVG structure
  - Has viewBox attribute
  - Has organized <g> groups with id attributes
  - Text is <text> elements (not baked as <path>)
  - File size within target
  - Path count reasonable (not over-anchored)
  - Layer naming follows convention

Returns structured results with actionable error messages.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from lxml import etree


# SVG namespace
SVG_NS = "http://www.w3.org/2000/svg"
NSMAP = {"svg": SVG_NS}


class ValidationResult:
    """Container for a single validation check result."""

    def __init__(self, check_name: str, passed: bool, message: str = "") -> None:
        self.check_name = check_name
        self.passed = passed
        self.message = message

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        msg = f": {self.message}" if self.message else ""
        return f"[{status}] {self.check_name}{msg}"


def validate_svg(
    svg_path: str,
    config: dict[str, Any] | None = None,
) -> tuple[bool, list[ValidationResult]]:
    """
    Run all deterministic validation checks on an SVG file.

    Args:
        svg_path: Path to the SVG file to validate.
        config: Optional resolved workflow config dict for threshold overrides.

    Returns:
        Tuple of (all_passed, list_of_results).
    """
    config = config or {}
    vector_cfg = config.get("vector", {})
    results: list[ValidationResult] = []

    path = Path(svg_path)

    # 1. File exists
    if not path.exists():
        results.append(ValidationResult(
            "file_exists", False, f"SVG file does not exist: {svg_path}"
        ))
        return False, results
    results.append(ValidationResult("file_exists", True))

    # 2. File not empty
    file_size = path.stat().st_size
    if file_size == 0:
        results.append(ValidationResult(
            "file_not_empty", False, "SVG file is empty (0 bytes)"
        ))
        return False, results
    results.append(ValidationResult("file_not_empty", True))

    # 3. Valid XML structure
    try:
        tree = etree.parse(str(path))
        root = tree.getroot()
    except etree.XMLSyntaxError as exc:
        results.append(ValidationResult(
            "xml_valid", False, f"Invalid XML: {exc}"
        ))
        return False, results
    results.append(ValidationResult("xml_valid", True))

    # 4. SVG root element
    tag = etree.QName(root.tag).localname if "}" in root.tag else root.tag
    if tag != "svg":
        results.append(ValidationResult(
            "svg_root", False,
            f"Root element must be <svg>, got <{tag}>"
        ))
        return False, results
    results.append(ValidationResult("svg_root", True))

    # 5. Has viewBox
    viewbox = root.get("viewBox") or root.get("viewbox")
    if not viewbox:
        results.append(ValidationResult(
            "svg_has_viewbox", False,
            "Missing viewBox attribute on <svg> element. "
            "Add viewBox='0 0 width height' for proper scaling."
        ))
    else:
        # Validate viewBox format (four numbers)
        parts = viewbox.strip().replace(",", " ").split()
        if len(parts) != 4:
            results.append(ValidationResult(
                "svg_has_viewbox", False,
                f"viewBox must have 4 values (minX minY width height), got: '{viewbox}'"
            ))
        else:
            try:
                [float(p) for p in parts]
                results.append(ValidationResult("svg_has_viewbox", True))
            except ValueError:
                results.append(ValidationResult(
                    "svg_has_viewbox", False,
                    f"viewBox contains non-numeric values: '{viewbox}'"
                ))

    # 6. Has organized <g> groups with id attributes
    g_elements = root.xpath("//svg:g[@id]", namespaces=NSMAP)
    # Also check without namespace (svgwrite may not always use namespace prefix)
    if not g_elements:
        g_elements = root.xpath("//*[local-name()='g'][@id]")

    min_groups = 1
    if len(g_elements) < min_groups:
        results.append(ValidationResult(
            "svg_has_layers", False,
            f"Expected at least {min_groups} <g> group(s) with id attribute, "
            f"found {len(g_elements)}. Organize elements into semantic groups "
            f"like <g id='icon-home'> or <g id='logo-mark'>."
        ))
    else:
        group_ids = [g.get("id") for g in g_elements]
        results.append(ValidationResult(
            "svg_has_layers", True,
            f"Found {len(g_elements)} named group(s): {', '.join(group_ids[:10])}"
        ))

    # 7. Text editability: check that text content uses <text> elements
    text_elements = root.xpath("//*[local-name()='text']")
    # Check for text-as-path anti-pattern: paths with very many control points
    # that look like text glyphs (heuristic)
    path_elements = root.xpath("//*[local-name()='path']")
    suspicious_paths = 0
    for path_el in path_elements:
        d = path_el.get("d", "")
        # Count the number of commands in the path
        commands = re.findall(r"[MLHVCSQTAZmlhvcsqtaz]", d)
        if len(commands) > 50:
            suspicious_paths += 1

    if text_elements:
        results.append(ValidationResult(
            "svg_text_editable", True,
            f"Found {len(text_elements)} <text> element(s). Text remains editable."
        ))
    else:
        # No text elements found -- this might be OK for icon-only SVGs
        # Only warn if there are suspicious paths that look like text
        if suspicious_paths > 0:
            results.append(ValidationResult(
                "svg_text_editable", False,
                f"No <text> elements found, but {suspicious_paths} path(s) with 50+ commands "
                f"detected (possible text baked as paths). Use <text> elements for editable text."
            ))
        else:
            results.append(ValidationResult(
                "svg_text_editable", True,
                "No <text> elements (may be icon-only SVG). No text-as-path detected."
            ))

    # 8. File size check
    file_size_limit_kb = vector_cfg.get("file_size_limit_kb", 500)
    file_size_kb = file_size / 1024
    if file_size_kb > file_size_limit_kb:
        results.append(ValidationResult(
            "svg_file_size", False,
            f"File size {file_size_kb:.1f}KB exceeds limit of {file_size_limit_kb}KB. "
            f"Simplify paths or reduce element count."
        ))
    else:
        results.append(ValidationResult(
            "svg_file_size", True,
            f"File size: {file_size_kb:.1f}KB (limit: {file_size_limit_kb}KB)"
        ))

    # 9. Path count check (not over-anchored)
    max_paths = vector_cfg.get("max_path_count", 500)
    total_paths = len(path_elements)
    if total_paths > max_paths:
        results.append(ValidationResult(
            "svg_path_count", False,
            f"Too many <path> elements: {total_paths} (max: {max_paths}). "
            f"Simplify or merge paths to reduce complexity."
        ))
    else:
        results.append(ValidationResult(
            "svg_path_count", True,
            f"Path count: {total_paths} (max: {max_paths})"
        ))

    # 10. Layer naming convention
    naming_issues: list[str] = []
    for g in g_elements:
        gid = g.get("id", "")
        # Check naming convention: should be kebab-case or snake_case
        if not re.match(r"^[a-z][a-z0-9_-]*$", gid):
            naming_issues.append(gid)

    if naming_issues:
        results.append(ValidationResult(
            "svg_layer_naming", False,
            f"Group id(s) not following naming convention (lowercase, kebab/snake_case): "
            f"{', '.join(naming_issues[:5])}. Use ids like 'icon-home' or 'logo_mark'."
        ))
    else:
        results.append(ValidationResult("svg_layer_naming", True))

    # Aggregate pass/fail
    all_passed = all(r.passed for r in results)
    return all_passed, results


def validate_svg_quick(svg_path: str) -> tuple[bool, list[str]]:
    """
    Quick validation that returns (passed, failure_messages).

    Simplified interface matching the evaluator's hard_check return signature.
    """
    passed, results = validate_svg(svg_path)
    failures = [r.message for r in results if not r.passed]
    return passed, failures


# ---------------------------------------------------------------------------
# PNG dimension verification
# ---------------------------------------------------------------------------

def check_png_dimensions(
    png_path: str,
    expected_width: int,
    expected_height: int,
    tolerance: int = 2,
) -> ValidationResult:
    """
    Verify that a PNG file matches expected dimensions.

    Reads the PNG IHDR chunk to extract width and height without requiring
    Pillow. Allows a small pixel tolerance for rounding differences in
    cairosvg rendering.

    Args:
        png_path: Path to the PNG file to check.
        expected_width: Expected pixel width.
        expected_height: Expected pixel height.
        tolerance: Allowed pixel deviation per dimension (default 2px).

    Returns:
        A ValidationResult indicating pass/fail.
    """
    import struct

    path = Path(png_path)
    if not path.exists():
        return ValidationResult(
            "png_dimensions", False,
            f"PNG file does not exist: {png_path}"
        )

    try:
        with open(path, "rb") as f:
            header = f.read(24)
    except OSError as exc:
        return ValidationResult(
            "png_dimensions", False, f"Cannot read PNG: {exc}"
        )

    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return ValidationResult(
            "png_dimensions", False,
            f"Not a valid PNG file: {png_path}"
        )

    actual_width = struct.unpack(">I", header[16:20])[0]
    actual_height = struct.unpack(">I", header[20:24])[0]

    width_ok = abs(actual_width - expected_width) <= tolerance
    height_ok = abs(actual_height - expected_height) <= tolerance

    if width_ok and height_ok:
        return ValidationResult(
            "png_dimensions", True,
            f"PNG dimensions match: {actual_width}x{actual_height} "
            f"(expected {expected_width}x{expected_height})"
        )
    else:
        return ValidationResult(
            "png_dimensions", False,
            f"PNG dimension mismatch: {actual_width}x{actual_height} "
            f"(expected {expected_width}x{expected_height}, "
            f"tolerance: +/-{tolerance}px)"
        )


def check_multi_resolution(
    png_paths: list[str],
    grid_size: str,
    tolerance: int = 4,
) -> list[dict[str, Any]]:
    """
    Verify icon multi-resolution PNG exports match expected dimensions.

    For a grid_size of "24x24", expects:
      - 1x PNG: viewBox-derived width/height (depends on icon count)
      - 2x PNG: double the 1x dimensions
      - 3x PNG: triple the 1x dimensions

    Since the SVG viewBox determines the base dimensions (not just grid_size),
    this checks relative scaling between exports rather than absolute sizes.

    Args:
        png_paths: List of PNG file paths (1x, @2x, @3x in order).
        grid_size: Grid size string (e.g., "24x24").
        tolerance: Allowed pixel deviation per dimension.

    Returns:
        List of check result dicts with keys: scale, path, passed, message.
    """
    import struct

    results: list[dict[str, Any]] = []

    if not png_paths:
        return results

    def _read_png_dims(p: str) -> tuple[int, int] | None:
        try:
            with open(p, "rb") as f:
                header = f.read(24)
            if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
                return None
            w = struct.unpack(">I", header[16:20])[0]
            h = struct.unpack(">I", header[20:24])[0]
            return w, h
        except OSError:
            return None

    # Read the 1x dimensions as the baseline
    base_dims = _read_png_dims(png_paths[0])
    if base_dims is None:
        results.append({
            "scale": "1x",
            "path": png_paths[0],
            "passed": False,
            "message": f"Cannot read 1x PNG dimensions: {png_paths[0]}",
        })
        return results

    base_w, base_h = base_dims
    results.append({
        "scale": "1x",
        "path": png_paths[0],
        "passed": True,
        "message": f"1x: {base_w}x{base_h}",
    })

    # Check each subsequent scale
    for i, png_path in enumerate(png_paths[1:], start=2):
        expected_w = base_w * i
        expected_h = base_h * i

        dims = _read_png_dims(png_path)
        if dims is None:
            results.append({
                "scale": f"{i}x",
                "path": png_path,
                "passed": False,
                "message": f"Cannot read {i}x PNG: {png_path}",
            })
            continue

        actual_w, actual_h = dims
        w_ok = abs(actual_w - expected_w) <= tolerance
        h_ok = abs(actual_h - expected_h) <= tolerance

        if w_ok and h_ok:
            results.append({
                "scale": f"{i}x",
                "path": png_path,
                "passed": True,
                "message": f"{i}x: {actual_w}x{actual_h} (expected {expected_w}x{expected_h})",
            })
        else:
            results.append({
                "scale": f"{i}x",
                "path": png_path,
                "passed": False,
                "message": (
                    f"{i}x dimension mismatch: {actual_w}x{actual_h} "
                    f"(expected {expected_w}x{expected_h})"
                ),
            })

    return results
