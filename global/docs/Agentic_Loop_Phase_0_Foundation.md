# Agentic Loop Phase 0: Foundation Implementation
## Design notes

**Philosophy:** Invest in sophisticated foundation upfront to avoid rewrites.

---

## Overview

Phase 0 builds the intelligent infrastructure before piloting agents:

1. **Normalized Feedback Schema** - Structured, quality-scored feedback from all tools
2. **Remediation Skills System** - Semantic retrieval of fix strategies using embeddings
3. **Adaptive Safety Mechanisms** - Dynamic limits with stuck detection
4. **Failure Trace Capture** - Learn from both successes and failures
5. **Escalation Heuristics** - Smart decision logic for when to escalate


---

## 1. Normalized Feedback Schema

### 1.1 Core Schema Definition

```python
# global/agent-loops/core/feedback_schema.py

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum
import time

class FeedbackCategory(Enum):
    """Standardized failure categories."""
    BUILD_ERROR = "build_error"
    TEST_FAILURE = "test_failure"
    LINT_WARNING = "lint_warning"
    TYPE_ERROR = "type_error"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    MISSING_DEPENDENCY = "missing_dependency"
    NETWORK_ERROR = "network_error"
    CAPTCHA_FAILURE = "captcha_failure"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN = "unknown"

class DeterministicBlocker(Enum):
    """Failures that require immediate escalation."""
    PERMISSION_DENIED = "permission_denied"
    MISSING_EXTERNAL_DEP = "missing_external_dependency"
    QUOTA_EXCEEDED = "quota_exceeded"
    SERVICE_DOWN = "service_down"
    SECURITY_VIOLATION = "security_violation"

@dataclass
class SalientFragment:
    """Key piece of error/warning information."""
    line_number: Optional[int]
    file_path: Optional[str]
    message: str
    context: str  # Surrounding lines if relevant
    severity: str  # error, warning, info

@dataclass
class NormalizedFeedback:
    """Structured feedback from validation tools."""

    # Core status
    success: bool
    exit_code: int

    # Categorization
    category: FeedbackCategory
    is_deterministic_blocker: bool
    blocker_type: Optional[DeterministicBlocker]

    # Structured error info
    salient_fragments: List[SalientFragment]  # Only key errors, not full logs
    suggested_scope: Optional[str]  # Which file/function to focus on

    # Quality metrics
    signal_quality_score: float  # 0.0-1.0, how actionable is this feedback
    feedback_source: str  # pytest, eslint, xcodebuild, etc.

    # Raw data (fallback)
    stdout: str
    stderr: str

    # Metadata
    timestamp: float
    tool_version: Optional[str]

    # Summarization
    auto_summary: str  # LLM-generated summary if logs are sprawling

    def is_actionable(self) -> bool:
        """Check if feedback is good enough to act on."""
        return self.signal_quality_score > 0.5

    def is_noisy(self) -> bool:
        """Check if feedback is too noisy to be useful."""
        return self.signal_quality_score < 0.3
```

### 1.2 Tool-Specific Normalizers

