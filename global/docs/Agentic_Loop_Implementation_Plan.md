# Agentic Loop Implementation Plan

## Overview

Step-by-step guide to implement autonomous agent loops in Huxley, starting with pilot agents and expanding to full system coverage.

**Goal:** Transform agents from one-shot executors to autonomous iterators that self-correct until success.

---

## Phase 1: Foundation (Week 1)

### 1.1 Create Loop Infrastructure

**Create base loop framework:**

```bash
# Create directory structure
mkdir -p global/agent-loops/{core,agents,feedback,metrics}
mkdir -p registry/loops
```

**Files to create:**

1. **`global/agent-loops/core/loop_executor.py`**
   - Base loop execution logic
   - Iteration management
   - Safety mechanisms

2. **`global/agent-loops/core/feedback_collector.py`**
   - Feedback source integrations
   - Result validation
   - Success criteria evaluation

3. **`global/agent-loops/core/fix_strategy.py`**
   - Pattern matching for common errors
   - Fix generation logic
   - Escalation decision logic

4. **`global/agent-loops/core/loop_state.py`**
   - State tracking across iterations
   - Persistence to `registry/loops/`
   - Metrics collection

**Example implementation:**

```python
# global/agent-loops/core/loop_executor.py

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum
import time
import json

class LoopStatus(Enum):
    SUCCESS = "success"
    ITERATE = "iterate"
    ESCALATE = "escalate"

@dataclass
class SuccessCriteria:
    """Define what constitutes success for this task."""
    required: Dict[str, bool]  # Must all be True
    preferred: Dict[str, Any]  # Should be True, but can iterate
    custom: Dict[str, Any]     # Custom checks per agent

@dataclass
class LoopConfig:
    """Configuration for loop execution."""
    max_iterations: int = 5
    timeout_minutes: int = 30
    escalation_triggers: List[str] = None

@dataclass
class Feedback:
    """Structured feedback from validation sources."""
    builds: bool
    tests_pass: bool
    errors: List[str]
    warnings: List[str]
    metrics: Dict[str, Any]

class LoopExecutor:
    """Base class for agent loop execution."""

    def __init__(self, agent_name: str, config: LoopConfig):
        self.agent_name = agent_name
        self.config = config
        self.iteration = 0
        self.start_time = time.time()
        self.loop_id = f"{agent_name}-{int(time.time())}"

    def execute_loop(self, task: Dict[str, Any], criteria: SuccessCriteria):
        """Main loop execution."""

        while self.iteration < self.config.max_iterations:
            self.iteration += 1

            # Check timeout
            if self._is_timeout():
                return self._escalate("timeout_exceeded")

            print(f"[Loop {self.loop_id}] Iteration {self.iteration}/{self.config.max_iterations}")

            # EXECUTE
            execution_result = self._execute_task(task)

            # VALIDATE
            feedback = self._gather_feedback(execution_result)

            # EVALUATE
            evaluation = self._evaluate_feedback(feedback, criteria)

            # Save iteration state
            self._save_iteration_state(execution_result, feedback, evaluation)

            # DECIDE
            if evaluation['status'] == LoopStatus.SUCCESS:
                return self._complete_success(execution_result)

            elif evaluation['status'] == LoopStatus.ESCALATE:
                return self._escalate(evaluation['reason'])

            elif evaluation['status'] == LoopStatus.ITERATE:
                # Generate fix and loop
                fix_strategy = self._generate_fix(evaluation['failures'])
                self._apply_fix(fix_strategy)
                continue

        # Max iterations reached
        return self._escalate("max_iterations_reached")

    def _execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the primary task. Override in subclass."""
        raise NotImplementedError("Subclass must implement _execute_task")

    def _gather_feedback(self, execution_result: Dict[str, Any]) -> Feedback:
        """Gather feedback from validation sources. Override in subclass."""
        raise NotImplementedError("Subclass must implement _gather_feedback")

    def _evaluate_feedback(self, feedback: Feedback, criteria: SuccessCriteria) -> Dict[str, Any]:
        """Evaluate feedback against success criteria."""
        failures = []

        # Check required criteria
        for key, expected in criteria.required.items():
            actual = getattr(feedback, key, None)
            if actual != expected:
                failures.append({
                    'type': key,
                    'expected': expected,
                    'actual': actual,
                    'fixable': self._is_fixable(key, feedback)
                })

        # Determine status
        if len(failures) == 0:
            return {'status': LoopStatus.SUCCESS}

        all_fixable = all(f['fixable'] for f in failures)
        if all_fixable:
            return {
                'status': LoopStatus.ITERATE,
                'failures': failures
            }
        else:
            return {
                'status': LoopStatus.ESCALATE,
                'reason': 'non_fixable_errors',
                'failures': failures
            }

    def _is_fixable(self, failure_type: str, feedback: Feedback) -> bool:
        """Determine if this failure type is fixable. Override in subclass."""
        return True  # Default: optimistic

    def _generate_fix(self, failures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate fix strategy. Override in subclass."""
        raise NotImplementedError("Subclass must implement _generate_fix")

    def _apply_fix(self, fix_strategy: Dict[str, Any]):
        """Apply the fix strategy. Override in subclass."""
        raise NotImplementedError("Subclass must implement _apply_fix")

    def _is_timeout(self) -> bool:
        """Check if loop has exceeded timeout."""
        elapsed = time.time() - self.start_time
        return elapsed > (self.config.timeout_minutes * 60)

    def _complete_success(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful completion."""
        return {
            'status': 'success',
            'iterations': self.iteration,
            'loop_id': self.loop_id,
            'result': result
        }

    def _escalate(self, reason: str) -> Dict[str, Any]:
        """Handle escalation."""
        return {
            'status': 'escalated',
            'reason': reason,
            'iterations': self.iteration,
            'loop_id': self.loop_id
        }

    def _save_iteration_state(self, execution_result, feedback, evaluation):
        """Save iteration state to registry."""
        state = {
            'loop_id': self.loop_id,
            'agent': self.agent_name,
            'iteration': self.iteration,
            'timestamp': time.time(),
            'execution_result': execution_result,
            'feedback': self._feedback_to_dict(feedback),
            'evaluation': evaluation
        }

        # Append to loop log
        log_path = f"registry/loops/{self.loop_id}.jsonl"
        with open(log_path, 'a') as f:
            f.write(json.dumps(state) + '\n')

    def _feedback_to_dict(self, feedback: Feedback) -> Dict[str, Any]:
        """Convert feedback to dict."""
        return {
            'builds': feedback.builds,
            'tests_pass': feedback.tests_pass,
            'errors': feedback.errors,
            'warnings': feedback.warnings,
            'metrics': feedback.metrics
        }
```

