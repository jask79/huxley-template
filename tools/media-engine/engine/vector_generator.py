"""
Vector SVG Generator for the Media Workflow Engine.

Generates professional, editable SVG files using svgwrite and svgpathtools.
Produces icons, geometric logos, diagrams, and badges with organized layers,
semantic groups, editable text elements, and defined viewBoxes.

All output follows the deliverable spec:
  - Organized <g> groups with semantic id attributes
  - Consistent naming convention (e.g., icon-home, logo-primary)
  - Defined viewBox and dimensions
  - Editable <text> elements (not baked as <path>)
  - Color palette as CSS classes
  - File size targets: <100KB icons, <500KB logos
"""

from __future__ import annotations

import math
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import svgwrite
from svgwrite import Drawing
from svgwrite.container import Group


class VectorGenerationError(Exception):
    """Raised when vector generation fails."""


# ---------------------------------------------------------------------------
# Color palette helpers
# ---------------------------------------------------------------------------

DEFAULT_PALETTE = {
    "primary": "#2563EB",
    "secondary": "#7C3AED",
    "accent": "#F59E0B",
    "neutral": "#6B7280",
    "background": "#FFFFFF",
    "foreground": "#111827",
    "success": "#10B981",
    "error": "#EF4444",
}

DUOTONE_FILL_OPACITY = 0.15


def resolve_palette(config: dict[str, Any]) -> dict[str, str]:
    """
    Resolve the color palette from config, falling back to defaults.

    Config can specify palette as:
      vector.palette: { primary: "#...", ... }
    or at top level:
      palette: { ... }
    """
    vector_cfg = config.get("vector", {})
    palette = vector_cfg.get("palette", config.get("palette", {}))
    if not palette or not isinstance(palette, dict):
        return dict(DEFAULT_PALETTE)
    merged = dict(DEFAULT_PALETTE)
    merged.update(palette)
    return merged


# ---------------------------------------------------------------------------
# Icon generation
# ---------------------------------------------------------------------------

# Pre-built icon shape definitions. Each icon is a function that draws into
# a group at the given position and size with the specified style parameters.

ICON_SHAPES = {
    "home": "_draw_icon_home",
    "search": "_draw_icon_search",
    "settings": "_draw_icon_settings",
    "profile": "_draw_icon_profile",
    "menu": "_draw_icon_menu",
    "heart": "_draw_icon_heart",
    "star": "_draw_icon_star",
    "mail": "_draw_icon_mail",
    "bell": "_draw_icon_bell",
    "lock": "_draw_icon_lock",
    "plus": "_draw_icon_plus",
    "check": "_draw_icon_check",
    "close": "_draw_icon_close",
    "arrow_right": "_draw_icon_arrow_right",
    "arrow_left": "_draw_icon_arrow_left",
    "edit": "_draw_icon_edit",
    "trash": "_draw_icon_trash",
    "download": "_draw_icon_download",
    "upload": "_draw_icon_upload",
    "share": "_draw_icon_share",
    "calendar": "_draw_icon_calendar",
    "clock": "_draw_icon_clock",
    "folder": "_draw_icon_folder",
    "image": "_draw_icon_image",
}


def generate_icon(config: dict[str, Any], prompt: str, output_path: str) -> str:
    """
    Generate an icon set SVG from a prompt.

    Parses the prompt for icon names, lays them out in a grid, and generates
    each icon with consistent stroke weights and sizing.

    Args:
        config: Resolved workflow config dict.
        prompt: Description of icons to generate (e.g., "home, search, settings").
        output_path: Path to write the SVG file.

    Returns:
        Absolute path to the generated SVG file.
    """
    vector_cfg = config.get("vector", {})
    grid_size_str = vector_cfg.get("grid_size", "24x24")
    stroke_weight = vector_cfg.get("stroke_weight", 2)
    corner_radius = vector_cfg.get("corner_radius", 0)
    icon_style = vector_cfg.get("icon_style", "line")
    palette = resolve_palette(config)

    # Parse grid size
    match = re.match(r"(\d+)x(\d+)", str(grid_size_str))
    if match:
        cell_w, cell_h = int(match.group(1)), int(match.group(2))
    else:
        cell_w, cell_h = 24, 24

    # Parse icon names from prompt
    icon_names = _parse_icon_names(prompt)
    if not icon_names:
        icon_names = ["home", "search", "settings", "profile"]

    # Calculate grid layout
    cols = min(len(icon_names), 6)
    rows = math.ceil(len(icon_names) / cols)
    padding = 8
    total_w = cols * (cell_w + padding) + padding
    total_h = rows * (cell_h + padding) + padding

    # Create SVG drawing
    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{total_w}px", f"{total_h}px"),
        viewBox=f"0 0 {total_w} {total_h}",
    )

    # Add CSS classes for palette
    style_text = _build_palette_css(palette)
    dwg.defs.add(dwg.style(style_text))

    # Create root icon set group
    icon_set_group = dwg.g(id="icon-set")

    for idx, name in enumerate(icon_names):
        col = idx % cols
        row = idx // cols
        x = padding + col * (cell_w + padding)
        y = padding + row * (cell_h + padding)

        icon_group = dwg.g(
            id=f"icon-{name}",
            transform=f"translate({x}, {y})",
        )
        icon_group["class"] = "icon"

        _draw_icon_shape(
            dwg, icon_group, name,
            cell_w, cell_h,
            stroke_weight, corner_radius,
            icon_style, palette,
        )

        # Add label text below icon
        label = dwg.text(
            name.replace("_", " "),
            insert=(cell_w / 2, cell_h + 4),
            text_anchor="middle",
            font_size="3px",
            font_family="system-ui, -apple-system, sans-serif",
            fill=palette["neutral"],
        )
        label["class"] = "icon-label"
        icon_group.add(label)

        icon_set_group.add(icon_group)

    dwg.add(icon_set_group)
    dwg.save()

    return os.path.abspath(output_path)


# ---------------------------------------------------------------------------
# Geometric logo generation
# ---------------------------------------------------------------------------

def generate_geometric_logo(config: dict[str, Any], prompt: str, output_path: str) -> str:
    """
    Generate a geometric logo SVG from a prompt.

    Creates a logo with geometric shapes, optional wordmark, and optional
    monogram. The prompt is parsed for a brand name and style hints.

    Args:
        config: Resolved workflow config dict.
        prompt: Description of the logo (e.g., "modern tech startup logo for Acme").
        output_path: Path to write the SVG file.

    Returns:
        Absolute path to the generated SVG file.
    """
    vector_cfg = config.get("vector", {})
    stroke_weight = vector_cfg.get("stroke_weight", 2)
    corner_radius = vector_cfg.get("corner_radius", 4)
    palette = resolve_palette(config)

    # Parse brand name from prompt
    brand_name = _extract_brand_name(prompt)

    # Logo dimensions
    logo_w, logo_h = 400, 200
    icon_size = 80

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{logo_w}px", f"{logo_h}px"),
        viewBox=f"0 0 {logo_w} {logo_h}",
    )

    style_text = _build_palette_css(palette)
    dwg.defs.add(dwg.style(style_text))

    # Root logo group
    logo_group = dwg.g(id="logo-primary")

    # Background (optional, transparent by default)
    bg_group = dwg.g(id="logo-background")
    logo_group.add(bg_group)

    # Icon mark group
    mark_group = dwg.g(
        id="logo-mark",
        transform=f"translate({logo_w / 2 - icon_size - 20}, {logo_h / 2 - icon_size / 2})",
    )

    # Generate geometric shapes based on prompt analysis
    _draw_geometric_mark(
        dwg, mark_group,
        icon_size, stroke_weight, corner_radius,
        palette, prompt,
    )
    logo_group.add(mark_group)

    # Wordmark group
    wordmark_group = dwg.g(id="logo-wordmark")
    wordmark_text = dwg.text(
        brand_name,
        insert=(logo_w / 2 + 10, logo_h / 2 + 10),
        font_size="36px",
        font_family="system-ui, -apple-system, sans-serif",
        font_weight="700",
        fill=palette["foreground"],
        text_anchor="start",
    )
    wordmark_text["class"] = "wordmark"
    wordmark_group.add(wordmark_text)
    logo_group.add(wordmark_group)

    # Monogram group (first letter)
    if brand_name:
        monogram_group = dwg.g(
            id="logo-monogram",
            transform=f"translate({logo_w / 2 - icon_size - 20}, {logo_h / 2 - icon_size / 2})",
        )
        monogram_text = dwg.text(
            brand_name[0].upper(),
            insert=(icon_size / 2, icon_size / 2 + 12),
            font_size="32px",
            font_family="system-ui, -apple-system, sans-serif",
            font_weight="800",
            fill=palette["background"],
            text_anchor="middle",
            dominant_baseline="middle",
        )
        monogram_text["class"] = "monogram"
        monogram_group.add(monogram_text)
        logo_group.add(monogram_group)

    dwg.add(logo_group)
    dwg.save()

    return os.path.abspath(output_path)


# ---------------------------------------------------------------------------
# Diagram generation
# ---------------------------------------------------------------------------

