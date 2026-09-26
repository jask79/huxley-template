# Huxley Agentic Loop Architecture

## Executive Summary

Transform Huxley agents from one-shot executors to autonomous iterators that self-correct until success. Agents execute → validate → iterate in tight loops with built-in safety mechanisms and escalation paths.

---

## 1. Core Architecture

### Loop Pattern Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    {{ORCHESTRATOR_NAME_UPPER}} ORCHESTRATION                      │
│  - Delegates task with success criteria                     │
│  - Monitors iteration count                                  │
│  - Receives completion or escalation                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    AGENT AUTONOMOUS LOOP                     │
│                                                              │
│  ┌──────────────┐                                           │
│  │   EXECUTE    │──────────────┐                            │
│  │   Task       │              │                            │
│  └──────────────┘              │                            │
│         │                      │                            │
│         ▼                      │                            │
│  ┌──────────────┐              │                            │
│  │   VALIDATE   │              │                            │
│  │   Results    │              │                            │
│  └──────────────┘              │                            │
│         │                      │                            │
│         ▼                      │                            │
│  ┌──────────────┐              │                            │
│  │   EVALUATE   │              │                            │
│  │   Feedback   │              │                            │
│  └──────────────┘              │                            │
│         │                      │                            │
│    ┌────┴────┐                 │                            │
│    │         │                 │                            │
│  SUCCESS  FAILURE              │                            │
│    │         │                 │                            │
│    │    ┌────┴─────┐           │                            │
│    │    │          │           │                            │
│    │  FIXABLE  ESCALATE        │                            │
│    │    │          │           │                            │
│    │    └──────────┘           │                            │
│    │         │                 │                            │
│    │         └─────────────────┘                            │
│    │                                                         │
│    ▼                                                         │
│  COMPLETE                                                    │
└─────────────────────────────────────────────────────────────┘
```

### Three-State Outcome Model

**1. SUCCESS** - Task complete, validation passed
- Return results to {{ORCHESTRATOR_NAME}}
- Update agent effectiveness metrics
- Store learned patterns

**2. ITERATE** - Fixable issue detected
- Analyze failure cause
- Generate fix strategy
- Loop back to EXECUTE (up to max iterations)
- Track iteration history

**3. ESCALATE** - Cannot fix autonomously
- Document failure analysis
- Return to {{ORCHESTRATOR_NAME}} with context
- {{ORCHESTRATOR_NAME}} decides: different agent, human intervention, or approach change

---

## 2. Feedback System Design

### Feedback Sources by Domain

```yaml
feedback_mechanisms:

  # Code Quality Feedback
  code_validation:
    - linting: "ESLint, SwiftLint, Ruff results"
    - type_checking: "TypeScript, mypy results"
    - compilation: "Build success/failure + error messages"
    - static_analysis: "Security scans, complexity metrics"

  # Runtime Feedback
  execution:
    - test_results: "Unit/integration test pass/fail"
    - error_logs: "Runtime exceptions, stack traces"
    - performance: "Execution time, memory usage, bundle size"
    - coverage: "Code coverage percentage"

  # Platform-Specific Feedback
  mobile:
    - xcode_build: "Build logs, compiler errors"
    - simulator: "Runtime behavior, UI correctness"
    - app_launch: "Crash reports, startup time"

  web:
    - browser_console: "JS errors, network failures"
    - lighthouse: "Performance, accessibility, SEO scores"
    - visual_regression: "Screenshot diffs"

  automation:
    - browser_state: "Page load success, element presence"
    - network_logs: "HTTP status codes, API responses"
    - captcha_solving: "Success/failure rates"
```

### Validation Framework

Each agent type defines **success criteria** as structured checks:

```typescript
interface SuccessCriteria {
  // Hard requirements (must pass)
  required: {
    builds: boolean;           // Code compiles/builds
    tests_pass: boolean;       // Test suite passes
    no_errors: boolean;        // No runtime errors
  };

  // Soft requirements (should pass, may iterate)
  preferred: {
    linting: boolean;          // Style/quality checks
    performance: {
      threshold: number;       // e.g., < 100ms response time
      actual: number;
    };
    coverage: {
      threshold: number;       // e.g., > 80% coverage
      actual: number;
    };
  };