### 1.2 Create Feedback Collectors

**Create feedback integrations:**

```python
# global/agent-loops/feedback/test_feedback.py

import subprocess
import json
from typing import Dict, Any

class TestFeedbackCollector:
    """Collect feedback from test execution."""

    def collect(self, test_command: str) -> Dict[str, Any]:
        """Run tests and parse results."""
        result = subprocess.run(
            test_command,
            shell=True,
            capture_output=True,
            text=True
        )

        return {
            'passed': result.returncode == 0,
            'exit_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'parsed': self._parse_test_output(result.stdout)
        }

    def _parse_test_output(self, output: str) -> Dict[str, Any]:
        """Parse test output for specific failures."""
        # TODO: Parse Jest/pytest/XCTest output
        return {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'failures': []
        }

# global/agent-loops/feedback/build_feedback.py

class BuildFeedbackCollector:
    """Collect feedback from build execution."""

    def collect(self, build_command: str) -> Dict[str, Any]:
        """Run build and parse results."""
        result = subprocess.run(
            build_command,
            shell=True,
            capture_output=True,
            text=True
        )

        return {
            'success': result.returncode == 0,
            'exit_code': result.returncode,
            'errors': self._extract_errors(result.stderr),
            'warnings': self._extract_warnings(result.stderr)
        }

    def _extract_errors(self, stderr: str) -> list:
        """Extract error messages from build output."""
        # TODO: Parse compiler errors
        return []

    def _extract_warnings(self, stderr: str) -> list:
        """Extract warnings from build output."""
        # TODO: Parse compiler warnings
        return []
```

### 1.3 Create Safety Mechanisms