def generate_diagram(config: dict[str, Any], prompt: str, output_path: str) -> str:
    """
    Generate a technical diagram SVG from a prompt.

    Creates boxes with labels connected by arrows. The prompt is parsed
    for node names and connections.

    Args:
        config: Resolved workflow config dict.
        prompt: Description of diagram (e.g., "Client -> API -> Database").
        output_path: Path to write the SVG file.

    Returns:
        Absolute path to the generated SVG file.
    """
    vector_cfg = config.get("vector", {})
    stroke_weight = vector_cfg.get("stroke_weight", 2)
    corner_radius = vector_cfg.get("corner_radius", 6)
    palette = resolve_palette(config)

    # Parse diagram nodes and connections from prompt
    nodes, connections = _parse_diagram(prompt)

    if not nodes:
        nodes = ["Start", "Process", "End"]
        connections = [("Start", "Process"), ("Process", "End")]

    # Layout: horizontal flow
    box_w, box_h = 140, 60
    h_gap = 80
    padding = 40

    # Calculate canvas size
    total_w = padding * 2 + len(nodes) * box_w + (len(nodes) - 1) * h_gap
    total_h = padding * 2 + box_h + 40  # extra for labels

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{total_w}px", f"{total_h}px"),
        viewBox=f"0 0 {total_w} {total_h}",
    )

    style_text = _build_palette_css(palette)
    dwg.defs.add(dwg.style(style_text))

    # Add arrowhead marker
    marker = dwg.marker(
        id="arrowhead",
        insert=(10, 5),
        size=(10, 10),
        orient="auto",
    )
    marker.add(dwg.polygon(
        points=[(0, 0), (10, 5), (0, 10)],
        fill=palette["neutral"],
    ))
    dwg.defs.add(marker)

    diagram_group = dwg.g(id="diagram")

    # Draw connections first (behind boxes)
    connections_group = dwg.g(id="diagram-connections")
    node_positions: dict[str, tuple[float, float]] = {}

    for idx, node_name in enumerate(nodes):
        cx = padding + idx * (box_w + h_gap) + box_w / 2
        cy = padding + box_h / 2
        node_positions[node_name] = (cx, cy)

    for src, dst in connections:
        if src in node_positions and dst in node_positions:
            sx, sy = node_positions[src]
            dx, dy = node_positions[dst]
            line = dwg.line(
                start=(sx + box_w / 2, sy),
                end=(dx - box_w / 2, dy),
                stroke=palette["neutral"],
                stroke_width=stroke_weight,
            )
            line["marker-end"] = "url(#arrowhead)"
            line["class"] = "connection"
            connections_group.add(line)

    diagram_group.add(connections_group)

    # Draw nodes
    nodes_group = dwg.g(id="diagram-nodes")

    for idx, node_name in enumerate(nodes):
        x = padding + idx * (box_w + h_gap)
        y = padding

        node_group = dwg.g(
            id=f"node-{_slugify(node_name)}",
            transform=f"translate({x}, {y})",
        )
        node_group["class"] = "diagram-node"

        # Box
        rect = dwg.rect(
            insert=(0, 0),
            size=(box_w, box_h),
            rx=corner_radius,
            ry=corner_radius,
            fill=palette["background"],
            stroke=palette["primary"],
            stroke_width=stroke_weight,
        )
        rect["class"] = "node-box"
        node_group.add(rect)

        # Label
        label = dwg.text(
            node_name,
            insert=(box_w / 2, box_h / 2 + 5),
            text_anchor="middle",
            font_size="14px",
            font_family="system-ui, -apple-system, sans-serif",
            font_weight="500",
            fill=palette["foreground"],
        )
        label["class"] = "node-label"
        node_group.add(label)

        nodes_group.add(node_group)

    diagram_group.add(nodes_group)
    dwg.add(diagram_group)
    dwg.save()

    return os.path.abspath(output_path)


# ---------------------------------------------------------------------------
# Badge generation
# ---------------------------------------------------------------------------

def generate_wordmark(config: dict[str, Any], prompt: str, output_path: str) -> str:
    """
    Generate a wordmark (text-based) logo SVG from a prompt.

    Creates a typographic logo with custom styling: letter-spacing,
    font weight, optional underline or decorative line.

    Args:
        config: Resolved workflow config dict.
        prompt: Description of the wordmark (e.g., "Acme in modern sans-serif").
        output_path: Path to write the SVG file.

    Returns:
        Absolute path to the generated SVG file.
    """
    vector_cfg = config.get("vector", {})
    stroke_weight = vector_cfg.get("stroke_weight", 2)
    palette = resolve_palette(config)

    brand_name = _extract_brand_name(prompt)
    prompt_lower = prompt.lower()

    # Wordmark dimensions
    logo_w, logo_h = 500, 120
    padding = 30

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{logo_w}px", f"{logo_h}px"),
        viewBox=f"0 0 {logo_w} {logo_h}",
    )

    style_text = _build_palette_css(palette)
    dwg.defs.add(dwg.style(style_text))

    logo_group = dwg.g(id="logo-wordmark")

    # Background group
    bg_group = dwg.g(id="wordmark-background")
    logo_group.add(bg_group)

    # Determine font weight from prompt
    if any(w in prompt_lower for w in ["bold", "heavy", "strong"]):
        font_weight = "800"
    elif any(w in prompt_lower for w in ["light", "thin"]):
        font_weight = "300"
    else:
        font_weight = "600"

    # Determine letter spacing
    if any(w in prompt_lower for w in ["wide", "spaced", "airy"]):
        letter_spacing = "0.2em"
    elif any(w in prompt_lower for w in ["tight", "compact"]):
        letter_spacing = "-0.02em"
    else:
        letter_spacing = "0.08em"

    # Determine case
    display_name = brand_name
    if any(w in prompt_lower for w in ["uppercase", "caps", "all caps"]):
        display_name = brand_name.upper()
    elif any(w in prompt_lower for w in ["lowercase"]):
        display_name = brand_name.lower()

    # Main wordmark text
    text_group = dwg.g(id="wordmark-text")
    main_text = dwg.text(
        display_name,
        insert=(logo_w / 2, logo_h / 2 + 8),
        text_anchor="middle",
        dominant_baseline="middle",
        font_size="48px",
        font_family="system-ui, -apple-system, sans-serif",
        font_weight=font_weight,
        fill=palette["foreground"],
    )
    main_text["letter-spacing"] = letter_spacing
    main_text["class"] = "wordmark"
    text_group.add(main_text)
    logo_group.add(text_group)

    # Decorative underline
    line_group = dwg.g(id="wordmark-decoration")
    if any(w in prompt_lower for w in ["underline", "line", "accent"]):
        line_y = logo_h / 2 + 30
        line_group.add(dwg.line(
            start=(padding + 20, line_y),
            end=(logo_w - padding - 20, line_y),
            stroke=palette["primary"],
            stroke_width=stroke_weight,
            stroke_linecap="round",
        ))
    else:
        # Subtle dot accent
        line_group.add(dwg.circle(
            center=(logo_w / 2, logo_h / 2 + 32),
            r=3,
            fill=palette["primary"],
        ))
    logo_group.add(line_group)

    dwg.add(logo_group)
    dwg.save()

    return os.path.abspath(output_path)


def generate_monogram(config: dict[str, Any], prompt: str, output_path: str) -> str:
    """
    Generate a monogram (single letter/initials) logo SVG from a prompt.

    Creates a single letter or initials with a geometric background shape
    (circle, square, or hexagon).

    Args:
        config: Resolved workflow config dict.
        prompt: Description of the monogram (e.g., "letter A in circle").
        output_path: Path to write the SVG file.

    Returns:
        Absolute path to the generated SVG file.
    """
    vector_cfg = config.get("vector", {})
    stroke_weight = vector_cfg.get("stroke_weight", 2)
    corner_radius = vector_cfg.get("corner_radius", 8)
    palette = resolve_palette(config)

    brand_name = _extract_brand_name(prompt)
    prompt_lower = prompt.lower()

    # Extract initials
    words = brand_name.split()
    if len(words) >= 2:
        initials = "".join(w[0].upper() for w in words[:3])
    else:
        initials = brand_name[0].upper() if brand_name else "A"

    # Monogram dimensions (square)
    size = 200
    cx, cy = size / 2, size / 2

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{size}px", f"{size}px"),
        viewBox=f"0 0 {size} {size}",
    )

    style_text = _build_palette_css(palette)
    dwg.defs.add(dwg.style(style_text))

    logo_group = dwg.g(id="logo-monogram")

    # Background shape
    bg_group = dwg.g(id="monogram-background")
    margin = 10

    if any(w in prompt_lower for w in ["circle", "round"]):
        bg_group.add(dwg.circle(
            center=(cx, cy), r=size / 2 - margin,
            fill=palette["primary"],
        ))
    elif any(w in prompt_lower for w in ["hex", "hexagon"]):
        points = []
        for i in range(6):
            angle = math.radians(60 * i - 30)
            r = size / 2 - margin
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        bg_group.add(dwg.polygon(points=points, fill=palette["primary"]))
    elif any(w in prompt_lower for w in ["diamond"]):
        bg_group.add(dwg.rect(
            insert=(margin + 15, margin + 15),
            size=(size - 2 * margin - 30, size - 2 * margin - 30),
            rx=corner_radius, ry=corner_radius,
            fill=palette["primary"],
            transform=f"rotate(45, {cx}, {cy})",
        ))
    else:
        # Default: rounded square
        bg_group.add(dwg.rect(
            insert=(margin, margin),
            size=(size - 2 * margin, size - 2 * margin),
            rx=corner_radius * 3, ry=corner_radius * 3,
            fill=palette["primary"],
        ))

    logo_group.add(bg_group)

    # Initials text
    text_group = dwg.g(id="monogram-text")
    font_size = "72px" if len(initials) == 1 else ("52px" if len(initials) == 2 else "40px")
    text_group.add(dwg.text(
        initials,
        insert=(cx, cy + 4),
        text_anchor="middle",
        dominant_baseline="middle",
        font_size=font_size,
        font_family="system-ui, -apple-system, sans-serif",
        font_weight="800",
        fill=palette["background"],
    ))
    logo_group.add(text_group)

    # Subtle inner accent ring
    accent_group = dwg.g(id="monogram-accent")
    accent_group.add(dwg.circle(
        center=(cx, cy),
        r=size / 2 - margin - 8,
        fill="none",
        stroke=palette["background"],
        stroke_width=1,
        stroke_opacity=0.2,
    ))
    logo_group.add(accent_group)

    dwg.add(logo_group)
    dwg.save()

    return os.path.abspath(output_path)


