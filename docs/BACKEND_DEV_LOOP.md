# Backend Dev Agentic Loop

Complete autonomous backend development with feedback iteration and intelligent remediation.

## Overview

The Backend Dev Loop integrates the Phase 0 agentic loop foundation with backend-specific validation, error patterns, and remediation skills. It enables autonomous iteration for API development, database work, and backend testing.

## Features

### 🔄 Autonomous Iteration
- **Build → Validate → Fix → Repeat** until success or escalation
- Intelligent error detection and categorization
- Adaptive iteration limits based on progress

### 🔍 Backend-Specific Validation
- **pytest**: Unit and integration test execution
- **mypy**: Static type checking for Python
- **ruff**: Fast Python linting and code quality
- **api_test**: API health checks and endpoint validation

### 🛠️ Remediation Skills (10 Backend-Specific)
1. **fix_sqlalchemy_query** - SQLAlchemy query errors
2. **fix_pydantic_validation** - Pydantic model validation
3. **fix_async_endpoint** - FastAPI async/await issues
4. **add_api_error_handling** - API error responses
5. **fix_database_migration** - Alembic migration issues
6. **fix_cors_configuration** - CORS setup and preflight
7. **add_request_validation** - Input validation patterns
8. **fix_authentication** - JWT token validation
9. **optimize_database_query** - N+1 queries and performance
10. **fix_serialization** - JSON encoding errors

### 🎯 Smart Error Normalization
- Structured feedback from all validation tools
- Signal quality scoring (actionable vs noisy)
- Deterministic blocker detection (permissions, quotas, etc.)
- File/line/column extraction for precise fixes

## Installation

### Prerequisites
```bash
# Python 3.8+
pip install pytest mypy ruff

# FastAPI projects
pip install fastapi pydantic sqlalchemy alembic

# Optional: async support
pip install asyncio aiofiles httpx
```

### Setup Backend Loop
```bash
# Skills are auto-loaded on first use
# Or manually seed:
cd {{CATALYST_ROOT}}/global/agent-loops/remediation
python backend_skills.py
```

## Usage

### Basic Usage

```python
from agents.backend_dev_loop import BackendDevLoop, BackendTask

# Create loop instance
loop = BackendDevLoop(
    project_root="/path/to/project",
    max_iterations=5,
    verbose=True
)

# Define task
task = BackendTask(
    description="Create user CRUD API with authentication",
    api_file="api/users.py",
    model_file="models/user.py",
    test_file="tests/test_users.py",
    validation_tools=["pytest", "mypy", "ruff"]
)

# Run autonomous loop
result = loop.build_api(task)

if result.success:
    print(f"✅ Completed in {result.iterations} iterations")
else:
    print(f"❌ Escalated: {result.escalation_reason}")
```

### Command Line Usage

```bash
python -m agents.backend_dev_loop \
  --project /path/to/project \
  --description "Create user CRUD API" \
  --api-file api/users.py \
  --test-file tests/test_users.py \
  --tools pytest mypy ruff \
  --max-iterations 5 \
  --verbose
```

### Batch Processing

```python
# Build multiple endpoints
tasks = [
    BackendTask(
        description="User authentication endpoints",
        api_file="api/auth.py",
        test_file="tests/test_auth.py"
    ),
    BackendTask(
        description="User profile CRUD",
        api_file="api/users.py",
        test_file="tests/test_users.py"
    ),
    BackendTask(
        description="Post creation and retrieval",
        api_file="api/posts.py",
        test_file="tests/test_posts.py"
    )
]

results = loop.batch_build(tasks)

# Check results
for i, result in enumerate(results, 1):
    status = "✅" if result.success else "❌"
    print(f"{status} Task {i}: {result.iterations} iterations")
```

### Async Usage

```python
import asyncio

async def build_multiple_apis():
    loop = BackendDevLoop(project_root="/path/to/project")

    tasks = [
        BackendTask(description="Users API", api_file="api/users.py"),
        BackendTask(description="Posts API", api_file="api/posts.py"),
    ]

    # Build concurrently
    results = await asyncio.gather(*[
        loop.build_api_async(task) for task in tasks
    ])

    return results

# Run async
results = asyncio.run(build_multiple_apis())
```

