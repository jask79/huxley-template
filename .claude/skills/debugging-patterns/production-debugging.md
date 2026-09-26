# Enterprise Production Debugging

Advanced debugging patterns for production systems: profiling, heap analysis, distributed tracing.

## Profiling Protocol

### When to Profile

| Symptom | Profile Type | Threshold |
|---------|--------------|-----------|
| CPU | Response time | >2x baseline, sustained high utilization |
| Memory | RSS growth | >10%/hour, suspected leak, OOM crashes |
| Concurrency | Thread/goroutine | Deadlocks, leaks, race conditions |

### Prerequisites by Language

| Language | Tool | Requirement | Overhead |
|----------|------|-------------|----------|
| Python | py-spy | `ptrace_scope=0` on Linux | ~10% |
| JavaScript | V8 profiling | Sampling mode in production | Variable |
| Go | pprof | `import _ "net/http/pprof"` | Minimal |
| Rust | flamegraph | `perf_event_paranoid` setting | Build-time |
| Swift | Instruments | Xcode required | Sampling safe |

### Tool Selection Matrix

| Language | CPU | Memory | References |
|----------|-----|--------|------------|
| Python | py-spy | memray, tracemalloc | objgraph |
| JavaScript | Clinic.js, 0x | Chrome DevTools heap | -- |
| Go | pprof | pprof heap | escape analysis |
| Rust | flamegraph | valgrind | perf |
| Swift/macOS | Instruments Time Profiler | Allocations, Leaks | sample |
| Cross-platform | perf (Linux) | dtrace (macOS/BSD) | -- |
| Other | Query Context7 | Query Context7 | -- |

### Profiling Workflow

1. Identify symptom category (CPU/memory/concurrency)
2. Query Context7: `"How to profile [symptom] in [language]"`
3. Capture profile data with minimal disruption (sampling mode)
4. Generate visualization (flame graph for CPU, heap comparison for memory)
5. Identify hotspots and correlate with code
6. Cross-reference with APM metrics and distributed traces

### Production Safety Rules

- Use sampling profilers to minimize overhead (<5% impact)
- Profile representative workload, not synthetic tests
- Capture baseline before and after optimization
- Enable profiling endpoints behind authentication

---

## Flame Graph Analysis

### When to Use
- CPU profiling, identifying hot code paths, optimization verification

### Reading Patterns

| Pattern | Meaning | Action |
|---------|---------|--------|
| Width | Time spent | Wider = more CPU time |
| Height | Call stack depth | Taller = deeper nesting |
| Plateau | Hot spot | Wide and flat = investigate |
| Towers | Deep recursion | Tall and narrow = check recursion |

### Generation
- Query Context7 for flame graph generation in [language]
- Tools: py-spy, 0x (Node.js), pprof (Go), perf (Linux)

---

## Heap Dump Analysis

### When to Capture
- Memory leak suspected (RSS growing without bound)
- OOM crash investigation (post-mortem analysis)
- Heap fragmentation issues
- GC pressure investigation (excessive pause times)

### Prerequisites

| Language | Tool | Notes |
|----------|------|-------|
| Python | tracemalloc | ~10% overhead, enable before workload |
| Node.js | Heap snapshots | Can pause execution, capture during low traffic |
| Go | Heap profiles | Live objects only, not full heap state |
| Java | jmap | Can trigger full GC, use with caution |

### Detection Strategies

1. **Baseline comparison**: Capture heap at T0, run workload, capture at T1, compare retention
2. **Growth tracking**: Monitor RSS over hours, correlate with traffic patterns
3. **Retention analysis**: Identify objects that should be GC'd but persist

### Leak Detection Patterns

| Pattern | Meaning | Likely Cause |
|---------|---------|--------------|
| Sawtooth without GC drop | Confirmed leak | Objects never collected |
| Linear growth | Accumulator bug | Collections growing unbounded |
| Sudden spike | Cache issue | Cache without eviction policy |

### Analysis Workflow

1. Query Context7: `"How to capture heap dump in [language]"`
2. Capture baseline snapshot
3. Run representative workload
4. Capture second snapshot
5. Query Context7: `"How to analyze [tool] heap dumps for memory leaks"`
6. Identify leaked object types and retainer chains

---

## Distributed Tracing

### When to Use
- Cross-service debugging (issue spans multiple services)
- Latency investigation (slow requests, timeout diagnosis)
- Request flow visualization (understand execution path)
- Dependency mapping (identify service bottlenecks)

### Prerequisites
- **OpenTelemetry**: Instrumentation libraries installed, collector configured
- **Correlation IDs**: Propagated through headers (X-Correlation-ID or W3C Trace Context)
- **Span context**: Parent-child relationships maintained across service boundaries

### Critical Patterns