def generate_combination_mark(config: dict[str, Any], prompt: str, output_path: str) -> str:
    """
    Generate a combination mark (icon + wordmark) logo SVG from a prompt.

    Combines a geometric icon mark on the left with a wordmark on the right.

    Args:
        config: Resolved workflow config dict.
        prompt: Description of the logo (e.g., "tech company Acme with shield icon").
        output_path: Path to write the SVG file.

    Returns:
        Absolute path to the generated SVG file.
    """
    vector_cfg = config.get("vector", {})
    stroke_weight = vector_cfg.get("stroke_weight", 2)
    corner_radius = vector_cfg.get("corner_radius", 4)
    palette = resolve_palette(config)

    brand_name = _extract_brand_name(prompt)

    # Combination mark dimensions
    logo_w, logo_h = 480, 120
    icon_size = 80
    icon_x = 30
    icon_cy = logo_h / 2

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{logo_w}px", f"{logo_h}px"),
        viewBox=f"0 0 {logo_w} {logo_h}",
    )

    style_text = _build_palette_css(palette)
    dwg.defs.add(dwg.style(style_text))

    logo_group = dwg.g(id="logo-combination")

    # Icon mark
    mark_group = dwg.g(
        id="combination-mark",
        transform=f"translate({icon_x}, {icon_cy - icon_size / 2})",
    )
    _draw_geometric_mark(
        dwg, mark_group,
        icon_size, stroke_weight, corner_radius,
        palette, prompt,
    )
    logo_group.add(mark_group)

    # Divider line
    divider_group = dwg.g(id="combination-divider")
    div_x = icon_x + icon_size + 20
    divider_group.add(dwg.line(
        start=(div_x, logo_h * 0.25),
        end=(div_x, logo_h * 0.75),
        stroke=palette["neutral"],
        stroke_width=1,
        stroke_opacity=0.3,
    ))
    logo_group.add(divider_group)

    # Wordmark
    wordmark_group = dwg.g(id="combination-wordmark")
    text_x = div_x + 20
    wordmark_group.add(dwg.text(
        brand_name,
        insert=(text_x, icon_cy + 6),
        font_size="36px",
        font_family="system-ui, -apple-system, sans-serif",
        font_weight="700",
        fill=palette["foreground"],
        text_anchor="start",
        dominant_baseline="middle",
    ))
    logo_group.add(wordmark_group)

    # Tagline area
    tagline_group = dwg.g(id="combination-tagline")
    logo_group.add(tagline_group)

    dwg.add(logo_group)
    dwg.save()

    return os.path.abspath(output_path)


def generate_brand_palette(config: dict[str, Any], prompt: str, output_path: str) -> str:
    """
    Generate a color palette visualization SVG.

    Creates a grid of color swatches with hex values, organized neatly.

    Args:
        config: Resolved workflow config dict.
        prompt: Description or color list (e.g., "blue primary palette").
        output_path: Path to write the SVG file.

    Returns:
        Absolute path to the generated SVG file.
    """
    vector_cfg = config.get("vector", {})
    corner_radius = vector_cfg.get("corner_radius", 8)
    palette = resolve_palette(config)

    # Parse custom colors from prompt, or use palette
    colors = _parse_palette_colors(prompt, palette)

    # Layout
    swatch_w = 100
    swatch_h = 120
    label_h = 30
    cols = min(len(colors), 6)
    rows = math.ceil(len(colors) / cols)
    padding = 20
    gap = 12

    total_w = padding * 2 + cols * swatch_w + (cols - 1) * gap
    total_h = padding * 2 + rows * (swatch_h + label_h + gap) + 40

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{total_w}px", f"{total_h}px"),
        viewBox=f"0 0 {total_w} {total_h}",
    )

    style_text = _build_palette_css(palette)
    dwg.defs.add(dwg.style(style_text))

    palette_group = dwg.g(id="brand-palette")

    # Title
    title_group = dwg.g(id="palette-title")
    title_group.add(dwg.text(
        "Color Palette",
        insert=(padding, padding + 16),
        font_size="18px",
        font_family="system-ui, -apple-system, sans-serif",
        font_weight="600",
        fill=palette["foreground"],
    ))
    palette_group.add(title_group)

    # Swatches
    swatches_group = dwg.g(id="palette-swatches")
    y_offset = padding + 40

    for idx, (name, color) in enumerate(colors.items()):
        col = idx % cols
        row = idx // cols
        x = padding + col * (swatch_w + gap)
        y = y_offset + row * (swatch_h + label_h + gap)

        swatch_group = dwg.g(
            id=f"swatch-{_slugify(name)}",
            transform=f"translate({x}, {y})",
        )

        # Color rectangle
        swatch_group.add(dwg.rect(
            insert=(0, 0),
            size=(swatch_w, swatch_h),
            rx=corner_radius, ry=corner_radius,
            fill=color,
            stroke=palette.get("neutral", "#999"),
            stroke_width=0.5,
            stroke_opacity=0.3,
        ))

        # Color name
        swatch_group.add(dwg.text(
            name.replace("_", " ").title(),
            insert=(swatch_w / 2, swatch_h + 16),
            text_anchor="middle",
            font_size="11px",
            font_family="system-ui, -apple-system, sans-serif",
            font_weight="500",
            fill=palette["foreground"],
        ))

        # Hex value
        swatch_group.add(dwg.text(
            color.upper(),
            insert=(swatch_w / 2, swatch_h + 28),
            text_anchor="middle",
            font_size="9px",
            font_family="ui-monospace, monospace",
            font_weight="400",
            fill=palette.get("neutral", "#666"),
        ))

        swatches_group.add(swatch_group)

    palette_group.add(swatches_group)
    dwg.add(palette_group)
    dwg.save()

    return os.path.abspath(output_path)


def generate_brand_typography(config: dict[str, Any], prompt: str, output_path: str) -> str:
    """
    Generate a typography specimen sheet SVG.

    Shows headings, body text, font weights, and sizes in a structured layout.

    Args:
        config: Resolved workflow config dict.
        prompt: Description (e.g., "typography specimen for Acme brand").
        output_path: Path to write the SVG file.

    Returns:
        Absolute path to the generated SVG file.
    """
    palette = resolve_palette(config)
    brand_name = _extract_brand_name(prompt)

    # Layout
    page_w, page_h = 600, 700
    padding = 40
    col_w = page_w - 2 * padding

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{page_w}px", f"{page_h}px"),
        viewBox=f"0 0 {page_w} {page_h}",
    )

    style_text = _build_palette_css(palette)
    dwg.defs.add(dwg.style(style_text))

    typo_group = dwg.g(id="brand-typography")

    # Title
    title_group = dwg.g(id="typo-title")
    title_group.add(dwg.text(
        "Typography Specimen",
        insert=(padding, padding + 20),
        font_size="14px",
        font_family="system-ui, -apple-system, sans-serif",
        font_weight="400",
        fill=palette.get("neutral", "#666"),
    ))
    typo_group.add(title_group)

    y = padding + 60

    # Heading showcase
    headings_group = dwg.g(id="typo-headings")
    heading_specs = [
        ("H1 / Display", "48px", "800", brand_name),
        ("H2 / Title", "36px", "700", f"Welcome to {brand_name}"),
        ("H3 / Subtitle", "24px", "600", "A heading that explains"),
        ("H4 / Section", "18px", "600", "Section heading with detail"),
        ("Body / Regular", "14px", "400", "The quick brown fox jumps over the lazy dog. "
         "Typography is the art and technique of arranging type."),
        ("Caption / Small", "11px", "400", "Caption text, metadata, timestamps, and labels"),
    ]

    for label, size, weight, sample in heading_specs:
        # Label
        headings_group.add(dwg.text(
            label,
            insert=(padding, y),
            font_size="9px",
            font_family="ui-monospace, monospace",
            font_weight="400",
            fill=palette.get("neutral", "#999"),
        ))
        y += 8

        # Sample text
        headings_group.add(dwg.text(
            sample,
            insert=(padding, y + int(size.replace("px", "")) * 0.7),
            font_size=size,
            font_family="system-ui, -apple-system, sans-serif",
            font_weight=weight,
            fill=palette["foreground"],
        ))
        y += int(size.replace("px", "")) + 24

    typo_group.add(headings_group)

    # Font weight showcase
    y += 10
    weights_group = dwg.g(id="typo-weights")
    weights_group.add(dwg.text(
        "Font Weights",
        insert=(padding, y),
        font_size="9px",
        font_family="ui-monospace, monospace",
        font_weight="400",
        fill=palette.get("neutral", "#999"),
    ))
    y += 20

    weight_samples = [
        ("300 Light", "300"),
        ("400 Regular", "400"),
        ("500 Medium", "500"),
        ("600 Semibold", "600"),
        ("700 Bold", "700"),
        ("800 Extra Bold", "800"),
    ]

    for label, weight in weight_samples:
        weights_group.add(dwg.text(
            label,
            insert=(padding, y),
            font_size="16px",
            font_family="system-ui, -apple-system, sans-serif",
            font_weight=weight,
            fill=palette["foreground"],
        ))
        y += 28

    typo_group.add(weights_group)

    dwg.add(typo_group)
    dwg.save()

    return os.path.abspath(output_path)