  // Custom domain checks
  custom: Record<string, boolean>;
}
```

---

## 3. Agent Loop Protocol

### Loop Execution Specification

```yaml
loop_protocol:

  initialization:
    - agent: "Receives task from {{ORCHESTRATOR_NAME}}"
    - context: "Success criteria, max iterations, timeout"
    - state: "Initialize iteration counter = 0"

  execute_phase:
    - action: "Perform primary task (build, test, automate)"
    - capture: "Collect all feedback sources"
    - log: "Store execution artifacts (logs, screenshots, diffs)"

  validate_phase:
    - collect: "Gather feedback from all relevant sources"
    - structure: "Map feedback to SuccessCriteria format"
    - timestamp: "Record validation attempt"

  evaluate_phase:
    - check_required: "All hard requirements met?"
    - check_preferred: "Soft requirements met or acceptable?"
    - classify_failures: "Categorize each failure type"
    - determine_fixability: "Can agent fix this autonomously?"

  decision_phase:
    success:
      - condition: "All required criteria met"
      - action: "Return results to {{ORCHESTRATOR_NAME}}"
      - cleanup: "Store metrics, patterns learned"

    iterate:
      - condition: "Fixable failure + iterations < max"
      - action: "Generate fix strategy"
      - increment: "iteration_counter++"
      - loop: "Back to execute_phase with fix applied"

    escalate:
      - condition: "Non-fixable OR iterations >= max"
      - package: "Failure analysis + iteration history"
      - return: "To {{ORCHESTRATOR_NAME}} with escalation context"

  safety_mechanisms:
    - max_iterations: 5  # Prevent infinite loops
    - timeout: "30 minutes total"
    - resource_limits: "CPU/memory thresholds"
    - escalation_triggers: "Critical errors, security issues"
```

### Iteration Intelligence

Agents don't blindly retry - they **learn from failures**:

**Fix Strategy Generation:**
```python
def generate_fix_strategy(failure_feedback: FeedbackData) -> FixStrategy:
    """
    Analyze failure and determine intelligent fix approach.
    """

    # Pattern matching from learned fixes
    if failure_feedback.error_type in known_patterns:
        return known_patterns[failure_feedback.error_type].fix

    # Categorize failure
    categories = {
        'syntax': fix_syntax_error,
        'type_mismatch': fix_type_error,
        'missing_dependency': install_dependency,
        'test_failure': debug_test_logic,
        'performance': optimize_code,
        'ui_regression': fix_visual_issue,
    }

    failure_category = classify_failure(failure_feedback)
    fix_function = categories.get(failure_category, escalate)

    return fix_function(failure_feedback)
```

---

## 4. Integration with Huxley Agent System

### {{ORCHESTRATOR_NAME}} Delegation Enhancement

**Current Pattern:**
```typescript
// One-shot execution
orchestrator.delegate({
  agent: "Frontend Dev",
  task: "Build header component",
  context: {...}
});
// Agent returns → Done
```

**Enhanced Pattern:**
```typescript
// Autonomous loop delegation
orchestrator.delegate({
  agent: "Frontend Dev",
  task: "Build header component",
  context: {...},

  // NEW: Loop configuration
  loop_config: {
    success_criteria: {
      required: {
        builds: true,
        tests_pass: true,
        no_errors: true
      },
      preferred: {
        linting: true,
        coverage: { threshold: 80, actual: 0 }
      }
    },
    max_iterations: 5,
    timeout_minutes: 30,
    escalation_triggers: ['security_vulnerability', 'breaking_change']
  }
});

