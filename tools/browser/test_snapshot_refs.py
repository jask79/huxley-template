"""
Tests for snapshot_refs module.

Run with: pytest tools/browser/test_snapshot_refs.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from tools.browser.snapshot_refs import (
    SnapshotRefs,
    SnapshotOptions,
    SnapshotResult,
    SnapshotStats,
    ElementInfo,
    RoleRef,
    RefMode,
    snapshot,
    parse_frame_ref,
    INTERACTIVE_ROLES,
    CONTENT_ROLES,
    STRUCTURAL_ROLES,
)


class TestRoleSets:
    """Test role classification sets."""

    def test_interactive_roles_contains_button(self):
        assert "button" in INTERACTIVE_ROLES

    def test_interactive_roles_contains_link(self):
        assert "link" in INTERACTIVE_ROLES

    def test_interactive_roles_contains_textbox(self):
        assert "textbox" in INTERACTIVE_ROLES

    def test_content_roles_contains_heading(self):
        assert "heading" in CONTENT_ROLES

    def test_structural_roles_contains_generic(self):
        assert "generic" in STRUCTURAL_ROLES


class TestSnapshotOptions:
    """Test SnapshotOptions dataclass."""

    def test_defaults(self):
        opts = SnapshotOptions()
        assert opts.interactive_only is False
        assert opts.max_depth is None
        assert opts.compact is False
        assert opts.include_content_roles is True

    def test_custom_values(self):
        opts = SnapshotOptions(
            interactive_only=True,
            max_depth=3,
            compact=True,
            include_content_roles=False,
        )
        assert opts.interactive_only is True
        assert opts.max_depth == 3
        assert opts.compact is True
        assert opts.include_content_roles is False


class TestRoleRef:
    """Test RoleRef dataclass."""

    def test_basic_role(self):
        ref = RoleRef(role="button")
        assert ref.role == "button"
        assert ref.name is None
        assert ref.nth is None

    def test_role_with_name(self):
        ref = RoleRef(role="button", name="Submit")
        assert ref.role == "button"
        assert ref.name == "Submit"

    def test_role_with_nth(self):
        ref = RoleRef(role="button", name="Item", nth=2)
        assert ref.nth == 2


class TestSnapshotRefs:
    """Test SnapshotRefs class."""

    @pytest.fixture
    def mock_page(self):
        """Create a mock Playwright page."""
        page = MagicMock()
        page.locator = MagicMock(return_value=MagicMock())
        page.frame_locator = MagicMock(return_value=MagicMock())
        page.get_by_role = MagicMock(return_value=MagicMock())
        page.evaluate = AsyncMock(return_value={})
        return page

    @pytest.fixture
    def snapshot_refs(self, mock_page):
        """Create SnapshotRefs instance."""
        return SnapshotRefs(mock_page)

    def test_init(self, mock_page):
        """Test initialization."""
        refs = SnapshotRefs(mock_page, cache_ttl=30.0, default_timeout=5000.0)
        assert refs.page is mock_page
        assert refs.cache_ttl == 30.0
        assert refs.default_timeout == 5000.0

    def test_get_indent_level(self, snapshot_refs):
        """Test indent level parsing."""
        assert snapshot_refs._get_indent_level("- button") == 0
        assert snapshot_refs._get_indent_level("  - button") == 1
        assert snapshot_refs._get_indent_level("    - button") == 2
        assert snapshot_refs._get_indent_level("      - button") == 3

    def test_parse_aria_line_button(self, snapshot_refs):
        """Test parsing button line."""
        role, name, suffix = snapshot_refs._parse_aria_line('- button "Submit"')
        assert role == "button"
        assert name == "Submit"

    def test_parse_aria_line_unnamed(self, snapshot_refs):
        """Test parsing unnamed element."""
        role, name, suffix = snapshot_refs._parse_aria_line("- textbox")
        assert role == "textbox"
        assert name is None

    def test_parse_aria_line_closing_tag(self, snapshot_refs):
        """Test parsing closing tag returns None."""
        role, name, suffix = snapshot_refs._parse_aria_line("- /list")
        assert role is None

    def test_normalize_ref_plain(self, snapshot_refs):
        """Test normalizing plain ref."""
        assert snapshot_refs._normalize_ref("e1") == "e1"
        assert snapshot_refs._normalize_ref("e123") == "e123"

    def test_normalize_ref_with_at(self, snapshot_refs):
        """Test normalizing ref with @ prefix."""
        assert snapshot_refs._normalize_ref("@e1") == "e1"

    def test_normalize_ref_with_prefix(self, snapshot_refs):
        """Test normalizing ref with ref= prefix."""
        assert snapshot_refs._normalize_ref("ref=e1") == "e1"

    def test_validate_ref_invalid_format(self, snapshot_refs):
        """Test validation rejects invalid format."""
        with pytest.raises(ValueError, match="Invalid ref format"):
            snapshot_refs._validate_ref("invalid")

    def test_validate_ref_not_found(self, snapshot_refs):
        """Test validation rejects unknown ref."""
        with pytest.raises(ValueError, match="Unknown ref"):
            snapshot_refs._validate_ref("e1")

    def test_build_role_snapshot_basic(self, snapshot_refs):
        """Test building basic role snapshot."""
        aria = """- button "Submit"
