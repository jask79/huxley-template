# Frontend Dev Agentic Loop

Complete autonomous frontend development with feedback iteration.

## Overview

The Frontend Dev agentic loop enables autonomous component building with automatic iteration until all validations pass. It integrates the Phase 0 foundation with frontend-specific normalizers, skills, and validation strategies.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Dev Loop                         │
│                                                               │
│  1. Execute Task (build component)                           │
│  2. Validate (npm build, vitest, tsc, eslint)               │
│  3. Normalize Feedback (Vitest/TSC normalizers)             │
│  4. Apply Skills (10 frontend-specific remediation patterns) │
│  5. Iterate until success or escalation                      │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │    Foundation Loop Executor          │
        │                                       │
        │  - Adaptive iteration limits         │
        │  - Stuck detection                   │
        │  - Resource guards                   │
        │  - Trace collection                  │
        │  - Escalation decisions              │
        └──────────────────────────────────────┘
```

## Components

### 1. Normalizers (2 new)

**Vitest Normalizer** (`feedback/normalizers/vitest_normalizer.py`)
- Parses Vitest test output (JSON and text formats)
- Extracts test failures with file/line numbers
- Handles assertion errors, timeout errors, setup failures

**TypeScript Compiler Normalizer** (`feedback/normalizers/tsc_normalizer.py`)
- Parses TypeScript compiler errors
- Extracts type mismatches, missing types, import errors
- Provides actionable error locations with context

### 2. Remediation Skills (10 new)

**Frontend Skills** (`remediation/frontend_skills.py`)

1. **fix_react_hook_dependency** - Fix useEffect/useCallback dependency arrays
2. **fix_jsx_syntax** - Correct JSX syntax (self-closing tags, className, fragments)
3. **fix_import_path** - Resolve module import paths
4. **fix_prop_types** - Add/correct TypeScript prop types
5. **fix_state_mutation** - Replace direct mutations with immutable updates
6. **add_key_prop** - Add missing keys to list items
7. **fix_event_handler** - Correct event handler types and signatures
8. **fix_css_module_import** - Fix CSS module imports and usage
9. **fix_async_component** - Correct async/await patterns in components/effects
10. **fix_context_usage** - Fix React Context API setup and consumption

### 3. FrontendDevLoop Agent Class

**Location:** `agents/frontend_dev_loop.py`

**Key Methods:**

- `build_component(task)` - Main entry point for autonomous component building
- `_run_all_validations(task)` - Execute npm build, vitest, tsc, eslint
- `_run_tsc(task)` - TypeScript compilation
- `_run_vitest(task)` - Test execution
- `_run_eslint(task)` - Linting
- `get_stats()` - Retrieve iteration statistics
- `reset()` - Reset loop state for new task

## Usage

### Basic Example

```python
from agents.frontend_dev_loop import FrontendDevLoop

# Initialize loop
loop = FrontendDevLoop(
    project_dir="/path/to/your/next-app",
    max_iterations=8
)

# Define task
task = {
    'description': 'Build accessible Button component with primary/secondary variants',
    'component_path': 'src/components/Button.tsx',
    'test_path': 'src/components/Button.test.tsx',
    'requirements': ['types', 'build', 'test', 'lint']
}

# Execute with autonomous iteration
result = loop.build_component(task)

# Check result
print(f"✅ Success: {result.success}")
print(f"🔄 Iterations: {result.iterations}")
print(f"⏱️  Time: {result.execution_time:.2f}s")

if result.escalation_triggered:
    print(f"⚠️  Escalated: {result.escalation_reason}")
```

### Task Definition

```python
task = {
    'description': str,          # Human-readable task description
    'component_path': str,       # Path to component file (relative to project_dir)
    'test_path': str,           # Optional: path to test file
    'requirements': List[str]    # ['build', 'test', 'types', 'lint']
}
```

### Validation Requirements

| Requirement | Tool    | Checks                          |
|-------------|---------|----------------------------------|
| `types`     | tsc     | TypeScript compilation          |
| `build`     | npm     | Production build                |
| `test`      | vitest  | Unit/integration tests          |
| `lint`      | eslint  | Code quality and style          |

### Iteration Workflow

```
Iteration 1:
├─ Execute: Build component
├─ Validate: Run tsc
├─ Feedback: Type error in Button.tsx:45
├─ Normalize: Extract TS2322 error details
├─ Match Skills: find "fix_prop_types"
├─ Apply: Add missing prop type
└─ Continue...

Iteration 2:
├─ Execute: Apply fix
├─ Validate: Run vitest
├─ Feedback: Test assertion failed
├─ Normalize: Extract assertion details
├─ Match Skills: find "fix_test_assertion"
├─ Apply: Update test expectation
└─ Continue...

Iteration 3:
├─ Execute: Apply fix
├─ Validate: Run all checks
├─ Feedback: All validations pass ✅
└─ Success!
```

## Statistics and Monitoring

```python
# Get loop statistics
stats = loop.get_stats()

print(f"Total iterations: {stats['total_iterations']}")
print(f"Skill stats: {stats['skill_library_stats']}")
print(f"Validation history: {stats['validation_history']}")
```

**Available Stats:**
- Total iterations completed
- Max iterations allowed
- Skill library statistics (total skills, success rate, most used)
- Validation history across iterations

## Error Handling

### Automatic Escalation Triggers

1. **Deterministic Blockers**
   - Permission errors (EACCES)
   - Missing external dependencies
   - Service unavailable errors

2. **Stuck Detection**
   - Same error repeated 3+ times
   - No validation progress across iterations
   - Error cycling between multiple issues

3. **Resource Limits**
   - CPU usage >90% sustained
   - Memory usage >80%
   - Timeout exceeded (per-validation timeouts)

4. **Iteration Limit**
   - Max iterations reached (default: 8)
   - Adaptive limit adjustment based on progress

### Escalation Response

```python
result = loop.build_component(task)