```python
# global/agent-loops/feedback/normalizers/base.py

from abc import ABC, abstractmethod
from global.agent_loops.core.feedback_schema import NormalizedFeedback

class FeedbackNormalizer(ABC):
    """Base class for tool-specific feedback normalizers."""

    @abstractmethod
    def normalize(self, raw_output: Dict[str, Any]) -> NormalizedFeedback:
        """Convert tool output to normalized feedback."""
        pass

    @abstractmethod
    def compute_signal_quality(self, feedback: NormalizedFeedback) -> float:
        """Compute quality score for this feedback."""
        pass

# global/agent-loops/feedback/normalizers/pytest_normalizer.py

import re
from typing import List
from global.agent_loops.feedback.normalizers.base import FeedbackNormalizer
from global.agent_loops.core.feedback_schema import (
    NormalizedFeedback, FeedbackCategory, SalientFragment
)

class PytestNormalizer(FeedbackNormalizer):
    """Normalize pytest output to structured feedback."""

    def normalize(self, raw_output: Dict[str, Any]) -> NormalizedFeedback:
        """Parse pytest output."""

        exit_code = raw_output['exit_code']
        stdout = raw_output['stdout']
        stderr = raw_output['stderr']

        # Parse test results
        failures = self._parse_failures(stdout)
        salient_fragments = self._extract_salient_fragments(failures)

        # Determine category
        category = FeedbackCategory.TEST_FAILURE if len(failures) > 0 else FeedbackCategory.UNKNOWN

        # Check for deterministic blockers
        is_blocker, blocker_type = self._check_deterministic_blockers(stderr)

        # Compute quality score
        signal_quality = self._compute_quality(salient_fragments, stdout)

        # Generate summary if needed
        auto_summary = self._generate_summary(failures) if len(stdout) > 2000 else ""

        return NormalizedFeedback(
            success=exit_code == 0,
            exit_code=exit_code,
            category=category,
            is_deterministic_blocker=is_blocker,
            blocker_type=blocker_type,
            salient_fragments=salient_fragments,
            suggested_scope=self._suggest_scope(failures),
            signal_quality_score=signal_quality,
            feedback_source="pytest",
            stdout=stdout,
            stderr=stderr,
            timestamp=time.time(),
            tool_version=self._get_pytest_version(stdout),
            auto_summary=auto_summary
        )

    def _parse_failures(self, stdout: str) -> List[Dict[str, str]]:
        """Extract failure information from pytest output."""
        failures = []

        # Regex patterns for pytest output
        failure_pattern = r'FAILED (.*?) - (.*?)(?=\n|$)'

        for match in re.finditer(failure_pattern, stdout, re.MULTILINE):
            test_name = match.group(1)
            error_msg = match.group(2)

            failures.append({
                'test': test_name,
                'error': error_msg,
                'file': self._extract_file_from_test_name(test_name)
            })

        return failures

    def _extract_salient_fragments(self, failures: List[Dict]) -> List[SalientFragment]:
        """Convert failures to salient fragments."""
        fragments = []

        for failure in failures:
            fragments.append(SalientFragment(
                line_number=None,  # pytest doesn't always provide
                file_path=failure.get('file'),
                message=failure['error'],
                context=failure['test'],
                severity='error'
            ))

        return fragments

    def _check_deterministic_blockers(self, stderr: str) -> tuple:
        """Check for blockers that require immediate escalation."""

        if 'Permission denied' in stderr or 'EACCES' in stderr:
            return True, DeterministicBlocker.PERMISSION_DENIED

        if 'ModuleNotFoundError' in stderr and 'site-packages' in stderr:
            return True, DeterministicBlocker.MISSING_EXTERNAL_DEP

        return False, None

    def _compute_quality(self, fragments: List[SalientFragment], full_output: str) -> float:
        """Compute signal quality score."""

        if len(fragments) == 0:
            return 0.1  # No useful info

        # High quality if we have specific error messages
        if all(len(f.message) > 10 for f in fragments):
            score = 0.9
        else:
            score = 0.5

        # Reduce score if output is extremely long (noisy)
        if len(full_output) > 10000:
            score *= 0.7

        return min(1.0, max(0.0, score))

    def _suggest_scope(self, failures: List[Dict]) -> Optional[str]:
        """Suggest which file/function to focus on."""
        if len(failures) == 0:
            return None

        # If all failures in same file, suggest that file
        files = set(f.get('file') for f in failures if f.get('file'))
        if len(files) == 1:
            return list(files)[0]

        return None

    def _generate_summary(self, failures: List[Dict]) -> str:
        """Generate LLM summary for sprawling output."""
        # TODO: Call LLM to summarize
        return f"{len(failures)} test failures: " + ", ".join(f['test'] for f in failures[:3])

    def _extract_file_from_test_name(self, test_name: str) -> Optional[str]:
        """Extract file path from test name."""
        parts = test_name.split('::')
        if len(parts) > 0:
            return parts[0]
        return None

    def _get_pytest_version(self, stdout: str) -> Optional[str]:
        """Extract pytest version from output."""
        match = re.search(r'pytest (\d+\.\d+\.\d+)', stdout)
        return match.group(1) if match else None

# Similar normalizers for:
# - ESLintNormalizer
# - TypeScriptNormalizer
# - XcodeBuildNormalizer
# - PlaywrightNormalizer
```

### 1.3 Feedback Registry

```python
# global/agent-loops/feedback/feedback_registry.py

from typing import Dict, Type
from global.agent_loops.feedback.normalizers.base import FeedbackNormalizer
from global.agent_loops.feedback.normalizers.pytest_normalizer import PytestNormalizer
# ... other normalizers

class FeedbackRegistry:
    """Central registry of feedback normalizers."""

    def __init__(self):
        self.normalizers: Dict[str, FeedbackNormalizer] = {
            'pytest': PytestNormalizer(),
            'eslint': ESLintNormalizer(),
            'tsc': TypeScriptNormalizer(),
            'xcodebuild': XcodeBuildNormalizer(),
            'playwright': PlaywrightNormalizer(),
        }

    def get_normalizer(self, tool: str) -> FeedbackNormalizer:
        """Get normalizer for a specific tool."""
        if tool not in self.normalizers:
            raise ValueError(f"No normalizer registered for tool: {tool}")
        return self.normalizers[tool]

    def normalize(self, tool: str, raw_output: Dict) -> NormalizedFeedback:
        """Normalize output from any tool."""
        normalizer = self.get_normalizer(tool)
        return normalizer.normalize(raw_output)
```

---

## 2. Remediation Skills System

### 2.1 Skill Definition