def generate_flowchart(config: dict[str, Any], prompt: str, output_path: str) -> str:
    """
    Generate a decision flowchart SVG from a prompt.

    Creates diamond decision nodes with yes/no paths, rectangular process
    nodes, and rounded start/end nodes.

    Args:
        config: Resolved workflow config dict.
        prompt: Description of the flowchart (e.g., "Login -> Valid? -> yes:Dashboard, no:Error").
        output_path: Path to write the SVG file.

    Returns:
        Absolute path to the generated SVG file.
    """
    vector_cfg = config.get("vector", {})
    stroke_weight = vector_cfg.get("stroke_weight", 2)
    corner_radius = vector_cfg.get("corner_radius", 6)
    palette = resolve_palette(config)

    # Parse flowchart nodes
    flow_nodes = _parse_flowchart(prompt)

    if not flow_nodes:
        flow_nodes = [
            {"type": "start", "label": "Start"},
            {"type": "process", "label": "Process Data"},
            {"type": "decision", "label": "Valid?", "yes": "Output", "no": "Error"},
            {"type": "process", "label": "Output"},
            {"type": "end", "label": "End"},
            {"type": "process", "label": "Error"},
        ]

    # Layout constants
    node_w, node_h = 140, 50
    decision_size = 70
    v_gap = 60
    h_gap = 180
    padding = 50

    # Simple vertical layout
    total_h = padding * 2 + len(flow_nodes) * (node_h + v_gap)
    total_w = padding * 2 + node_w + h_gap + node_w  # Main column + side branch

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{total_w}px", f"{total_h}px"),
        viewBox=f"0 0 {total_w} {total_h}",
    )

    style_text = _build_palette_css(palette)
    dwg.defs.add(dwg.style(style_text))

    # Arrowhead marker
    marker = dwg.marker(
        id="flow-arrow", insert=(10, 5), size=(10, 10), orient="auto",
    )
    marker.add(dwg.polygon(
        points=[(0, 0), (10, 5), (0, 10)], fill=palette["neutral"],
    ))
    dwg.defs.add(marker)

    chart_group = dwg.g(id="flowchart")
    nodes_group = dwg.g(id="flowchart-nodes")
    connections_group = dwg.g(id="flowchart-connections")

    # Track node centers for connections
    node_centers: list[tuple[float, float]] = []
    main_x = padding + node_w / 2
    side_x = main_x + h_gap

    y = padding
    side_branch_nodes: list[tuple[int, str, float, float]] = []

    for idx, node in enumerate(flow_nodes):
        cx = main_x
        cy = y + node_h / 2
        node_id = f"node-{_slugify(node['label'])}"

        if node["type"] == "start" or node["type"] == "end":
            # Rounded rectangle (pill shape)
            ng = dwg.g(id=node_id, transform=f"translate({cx - node_w / 2}, {y})")
            ng["class"] = "flowchart-node"
            ng.add(dwg.rect(
                insert=(0, 0), size=(node_w, node_h),
                rx=node_h / 2, ry=node_h / 2,
                fill=palette["primary"] if node["type"] == "start" else palette["neutral"],
                stroke=palette["foreground"], stroke_width=stroke_weight,
            ))
            ng.add(dwg.text(
                node["label"], insert=(node_w / 2, node_h / 2 + 5),
                text_anchor="middle", font_size="14px",
                font_family="system-ui, -apple-system, sans-serif",
                font_weight="600",
                fill=palette["background"],
            ))
            nodes_group.add(ng)

        elif node["type"] == "decision":
            # Diamond shape
            ds = decision_size
            ng = dwg.g(id=node_id, transform=f"translate({cx}, {cy})")
            ng["class"] = "flowchart-decision"
            ng.add(dwg.polygon(
                points=[(0, -ds / 2), (ds / 2, 0), (0, ds / 2), (-ds / 2, 0)],
                fill=palette.get("accent", palette["secondary"]),
                stroke=palette["foreground"], stroke_width=stroke_weight,
            ))
            ng.add(dwg.text(
                node["label"], insert=(0, 5),
                text_anchor="middle", font_size="11px",
                font_family="system-ui, -apple-system, sans-serif",
                font_weight="600",
                fill=palette["foreground"],
            ))
            nodes_group.add(ng)

            # "Yes" label on the down arrow
            connections_group.add(dwg.text(
                "Yes", insert=(cx + 8, cy + ds / 2 + 14),
                font_size="10px", font_family="system-ui, sans-serif",
                fill=palette.get("success", "#10B981"), font_weight="500",
            ))

            # "No" side branch
            if node.get("no"):
                connections_group.add(dwg.text(
                    "No", insert=(cx + ds / 2 + 8, cy - 4),
                    font_size="10px", font_family="system-ui, sans-serif",
                    fill=palette.get("error", "#EF4444"), font_weight="500",
                ))
                # Side arrow
                side_arrow = dwg.line(
                    start=(cx + ds / 2, cy),
                    end=(side_x - node_w / 2, cy),
                    stroke=palette["neutral"], stroke_width=stroke_weight,
                )
                side_arrow["marker-end"] = "url(#flow-arrow)"
                connections_group.add(side_arrow)

                side_branch_nodes.append((idx, node["no"], side_x, cy))

        else:
            # Regular process box
            ng = dwg.g(id=node_id, transform=f"translate({cx - node_w / 2}, {y})")
            ng["class"] = "flowchart-node"
            ng.add(dwg.rect(
                insert=(0, 0), size=(node_w, node_h),
                rx=corner_radius, ry=corner_radius,
                fill=palette["background"],
                stroke=palette["primary"], stroke_width=stroke_weight,
            ))
            ng.add(dwg.text(
                node["label"], insert=(node_w / 2, node_h / 2 + 5),
                text_anchor="middle", font_size="13px",
                font_family="system-ui, -apple-system, sans-serif",
                font_weight="500",
                fill=palette["foreground"],
            ))
            nodes_group.add(ng)

        node_centers.append((cx, cy))

        # Draw connection to next node
        if idx < len(flow_nodes) - 1:
            next_y = y + node_h + v_gap
            conn_line = dwg.line(
                start=(cx, y + node_h),
                end=(cx, next_y),
                stroke=palette["neutral"], stroke_width=stroke_weight,
            )
            conn_line["marker-end"] = "url(#flow-arrow)"
            connections_group.add(conn_line)

        y += node_h + v_gap

    # Draw side branch nodes
    for _, label, sx, sy in side_branch_nodes:
        ng = dwg.g(
            id=f"node-{_slugify(label)}",
            transform=f"translate({sx - node_w / 2}, {sy - node_h / 2})",
        )
        ng["class"] = "flowchart-node"
        ng.add(dwg.rect(
            insert=(0, 0), size=(node_w, node_h),
            rx=corner_radius, ry=corner_radius,
            fill=palette["background"],
            stroke=palette.get("error", "#EF4444"), stroke_width=stroke_weight,
        ))
        ng.add(dwg.text(
            label, insert=(node_w / 2, node_h / 2 + 5),
            text_anchor="middle", font_size="13px",
            font_family="system-ui, sans-serif", font_weight="500",
            fill=palette["foreground"],
        ))
        nodes_group.add(ng)

    chart_group.add(connections_group)
    chart_group.add(nodes_group)
    dwg.add(chart_group)
    dwg.save()

    return os.path.abspath(output_path)


def generate_architecture(config: dict[str, Any], prompt: str, output_path: str) -> str:
    """
    Generate a system architecture diagram SVG from a prompt.

    Creates service boxes arranged in tiers (client/server/data) with
    arrows showing communication flow.

    Args:
        config: Resolved workflow config dict.
        prompt: Description (e.g., "Browser -> API Gateway -> Auth Service, User DB").
        output_path: Path to write the SVG file.

    Returns:
        Absolute path to the generated SVG file.
    """
    vector_cfg = config.get("vector", {})
    stroke_weight = vector_cfg.get("stroke_weight", 2)
    corner_radius = vector_cfg.get("corner_radius", 8)
    palette = resolve_palette(config)

    # Parse nodes and connections
    nodes, connections = _parse_diagram(prompt)

    if not nodes:
        nodes = ["Browser", "API Gateway", "Auth Service", "User DB", "Cache"]
        connections = [
            ("Browser", "API Gateway"),
            ("API Gateway", "Auth Service"),
            ("API Gateway", "User DB"),
            ("API Gateway", "Cache"),
        ]

    # Tiered layout: distribute nodes across rows
    box_w, box_h = 150, 70
    h_gap = 40
    v_gap = 80
    padding = 50

    # Simple distribution: first node is top tier, connected nodes form tiers
    tiers: list[list[str]] = []
    placed: set[str] = set()

    # BFS to build tiers
    tier_queue = [nodes[0]]
    placed.add(nodes[0])
    while tier_queue:
        tiers.append(list(tier_queue))
        next_tier = []
        for n in tier_queue:
            for src, dst in connections:
                target = dst if src == n else (src if dst == n else None)
                if target and target not in placed:
                    next_tier.append(target)
                    placed.add(target)
        tier_queue = next_tier

    # Place any unplaced nodes in the last tier
    for n in nodes:
        if n not in placed:
            if not tiers:
                tiers.append([])
            tiers[-1].append(n)

    # Calculate canvas size
    max_cols = max(len(tier) for tier in tiers) if tiers else 1
    total_w = padding * 2 + max_cols * box_w + (max_cols - 1) * h_gap
    total_h = padding * 2 + len(tiers) * box_h + (len(tiers) - 1) * v_gap + 30

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{total_w}px", f"{total_h}px"),
        viewBox=f"0 0 {total_w} {total_h}",
    )

    style_text = _build_palette_css(palette)
    dwg.defs.add(dwg.style(style_text))

    # Arrowhead
    marker = dwg.marker(
        id="arch-arrow", insert=(10, 5), size=(10, 10), orient="auto",
    )
    marker.add(dwg.polygon(
        points=[(0, 0), (10, 5), (0, 10)], fill=palette["neutral"],
    ))
    dwg.defs.add(marker)

    arch_group = dwg.g(id="architecture")

    # Tier label colors
    tier_colors = [
        palette["primary"],
        palette["secondary"],
        palette.get("accent", palette["primary"]),
        palette.get("neutral", "#6B7280"),
    ]

    # Track positions
    node_pos: dict[str, tuple[float, float]] = {}

    nodes_group = dwg.g(id="arch-nodes")
    for tier_idx, tier in enumerate(tiers):
        tier_w = len(tier) * box_w + (len(tier) - 1) * h_gap
        start_x = (total_w - tier_w) / 2
        y = padding + tier_idx * (box_h + v_gap)
        color = tier_colors[tier_idx % len(tier_colors)]

        for col_idx, node_name in enumerate(tier):
            x = start_x + col_idx * (box_w + h_gap)
            cx = x + box_w / 2
            cy = y + box_h / 2
            node_pos[node_name] = (cx, cy)

            ng = dwg.g(
                id=f"service-{_slugify(node_name)}",
                transform=f"translate({x}, {y})",
            )
            ng["class"] = "arch-service"

            # Service box with colored top border
            ng.add(dwg.rect(
                insert=(0, 0), size=(box_w, box_h),
                rx=corner_radius, ry=corner_radius,
                fill=palette["background"],
                stroke=color, stroke_width=stroke_weight,
            ))
            # Colored header band
            ng.add(dwg.rect(
                insert=(0, 0), size=(box_w, 6),
                rx=corner_radius, ry=corner_radius,
                fill=color,
            ))
            # Service name
            ng.add(dwg.text(
                node_name, insert=(box_w / 2, box_h / 2 + 8),
                text_anchor="middle", font_size="13px",
                font_family="system-ui, -apple-system, sans-serif",
                font_weight="500", fill=palette["foreground"],
            ))

            nodes_group.add(ng)

    arch_group.add(nodes_group)

    # Draw connections
    conn_group = dwg.g(id="arch-connections")
    for src, dst in connections:
        if src in node_pos and dst in node_pos:
            sx, sy = node_pos[src]
            dx, dy = node_pos[dst]

            # Draw from bottom of source to top of destination
            if abs(sy - dy) > 10:
                # Vertical connection
                arch_line = dwg.line(
                    start=(sx, sy + box_h / 2),
                    end=(dx, dy - box_h / 2),
                    stroke=palette["neutral"], stroke_width=stroke_weight,
                )
            else:
                # Horizontal connection
                arch_line = dwg.line(
                    start=(sx + box_w / 2, sy),
                    end=(dx - box_w / 2, dy),
                    stroke=palette["neutral"], stroke_width=stroke_weight,
                )
            arch_line["marker-end"] = "url(#arch-arrow)"
            conn_group.add(arch_line)

    arch_group.add(conn_group)
    dwg.add(arch_group)
    dwg.save()

    return os.path.abspath(output_path)


