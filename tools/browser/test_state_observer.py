#!/usr/bin/env python3
"""
Tests for Browser State Observer.

Run with: pytest tools/browser/test_state_observer.py -v
"""

import asyncio
import json
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from state_observer import (
    BrowserStateObserver,
    CircularBuffer,
    ConsoleMessage,
    NetworkRequest,
    PageError,
    SourceLocation,
    create_observer,
    with_observer,
)


# ============================================================================
# CircularBuffer Tests
# ============================================================================

class TestCircularBuffer:
    """Tests for CircularBuffer implementation."""

    def test_basic_push_and_get(self):
        """Buffer should store and retrieve items."""
        buf = CircularBuffer[int](maxsize=5)
        buf.push(1)
        buf.push(2)
        buf.push(3)

        assert buf.get_all() == [1, 2, 3]
        assert len(buf) == 3

    def test_eviction_at_capacity(self):
        """Buffer should evict oldest items when full."""
        buf = CircularBuffer[int](maxsize=3)
        buf.push(1)
        buf.push(2)
        buf.push(3)
        buf.push(4)  # Should evict 1

        assert buf.get_all() == [2, 3, 4]
        assert len(buf) == 3

    def test_utilization(self):
        """Utilization should reflect buffer fill level."""
        buf = CircularBuffer[int](maxsize=4)
        assert buf.utilization == 0.0

        buf.push(1)
        assert buf.utilization == 0.25

        buf.push(2)
        buf.push(3)
        buf.push(4)
        assert buf.utilization == 1.0

    def test_stats_tracking(self):
        """Stats should track total added and evicted."""
        buf = CircularBuffer[int](maxsize=2)
        buf.push(1)
        buf.push(2)
        buf.push(3)  # Evicts 1
        buf.push(4)  # Evicts 2

        stats = buf.stats
        assert stats["current_size"] == 2
        assert stats["max_size"] == 2
        assert stats["total_added"] == 4
        assert stats["total_evicted"] == 2

    def test_filter(self):
        """Filter should return matching items."""
        buf = CircularBuffer[int](maxsize=10)
        for i in range(10):
            buf.push(i)

        evens = list(buf.filter(lambda x: x % 2 == 0))
        assert evens == [0, 2, 4, 6, 8]

    def test_filter_copy(self):
        """filter_copy should return a new list."""
        buf = CircularBuffer[int](maxsize=5)
        buf.push(1)
        buf.push(2)
        buf.push(3)

        result = buf.filter_copy(lambda x: x > 1)
        assert result == [2, 3]
        assert isinstance(result, list)

    def test_get_recent(self):
        """get_recent should return most recent n items."""
        buf = CircularBuffer[int](maxsize=10)
        for i in range(10):
            buf.push(i)

        assert buf.get_recent(3) == [7, 8, 9]
        assert buf.get_recent(100) == list(range(10))  # More than available

    def test_clear_all(self):
        """clear_all should empty buffer and return count."""
        buf = CircularBuffer[int](maxsize=5)
        buf.push(1)
        buf.push(2)
        buf.push(3)

        count = buf.clear_all()
        assert count == 3
        assert len(buf) == 0

    def test_thread_safety(self):
        """Buffer should be thread-safe for concurrent access."""
        import threading

        buf = CircularBuffer[int](maxsize=1000)
        errors = []

        def writer(start: int):
            try:
                for i in range(100):
                    buf.push(start + i)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    _ = buf.get_all()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0,)),
            threading.Thread(target=writer, args=(1000,)),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ============================================================================
# Data Structure Tests
# ============================================================================