```python
# global/agent-loops/remediation/skill.py

from dataclasses import dataclass
from typing import Callable, Dict, Any, List, Optional
import numpy as np

@dataclass
class RemediationSkill:
    """Reusable fix strategy indexed by failure signature."""

    skill_id: str
    name: str
    description: str

    # Failure signature
    failure_category: str  # From FeedbackCategory
    error_pattern_embedding: np.ndarray  # Semantic embedding of error pattern

    # Context matching
    tools: List[str]  # Which tools this applies to (pytest, eslint, etc.)
    stacks: List[str]  # Which tech stacks (python, typescript, swift, etc.)
    components: List[str]  # Which components (frontend, backend, etc.)

    # Fix strategy
    fix_function: Callable[[Dict[str, Any]], Dict[str, Any]]
    fix_description: str  # Human-readable explanation

    # Metadata
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0
    created_at: float = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate for this skill."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    @property
    def confidence(self) -> float:
        """Confidence score based on usage history."""
        # More uses = higher confidence
        total_uses = self.success_count + self.failure_count
        base_confidence = min(1.0, total_uses / 10.0)

        # Weight by success rate
        return base_confidence * self.success_rate

# Example skills:

def fix_missing_import(context: Dict[str, Any]) -> Dict[str, Any]:
    """Fix missing import errors."""
    missing_module = context['missing_module']
    file_path = context['file_path']

    return {
        'action': 'add_import',
        'module': missing_module,
        'file': file_path,
        'location': 'top_of_file'
    }

def fix_null_check(context: Dict[str, Any]) -> Dict[str, Any]:
    """Add null/undefined checks."""
    variable = context['variable']
    line_number = context['line_number']

    return {
        'action': 'add_null_check',
        'variable': variable,
        'line': line_number,
        'pattern': 'guard_clause'
    }

def install_dependency(context: Dict[str, Any]) -> Dict[str, Any]:
    """Install missing npm/pip dependency."""
    package = context['package']
    package_manager = context['package_manager']

    return {
        'action': 'install_package',
        'package': package,
        'manager': package_manager
    }
```

### 2.2 Skill Library with Embeddings

```python
# global/agent-loops/remediation/skill_library.py

from typing import List, Dict, Any, Optional
import numpy as np
import json
from pathlib import Path
import openai

class SkillLibrary:
    """Library of remediation skills with semantic retrieval."""

    def __init__(self, embedding_model: str = "text-embedding-3-small"):
        self.skills: List[RemediationSkill] = []
        self.embedding_model = embedding_model
        self.skills_file = Path("registry/remediation_skills.json")

        # Load existing skills
        self._load_skills()

    def add_skill(self, skill: RemediationSkill):
        """Add a skill to the library."""
        self.skills.append(skill)
        self._save_skills()

    def retrieve_skills(
        self,
        error_embedding: np.ndarray,
        feedback: NormalizedFeedback,
        top_k: int = 5
    ) -> List[RemediationSkill]:
        """Retrieve most relevant skills using semantic similarity."""

        # Filter by metadata first
        candidates = self._filter_by_metadata(feedback)

        if len(candidates) == 0:
            return []

        # Compute similarity scores
        scored_skills = []
        for skill in candidates:
            # Cosine similarity
            similarity = np.dot(error_embedding, skill.error_pattern_embedding) / (
                np.linalg.norm(error_embedding) * np.linalg.norm(skill.error_pattern_embedding)
            )

            # Boost by confidence
            score = similarity * (0.7 + 0.3 * skill.confidence)

            # Exact category match boost
            if skill.failure_category == feedback.category.value:
                score *= 1.2

            # Freshness decay (prefer recently successful skills)
            recency_factor = self._compute_recency_factor(skill.last_used)
            score *= recency_factor

            scored_skills.append((score, skill))

        # Sort by score and return top K
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        return [skill for _, skill in scored_skills[:top_k]]

    def _filter_by_metadata(self, feedback: NormalizedFeedback) -> List[RemediationSkill]:
        """Filter skills by tool, stack, component metadata."""
        candidates = []

        for skill in self.skills:
            # Match by tool
            if feedback.feedback_source in skill.tools:
                candidates.append(skill)
                continue

            # Match by failure category
            if skill.failure_category == feedback.category.value:
                candidates.append(skill)

        return candidates

    def _compute_recency_factor(self, last_used: float) -> float:
        """Compute recency factor with decay."""
        import time

        if last_used == 0:
            return 0.8  # New skill, slightly penalized

        days_since_use = (time.time() - last_used) / (60 * 60 * 24)

        # Decay over 90 days
        decay = np.exp(-days_since_use / 90.0)
        return 0.5 + 0.5 * decay  # Range: 0.5 to 1.0

    def record_usage(self, skill_id: str, success: bool):
        """Record skill usage outcome."""
        skill = self._find_skill(skill_id)
        if skill:
            if success:
                skill.success_count += 1
            else:
                skill.failure_count += 1
            skill.last_used = time.time()
            self._save_skills()

    def _find_skill(self, skill_id: str) -> Optional[RemediationSkill]:
        """Find skill by ID."""
        for skill in self.skills:
            if skill.skill_id == skill_id:
                return skill
        return None

    def _load_skills(self):
        """Load skills from disk."""
        if not self.skills_file.exists():
            return

        with open(self.skills_file, 'r') as f:
            data = json.load(f)

        # Reconstruct skills from JSON
        # TODO: Deserialize embeddings and functions

    def _save_skills(self):
        """Save skills to disk."""
        # TODO: Serialize skills to JSON
        pass

    def embed_error(self, error_text: str) -> np.ndarray:
        """Generate embedding for error text."""
        response = openai.embeddings.create(
            model=self.embedding_model,
            input=error_text
        )
        return np.array(response.data[0].embedding)
```