```python
# global/agent-loops/core/safety.py

from dataclasses import dataclass
import time
from typing import Dict, List

@dataclass
class SafetyLimits:
    """Safety limits for loop execution."""
    max_iterations: int = 5
    timeout_minutes: int = 30
    max_memory_mb: int = 2048
    max_cpu_percent: int = 80

class SafetyMonitor:
    """Monitor loop safety and enforce limits."""

    def __init__(self, limits: SafetyLimits):
        self.limits = limits
        self.active_loops: Dict[str, Dict] = {}

    def register_loop(self, loop_id: str, agent: str):
        """Register a new active loop."""
        self.active_loops[loop_id] = {
            'agent': agent,
            'start_time': time.time(),
            'iteration': 0,
            'status': 'running'
        }

    def update_iteration(self, loop_id: str, iteration: int):
        """Update iteration count."""
        if loop_id in self.active_loops:
            self.active_loops[loop_id]['iteration'] = iteration

    def check_safety(self, loop_id: str) -> Dict[str, Any]:
        """Check if loop is within safety limits."""
        if loop_id not in self.active_loops:
            return {'safe': True}

        loop = self.active_loops[loop_id]

        # Check iteration limit
        if loop['iteration'] >= self.limits.max_iterations:
            return {
                'safe': False,
                'reason': 'max_iterations_exceeded',
                'action': 'escalate'
            }

        # Check timeout
        elapsed = time.time() - loop['start_time']
        if elapsed > (self.limits.timeout_minutes * 60):
            return {
                'safe': False,
                'reason': 'timeout_exceeded',
                'action': 'escalate'
            }

        return {'safe': True}

    def complete_loop(self, loop_id: str, status: str):
        """Mark loop as complete."""
        if loop_id in self.active_loops:
            self.active_loops[loop_id]['status'] = status
            del self.active_loops[loop_id]
```

---

## Phase 2: Pilot Implementation (Week 2)

### 2.1 Implement Frontend Dev Loop

**Create Frontend Dev loop agent:**

```python
# global/agent-loops/agents/frontend_dev_loop.py

from global.agent_loops.core.loop_executor import LoopExecutor, SuccessCriteria, LoopConfig, Feedback
from global.agent_loops.feedback.test_feedback import TestFeedbackCollector
from global.agent_loops.feedback.build_feedback import BuildFeedbackCollector
import subprocess

class FrontendDevLoop(LoopExecutor):
    """Frontend Dev agent with loop capability."""

    def __init__(self):
        config = LoopConfig(
            max_iterations=5,
            timeout_minutes=30
        )
        super().__init__("Frontend Dev", config)
        self.test_collector = TestFeedbackCollector()
        self.build_collector = BuildFeedbackCollector()

    def _execute_task(self, task: dict) -> dict:
        """Execute frontend development task."""
        # This would be Claude Code agent execution
        # For now, simulate with file operations

        return {
            'files_modified': task.get('files', []),
            'timestamp': time.time()
        }

    def _gather_feedback(self, execution_result: dict) -> Feedback:
        """Gather feedback from build and tests."""

        # Run build
        build_result = self.build_collector.collect("npm run build")

        # Run tests
        test_result = self.test_collector.collect("npm test")

        # Run linting
        lint_result = subprocess.run(
            "npm run lint",
            shell=True,
            capture_output=True
        )

        return Feedback(
            builds=build_result['success'],
            tests_pass=test_result['passed'],
            errors=build_result['errors'] + test_result.get('parsed', {}).get('failures', []),
            warnings=build_result['warnings'],
            metrics={
                'lint_exit_code': lint_result.returncode
            }
        )

    def _is_fixable(self, failure_type: str, feedback: Feedback) -> bool:
        """Determine if failure is fixable."""

        # Build failures are usually fixable
        if failure_type == 'builds':
            return self._can_fix_build_errors(feedback.errors)

        # Test failures are usually fixable
        if failure_type == 'tests_pass':
            return self._can_fix_test_errors(feedback.errors)

        return False

    def _can_fix_build_errors(self, errors: list) -> bool:
        """Check if build errors are fixable."""
        for error in errors:
            # Non-fixable patterns
            if 'Module not found' in error and 'node_modules' in error:
                return False  # Missing dependency
            if 'EACCES' in error or 'permission denied' in error:
                return False  # Permission issue

        return True  # Assume fixable

    def _can_fix_test_errors(self, errors: list) -> bool:
        """Check if test errors are fixable."""
        # Most test failures are fixable
        return True

    def _generate_fix(self, failures: list) -> dict:
        """Generate fix strategy for failures."""

        for failure in failures:
            failure_type = failure['type']

            if failure_type == 'builds':
                return self._generate_build_fix(failure)

            if failure_type == 'tests_pass':
                return self._generate_test_fix(failure)

        return {'action': 'escalate'}

    def _generate_build_fix(self, failure: dict) -> dict:
        """Generate fix for build failures."""
        # TODO: Pattern matching on error messages
        return {
            'action': 'fix_build_error',
            'target': 'analyze_error_and_fix'
        }

    def _generate_test_fix(self, failure: dict) -> dict:
        """Generate fix for test failures."""
        return {
            'action': 'fix_test_failure',
            'target': 'analyze_test_and_fix'
        }

    def _apply_fix(self, fix_strategy: dict):
        """Apply the fix strategy."""
        # This would delegate back to Claude Code agent
        # with specific fix instructions
        print(f"Applying fix: {fix_strategy['action']}")
```

