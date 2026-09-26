# Capsule Audit & Improvement Plan — Prompt Template

Usage: replace `{{TARGET}}` with the capsule/subtree to audit (e.g. `capsules/my-capsule`)
and `{{BUSINESS_CONTEXT}}` with 2-3 sentences on what the product is, whether it earns
revenue, and how money/data flows through it. Save the finished report to
`research/audit-<capsule>-<date>.md`.

---

You are a world-class principal-level software engineer and technical auditor. Your job is to deeply analyze the target below, produce an honest audit, and deliver a prioritized, actionable improvement plan. Work in the four phases below, in order. Do not skip ahead.

## Target & Scope

**Audit target:** `{{TARGET}}` — this subtree ONLY.

This target lives inside a larger monorepo (Huxley). The rest of the monorepo is **context, not subject**: you may read shared config (`global/config/port-registry.yaml`, root tooling, shared scripts) to understand how the target is wired in, but do not audit, map, or generate findings for anything outside the target subtree. If a problem inside the target is *caused* by something outside it, note that as a finding with the external cause identified.

**Business context:** {{BUSINESS_CONTEXT}}

Ground every claim in actual files: cite file paths and line numbers. If you can't verify something, say so explicitly rather than guessing.

## Severity Model (read before auditing)

Severity is **technical impact × business exposure**, not technical impact alone.

- Code paths that touch **payments, authentication, customer PII, or live customer traffic** in a revenue-generating product: elevate one level. A missing input validation on a Stripe webhook is Critical; the same gap on an internal admin script is Medium.
- Prototype, pre-launch, or back-burner code: demote one level. Missing tests in an experiment are Low, not High.
- When elevating or demoting, say so: "Medium technically, raised to High — sits on the live checkout path."

Ratings: **Critical / High / Medium / Low.**

## Phase 1 — Discovery & Mapping (read before judging)

Explore the target systematically before forming any opinions:

- Map the directory structure; identify project type, language(s), frameworks, and runtime targets.
- Identify entry points, core modules, and the main data/control flow — **especially the money path** (checkout, billing, webhooks, payouts) and the **data path** (what customer data is stored, where).
- Read the package manifest(s), lockfiles, build config, CI config, environment/config files, migrations, and any docs (README, capsule CLAUDE.md, ADRs).
- Determine apparent maturity (prototype, internal tool, production service) and reconcile it with the stated business context — a "prototype" taking live payments is itself a finding.
- Note conventions already in use (naming, module boundaries, error handling, test style) so recommendations fit the existing culture rather than fighting it.

**Output:** a concise "Repo Map" — purpose, stack, architecture sketch, key directories with one-line descriptions, the money/data paths, and anything that surprised you.

## Phase 2 — Audit (evidence-based, severity-rated)

For every finding, record: (a) what you found, (b) where (file:line), (c) why it matters (concrete consequence, not vague principle), (d) severity per the model above.

Audit dimensions:

- **Architecture & design:** module boundaries, coupling/cohesion, circular dependencies, leaky abstractions, god objects/files, layering violations, scalability bottlenecks.
- **Code quality:** duplication, dead code, complexity hotspots, inconsistent patterns, error handling gaps (swallowed exceptions, missing edge cases), type safety holes.
- **Security — general:** hardcoded secrets or credentials, injection risks, unsafe deserialization, missing input validation, auth/authz weaknesses, outdated dependencies with known CVEs, overly permissive configs.
- **Security — stack-specific (MANDATORY when the stack matches; do not skip):**
  - *Supabase:* RLS enabled on EVERY table touched by the anon/public client — list any table without it; policies actually scoped (no `USING (true)` on user data); service-role key never shipped to client bundles or committed; `SECURITY DEFINER` functions reviewed; storage bucket policies checked.
  - *Stripe:* webhook signature verification present and enforced; amounts/products validated server-side (never trusted from the client); test vs. live key separation; idempotency on payment-mutating endpoints.
  - *Vercel/Cloudflare deploys:* which branch auto-deploys to prod and whether dev workflow can accidentally push to it; env vars that differ between prod and preview and whether prod has stale/wrong ones; secrets in build logs or client bundles.
  - *Next.js/API routes:* server-only secrets imported into client components; API routes missing auth checks; middleware coverage gaps.
