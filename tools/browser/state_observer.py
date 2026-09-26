#!/usr/bin/env python3
"""
Browser State Observer - Buffered capture of console, network, and error events.

Provides observability into browser page state for debugging, testing, and automation.
Implements circular buffers with efficient filtering for production use.

Based on patterns from example-agent's pw-session.ts state tracking.

Usage:
    from playwright.async_api import async_playwright
    from tools.browser.state_observer import BrowserStateObserver, with_observer

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        observer = BrowserStateObserver()
        observer.attach(page)

        await page.goto("https://example.com")

        # Get filtered data
        errors = observer.get_errors()
        console_errors = observer.get_console_messages(level="error")
        failed_requests = observer.get_network_requests(status_range=(400, 599))

        # Export for debugging
        observer.export_json("/tmp/browser_state.json")
"""

from __future__ import annotations

import json
import re
import threading
from collections import deque
from contextlib import asynccontextmanager, contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import (
    Any,
    Callable,
    Deque,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

# Type aliases for Playwright objects (avoid hard dependency)
try:
    from playwright.async_api import Page as AsyncPage
    from playwright.sync_api import Page as SyncPage
    Page = Union[AsyncPage, SyncPage]
except ImportError:
    Page = Any  # type: ignore


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class SourceLocation:
    """Source code location for console messages."""
    url: Optional[str] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None

    def __str__(self) -> str:
        if not self.url:
            return "<unknown>"
        loc = self.url
        if self.line_number is not None:
            loc += f":{self.line_number}"
            if self.column_number is not None:
                loc += f":{self.column_number}"
        return loc


@dataclass
class ConsoleMessage:
    """Captured console message from browser page."""
    type: str  # log, warn, error, info, debug, trace, dir, dirxml, table, etc.
    text: str
    timestamp: datetime
    location: Optional[SourceLocation] = None

    def matches(
        self,
        level: Optional[str] = None,
        pattern: Optional[str] = None,
        url_pattern: Optional[str] = None,
    ) -> bool:
        """Check if message matches filter criteria."""
        if level and self.type != level:
            return False
        if pattern and not re.search(pattern, self.text, re.IGNORECASE):
            return False
        if url_pattern and self.location:
            if not self.location.url or not re.search(url_pattern, self.location.url):
                return False
        return True


@dataclass
class NetworkRequest:
    """Captured network request from browser page."""
    id: str
    method: str
    url: str
    resource_type: str  # document, stylesheet, image, script, xhr, fetch, etc.
    timestamp: datetime
    status: Optional[int] = None
    ok: Optional[bool] = None
    failure_reason: Optional[str] = None
    timing_ms: Optional[float] = None  # Response time

    @property
    def is_failed(self) -> bool:
        """Check if request failed."""
        return self.failure_reason is not None or (self.status and self.status >= 400)

    @property
    def is_pending(self) -> bool:
        """Check if request is still pending (no response yet)."""
        return self.status is None and self.failure_reason is None

    def matches(
        self,
        url_pattern: Optional[str] = None,
        method: Optional[str] = None,
        resource_type: Optional[str] = None,
        status_range: Optional[Tuple[int, int]] = None,
        failed_only: bool = False,
        pending_only: bool = False,
    ) -> bool:
        """Check if request matches filter criteria."""
        if url_pattern and not re.search(url_pattern, self.url, re.IGNORECASE):
            return False
        if method and self.method.upper() != method.upper():
            return False
        if resource_type and self.resource_type != resource_type:
            return False
        if status_range:
            if self.status is None:
                return False
            min_status, max_status = status_range
            if not (min_status <= self.status <= max_status):
                return False
        if failed_only and not self.is_failed:
            return False
        if pending_only and not self.is_pending:
            return False
        return True


@dataclass
class PageError:
    """Captured page error (uncaught exception)."""
    message: str
    name: str
    stack: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def short_message(self) -> str:
        """Get first line of error message."""
        return self.message.split("\n")[0]


@dataclass
class ObserverStats:
    """Summary statistics from observer."""
    console_total: int = 0
    console_by_type: Dict[str, int] = field(default_factory=dict)
    network_total: int = 0
    network_by_status: Dict[str, int] = field(default_factory=dict)  # "2xx", "3xx", etc.
    network_by_type: Dict[str, int] = field(default_factory=dict)
    network_failed: int = 0
    network_pending: int = 0
    errors_total: int = 0
    buffer_utilization: Dict[str, float] = field(default_factory=dict)


# ============================================================================
# Circular Buffer Implementation
# ============================================================================

T = TypeVar("T")


class CircularBuffer(Deque[T]):
    """
    Thread-safe circular buffer with automatic eviction.

    Extends deque with:
    - Max size enforcement with oldest-first eviction
    - Thread-safe operations
    - Efficient filtering without copying (via generator)
    """

    def __init__(self, maxsize: int = 500):
        super().__init__(maxlen=maxsize)
        self._lock = threading.RLock()
        self._maxsize = maxsize
        self._total_added = 0
        self._total_evicted = 0

    @property
    def maxsize(self) -> int:
        return self._maxsize

    @property
    def utilization(self) -> float:
        """Return buffer utilization as percentage (0.0 - 1.0)."""
        with self._lock:
            return len(self) / self._maxsize if self._maxsize > 0 else 0.0

    @property
    def stats(self) -> Dict[str, int]:
        """Get buffer statistics."""
        with self._lock:
            return {
                "current_size": len(self),
                "max_size": self._maxsize,
                "total_added": self._total_added,
                "total_evicted": self._total_evicted,
            }

    def push(self, item: T) -> None:
        """Add item, evicting oldest if at capacity."""
        with self._lock:
            was_full = len(self) >= self._maxsize
            self.append(item)
            self._total_added += 1
            if was_full:
                self._total_evicted += 1

    def filter(self, predicate: Callable[[T], bool]) -> Iterator[T]:
        """
        Efficiently filter items without copying.

        Note: Caller should consume iterator quickly as buffer may change.
        For a stable copy, use filter_copy().
        """
        with self._lock:
            for item in self:
                if predicate(item):
                    yield item

    def filter_copy(self, predicate: Callable[[T], bool]) -> List[T]:
        """Return filtered copy of items matching predicate."""
        with self._lock:
            return [item for item in self if predicate(item)]

    def get_all(self) -> List[T]:
        """Return copy of all items."""
        with self._lock:
            return list(self)

    def get_recent(self, n: int) -> List[T]:
        """Return most recent n items."""
        with self._lock:
            items = list(self)
            return items[-n:] if n < len(items) else items

    def clear_all(self) -> int:
        """Clear buffer, return count of items cleared."""
        with self._lock:
            count = len(self)
            self.clear()
            return count


# ============================================================================
# Browser State Observer
# ============================================================================

class BrowserStateObserver:
    """
    Observes and buffers browser page state events.

    Captures:
    - Console messages (log, warn, error, info, debug, etc.)
    - Network requests (with status, timing, failures)
    - Page errors (uncaught exceptions)

    Features:
    - Circular buffers with configurable sizes
    - Thread-safe operations
    - Efficient filtering
    - JSON export for debugging
    """

    def __init__(
        self,
        console_buffer_size: int = 500,
        network_buffer_size: int = 500,
        error_buffer_size: int = 200,
    ):
        self._console: CircularBuffer[ConsoleMessage] = CircularBuffer(console_buffer_size)
        self._network: CircularBuffer[NetworkRequest] = CircularBuffer(network_buffer_size)
        self._errors: CircularBuffer[PageError] = CircularBuffer(error_buffer_size)

        # Request ID tracking for correlating requests/responses
        self._request_ids: Dict[Any, str] = {}
        self._next_request_id = 0
        self._id_lock = threading.Lock()

        # Track attached pages
        self._attached_pages: List[Any] = []

        # Listener references for cleanup
        self._listeners: Dict[Any, Dict[str, Callable]] = {}

    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        with self._id_lock:
            self._next_request_id += 1
            return f"r{self._next_request_id}"

    # ========================================================================
    # Attachment
    # ========================================================================

    def attach(self, page: Page) -> "BrowserStateObserver":
        """
        Attach observer to a Playwright page.

        Supports both sync and async Playwright pages.
        Returns self for chaining.
        """
        if page in self._attached_pages:
            return self  # Already attached

        # Store listener references for cleanup
        listeners: Dict[str, Callable] = {}

        def on_console(msg: Any) -> None:
            location = None
            loc_data = msg.location
            if loc_data:
                location = SourceLocation(
                    url=loc_data.get("url"),
                    line_number=loc_data.get("lineNumber"),
                    column_number=loc_data.get("columnNumber"),
                )

            entry = ConsoleMessage(
                type=msg.type,
                text=msg.text,
                timestamp=datetime.now(),
                location=location,
            )
            self._console.push(entry)

        def on_pageerror(err: Any) -> None:
            entry = PageError(
                message=str(err.message) if hasattr(err, "message") else str(err),
                name=str(err.name) if hasattr(err, "name") else "Error",
                stack=str(err.stack) if hasattr(err, "stack") else None,
                timestamp=datetime.now(),
            )
            self._errors.push(entry)

        def on_request(req: Any) -> None:
            req_id = self._generate_request_id()
            self._request_ids[req] = req_id

            entry = NetworkRequest(
                id=req_id,
                method=req.method,
                url=req.url,
                resource_type=req.resource_type,
                timestamp=datetime.now(),
            )
            self._network.push(entry)

        def on_response(resp: Any) -> None:
            req = resp.request
            req_id = self._request_ids.get(req)
            if not req_id:
                return

            # Find and update the request entry
            for entry in self._network:
                if entry.id == req_id:
                    entry.status = resp.status
                    entry.ok = resp.ok
                    break

        def on_requestfailed(req: Any) -> None:
            req_id = self._request_ids.get(req)
            if not req_id:
                return

            failure = req.failure
            failure_text = failure.error_text if hasattr(failure, "error_text") else str(failure) if failure else None

            # Find and update the request entry
            for entry in self._network:
                if entry.id == req_id:
                    entry.failure_reason = failure_text
                    entry.ok = False
                    break

        def on_close() -> None:
            self.detach(page)

        # Attach listeners
        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.on("request", on_request)
        page.on("response", on_response)
        page.on("requestfailed", on_requestfailed)
        page.on("close", on_close)

        listeners["console"] = on_console
        listeners["pageerror"] = on_pageerror
        listeners["request"] = on_request
        listeners["response"] = on_response
        listeners["requestfailed"] = on_requestfailed
        listeners["close"] = on_close

        self._listeners[page] = listeners
        self._attached_pages.append(page)

        return self

    def detach(self, page: Page) -> "BrowserStateObserver":
        """Detach observer from a page, removing all listeners."""
        if page not in self._attached_pages:
            return self

        listeners = self._listeners.get(page, {})
        for event, handler in listeners.items():
            try:
                page.remove_listener(event, handler)
            except Exception:
                pass  # Page may already be closed

        self._attached_pages.remove(page)
        self._listeners.pop(page, None)

        # Clean up request IDs for this page (best effort)
        # Note: Can't easily filter by page, so we leave them for GC

        return self

    def detach_all(self) -> "BrowserStateObserver":
        """Detach from all pages."""
        for page in list(self._attached_pages):
            self.detach(page)
        return self

    # ========================================================================
    # Query Methods
    # ========================================================================

    def get_console_messages(
        self,
        level: Optional[str] = None,
        pattern: Optional[str] = None,
        url_pattern: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[ConsoleMessage]:
        """
        Get console messages matching criteria.

        Args:
            level: Filter by type (log, warn, error, info, debug)
            pattern: Regex pattern to match message text
            url_pattern: Regex pattern to match source URL
            limit: Maximum number of results (most recent)

        Returns:
            List of matching ConsoleMessage objects
        """
        results = self._console.filter_copy(
            lambda m: m.matches(level=level, pattern=pattern, url_pattern=url_pattern)
        )
        if limit:
            results = results[-limit:]
        return results

    def get_network_requests(
        self,
        url_pattern: Optional[str] = None,
        method: Optional[str] = None,
        resource_type: Optional[str] = None,
        status_range: Optional[Tuple[int, int]] = None,
        failed_only: bool = False,
        pending_only: bool = False,
        limit: Optional[int] = None,
    ) -> List[NetworkRequest]:
        """
        Get network requests matching criteria.

        Args:
            url_pattern: Regex pattern to match URL
            method: HTTP method (GET, POST, etc.)
            resource_type: Resource type (document, script, xhr, fetch, etc.)
            status_range: Tuple of (min_status, max_status) inclusive
            failed_only: Only return failed requests
            pending_only: Only return pending requests (no response yet)
            limit: Maximum number of results (most recent)

        Returns:
            List of matching NetworkRequest objects
        """
        results = self._network.filter_copy(
            lambda r: r.matches(
                url_pattern=url_pattern,
                method=method,
                resource_type=resource_type,
                status_range=status_range,
                failed_only=failed_only,
                pending_only=pending_only,
            )
        )
        if limit:
            results = results[-limit:]
        return results

    def get_errors(
        self,
        pattern: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[PageError]:
        """
        Get page errors matching criteria.

        Args:
            pattern: Regex pattern to match error message
            limit: Maximum number of results (most recent)

        Returns:
            List of matching PageError objects
        """
        if pattern:
            results = self._errors.filter_copy(
                lambda e: re.search(pattern, e.message, re.IGNORECASE) is not None
            )
        else:
            results = self._errors.get_all()

        if limit:
            results = results[-limit:]
        return results

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> ObserverStats:
        """Get summary statistics from observer."""
        stats = ObserverStats()

        # Console stats
        console_messages = self._console.get_all()
        stats.console_total = len(console_messages)
        for msg in console_messages:
            stats.console_by_type[msg.type] = stats.console_by_type.get(msg.type, 0) + 1

        # Network stats
        network_requests = self._network.get_all()
        stats.network_total = len(network_requests)
        for req in network_requests:
            # By type
            stats.network_by_type[req.resource_type] = (
                stats.network_by_type.get(req.resource_type, 0) + 1
            )

            # By status range
            if req.status:
                status_range = f"{req.status // 100}xx"
                stats.network_by_status[status_range] = (
                    stats.network_by_status.get(status_range, 0) + 1
                )

            # Failed/pending counts
            if req.is_failed:
                stats.network_failed += 1
            elif req.is_pending:
                stats.network_pending += 1

        # Error stats
        stats.errors_total = len(self._errors)

        # Buffer utilization
        stats.buffer_utilization = {
            "console": self._console.utilization,
            "network": self._network.utilization,
            "errors": self._errors.utilization,
        }

        return stats

    # ========================================================================
    # Export and Clear
    # ========================================================================

    def export_json(
        self,
        path: Optional[str] = None,
        include_stats: bool = True,
    ) -> Dict[str, Any]:
        """
        Export all captured data as JSON.

        Args:
            path: Optional file path to write JSON
            include_stats: Include summary statistics

        Returns:
            Dict containing all captured data
        """
        def serialize_datetime(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        data: Dict[str, Any] = {
            "console": [asdict(m) for m in self._console.get_all()],
            "network": [asdict(r) for r in self._network.get_all()],
            "errors": [asdict(e) for e in self._errors.get_all()],
            "exported_at": datetime.now().isoformat(),
        }

        if include_stats:
            data["stats"] = asdict(self.get_stats())

        if path:
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=serialize_datetime)

        return data

    def clear(self) -> Dict[str, int]:
        """
        Clear all buffers.

        Returns:
            Dict with count of cleared items per buffer
        """
        return {
            "console": self._console.clear_all(),
            "network": self._network.clear_all(),
            "errors": self._errors.clear_all(),
        }

    # ========================================================================
    # Context Manager Support
    # ========================================================================

    def __enter__(self) -> "BrowserStateObserver":
        return self

    def __exit__(self, *args: Any) -> None:
        self.detach_all()


# ============================================================================
# Context Manager Helpers
# ============================================================================

@asynccontextmanager
async def with_observer_async(
    page: Page,
    console_buffer_size: int = 500,
    network_buffer_size: int = 500,
    error_buffer_size: int = 200,
):
    """
    Async context manager for observing a page.

    Usage:
        async with with_observer_async(page) as observer:
            await page.goto("https://example.com")
            errors = observer.get_errors()
    """
    observer = BrowserStateObserver(
        console_buffer_size=console_buffer_size,
        network_buffer_size=network_buffer_size,
        error_buffer_size=error_buffer_size,
    )
    observer.attach(page)
    try:
        yield observer
    finally:
        observer.detach(page)


@contextmanager
def with_observer(
    page: Page,
    console_buffer_size: int = 500,
    network_buffer_size: int = 500,
    error_buffer_size: int = 200,
):
    """
    Sync context manager for observing a page.

    Usage:
        with with_observer(page) as observer:
            page.goto("https://example.com")
            errors = observer.get_errors()
    """
    observer = BrowserStateObserver(
        console_buffer_size=console_buffer_size,
        network_buffer_size=network_buffer_size,
        error_buffer_size=error_buffer_size,
    )
    observer.attach(page)
    try:
        yield observer
    finally:
        observer.detach(page)


# ============================================================================
# Convenience Functions
# ============================================================================

def create_observer(
    page: Optional[Page] = None,
    console_buffer_size: int = 500,
    network_buffer_size: int = 500,
    error_buffer_size: int = 200,
) -> BrowserStateObserver:
    """
    Create and optionally attach an observer.

    Args:
        page: Optional page to attach to
        console_buffer_size: Max console messages to buffer
        network_buffer_size: Max network requests to buffer
        error_buffer_size: Max page errors to buffer

    Returns:
        Configured BrowserStateObserver
    """
    observer = BrowserStateObserver(
        console_buffer_size=console_buffer_size,
        network_buffer_size=network_buffer_size,
        error_buffer_size=error_buffer_size,
    )
    if page:
        observer.attach(page)
    return observer


# ============================================================================
# CLI for Testing
# ============================================================================

if __name__ == "__main__":
    import asyncio
    import argparse

    parser = argparse.ArgumentParser(
        description="Browser State Observer - capture browser events"
    )
    parser.add_argument("url", help="URL to navigate to")
    parser.add_argument(
        "--output", "-o", help="Output JSON file path", default="/tmp/browser_state.json"
    )
    parser.add_argument(
        "--console-size", type=int, default=500, help="Console buffer size"
    )
    parser.add_argument(
        "--network-size", type=int, default=500, help="Network buffer size"
    )
    parser.add_argument("--error-size", type=int, default=200, help="Error buffer size")
    parser.add_argument("--wait", type=int, default=5, help="Seconds to wait after load")

    args = parser.parse_args()

    async def main():
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            observer = BrowserStateObserver(
                console_buffer_size=args.console_size,
                network_buffer_size=args.network_size,
                error_buffer_size=args.error_size,
            )
            observer.attach(page)

            print(f"Navigating to {args.url}...")
            await page.goto(args.url, wait_until="networkidle")

            print(f"Waiting {args.wait} seconds...")
            await asyncio.sleep(args.wait)

            # Get stats
            stats = observer.get_stats()
            print(f"\nStats:")
            print(f"  Console messages: {stats.console_total}")
            print(f"    By type: {stats.console_by_type}")
            print(f"  Network requests: {stats.network_total}")
            print(f"    By status: {stats.network_by_status}")
            print(f"    Failed: {stats.network_failed}")
            print(f"    Pending: {stats.network_pending}")
            print(f"  Errors: {stats.errors_total}")

            # Export
            observer.export_json(args.output)
            print(f"\nExported to {args.output}")

            await browser.close()

    asyncio.run(main())