### 2.3 Skill Composition & LLM Selection

```python
# global/agent-loops/remediation/skill_composer.py

from typing import List, Dict, Any
from global.agent_loops.remediation.skill import RemediationSkill
from global.agent_loops.core.feedback_schema import NormalizedFeedback

class SkillComposer:
    """Let LLM choose and compose multiple skills."""

    def __init__(self, skill_library: SkillLibrary):
        self.library = skill_library

    def select_fix_strategy(
        self,
        feedback: NormalizedFeedback,
        candidate_skills: List[RemediationSkill]
    ) -> Dict[str, Any]:
        """Use LLM to select and compose skills."""

        if len(candidate_skills) == 0:
            # No skills found, fall back to direct reasoning
            return self._direct_reasoning_fallback(feedback)

        # Build prompt for LLM
        prompt = self._build_skill_selection_prompt(feedback, candidate_skills)

        # Call LLM to choose/compose
        response = self._call_llm(prompt)

        # Parse LLM response into fix strategy
        fix_strategy = self._parse_fix_strategy(response)

        # Capture this attempt for later curation
        self._capture_attempt(feedback, candidate_skills, fix_strategy)

        return fix_strategy

    def _build_skill_selection_prompt(
        self,
        feedback: NormalizedFeedback,
        skills: List[RemediationSkill]
    ) -> str:
        """Build prompt for LLM skill selection."""

        prompt = f"""You are a fix strategy composer. Given an error and available remediation skills, select the best skill(s) to fix the error.

**Error Information:**
Category: {feedback.category.value}
Source: {feedback.feedback_source}
Salient errors:
"""
        for fragment in feedback.salient_fragments[:3]:
            prompt += f"  - {fragment.message}\n"

        prompt += f"\n**Available Skills ({len(skills)}):**\n"

        for i, skill in enumerate(skills, 1):
            prompt += f"{i}. {skill.name} (confidence: {skill.confidence:.2f})\n"
            prompt += f"   Description: {skill.description}\n"
            prompt += f"   Fix: {skill.fix_description}\n"
            prompt += f"   Success rate: {skill.success_rate:.1%}\n\n"

        prompt += """
**Instructions:**
1. Select the single best skill OR compose multiple skills if needed
2. Explain why you chose this approach
3. Provide any additional context needed for the fix

**Output format:**
```json
{
  "selected_skills": ["skill_id_1", "skill_id_2"],
  "reasoning": "Why this approach will work...",
  "composition_strategy": "sequential|parallel",
  "additional_context": {}
}
```
"""
        return prompt

    def _direct_reasoning_fallback(self, feedback: NormalizedFeedback) -> Dict[str, Any]:
        """Fall back to direct LLM reasoning when no skills match."""

        prompt = f"""No pre-existing remediation skill matches this error. Analyze and propose a fix.

**Error:**
{feedback.salient_fragments[0].message if feedback.salient_fragments else 'Unknown error'}

**Context:**
{feedback.auto_summary or feedback.stdout[:500]}

Propose a fix strategy in JSON format:
```json
{{
  "action": "action_type",
  "target": "what to fix",
  "approach": "how to fix it",
  "reasoning": "why this should work"
}}
```
"""

        response = self._call_llm(prompt)
        fix_strategy = self._parse_fix_strategy(response)

        # CAPTURE this for later curation into a skill
        self._capture_new_pattern(feedback, fix_strategy)

        return fix_strategy

    def _call_llm(self, prompt: str) -> str:
        """Call LLM for reasoning."""
        # TODO: Implement actual LLM call
        return "{}"

    def _parse_fix_strategy(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into fix strategy."""
        # TODO: Implement JSON parsing
        return {}

    def _capture_attempt(
        self,
        feedback: NormalizedFeedback,
        skills: List[RemediationSkill],
        strategy: Dict[str, Any]
    ):
        """Capture this attempt for learning."""
        # TODO: Log to registry/remediation_attempts.jsonl
        pass

    def _capture_new_pattern(
        self,
        feedback: NormalizedFeedback,
        strategy: Dict[str, Any]
    ):
        """Capture new pattern for potential skill creation."""
        # TODO: Log to registry/new_patterns.jsonl
        # Human/automated curation can convert these to skills
        pass
```

---

## 3. Adaptive Safety Mechanisms

### 3.1 Dynamic Iteration Limits