## Validation Tools

### pytest
Runs unit and integration tests.

```python
task = BackendTask(
    description="Test-driven API development",
    test_file="tests/test_api.py",
    validation_tools=["pytest"]
)
```

**Output normalized**:
- Test failures with file/line
- Assertion errors
- Setup/teardown issues

### mypy
Static type checking for Python.

```python
task = BackendTask(
    description="Type-safe API",
    api_file="api/users.py",
    validation_tools=["mypy"]
)
```

**Catches**:
- Type mismatches
- Missing annotations
- Incompatible return types
- Attribute errors

### ruff
Fast Python linting.

```python
task = BackendTask(
    description="Clean code API",
    api_file="api/users.py",
    validation_tools=["ruff"]
)
```

**Checks**:
- Code style (PEP 8)
- Security issues
- Unused imports/variables
- Complexity warnings

### api_test
Custom API health checks.

```python
task = BackendTask(
    description="API health validation",
    validation_tools=["api_test"]
)
```

**Validates**:
- Endpoint availability
- Response status codes
- Response schemas
- Performance thresholds

## Remediation Skills Deep Dive

### 1. SQLAlchemy Query Fixes

**Handles**:
- DetachedInstanceError
- Multiple/no rows found
- Relationship issues

**Example Fix**:
```python
# Before: DetachedInstanceError
user = session.query(User).first()
session.close()
print(user.posts)  # Error!

# After: Eager loading
user = session.query(User).options(joinedload(User.posts)).first()
session.close()
print(user.posts)  # Works!
```

### 2. Pydantic Validation

**Handles**:
- Field required errors
- Type mismatches
- Extra fields
- Nested validation

**Example Fix**:
```python
# Before: ValidationError
class User(BaseModel):
    email: str

User(name="John")  # Error: email required

# After: Optional fields
class User(BaseModel):
    email: str
    name: Optional[str] = None

User(email="john@example.com")  # Works!
```

### 3. Async Endpoint Fixes

**Handles**:
- Coroutine not awaited
- Mixing sync/async
- Event loop issues

**Example Fix**:
```python
# Before: RuntimeWarning
@app.get("/users")
async def get_users():
    users = get_users_from_db()  # Forgot await!
    return users

# After: Proper await
@app.get("/users")
async def get_users():
    users = await get_users_from_db()
    return users
```

### 4. API Error Handling

**Handles**:
- Unhandled exceptions
- Missing HTTPException
- 500 errors

**Example Fix**:
```python
# Before: 500 error
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    user = db.query(User).filter(User.id == user_id).first()
    return user  # Returns None if not found!

# After: Proper error handling
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

### 5. Database Migration Fixes

**Handles**:
- Multiple heads
- Target not up to date
- Missing revisions
- Schema conflicts

**Example Fix**:
```bash
# Before: Multiple heads error
alembic upgrade head  # Error: Multiple heads!

