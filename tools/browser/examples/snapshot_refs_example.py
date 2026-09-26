"""
Example: Using Snapshot Refs for Browser Automation

This example demonstrates how to use the snapshot_refs module for
robust element targeting in browser automation tasks.

Run with:
    python3 tools/browser/examples/snapshot_refs_example.py
"""

import asyncio
from playwright.async_api import async_playwright

# Add parent directory to path for imports
import sys
sys.path.insert(0, "{{CATALYST_ROOT}}")

from tools.browser.snapshot_refs import SnapshotRefs, SnapshotOptions


async def basic_example():
    """Basic usage: Take snapshot and interact with elements."""
    print("\n=== Basic Example ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to a page
        await page.goto("https://example.com")

        # Create SnapshotRefs instance
        refs = SnapshotRefs(page)

        # Take a snapshot
        result = await refs.snapshot()

        print("Snapshot text (first 500 chars):")
        print(result.text[:500])
        print("\nStats:")
        print(f"  - Lines: {result.stats.lines}")
        print(f"  - Refs: {result.stats.refs}")
        print(f"  - Interactive elements: {result.stats.interactive}")

        print("\nElement refs found:")
        for ref_id, role_ref in result.refs.items():
            print(f"  {ref_id}: {role_ref.role}" + (f' "{role_ref.name}"' if role_ref.name else ""))

        await browser.close()


async def interactive_only_example():
    """Get only interactive elements (buttons, links, inputs)."""
    print("\n=== Interactive-Only Example ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://github.com/login")

        refs = SnapshotRefs(page)

        # Get only interactive elements (more compact output)
        result = await refs.snapshot_interactive()

        print("Interactive elements:")
        print(result.text)

        print(f"\nFound {result.stats.interactive} interactive elements")

        await browser.close()


async def click_and_type_example():
    """Demonstrate clicking and typing using refs."""
    print("\n=== Click and Type Example ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://github.com/login")

        refs = SnapshotRefs(page)

        # Take snapshot to discover elements
        result = await refs.snapshot()

        print("Looking for login form elements...")

        # Find username/email field
        username_ref = None
        password_ref = None
        for ref_id, role_ref in result.refs.items():
            if role_ref.role == "textbox":
                if role_ref.name and "username" in role_ref.name.lower():
                    username_ref = ref_id
                elif role_ref.name and "password" in role_ref.name.lower():
                    password_ref = ref_id

        if username_ref:
            print(f"  Username field: {username_ref}")
            # Would type here: await refs.type(username_ref, "user@example.com")

        if password_ref:
            print(f"  Password field: {password_ref}")
            # Would type here: await refs.type(password_ref, "password")

        await browser.close()


async def element_info_example():
    """Get detailed information about an element."""
    print("\n=== Element Info Example ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://example.com")

        refs = SnapshotRefs(page)
        await refs.snapshot()

        # Get info about first element
        if refs.get_ref_count() > 0:
            first_ref = list(refs.get_refs().keys())[0]
            info = await refs.get_element_info(first_ref)

            print(f"Element {first_ref}:")
            print(f"  Role: {info.role}")
            print(f"  Name: {info.name}")
            print(f"  Visible: {info.visible}")
            print(f"  Enabled: {info.enabled}")
            if info.bounding_box:
                print(f"  Position: ({info.bounding_box['x']}, {info.bounding_box['y']})")
                print(f"  Size: {info.bounding_box['width']}x{info.bounding_box['height']}")

        await browser.close()


async def screenshot_with_labels_example():
    """Take a screenshot with element labels overlaid."""
    print("\n=== Screenshot with Labels Example ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://example.com")

        refs = SnapshotRefs(page)
        await refs.snapshot()

        # Take screenshot with labels
        screenshot, labels_drawn, labels_skipped = await refs.screenshot_with_labels(
            path="/tmp/snapshot_refs_labeled.png"
        )

        print(f"Screenshot saved to: /tmp/snapshot_refs_labeled.png")
        print(f"Labels drawn: {labels_drawn}")
        print(f"Labels skipped: {labels_skipped}")

        await browser.close()


async def compact_mode_example():
    """Use compact mode to reduce noise in the snapshot."""
    print("\n=== Compact Mode Example ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://news.ycombinator.com")

        refs = SnapshotRefs(page)

        # Full snapshot (can be verbose)
        full_result = await refs.snapshot()
        print(f"Full snapshot: {full_result.stats.lines} lines, {full_result.stats.chars} chars")

        # Compact snapshot (removes empty structural elements)
        compact_result = await refs.snapshot(
            options=SnapshotOptions(compact=True),
            force_refresh=True,
        )
        print(f"Compact snapshot: {compact_result.stats.lines} lines, {compact_result.stats.chars} chars")

        # Interactive only (most compact)
        interactive_result = await refs.snapshot_interactive()
        print(f"Interactive only: {interactive_result.stats.lines} lines, {interactive_result.stats.chars} chars")

        await browser.close()


async def main():
    """Run all examples."""
    try:
        await basic_example()
    except Exception as e:
        print(f"Basic example failed: {e}")

    try:
        await interactive_only_example()
    except Exception as e:
        print(f"Interactive-only example failed: {e}")

    try:
        await click_and_type_example()
    except Exception as e:
        print(f"Click and type example failed: {e}")

    try:
        await element_info_example()
    except Exception as e:
        print(f"Element info example failed: {e}")

    try:
        await screenshot_with_labels_example()
    except Exception as e:
        print(f"Screenshot with labels example failed: {e}")

    try:
        await compact_mode_example()
    except Exception as e:
        print(f"Compact mode example failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