```python
# global/agent-loops/safety/adaptive_limits.py

from dataclasses import dataclass
from typing import List, Optional
import time

@dataclass
class IterationHistory:
    """Track history of iteration attempts."""
    iteration: int
    timestamp: float
    feedback_hash: str  # Hash of feedback for duplicate detection
    made_progress: bool
    confidence: float

class AdaptiveLimits:
    """Dynamically adjust iteration limits based on progress."""

    def __init__(self, base_max_iterations: int = 5):
        self.base_max = base_max_iterations
        self.history: List[IterationHistory] = []

    def get_current_limit(self) -> int:
        """Get current iteration limit based on progress."""

        if len(self.history) == 0:
            return self.base_max

        # Check for progress in recent iterations
        recent = self.history[-3:]  # Last 3 iterations

        progress_count = sum(1 for h in recent if h.made_progress)

        # If making progress, extend limit
        if progress_count >= 2:
            return self.base_max + 2

        # If no progress, shrink limit
        if progress_count == 0:
            return max(2, self.base_max - 2)

        return self.base_max

    def record_iteration(
        self,
        iteration: int,
        feedback_hash: str,
        made_progress: bool,
        confidence: float
    ):
        """Record iteration outcome."""
        self.history.append(IterationHistory(
            iteration=iteration,
            timestamp=time.time(),
            feedback_hash=feedback_hash,
            made_progress=made_progress,
            confidence=confidence
        ))

    def should_extend_for_build(self, build_time_seconds: float) -> bool:
        """Check if we should extend timeout for long build."""
        # If build takes > 5 minutes, extend timeout
        return build_time_seconds > 300
```

### 3.2 Stuck Detection

```python
# global/agent-loops/safety/stuck_detector.py

from typing import List, Optional
import hashlib

class StuckDetector:
    """Detect when loop is stuck with no progress."""

    def __init__(self):
        self.feedback_hashes: List[str] = []

    def check_stuck(self, feedback: NormalizedFeedback) -> tuple[bool, Optional[str]]:
        """Check if we're stuck in a loop."""

        # Hash the feedback
        feedback_hash = self._hash_feedback(feedback)

        # Check for repeated identical feedback
        if feedback_hash in self.feedback_hashes:
            occurrences = self.feedback_hashes.count(feedback_hash)

            if occurrences >= 2:
                return True, "repeated_identical_failures"

        self.feedback_hashes.append(feedback_hash)

        # Check for no progress indicators
        if self._check_no_progress_indicators(feedback):
            return True, "no_progress_detected"

        return False, None

    def _hash_feedback(self, feedback: NormalizedFeedback) -> str:
        """Create hash of feedback for duplicate detection."""
        # Hash based on category + salient fragments
        content = feedback.category.value + "|"
        content += "|".join(f.message for f in feedback.salient_fragments)

        return hashlib.sha256(content.encode()).hexdigest()

    def _check_no_progress_indicators(self, feedback: NormalizedFeedback) -> bool:
        """Check if feedback indicates no progress."""

        # Same error messages as before
        # Same files failing
        # Same test failures
        # TODO: Implement deeper analysis

        return False
```

### 3.3 Resource Guards

```python
# global/agent-loops/safety/resource_guards.py

import psutil
import time
from dataclasses import dataclass

@dataclass
class ResourceLimits:
    """Resource limits for loop execution."""
    max_memory_mb: int = 2048
    max_cpu_percent: int = 80
    per_validation_timeout_seconds: int = 300  # 5 minutes per validation step

class ResourceGuard:
    """Monitor and enforce resource limits."""

    def __init__(self, limits: ResourceLimits):
        self.limits = limits

    def check_resources(self) -> tuple[bool, Optional[str]]:
        """Check if resources are within limits."""

        # Check memory
        memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        if memory > self.limits.max_memory_mb:
            return False, f"memory_exceeded_{memory:.0f}MB"

        # Check CPU (average over last 1 second)
        cpu = psutil.Process().cpu_percent(interval=1.0)
        if cpu > self.limits.max_cpu_percent:
            return False, f"cpu_exceeded_{cpu:.0f}%"

        return True, None

    def with_timeout(self, func, timeout_seconds: int = None):
        """Execute function with timeout."""
        import signal

        timeout = timeout_seconds or self.limits.per_validation_timeout_seconds

        def timeout_handler(signum, frame):
            raise TimeoutError(f"Validation step exceeded {timeout}s")

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)

        try:
            result = func()
        finally:
            signal.alarm(0)

        return result
```

### 3.4 State Isolation

```python
# global/agent-loops/safety/state_isolation.py

import os
import tempfile
import shutil
from contextlib import contextmanager

class StateIsolation:
    """Prevent state leakage between loop executions."""

    def __init__(self, loop_id: str):
        self.loop_id = loop_id
        self.temp_dir = None

    @contextmanager
    def isolated_execution(self):
        """Execute with isolated temp directory."""

        # Create isolated temp directory
        self.temp_dir = tempfile.mkdtemp(prefix=f"loop_{self.loop_id}_")

        # Set environment variables for isolation
        old_temp = os.environ.get('TMPDIR')
        os.environ['TMPDIR'] = self.temp_dir

        try:
            yield self.temp_dir
        finally:
            # Cleanup
            os.environ['TMPDIR'] = old_temp or '/tmp'

            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)

    def prevent_cache_contamination(self):
        """Prevent build cache contamination between loops."""
        # Clear build caches specific to this loop
        cache_dirs = [
            '.pytest_cache',
            'node_modules/.cache',
            'build/intermediates',
            'DerivedData'
        ]

        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                # Add loop-specific marker
                marker_file = os.path.join(cache_dir, f'.loop_{self.loop_id}')
                with open(marker_file, 'w') as f:
                    f.write(str(time.time()))
```