def generate_wireframe(config: dict[str, Any], prompt: str, output_path: str) -> str:
    """
    Generate a basic wireframe SVG from a prompt.

    Creates a page layout with standard UI sections: header, navigation,
    content area, sidebar, and footer.

    Args:
        config: Resolved workflow config dict.
        prompt: Description of the wireframe (e.g., "blog page with sidebar").
        output_path: Path to write the SVG file.

    Returns:
        Absolute path to the generated SVG file.
    """
    vector_cfg = config.get("vector", {})
    stroke_weight = vector_cfg.get("stroke_weight", 1.5)
    corner_radius = vector_cfg.get("corner_radius", 4)
    palette = resolve_palette(config)

    prompt_lower = prompt.lower()

    # Page dimensions
    page_w, page_h = 800, 600
    padding = 16
    gap = 8

    # Determine layout variant
    has_sidebar = any(w in prompt_lower for w in ["sidebar", "side", "aside", "two-column"])
    has_hero = any(w in prompt_lower for w in ["hero", "banner", "landing"])

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{page_w}px", f"{page_h}px"),
        viewBox=f"0 0 {page_w} {page_h}",
    )

    style_text = _build_palette_css(palette)
    dwg.defs.add(dwg.style(style_text))

    wire_group = dwg.g(id="wireframe")

    # Background
    bg_group = dwg.g(id="wireframe-background")
    bg_group.add(dwg.rect(
        insert=(0, 0), size=(page_w, page_h),
        fill="#F9FAFB", stroke=palette.get("neutral", "#ccc"), stroke_width=1,
    ))
    wire_group.add(bg_group)

    # Header
    header_h = 50
    header_group = dwg.g(id="wireframe-header")
    header_group.add(dwg.rect(
        insert=(padding, padding), size=(page_w - 2 * padding, header_h),
        rx=corner_radius, ry=corner_radius,
        fill=palette["background"], stroke=palette.get("neutral", "#ccc"),
        stroke_width=stroke_weight,
    ))
    # Logo placeholder
    header_group.add(dwg.rect(
        insert=(padding + 12, padding + 12), size=(80, 26),
        rx=4, ry=4, fill=palette["primary"], opacity=0.2,
    ))
    header_group.add(dwg.text(
        "LOGO", insert=(padding + 52, padding + 30),
        text_anchor="middle", font_size="10px",
        font_family="system-ui, sans-serif", font_weight="600",
        fill=palette["primary"],
    ))
    # Nav placeholders
    nav_x = padding + 120
    for i, label in enumerate(["Home", "About", "Services", "Contact"]):
        header_group.add(dwg.text(
            label, insert=(nav_x + i * 80, padding + 30),
            font_size="11px", font_family="system-ui, sans-serif",
            font_weight="400", fill=palette.get("neutral", "#666"),
        ))
    wire_group.add(header_group)

    # Content area starts after header
    content_y = padding + header_h + gap
    content_h = page_h - content_y - padding - 50 - gap  # Leave room for footer
    content_w = page_w - 2 * padding

    if has_hero:
        # Hero section
        hero_h = 180
        hero_group = dwg.g(id="wireframe-hero")
        hero_group.add(dwg.rect(
            insert=(padding, content_y), size=(content_w, hero_h),
            rx=corner_radius, ry=corner_radius,
            fill=palette["primary"], opacity=0.08,
            stroke=palette["primary"], stroke_width=stroke_weight, stroke_opacity=0.3,
        ))
        # Placeholder heading
        hero_group.add(dwg.text(
            "Hero Headline",
            insert=(page_w / 2, content_y + 60),
            text_anchor="middle", font_size="28px",
            font_family="system-ui, sans-serif", font_weight="700",
            fill=palette.get("neutral", "#999"), opacity=0.4,
        ))
        # Placeholder subtext
        for i in range(2):
            hero_group.add(dwg.rect(
                insert=(page_w / 2 - 120, content_y + 85 + i * 16),
                size=(240, 10), rx=2, ry=2,
                fill=palette.get("neutral", "#ccc"), opacity=0.2,
            ))
        # CTA button placeholder
        hero_group.add(dwg.rect(
            insert=(page_w / 2 - 60, content_y + 130),
            size=(120, 32), rx=6, ry=6,
            fill=palette["primary"], opacity=0.3,
        ))
        hero_group.add(dwg.text(
            "CTA Button",
            insert=(page_w / 2, content_y + 150),
            text_anchor="middle", font_size="11px",
            font_family="system-ui, sans-serif", font_weight="500",
            fill=palette["primary"], opacity=0.6,
        ))
        wire_group.add(hero_group)
        content_y += hero_h + gap
        content_h -= hero_h + gap

    if has_sidebar:
        # Two-column layout
        sidebar_w = 200
        main_w = content_w - sidebar_w - gap

        # Main content
        main_group = dwg.g(id="wireframe-main")
        main_group.add(dwg.rect(
            insert=(padding, content_y), size=(main_w, content_h),
            rx=corner_radius, ry=corner_radius,
            fill=palette["background"], stroke=palette.get("neutral", "#ccc"),
            stroke_width=stroke_weight,
        ))
        # Content placeholders (lines)
        for i in range(8):
            line_w = main_w * (0.9 if i % 3 != 2 else 0.6) - 40
            main_group.add(dwg.rect(
                insert=(padding + 20, content_y + 20 + i * 22),
                size=(line_w, 10), rx=2, ry=2,
                fill=palette.get("neutral", "#ccc"), opacity=0.2,
            ))
        wire_group.add(main_group)

        # Sidebar
        sidebar_group = dwg.g(id="wireframe-sidebar")
        sidebar_x = padding + main_w + gap
        sidebar_group.add(dwg.rect(
            insert=(sidebar_x, content_y), size=(sidebar_w, content_h),
            rx=corner_radius, ry=corner_radius,
            fill=palette["background"], stroke=palette.get("neutral", "#ccc"),
            stroke_width=stroke_weight,
        ))
        # Sidebar content placeholders
        for i in range(4):
            sidebar_group.add(dwg.rect(
                insert=(sidebar_x + 16, content_y + 20 + i * 50),
                size=(sidebar_w - 32, 36), rx=4, ry=4,
                fill=palette.get("neutral", "#ccc"), opacity=0.1,
                stroke=palette.get("neutral", "#ccc"), stroke_width=0.5,
            ))
        wire_group.add(sidebar_group)

    else:
        # Single-column layout
        main_group = dwg.g(id="wireframe-main")
        main_group.add(dwg.rect(
            insert=(padding, content_y), size=(content_w, content_h),
            rx=corner_radius, ry=corner_radius,
            fill=palette["background"], stroke=palette.get("neutral", "#ccc"),
            stroke_width=stroke_weight,
        ))
        # Content card placeholders
        card_w = (content_w - gap * 3) / 3
        for i in range(3):
            card_x = padding + gap + i * (card_w + gap)
            main_group.add(dwg.rect(
                insert=(card_x, content_y + 20),
                size=(card_w - gap, content_h - 40), rx=corner_radius, ry=corner_radius,
                fill=palette.get("neutral", "#ccc"), opacity=0.06,
                stroke=palette.get("neutral", "#ccc"), stroke_width=0.5,
            ))
            # Image placeholder
            main_group.add(dwg.rect(
                insert=(card_x + 8, content_y + 28),
                size=(card_w - gap - 16, 80), rx=4, ry=4,
                fill=palette.get("neutral", "#ccc"), opacity=0.15,
            ))
            # Text placeholders
            for j in range(3):
                lw = (card_w - gap - 32) * (0.9 if j < 2 else 0.5)
                main_group.add(dwg.rect(
                    insert=(card_x + 8, content_y + 120 + j * 16),
                    size=(lw, 8), rx=2, ry=2,
                    fill=palette.get("neutral", "#ccc"), opacity=0.2,
                ))
        wire_group.add(main_group)

    # Footer
    footer_y = page_h - padding - 40
    footer_group = dwg.g(id="wireframe-footer")
    footer_group.add(dwg.rect(
        insert=(padding, footer_y), size=(page_w - 2 * padding, 40),
        rx=corner_radius, ry=corner_radius,
        fill=palette["background"], stroke=palette.get("neutral", "#ccc"),
        stroke_width=stroke_weight,
    ))
    footer_group.add(dwg.text(
        "Footer", insert=(page_w / 2, footer_y + 24),
        text_anchor="middle", font_size="11px",
        font_family="system-ui, sans-serif", font_weight="400",
        fill=palette.get("neutral", "#999"),
    ))
    wire_group.add(footer_group)

    dwg.add(wire_group)
    dwg.save()

    return os.path.abspath(output_path)