// Agent iterates autonomously → Returns when complete OR escalates
```

### State Management

**Loop State Tracking:**
```json
{
  "loop_id": "frontend-dev-header-20250127-001",
  "agent": "Frontend Dev",
  "task": "Build header component",
  "status": "iterating",

  "iterations": [
    {
      "iteration": 1,
      "timestamp": "2025-01-27T10:00:00Z",
      "execution": {
        "files_modified": ["src/components/Header.tsx"],
        "commands_run": ["npm run build", "npm test"]
      },
      "feedback": {
        "builds": true,
        "tests_pass": false,
        "errors": ["TypeError: Cannot read property 'map' of undefined"]
      },
      "evaluation": "iterate",
      "fix_strategy": "Add null check for props.items"
    },
    {
      "iteration": 2,
      "timestamp": "2025-01-27T10:05:00Z",
      "execution": {
        "files_modified": ["src/components/Header.tsx"],
        "commands_run": ["npm run build", "npm test"]
      },
      "feedback": {
        "builds": true,
        "tests_pass": true,
        "linting": true,
        "coverage": { "actual": 85 }
      },
      "evaluation": "success"
    }
  ],

  "final_status": "success",
  "total_iterations": 2,
  "total_time_seconds": 320
}
```

### Communication Protocol

**Agent → {{ORCHESTRATOR_NAME}} Messages:**

```yaml
# During iteration (optional progress updates)
progress_update:
  type: "iteration_progress"
  loop_id: "frontend-dev-header-20250127-001"
  iteration: 2
  status: "iterating"
  message: "Fixed null check, re-running tests..."

# On success
success_completion:
  type: "loop_complete"
  loop_id: "frontend-dev-header-20250127-001"
  status: "success"
  iterations: 2
  results: {...}
  artifacts: ["src/components/Header.tsx", "test/Header.test.tsx"]

# On escalation
escalation:
  type: "loop_escalated"
  loop_id: "frontend-dev-header-20250127-001"
  status: "escalated"
  iterations: 5
  reason: "max_iterations_reached"
  failure_analysis: {
    category: "test_failure",
    error: "Timeout in integration test",
    context: "API mock server not responding",
    attempted_fixes: [...]
  }
```

---

## 5. Implementation Examples

### Example 1: 🎨 Frontend Dev with Testing Feedback

**Task:** Build a React component with tests

```typescript
// Frontend Dev Agent Loop Implementation

class FrontendDevAgent {
  async executeWithLoop(task: Task, criteria: SuccessCriteria): Promise<Result> {
    let iteration = 0;
    const maxIterations = 5;

    while (iteration < maxIterations) {
      iteration++;
      console.log(`Iteration ${iteration}/${maxIterations}`);

      // EXECUTE: Build component
      const buildResult = await this.buildComponent(task);

      // VALIDATE: Run tests and linting
      const feedback = await this.gatherFeedback({
        build: buildResult,
        tests: await this.runTests(),
        linting: await this.runLinter(),
        typeCheck: await this.runTypeChecker()
      });

      // EVALUATE: Check against criteria
      const evaluation = this.evaluateFeedback(feedback, criteria);

      if (evaluation.status === 'success') {
        return {
          status: 'complete',
          iterations: iteration,
          artifacts: buildResult.files
        };
      }

      if (evaluation.status === 'escalate') {
        return {
          status: 'escalated',
          reason: evaluation.reason,
          iterations: iteration,
          failureAnalysis: evaluation.analysis
        };
      }

      // ITERATE: Generate and apply fix
      const fixStrategy = this.generateFix(evaluation.failures);
      await this.applyFix(fixStrategy);
    }

    // Max iterations reached
    return {
      status: 'escalated',
      reason: 'max_iterations_reached',
      iterations: iteration
    };
  }

  evaluateFeedback(feedback: Feedback, criteria: SuccessCriteria): Evaluation {
    const failures = [];

    // Check required criteria
    if (!feedback.build.success) {
      failures.push({
        type: 'build_failure',
        fixable: this.canFixBuildError(feedback.build.errors),
        errors: feedback.build.errors
      });
    }

    if (!feedback.tests.allPassed) {
      failures.push({
        type: 'test_failure',
        fixable: this.canFixTestError(feedback.tests.failures),
        failures: feedback.tests.failures
      });
    }

    // Determine if fixable
    const allFixable = failures.every(f => f.fixable);
    const hasBlockingErrors = failures.some(f => f.type === 'build_failure');

    if (failures.length === 0) {
      return { status: 'success' };
    } else if (allFixable && !hasBlockingErrors) {
      return { status: 'iterate', failures };
    } else {
      return {
        status: 'escalate',
        reason: 'non_fixable_error',
        analysis: this.analyzeFailures(failures)
      };
    }
  }

