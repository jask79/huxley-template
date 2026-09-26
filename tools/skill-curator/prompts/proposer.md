You are drafting a candidate Huxley skill from a successful Claude Code session.

A "skill" in Huxley is a reusable workflow saved as a single SKILL.md file in agentskills.io format. Skills get loaded by {{ORCHESTRATOR_NAME}} ({{USER_NAME}}'s primary AI assistant) when their trigger conditions match the user's request.

# Your Job

Given the session below, write a draft `SKILL.md` if and only if the workflow is genuinely worth saving. The session was already filtered by a heuristic (≥ 8 tool calls, ≥ 3 distinct tool types, success signal present, not a duplicate of an existing skill). Your job is the *content* — turn the trajectory into a clean, reusable skill spec.

# Output Format (STRICT)

Output ONLY the contents of SKILL.md, no commentary. The file MUST start with YAML frontmatter:

```
---
name: <kebab-case-slug>
description: <one-line description, ≤ 200 chars, starts with an action verb when possible>
when: <one-line trigger description — when should {{ORCHESTRATOR_NAME}} activate this skill>
allowed-tools:
  - <tool name>
  - <tool name>
metadata:
  version: "1.0.0"
  privacy: "normal"
proposed_at: "{{PROPOSED_AT}}"
source_session: "{{SOURCE_SESSION}}"
proposer_version: "1.0"
---

# <Human-readable title>

## Purpose
<1-2 sentences on what this skill does and why it exists>

## Trigger Conditions
- <when user says X>
- <when user does Y>
- <other situations where this skill should fire>

## Workflow
<numbered steps reproducing the successful trajectory, generalized so it works for similar future requests — not a transcript of this specific session>

## Notes
- <anything subtle the agent learned during the session that future invocations should know>
```

# Quality Bar

- The skill must be **generalizable** — not a one-off. If this is a unique-to-this-session task, output exactly the string `SKIP: not reusable` and nothing else.
- Name should be ≤ 30 characters, kebab-case, descriptive.
- Description should be specific enough that {{ORCHESTRATOR_NAME}} knows when to fire it, not vague like "helps with stuff".
- Workflow should be 3-8 numbered steps. If you need more than 8, the skill is too broad — narrow it.
- Do not invent tool calls that weren't in the trajectory. Stay grounded in what actually happened.
- Body must be at least 200 characters of substantive content (not counting frontmatter).

# The Session

**Final user message:**
{{FINAL_USER_MESSAGE}}

**Tool sequence (in order):**
{{TOOL_SEQUENCE}}

**Outcome signal:** {{OUTCOME_SIGNAL}}

Now write the SKILL.md draft (or `SKIP: not reusable` if it doesn't generalize).
