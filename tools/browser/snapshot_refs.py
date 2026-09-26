"""
Snapshot-Based Element Targeting for Huxley Browser Automation

This module provides accessibility tree-based element refs that are more robust
than CSS selectors. Based on example-agent's superior browser targeting pattern.

Key Features:
- Generate accessibility tree snapshots from Playwright pages
- Assign numeric refs (e.g., e1, e2) to interactive elements
- Support both AI format (natural language + refs) and Role format (structured tree)
- Frame-scoped refs for iframe content
- Cached snapshots with TTL for performance
- Seamless integration with existing Playwright MCP tools

Usage:
    from tools.browser.snapshot_refs import SnapshotRefs

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://example.com")

        # Create snapshot manager for this page
        refs = SnapshotRefs(page)

        # Take snapshot and get refs
        snapshot = await refs.snapshot()
        print(snapshot.text)  # Human-readable accessibility tree with refs
        print(snapshot.refs)  # Dict mapping ref IDs to element info

        # Interact using refs
        await refs.click("e1")
        await refs.type("e2", "Hello World")

        # Get element details
        info = await refs.get_element_info("e3")
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional, Union

from playwright.async_api import Page, Locator, FrameLocator


# Interactive roles that should get refs assigned
INTERACTIVE_ROLES = frozenset([
    "button",
    "link",
    "textbox",
    "checkbox",
    "radio",
    "combobox",
    "listbox",
    "menuitem",
    "menuitemcheckbox",
    "menuitemradio",
    "option",
    "searchbox",
    "slider",
    "spinbutton",
    "switch",
    "tab",
    "treeitem",
])

# Content roles that may get refs if they have names
CONTENT_ROLES = frozenset([
    "heading",
    "cell",
    "gridcell",
    "columnheader",
    "rowheader",
    "listitem",
    "article",
    "region",
    "main",
    "navigation",
])

# Structural roles (usually filtered out in compact mode)
STRUCTURAL_ROLES = frozenset([
    "generic",
    "group",
    "list",
    "table",
    "row",
    "rowgroup",
    "grid",
    "treegrid",
    "menu",
    "menubar",
    "toolbar",
    "tablist",
    "tree",
    "directory",
    "document",
    "application",
    "presentation",
    "none",
])


class RefMode(Enum):
    """Mode for ref resolution."""
    ROLE = "role"  # Use getByRole with role/name
    ARIA = "aria"  # Use aria-ref attribute directly


@dataclass
class RoleRef:
    """Reference to an element by its accessibility role."""
    role: str
    name: Optional[str] = None
    nth: Optional[int] = None  # Index for duplicate role+name combinations


@dataclass
class SnapshotOptions:
    """Options for snapshot generation."""
    interactive_only: bool = False  # Only include interactive elements
    max_depth: Optional[int] = None  # Maximum depth to include
    compact: bool = False  # Remove unnamed structural elements
    include_content_roles: bool = True  # Include content roles with names


@dataclass
class SnapshotStats:
    """Statistics about a snapshot."""
    lines: int
    chars: int
    refs: int
    interactive: int


@dataclass
class SnapshotResult:
    """Result of a snapshot operation."""
    text: str
    refs: dict[str, RoleRef]
    stats: SnapshotStats
    frame_selector: Optional[str] = None
    mode: RefMode = RefMode.ROLE
    timestamp: float = field(default_factory=time.time)

    @property
    def is_stale(self) -> bool:
        """Check if snapshot is older than default TTL (60 seconds)."""
        return time.time() - self.timestamp > 60.0


@dataclass
class ElementInfo:
    """Detailed information about an element."""
    ref: str
    role: str
    name: Optional[str]
    visible: bool
    enabled: bool
    checked: Optional[bool]
    focused: bool
    bounding_box: Optional[dict[str, float]]
    text_content: Optional[str]
    input_value: Optional[str]
    attributes: dict[str, str]


class SnapshotRefs:
    """
    Snapshot-based element targeting for Playwright pages.

    This class manages accessibility tree snapshots and provides
    ref-based element targeting that is more robust than CSS selectors.
    """

    def __init__(
        self,
        page: Page,
        cache_ttl: float = 60.0,
        default_timeout: float = 8000.0,
    ):
        """
        Initialize SnapshotRefs for a Playwright page.

        Args:
            page: Playwright Page object
            cache_ttl: Time-to-live for cached snapshots in seconds
            default_timeout: Default timeout for operations in milliseconds
        """
        self.page = page
        self.cache_ttl = cache_ttl
        self.default_timeout = default_timeout

        # Cached snapshot data
        self._cached_snapshot: Optional[SnapshotResult] = None
        self._refs: dict[str, RoleRef] = {}
        self._mode: RefMode = RefMode.ROLE
        self._frame_selector: Optional[str] = None

    def _get_indent_level(self, line: str) -> int:
        """Get indentation level from a line (2 spaces per level)."""
        match = re.match(r'^(\s*)', line)
        return len(match.group(1)) // 2 if match else 0

    def _parse_aria_line(self, line: str) -> tuple[Optional[str], Optional[str], str]:
        """
        Parse an aria snapshot line into role, name, and suffix.

        Returns:
            Tuple of (role, name, suffix) or (None, None, line) if not parseable
        """
        # Match pattern: "  - role "name" [attrs]" or "  - role [attrs]"
        match = re.match(r'^(\s*-\s*)(\w+)(?:\s+"([^"]*)")?(.*)$', line)
        if not match:
            return None, None, line

        prefix, role_raw, name, suffix = match.groups()

        # Skip closing tags like "/list"
        if role_raw.startswith('/'):
            return None, None, line

        role = role_raw.lower()
        return role, name, suffix

    def _parse_ai_snapshot_ref(self, suffix: str) -> Optional[str]:
        """Extract ref ID from AI snapshot suffix like '[ref=e13]'."""
        match = re.search(r'\[ref=(e\d+)\]', suffix, re.IGNORECASE)
        return match.group(1) if match else None

    def _build_role_snapshot(
        self,
        aria_snapshot: str,
        options: SnapshotOptions,
    ) -> SnapshotResult:
        """
        Build a role snapshot from Playwright's ariaSnapshot output.

        This assigns numeric refs (e1, e2, etc.) to interactive elements.
        """
        lines = aria_snapshot.split('\n')
        refs: dict[str, RoleRef] = {}
        result_lines: list[str] = []

        # Track role+name combinations for nth indexing
        role_name_counts: dict[str, int] = {}
        role_name_refs: dict[str, list[str]] = {}

        ref_counter = 0

        def get_next_ref() -> str:
            nonlocal ref_counter
            ref_counter += 1
            return f"e{ref_counter}"

        def get_role_name_key(role: str, name: Optional[str]) -> str:
            return f"{role}:{name or ''}"

        for line in lines:
            depth = self._get_indent_level(line)

            # Check max depth
            if options.max_depth is not None and depth > options.max_depth:
                continue

            role, name, suffix = self._parse_aria_line(line)

            if role is None:
                if not options.interactive_only:
                    result_lines.append(line)
                continue

            is_interactive = role in INTERACTIVE_ROLES
            is_content = role in CONTENT_ROLES
            is_structural = role in STRUCTURAL_ROLES

            # Apply filters
            if options.interactive_only and not is_interactive:
                continue

            if options.compact and is_structural and not name:
                continue

            # Determine if element should get a ref
            should_have_ref = is_interactive or (
                options.include_content_roles and is_content and name
            )

            if not should_have_ref:
                result_lines.append(line)
                continue

            # Assign ref
            ref = get_next_ref()
            key = get_role_name_key(role, name)

            # Track nth index for duplicates
            nth = role_name_counts.get(key, 0)
            role_name_counts[key] = nth + 1

            if key not in role_name_refs:
                role_name_refs[key] = []
            role_name_refs[key].append(ref)

            refs[ref] = RoleRef(role=role, name=name, nth=nth)

            # Build enhanced line
            prefix_match = re.match(r'^(\s*-\s*)', line)
            prefix = prefix_match.group(1) if prefix_match else "- "

            enhanced = f"{prefix}{role}"
            if name:
                enhanced += f' "{name}"'
            enhanced += f" [ref={ref}]"
            if nth > 0:
                enhanced += f" [nth={nth}]"

            # Preserve any existing attributes in suffix
            if '[' in suffix and 'ref=' not in suffix.lower():
                enhanced += suffix

            result_lines.append(enhanced)

        # Remove nth from non-duplicates for cleaner output
        for key, ref_list in role_name_refs.items():
            if len(ref_list) == 1:
                ref_id = ref_list[0]
                if ref_id in refs:
                    refs[ref_id].nth = None

        # Apply compaction if requested
        snapshot_text = '\n'.join(result_lines) or "(empty)"
        if options.compact:
            snapshot_text = self._compact_tree(snapshot_text)

        # Calculate stats
        interactive_count = sum(
            1 for r in refs.values() if r.role in INTERACTIVE_ROLES
        )
        stats = SnapshotStats(
            lines=len(result_lines),
            chars=len(snapshot_text),
            refs=len(refs),
            interactive=interactive_count,
        )

        return SnapshotResult(
            text=snapshot_text,
            refs=refs,
            stats=stats,
            mode=RefMode.ROLE,
        )

    def _build_ai_snapshot(
        self,
        ai_snapshot: str,
        options: SnapshotOptions,
    ) -> SnapshotResult:
        """
        Build a role snapshot from Playwright's AI snapshot output.

        This preserves Playwright's own aria-ref IDs (e.g., ref=e13)
        making refs self-resolving across calls.
        """
        lines = (ai_snapshot or "").split('\n')
        refs: dict[str, RoleRef] = {}
        result_lines: list[str] = []

        for line in lines:
            depth = self._get_indent_level(line)

            if options.max_depth is not None and depth > options.max_depth:
                continue

            role, name, suffix = self._parse_aria_line(line)

            if role is None:
                if not options.interactive_only:
                    result_lines.append(line)
                continue

            is_interactive = role in INTERACTIVE_ROLES
            is_structural = role in STRUCTURAL_ROLES

            if options.interactive_only and not is_interactive:
                continue

            if options.compact and is_structural and not name:
                continue

            # Extract existing ref from AI snapshot
            ref = self._parse_ai_snapshot_ref(suffix)
            if ref:
                refs[ref] = RoleRef(role=role, name=name)

            result_lines.append(line)

        snapshot_text = '\n'.join(result_lines) or "(no interactive elements)"
        if options.compact:
            snapshot_text = self._compact_tree(snapshot_text)

        interactive_count = sum(
            1 for r in refs.values() if r.role in INTERACTIVE_ROLES
        )
        stats = SnapshotStats(
            lines=len(result_lines),
            chars=len(snapshot_text),
            refs=len(refs),
            interactive=interactive_count,
        )

        return SnapshotResult(
            text=snapshot_text,
            refs=refs,
            stats=stats,
            mode=RefMode.ARIA,
        )

    def _compact_tree(self, tree: str) -> str:
        """
        Remove unnamed structural elements and empty branches.

        Keeps only elements that have refs or lead to elements with refs.
        """
        lines = tree.split('\n')
        result: list[str] = []

        for i, line in enumerate(lines):
            # Always keep lines with refs
            if '[ref=' in line:
                result.append(line)
                continue

            # Keep lines with content (not ending with just colon)
            if ':' in line and not line.rstrip().endswith(':'):
                result.append(line)
                continue

            # Check if this line has relevant children with refs
            current_indent = self._get_indent_level(line)
            has_relevant_children = False

            for j in range(i + 1, len(lines)):
                child_indent = self._get_indent_level(lines[j])
                if child_indent <= current_indent:
                    break
                if '[ref=' in lines[j]:
                    has_relevant_children = True
                    break

            if has_relevant_children:
                result.append(line)

        return '\n'.join(result)

    def _normalize_ref(self, ref: str) -> str:
        """Normalize a ref string to standard format."""
        trimmed = ref.strip()

        # Handle various formats
        if trimmed.startswith('@'):
            trimmed = trimmed[1:]
        elif trimmed.startswith('ref='):
            trimmed = trimmed[4:]

        return trimmed

    def _validate_ref(self, ref: str) -> str:
        """Validate and normalize a ref, raising if invalid."""
        normalized = self._normalize_ref(ref)

        if not re.match(r'^e\d+$', normalized):
            raise ValueError(
                f'Invalid ref format: "{ref}". Expected format like "e1", "e2", etc.'
            )

        if normalized not in self._refs:
            available = ', '.join(sorted(self._refs.keys(), key=lambda x: int(x[1:])))
            raise ValueError(
                f'Unknown ref "{normalized}". '
                f'Run a new snapshot to get valid refs. '
                f'Available refs: {available or "(none)"}'
            )

        return normalized

    def _get_scope(self) -> Union[Page, FrameLocator]:
        """Get the current scope (page or frame)."""
        if self._frame_selector:
            return self.page.frame_locator(self._frame_selector)
        return self.page

    def resolve_ref(self, ref: str) -> Locator:
        """
        Resolve a ref to a Playwright Locator.

        Args:
            ref: Ref string like "e1", "@e1", or "ref=e1"

        Returns:
            Playwright Locator for the element

        Raises:
            ValueError: If ref is invalid or not found
        """
        normalized = self._validate_ref(ref)
        scope = self._get_scope()

        if self._mode == RefMode.ARIA:
            # Use aria-ref attribute selector
            return scope.locator(f'[aria-ref="{normalized}"]')

        # Use getByRole with the stored role info
        role_ref = self._refs[normalized]

        if role_ref.name:
            locator = scope.get_by_role(role_ref.role, name=role_ref.name, exact=True)
        else:
            locator = scope.get_by_role(role_ref.role)

        # Apply nth index if needed
        if role_ref.nth is not None and role_ref.nth > 0:
            locator = locator.nth(role_ref.nth)

        return locator

    async def snapshot(
        self,
        options: Optional[SnapshotOptions] = None,
        frame_selector: Optional[str] = None,
        mode: RefMode = RefMode.ROLE,
        force_refresh: bool = False,
    ) -> SnapshotResult:
        """
        Generate an accessibility tree snapshot with element refs.

        Args:
            options: Snapshot generation options
            frame_selector: CSS selector for iframe to snapshot
            mode: Ref resolution mode (ROLE or ARIA)
            force_refresh: Force regeneration even if cached

        Returns:
            SnapshotResult with text, refs, and stats
        """
        if options is None:
            options = SnapshotOptions()

        # Check cache
        if (
            not force_refresh
            and self._cached_snapshot is not None
            and not self._cached_snapshot.is_stale
            and self._cached_snapshot.frame_selector == frame_selector
            and self._cached_snapshot.mode == mode
        ):
            return self._cached_snapshot

        # Get the target scope
        if frame_selector:
            target = self.page.frame_locator(frame_selector).locator(':root')
        else:
            target = self.page.locator(':root')

        # Generate snapshot
        if mode == RefMode.ARIA:
            # Use internal AI snapshot if available
            try:
                ai_result = await self.page.evaluate('''
                    () => {
                        if (window.__playwright_snapshot_for_ai) {
                            return window.__playwright_snapshot_for_ai();
                        }
                        return null;
                    }
                ''')
                if ai_result:
                    result = self._build_ai_snapshot(ai_result, options)
                else:
                    # Fall back to ariaSnapshot
                    aria_snapshot = await target.aria_snapshot()
                    result = self._build_role_snapshot(aria_snapshot, options)
            except Exception:
                # Fall back to role mode
                aria_snapshot = await target.aria_snapshot()
                result = self._build_role_snapshot(aria_snapshot, options)
        else:
            aria_snapshot = await target.aria_snapshot()
            result = self._build_role_snapshot(aria_snapshot, options)

        # Update result with frame info
        result.frame_selector = frame_selector
        result.mode = mode

        # Update cache
        self._cached_snapshot = result
        self._refs = result.refs
        self._mode = mode
        self._frame_selector = frame_selector

        return result

    async def snapshot_interactive(
        self,
        frame_selector: Optional[str] = None,
    ) -> SnapshotResult:
        """
        Generate a compact snapshot with only interactive elements.

        This is optimized for AI agents that only need actionable elements.
        """
        return await self.snapshot(
            options=SnapshotOptions(interactive_only=True),
            frame_selector=frame_selector,
        )

    async def click(
        self,
        ref: str,
        *,
        double: bool = False,
        button: Literal["left", "right", "middle"] = "left",
        modifiers: Optional[list[str]] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Click an element by ref.

        Args:
            ref: Element ref like "e1"
            double: Whether to double-click
            button: Mouse button to use
            modifiers: Keyboard modifiers (Alt, Control, Meta, Shift)
            timeout: Timeout in milliseconds
        """
        locator = self.resolve_ref(ref)
        timeout_ms = timeout or self.default_timeout

        click_options = {
            "timeout": timeout_ms,
            "button": button,
        }
        if modifiers:
            click_options["modifiers"] = modifiers

        if double:
            await locator.dblclick(**click_options)
        else:
            await locator.click(**click_options)

    async def type(
        self,
        ref: str,
        text: str,
        *,
        clear: bool = True,
        slowly: bool = False,
        submit: bool = False,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Type text into an element by ref.

        Args:
            ref: Element ref like "e1"
            text: Text to type
            clear: Clear existing content first (uses fill)
            slowly: Type character by character with delays
            submit: Press Enter after typing
            timeout: Timeout in milliseconds
        """
        locator = self.resolve_ref(ref)
        timeout_ms = timeout or self.default_timeout

        if slowly:
            await locator.click(timeout=timeout_ms)
            if clear:
                await locator.clear(timeout=timeout_ms)
            await locator.type(text, timeout=timeout_ms, delay=75)
        else:
            if clear:
                await locator.fill(text, timeout=timeout_ms)
            else:
                await locator.click(timeout=timeout_ms)
                await locator.type(text, timeout=timeout_ms)

        if submit:
            await locator.press("Enter", timeout=timeout_ms)

    async def fill(
        self,
        ref: str,
        text: str,
        *,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Fill an input element by ref (clears and types instantly).

        Args:
            ref: Element ref like "e1"
            text: Text to fill
            timeout: Timeout in milliseconds
        """
        locator = self.resolve_ref(ref)
        await locator.fill(text, timeout=timeout or self.default_timeout)

    async def hover(
        self,
        ref: str,
        *,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Hover over an element by ref.

        Args:
            ref: Element ref like "e1"
            timeout: Timeout in milliseconds
        """
        locator = self.resolve_ref(ref)
        await locator.hover(timeout=timeout or self.default_timeout)

    async def select_option(
        self,
        ref: str,
        values: Union[str, list[str]],
        *,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Select option(s) in a select element by ref.

        Args:
            ref: Element ref like "e1"
            values: Option value(s) to select
            timeout: Timeout in milliseconds
        """
        locator = self.resolve_ref(ref)
        if isinstance(values, str):
            values = [values]
        await locator.select_option(values, timeout=timeout or self.default_timeout)

    async def check(
        self,
        ref: str,
        checked: bool = True,
        *,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Check or uncheck a checkbox by ref.

        Args:
            ref: Element ref like "e1"
            checked: Whether to check (True) or uncheck (False)
            timeout: Timeout in milliseconds
        """
        locator = self.resolve_ref(ref)
        await locator.set_checked(checked, timeout=timeout or self.default_timeout)

    async def scroll_into_view(
        self,
        ref: str,
        *,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Scroll element into view by ref.

        Args:
            ref: Element ref like "e1"
            timeout: Timeout in milliseconds
        """
        locator = self.resolve_ref(ref)
        await locator.scroll_into_view_if_needed(
            timeout=timeout or self.default_timeout
        )

    async def highlight(
        self,
        ref: str,
    ) -> None:
        """
        Highlight an element for debugging.

        Args:
            ref: Element ref like "e1"
        """
        locator = self.resolve_ref(ref)
        await locator.highlight()

    async def get_element_info(
        self,
        ref: str,
        *,
        timeout: Optional[float] = None,
    ) -> ElementInfo:
        """
        Get detailed information about an element by ref.

        Args:
            ref: Element ref like "e1"
            timeout: Timeout in milliseconds

        Returns:
            ElementInfo with visibility, state, and attributes
        """
        normalized = self._validate_ref(ref)
        locator = self.resolve_ref(ref)
        role_ref = self._refs[normalized]
        timeout_ms = timeout or self.default_timeout

        # Get basic state
        visible = await locator.is_visible(timeout=timeout_ms)
        enabled = await locator.is_enabled(timeout=timeout_ms)
        focused = await locator.evaluate(
            "el => document.activeElement === el",
            timeout=timeout_ms,
        )

        # Get checked state for checkboxes/radios
        checked = None
        if role_ref.role in ("checkbox", "radio", "switch"):
            try:
                checked = await locator.is_checked(timeout=timeout_ms)
            except Exception:
                pass

        # Get bounding box
        bounding_box = await locator.bounding_box(timeout=timeout_ms)
        if bounding_box:
            bounding_box = {
                "x": bounding_box["x"],
                "y": bounding_box["y"],
                "width": bounding_box["width"],
                "height": bounding_box["height"],
            }

        # Get text content
        text_content = None
        try:
            text_content = await locator.text_content(timeout=timeout_ms)
        except Exception:
            pass

        # Get input value if applicable
        input_value = None
        if role_ref.role in ("textbox", "searchbox", "combobox", "spinbutton"):
            try:
                input_value = await locator.input_value(timeout=timeout_ms)
            except Exception:
                pass

        # Get attributes
        attributes = {}
        try:
            attrs = await locator.evaluate('''
                el => {
                    const result = {};
                    for (const attr of el.attributes) {
                        result[attr.name] = attr.value;
                    }
                    return result;
                }
            ''', timeout=timeout_ms)
            attributes = attrs or {}
        except Exception:
            pass

        return ElementInfo(
            ref=normalized,
            role=role_ref.role,
            name=role_ref.name,
            visible=visible,
            enabled=enabled,
            checked=checked,
            focused=focused,
            bounding_box=bounding_box,
            text_content=text_content,
            input_value=input_value,
            attributes=attributes,
        )

    async def screenshot(
        self,
        ref: Optional[str] = None,
        *,
        path: Optional[str] = None,
        full_page: bool = False,
        type: Literal["png", "jpeg"] = "png",
    ) -> bytes:
        """
        Take a screenshot of the page or a specific element.

        Args:
            ref: Optional element ref to screenshot (None for full page)
            path: Optional path to save screenshot
            full_page: Whether to capture full scrollable page
            type: Image format

        Returns:
            Screenshot bytes
        """
        if ref:
            if full_page:
                raise ValueError("full_page is not supported for element screenshots")
            locator = self.resolve_ref(ref)
            return await locator.screenshot(path=path, type=type)

        return await self.page.screenshot(
            path=path,
            full_page=full_page,
            type=type,
        )

    async def screenshot_with_labels(
        self,
        *,
        path: Optional[str] = None,
        max_labels: int = 150,
        type: Literal["png", "jpeg"] = "png",
    ) -> tuple[bytes, int, int]:
        """
        Take a screenshot with ref labels overlaid on elements.

        This is useful for visual debugging and AI understanding.

        Args:
            path: Optional path to save screenshot
            max_labels: Maximum number of labels to draw
            type: Image format

        Returns:
            Tuple of (screenshot bytes, labels drawn, labels skipped)
        """
        if not self._refs:
            return await self.page.screenshot(path=path, type=type), 0, 0

        # Get viewport info
        viewport = await self.page.evaluate('''
            () => ({
                scrollX: window.scrollX || 0,
                scrollY: window.scrollY || 0,
                width: window.innerWidth || 0,
                height: window.innerHeight || 0,
            })
        ''')

        # Collect visible element boxes
        boxes: list[dict[str, Any]] = []
        skipped = 0

        for ref in sorted(self._refs.keys(), key=lambda x: int(x[1:])):
            if len(boxes) >= max_labels:
                skipped += 1
                continue

            try:
                locator = self.resolve_ref(ref)
                box = await locator.bounding_box()

                if not box:
                    skipped += 1
                    continue

                # Check if visible in viewport
                x0, y0 = box["x"], box["y"]
                x1, y1 = x0 + box["width"], y0 + box["height"]
                vx0, vy0 = viewport["scrollX"], viewport["scrollY"]
                vx1, vy1 = vx0 + viewport["width"], vy0 + viewport["height"]

                if x1 < vx0 or x0 > vx1 or y1 < vy0 or y0 > vy1:
                    skipped += 1
                    continue

                boxes.append({
                    "ref": ref,
                    "x": x0 - viewport["scrollX"],
                    "y": y0 - viewport["scrollY"],
                    "w": max(1, box["width"]),
                    "h": max(1, box["height"]),
                })
            except Exception:
                skipped += 1

        try:
            # Inject label overlay
            if boxes:
                await self.page.evaluate('''
                    (labels) => {
                        // Remove existing labels
                        document.querySelectorAll('[data-catalyst-labels]')
                            .forEach(el => el.remove());

                        const root = document.createElement('div');
                        root.setAttribute('data-catalyst-labels', '1');
                        root.style.position = 'fixed';
                        root.style.left = '0';
                        root.style.top = '0';
                        root.style.zIndex = '2147483647';
                        root.style.pointerEvents = 'none';
                        root.style.fontFamily = '"SF Mono", Menlo, Monaco, monospace';

                        const clamp = (v, min, max) => Math.min(max, Math.max(min, v));

                        for (const label of labels) {
                            // Box outline
                            const box = document.createElement('div');
                            box.setAttribute('data-catalyst-labels', '1');
                            box.style.position = 'absolute';
                            box.style.left = `${label.x}px`;
                            box.style.top = `${label.y}px`;
                            box.style.width = `${label.w}px`;
                            box.style.height = `${label.h}px`;
                            box.style.border = '2px solid #ffb020';
                            box.style.boxSizing = 'border-box';

                            // Label tag
                            const tag = document.createElement('div');
                            tag.setAttribute('data-catalyst-labels', '1');
                            tag.textContent = label.ref;
                            tag.style.position = 'absolute';
                            tag.style.left = `${label.x}px`;
                            tag.style.top = `${clamp(label.y - 18, 0, 20000)}px`;
                            tag.style.background = '#ffb020';
                            tag.style.color = '#1a1a1a';
                            tag.style.fontSize = '12px';
                            tag.style.lineHeight = '14px';
                            tag.style.padding = '1px 4px';
                            tag.style.borderRadius = '3px';
                            tag.style.boxShadow = '0 1px 2px rgba(0,0,0,0.35)';
                            tag.style.whiteSpace = 'nowrap';

                            root.appendChild(box);
                            root.appendChild(tag);
                        }

                        document.documentElement.appendChild(root);
                    }
                ''', boxes)

            # Take screenshot
            buffer = await self.page.screenshot(path=path, type=type)
            return buffer, len(boxes), skipped

        finally:
            # Clean up labels
            await self.page.evaluate('''
                () => {
                    document.querySelectorAll('[data-catalyst-labels]')
                        .forEach(el => el.remove());
                }
            ''')

    def get_refs(self) -> dict[str, RoleRef]:
        """Get the current ref mapping."""
        return self._refs.copy()

    def get_ref_count(self) -> int:
        """Get the number of refs in current snapshot."""
        return len(self._refs)

    def clear_cache(self) -> None:
        """Clear the cached snapshot."""
        self._cached_snapshot = None
        self._refs = {}


# Convenience function for quick snapshot
async def snapshot(page: Page, **kwargs) -> SnapshotResult:
    """
    Quick snapshot function for one-off usage.

    For repeated usage on the same page, create a SnapshotRefs instance instead.
    """
    refs = SnapshotRefs(page)
    return await refs.snapshot(**kwargs)


# Frame ref support for nested contexts
def parse_frame_ref(ref: str) -> tuple[Optional[str], str]:
    """
    Parse a frame-scoped ref like "frame1:e12".

    Returns:
        Tuple of (frame_selector, element_ref)
    """
    if ':' in ref:
        frame, element = ref.split(':', 1)
        return frame, element
    return None, ref


__all__ = [
    "SnapshotRefs",
    "SnapshotResult",
    "SnapshotOptions",
    "SnapshotStats",
    "ElementInfo",
    "RoleRef",
    "RefMode",
    "snapshot",
    "parse_frame_ref",
    "INTERACTIVE_ROLES",
    "CONTENT_ROLES",
    "STRUCTURAL_ROLES",
]