  generateFix(failures: Failure[]): FixStrategy {
    // Pattern matching for common errors
    for (const failure of failures) {
      if (failure.errors.includes('Cannot find module')) {
        return { action: 'install_dependency', target: this.extractModule(failure) };
      }
      if (failure.errors.includes('Type mismatch')) {
        return { action: 'fix_types', target: this.extractTypeError(failure) };
      }
      if (failure.type === 'test_failure') {
        return { action: 'fix_test_logic', target: failure.failures[0] };
      }
    }

    // Fallback
    return { action: 'escalate', reason: 'unknown_error_pattern' };
  }
}
```

**Feedback Flow:**
```
Build component → npm run build → Check exit code
                ↓
                Success/Failure + error messages
                ↓
Run tests → npm test → Parse TAP/JSON output
                ↓
                Pass/Fail + failure details
                ↓
Linting → eslint → Parse warnings/errors
                ↓
Type check → tsc --noEmit → Parse type errors
                ↓
EVALUATE all feedback → SUCCESS | ITERATE | ESCALATE
```

### Example 2: 📱 Mobile Dev with Build/Simulator Feedback

**Task:** Build iOS feature with UI validation

```swift
// Mobile Dev Agent Loop Implementation

class MobileDevAgent {
  async executeWithLoop(task: Task, criteria: SuccessCriteria): Promise<Result> {
    let iteration = 0;
    const maxIterations = 5;

    while (iteration < maxIterations) {
      iteration++;
      console.log(`iOS Build Iteration ${iteration}/${maxIterations}`);

      // EXECUTE: Implement feature in Swift
      await this.implementFeature(task);

      // VALIDATE: Build → Run → Visual Check
      const feedback = await this.gatherFeedback({
        xcodeBuild: await this.runXcodeBuild(),
        simulator: await this.launchSimulator(),
        uiTests: await this.runUITests(),
        visualCheck: await this.captureScreenshots()
      });

      // EVALUATE
      const evaluation = this.evaluateFeedback(feedback, criteria);

      if (evaluation.status === 'success') {
        return {
          status: 'complete',
          iterations: iteration,
          screenshots: feedback.visualCheck.screenshots
        };
      }

      if (evaluation.status === 'escalate') {
        return {
          status: 'escalated',
          reason: evaluation.reason,
          buildLogs: feedback.xcodeBuild.logs
        };
      }

      // ITERATE: Fix based on build/runtime errors
      const fixStrategy = this.generateIOSFix(evaluation.failures);
      await this.applyFix(fixStrategy);
    }

    return { status: 'escalated', reason: 'max_iterations' };
  }

  async gatherFeedback(sources: FeedbackSources): Promise<Feedback> {
    return {
      builds: sources.xcodeBuild.exitCode === 0,
      buildErrors: sources.xcodeBuild.errors,
      launchSuccess: sources.simulator.appLaunched,
      crashReports: sources.simulator.crashes,
      uiTestsPassed: sources.uiTests.allPassed,
      visualRegression: sources.visualCheck.diffs.length === 0
    };
  }

  generateIOSFix(failures: Failure[]): FixStrategy {
    for (const failure of failures) {
      // Build errors
      if (failure.buildErrors.includes('Use of unresolved identifier')) {
        return { action: 'add_import', target: this.extractMissingImport(failure) };
      }
      if (failure.buildErrors.includes('Type mismatch')) {
        return { action: 'fix_swift_types', target: failure.context };
      }

      // Runtime errors
      if (failure.crashReports.length > 0) {
        const crash = failure.crashReports[0];
        if (crash.reason.includes('nil')) {
          return { action: 'add_nil_check', target: crash.stackTrace };
        }
      }

      // UI test failures
      if (!failure.uiTestsPassed) {
        return { action: 'fix_ui_interaction', target: failure.failedTests[0] };
      }
    }

    return { action: 'escalate' };
  }
}
```

**Feedback Flow:**
```
Implement in Swift → xcodebuild → Build success/failure
                    ↓
                    Compiler errors + warnings
                    ↓
Launch Simulator → xcrun simctl → App launches
                    ↓
                    Crash reports
                    ↓
Run UI Tests → xcodebuild test → XCTest results
                    ↓
                    Pass/Fail + failure reasons
                    ↓
Capture Screenshots → Compare to baseline → Diffs
                    ↓
EVALUATE → SUCCESS | ITERATE | ESCALATE
```

### Example 3: 🐲 Bowser with Browser Automation Validation

**Task:** Automate account registration with CAPTCHA

```typescript
// Bowser Agent Loop Implementation