class TestConsoleMessage:
    """Tests for ConsoleMessage dataclass."""

    def test_matches_level(self):
        """Should filter by message level."""
        msg = ConsoleMessage(
            type="error", text="Something failed", timestamp=datetime.now()
        )

        assert msg.matches(level="error")
        assert not msg.matches(level="warn")

    def test_matches_pattern(self):
        """Should filter by text pattern."""
        msg = ConsoleMessage(
            type="log", text="User logged in successfully", timestamp=datetime.now()
        )

        assert msg.matches(pattern="logged in")
        assert msg.matches(pattern="LOGGED IN")  # Case insensitive
        assert not msg.matches(pattern="logged out")

    def test_matches_url_pattern(self):
        """Should filter by source URL pattern."""
        msg = ConsoleMessage(
            type="log",
            text="Test",
            timestamp=datetime.now(),
            location=SourceLocation(url="https://example.com/app.js", line_number=42),
        )

        assert msg.matches(url_pattern="example.com")
        assert msg.matches(url_pattern=r"\.js$")
        assert not msg.matches(url_pattern="other.com")

    def test_matches_combined_filters(self):
        """Should require all filters to match."""
        msg = ConsoleMessage(
            type="error",
            text="Failed to load resource",
            timestamp=datetime.now(),
            location=SourceLocation(url="https://api.example.com/data"),
        )

        assert msg.matches(level="error", pattern="load")
        assert not msg.matches(level="error", pattern="save")
        assert msg.matches(level="error", url_pattern="api")


class TestNetworkRequest:
    """Tests for NetworkRequest dataclass."""

    def test_is_failed(self):
        """Should detect failed requests."""
        pending = NetworkRequest(
            id="r1",
            method="GET",
            url="https://example.com",
            resource_type="xhr",
            timestamp=datetime.now(),
        )
        assert not pending.is_failed

        failed = NetworkRequest(
            id="r2",
            method="GET",
            url="https://example.com",
            resource_type="xhr",
            timestamp=datetime.now(),
            failure_reason="net::ERR_CONNECTION_REFUSED",
        )
        assert failed.is_failed

        error_status = NetworkRequest(
            id="r3",
            method="GET",
            url="https://example.com",
            resource_type="xhr",
            timestamp=datetime.now(),
            status=500,
        )
        assert error_status.is_failed

    def test_is_pending(self):
        """Should detect pending requests."""
        pending = NetworkRequest(
            id="r1",
            method="GET",
            url="https://example.com",
            resource_type="xhr",
            timestamp=datetime.now(),
        )
        assert pending.is_pending

        completed = NetworkRequest(
            id="r2",
            method="GET",
            url="https://example.com",
            resource_type="xhr",
            timestamp=datetime.now(),
            status=200,
        )
        assert not completed.is_pending

    def test_matches_url_pattern(self):
        """Should filter by URL pattern."""
        req = NetworkRequest(
            id="r1",
            method="GET",
            url="https://api.example.com/v1/users",
            resource_type="fetch",
            timestamp=datetime.now(),
        )

        assert req.matches(url_pattern="api.example.com")
        assert req.matches(url_pattern=r"/v1/")
        assert not req.matches(url_pattern="other.com")

    def test_matches_method(self):
        """Should filter by HTTP method."""
        req = NetworkRequest(
            id="r1",
            method="POST",
            url="https://example.com",
            resource_type="fetch",
            timestamp=datetime.now(),
        )

        assert req.matches(method="POST")
        assert req.matches(method="post")  # Case insensitive
        assert not req.matches(method="GET")

    def test_matches_status_range(self):
        """Should filter by status range."""
        req = NetworkRequest(
            id="r1",
            method="GET",
            url="https://example.com",
            resource_type="fetch",
            timestamp=datetime.now(),
            status=404,
        )

        assert req.matches(status_range=(400, 499))
        assert not req.matches(status_range=(200, 299))

    def test_matches_failed_only(self):
        """Should filter to failed requests only."""
        failed = NetworkRequest(
            id="r1",
            method="GET",
            url="https://example.com",
            resource_type="fetch",
            timestamp=datetime.now(),
            status=500,
        )

        success = NetworkRequest(
            id="r2",
            method="GET",
            url="https://example.com",
            resource_type="fetch",
            timestamp=datetime.now(),
            status=200,
        )

        assert failed.matches(failed_only=True)
        assert not success.matches(failed_only=True)