if result.escalation_triggered:
    print(f"Reason: {result.escalation_reason}")

    # Get final feedback for debugging
    if result.final_feedback:
        print(f"Category: {result.final_feedback.category}")
        print(f"Errors: {result.final_feedback.salient_fragments}")
```

## Testing

### Run All Tests

```bash
cd {{CATALYST_ROOT}}/global/agent-loops
pytest tests/test_frontend_dev_loop.py -v
```

### Test Categories

1. **Unit Tests** - Skill matching, normalization, context extraction
2. **Integration Tests** - Full loop execution (requires real project)

### Example Test

```python
def test_skill_pattern_matching():
    """Test that frontend skills match expected error patterns."""
    library = SkillLibrary()
    seed_frontend_skills(library)

    # Test React Hook dependency skill
    hook_skill = library.get_skill('fix_react_hook_dependency')
    assert hook_skill.matches_error(
        "React Hook useEffect has a missing dependency: 'userId'",
        "build_error"
    )
```

## Configuration

### Project Setup Requirements

Your Next.js/React project needs:

```json
// package.json
{
  "scripts": {
    "build": "next build",        // or "vite build"
    "test": "vitest",
    "lint": "eslint .",
    "type-check": "tsc --noEmit"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "vitest": "^1.0.0",
    "eslint": "^8.0.0"
  }
}
```

### TypeScript Configuration

```json
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "jsx": "preserve",
    "moduleResolution": "bundler",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

## Advanced Usage

### Custom Validation Requirements

```python
# Only check types and tests (skip build and lint)
task = {
    'description': 'Quick component prototype',
    'component_path': 'src/components/Prototype.tsx',
    'requirements': ['types', 'test']  # Subset of validations
}
```

### State Isolation

```python
# Enable state isolation for parallel execution
loop = FrontendDevLoop(
    project_dir="/path/to/project",
    max_iterations=8,
    enable_state_isolation=True  # Uses temp directories
)
```

### Custom Max Iterations

```python
# Adjust iteration limit based on complexity
simple_loop = FrontendDevLoop(
    project_dir="/path/to/project",
    max_iterations=5  # Quick tasks
)

complex_loop = FrontendDevLoop(
    project_dir="/path/to/project",
    max_iterations=15  # Complex refactoring
)
```

## Performance Metrics

**Target Metrics (Phase 1 Goal):**

| Metric                | Target  | Current |
|-----------------------|---------|---------|
| Completion Rate       | ≥70%    | TBD     |
| Avg Iterations        | <5      | TBD     |
| Skill Applicability   | ≥80%    | TBD     |
| Escalation Rate       | <30%    | TBD     |

*Current values will be measured during Phase 1 pilot (10 real tasks).*

## Troubleshooting

### Common Issues

**Issue: "Cannot find module 'vitest'"**
```bash
# Install missing dependencies
npm install --save-dev vitest @vitest/ui
```

**Issue: "tsc command not found"**
```bash
# Install TypeScript
npm install --save-dev typescript
```

**Issue: "Build command failed"**
```bash
# Check package.json has build script
cat package.json | grep "build"

# Or specify custom build command
# (Modify _detect_build_command() in frontend_dev_loop.py)
```

### Debug Mode

```python
# Enable verbose logging
import logging
logging.basicConfig(level=logging.DEBUG)

loop = FrontendDevLoop(project_dir="/path/to/project")
result = loop.build_component(task)
```

## Integration with Huxley

### Usage in Agent Workflow

```python
# In Frontend Dev agent
from global.agent_loops.agents import FrontendDevLoop

def build_component_autonomously(task_description: str, component_path: str):
    """Frontend Dev agent entry point."""

    loop = FrontendDevLoop(
        project_dir=os.getcwd(),
        max_iterations=8
    )

    task = {
        'description': task_description,
        'component_path': component_path,
        'requirements': ['types', 'build', 'test', 'lint']
    }

    result = loop.build_component(task)

    return result
```

### Trace Collection

All iterations are automatically traced for learning:

```python
# Traces stored in registry/loops/
# Each trace includes:
# - Initial error
# - Iteration count
# - Skills applied
# - Validation results
# - Success/escalation outcome
```

## Next Steps

**Phase 1 Pilot:**
1. Run on 10 real component tasks
2. Measure effectiveness metrics
3. Identify skill gaps
4. Tune iteration limits
5. Improve remediation quality

**Future Enhancements:**
- Add Playwright normalizer for E2E tests
- Lighthouse normalizer for performance
- Integration with react-spring MCP for animation tasks
- Context7 MCP for library-specific guidance

## Reference

- **Quick Start:** `{{CATALYST_ROOT}}/global/agent-loops/QUICK_START.md`
- **Skill Library:** `{{CATALYST_ROOT}}/global/agent-loops/remediation/skill_library.py`
- **Tests:** `{{CATALYST_ROOT}}/global/agent-loops/tests/test_frontend_dev_loop.py`

## Support

Questions or issues? Check:
1. Phase 0 documentation for foundation concepts
2. Test suite for usage examples
3. Skill library for available remediation patterns
4. Trace logs in `registry/loops/` for debugging

---