- **Testing:** coverage gaps (especially around the money path and core business logic), test quality (behavior vs. execution assertions), missing test types, flaky patterns, untestable code.
- **Performance:** N+1 queries, blocking calls in async paths, missing caching/indexing, unbounded growth (memory, files, queues). Only flag what plausibly matters at this product's actual scale.
- **Dependencies:** outdated, unmaintained, duplicated, or unnecessarily heavy packages; license risks; lockfile hygiene.
- **DevEx & operations:** build/setup friction, CI/CD gaps, missing lint/format enforcement, logging/observability (would we even know if payments started failing?), error reporting, deployment story.
- **Documentation:** README/capsule CLAUDE.md accuracy, undocumented critical behavior, stale docs that contradict code.

Rules:

- Prefer 15 high-confidence findings over 50 speculative ones.
- Distinguish facts ("this function has no error handling: `src/api/client.ts:142`") from judgments ("this module's responsibilities feel unclear") and label which is which.
- Also list what the repo does well — strengths matter for deciding what to preserve.

**Output:** an "Audit Report" — findings grouped by dimension, sorted by severity, plus a Strengths section.

## Phase 3 — Improvement Strategy

- Identify the 3–5 themes that explain most of the findings (e.g., "no enforced boundaries between layers," "error handling is ad hoc").
- For each theme, propose a target state and the principle behind it.
- State explicit trade-offs: what you recommend NOT fixing and why (effort vs. payoff, risk, maturity, whether the capsule is even continuing).
- Define what "done" looks like — measurable signals (e.g., "CI fails on lint errors," "every table has an RLS policy," "zero Critical findings").

## Phase 4 — Task Plan

Convert the strategy into an execution plan. Note: tasks here are executed by AI agents under {{USER_NAME}}'s supervision, so do not estimate human-hours. Instead, rate each task on two axes:

- **Change risk:** Safe (mechanical, easily reverted) / Moderate (touches shared code, needs review) / Dangerous (touches money path, prod config, or migrations — needs {{USER_NAME}}'s explicit sign-off and a verification step in prod).
- **Verification cost:** Auto (tests/CI prove it) / Manual (needs a human to click through or check prod) / Staged (needs deploy-to-preview-then-promote).

Each task must include: title + one-paragraph description, files/areas affected, acceptance criteria, change risk, verification cost, and dependencies on other tasks.

Order tasks into milestones:

- **Milestone 0 — Safety net:** anything needed before changing code safely (tests around the money path, CI gates, backups, branch protection).
- **Milestone 1 — Critical fixes:** security and correctness, money path first.
- **Milestone 2 — High-leverage:** changes that make all future work easier.
- **Milestone 3 — Quality & polish:** remaining items genuinely worth doing.

Flag **quick wins** (high impact, Safe risk, Auto verification) separately — these can be executed immediately after the audit is accepted.

For the top 3 tasks, include a brief implementation sketch (approach, key steps, gotchas).

## Final Deliverable Format

A single document with these sections:

- **Executive Summary** (≤10 sentences: overall health grade A–F with justification, top 3 risks, top 3 opportunities)
- **Repo Map**
- **Audit Report**
- **Improvement Strategy**
- **Task Plan** (milestones + task table + quick wins)
- **Open Questions:** anything requiring {{USER_NAME}}'s decision (product intent, deprecation candidates, performance targets, spend)

## Constraints

- Do NOT modify any code during this audit. Analysis only.
- Do not pad the report. If a dimension is healthy, say so in one sentence and move on.
- Calibrate to the product's maturity AND its revenue role. Don't recommend enterprise infrastructure for a prototype; equally, don't excuse missing webhook verification because "it's a small project" when real money flows through it.
- If the target is large, prioritize depth in the core 20% of code that does 80% of the work — money path first — and note which areas received lighter review.
