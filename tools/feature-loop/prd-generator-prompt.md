# PRD Generation Prompt Template

This template guides PRD generation from natural language feature descriptions. Use this when processing `/build-feature` requests.

---

## PRD Structure

```json
{
  "feature": "Feature Name",
  "branch": "feature/kebab-case-slug",
  "description": "Brief description of what's being built",
  "maxIterations": 10,
  "governance": {
    "requireValidation": true,
    "notifyOnComplete": true,
    "costAlertThreshold": 5
  },
  "tasks": [
    {
      "id": "PREFIX-001",
      "title": "Task title",
      "description": "Detailed description",
      "specialist": "Specialist Name",
      "priority": 1,
      "acceptanceCriteria": [
        "Criterion 1",
        "Criterion 2"
      ],
      "passes": false,
      "completedAt": null,
      "learnings": []
    }
  ]
}
```

---

## Task Decomposition Strategy

### Context Window Constraints

Each task must be completable in a single agent context window (~15-20 minutes of work).

**Too large (split into multiple tasks):**
- ❌ "Build entire authentication system"
- ❌ "Implement payment processing"
- ❌ "Create admin dashboard"

**Right-sized (single task):**
- ✅ "Create user model and migration"
- ✅ "Implement JWT token generation endpoint"
- ✅ "Build login form component"

### Separation of Concerns

**Split by domain:**
- Database/schema changes separate from application logic
- Backend APIs separate from frontend UI
- Infrastructure separate from business logic
- Testing separate from implementation

**Example breakdown:**

Feature: "User authentication"

```
Task 1: Database (Backend Dev)
  - User table schema
  - Migration file
  - Password hashing setup

Task 2: Auth API (Backend Dev)
  - JWT token generation
  - Login endpoint
  - Token validation middleware

Task 3: Login UI (Frontend Dev)
  - Login form component
  - API integration
  - Error handling

Task 4: Validation (Validator)
  - E2E login flow
  - Error case testing
  - Token persistence
```

### Dependency Ordering

**Sequential priorities:**
1. **Infrastructure first** - migrations, schemas, base configuration
2. **Backend logic** - APIs, business logic, data processing
3. **Frontend implementation** - UI components, user interactions
4. **Integration & testing** - E2E flows, validation, edge cases

**Example:**
```json
[
  {
    "priority": 1,
    "title": "Create payment transactions table",
    "specialist": "Backend Dev"
  },
  {
    "priority": 2,
    "title": "Implement Stripe webhook endpoint",
    "specialist": "Backend Dev"
  },
  {
    "priority": 3,
    "title": "Build checkout form UI",
    "specialist": "Frontend Dev"
  },
  {
    "priority": 4,
    "title": "Validate payment flow E2E",
    "specialist": "Validator"
  }
]
```

---

## Specialist Assignment Rules

### Automatic Routing by Task Type

**Backend Developer:**
- Database schemas and migrations
- API endpoints and business logic
- Authentication and authorization
- External API integrations
- Server-side rendering setup
- Deployment configuration (Vercel, Cloudflare, etc.)
- All Cloudflare services (Pages, Workers, R2, D1, DNS, CDN)
- CI/CD pipelines
- Environment configuration

**Frontend Developer:**
- React/Next.js/Vue components
- UI state management
- Client-side routing
- Form handling and validation
- Frontend API integration
- shadcn/ui component usage
- Component styling (Tailwind, CSS)

**Mobile Developer:**
- iOS Swift development
- React Native implementation
- Mobile UI components
- iOS simulator testing
- Mobile app deployment

**Automator:**
- n8n workflow creation
- Apple Shortcuts generation
- Webhook automation
- Scheduled tasks
- Integration workflows

**Validator:**
- E2E testing (always final task)
- Integration testing
- Edge case validation
- Performance testing
- Cross-browser/device testing

### Multi-Specialist Features

For complex features requiring multiple specialists:

**Example: E-commerce checkout**
```json
[
  {
    "specialist": "Backend Dev",
    "title": "Create order processing API"
  },
  {
    "specialist": "Backend Dev",
    "title": "Implement Stripe webhook handler"
  },
  {
    "specialist": "Frontend Dev",
    "title": "Build product selection UI"
  },
  {
    "specialist": "Frontend Dev",
    "title": "Create checkout form with Stripe Elements"
  },
  {
    "specialist": "Validator",
    "title": "E2E purchase flow validation"
  }
]
```

---

## Acceptance Criteria Guidelines

### Quality Criteria

**Specific and Measurable:**
- ✅ "Returns 401 status on invalid credentials"
- ❌ "Handles authentication errors"

**Include Edge Cases:**
- ✅ "Shows loading spinner during API call"
- ✅ "Displays error message on network failure"
- ❌ "Works correctly"

**Reference Concrete Behaviors:**
- ✅ "Card input validates format before submission"
- ✅ "Redirects to dashboard on successful login"
- ❌ "Form works as expected"