class BowserAgent {
  async executeWithLoop(task: Task, criteria: SuccessCriteria): Promise<Result> {
    let iteration = 0;
    const maxIterations = 3; // Lower for browser automation

    while (iteration < maxIterations) {
      iteration++;
      console.log(`Browser Automation Iteration ${iteration}/${maxIterations}`);

      // EXECUTE: Run Playwright automation
      const page = await this.launchBrowser();
      const result = await this.performRegistration(page, task);

      // VALIDATE: Check success indicators
      const feedback = await this.gatherFeedback({
        pageState: await this.checkPageState(page),
        networkLogs: await this.getNetworkLogs(page),
        captchaSolved: result.captchaSolved,
        formSubmitted: result.submitted,
        accountCreated: await this.verifyAccountCreation(page)
      });

      await page.close();

      // EVALUATE
      const evaluation = this.evaluateFeedback(feedback, criteria);

      if (evaluation.status === 'success') {
        return {
          status: 'complete',
          iterations: iteration,
          credentials: result.credentials
        };
      }

      if (evaluation.status === 'escalate') {
        return {
          status: 'escalated',
          reason: evaluation.reason,
          screenshots: await this.captureFailureState()
        };
      }

      // ITERATE: Adjust automation strategy
      const fixStrategy = this.generateBrowserFix(evaluation.failures);
      await this.applyFix(fixStrategy);
      await this.sleep(2000); // Rate limiting between attempts
    }

    return { status: 'escalated', reason: 'max_iterations' };
  }

  evaluateFeedback(feedback: Feedback, criteria: SuccessCriteria): Evaluation {
    const failures = [];

    // CAPTCHA failures
    if (!feedback.captchaSolved && criteria.required.captcha_solved) {
      failures.push({
        type: 'captcha_failure',
        fixable: iteration < 3, // Retry CAPTCHA a few times
        context: 'reCAPTCHA v2 solving failed'
      });
    }

    // Form submission failures
    if (!feedback.formSubmitted) {
      const reason = this.analyzeFormFailure(feedback.pageState);
      failures.push({
        type: 'form_submission_failure',
        fixable: reason.fixable,
        context: reason
      });
    }

    // Network errors
    if (feedback.networkLogs.some(log => log.status >= 500)) {
      failures.push({
        type: 'server_error',
        fixable: false, // Can't fix server-side issues
        context: 'Target site experiencing errors'
      });
    }

    if (failures.length === 0) {
      return { status: 'success' };
    } else if (failures.every(f => f.fixable)) {
      return { status: 'iterate', failures };
    } else {
      return { status: 'escalate', reason: 'non_fixable', analysis: failures };
    }
  }

  generateBrowserFix(failures: Failure[]): FixStrategy {
    for (const failure of failures) {
      if (failure.type === 'captcha_failure') {
        return { action: 'retry_captcha', method: 'playwright-recaptcha' };
      }
      if (failure.type === 'form_submission_failure') {
        if (failure.context.missingFields) {
          return { action: 'fill_missing_fields', fields: failure.context.missingFields };
        }
        if (failure.context.validationError) {
          return { action: 'fix_validation', error: failure.context.validationError };
        }
      }
      if (failure.type === 'element_not_found') {
        return { action: 'update_selector', selector: failure.context.selector };
      }
    }

    return { action: 'escalate' };
  }
}
```

**Feedback Flow:**
```
Launch browser → Navigate to site → Page load success
                ↓
Fill form → Field validation → Success/errors
                ↓
Solve CAPTCHA → playwright-recaptcha → Success (85-90%)
                ↓
Submit form → POST request → 200 OK or error
                ↓
Check success page → URL change + success message → Account created
                ↓