| Pattern | Implementation |
|---------|----------------|
| Correlation ID | Generate UUID at entry point, add to all logs/headers/DB operations |
| W3C Trace Context | Use `traceparent` and `tracestate` headers |
| Span events | Record important operations (DB queries, external calls) |
| Span attributes | Add context (user_id, order_id, feature flags) for filtering |

### Setup Workflow

1. Query Context7: `"How to setup OpenTelemetry for [language]"`
2. Instrument entry points and service boundaries
3. Propagate trace context through headers
4. Configure exporter (Jaeger, Zipkin, Honeycomb)
5. Add span attributes for debugging context

### Cross-Tool Orchestration

For distributed issues, capture simultaneously:
- Distributed trace + heap dump + CPU profile
- Correlate span IDs with profiler timestamps
- Use trace correlation IDs to link cross-service allocations
- Cross-reference APM metrics with trace data

### Tracing Platforms
- Jaeger (open source, CNCF project)
- Zipkin (Twitter origin, widely adopted)
- Honeycomb (commercial, powerful querying)

---

## APM Integration

### Supported Platforms
New Relic, Datadog APM, Elastic APM, Dynatrace, AWS X-Ray, Honeycomb

### Key Metrics Frameworks

| Framework | Metrics |
|-----------|---------|
| Golden Signals | Latency, traffic, errors, saturation |
| RED Method | Rate, errors, duration |
| USE Method | Utilization, saturation, errors |

### Instrumentation Workflow

1. Query Context7: `"How to instrument [APM tool] for [language]"`
2. Add custom spans for critical operations
3. Add custom attributes for filtering (user context, feature flags)
4. Configure error reporting with stack traces

### Alert Configuration
- Anomaly detection for baseline metrics
- Threshold alerts: error rate >1%, p95 latency >500ms, saturation >80%
- Route to incident management (PagerDuty, Opsgenie)

---

## Core Dump Analysis

### When to Use
- Crash investigation (segfault, abort, signal)
- Post-mortem debugging (no live process)
- Memory corruption analysis

### Prerequisites

| OS | Setup |
|----|-------|
| Linux | `ulimit -c unlimited`, configure core_pattern |
| macOS | Set kern.corefile path, enable core dumps |
| Go | Core dumps include goroutine state |

### Analysis Workflow

1. Query Context7: `"How to analyze core dumps with [debugger] for [language]"`
2. Load core dump in debugger (gdb, lldb, dlv)
3. Examine backtrace and thread states
4. Check local variables and heap state
5. Correlate with logs/metrics at crash time
6. Reproduce in controlled environment

### Post-Mortem Checklist

1. Identify crash location (instruction pointer, stack trace)
2. Check thread states (deadlock, race conditions)
3. Examine local variables and heap state
4. Correlate with logs/metrics at crash time
5. Reproduce in controlled environment
6. Document in Phase 5 for pattern learning

### Debuggers by Platform
- **gdb** (Linux, cross-platform)
- **lldb** (macOS, iOS)
- **delve** (Go-specific)
- Query Context7 for debugger commands and usage

---

## Production Safety Rules (Non-Negotiable)

### Read-Only Debugging
- Never modify production state during investigation
- Use read replicas for database queries
- Copy data to staging for testing hypotheses
- Feature flags for selective debug logging only

### Sampling and Throttling
- Sample 1% of requests for detailed logging (avoid log storms)
- Use probabilistic sampling to reduce overhead
- Time-bound debug instrumentation with automatic cleanup

### Data Protection
- Never log PII (emails, passwords, credit cards)
- Sanitize request/response samples before storage
- Use structured logging with redaction filters

### Minimal Disruption
- Sampling profilers only (<5% overhead)
- Avoid production breakpoints (use conditional logging)
- Dynamic log levels without restart
- APM remote debugging over direct attachment

---

## Emergency Debugging Protocol

### 1. Incident Triage (5 min)
- Check health endpoints, metrics dashboards
- Review recent deployments/config changes
- Query APM for error rate spikes

### 2. Gather Evidence (10 min)
- Export relevant log segments (query Loki/Elasticsearch)
- Capture metrics screenshots (Prometheus, Grafana)
- Download recent heap dumps if available

### 3. Form Hypothesis (5 min)
- Correlate with recent changes (git log, deployment history)
- Query quality.db for similar past incidents (pattern match)
- Identify suspect components from error clusters

### 4. Test Hypothesis (variable)
- Use feature flags to isolate issue (canary testing)
- Compare behavior in canary vs stable deployment
- Rollback if hypothesis confirmed

### 5. Implement Fix (variable)
- Apply hotfix with minimal scope (single component)
- Monitor metrics for improvement (error rate, latency)
- Log incident to Phase 5 for pattern learning
