# Phase 0 Agentic Loops - Quick Start

## What Is This?

Complete foundation for self-healing agentic loops. Agents can now:
- Execute tasks iteratively
- Validate results automatically
- Learn from past successes/failures
- Fix errors using learned skills
- Detect when stuck and escalate

## 30-Second Example

```python
from core.loop_executor import FoundationLoopExecutor

# Create executor
executor = FoundationLoopExecutor(agent_name="Frontend Dev", max_iterations=5)

# Define what to do
def build_component(task):
    # Your build logic here
    return True

def validate_build():
    # Run tests/lint
    return "pytest", {"exit_code": 0, "stdout": "All passed", "stderr": ""}

# Run loop
result = executor.execute_loop(
    task={'description': 'Build header component'},
    execute_fn=build_component,
    validate_fn=validate_build,
    criteria={'tests_pass': True, 'linting': True}
)

print(f"Success: {result.success} in {result.iterations} iterations")
```

## What You Get

### 1. Feedback Normalization
All tool output → structured errors with quality scoring

### 2. Remediation Skills
15 pre-built skills for common errors + semantic search

### 3. Safety Mechanisms
- Adaptive iteration limits (2-15)
- Stuck detection (3 signals)
- Resource guards (CPU/memory/time)
- State isolation (temp dirs)

### 4. Learning System
- Success/failure trace collection
- Pattern extraction
- Avoidance recommendations

### 5. Complete Integration
Loop executor orchestrates everything:
Execute → Validate → Evaluate → Decide → Repeat

## File Count

**36 Python files** | **6,654 lines of code** | **9 test files**

## Directory Structure

```
agent-loops/
├── core/           # Loop executor + schemas
├── feedback/       # Normalizers (pytest, eslint, xcodebuild)
├── remediation/    # Skills library (15 initial skills)
├── safety/         # Adaptive limits + stuck detection
├── learning/       # Trace collection + patterns
└── tests/          # Unit + integration tests
```

## Storage

```
registry/
├── remediation_skills.json  # Skill library
├── loops/                   # Per-loop execution logs
└── traces/                  # Success/failure patterns
    ├── success_traces.jsonl
    └── failure_traces.jsonl
```

## Dependencies

```bash
pip install openai numpy psutil pytest
```

## Run Tests

```bash
cd {{CATALYST_ROOT}}/global/agent-loops
pytest tests/ -v
```

## Next: Phase 1 Pilot

Integrate with Frontend Dev agent for real-world testing.

**Full Documentation:** See `PHASE_0_COMPLETE.md`