def generate_badge(config: dict[str, Any], prompt: str, output_path: str) -> str:
    """
    Generate a badge/emblem SVG from a prompt.

    Creates circular or shield-shaped badges with text elements and borders.

    Args:
        config: Resolved workflow config dict.
        prompt: Description of the badge (e.g., "Premium Member gold badge").
        output_path: Path to write the SVG file.

    Returns:
        Absolute path to the generated SVG file.
    """
    vector_cfg = config.get("vector", {})
    stroke_weight = vector_cfg.get("stroke_weight", 2)
    palette = resolve_palette(config)

    # Parse badge content from prompt
    badge_text, subtitle = _parse_badge_text(prompt)

    badge_size = 200
    cx, cy = badge_size / 2, badge_size / 2
    outer_r = 90
    inner_r = 78

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{badge_size}px", f"{badge_size}px"),
        viewBox=f"0 0 {badge_size} {badge_size}",
    )

    style_text = _build_palette_css(palette)
    dwg.defs.add(dwg.style(style_text))

    badge_group = dwg.g(id="badge")

    # Outer circle border
    border_group = dwg.g(id="badge-border")
    border_group.add(dwg.circle(
        center=(cx, cy),
        r=outer_r,
        fill=palette["primary"],
        stroke=palette["foreground"],
        stroke_width=stroke_weight,
    ))
    badge_group.add(border_group)

    # Inner circle
    inner_group = dwg.g(id="badge-inner")
    inner_group.add(dwg.circle(
        center=(cx, cy),
        r=inner_r,
        fill=palette["background"],
        stroke=palette["primary"],
        stroke_width=stroke_weight * 0.5,
    ))
    badge_group.add(inner_group)

    # Decorative ring
    ring_group = dwg.g(id="badge-ring")
    ring_group.add(dwg.circle(
        center=(cx, cy),
        r=(outer_r + inner_r) / 2,
        fill="none",
        stroke=palette["accent"],
        stroke_width=1,
        stroke_dasharray="4,4",
    ))
    badge_group.add(ring_group)

    # Main text
    text_group = dwg.g(id="badge-text")
    main_text = dwg.text(
        badge_text,
        insert=(cx, cy - 5),
        text_anchor="middle",
        dominant_baseline="middle",
        font_size="18px",
        font_family="system-ui, -apple-system, sans-serif",
        font_weight="700",
        fill=palette["foreground"],
    )
    main_text["class"] = "badge-title"
    text_group.add(main_text)

    # Subtitle text
    if subtitle:
        sub_text = dwg.text(
            subtitle,
            insert=(cx, cy + 20),
            text_anchor="middle",
            dominant_baseline="middle",
            font_size="10px",
            font_family="system-ui, -apple-system, sans-serif",
            font_weight="400",
            fill=palette["neutral"],
        )
        sub_text["class"] = "badge-subtitle"
        text_group.add(sub_text)

    badge_group.add(text_group)

    # Small decorative stars at top
    deco_group = dwg.g(id="badge-decoration")
    for angle_offset in [-30, 0, 30]:
        angle_rad = math.radians(-90 + angle_offset)
        star_x = cx + (inner_r - 15) * math.cos(angle_rad)
        star_y = cy + (inner_r - 15) * math.sin(angle_rad)
        _draw_small_star(dwg, deco_group, star_x, star_y, 4, palette["accent"])
    badge_group.add(deco_group)

    dwg.add(badge_group)
    dwg.save()

    return os.path.abspath(output_path)


# ---------------------------------------------------------------------------
# Icon shape drawing helpers
# ---------------------------------------------------------------------------

def _draw_icon_shape(
    dwg: Drawing,
    group: Group,
    name: str,
    w: float,
    h: float,
    stroke_weight: float,
    corner_radius: float,
    style: str,
    palette: dict[str, str],
) -> None:
    """
    Draw an icon shape into the given group.

    Dispatches to the appropriate shape function based on name. Falls back
    to a generic placeholder if the icon name is not recognized.
    """
    method_name = ICON_SHAPES.get(name)
    if method_name and method_name in globals():
        globals()[method_name](dwg, group, w, h, stroke_weight, corner_radius, style, palette)
    else:
        _draw_icon_placeholder(dwg, group, name, w, h, stroke_weight, style, palette)


def _icon_stroke_and_fill(style: str, palette: dict[str, str]) -> tuple[str, str]:
    """Return (stroke_color, fill_color) based on icon style."""
    if style == "filled":
        return palette["primary"], palette["primary"]
    elif style == "duotone":
        return palette["primary"], palette["primary"]
    else:  # "line" default
        return palette["foreground"], "none"