---

## 4. Failure Trace Capture

### 4.1 Trace Schema

```python
# global/agent-loops/learning/trace_schema.py

from dataclasses import dataclass
from typing import List, Dict, Any
from enum import Enum

class TraceType(Enum):
    SUCCESS = "success"
    FAILURE = "failure"

@dataclass
class RemediationTrace:
    """Capture both successful and failed remediation attempts."""

    trace_id: str
    trace_type: TraceType

    # Initial state
    initial_feedback: NormalizedFeedback
    error_embedding: np.ndarray

    # Attempted fix
    selected_skills: List[str]
    fix_strategy: Dict[str, Any]
    reasoning: str

    # Outcome
    final_feedback: NormalizedFeedback
    iterations_taken: int
    success: bool

    # Why it failed (if failure)
    failure_reason: Optional[str]
    stuck_pattern: Optional[str]

    # Metadata
    agent: str
    timestamp: float
    capsule: str

    # Context
    code_context: Dict[str, Any]  # File paths, stack trace, etc.
```

### 4.2 Trace Collector

```python
# global/agent-loops/learning/trace_collector.py

from global.agent_loops.learning.trace_schema import RemediationTrace, TraceType
import json

class TraceCollector:
    """Collect success and failure traces for learning."""

    def __init__(self):
        self.success_traces_file = "registry/traces/success_traces.jsonl"
        self.failure_traces_file = "registry/traces/failure_traces.jsonl"

    def record_trace(self, trace: RemediationTrace):
        """Record a remediation trace."""

        if trace.trace_type == TraceType.SUCCESS:
            self._append_to_file(self.success_traces_file, trace)
        else:
            self._append_to_file(self.failure_traces_file, trace)

    def _append_to_file(self, filepath: str, trace: RemediationTrace):
        """Append trace to JSONL file."""
        with open(filepath, 'a') as f:
            f.write(json.dumps(self._serialize_trace(trace)) + '\n')

    def _serialize_trace(self, trace: RemediationTrace) -> Dict:
        """Serialize trace to dict."""
        # TODO: Convert to JSON-serializable format
        return {}

    def get_failure_patterns(self) -> List[Dict]:
        """Get patterns from failure traces to avoid."""
        patterns = []

        with open(self.failure_traces_file, 'r') as f:
            for line in f:
                trace_data = json.loads(line)

                # Extract pattern
                pattern = {
                    'error_type': trace_data['initial_feedback']['category'],
                    'attempted_fix': trace_data['fix_strategy'],
                    'failure_reason': trace_data['failure_reason'],
                    'stuck_pattern': trace_data['stuck_pattern']
                }

                patterns.append(pattern)

        return patterns

    def should_avoid_strategy(
        self,
        feedback: NormalizedFeedback,
        proposed_strategy: Dict[str, Any]
    ) -> bool:
        """Check if this strategy previously failed for similar error."""

        failure_patterns = self.get_failure_patterns()

        for pattern in failure_patterns:
            # Check similarity
            if self._is_similar_error(feedback, pattern):
                if self._is_similar_strategy(proposed_strategy, pattern['attempted_fix']):
                    return True  # Avoid this known-bad approach

        return False

    def _is_similar_error(self, feedback: NormalizedFeedback, pattern: Dict) -> bool:
        """Check if error is similar to known failure pattern."""
        # TODO: Implement similarity check
        return False

    def _is_similar_strategy(self, strategy: Dict, known_bad: Dict) -> bool:
        """Check if strategy is similar to known-bad approach."""
        # TODO: Implement similarity check
        return False
```

---

## 5. Escalation Heuristics

### 5.1 Escalation Decision Logic

```python
# global/agent-loops/core/escalation.py

from global.agent_loops.core.feedback_schema import NormalizedFeedback, DeterministicBlocker
from typing import Optional, Dict, Any

class EscalationDecider:
    """Decide when to escalate vs iterate."""

    def __init__(self):
        self.confidence_threshold = 0.3

    def should_escalate(
        self,
        feedback: NormalizedFeedback,
        iteration: int,
        max_iterations: int,
        fix_confidence: float,
        stuck_detector: StuckDetector,
        priority_flags: List[str] = None
    ) -> tuple[bool, Optional[str]]:
        """Determine if loop should escalate."""

        # 1. Check for deterministic blockers (immediate escalation)
        if feedback.is_deterministic_blocker:
            return True, f"deterministic_blocker_{feedback.blocker_type.value}"

        # 2. Check for stuck patterns
        is_stuck, stuck_reason = stuck_detector.check_stuck(feedback)
        if is_stuck:
            return True, f"stuck_{stuck_reason}"

        # 3. Check confidence threshold
        if fix_confidence < self.confidence_threshold:
            return True, "low_confidence_fix"

        # 4. Check max iterations
        if iteration >= max_iterations:
            return True, "max_iterations_reached"

        # 5. Check priority flags
        if priority_flags:
            if "prod_touching" in priority_flags:
                # Escalate faster for prod work
                if iteration >= max_iterations // 2:
                    return True, "prod_caution_escalation"

            if "user_specified_caution" in priority_flags:
                if iteration >= 2:
                    return True, "user_caution_escalation"

        # 6. Check feedback quality
        if feedback.is_noisy():
            return True, "noisy_feedback_cannot_fix"

        return False, None
```