# After: Merge branches
alembic merge -m "merge migration branches" rev1 rev2
alembic upgrade head  # Works!
```

## Loop Execution Flow

```
┌─────────────────────────────────────────────────┐
│ 1. EXECUTE IMPLEMENTATION                       │
│    - Generate code using LLM                    │
│    - Write files with Edit/Write tools          │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ 2. VALIDATE WITH TOOLS                          │
│    - Run pytest, mypy, ruff                     │
│    - Capture stdout/stderr/exit_code            │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ 3. NORMALIZE FEEDBACK                           │
│    - Parse tool output → structured errors      │
│    - Extract file/line/column                   │
│    - Score signal quality                       │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ 4. CHECK FOR BLOCKERS                           │
│    - Permission denied?                         │
│    - Missing external dependency?               │
│    - Quota exceeded?                            │
│    → If blocker: ESCALATE IMMEDIATELY           │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ 5. EVALUATE PROGRESS                            │
│    - Are errors decreasing?                     │
│    - Are more tests passing?                    │
│    - Is signal quality improving?               │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ 6. SEARCH FOR REMEDIATION SKILLS                │
│    - Pattern match error messages               │
│    - Semantic similarity search                 │
│    - Select best skill by success rate          │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ 7. APPLY FIX                                    │
│    - Generate fix prompt from skill             │
│    - Execute fix with LLM                       │
│    - Update files                               │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ 8. CHECK SUCCESS CRITERIA                       │
│    ✅ All tests pass?    → COMPLETE             │
│    ✅ No type errors?    → COMPLETE             │
│    ✅ No lint warnings?  → COMPLETE             │
│    ❌ Still errors?      → REPEAT (max 5x)      │
│    ❌ Stuck/no progress? → ESCALATE             │
└─────────────────────────────────────────────────┘
```

## Configuration

### Custom Validation Tools

```python
# Add custom validator
def custom_validator(project_root: Path) -> Dict[str, Any]:
    """Run custom validation logic."""
    # Your validation code
    return {
        'exit_code': 0,
        'stdout': 'Validation passed',
        'stderr': ''
    }

# Use in loop (requires extending BackendDevLoop)
```

### Adaptive Iteration Limits

```python
# Loop automatically adjusts max iterations based on:
# - Error severity (increase for simple errors)
# - Progress rate (increase if making steady progress)
# - Historical patterns (learn from past tasks)

loop = BackendDevLoop(
    project_root="/path/to/project",
    max_iterations=5  # Starting point, adapts during execution
)
```

### State Isolation

```python
# For safer experimentation (currently disabled for backend)
# Backend work modifies files directly for persistence

loop = FoundationLoopExecutor(
    agent_name="Backend Dev",
    use_state_isolation=True  # Creates temp directory for each iteration
)
```

## Escalation Scenarios

Loop escalates to human when:

1. **Deterministic Blockers**
   - Permission denied errors
   - Missing external dependencies (APIs, services)
   - Rate limits/quota exceeded
   - Service unavailable

2. **Stuck Detection**
   - Same error repeating 3+ times
   - No progress in validation criteria
   - Signal quality degrading

3. **Max Iterations Reached**
   - Default: 5 iterations
   - Adaptive limit can extend to 10 for simple errors

4. **Resource Limits**
   - Validation timeout (>60s)
   - Memory constraints
   - Disk space issues

## Monitoring & Debugging

### Trace Collection

```python
# Traces are automatically collected for learning
# Location: {{CATALYST_ROOT}}/registry/traces/

loop = BackendDevLoop(project_root="/path/to/project")
result = loop.build_api(task)

print(f"Trace ID: {result.trace_id}")
# View trace: registry/traces/{trace_id}.json
```

### Verbose Output

```python
loop = BackendDevLoop(
    project_root="/path/to/project",
    verbose=True  # Print detailed execution logs
)
```

### Skill Performance

```python
from remediation.skill_library import get_library

library = get_library()
stats = library.get_stats()

print(f"Total skills: {stats['total_skills']}")
print(f"Average success rate: {stats['avg_success_rate']:.2%}")
print(f"Most used: {stats['most_used_skill']}")
```

## Testing

### Run Test Suite

```bash
cd {{CATALYST_ROOT}}/global/agent-loops
pytest tests/test_backend_dev_loop.py -v
```

### Test Coverage

```bash
pytest tests/test_backend_dev_loop.py --cov=agents.backend_dev_loop --cov-report=html
```

## Example Projects

### FastAPI CRUD API

```python
task = BackendTask(
    description="""
    Create FastAPI CRUD endpoints for User resource:
    - POST /users (create with validation)
    - GET /users (list with pagination)
    - GET /users/{id} (retrieve single)
    - PUT /users/{id} (update)
    - DELETE /users/{id} (soft delete)

    Requirements:
    - Pydantic schemas for request/response
    - SQLAlchemy models with relationships
    - Async database operations
    - JWT authentication
    - Comprehensive tests
    """,
    api_file="api/users.py",
    model_file="models/user.py",
    test_file="tests/test_users_api.py",
    validation_tools=["pytest", "mypy", "ruff", "api_test"]
)