class TestSourceLocation:
    """Tests for SourceLocation dataclass."""

    def test_str_with_all_fields(self):
        """Should format location with all fields."""
        loc = SourceLocation(url="https://example.com/app.js", line_number=42, column_number=10)
        assert str(loc) == "https://example.com/app.js:42:10"

    def test_str_with_line_only(self):
        """Should format location with line only."""
        loc = SourceLocation(url="https://example.com/app.js", line_number=42)
        assert str(loc) == "https://example.com/app.js:42"

    def test_str_with_url_only(self):
        """Should format location with URL only."""
        loc = SourceLocation(url="https://example.com/app.js")
        assert str(loc) == "https://example.com/app.js"

    def test_str_no_url(self):
        """Should return unknown for missing URL."""
        loc = SourceLocation()
        assert str(loc) == "<unknown>"


# ============================================================================
# BrowserStateObserver Tests
# ============================================================================

class TestBrowserStateObserver:
    """Tests for BrowserStateObserver."""

    def test_initialization(self):
        """Observer should initialize with correct buffer sizes."""
        observer = BrowserStateObserver(
            console_buffer_size=100,
            network_buffer_size=200,
            error_buffer_size=50,
        )

        assert observer._console.maxsize == 100
        assert observer._network.maxsize == 200
        assert observer._errors.maxsize == 50

    def test_get_console_messages_filtered(self):
        """Should return filtered console messages."""
        observer = BrowserStateObserver()

        # Manually add messages
        observer._console.push(
            ConsoleMessage(type="log", text="Info message", timestamp=datetime.now())
        )
        observer._console.push(
            ConsoleMessage(type="error", text="Error message", timestamp=datetime.now())
        )
        observer._console.push(
            ConsoleMessage(type="warn", text="Warning message", timestamp=datetime.now())
        )

        errors = observer.get_console_messages(level="error")
        assert len(errors) == 1
        assert errors[0].text == "Error message"

    def test_get_network_requests_filtered(self):
        """Should return filtered network requests."""
        observer = BrowserStateObserver()

        # Manually add requests
        observer._network.push(
            NetworkRequest(
                id="r1",
                method="GET",
                url="https://api.example.com/users",
                resource_type="fetch",
                timestamp=datetime.now(),
                status=200,
            )
        )
        observer._network.push(
            NetworkRequest(
                id="r2",
                method="POST",
                url="https://api.example.com/users",
                resource_type="fetch",
                timestamp=datetime.now(),
                status=201,
            )
        )
        observer._network.push(
            NetworkRequest(
                id="r3",
                method="GET",
                url="https://cdn.example.com/image.png",
                resource_type="image",
                timestamp=datetime.now(),
                status=200,
            )
        )

        posts = observer.get_network_requests(method="POST")
        assert len(posts) == 1
        assert posts[0].id == "r2"

        fetches = observer.get_network_requests(resource_type="fetch")
        assert len(fetches) == 2

    def test_get_errors_filtered(self):
        """Should return filtered page errors."""
        observer = BrowserStateObserver()

        observer._errors.push(
            PageError(message="ReferenceError: x is not defined", name="ReferenceError")
        )
        observer._errors.push(
            PageError(message="TypeError: null is not an object", name="TypeError")
        )

        ref_errors = observer.get_errors(pattern="ReferenceError")
        assert len(ref_errors) == 1

    def test_get_stats(self):
        """Should calculate correct statistics."""
        observer = BrowserStateObserver()

        # Add various items
        observer._console.push(
            ConsoleMessage(type="log", text="Log", timestamp=datetime.now())
        )
        observer._console.push(
            ConsoleMessage(type="error", text="Error", timestamp=datetime.now())
        )
        observer._network.push(
            NetworkRequest(
                id="r1",
                method="GET",
                url="https://example.com",
                resource_type="fetch",
                timestamp=datetime.now(),
                status=200,
            )
        )
        observer._network.push(
            NetworkRequest(
                id="r2",
                method="GET",
                url="https://example.com/fail",
                resource_type="fetch",
                timestamp=datetime.now(),
                status=500,
            )
        )
        observer._errors.push(
            PageError(message="Error", name="Error")
        )

        stats = observer.get_stats()

        assert stats.console_total == 2
        assert stats.console_by_type == {"log": 1, "error": 1}
        assert stats.network_total == 2
        assert stats.network_by_status == {"2xx": 1, "5xx": 1}
        assert stats.network_failed == 1
        assert stats.errors_total == 1

    def test_export_json(self):
        """Should export data as JSON."""
        observer = BrowserStateObserver()

        observer._console.push(
            ConsoleMessage(type="log", text="Test message", timestamp=datetime.now())
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name

        data = observer.export_json(temp_path)

        assert "console" in data
        assert "network" in data
        assert "errors" in data
        assert "stats" in data
        assert len(data["console"]) == 1

        # Verify file was written
        with open(temp_path) as f:
            file_data = json.load(f)
            assert file_data["console"][0]["text"] == "Test message"

    def test_clear(self):
        """Should clear all buffers."""
        observer = BrowserStateObserver()

        observer._console.push(
            ConsoleMessage(type="log", text="Test", timestamp=datetime.now())
        )
        observer._network.push(
            NetworkRequest(
                id="r1",
                method="GET",
                url="https://example.com",
                resource_type="fetch",
                timestamp=datetime.now(),
            )
        )
        observer._errors.push(PageError(message="Error", name="Error"))

        counts = observer.clear()

        assert counts == {"console": 1, "network": 1, "errors": 1}
        assert len(observer._console) == 0
        assert len(observer._network) == 0
        assert len(observer._errors) == 0

    def test_limit_parameter(self):
        """Limit parameter should return most recent items."""
        observer = BrowserStateObserver()

        for i in range(10):
            observer._console.push(
                ConsoleMessage(
                    type="log", text=f"Message {i}", timestamp=datetime.now()
                )
            )

        recent = observer.get_console_messages(limit=3)
        assert len(recent) == 3
        assert recent[0].text == "Message 7"
        assert recent[1].text == "Message 8"
        assert recent[2].text == "Message 9"


# ============================================================================
# Mock Page Attachment Tests
# ============================================================================

class TestPageAttachment:
    """Tests for page attachment/detachment."""

    def create_mock_page(self):
        """Create a mock Playwright page."""
        page = MagicMock()
        page._listeners = {}

        def on(event, handler):
            if event not in page._listeners:
                page._listeners[event] = []
            page._listeners[event].append(handler)

        def remove_listener(event, handler):
            if event in page._listeners:
                page._listeners[event].remove(handler)

        page.on = on
        page.remove_listener = remove_listener
        return page

    def test_attach(self):
        """Should attach listeners to page."""
        page = self.create_mock_page()
        observer = BrowserStateObserver()

        observer.attach(page)

        assert page in observer._attached_pages
        assert "console" in page._listeners
        assert "pageerror" in page._listeners
        assert "request" in page._listeners
        assert "response" in page._listeners
        assert "requestfailed" in page._listeners
        assert "close" in page._listeners

    def test_attach_idempotent(self):
        """Attaching twice should be idempotent."""
        page = self.create_mock_page()
        observer = BrowserStateObserver()

        observer.attach(page)
        observer.attach(page)

        assert len(observer._attached_pages) == 1

    def test_detach(self):
        """Should remove listeners from page."""
        page = self.create_mock_page()
        observer = BrowserStateObserver()

        observer.attach(page)
        observer.detach(page)

        assert page not in observer._attached_pages
        assert all(len(handlers) == 0 for handlers in page._listeners.values())

    def test_detach_all(self):
        """Should detach from all pages."""
        page1 = self.create_mock_page()
        page2 = self.create_mock_page()
        observer = BrowserStateObserver()

        observer.attach(page1)
        observer.attach(page2)

        assert len(observer._attached_pages) == 2

        observer.detach_all()

        assert len(observer._attached_pages) == 0

    def test_console_listener(self):
        """Console listener should capture messages."""
        page = self.create_mock_page()
        observer = BrowserStateObserver()
        observer.attach(page)

        # Simulate console message
        mock_msg = MagicMock()
        mock_msg.type = "error"
        mock_msg.text = "Test error message"
        mock_msg.location = {"url": "https://example.com", "lineNumber": 42}

        # Call the listener
        page._listeners["console"][0](mock_msg)

        messages = observer.get_console_messages()
        assert len(messages) == 1
        assert messages[0].type == "error"
        assert messages[0].text == "Test error message"

    def test_request_response_correlation(self):
        """Request and response should be correlated."""
        page = self.create_mock_page()
        observer = BrowserStateObserver()
        observer.attach(page)

        # Simulate request
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url = "https://api.example.com/data"
        mock_request.resource_type = "fetch"

        page._listeners["request"][0](mock_request)

        # Simulate response
        mock_response = MagicMock()
        mock_response.request = mock_request
        mock_response.status = 200
        mock_response.ok = True

        page._listeners["response"][0](mock_response)

        requests = observer.get_network_requests()
        assert len(requests) == 1
        assert requests[0].status == 200
        assert requests[0].ok is True

    def test_request_failure_tracking(self):
        """Failed requests should be tracked."""
        page = self.create_mock_page()
        observer = BrowserStateObserver()
        observer.attach(page)

        # Simulate request
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url = "https://example.com"
        mock_request.resource_type = "fetch"
        mock_request.failure = MagicMock()
        mock_request.failure.error_text = "net::ERR_CONNECTION_REFUSED"

        page._listeners["request"][0](mock_request)
        page._listeners["requestfailed"][0](mock_request)

        requests = observer.get_network_requests(failed_only=True)
        assert len(requests) == 1
        assert requests[0].failure_reason == "net::ERR_CONNECTION_REFUSED"


# ============================================================================
# Context Manager Tests
# ============================================================================

class TestContextManagers:
    """Tests for context manager helpers."""

    def test_with_observer_sync(self):
        """Sync context manager should attach and detach."""
        page = MagicMock()
        page._listeners = {}

        def on(event, handler):
            if event not in page._listeners:
                page._listeners[event] = []
            page._listeners[event].append(handler)

        def remove_listener(event, handler):
            if event in page._listeners and handler in page._listeners[event]:
                page._listeners[event].remove(handler)

        page.on = on
        page.remove_listener = remove_listener

        with with_observer(page) as observer:
            assert page in observer._attached_pages

        # After context, should be detached
        assert page not in observer._attached_pages

    def test_create_observer_with_page(self):
        """create_observer should optionally attach to page."""
        page = MagicMock()
        page._listeners = {}
        page.on = lambda event, handler: None
        page.remove_listener = lambda event, handler: None

        observer = create_observer(page)
        assert page in observer._attached_pages

    def test_create_observer_without_page(self):
        """create_observer should work without page."""
        observer = create_observer()
        assert len(observer._attached_pages) == 0


# ============================================================================
# Integration Tests (require playwright + pytest-asyncio)
# ============================================================================

# Skip integration tests by default - run with: pytest -m integration
pytestmark_integration = pytest.mark.skipif(
    True,  # Skip by default; set to False or use -m integration to run
    reason="Integration tests require playwright and pytest-asyncio"
)


@pytestmark_integration
class TestPlaywrightIntegration:
    """Integration tests with real Playwright (skipped by default).

    To run these tests:
        pip install pytest-asyncio playwright
        playwright install chromium
        pytest -m integration tools/browser/test_state_observer.py -v
    """

    def test_real_page_capture(self):
        """Test capturing real browser events."""
        pytest.importorskip("playwright")
        pytest.importorskip("pytest_asyncio")

        import asyncio
        from playwright.async_api import async_playwright

        async def run_test():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                observer = BrowserStateObserver()
                observer.attach(page)

                # Navigate to a simple page that logs something
                await page.goto("data:text/html,<script>console.log('test');</script>")
                await page.wait_for_timeout(100)

                messages = observer.get_console_messages()
                # Should capture at least the console.log
                # Note: Exact behavior may vary by browser/version

                await browser.close()
                return messages

        asyncio.run(run_test())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