### 5.2 Failure Taxonomy

```python
# global/agent-loops/core/failure_taxonomy.py

from enum import Enum

class FailureSeverity(Enum):
    """Severity levels for failures."""
    CRITICAL = "critical"  # Immediate escalation
    HIGH = "high"          # Escalate after 1-2 attempts
    MEDIUM = "medium"      # Normal iteration
    LOW = "low"            # Can iterate many times

class FailureTaxonomy:
    """Classify failures for appropriate handling."""

    TAXONOMY = {
        # Critical - Escalate immediately
        FeedbackCategory.PERMISSION_DENIED: FailureSeverity.CRITICAL,
        FeedbackCategory.SECURITY_VIOLATION: FailureSeverity.CRITICAL,

        # High - Escalate quickly
        FeedbackCategory.MISSING_DEPENDENCY: FailureSeverity.HIGH,
        FeedbackCategory.NETWORK_ERROR: FailureSeverity.HIGH,

        # Medium - Normal iteration
        FeedbackCategory.TEST_FAILURE: FailureSeverity.MEDIUM,
        FeedbackCategory.BUILD_ERROR: FailureSeverity.MEDIUM,
        FeedbackCategory.TYPE_ERROR: FailureSeverity.MEDIUM,

        # Low - Can iterate
        FeedbackCategory.LINT_WARNING: FailureSeverity.LOW,
    }

    @classmethod
    def get_severity(cls, category: FeedbackCategory) -> FailureSeverity:
        """Get severity for a failure category."""
        return cls.TAXONOMY.get(category, FailureSeverity.MEDIUM)

    @classmethod
    def get_max_iterations(cls, severity: FailureSeverity) -> int:
        """Get max iterations based on severity."""
        return {
            FailureSeverity.CRITICAL: 0,
            FailureSeverity.HIGH: 2,
            FailureSeverity.MEDIUM: 5,
            FailureSeverity.LOW: 3
        }[severity]
```

---

## 6. Updated Loop Executor

### 6.1 Foundation-Enhanced Executor