**Testable/Verifiable:**
- ✅ "Migration creates users table with email column"
- ✅ "Webhook signature validation prevents unauthorized requests"
- ❌ "Database is set up correctly"

### Examples by Task Type

**Database/Migration Tasks:**
```json
"acceptanceCriteria": [
  "Users table created with id, email, password_hash, created_at columns",
  "Migration runs without errors on fresh database",
  "Email column has unique constraint",
  "Indexes on email and created_at columns"
]
```

**API Endpoint Tasks:**
```json
"acceptanceCriteria": [
  "POST /auth/login accepts email and password",
  "Returns JWT token on valid credentials",
  "Returns 401 with error message on invalid credentials",
  "Token expires in 24 hours",
  "Rate limiting prevents brute force (5 attempts/minute)"
]
```

**UI Component Tasks:**
```json
"acceptanceCriteria": [
  "Email and password inputs with proper validation",
  "Submit button disabled during loading",
  "Shows error message below form on failure",
  "Clears password field on error",
  "Redirects to /dashboard on success",
  "Accessible (keyboard navigation, ARIA labels)"
]
```

**Validation Tasks:**
```json
"acceptanceCriteria": [
  "Can create account and login successfully",
  "Invalid credentials show error message",
  "Token persists across page refreshes",
  "Protected routes redirect to login when not authenticated",
  "Logout clears token and redirects to login"
]
```

---

## Branch Naming Convention

**Format:** `feature/[kebab-case-slug]`

**Slug Generation:**
- Lowercase only
- Hyphens separate words
- Max 3-4 words
- Descriptive but concise

**Examples:**

| Feature Description | Branch Name |
|---------------------|-------------|
| User authentication with JWT | `feature/user-auth` |
| Stripe payment checkout | `feature/stripe-checkout` |
| Email notification system | `feature/email-notifications` |
| Admin dashboard UI | `feature/admin-dashboard` |
| Real-time chat with WebSockets | `feature/realtime-chat` |

**Avoid:**
- ❌ `feature/implement-user-authentication-with-jwt-tokens` (too long)
- ❌ `feature/auth` (too vague)
- ❌ `feature/STRIPE-PAYMENT` (uppercase)
- ❌ `feature/user_auth` (underscores)

---

## Task ID Prefix Strategy

Use feature-specific prefixes for task IDs to improve traceability.

**Format:** `[PREFIX]-[NUMBER]`

**Prefix Selection:**

| Feature Type | Prefix | Example IDs |
|--------------|--------|-------------|
| Authentication | AUTH | AUTH-001, AUTH-002 |
| Payments/Stripe | PAY | PAY-001, PAY-002 |
| Email/Notifications | NOTIF | NOTIF-001, NOTIF-002 |
| User Profile | PROF | PROF-001, PROF-002 |
| Admin Dashboard | ADMIN | ADMIN-001, ADMIN-002 |
| Search | SEARCH | SEARCH-001, SEARCH-002 |
| Chat/Messaging | CHAT | CHAT-001, CHAT-002 |
| Analytics | ANALYTICS | ANALYTICS-001 |
| API Integration | API | API-001, API-002 |

**Guidelines:**
- Keep prefix 3-8 characters
- All uppercase
- Descriptive but not too long
- Consistent within feature

---

## Iteration Estimation

Estimate `maxIterations` based on task complexity and count.

**Formula:**
```
maxIterations = (task_count * 1.2) + 2
```

**Examples:**

| Task Count | Base Estimate | With Buffer | Final |
|------------|---------------|-------------|-------|
| 3 tasks | 3 | 3.6 | 6 |
| 5 tasks | 5 | 6 | 8 |
| 8 tasks | 8 | 9.6 | 12 |
| 10 tasks | 10 | 12 | 14 |

**Factors increasing iterations:**
- Complex integrations (+2-3)
- External APIs with rate limits (+2)
- Heavy testing requirements (+2)
- Novel technologies (+2-3)

**Conservative approach:** Round up to nearest even number.

---

## Governance Configuration

**Standard settings for all PRDs:**

```json
"governance": {
  "requireValidation": true,
  "notifyOnComplete": true,
  "costAlertThreshold": 5
}
```

**requireValidation:** Always true - Validator must verify final state

**notifyOnComplete:** Always true - Alert {{USER_NAME}} when feature completes

**costAlertThreshold:** Alert if iterations exceed this multiple of task count
- Standard: 5 (reasonable for most features)
- Increase to 8 for experimental/research features
- Decrease to 3 for simple CRUD operations

---

## Full Example PRD

**Input:** "Add user authentication with JWT tokens and React login form"

**Generated PRD:**