**Test the implementation:**

```python
# test_frontend_loop.py

from global.agent_loops.agents.frontend_dev_loop import FrontendDevLoop
from global.agent_loops.core.loop_executor import SuccessCriteria

def test_frontend_loop():
    """Test frontend dev loop."""

    loop = FrontendDevLoop()

    task = {
        'files': ['src/components/Header.tsx'],
        'instructions': 'Build header component with tests'
    }

    criteria = SuccessCriteria(
        required={
            'builds': True,
            'tests_pass': True
        },
        preferred={
            'linting': True
        },
        custom={}
    )

    result = loop.execute_loop(task, criteria)

    print(f"Result: {result}")
    print(f"Status: {result['status']}")
    print(f"Iterations: {result['iterations']}")

if __name__ == '__main__':
    test_frontend_loop()
```

### 2.2 Implement Bowser Loop

**Create Bowser loop agent:**

```python
# global/agent-loops/agents/bowser_loop.py

from global.agent_loops.core.loop_executor import LoopExecutor, SuccessCriteria, LoopConfig, Feedback
import time

class BowserLoop(LoopExecutor):
    """Bowser agent with loop capability for browser automation."""

    def __init__(self):
        config = LoopConfig(
            max_iterations=3,  # Lower for browser automation
            timeout_minutes=15
        )
        super().__init__("Bowser", config)

    def _execute_task(self, task: dict) -> dict:
        """Execute browser automation task."""
        # Call Playwright automation
        # For now, simulate

        return {
            'page_loaded': True,
            'form_filled': True,
            'captcha_solved': False,  # Simulate failure
            'form_submitted': False,
            'timestamp': time.time()
        }

    def _gather_feedback(self, execution_result: dict) -> Feedback:
        """Gather feedback from browser automation."""

        errors = []
        if not execution_result['captcha_solved']:
            errors.append('CAPTCHA solving failed')
        if not execution_result['form_submitted']:
            errors.append('Form submission failed')

        return Feedback(
            builds=True,  # Not applicable
            tests_pass=execution_result['form_submitted'],
            errors=errors,
            warnings=[],
            metrics={
                'captcha_solved': execution_result['captcha_solved'],
                'page_loaded': execution_result['page_loaded']
            }
        )

    def _is_fixable(self, failure_type: str, feedback: Feedback) -> bool:
        """Determine if browser automation failure is fixable."""

        # CAPTCHA failures are retryable (up to max iterations)
        if 'CAPTCHA' in str(feedback.errors):
            return self.iteration < 3

        # Form submission failures might be fixable
        if 'Form submission' in str(feedback.errors):
            return True

        return False

    def _generate_fix(self, failures: list) -> dict:
        """Generate fix for browser automation failures."""

        for failure in failures:
            if 'CAPTCHA' in str(failure.get('actual', '')):
                return {
                    'action': 'retry_captcha',
                    'method': 'playwright-recaptcha'
                }

            if 'Form submission' in str(failure.get('actual', '')):
                return {
                    'action': 'retry_form_submission',
                    'check': 'field_validation'
                }

        return {'action': 'escalate'}

    def _apply_fix(self, fix_strategy: dict):
        """Apply browser automation fix."""
        print(f"Applying browser fix: {fix_strategy['action']}")
        time.sleep(2)  # Rate limiting
```

---

## Phase 3: Integration with {{ORCHESTRATOR_NAME}} (Week 3)

### 3.1 Update {{ORCHESTRATOR_NAME}} Delegation

**Modify {{ORCHESTRATOR_NAME}} to support loop-enabled delegation:**