```python
# global/agent-loops/core/foundation_loop_executor.py

from global.agent_loops.core.feedback_schema import NormalizedFeedback
from global.agent_loops.feedback.feedback_registry import FeedbackRegistry
from global.agent_loops.remediation.skill_library import SkillLibrary
from global.agent_loops.remediation.skill_composer import SkillComposer
from global.agent_loops.safety.adaptive_limits import AdaptiveLimits
from global.agent_loops.safety.stuck_detector import StuckDetector
from global.agent_loops.safety.resource_guards import ResourceGuard
from global.agent_loops.safety.state_isolation import StateIsolation
from global.agent_loops.learning.trace_collector import TraceCollector
from global.agent_loops.core.escalation import EscalationDecider
from global.agent_loops.core.failure_taxonomy import FailureTaxonomy

class FoundationLoopExecutor:
    """Loop executor with full Codex-enhanced foundation."""

    def __init__(self, agent_name: str, config: LoopConfig):
        self.agent_name = agent_name
        self.config = config
        self.loop_id = f"{agent_name}-{int(time.time())}"

        # Foundation components
        self.feedback_registry = FeedbackRegistry()
        self.skill_library = SkillLibrary()
        self.skill_composer = SkillComposer(self.skill_library)
        self.adaptive_limits = AdaptiveLimits(config.max_iterations)
        self.stuck_detector = StuckDetector()
        self.resource_guard = ResourceGuard(ResourceLimits())
        self.state_isolation = StateIsolation(self.loop_id)
        self.trace_collector = TraceCollector()
        self.escalation_decider = EscalationDecider()

        self.iteration = 0
        self.start_time = time.time()

    def execute_loop(
        self,
        task: Dict[str, Any],
        criteria: SuccessCriteria,
        priority_flags: List[str] = None
    ) -> Dict[str, Any]:
        """Execute loop with foundation enhancements."""

        with self.state_isolation.isolated_execution():

            while True:
                self.iteration += 1

                # Get current adaptive limit
                current_max = self.adaptive_limits.get_current_limit()

                print(f"[{self.loop_id}] Iteration {self.iteration}/{current_max}")

                # Check resources
                resources_ok, resource_issue = self.resource_guard.check_resources()
                if not resources_ok:
                    return self._escalate(f"resource_limit_{resource_issue}")

                # EXECUTE
                execution_result = self._execute_task(task)

                # VALIDATE (with timeout)
                try:
                    raw_feedback = self.resource_guard.with_timeout(
                        lambda: self._gather_raw_feedback(execution_result)
                    )
                except TimeoutError:
                    return self._escalate("validation_timeout")

                # Normalize feedback
                normalized_feedback = self._normalize_feedback(raw_feedback)

                # Check if feedback is actionable
                if not normalized_feedback.is_actionable():
                    return self._escalate("low_quality_feedback")

                # EVALUATE
                evaluation = self._evaluate_feedback(normalized_feedback, criteria)

                # Record iteration for adaptive limits
                self.adaptive_limits.record_iteration(
                    iteration=self.iteration,
                    feedback_hash=self._hash_feedback(normalized_feedback),
                    made_progress=evaluation.get('made_progress', False),
                    confidence=evaluation.get('confidence', 0.5)
                )

                # DECIDE
                if evaluation['status'] == 'success':
                    # Record success trace
                    self._record_success_trace(task, normalized_feedback, execution_result)
                    return self._complete_success(execution_result)

                # Check escalation conditions
                should_escalate, escalation_reason = self.escalation_decider.should_escalate(
                    feedback=normalized_feedback,
                    iteration=self.iteration,
                    max_iterations=current_max,
                    fix_confidence=evaluation.get('confidence', 0.5),
                    stuck_detector=self.stuck_detector,
                    priority_flags=priority_flags
                )

                if should_escalate:
                    self._record_failure_trace(
                        task, normalized_feedback, escalation_reason
                    )
                    return self._escalate(escalation_reason)

                # ITERATE - Generate fix with skill system
                fix_strategy = self._generate_intelligent_fix(
                    normalized_feedback, evaluation
                )

                # Check if we should avoid this strategy (learned from failures)
                if self.trace_collector.should_avoid_strategy(normalized_feedback, fix_strategy):
                    return self._escalate("known_bad_strategy")

                # Apply fix
                self._apply_fix(fix_strategy)

    def _normalize_feedback(self, raw_feedback: Dict) -> NormalizedFeedback:
        """Normalize raw feedback using registry."""
        tool = raw_feedback['tool']
        return self.feedback_registry.normalize(tool, raw_feedback)

    def _generate_intelligent_fix(
        self,
        feedback: NormalizedFeedback,
        evaluation: Dict
    ) -> Dict[str, Any]:
        """Generate fix using skill library and LLM composition."""

        # Embed the error
        error_text = " ".join(f.message for f in feedback.salient_fragments)
        error_embedding = self.skill_library.embed_error(error_text)

        # Retrieve candidate skills
        candidate_skills = self.skill_library.retrieve_skills(
            error_embedding=error_embedding,
            feedback=feedback,
            top_k=5
        )

        # Let LLM select and compose
        fix_strategy = self.skill_composer.select_fix_strategy(
            feedback=feedback,
            candidate_skills=candidate_skills
        )

        return fix_strategy

    def _record_success_trace(self, task, feedback, result):
        """Record successful remediation trace."""
        # TODO: Implement trace recording
        pass

    def _record_failure_trace(self, task, feedback, reason):
        """Record failed remediation trace."""
        # TODO: Implement trace recording
        pass

    # ... other methods from base LoopExecutor
```

---

## Implementation Timeline

### Week 1: Core Infrastructure
- [ ] Implement NormalizedFeedback schema
- [ ] Build 3 normalizers: pytest, eslint, xcodebuild
- [ ] Create FeedbackRegistry
- [ ] Write unit tests for normalization

### Week 2: Remediation Skills
- [ ] Implement RemediationSkill class
- [ ] Build SkillLibrary with embeddings
- [ ] Create SkillComposer with LLM selection
- [ ] Seed initial skill library (10-15 common fixes)
- [ ] Test skill retrieval

### Week 3: Safety & Learning
- [ ] Implement AdaptiveLimits
- [ ] Build StuckDetector
- [ ] Create ResourceGuard
- [ ] Implement StateIsolation
- [ ] Build TraceCollector for success/failure traces
- [ ] Test safety mechanisms

### Week 4: Integration & Testing
- [ ] Update FoundationLoopExecutor
- [ ] Build EscalationDecider
- [ ] Create FailureTaxonomy
- [ ] Integration tests for complete system
- [ ] Performance benchmarks
- [ ] Documentation

---

## Success Criteria

**Phase 0 complete when:**
- [ ] All 5 core systems implemented and tested
- [ ] At least 3 tool normalizers working (pytest, eslint, xcodebuild)
- [ ] Skill library seeded with 10+ skills
- [ ] Safety mechanisms validated (no runaway loops in tests)
- [ ] Failure traces being captured correctly
- [ ] Integration tests passing
- [ ] Ready to pilot with Frontend Dev agent

---

## Next Steps

1. **Start with feedback schema** (most foundational)
2. **Build normalizers** for key tools
3. **Implement skill system** with embeddings
4. **Add safety guards** with testing
5. **Integrate everything** into FoundationLoopExecutor

This foundation makes Phase 1 pilots much more likely to succeed on first deployment.