- textbox "Email"
- link "Home"
"""
        result = snapshot_refs._build_role_snapshot(aria, SnapshotOptions())

        assert "e1" in result.refs
        assert "e2" in result.refs
        assert "e3" in result.refs
        assert result.refs["e1"].role == "button"
        assert result.refs["e1"].name == "Submit"
        assert result.refs["e2"].role == "textbox"
        assert result.refs["e3"].role == "link"

    def test_build_role_snapshot_interactive_only(self, snapshot_refs):
        """Test interactive-only mode."""
        aria = """- heading "Title"
- button "Submit"
- paragraph
"""
        result = snapshot_refs._build_role_snapshot(
            aria, SnapshotOptions(interactive_only=True)
        )

        # Only button should get a ref
        assert len(result.refs) == 1
        assert result.refs["e1"].role == "button"

    def test_build_role_snapshot_max_depth(self, snapshot_refs):
        """Test max depth filtering."""
        aria = """- list
  - listitem
    - button "Deep"
"""
        result = snapshot_refs._build_role_snapshot(
            aria, SnapshotOptions(max_depth=1)
        )

        # Button at depth 2 should be excluded
        assert "button" not in result.text.lower() or "Deep" not in result.text

    def test_build_role_snapshot_duplicate_handling(self, snapshot_refs):
        """Test nth index for duplicate role+name."""
        aria = """- button "Save"
- button "Save"
- button "Cancel"
"""
        result = snapshot_refs._build_role_snapshot(aria, SnapshotOptions())

        # First "Save" should have no nth (or nth=0)
        # Second "Save" should have nth=1
        save_refs = [r for r in result.refs.values() if r.name == "Save"]
        assert len(save_refs) == 2

        # One should have nth=None or 0, other should have nth=1
        nths = sorted([r.nth for r in save_refs])
        assert nths == [None, 1] or nths == [0, 1]

    def test_build_role_snapshot_stats(self, snapshot_refs):
        """Test statistics calculation."""
        aria = """- button "Submit"
- link "Home"
- heading "Title"
"""
        result = snapshot_refs._build_role_snapshot(aria, SnapshotOptions())

        assert result.stats.refs == 3
        assert result.stats.interactive == 2  # button and link
        assert result.stats.lines > 0
        assert result.stats.chars > 0

    def test_compact_tree(self, snapshot_refs):
        """Test tree compaction."""
        tree = """- generic
  - button "Submit" [ref=e1]
- group
  - paragraph:
"""
        compacted = snapshot_refs._compact_tree(tree)

        # Should keep line with ref and its parent
        assert "[ref=e1]" in compacted
        # Should remove empty group without refs
        assert "group" not in compacted or "[ref=" in compacted

    def test_get_refs_returns_copy(self, snapshot_refs):
        """Test get_refs returns a copy."""
        snapshot_refs._refs = {"e1": RoleRef(role="button")}
        refs = snapshot_refs.get_refs()

        # Modify returned dict
        refs["e2"] = RoleRef(role="link")

        # Original should be unchanged
        assert "e2" not in snapshot_refs._refs

    def test_get_ref_count(self, snapshot_refs):
        """Test ref count."""
        snapshot_refs._refs = {
            "e1": RoleRef(role="button"),
            "e2": RoleRef(role="link"),
        }
        assert snapshot_refs.get_ref_count() == 2

    def test_clear_cache(self, snapshot_refs):
        """Test cache clearing."""
        snapshot_refs._refs = {"e1": RoleRef(role="button")}
        snapshot_refs._cached_snapshot = SnapshotResult(
            text="test",
            refs={"e1": RoleRef(role="button")},
            stats=SnapshotStats(lines=1, chars=4, refs=1, interactive=1),
        )

        snapshot_refs.clear_cache()

        assert snapshot_refs._cached_snapshot is None
        assert len(snapshot_refs._refs) == 0


class TestParseFrameRef:
    """Test frame ref parsing."""

    def test_simple_ref(self):
        """Test parsing ref without frame."""
        frame, ref = parse_frame_ref("e1")
        assert frame is None
        assert ref == "e1"

    def test_frame_scoped_ref(self):
        """Test parsing frame-scoped ref."""
        frame, ref = parse_frame_ref("iframe1:e12")
        assert frame == "iframe1"
        assert ref == "e12"

    def test_complex_frame_ref(self):
        """Test parsing ref with complex frame selector."""
        frame, ref = parse_frame_ref("#content:e5")
        assert frame == "#content"
        assert ref == "e5"


class TestSnapshotResult:
    """Test SnapshotResult dataclass."""

    def test_is_stale_fresh(self):
        """Test freshly created snapshot is not stale."""
        result = SnapshotResult(
            text="test",
            refs={},
            stats=SnapshotStats(lines=1, chars=4, refs=0, interactive=0),
        )
        assert not result.is_stale

    def test_is_stale_old(self):
        """Test old snapshot is stale."""
        import time
        result = SnapshotResult(
            text="test",
            refs={},
            stats=SnapshotStats(lines=1, chars=4, refs=0, interactive=0),
            timestamp=time.time() - 120,  # 2 minutes ago
        )
        assert result.is_stale


class TestAsyncOperations:
    """Test async operations with mocked Playwright.

    These tests use asyncio.run() to execute async methods synchronously.
    """

    @pytest.fixture
    def mock_page(self):
        """Create a mock async Playwright page."""
        page = MagicMock()

        # Mock locator chain
        mock_locator = MagicMock()
        mock_locator.aria_snapshot = AsyncMock(
            return_value='- button "Submit"\n- textbox "Email"'
        )
        mock_locator.click = AsyncMock()
        mock_locator.dblclick = AsyncMock()
        mock_locator.fill = AsyncMock()
        mock_locator.type = AsyncMock()
        mock_locator.clear = AsyncMock()
        mock_locator.hover = AsyncMock()
        mock_locator.highlight = AsyncMock()
        mock_locator.press = AsyncMock()
        mock_locator.select_option = AsyncMock()
        mock_locator.set_checked = AsyncMock()
        mock_locator.scroll_into_view_if_needed = AsyncMock()
        mock_locator.screenshot = AsyncMock(return_value=b"fake_png")
        mock_locator.is_visible = AsyncMock(return_value=True)
        mock_locator.is_enabled = AsyncMock(return_value=True)
        mock_locator.is_checked = AsyncMock(return_value=False)
        mock_locator.text_content = AsyncMock(return_value="Submit")
        mock_locator.input_value = AsyncMock(return_value="")
        mock_locator.bounding_box = AsyncMock(
            return_value={"x": 10, "y": 20, "width": 100, "height": 30}
        )
        mock_locator.evaluate = AsyncMock(return_value=False)
        mock_locator.nth = MagicMock(return_value=mock_locator)

        page.locator = MagicMock(return_value=mock_locator)
        page.get_by_role = MagicMock(return_value=mock_locator)
        page.evaluate = AsyncMock(return_value={
            "scrollX": 0, "scrollY": 0, "width": 1280, "height": 720
        })
        page.screenshot = AsyncMock(return_value=b"fake_png")

        return page

    def test_snapshot(self, mock_page):
        """Test snapshot generation."""
        refs = SnapshotRefs(mock_page)
        result = asyncio.run(refs.snapshot())

        assert "e1" in result.refs
        assert "e2" in result.refs
        assert result.refs["e1"].role == "button"
        assert result.refs["e2"].role == "textbox"

    def test_snapshot_caching(self, mock_page):
        """Test snapshot caching."""
        refs = SnapshotRefs(mock_page)

        async def run():
            # First snapshot
            result1 = await refs.snapshot()
            # Second snapshot should use cache
            result2 = await refs.snapshot()
            return result1, result2

        result1, result2 = asyncio.run(run())

        # aria_snapshot should only be called once
        mock_page.locator.return_value.aria_snapshot.assert_called_once()

        assert result1.text == result2.text

    def test_snapshot_force_refresh(self, mock_page):
        """Test force refresh bypasses cache."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.snapshot(force_refresh=True)

        asyncio.run(run())

        # aria_snapshot should be called twice
        assert mock_page.locator.return_value.aria_snapshot.call_count == 2

    def test_snapshot_interactive(self, mock_page):
        """Test interactive-only snapshot."""
        refs = SnapshotRefs(mock_page)
        result = asyncio.run(refs.snapshot_interactive())

        # Should only include interactive elements
        for role_ref in result.refs.values():
            assert role_ref.role in INTERACTIVE_ROLES

    def test_click(self, mock_page):
        """Test click operation."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.click("e1")

        asyncio.run(run())

        mock_page.get_by_role.assert_called()
        mock_page.get_by_role.return_value.click.assert_called_once()

    def test_double_click(self, mock_page):
        """Test double-click operation."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.click("e1", double=True)

        asyncio.run(run())

        mock_page.get_by_role.return_value.dblclick.assert_called_once()

    def test_type_with_clear(self, mock_page):
        """Test type operation with clear (default)."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.type("e2", "test@example.com")

        asyncio.run(run())

        mock_page.get_by_role.return_value.fill.assert_called_once_with(
            "test@example.com", timeout=8000.0
        )

    def test_type_slowly(self, mock_page):
        """Test slow typing."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.type("e2", "hello", slowly=True)

        asyncio.run(run())

        mock_page.get_by_role.return_value.click.assert_called()
        mock_page.get_by_role.return_value.type.assert_called()

    def test_fill(self, mock_page):
        """Test fill operation."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.fill("e2", "value")

        asyncio.run(run())

        mock_page.get_by_role.return_value.fill.assert_called_with(
            "value", timeout=8000.0
        )

    def test_hover(self, mock_page):
        """Test hover operation."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.hover("e1")

        asyncio.run(run())

        mock_page.get_by_role.return_value.hover.assert_called_once()

    def test_select_option_single(self, mock_page):
        """Test select single option."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.select_option("e1", "value1")

        asyncio.run(run())

        mock_page.get_by_role.return_value.select_option.assert_called_once()

    def test_select_option_multiple(self, mock_page):
        """Test select multiple options."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.select_option("e1", ["value1", "value2"])

        asyncio.run(run())

        mock_page.get_by_role.return_value.select_option.assert_called_once()

    def test_check(self, mock_page):
        """Test check operation."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.check("e1", True)

        asyncio.run(run())

        mock_page.get_by_role.return_value.set_checked.assert_called_once_with(
            True, timeout=8000.0
        )

    def test_uncheck(self, mock_page):
        """Test uncheck operation."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.check("e1", False)

        asyncio.run(run())

        mock_page.get_by_role.return_value.set_checked.assert_called_once_with(
            False, timeout=8000.0
        )

    def test_scroll_into_view(self, mock_page):
        """Test scroll into view."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.scroll_into_view("e1")

        asyncio.run(run())

        mock_page.get_by_role.return_value.scroll_into_view_if_needed.assert_called_once()

    def test_highlight(self, mock_page):
        """Test highlight."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.highlight("e1")

        asyncio.run(run())

        mock_page.get_by_role.return_value.highlight.assert_called_once()

    def test_get_element_info(self, mock_page):
        """Test getting element info."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            return await refs.get_element_info("e1")

        info = asyncio.run(run())

        assert info.ref == "e1"
        assert info.role == "button"
        assert info.name == "Submit"
        assert info.visible is True
        assert info.enabled is True
        assert info.bounding_box is not None

    def test_screenshot_page(self, mock_page):
        """Test page screenshot."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            return await refs.screenshot()

        result = asyncio.run(run())

        mock_page.screenshot.assert_called_once()
        assert result == b"fake_png"

    def test_screenshot_element(self, mock_page):
        """Test element screenshot."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            return await refs.screenshot("e1")

        result = asyncio.run(run())

        mock_page.get_by_role.return_value.screenshot.assert_called_once()
        assert result == b"fake_png"

    def test_screenshot_full_page(self, mock_page):
        """Test full page screenshot."""
        refs = SnapshotRefs(mock_page)

        result = asyncio.run(refs.screenshot(full_page=True))

        mock_page.screenshot.assert_called_with(
            path=None, full_page=True, type="png"
        )

    def test_screenshot_full_page_with_ref_raises(self, mock_page):
        """Test that full_page with ref raises error."""
        refs = SnapshotRefs(mock_page)

        async def run():
            await refs.snapshot()
            await refs.screenshot("e1", full_page=True)

        with pytest.raises(ValueError, match="full_page is not supported"):
            asyncio.run(run())


class TestConvenienceFunction:
    """Test convenience snapshot function."""

    def test_quick_snapshot(self):
        """Test quick snapshot function."""
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.aria_snapshot = AsyncMock(return_value='- button "Test"')
        mock_page.locator = MagicMock(return_value=mock_locator)

        result = asyncio.run(snapshot(mock_page))

        assert "e1" in result.refs
        assert result.refs["e1"].role == "button"


class TestRefModes:
    """Test different ref resolution modes."""

    @pytest.fixture
    def mock_page(self):
        """Create a mock page."""
        page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.aria_snapshot = AsyncMock(
            return_value='- button "Submit" [ref=e5]'
        )
        page.locator = MagicMock(return_value=mock_locator)
        page.get_by_role = MagicMock(return_value=mock_locator)
        return page

    def test_role_mode_uses_get_by_role(self, mock_page):
        """Test ROLE mode uses getByRole for resolution."""
        refs = SnapshotRefs(mock_page)

        # Set up refs manually
        refs._refs = {"e1": RoleRef(role="button", name="Submit")}
        refs._mode = RefMode.ROLE

        locator = refs.resolve_ref("e1")

        mock_page.get_by_role.assert_called_with("button", name="Submit", exact=True)

    def test_aria_mode_uses_locator(self, mock_page):
        """Test ARIA mode uses locator selector for resolution."""
        refs = SnapshotRefs(mock_page)

        # Set up refs manually
        refs._refs = {"e1": RoleRef(role="button", name="Submit")}
        refs._mode = RefMode.ARIA

        locator = refs.resolve_ref("e1")

        mock_page.locator.assert_called_with('[aria-ref="e1"]')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