```python
# global/{{ORCHESTRATOR_NAME_LOWER}}/loop_delegation.py

from global.agent_loops.core.loop_executor import SuccessCriteria, LoopConfig
from global.agent_loops.agents.frontend_dev_loop import FrontendDevLoop
from global.agent_loops.agents.bowser_loop import BowserLoop

class LoopDelegationManager:
    """Manage loop-enabled agent delegation."""

    def __init__(self):
        self.loop_agents = {
            'Frontend Dev': FrontendDevLoop,
            'Bowser': BowserLoop
        }

    def delegate_with_loop(
        self,
        agent_name: str,
        task: dict,
        criteria: SuccessCriteria,
        loop_config: LoopConfig = None
    ) -> dict:
        """Delegate task to loop-enabled agent."""

        if agent_name not in self.loop_agents:
            raise ValueError(f"Agent {agent_name} not loop-enabled")

        # Create agent instance
        AgentClass = self.loop_agents[agent_name]
        agent = AgentClass()

        # Override config if provided
        if loop_config:
            agent.config = loop_config

        # Execute with loop
        result = agent.execute_loop(task, criteria)

        # Handle result
        if result['status'] == 'success':
            print(f"✓ Task completed in {result['iterations']} iterations")
            return result

        elif result['status'] == 'escalated':
            print(f"⚠ Task escalated after {result['iterations']} iterations")
            print(f"  Reason: {result['reason']}")
            return result

        return result
```

**Update CLAUDE.md to enable loop delegation:**

Add to CLAUDE.md:

```markdown
## Agentic Loop Delegation

{{ORCHESTRATOR_NAME}} can delegate tasks with autonomous iteration enabled:

**Loop-Enabled Agents:**
- 🎨 Frontend Dev
- 🐲 Bowser

**Usage:**
When delegating to these agents, specify success criteria and loop configuration:

```python
# Example: Frontend Dev with loop
orchestrator.delegate_with_loop(
    agent_name="Frontend Dev",
    task={
        'files': ['src/components/Header.tsx'],
        'instructions': 'Build header component with tests'
    },
    criteria=SuccessCriteria(
        required={'builds': True, 'tests_pass': True},
        preferred={'linting': True}
    ),
    loop_config=LoopConfig(max_iterations=5)
)
```

The agent will iterate autonomously until:
- Success criteria met → Returns success
- Max iterations reached → Escalates to {{ORCHESTRATOR_NAME}}
- Non-fixable error → Escalates immediately
```

### 3.2 Add Loop Monitoring

**Create monitoring dashboard:**

```python
# global/agent-loops/monitoring/loop_monitor.py

import json
import os
from typing import Dict, List
from datetime import datetime

class LoopMonitor:
    """Monitor active and completed loops."""

    def __init__(self):
        self.loops_dir = "registry/loops"

    def get_active_loops(self) -> List[Dict]:
        """Get all active loops."""
        active = []

        for filename in os.listdir(self.loops_dir):
            if filename.endswith('.jsonl'):
                loop_id = filename.replace('.jsonl', '')
                status = self._get_loop_status(loop_id)

                if status['status'] == 'running':
                    active.append(status)

        return active

    def _get_loop_status(self, loop_id: str) -> Dict:
        """Get status of a specific loop."""
        filepath = f"{self.loops_dir}/{loop_id}.jsonl"

        iterations = []
        with open(filepath, 'r') as f:
            for line in f:
                iterations.append(json.loads(line))

        if len(iterations) == 0:
            return {'status': 'unknown'}

        latest = iterations[-1]

        return {
            'loop_id': loop_id,
            'agent': latest['agent'],
            'iteration': latest['iteration'],
            'status': 'running',  # Assume running if not marked complete
            'start_time': iterations[0]['timestamp'],
            'latest_iteration': latest['timestamp']
        }

    def get_loop_metrics(self) -> Dict:
        """Get aggregate loop metrics."""
        completed_loops = self._get_completed_loops()

        total = len(completed_loops)
        if total == 0:
            return {'total': 0}

        successes = len([l for l in completed_loops if l['final_status'] == 'success'])
        escalations = len([l for l in completed_loops if l['final_status'] == 'escalated'])

        avg_iterations = sum(l['iterations'] for l in completed_loops) / total

        return {
            'total_loops': total,
            'successes': successes,
            'success_rate': successes / total if total > 0 else 0,
            'escalations': escalations,
            'escalation_rate': escalations / total if total > 0 else 0,
            'avg_iterations': avg_iterations
        }

    def _get_completed_loops(self) -> List[Dict]:
        """Get all completed loops."""
        # TODO: Parse completed loop files
        return []
```