EVALUATE → SUCCESS | ITERATE (retry CAPTCHA) | ESCALATE
```

---

## 6. Safety Mechanisms

### Preventing Runaway Loops

```yaml
safety_controls:

  iteration_limits:
    default_max: 5
    by_agent_type:
      frontend_dev: 5
      mobile_dev: 5
      bowser: 3  # Lower for external dependencies
      backend_dev: 5
      automator: 3

  time_limits:
    max_loop_duration: "30 minutes"
    per_iteration_timeout: "10 minutes"

  resource_limits:
    max_memory_mb: 2048
    max_cpu_percent: 80
    max_concurrent_loops: 10

  escalation_triggers:
    # Immediate escalation, no iteration
    critical_errors:
      - "security_vulnerability"
      - "data_loss_risk"
      - "breaking_change_detected"
      - "external_service_down"

    # Escalate after N failures
    repeated_failures:
      same_error_threshold: 3
      action: "escalate_with_pattern_analysis"

  circuit_breaker:
    # Stop all loops if system health degraded
    conditions:
      - "disk_space_low"
      - "memory_pressure_high"
      - "too_many_failed_loops"
    action: "pause_all_loops_and_alert"
```

### Monitoring and Observability

```typescript
interface LoopMetrics {
  loop_id: string;
  agent: string;
  start_time: string;
  current_iteration: number;
  status: 'running' | 'success' | 'escalated' | 'failed';

  performance: {
    iteration_times: number[];
    total_time_seconds: number;
    resource_usage: {
      peak_memory_mb: number;
      avg_cpu_percent: number;
    };
  };

  quality: {
    success_rate: number; // Across all loops for this agent type
    avg_iterations_to_success: number;
    common_failure_patterns: string[];
  };
}

// {{ORCHESTRATOR_NAME}} monitors all active loops
class LoopMonitor {
  activeLoops: Map<string, LoopMetrics>;

  checkHealth(): HealthReport {
    const tooManyIterations = Array.from(this.activeLoops.values())
      .filter(loop => loop.current_iteration > 4);

    const longRunning = Array.from(this.activeLoops.values())
      .filter(loop => this.getDuration(loop) > 20 * 60); // 20 min

    if (tooManyIterations.length > 0 || longRunning.length > 0) {
      return {
        status: 'warning',
        action: 'review_struggling_loops',
        loops: [...tooManyIterations, ...longRunning]
      };
    }

    return { status: 'healthy' };
  }
}
```

---

## 7. Rollout Strategy

### Phase 1: Pilot Agents (Week 1-2)

**Target Agents:**
- 🎨 Frontend Dev (testing feedback is mature)
- 🐲 Bowser (clear success/failure signals)

**Implementation:**
1. Add loop capability to these 2 agents
2. Run alongside existing one-shot mode (feature flag)
3. Collect metrics on iteration patterns
4. Validate safety mechanisms work

**Success Criteria:**
- Zero runaway loops
- >50% of tasks complete without escalation
- Average <3 iterations per successful task

### Phase 2: Expand to Build Agents (Week 3-4)

**Target Agents:**
- 📱 Mobile Dev
- 💻 macOS Dev
- 🏛️ Backend Dev

**Implementation:**
1. Integrate Xcode build feedback for mobile
2. Add compilation feedback for backend
3. Test with real capsule builds
4. Tune iteration limits per agent

### Phase 3: Full Rollout (Week 5-6)

**All Remaining Agents:**
- 🤖 Automator (n8n workflow validation)
- 🛒 Ecomm Bro (theme deployment checks)
- 🔍 Research Agent (quality validation)
- Others as applicable

**Implementation:**
1. Default all agents to loop mode
2. Remove feature flags
3. Document patterns learned
4. Update agent effectiveness tracking

### Phase 4: Optimization (Week 7+)

**Improvements:**
- Machine learning on fix patterns
- Cross-agent pattern sharing
- Predictive escalation (escalate early if pattern detected)
- Dynamic iteration limits based on task complexity

---

## 8. Benefits and Trade-offs

### Benefits

**Efficiency:**
- Reduce human intervention for fixable errors
- Faster development cycles (agent self-corrects vs. waiting for human)
- Better first-time success rates (agents learn patterns)

**Quality:**
- Catch errors earlier in the loop
- More thorough validation before completion
- Consistent application of quality standards

**Learning:**
- Agents build fix pattern libraries over time
- Share learnings across similar agents
- Improve success rates with experience

### Trade-offs

**Complexity:**
- More complex agent logic (execute + validate + evaluate)
- Harder to debug multi-iteration failures
- Need robust state management

**Resource Usage:**
- More compute (multiple iterations per task)
- More storage (logging all iteration attempts)
- Potential for wasted cycles on un-fixable errors

**Risk:**
- Possibility of runaway loops (mitigated by safety mechanisms)
- Agents might iterate on wrong solution approach
- Delayed escalation if agent keeps trying

### Mitigation Strategies

1. **Start conservative** - Low iteration limits, aggressive timeouts
2. **Monitor closely** - Real-time loop health dashboards
3. **Easy kill switch** - Ability to disable loop mode instantly
4. **Gradual rollout** - Phase in agents one at a time
5. **Human oversight** - {{ORCHESTRATOR_NAME}} reviews iteration patterns

---

## 9. Integration with Current Huxley

### Minimal Changes Required

**Agent Framework:**
- Add `executeWithLoop()` method to agent base class
- Agents can opt-in to loop mode (backward compatible)
- Falls back to one-shot if loop not supported

**{{ORCHESTRATOR_NAME}} Orchestration:**
- Add optional `loop_config` to delegation calls
- Monitor active loops in background
- Handle escalations with iteration context

**MCP/Tools:**
- No changes to existing MCP servers
- Tools already provide feedback (exit codes, logs, test results)
- Just need to capture and structure feedback

**State Management:**
- Use existing `registry/events.jsonl` for loop events
- Store iteration history in `registry/loops/`
- Extend `agent_effectiveness.db` with loop metrics

### Backward Compatibility

**Guarantee:**
- All existing one-shot agent calls continue working
- Loop mode is opt-in per task
- No breaking changes to agent interfaces

**Migration Path:**
```typescript
// Old (still works)
orchestrator.delegate({
  agent: "Frontend Dev",
  task: "Build header"
});

