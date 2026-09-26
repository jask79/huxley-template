# Chrome DevTools MCP Debugging

Browser debugging patterns using Chrome DevTools MCP integration.

## Overview

Chrome DevTools MCP (`mcp__chrome-devtools__*`) provides browser-level debugging for web applications in Huxley.

**When to use:**
- Frontend JavaScript errors
- Network request failures
- Performance issues in web apps
- DOM manipulation bugs

## Core Debugging Functions

### 1. Console Error Collection

```python
def collect_console_errors(page_id=None):
    """
    Collect all console errors from the browser
    """
    # List pages to find target
    pages = mcp__chrome-devtools__list_pages()

    if page_id is None:
        page_id = pages[0]['id']  # Use first page

    # Select the page
    mcp__chrome-devtools__select_page(pageId=page_id)

    # Get console messages filtered by error types
    messages = mcp__chrome-devtools__list_console_messages(
        types=['error', 'warn', 'assert']
    )

    return {
        'page_url': pages[0].get('url'),
        'errors': messages,
        'count': len(messages)
    }
```

### 2. Network Request Forensics

```python
def analyze_failed_requests(page_id=None):
    """
    Find and analyze failed network requests
    """
    mcp__chrome-devtools__select_page(pageId=page_id)

    # Get all network requests
    requests = mcp__chrome-devtools__list_network_requests(
        resourceTypes=['xhr', 'fetch', 'document']
    )

    failed = []
    for req in requests:
        # Get full request details
        details = mcp__chrome-devtools__get_network_request(reqid=req['reqid'])

        if details.get('response', {}).get('status', 0) >= 400:
            failed.append({
                'url': details.get('request', {}).get('url'),
                'method': details.get('request', {}).get('method'),
                'status': details.get('response', {}).get('status'),
                'error': details.get('error')
            })

    return failed
```

### 3. Page State Snapshot

```python
def capture_page_state():
    """
    Capture current page state for debugging
    """
    # Take accessibility snapshot (better than screenshot for debugging)
    snapshot = mcp__chrome-devtools__take_snapshot()

    # Take screenshot for visual reference
    screenshot = mcp__chrome-devtools__take_screenshot(
        format='png',
        fullPage=False
    )

    # Get console messages
    console = mcp__chrome-devtools__list_console_messages()

    # Get network requests
    network = mcp__chrome-devtools__list_network_requests()

    return {
        'snapshot': snapshot,
        'screenshot': screenshot,
        'console': console,
        'network': network
    }
```

### 4. JavaScript Evaluation

```python
def evaluate_debug_expression(expression, element_uid=None):
    """
    Evaluate JavaScript for debugging
    """
    if element_uid:
        # Evaluate on specific element
        result = mcp__chrome-devtools__evaluate_script(
            function=f"(el) => {{ {expression} }}",
            args=[{'uid': element_uid}]
        )
    else:
        # Evaluate on page
        result = mcp__chrome-devtools__evaluate_script(
            function=f"() => {{ {expression} }}"
        )

    return result
```

### 5. Performance Trace Capture

```python
def capture_performance_trace(reload=True, duration_seconds=5):
    """
    Capture performance trace for analysis
    """
    import time

    # Start trace with optional reload
    mcp__chrome-devtools__performance_start_trace(
        reload=reload,
        autoStop=False,
        filePath='/tmp/trace.json.gz'
    )

    # Wait for trace duration
    time.sleep(duration_seconds)

    # Stop and get results
    result = mcp__chrome-devtools__performance_stop_trace(
        filePath='/tmp/trace.json.gz'
    )

    return result
```

### 6. Element Interaction Debugging

```python
def debug_element_interaction(uid, action='click'):
    """
    Debug element interaction issues
    """
    # Take snapshot to verify element exists
    snapshot = mcp__chrome-devtools__take_snapshot()

    # Hover to check element is interactive
    mcp__chrome-devtools__hover(uid=uid)

    # Perform action
    if action == 'click':
        mcp__chrome-devtools__click(uid=uid)
    elif action == 'fill':
        mcp__chrome-devtools__fill(uid=uid, value='test')

    # Capture state after interaction
    post_snapshot = mcp__chrome-devtools__take_snapshot()
    post_console = mcp__chrome-devtools__list_console_messages()

    return {
        'pre_snapshot': snapshot,
        'post_snapshot': post_snapshot,
        'console_after': post_console
    }
```

### 7. Full Debug Workflow

```python
def comprehensive_page_debug(url=None):
    """
    Complete debug workflow for a web page
    """
    # Navigate if URL provided
    if url:
        mcp__chrome-devtools__navigate_page(type='url', url=url)
        mcp__chrome-devtools__wait_for(text='', timeout=5000)  # Wait for load

    # Collect all diagnostic data
    diagnostics = {
        'console_errors': collect_console_errors(),
        'failed_requests': analyze_failed_requests(),
        'page_state': capture_page_state()
    }

    # Analyze patterns
    analysis = analyze_debug_patterns(diagnostics)

    return {
        'diagnostics': diagnostics,
        'analysis': analysis,
        'hypotheses': generate_hypotheses(analysis)
    }
```

## Debugging Checklist

**1. Initial Assessment:**
- [ ] List pages: `list_pages()`
- [ ] Select target page: `select_page(pageId)`
- [ ] Take snapshot: `take_snapshot()`
- [ ] Check console: `list_console_messages(types=['error', 'warn'])`

**2. Network Analysis:**
- [ ] List requests: `list_network_requests()`
- [ ] Check failed requests (4xx, 5xx status)
- [ ] Examine request/response details
- [ ] Look for CORS errors

**3. JavaScript Debugging:**
- [ ] Evaluate expressions: `evaluate_script()`
- [ ] Check for undefined variables
- [ ] Verify data structures
- [ ] Test event handlers

**4. Performance:**
- [ ] Start trace: `performance_start_trace()`
- [ ] Capture interactions
- [ ] Stop and analyze: `performance_stop_trace()`
- [ ] Use `performance_analyze_insight()` for specific metrics

**5. Visual Verification:**
- [ ] Take screenshots: `take_screenshot()`
- [ ] Compare expected vs actual
- [ ] Check responsive layouts

## Error Categories

| Error Type | Symptoms | Debug Approach |
|------------|----------|----------------|
| JavaScript Error | Console errors, broken functionality | Check console messages, evaluate expressions |
| Network Failure | Failed requests, loading issues | Analyze network requests, check CORS |
| Performance | Slow loading, janky interactions | Capture performance trace |
| DOM Issues | Missing elements, wrong content | Take snapshots, verify element UIDs |
| State Issues | Unexpected behavior | Evaluate JavaScript state |

## Integration with Huxley

**Store patterns in quality.db:**
```python
def log_browser_debug_pattern(error, resolution):
    """Log browser debugging pattern for future reference"""
    import sqlite3
    import json

    db = sqlite3.connect('{{CATALYST_ROOT}}/monitoring/quality.db')
    db.execute("""
        INSERT INTO debug_patterns (
            error_signature, context_fingerprint,
            root_cause, resolution, mode
        ) VALUES (?, ?, ?, ?, ?)
    """, (
        f"browser:{error.type}:{error.message}",
        json.dumps({'url': error.url, 'element': error.element}),
        error.root_cause,
        resolution,
        'browser'
    ))
    db.commit()
```