---

## Phase 4: Expand to Build Agents (Week 4)

### 4.1 Implement Mobile Dev Loop

```python
# global/agent-loops/agents/mobile_dev_loop.py

from global.agent_loops.core.loop_executor import LoopExecutor, Feedback
import subprocess

class MobileDevLoop(LoopExecutor):
    """Mobile Dev agent with iOS build loop."""

    def _gather_feedback(self, execution_result: dict) -> Feedback:
        """Gather feedback from Xcode build and simulator."""

        # Run Xcode build
        build_result = subprocess.run(
            "xcodebuild -scheme MyApp -sdk iphonesimulator build",
            shell=True,
            capture_output=True,
            text=True
        )

        # Launch simulator (if build succeeded)
        simulator_launched = False
        if build_result.returncode == 0:
            sim_result = subprocess.run(
                "xcrun simctl boot 'iPhone 15'",
                shell=True,
                capture_output=True
            )
            simulator_launched = sim_result.returncode == 0

        return Feedback(
            builds=build_result.returncode == 0,
            tests_pass=True,  # TODO: Run XCTest
            errors=self._parse_xcode_errors(build_result.stderr),
            warnings=[],
            metrics={
                'simulator_launched': simulator_launched
            }
        )

    def _parse_xcode_errors(self, stderr: str) -> list:
        """Parse Xcode compiler errors."""
        errors = []
        for line in stderr.split('\n'):
            if 'error:' in line.lower():
                errors.append(line.strip())
        return errors
```

### 4.2 Implement Backend Dev Loop

```python
# global/agent-loops/agents/backend_dev_loop.py

from global.agent_loops.core.loop_executor import LoopExecutor, Feedback
import subprocess

class BackendDevLoop(LoopExecutor):
    """Backend Dev agent with API testing loop."""

    def _gather_feedback(self, execution_result: dict) -> Feedback:
        """Gather feedback from backend tests."""

        # Run tests
        test_result = subprocess.run(
            "pytest tests/ -v",
            shell=True,
            capture_output=True,
            text=True
        )

        # Run type checking
        mypy_result = subprocess.run(
            "mypy src/",
            shell=True,
            capture_output=True
        )

        return Feedback(
            builds=True,  # Python doesn't compile
            tests_pass=test_result.returncode == 0,
            errors=self._parse_pytest_errors(test_result.stdout),
            warnings=[],
            metrics={
                'type_check': mypy_result.returncode == 0
            }
        )
```

---

## Phase 5: Metrics and Optimization (Week 5+)

### 5.1 Collect Loop Effectiveness Metrics

```python
# global/agent-loops/metrics/effectiveness.py

import sqlite3
from datetime import datetime
from typing import Dict

class LoopEffectivenessTracker:
    """Track agent loop effectiveness over time."""

    def __init__(self, db_path="registry/agent_loops.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loop_executions (
                loop_id TEXT PRIMARY KEY,
                agent_name TEXT,
                task_type TEXT,
                start_time REAL,
                end_time REAL,
                iterations INTEGER,
                final_status TEXT,
                escalation_reason TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loop_iterations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loop_id TEXT,
                iteration INTEGER,
                timestamp REAL,
                feedback_json TEXT,
                fix_strategy_json TEXT,
                FOREIGN KEY (loop_id) REFERENCES loop_executions(loop_id)
            )
        """)

        conn.commit()
        conn.close()

    def record_loop(self, loop_data: Dict):
        """Record completed loop execution."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO loop_executions
            (loop_id, agent_name, task_type, start_time, end_time, iterations, final_status, escalation_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            loop_data['loop_id'],
            loop_data['agent_name'],
            loop_data['task_type'],
            loop_data['start_time'],
            loop_data['end_time'],
            loop_data['iterations'],
            loop_data['final_status'],
            loop_data.get('escalation_reason')
        ))

        conn.commit()
        conn.close()

    def get_agent_metrics(self, agent_name: str) -> Dict:
        """Get effectiveness metrics for an agent."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                AVG(iterations) as avg_iterations,
                SUM(CASE WHEN final_status = 'success' THEN 1 ELSE 0 END) as successes,
                SUM(CASE WHEN final_status = 'escalated' THEN 1 ELSE 0 END) as escalations
            FROM loop_executions
            WHERE agent_name = ?
        """, (agent_name,))

        result = cursor.fetchone()
        conn.close()

        total, avg_iter, successes, escalations = result

        return {
            'agent': agent_name,
            'total_loops': total,
            'avg_iterations': avg_iter or 0,
            'success_rate': (successes / total) if total > 0 else 0,
            'escalation_rate': (escalations / total) if total > 0 else 0
        }
```

