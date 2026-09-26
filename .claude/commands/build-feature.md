# /build-feature - Natural Language Feature Builder

**Purpose:** Conversational wrapper for the autonomous feature loop. Describe features in plain English and {{ORCHESTRATOR_NAME}} generates a PRD and immediately starts building.

**Invocation = Approval.** No confirmation prompts - when you invoke, you're ready to build.

---

## Usage

```
/build-feature "Add user authentication with JWT tokens and a React login form"
```

The system will:
1. Parse your description
2. Generate a structured PRD with tasks
3. Show the plan (for visibility, not approval)
4. Immediately start the autonomous feature loop

---

## Workflow

### Step 1: Parse Description

Analyze the feature description to identify:
- **What's being built** (core functionality)
- **Technology requirements** (frameworks, APIs, services)
- **Components needed** (UI, API, database, etc.)
- **Integration points** (external services, existing systems)

### Step 2: Generate PRD

Use the PRD generation template at `{{CATALYST_ROOT}}/tools/feature-loop/prd-generator-prompt.md` to create a structured plan.

**Key elements:**
- Feature name and description
- Branch name (kebab-case)
- Decomposed tasks (context-window-sized)
- Specialist assignments
- Acceptance criteria
- Priority ordering

### Step 3: Present Plan (Visibility Only)

Show the user what's being built (no approval needed):
```
📋 Feature: [Name]
🌿 Branch: feature/[slug]
📝 Tasks: [count]

1. [Specialist] Task title
2. [Specialist] Task title
...

Starting autonomous build...
```

### Step 4: Execute Immediately

No approval prompt - invocation is approval:
1. Create `tasks/` directory if needed
2. Save PRD to `tasks/[feature-slug].json`
3. Invoke `/feature-loop tasks/[feature-slug].json`
4. Feature loop runs autonomously until complete

---

## PRD Generation Guidelines

### Task Decomposition

**Rules:**
- Each task completable in one context window
- Separate concerns: UI separate from API, migrations separate from endpoints
- Sequential dependencies respected
- Testing as final validation tasks

**Example breakdown for "Stripe payments":**
- Task 1: Create database schema for transactions
- Task 2: Implement Stripe webhook endpoint
- Task 3: Build checkout UI component
- Task 4: E2E payment flow test

### Specialist Assignment

**Automatic routing based on task type:**
- Database/migrations/APIs → **Backend Dev**
- React/Vue/UI components → **Frontend Dev**
- iOS/Swift/mobile → **Mobile Dev**
- Workflows/automation → **Automator**
- Final validation/testing → **Validator**

### Priority Logic

**Sequential ordering:**
1. Infrastructure/dependencies first (migrations, schemas)
2. Core backend functionality (APIs, business logic)
3. Frontend implementation (UI, components)
4. Integration/testing (E2E, validation)

### Acceptance Criteria

**Quality criteria:**
- Specific and measurable
- Include edge cases
- Reference concrete behaviors
- Testable/verifiable

**Good examples:**
- ✅ "Returns 401 on invalid credentials"
- ✅ "Card input with validation and error messages"
- ✅ "Migration runs without errors"

**Bad examples:**
- ❌ "Works correctly"
- ❌ "Handles errors"
- ❌ "Is secure"

### Branch Naming

**Convention:** `feature/[kebab-case-slug]`

**Examples:**
- `feature/user-auth`
- `feature/stripe-payments`
- `feature/email-notifications`

### Task ID Prefixes

Use feature-specific prefixes for task IDs:
- Authentication → `AUTH-001`, `AUTH-002`
- Payments → `PAY-001`, `PAY-002`
- Notifications → `NOTIF-001`, `NOTIF-002`

---

## Example Interaction

```
User: /build-feature "Add Stripe payment checkout flow"

{{ORCHESTRATOR_NAME}}: 📋 Feature: Stripe Payment Checkout
🌿 Branch: feature/stripe-checkout
📝 Tasks: 5

1. [Backend Dev] Create transactions table and migration
2. [Backend Dev] Implement Stripe webhook endpoint
3. [Backend Dev] Create payment intent endpoint
4. [Frontend Dev] Build checkout form with Stripe Elements
5. [Validator] E2E payment flow validation

PRD saved to tasks/stripe-checkout.json
Starting autonomous build...

🔄 Feature Loop Started
Iteration 1/10 - Delegating AUTH-001 to Backend Dev...
```

---

## Error Handling

**Invalid descriptions:**
If description is too vague:
- Ask clarifying questions
- Suggest alternatives
- Provide examples

**Validation failures:**
If PRD generation fails:
- Show error details
- Suggest fixes
- Offer to retry

**Feature loop errors:**
Loop handles its own errors, but if invocation fails:
- Show error message
- Preserve PRD file for manual inspection
- Suggest manual `/feature-loop` invocation

---

## File Locations

- **Command:** `{{CATALYST_ROOT}}/.claude/commands/build-feature.md`
- **PRD Template:** `{{CATALYST_ROOT}}/tools/feature-loop/prd-generator-prompt.md`
- **Generated PRDs:** `{{CATALYST_ROOT}}/tasks/[feature-slug].json`
- **Feature Loop:** `{{CATALYST_ROOT}}/tools/feature-loop/loop.sh`

---

## Integration Notes

**Works with:**
- Feature loop autonomous execution
- Agent memory system (stores learnings)
- Quality workflow (Code Reviewer → Debugger → Validator)

**Respects:**
- Governance rules (validation required, cost thresholds)
- Context window limits (tasks sized appropriately)
- Specialist expertise (proper routing)

---

*This skill makes Huxley feature development conversational and autonomous.*
