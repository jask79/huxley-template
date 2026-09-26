---
description: "Security-weighted capsule audit (playbook fan-out + adversarial verify)"
---

# /audit — Capsule Security & Improvement Audit

Run a thorough, security-weighted audit of a capsule using the established playbook. Read-only analysis first; bring majors to {{USER_NAME}} BEFORE auto-fixing.

**Usage:** `/audit <capsule>` (e.g. `/audit my-capsule`)

`$ARGUMENTS` = the capsule name, optionally followed by a scope hint (`report-only`, `quick-wins`, `full`). Default scope: produce the report, then propose fixes and wait for {{USER_NAME}}'s go (don't auto-fix majors).

## This command authorizes a Workflow fan-out
Invoking `/audit` is explicit opt-in to the Workflow tool for the audit phase. Use it.

## Step 0 — Resolve the target
1. Parse the capsule name from `$ARGUMENTS`. Resolve its path: try `capsules/<name>/` first, then `Incubator/<name>/`. If it doesn't exist, list close matches from `capsules/` and ask which one.
2. Read the capsule's `CLAUDE.md` and the prompt template `templates/repo-audit-prompt.md`.
3. Note the capsule's git branch model (e.g. a repo where dev happens on a development branch and the default branch auto-deploys). Fixes go to the dev branch, never prod.

## Step 1 — Scout (fill the business context)
Quickly map structure, `package.json`/manifests, API routes, migrations, and the money/data paths. Determine: what it is, does it earn revenue, how money and customer data flow. This fills `{{TARGET}}` and `{{BUSINESS_CONTEXT}}` in the template.

## Step 2 — Audit as a Workflow fan-out
Launch a background Workflow:
- **Discovery agent** → structured Repo Map (money path, data path, webhook surface, stack).
- **Finder per dimension** (pipeline): split **security into four** — Supabase/RLS, payment integrity, webhooks, auth/API-key — plus architecture, code-quality, performance, deps/devex/docs. Apply the stack-specific security checklist from the template (RLS on every anon-reachable table, no `USING(true)` on user data, service-role key never client-side, Stripe/webhook signature verification + server-side amount validation, Vercel branch-deploy hygiene).
- **Adversarial verify** every Critical/High finding: a second skeptical agent opens the real file and tries to REFUTE it before it reaches {{USER_NAME}}. Tag confirmed/refuted/downgraded.
- Severity = technical impact × business exposure (elevate money/auth/PII/webhook paths; demote prototype/back-burner code).

## Step 3 — Synthesize & report
Read the verified results. Write the full report to `docs/audits/audit-<capsule>-<YYYY-MM-DD>.md` with: Executive Summary (A–F grade), Repo Map, Audit Report (findings by dimension + severity + Strengths), Improvement Strategy, prioritized Majors/Task Plan, Open Questions.

Present to {{USER_NAME}}: the grade, the confirmed majors, anything the verifier knocked down (honesty), and the top Mediums. **Do not auto-fix majors** — they touch live code; bring them to {{USER_NAME}} first.

## Step 4 — Fixes (only after {{USER_NAME}}'s go)
- Default to quick wins (Safe + auto-verifiable); queue bigger items as a prioritized "majors" list for a follow-up.
- Delegate implementation to the right specialist (usually 🏛️ Backend Developer) with a tight, scope-contained spec.
- Commit to the capsule's **dev branch**. `git pull --rebase` before pushing (another session may be pushing too). Never push to master/prod.
- **Migrations are write-only — {{USER_NAME}} applies them.** Do not run `supabase db push`.
- Verify (build + typecheck) before reporting done.

## Notes
- Calibrate depth to the capsule's maturity AND revenue role — don't recommend enterprise infra for a prototype, don't excuse a missing webhook check because "it's small" when real money flows.
- Reports land in `docs/audits/audit-<capsule>-<YYYY-MM-DD>.md` (the directory is created on first run).