### 5.2 Learn from Patterns

```python
# global/agent-loops/learning/pattern_learner.py

from collections import defaultdict
from typing import Dict, List
import json

class PatternLearner:
    """Learn fix patterns from successful iterations."""

    def __init__(self):
        self.patterns = defaultdict(list)
        self.pattern_file = "registry/fix_patterns.json"
        self._load_patterns()

    def _load_patterns(self):
        """Load learned patterns from file."""
        try:
            with open(self.pattern_file, 'r') as f:
                self.patterns = json.load(f)
        except FileNotFoundError:
            self.patterns = {}

    def learn_pattern(self, error_type: str, fix_strategy: Dict, success: bool):
        """Learn from a fix attempt."""
        if success:
            pattern = {
                'error_type': error_type,
                'fix': fix_strategy,
                'success_count': 1
            }

            # Check if pattern exists
            existing = self._find_existing_pattern(error_type, fix_strategy)
            if existing:
                existing['success_count'] += 1
            else:
                self.patterns[error_type].append(pattern)

            self._save_patterns()

    def get_suggested_fix(self, error_type: str) -> Dict:
        """Get suggested fix for error type."""
        if error_type in self.patterns:
            # Return most successful pattern
            patterns = self.patterns[error_type]
            best = max(patterns, key=lambda p: p['success_count'])
            return best['fix']

        return None

    def _find_existing_pattern(self, error_type: str, fix_strategy: Dict):
        """Find existing pattern that matches."""
        if error_type not in self.patterns:
            return None

        for pattern in self.patterns[error_type]:
            if pattern['fix'] == fix_strategy:
                return pattern

        return None

    def _save_patterns(self):
        """Save patterns to file."""
        with open(self.pattern_file, 'w') as f:
            json.dump(self.patterns, f, indent=2)
```

---

## Testing Strategy

### Unit Tests

```bash
# Test core loop executor
pytest global/agent-loops/tests/test_loop_executor.py

# Test feedback collectors
pytest global/agent-loops/tests/test_feedback_collectors.py

# Test safety mechanisms
pytest global/agent-loops/tests/test_safety.py
```

### Integration Tests

```bash
# Test Frontend Dev loop end-to-end
pytest global/agent-loops/tests/integration/test_frontend_loop.py

# Test Bowser loop end-to-end
pytest global/agent-loops/tests/integration/test_bowser_loop.py
```

### Manual Testing

1. **Frontend Dev Loop:**
   - Create intentional type error
   - Run loop, verify it fixes error
   - Verify iterations logged

2. **Bowser Loop:**
   - Test CAPTCHA retry logic
   - Verify escalation after max attempts
   - Check state persistence

---

## Success Criteria

### Phase 1 Complete When:
- [ ] Base loop framework created
- [ ] Feedback collectors implemented
- [ ] Safety mechanisms working
- [ ] Unit tests passing

### Phase 2 Complete When:
- [ ] Frontend Dev loop working
- [ ] Bowser loop working
- [ ] Both agents fix >50% of simple errors autonomously
- [ ] Integration tests passing

### Phase 3 Complete When:
- [ ] {{ORCHESTRATOR_NAME}} can delegate to loop-enabled agents
- [ ] Loop monitoring dashboard showing metrics
- [ ] Documentation updated in CLAUDE.md

### Phase 4 Complete When:
- [ ] Mobile Dev, Backend Dev loops implemented
- [ ] All build agents using loop mode
- [ ] Success rate >60% across all agents

### Phase 5 Complete When:
- [ ] Pattern learning system operational
- [ ] Metrics collection automated
- [ ] Optimization showing improved success rates

---

## Next Steps

1. **Start Phase 1:**
   ```bash
   mkdir -p global/agent-loops/{core,agents,feedback,metrics}
   mkdir -p registry/loops
   ```

2. **Create base framework files** (see Phase 1.1)

3. **Test with simple cases** before full agent integration

4. **Iterate on feedback mechanisms** based on real usage

5. **Document learnings** as patterns emerge
