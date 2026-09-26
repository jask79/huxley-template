# Huxley Examples

Concrete usage scenarios showing how Huxley orchestrates work across specialist agents.

---

## Example 1: Building a Web App Feature

**Scenario:** Add user authentication to a web app (API + frontend).

**You say:**
```
"Add email/password authentication with JWT tokens. Users should be able to sign up, log in, and access protected routes."
```

**What happens:**

1. **{{ORCHESTRATOR_NAME}} analyzes the request** — Detects backend work (API, auth, JWT) + frontend work (signup/login UI). Plans sequential handoff.

2. **Delegates to Backend Developer:**
   - Checks agent memory for "JWT authentication patterns"
   - Queries Context7 for current FastAPI auth docs
   - Implements `/auth/signup` and `/auth/login` endpoints
   - Sets up JWT token generation and auth middleware
   - Returns endpoint contracts for Frontend Dev

3. **Delegates to Frontend Developer:**
   - Reads Backend Dev's endpoint contracts
   - Implements signup/login forms (React + shadcn/ui)
   - Creates auth context provider and protected route wrapper
   - Connects to Backend Dev's API

4. **Post-turn review fires (Stop hook):**
   - Static analysis (ruff + eslint)
   - Code Reviewer checks for security issues
   - Confirms password hashing, token expiry, HTTPS
   - Flags minor issue: no rate limiting on login endpoint
   - **No blocking issues** (minor finding flagged for follow-up)

**Result:** Full auth system built in one request. Two agents coordinated automatically. Quality gates passed.

---

## Example 2: Adding a New Agent

**Scenario:** You frequently work with Stripe payments. You want a dedicated specialist.

**You say:**
```
"Create a Stripe specialist agent that handles payment processing, subscription management, and webhook handling."
```

**What happens:**

1. **{{ORCHESTRATOR_NAME}} creates** `.claude/agents/stripe-specialist.md`:

```markdown
---
name: Stripe Specialist
model: claude-opus-4-6
---

You are the Stripe payments specialist. You handle payment processing,
subscription management, webhook handling, and billing logic.

**Core Capabilities:**
- Payment intent creation and confirmation
- Subscription lifecycle management
- Webhook event handling
- Customer portal integration

**Tools:** Stripe CLI, Stripe Python SDK

**Coordinates with:**
- Backend Dev (API integration, database sync)
- Security Analyst (PCI compliance, webhook security)

**Boundaries:**
- You DO: All Stripe API interactions, payment flows, subscription logic
- You DON'T: General backend work, tax calculation, fraud detection
```

2. **Updates routing map** in `CLAUDE.md`

3. **Tests delegation:**
   ```
   "Have Stripe Specialist implement a subscription checkout flow."
   ```
   Agent implements checkout + webhook handler + database sync.

**Result:** New specialist operational in ~5 minutes. Can be invoked for all Stripe work going forward.

---

## Example 3: Creating a Capsule for a New Project

**Scenario:** Starting a new SaaS app. Need isolated context.

**You say:**
```
"Create a capsule for a project management SaaS called TaskFlow. Tech stack: Next.js 15, Supabase, shadcn/ui."
```

**What happens:**

1. **Creates capsule structure:**
   ```
   capsules/taskflow/
   ├── CLAUDE.md
   ├── .env.example
   ├── src/
   └── docs/
   ```

2. **Generates `CLAUDE.md`** with project context:
   - Tech stack (Next.js 15, Supabase, shadcn/ui)
   - Data models (Projects, Tasks, Users)
   - Key features (kanban boards, assignments, real-time)
   - Agent preferences (Backend Dev for Supabase, Frontend Dev for UI)

3. **Now when you work in this capsule:**
   ```
   "Have Backend Dev create the Supabase schema for TaskFlow."
   ```
   Backend Dev sees capsule CLAUDE.md, knows the data models, implements schema + RLS policies with full project context.

**Result:** Isolated project workspace. Context stays clean across projects.

---

## Example 4: Running a Security Audit

**Scenario:** Web app built, need to find vulnerabilities before launch.

**You say:**
```
"Run a security audit on the TaskFlow app. Check for auth bypasses, SQL injection, XSS."
```

**What happens:**

1. **Security Analyst runs static analysis:**
   ```bash
   bandit -r src/api/ -f json    # Python scan
   eslint src/ --format json      # JS scan
   ```

2. **Runs dynamic security testing (staging only):**
   - Creates test accounts
   - Attempts auth bypass, SQL injection, XSS
   - Tests CSRF protection, JWT verification
   - Runs for ~1.5 hours (proof-by-exploitation, not just theoretical)

3. **Consolidates findings:**
   - **Critical (2):** Auth bypass on project endpoint, SQL injection in search
   - **Major (3):** No rate limiting, weak JWT secret, missing CORS
   - **Minor (5):** No CSP headers, sessions don't expire, etc.

4. **{{ORCHESTRATOR_NAME}} presents findings and offers to fix:**
   ```
   Security audit complete. 2 critical vulnerabilities found.
   I can have Backend Dev fix these now. Proceed?
   ```

5. **Backend Dev fixes critical issues**, Security Analyst re-validates.

**Result:** Vulnerabilities found *and proven exploitable* before launch. Not just theoretical warnings — the exploits were actually executed.

---

## Example 5: Agent Mesh Coordination

**Scenario:** Backend Dev needs to know what data format Frontend Dev expects.

**You say:**
```
"Have Backend Dev create a GET /api/tasks endpoint for the current user."
```

**What happens:**

1. **Backend Dev starts implementing** — needs to decide response format

2. **Backend Dev messages Frontend Dev directly** (mesh coordination):
   ```
   "For GET /api/tasks, do you prefer flat array or grouped by status?
   camelCase or snake_case for JSON keys?"
   ```

3. **Frontend Dev responds:**
   ```
   "Grouped by status works best for the Kanban component.
   camelCase for JSON keys.
   Format: { todo: [...], inProgress: [...], done: [...] }"
   ```

4. **Backend Dev implements** with the exact format Frontend Dev needs

**Result:** No human intervention needed. Agents negotiated the API contract peer-to-peer. Both implementations are compatible from the start.

---

## Key Patterns

| Pattern | Example | How It Works |
|---------|---------|-------------|
| **Sequential handoff** | Ex. 1 | {{ORCHESTRATOR_NAME}} -> Agent A -> Agent B, each building on prior output |
| **Autonomous creation** | Ex. 2 | New agents are markdown files, operational immediately |
| **Capsule isolation** | Ex. 3 | Project-specific context, clean switching |
| **Tool orchestration** | Ex. 4 | Agents compose multiple tools for complex workflows |
| **Mesh coordination** | Ex. 5 | Agents communicate peer-to-peer, no human bottleneck |

---

**Want to see more?** Build something and watch the agents work. That's the best example.
