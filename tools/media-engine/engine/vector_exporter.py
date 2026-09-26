"""
Multi-Format Vector Exporter for the Media Workflow Engine.

Handles exporting SVG files to other formats using cairosvg:
  - SVG -> PNG preview (for agent visual evaluation)
  - SVG -> PDF (RGB, standard export)
  - Multi-resolution PNG export (1x, 2x, 3x for icons)

Phase 3 additions (Inkscape CLI integration):
  - SVG -> EPS (via Inkscape CLI, for legacy print workflows)
  - SVG -> outlined SVG (text-to-path via Inkscape CLI)
  - SVG -> print-ready PDF (CMYK, bleeds, crop marks via Inkscape CLI)
  - Print-ready bundle (combined bleed + outline + CMYK + EPS)

All Phase 3 exports gracefully degrade when Inkscape is not installed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import cairosvg


class ExportError(Exception):
    """Raised when an export operation fails."""


def export_all(
    svg_path: str,
    config: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """
    Export an SVG file to all configured formats.

    Reads the export_formats from config (defaults to svg, pdf, png).
    Returns a dict mapping format names to lists of exported file paths.

    Args:
        svg_path: Path to the source SVG file.
        config: Resolved workflow config dict.

    Returns:
        Dict mapping format -> list of exported file paths.
        The "svg" entry always contains the original SVG path.
    """
    config = config or {}
    vector_cfg = config.get("vector", {})
    export_formats = vector_cfg.get("export_formats", ["svg", "pdf", "png"])
    if isinstance(export_formats, str):
        export_formats = [export_formats]

    svg_path = os.path.abspath(svg_path)
    results: dict[str, list[str]] = {}

    if not Path(svg_path).exists():
        raise ExportError(f"Source SVG not found: {svg_path}")

    # SVG is always available (it's the source)
    if "svg" in export_formats:
        results["svg"] = [svg_path]

    # PDF export
    if "pdf" in export_formats:
        try:
            pdf_paths = export_to_pdf(svg_path)
            results["pdf"] = pdf_paths
        except ExportError as exc:
            results["pdf"] = []
            print(f"Warning: PDF export failed: {exc}")

    # EPS export (Phase 3 -- requires Inkscape)
    if "eps" in export_formats:
        try:
            eps_paths = export_eps(svg_path)
            results["eps"] = eps_paths
        except ExportError as exc:
            results["eps"] = []
            print(f"Warning: EPS export failed: {exc}")

    # PNG export (multi-resolution for icons)
    if "png" in export_formats:
        try:
            # Determine if multi-resolution based on media subtype
            grid_size = vector_cfg.get("grid_size", "")
            icon_mode = "icon" in str(config.get("name", "")).lower() or bool(grid_size)

            if icon_mode:
                png_paths = export_to_png_multi(svg_path, scales=[1, 2, 3])
            else:
                png_paths = export_to_png(svg_path)

            results["png"] = png_paths
        except ExportError as exc:
            results["png"] = []
            print(f"Warning: PNG export failed: {exc}")

    # Print-ready exports (Phase 3 -- conditional on config flags)
    print_cfg = vector_cfg.get("print", {})
    if print_cfg.get("print_ready") or config.get("_print_ready"):
        try:
            print_results = export_print_ready(svg_path, config)
            results["print"] = list(print_results.values())
        except ExportError as exc:
            results["print"] = []
            print(f"Warning: Print-ready export failed: {exc}")

    return results


def export_to_pdf(svg_path: str, output_path: str | None = None) -> list[str]:
    """
    Export an SVG file to PDF.

    Args:
        svg_path: Path to the source SVG.
        output_path: Optional explicit output path. If None, uses
                     the SVG path with .pdf extension.

    Returns:
        List containing the PDF file path.

    Raises:
        ExportError: If the conversion fails.
    """
    svg_path = os.path.abspath(svg_path)
    if output_path is None:
        output_path = str(Path(svg_path).with_suffix(".pdf"))

    try:
        cairosvg.svg2pdf(
            url=svg_path,
            write_to=output_path,
        )
    except Exception as exc:
        raise ExportError(f"SVG to PDF conversion failed: {exc}") from exc

    if not Path(output_path).exists():
        raise ExportError(f"PDF output file not created: {output_path}")

    return [os.path.abspath(output_path)]


def export_to_png(
    svg_path: str,
    output_path: str | None = None,
    scale: float = 2.0,
    dpi: int | None = None,
) -> list[str]:
    """
    Export an SVG file to PNG at the specified scale.

    Args:
        svg_path: Path to the source SVG.
        output_path: Optional explicit output path. If None, uses
                     the SVG path with .png extension.
        scale: Scale factor (2.0 = 2x resolution, good for previews).
        dpi: Optional DPI override (takes precedence over scale).

    Returns:
        List containing the PNG file path.

    Raises:
        ExportError: If the conversion fails.
    """
    svg_path = os.path.abspath(svg_path)
    if output_path is None:
        output_path = str(Path(svg_path).with_suffix(".png"))

    try:
        kwargs: dict[str, Any] = {
            "url": svg_path,
            "write_to": output_path,
        }
        if dpi:
            kwargs["dpi"] = dpi
        else:
            kwargs["scale"] = scale

        cairosvg.svg2png(**kwargs)
    except Exception as exc:
        raise ExportError(f"SVG to PNG conversion failed: {exc}") from exc

    if not Path(output_path).exists():
        raise ExportError(f"PNG output file not created: {output_path}")

    return [os.path.abspath(output_path)]


def export_to_png_multi(
    svg_path: str,
    scales: list[int] | None = None,
) -> list[str]:
    """
    Export an SVG file to multiple PNG resolutions (1x, 2x, 3x).

    Useful for icon sets that need multiple sizes for different DPIs.

    Args:
        svg_path: Path to the source SVG.
        scales: List of integer scale factors. Defaults to [1, 2, 3].

    Returns:
        List of PNG file paths, one per scale.

    Raises:
        ExportError: If any conversion fails.
    """
    if scales is None:
        scales = [1, 2, 3]

    svg_path = os.path.abspath(svg_path)
    stem = Path(svg_path).stem
    parent = Path(svg_path).parent
    results: list[str] = []

    for scale in scales:
        suffix = f"@{scale}x" if scale > 1 else ""
        output_path = str(parent / f"{stem}{suffix}.png")

        try:
            cairosvg.svg2png(
                url=svg_path,
                write_to=output_path,
                scale=float(scale),
            )
            results.append(os.path.abspath(output_path))
        except Exception as exc:
            raise ExportError(
                f"SVG to PNG @{scale}x conversion failed: {exc}"
            ) from exc

    return results


# ---------------------------------------------------------------------------
# Phase 3: Inkscape-powered exports
# ---------------------------------------------------------------------------


def export_eps(
    svg_path: str,
    output_path: str | None = None,
) -> list[str]:
    """
    Export an SVG file to EPS format via Inkscape CLI (Phase 3).

    Requires Inkscape >= 1.3 to be installed. Returns a clear error
    message with installation instructions if Inkscape is not available.

    Args:
        svg_path: Path to the source SVG.
        output_path: Optional explicit output path. If None, uses
                     the SVG path with .eps extension.

    Returns:
        List containing the EPS file path.

    Raises:
        ExportError: If the conversion fails or Inkscape is not available.
    """
    from engine.inkscape_cli import get_inkscape, InkscapeError, InkscapeNotFoundError

    inkscape = get_inkscape()
    if not inkscape.is_available():
        raise ExportError(
            "EPS export requires Inkscape (not installed). "
            "Install via: brew install --cask inkscape"
        )

    svg_path = os.path.abspath(svg_path)
    if output_path is None:
        output_path = str(Path(svg_path).with_suffix(".eps"))

    try:
        result = inkscape.export_eps(svg_path, output_path)
        return [os.path.abspath(result)]
    except InkscapeNotFoundError as exc:
        raise ExportError(
            f"EPS export requires Inkscape: {exc}"
        ) from exc
    except InkscapeError as exc:
        raise ExportError(f"EPS export via Inkscape failed: {exc}") from exc


def export_outlined_svg(
    svg_path: str,
    output_path: str | None = None,
) -> list[str]:
    """
    Create a text-to-path (outlined) SVG version via Inkscape CLI (Phase 3).

    Converts all <text> elements to <path> for font portability. The
    original SVG with editable text is preserved; this creates a separate
    "outlined" version.

    Requires Inkscape >= 1.3.

    Args:
        svg_path: Path to the source SVG.
        output_path: Optional explicit output path. If None, generates
                     an *-outlined.svg alongside the original.

    Returns:
        List containing the outlined SVG file path.

    Raises:
        ExportError: If the conversion fails or Inkscape is not available.
    """
    from engine.inkscape_cli import get_inkscape, InkscapeError, InkscapeNotFoundError

    inkscape = get_inkscape()
    if not inkscape.is_available():
        raise ExportError(
            "Text-to-path conversion requires Inkscape (not installed). "
            "Install via: brew install --cask inkscape"
        )

    svg_path = os.path.abspath(svg_path)
    if output_path is None:
        stem = Path(svg_path).stem
        parent = Path(svg_path).parent
        output_path = str(parent / f"{stem}-outlined.svg")

    try:
        result = inkscape.text_to_path(svg_path, output_path)
        return [os.path.abspath(result)]
    except InkscapeNotFoundError as exc:
        raise ExportError(
            f"Text-to-path requires Inkscape: {exc}"
        ) from exc
    except InkscapeError as exc:
        raise ExportError(f"Text-to-path via Inkscape failed: {exc}") from exc


def export_print_ready_pdf(
    svg_path: str,
    output_path: str | None = None,
    bleed_mm: float = 3.0,
    cmyk: bool = True,
    color_profile: str | None = None,
) -> list[str]:
    """
    Export a print-ready PDF with bleeds and optional CMYK conversion (Phase 3).

    Combines bleed addition (lxml-based) with Inkscape PDF export for a
    production-quality print output.

    Args:
        svg_path: Path to the source SVG.
        output_path: Optional explicit output path. If None, generates
                     *-print.pdf alongside the original.
        bleed_mm: Bleed area in millimeters (default: 3.0).
        cmyk: If True, export as CMYK PDF (requires Inkscape).
        color_profile: Optional ICC color profile path.

    Returns:
        List of file paths produced (bleed SVG, CMYK PDF, etc.).

    Raises:
        ExportError: If the operation fails.
    """
    from engine.inkscape_cli import get_inkscape, InkscapeError

    inkscape = get_inkscape()
    svg_path = os.path.abspath(svg_path)

    if not Path(svg_path).exists():
        raise ExportError(f"Source SVG not found: {svg_path}")

    results: list[str] = []
    output_dir = str(Path(svg_path).parent)

    try:
        print_outputs = inkscape.export_print_ready(
            input_svg=svg_path,
            output_dir=output_dir,
            bleed_mm=bleed_mm,
            text_to_path=False,  # Handled separately by export_outlined_svg
            cmyk=cmyk,
            export_eps=False,    # Handled separately by export_eps
            color_profile=color_profile,
        )

        for path in print_outputs.values():
            results.append(os.path.abspath(path))

    except InkscapeError as exc:
        raise ExportError(f"Print-ready export failed: {exc}") from exc

    return results


def export_print_ready(
    svg_path: str,
    config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Produce a full set of print-ready outputs from config flags (Phase 3).

    Reads print settings from config.vector.print and produces all
    configured print outputs. This is the high-level orchestration
    function called by export_all when print_ready is True.

    Args:
        svg_path: Path to the source SVG.
        config: Resolved workflow config dict.

    Returns:
        Dict mapping output type name to file path.

    Raises:
        ExportError: If a critical operation fails.
    """
    from engine.inkscape_cli import get_inkscape, InkscapeError

    config = config or {}
    vector_cfg = config.get("vector", {})
    print_cfg = vector_cfg.get("print", {})

    # Merge top-level vector flags with print sub-section
    bleed_mm = print_cfg.get("bleed_mm", vector_cfg.get("bleed_mm", 3.0))
    do_cmyk = print_cfg.get("cmyk", vector_cfg.get("cmyk", False))
    do_text_to_path = print_cfg.get(
        "text_to_path", vector_cfg.get("text_to_path", False)
    )
    color_profile = print_cfg.get(
        "color_profile", vector_cfg.get("color_profile")
    )
    do_eps = "eps" in vector_cfg.get("export_formats", [])

    inkscape = get_inkscape()

    svg_path = os.path.abspath(svg_path)
    if not Path(svg_path).exists():
        raise ExportError(f"Source SVG not found: {svg_path}")

    results: dict[str, str] = {}

    try:
        print_outputs = inkscape.export_print_ready(
            input_svg=svg_path,
            bleed_mm=bleed_mm,
            text_to_path=do_text_to_path,
            cmyk=do_cmyk,
            export_eps=do_eps,
            color_profile=color_profile,
        )
        results.update(print_outputs)
    except InkscapeError as exc:
        raise ExportError(f"Print-ready export failed: {exc}") from exc

    return results
