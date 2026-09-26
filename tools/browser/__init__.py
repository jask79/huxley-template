"""
Huxley Browser Infrastructure

Browser profile isolation, state observability, snapshot-based targeting,
and management for Bowser agent automation.
Based on example-agent's superior patterns.

Modules:
    profile_manager: Browser profile isolation and management
    playwright_context: Playwright context creation helpers
    state_observer: Buffered capture of console, network, and error events
    snapshot_refs: Accessibility tree-based element targeting (robust refs)
"""

from .profile_manager import (
    BrowserProfileManager,
    Profile,
    ProfileOptions,
    ProfileColor,
    CDP_PORT_RANGE_START,
    CDP_PORT_RANGE_END,
)
from .playwright_context import create_browser_context, create_persistent_context
from .state_observer import (
    BrowserStateObserver,
    CircularBuffer,
    ConsoleMessage,
    NetworkRequest,
    ObserverStats,
    PageError,
    SourceLocation,
    create_observer,
    with_observer,
    with_observer_async,
)
from .snapshot_refs import (
    SnapshotRefs,
    SnapshotResult,
    SnapshotOptions,
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

__all__ = [
    # Profile management
    "BrowserProfileManager",
    "Profile",
    "ProfileOptions",
    "ProfileColor",
    "CDP_PORT_RANGE_START",
    "CDP_PORT_RANGE_END",
    # Context creation
    "create_browser_context",
    "create_persistent_context",
    # State observation
    "BrowserStateObserver",
    "CircularBuffer",
    "ConsoleMessage",
    "NetworkRequest",
    "ObserverStats",
    "PageError",
    "SourceLocation",
    "create_observer",
    "with_observer",
    "with_observer_async",
    # Snapshot-based element targeting
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