result = loop.build_api(task)
```

### Database Schema with Alembic

```python
task = BackendTask(
    description="""
    Create database schema for blog platform:
    - Users table (id, email, password_hash, created_at)
    - Posts table (id, user_id, title, content, published_at)
    - Comments table (id, post_id, user_id, content, created_at)

    Generate Alembic migration with:
    - Foreign key constraints
    - Indexes on foreign keys
    - Unique constraint on user email
    """,
    model_file="models/__init__.py",
    validation_tools=["mypy"]
)

result = loop.build_api(task)
```

## Best Practices

### 1. Comprehensive Task Descriptions
```python
# Good: Detailed requirements
task = BackendTask(
    description="""
    Create user authentication endpoint:
    - Accept email and password
    - Validate credentials against database
    - Return JWT token with 24h expiration
    - Include refresh token mechanism
    - Rate limit to 5 attempts per minute
    """,
    api_file="api/auth.py"
)

# Bad: Vague requirements
task = BackendTask(
    description="Make login endpoint",
    api_file="api/auth.py"
)
```

### 2. Use Appropriate Validation Tools
```python
# For type-heavy code: include mypy
task = BackendTask(
    description="Complex type transformations",
    validation_tools=["pytest", "mypy"]  # Include mypy
)

# For API endpoints: include api_test
task = BackendTask(
    description="REST API endpoints",
    validation_tools=["pytest", "api_test"]  # Include api_test
)
```

### 3. Iterate on Failures
```python
result = loop.build_api(task)

if not result.success:
    # Review escalation reason
    print(result.escalation_reason)

    # Check final feedback
    if result.final_feedback:
        primary_error = result.final_feedback.get_primary_error()
        print(f"Last error: {primary_error.message}")
        print(f"File: {primary_error.file_path}:{primary_error.line_number}")

    # Adjust task and retry
    task.validation_tools = ["pytest"]  # Simplify validation
    result = loop.build_api(task)
```

## Troubleshooting

### Issue: Skills Not Loading

```python
# Manually seed skills
from remediation.skill_library import get_library
from remediation.backend_skills import seed_backend_skills

library = get_library()
seed_backend_skills(library)
```

### Issue: Validation Tools Not Found

```bash
# Install missing tools
pip install pytest mypy ruff

# Verify installation
which pytest
which mypy
which ruff
```

### Issue: Loop Not Making Progress

```python
# Enable verbose output
loop = BackendDevLoop(project_root="/path", verbose=True)

# Check if stuck on same error
# Review trace: registry/traces/{trace_id}.json

# Increase max iterations if making slow progress
loop.executor.adaptive_limits.default_max_iterations = 10
```

## Contributing

### Adding New Backend Skills

```python
from remediation.skill import RemediationSkill, SkillType, SkillMetadata
import time

new_skill = RemediationSkill(
    skill_id="fix_new_pattern",
    name="Fix New Error Pattern",
    description="Resolve XYZ errors",
    skill_type=SkillType.CODE_FIX,
    error_patterns=[
        r"pattern1",
        r"pattern2"
    ],
    applicable_categories=["runtime_error"],
    fix_template="""
    Fix instructions here...
    """,
    required_context=["file_path", "error_message"],
    metadata=SkillMetadata(version="1.0", created_at=time.time()),
    tags=["backend", "custom"]
)

# Add to library
library = get_library()
library.add_skill(new_skill)
library.save()
```

### Adding New Normalizers

See `global/agent-loops/feedback/normalizers/` for examples.

## References

- Phase 0 Foundation: `{{CATALYST_ROOT}}/global/agent-loops/`
- Backend Skills: `global/agent-loops/remediation/backend_skills.py`
- Loop Executor: `global/agent-loops/core/loop_executor.py`
- Feedback Schema: `global/agent-loops/core/feedback_schema.py`

## Support

For issues or questions:
- Check existing test cases: `tests/test_backend_dev_loop.py`
- Review skill implementations: `remediation/backend_skills.py`