// New (loop-enabled)
orchestrator.delegate({
  agent: "Frontend Dev",
  task: "Build header",
  loop_config: { max_iterations: 5, ... }
});
```

---

## 10. Success Metrics

### Agent Performance

```yaml
metrics:

  effectiveness:
    - first_attempt_success_rate: "% tasks completed in 1 iteration"
    - avg_iterations_to_success: "Mean iterations for successful tasks"
    - escalation_rate: "% tasks that require escalation"
    - fix_success_rate: "% of fixable errors actually fixed"

  efficiency:
    - avg_time_per_iteration: "Seconds per iteration"
    - total_time_to_completion: "End-to-end task time"
    - wasted_iteration_percentage: "% iterations on unfixable errors"

  quality:
    - validation_coverage: "% feedback sources used"
    - false_positive_rate: "Tasks marked success but actually failed"
    - false_negative_rate: "Tasks escalated but were fixable"

  learning:
    - pattern_library_size: "# fix patterns learned"
    - pattern_reuse_rate: "% tasks using learned patterns"
    - improvement_over_time: "Success rate trend"
```

### System Health

```yaml
health_indicators:

  loop_health:
    - active_loops: "Current running loops"
    - avg_loop_duration: "Mean time in loop state"
    - longest_running_loop: "Max loop time"
    - loops_exceeding_threshold: "# loops > 80% of max iterations"

  resource_health:
    - cpu_usage: "% CPU across all loops"
    - memory_usage: "MB used by loops"
    - disk_usage: "MB of loop logs/artifacts"

  safety_health:
    - circuits_tripped: "# circuit breaker activations"
    - forced_escalations: "# safety-triggered escalations"
    - runaway_loop_incidents: "# loops terminated by safety"
```

---

## Conclusion

This agentic loop architecture transforms Huxley agents from one-shot executors to autonomous iterators that:

1. **Execute** tasks with full context
2. **Validate** results against clear criteria
3. **Evaluate** feedback intelligently
4. **Iterate** to fix issues autonomously
5. **Escalate** when appropriate with full context

**Key Enablers:**
- Structured feedback from validation sources
- Intelligent fix strategy generation
- Robust safety mechanisms
- Seamless integration with current Huxley

**Rollout:**
- Start with 2 pilot agents (Frontend Dev, Bowser)
- Expand to build agents (Mobile, Backend, macOS)
- Full rollout to all applicable agents
- Continuous optimization based on learned patterns

The system maintains {{ORCHESTRATOR_NAME}}'s orchestration role while giving agents autonomy to iterate to success, dramatically reducing human intervention for routine fixes.