def _draw_icon_home(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    m = 4  # margin
    # House body
    g.add(dwg.rect(
        insert=(m + 2, h / 2),
        size=(w - 2 * m - 4, h / 2 - m),
        rx=cr, ry=cr,
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
        stroke_linecap="round", stroke_linejoin="round",
    ))
    # Roof
    g.add(dwg.polyline(
        points=[(m, h / 2), (w / 2, m + 2), (w - m, h / 2)],
        fill="none", stroke=stroke, stroke_width=sw,
        stroke_linecap="round", stroke_linejoin="round",
    ))
    # Door
    g.add(dwg.rect(
        insert=(w / 2 - 2, h / 2 + 3),
        size=(4, h / 2 - m - 3),
        fill=stroke if style != "line" else "none",
        stroke=stroke, stroke_width=sw * 0.6,
    ))


def _draw_icon_search(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    m = 4
    cx, cy, r = w / 2 - 1, h / 2 - 1, min(w, h) / 2 - m - 2
    g.add(dwg.circle(
        center=(cx, cy), r=r,
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
    ))
    # Handle
    hx = cx + r * 0.7
    hy = cy + r * 0.7
    g.add(dwg.line(
        start=(hx, hy), end=(w - m, h - m),
        stroke=stroke, stroke_width=sw,
        stroke_linecap="round",
    ))


def _draw_icon_settings(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    cx, cy = w / 2, h / 2
    r_outer = min(w, h) / 2 - 4
    r_inner = r_outer * 0.55
    # Gear teeth (8 teeth around circle)
    g.add(dwg.circle(
        center=(cx, cy), r=r_inner,
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
    ))
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + r_inner * 0.9 * math.cos(angle)
        y1 = cy + r_inner * 0.9 * math.sin(angle)
        x2 = cx + r_outer * math.cos(angle)
        y2 = cy + r_outer * math.sin(angle)
        g.add(dwg.line(
            start=(x1, y1), end=(x2, y2),
            stroke=stroke, stroke_width=sw,
            stroke_linecap="round",
        ))
    # Center dot
    g.add(dwg.circle(
        center=(cx, cy), r=2,
        fill=stroke,
    ))


def _draw_icon_profile(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    cx = w / 2
    # Head
    g.add(dwg.circle(
        center=(cx, h * 0.35), r=min(w, h) * 0.18,
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
    ))
    # Body arc
    g.add(dwg.ellipse(
        center=(cx, h * 0.85), r=(w * 0.35, h * 0.22),
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
    ))


def _draw_icon_menu(dwg, g, w, h, sw, cr, style, pal):
    stroke, _ = _icon_stroke_and_fill(style, pal)
    m = 5
    for i, frac in enumerate([0.3, 0.5, 0.7]):
        y = h * frac
        g.add(dwg.line(
            start=(m, y), end=(w - m, y),
            stroke=stroke, stroke_width=sw,
            stroke_linecap="round",
        ))


def _draw_icon_heart(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    if style == "filled":
        fill = pal.get("error", pal["primary"])
        stroke = fill
    cx = w / 2
    # Heart using path
    s = min(w, h) * 0.4
    d = (
        f"M {cx},{h * 0.35 + s * 0.8} "
        f"C {cx - s},{h * 0.35 - s * 0.2} {cx - s * 1.2},{h * 0.35 + s * 0.3} {cx},{h * 0.35 + s * 0.8} "
        f"C {cx + s * 1.2},{h * 0.35 + s * 0.3} {cx + s},{h * 0.35 - s * 0.2} {cx},{h * 0.35 + s * 0.8} Z"
    )
    g.add(dwg.path(
        d=d,
        fill=fill if style != "line" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
        stroke_linejoin="round",
    ))


def _draw_icon_star(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    if style == "filled":
        fill = pal.get("accent", pal["primary"])
        stroke = fill
    cx, cy = w / 2, h / 2
    r_outer = min(w, h) / 2 - 4
    r_inner = r_outer * 0.45
    points = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        r = r_outer if i % 2 == 0 else r_inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    g.add(dwg.polygon(
        points=points,
        fill=fill if style != "line" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
        stroke_linejoin="round",
    ))


def _draw_icon_mail(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    m = 4
    g.add(dwg.rect(
        insert=(m, m + 3), size=(w - 2 * m, h - 2 * m - 3),
        rx=cr, ry=cr,
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
    ))
    # Envelope flap
    g.add(dwg.polyline(
        points=[(m, m + 3), (w / 2, h / 2 + 1), (w - m, m + 3)],
        fill="none", stroke=stroke, stroke_width=sw,
        stroke_linecap="round", stroke_linejoin="round",
    ))


def _draw_icon_bell(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    cx = w / 2
    m = 4
    # Bell body
    bw = w - 2 * m - 2
    bh = h * 0.55
    g.add(dwg.rect(
        insert=(m + 1, m + 2), size=(bw, bh),
        rx=bw / 2, ry=bw / 4,
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
    ))
    # Base
    g.add(dwg.line(
        start=(m - 1, m + 2 + bh), end=(w - m + 1, m + 2 + bh),
        stroke=stroke, stroke_width=sw, stroke_linecap="round",
    ))
    # Clapper
    g.add(dwg.circle(
        center=(cx, h - m - 1), r=2,
        fill=stroke,
    ))


def _draw_icon_lock(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    m = 5
    cx = w / 2
    body_top = h * 0.45
    # Lock body
    g.add(dwg.rect(
        insert=(m, body_top), size=(w - 2 * m, h - body_top - m),
        rx=cr, ry=cr,
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
    ))
    # Shackle
    r = (w - 2 * m) / 2 - 3
    g.add(dwg.path(
        d=f"M {cx - r},{body_top} A {r},{r} 0 0 1 {cx + r},{body_top}",
        fill="none", stroke=stroke, stroke_width=sw,
        stroke_linecap="round",
    ))
    # Keyhole
    g.add(dwg.circle(
        center=(cx, body_top + (h - body_top - m) * 0.4), r=2,
        fill=stroke,
    ))


def _draw_icon_plus(dwg, g, w, h, sw, cr, style, pal):
    stroke, _ = _icon_stroke_and_fill(style, pal)
    cx, cy = w / 2, h / 2
    arm = min(w, h) / 2 - 6
    g.add(dwg.line(start=(cx, cy - arm), end=(cx, cy + arm), stroke=stroke, stroke_width=sw, stroke_linecap="round"))
    g.add(dwg.line(start=(cx - arm, cy), end=(cx + arm, cy), stroke=stroke, stroke_width=sw, stroke_linecap="round"))


def _draw_icon_check(dwg, g, w, h, sw, cr, style, pal):
    stroke, _ = _icon_stroke_and_fill(style, pal)
    if style == "filled":
        stroke = pal.get("success", pal["primary"])
    m = 5
    g.add(dwg.polyline(
        points=[(m + 1, h / 2), (w * 0.4, h - m - 2), (w - m - 1, m + 2)],
        fill="none", stroke=stroke, stroke_width=sw,
        stroke_linecap="round", stroke_linejoin="round",
    ))


def _draw_icon_close(dwg, g, w, h, sw, cr, style, pal):
    stroke, _ = _icon_stroke_and_fill(style, pal)
    m = 6
    g.add(dwg.line(start=(m, m), end=(w - m, h - m), stroke=stroke, stroke_width=sw, stroke_linecap="round"))
    g.add(dwg.line(start=(w - m, m), end=(m, h - m), stroke=stroke, stroke_width=sw, stroke_linecap="round"))


def _draw_icon_arrow_right(dwg, g, w, h, sw, cr, style, pal):
    stroke, _ = _icon_stroke_and_fill(style, pal)
    m = 5
    cy = h / 2
    g.add(dwg.line(start=(m, cy), end=(w - m, cy), stroke=stroke, stroke_width=sw, stroke_linecap="round"))
    g.add(dwg.polyline(
        points=[(w - m - 5, cy - 5), (w - m, cy), (w - m - 5, cy + 5)],
        fill="none", stroke=stroke, stroke_width=sw,
        stroke_linecap="round", stroke_linejoin="round",
    ))


def _draw_icon_arrow_left(dwg, g, w, h, sw, cr, style, pal):
    stroke, _ = _icon_stroke_and_fill(style, pal)
    m = 5
    cy = h / 2
    g.add(dwg.line(start=(m, cy), end=(w - m, cy), stroke=stroke, stroke_width=sw, stroke_linecap="round"))
    g.add(dwg.polyline(
        points=[(m + 5, cy - 5), (m, cy), (m + 5, cy + 5)],
        fill="none", stroke=stroke, stroke_width=sw,
        stroke_linecap="round", stroke_linejoin="round",
    ))


def _draw_icon_edit(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    m = 4
    # Pencil body
    g.add(dwg.polygon(
        points=[(m + 2, h - m - 2), (m + 4, h - m - 6), (w - m - 2, m + 4), (w - m - 4, m + 2)],
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
        stroke_linejoin="round",
    ))
    # Pencil tip
    g.add(dwg.line(
        start=(m, h - m), end=(m + 2, h - m - 2),
        stroke=stroke, stroke_width=sw, stroke_linecap="round",
    ))


def _draw_icon_trash(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    m = 5
    top = m + 3
    # Can body
    g.add(dwg.rect(
        insert=(m + 1, top + 2), size=(w - 2 * m - 2, h - top - m - 2),
        rx=cr, ry=cr,
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
    ))
    # Lid
    g.add(dwg.line(start=(m - 1, top), end=(w - m + 1, top), stroke=stroke, stroke_width=sw, stroke_linecap="round"))
    # Handle
    g.add(dwg.line(start=(w * 0.38, top), end=(w * 0.38, m), stroke=stroke, stroke_width=sw, stroke_linecap="round"))
    g.add(dwg.line(start=(w * 0.62, top), end=(w * 0.62, m), stroke=stroke, stroke_width=sw, stroke_linecap="round"))
    g.add(dwg.line(start=(w * 0.38, m), end=(w * 0.62, m), stroke=stroke, stroke_width=sw, stroke_linecap="round"))


def _draw_icon_download(dwg, g, w, h, sw, cr, style, pal):
    stroke, _ = _icon_stroke_and_fill(style, pal)
    cx = w / 2
    m = 5
    # Arrow down
    g.add(dwg.line(start=(cx, m), end=(cx, h * 0.6), stroke=stroke, stroke_width=sw, stroke_linecap="round"))
    g.add(dwg.polyline(
        points=[(cx - 5, h * 0.6 - 5), (cx, h * 0.6), (cx + 5, h * 0.6 - 5)],
        fill="none", stroke=stroke, stroke_width=sw, stroke_linecap="round", stroke_linejoin="round",
    ))
    # Tray
    g.add(dwg.polyline(
        points=[(m, h * 0.55), (m, h - m), (w - m, h - m), (w - m, h * 0.55)],
        fill="none", stroke=stroke, stroke_width=sw, stroke_linecap="round", stroke_linejoin="round",
    ))


def _draw_icon_upload(dwg, g, w, h, sw, cr, style, pal):
    stroke, _ = _icon_stroke_and_fill(style, pal)
    cx = w / 2
    m = 5
    # Arrow up
    g.add(dwg.line(start=(cx, h * 0.6), end=(cx, m), stroke=stroke, stroke_width=sw, stroke_linecap="round"))
    g.add(dwg.polyline(
        points=[(cx - 5, m + 5), (cx, m), (cx + 5, m + 5)],
        fill="none", stroke=stroke, stroke_width=sw, stroke_linecap="round", stroke_linejoin="round",
    ))
    # Tray
    g.add(dwg.polyline(
        points=[(m, h * 0.55), (m, h - m), (w - m, h - m), (w - m, h * 0.55)],
        fill="none", stroke=stroke, stroke_width=sw, stroke_linecap="round", stroke_linejoin="round",
    ))


def _draw_icon_share(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    m = 5
    # Three nodes
    nodes = [(w - m - 2, m + 3), (m + 2, h / 2), (w - m - 2, h - m - 3)]
    for nx, ny in nodes:
        g.add(dwg.circle(
            center=(nx, ny), r=3,
            fill=fill if style == "filled" else "none",
            fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
            stroke=stroke, stroke_width=sw,
        ))
    # Lines connecting
    g.add(dwg.line(start=nodes[0], end=nodes[1], stroke=stroke, stroke_width=sw * 0.7))
    g.add(dwg.line(start=nodes[1], end=nodes[2], stroke=stroke, stroke_width=sw * 0.7))


def _draw_icon_calendar(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    m = 4
    top = m + 4
    # Body
    g.add(dwg.rect(
        insert=(m, top), size=(w - 2 * m, h - top - m),
        rx=cr, ry=cr,
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
    ))
    # Header line
    g.add(dwg.line(start=(m, top + 6), end=(w - m, top + 6), stroke=stroke, stroke_width=sw * 0.6))
    # Hangers
    for x_off in [0.3, 0.7]:
        x = w * x_off
        g.add(dwg.line(start=(x, m), end=(x, top + 2), stroke=stroke, stroke_width=sw, stroke_linecap="round"))


def _draw_icon_clock(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    cx, cy = w / 2, h / 2
    r = min(w, h) / 2 - 4
    g.add(dwg.circle(
        center=(cx, cy), r=r,
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
    ))
    # Hour hand
    g.add(dwg.line(start=(cx, cy), end=(cx, cy - r * 0.45), stroke=stroke, stroke_width=sw, stroke_linecap="round"))
    # Minute hand
    g.add(dwg.line(start=(cx, cy), end=(cx + r * 0.55, cy), stroke=stroke, stroke_width=sw * 0.7, stroke_linecap="round"))
    # Center dot
    g.add(dwg.circle(center=(cx, cy), r=1.5, fill=stroke))


def _draw_icon_folder(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    m = 4
    # Folder body
    tab_w = w * 0.4
    tab_h = 4
    g.add(dwg.polygon(
        points=[
            (m, m + tab_h), (m, h - m), (w - m, h - m),
            (w - m, m + tab_h), (m + tab_w + 2, m + tab_h),
            (m + tab_w, m), (m, m), (m, m + tab_h),
        ],
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
        stroke_linejoin="round",
    ))


def _draw_icon_image(dwg, g, w, h, sw, cr, style, pal):
    stroke, fill = _icon_stroke_and_fill(style, pal)
    m = 4
    g.add(dwg.rect(
        insert=(m, m), size=(w - 2 * m, h - 2 * m),
        rx=cr, ry=cr,
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
    ))
    # Mountain
    g.add(dwg.polyline(
        points=[(m + 2, h - m - 2), (w * 0.35, h * 0.45), (w * 0.55, h * 0.6), (w - m - 2, h * 0.35)],
        fill="none", stroke=stroke, stroke_width=sw * 0.7,
        stroke_linejoin="round",
    ))
    # Sun
    g.add(dwg.circle(center=(w * 0.7, h * 0.3), r=3, fill=stroke))


def _draw_icon_placeholder(dwg, g, name, w, h, sw, style, pal):
    """Fallback: draw a rounded rect with the first letter of the icon name."""
    stroke, fill = _icon_stroke_and_fill(style, pal)
    m = 3
    g.add(dwg.rect(
        insert=(m, m), size=(w - 2 * m, h - 2 * m),
        rx=4, ry=4,
        fill=fill if style == "filled" else "none",
        fill_opacity=DUOTONE_FILL_OPACITY if style == "duotone" else 1,
        stroke=stroke, stroke_width=sw,
    ))
    letter = name[0].upper() if name else "?"
    g.add(dwg.text(
        letter,
        insert=(w / 2, h / 2 + 3),
        text_anchor="middle",
        font_size="10px",
        font_family="system-ui, -apple-system, sans-serif",
        font_weight="600",
        fill=stroke,
    ))


# ---------------------------------------------------------------------------
# Geometric mark helpers
# ---------------------------------------------------------------------------

def _draw_geometric_mark(
    dwg: Drawing,
    group: Group,
    size: float,
    stroke_weight: float,
    corner_radius: float,
    palette: dict[str, str],
    prompt: str,
) -> None:
    """
    Draw a geometric logo mark based on prompt analysis.

    Creates layered geometric shapes (circles, squares, triangles) with
    the brand's color palette.
    """
    prompt_lower = prompt.lower()

    # Background shape
    if any(word in prompt_lower for word in ["circle", "round", "soft"]):
        group.add(dwg.circle(
            center=(size / 2, size / 2), r=size / 2,
            fill=palette["primary"],
        ))
    elif any(word in prompt_lower for word in ["diamond", "rotate"]):
        group.add(dwg.rect(
            insert=(size * 0.15, size * 0.15),
            size=(size * 0.7, size * 0.7),
            rx=corner_radius, ry=corner_radius,
            fill=palette["primary"],
            transform=f"rotate(45, {size / 2}, {size / 2})",
        ))
    elif any(word in prompt_lower for word in ["hex", "hexagon"]):
        points = []
        for i in range(6):
            angle = math.radians(60 * i - 30)
            points.append((
                size / 2 + size * 0.45 * math.cos(angle),
                size / 2 + size * 0.45 * math.sin(angle),
            ))
        group.add(dwg.polygon(points=points, fill=palette["primary"]))
    else:
        # Default: rounded square
        group.add(dwg.rect(
            insert=(0, 0), size=(size, size),
            rx=corner_radius * 2, ry=corner_radius * 2,
            fill=palette["primary"],
        ))

    # Inner accent shape
    inner_size = size * 0.4
    offset = (size - inner_size) / 2
    group.add(dwg.rect(
        insert=(offset, offset), size=(inner_size, inner_size),
        rx=corner_radius, ry=corner_radius,
        fill=palette["secondary"],
        opacity=0.5,
    ))


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_icon_names(prompt: str) -> list[str]:
    """
    Extract icon names from a prompt string.

    Handles formats like:
      - "home, search, settings, profile"
      - "navigation icons: home, search, settings"
      - "home search settings profile menu"
    """
    # Remove common prefixes
    cleaned = re.sub(
        r"^(navigation|nav|ui|interface|app|icons?|icon\s*set)\s*(icons?|set)?\s*:?\s*",
        "", prompt, flags=re.IGNORECASE,
    )

    # Split by comma, semicolon, or whitespace
    if "," in cleaned:
        parts = [p.strip() for p in cleaned.split(",")]
    elif ";" in cleaned:
        parts = [p.strip() for p in cleaned.split(";")]
    else:
        parts = cleaned.split()

    # Normalize: lowercase, replace spaces/hyphens with underscores
    names = []
    for part in parts:
        name = part.strip().lower()
        name = re.sub(r"[\s-]+", "_", name)
        name = re.sub(r"[^a-z0-9_]", "", name)
        if name:
            names.append(name)

    return names


def _extract_brand_name(prompt: str) -> str:
    """
    Extract a brand name from a logo prompt.

    Looks for patterns like "logo for Acme" or "Acme logo" or quoted names.
    Falls back to the first capitalized word.
    """
    # Check for quoted names
    quoted = re.findall(r'"([^"]+)"', prompt)
    if quoted:
        return quoted[0]

    quoted = re.findall(r"'([^']+)'", prompt)
    if quoted:
        return quoted[0]

    # Pattern: "for <Name>"
    for_match = re.search(r"\bfor\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)", prompt)
    if for_match:
        return for_match.group(1)

    # Pattern: "<Name> logo"
    name_match = re.search(r"([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)\s+logo", prompt, re.IGNORECASE)
    if name_match:
        return name_match.group(1)

    # Fallback: first capitalized word that is not a common word
    skip = {"create", "generate", "make", "design", "modern", "minimal", "logo",
            "geometric", "tech", "startup", "brand", "company", "simple", "clean"}
    words = prompt.split()
    for w in words:
        cleaned = re.sub(r"[^a-zA-Z]", "", w)
        if cleaned and cleaned[0].isupper() and cleaned.lower() not in skip:
            return cleaned

    return "Brand"


def _parse_diagram(prompt: str) -> tuple[list[str], list[tuple[str, str]]]:
    """
    Parse diagram nodes and connections from a prompt.

    Handles formats like:
      - "Client -> API -> Database"
      - "User, Auth, API, Database with connections"
      - "boxes: Input, Process, Output"
    """
    # Look for arrow-connected chains
    if "->" in prompt or "-->" in prompt:
        arrow_pattern = r"\s*-+>\s*"
        chains = re.split(r"[,;]+", prompt)
        all_nodes: list[str] = []
        connections: list[tuple[str, str]] = []

        for chain in chains:
            parts = re.split(arrow_pattern, chain.strip())
            parts = [p.strip() for p in parts if p.strip()]
            for p in parts:
                if p not in all_nodes:
                    all_nodes.append(p)
            for i in range(len(parts) - 1):
                connections.append((parts[i], parts[i + 1]))

        return all_nodes, connections

    # Comma-separated list -- assume sequential connections
    # Remove common prefixes (including multi-word like "API flow:", "data flow:", etc.)
    cleaned = re.sub(
        r"^(\w+\s+)?(diagram|flow|flowchart|process|boxes?|architecture|system|pipeline)\s*:?\s*",
        "", prompt, flags=re.IGNORECASE,
    )
    if "," in cleaned:
        parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    else:
        parts = [p.strip() for p in cleaned.split() if p.strip()]

    # Filter out connecting words
    skip = {"with", "and", "to", "from", "connections", "connecting", "linked"}
    nodes = [p for p in parts if p.lower() not in skip]

    connections = [(nodes[i], nodes[i + 1]) for i in range(len(nodes) - 1)]
    return nodes, connections


def _parse_badge_text(prompt: str) -> tuple[str, str]:
    """
    Parse badge text and subtitle from a prompt.

    Returns (main_text, subtitle).
    """
    # Check for quoted text
    quoted = re.findall(r'"([^"]+)"', prompt)
    if len(quoted) >= 2:
        return quoted[0], quoted[1]
    if len(quoted) == 1:
        return quoted[0], ""

    # Remove common prefixes
    cleaned = re.sub(
        r"^(create|generate|make|design)?\s*(a\s+)?(badge|emblem|seal)\s*(for|of|with)?\s*",
        "", prompt, flags=re.IGNORECASE,
    ).strip()

    # Take first few meaningful words as badge text
    words = cleaned.split()
    if not words:
        return "Badge", ""

    # Capitalize for badge display
    main = " ".join(words[:3]).title()
    subtitle = " ".join(words[3:6]).title() if len(words) > 3 else ""

    return main, subtitle


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _parse_palette_colors(prompt: str, palette: dict[str, str]) -> dict[str, str]:
    """
    Parse colors from a prompt or fall back to the config palette.

    Accepts hex codes in the prompt (e.g., "#FF5733") or named colors.
    Returns an ordered dict of name -> hex_color.
    """
    # Check for hex codes in prompt
    hex_codes = re.findall(r"#[0-9A-Fa-f]{6}", prompt)
    if hex_codes:
        return {f"color_{i + 1}": c for i, c in enumerate(hex_codes)}

    # Fall back to the config palette
    return dict(palette)


def _parse_flowchart(prompt: str) -> list[dict[str, Any]]:
    """
    Parse flowchart nodes from a prompt.

    Supports formats like:
      - "Start -> Check Input -> Valid? -> yes:Process, no:Error -> End"
      - Simple arrow chains: "A -> B -> C"
    """
    if "->" not in prompt and "-->" not in prompt:
        return []

    # Split on arrows
    arrow_pattern = r"\s*-+>\s*"
    parts = re.split(arrow_pattern, prompt.strip())
    parts = [p.strip() for p in parts if p.strip()]

    flow_nodes: list[dict[str, Any]] = []

    for i, part in enumerate(parts):
        # Check if this is a decision node (contains ?)
        if "?" in part:
            # Parse yes/no branches
            label = part
            yes_branch = ""
            no_branch = ""

            # Look for "yes:X, no:Y" in the next part
            if i + 1 < len(parts):
                next_part = parts[i + 1]
                yes_match = re.search(r"yes\s*:\s*(\w[\w\s]*)", next_part, re.IGNORECASE)
                no_match = re.search(r"no\s*:\s*(\w[\w\s]*)", next_part, re.IGNORECASE)
                if yes_match:
                    yes_branch = yes_match.group(1).strip()
                if no_match:
                    no_branch = no_match.group(1).strip()

            flow_nodes.append({
                "type": "decision",
                "label": label,
                "yes": yes_branch,
                "no": no_branch,
            })
        elif i == 0:
            flow_nodes.append({"type": "start", "label": part})
        elif i == len(parts) - 1 and "yes:" not in part.lower() and "no:" not in part.lower():
            flow_nodes.append({"type": "end", "label": part})
        elif "yes:" in part.lower() or "no:" in part.lower():
            # This is a branch specification, skip (handled by decision node)
            continue
        else:
            flow_nodes.append({"type": "process", "label": part})

    return flow_nodes


def _slugify(text: str) -> str:
    """Convert text to a URL/ID-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "unnamed"


def _build_palette_css(palette: dict[str, str]) -> str:
    """Build CSS class definitions for the color palette."""
    lines = [":root {"]
    for name, color in palette.items():
        lines.append(f"  --color-{name}: {color};")
    lines.append("}")
    lines.append("")
    for name, color in palette.items():
        lines.append(f".fill-{name} {{ fill: {color}; }}")
        lines.append(f".stroke-{name} {{ stroke: {color}; }}")
    lines.append("")
    lines.append(".icon { cursor: pointer; }")
    lines.append(".icon-label { font-size: 3px; }")
    lines.append(".wordmark { letter-spacing: 0.05em; }")
    lines.append(".monogram { font-weight: 800; }")
    return "\n".join(lines)


def _draw_small_star(dwg: Drawing, group: Group, cx: float, cy: float, r: float, color: str) -> None:
    """Draw a small decorative star."""
    points = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        radius = r if i % 2 == 0 else r * 0.4
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    group.add(dwg.polygon(points=points, fill=color))