```json
{
  "feature": "User Authentication",
  "branch": "feature/user-auth",
  "description": "JWT-based authentication system with secure login UI",
  "maxIterations": 10,
  "governance": {
    "requireValidation": true,
    "notifyOnComplete": true,
    "costAlertThreshold": 5
  },
  "tasks": [
    {
      "id": "AUTH-001",
      "title": "Create user model and database migration",
      "description": "Set up User table schema with password hashing support",
      "specialist": "Backend Dev",
      "priority": 1,
      "acceptanceCriteria": [
        "Users table created with id (UUID), email (unique), password_hash, created_at, updated_at",
        "Migration runs successfully on fresh database",
        "Email column has unique constraint and index",
        "Password hashing uses bcrypt with salt rounds = 10",
        "Includes rollback migration"
      ],
      "passes": false,
      "completedAt": null,
      "learnings": []
    },
    {
      "id": "AUTH-002",
      "title": "Implement JWT token generation and login endpoint",
      "description": "Create POST /auth/login endpoint that returns JWT on valid credentials",
      "specialist": "Backend Dev",
      "priority": 2,
      "acceptanceCriteria": [
        "POST /auth/login accepts email and password in request body",
        "Returns JWT token on valid credentials (200 OK)",
        "Returns 401 with error message on invalid credentials",
        "JWT token includes user ID and email in payload",
        "Token expires in 24 hours (configurable via env var)",
        "Token signed with secure secret from environment",
        "Rate limiting: max 5 login attempts per minute per IP"
      ],
      "passes": false,
      "completedAt": null,
      "learnings": []
    },
    {
      "id": "AUTH-003",
      "title": "Create JWT verification middleware",
      "description": "Middleware to protect routes requiring authentication",
      "specialist": "Backend Dev",
      "priority": 3,
      "acceptanceCriteria": [
        "Middleware extracts token from Authorization header (Bearer format)",
        "Validates token signature and expiration",
        "Returns 401 if token missing, invalid, or expired",
        "Attaches decoded user data to request context",
        "Can be applied to any route requiring authentication"
      ],
      "passes": false,
      "completedAt": null,
      "learnings": []
    },
    {
      "id": "AUTH-004",
      "title": "Build React login form component",
      "description": "Login UI with email/password inputs and API integration",
      "specialist": "Frontend Dev",
      "priority": 4,
      "acceptanceCriteria": [
        "Email input with format validation (email regex)",
        "Password input with minimum 8 character requirement",
        "Submit button calls POST /auth/login with credentials",
        "Shows loading spinner during API request (button disabled)",
        "Displays error message below form on 401 response",
        "Clears password field on error",
        "Stores JWT token in localStorage on success",
        "Redirects to /dashboard on successful login",
        "Accessible: keyboard navigation works, proper ARIA labels"
      ],
      "passes": false,
      "completedAt": null,
      "learnings": []
    },
    {
      "id": "AUTH-005",
      "title": "Implement protected route wrapper",
      "description": "React component/HOC to protect authenticated routes",
      "specialist": "Frontend Dev",
      "priority": 5,
      "acceptanceCriteria": [
        "Checks for valid JWT token in localStorage",
        "Redirects to /login if no token present",
        "Validates token expiration client-side",
        "Clears expired tokens and redirects to /login",
        "Can wrap any component requiring authentication"
      ],
      "passes": false,
      "completedAt": null,
      "learnings": []
    },
    {
      "id": "AUTH-006",
      "title": "E2E authentication flow validation",
      "description": "Complete testing of login, protected routes, and logout",
      "specialist": "Validator",
      "priority": 6,
      "acceptanceCriteria": [
        "Can successfully login with valid credentials",
        "Invalid credentials show appropriate error message",
        "JWT token stored in localStorage after login",
        "Protected routes accessible with valid token",
        "Protected routes redirect to /login without token",
        "Logout clears token and redirects to /login",
        "Token expiration handled correctly (24hr test)",
        "Rate limiting prevents brute force attacks (test 6+ attempts)",
        "No console errors during happy path flow"
      ],
      "passes": false,
      "completedAt": null,
      "learnings": []
    }
  ]
}
```

---

## Analysis Checklist

When generating PRD from description, verify:

**Feature Understanding:**
- [ ] Core functionality clearly identified
- [ ] Technology stack determined (React, Next.js, API framework, etc.)
- [ ] External dependencies identified (Stripe, Auth0, etc.)
- [ ] Integration points mapped (existing systems, APIs)

**Task Decomposition:**
- [ ] Each task is context-window-sized
- [ ] Concerns properly separated (DB, API, UI, testing)
- [ ] Dependencies respected in priority ordering
- [ ] No task requires multiple specialists

**Specialist Assignment:**
- [ ] Backend tasks → Backend Dev
- [ ] Frontend tasks → Frontend Dev
- [ ] Mobile tasks → Mobile Dev
- [ ] Automation tasks → Automator
- [ ] Final validation → Validator

**Acceptance Criteria:**
- [ ] Specific and measurable
- [ ] Include edge cases
- [ ] Reference concrete behaviors
- [ ] All criteria are testable

**Metadata:**
- [ ] Branch name follows kebab-case convention
- [ ] Task IDs use consistent prefix
- [ ] maxIterations estimated appropriately
- [ ] Governance config uses standard settings

---

*Use this template to generate high-quality PRDs that enable autonomous feature development.*
