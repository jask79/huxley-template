# Skill Creation Protocol

## Authority: {{ORCHESTRATOR_NAME}}, BOSS, Claudeception Only

**skill-creator skill is restricted to:**
- **{{ORCHESTRATOR_NAME}}** - Orchestrator, evaluates patterns from specialist work
- **👔 BOSS** - Strategic oversight of Huxley skill library
- **Claudeception** - Extracts learnings and creates skills from patterns

**NOT available to specialist agents.** They focus on domain work, not meta-work.

---

## Why Centralized Control?

### 1. Prevents Skill Sprawl
- Not every pattern needs to be a skill
- {{ORCHESTRATOR_NAME}}/BOSS evaluate: "Is this reusable across multiple tasks/agents?"
- Quality threshold prevents one-off skills

### 2. Quality Control
- Consistent formatting and structure
- Proper frontmatter (name, description, triggers)
- Appropriate degrees of freedom
- Concise content (context window is a public good)

### 3. Strategic Curation
- Skills serve Huxley goals
- Aligned with system architecture
- Fill real gaps, not imagined ones

---

## Workflow: Pattern → Skill

### Step 1: Pattern Discovery
**Who:** Specialist agents doing their work
**What:** Recognize recurring patterns, successful approaches, anti-patterns

**Specialist Action:**
- Complete the task successfully
- Note if the pattern is novel or reusable
- Report to {{ORCHESTRATOR_NAME}} (via task completion message)

**Example:**
```
Backend Dev: "Successfully implemented OAuth2 with refresh token rotation.
This pattern could be valuable as a skill if we do auth frequently."
```

### Step 2: Pattern Evaluation
**Who:** {{ORCHESTRATOR_NAME}}
**What:** Evaluate if pattern warrants a skill

**Evaluation Criteria:**
- ✅ Reusable across multiple tasks or agents
- ✅ Non-obvious (not something Claude already knows)
- ✅ Procedural knowledge (step-by-step workflow)
- ✅ Reduces context needed in future tasks
- ❌ One-off implementation
- ❌ Trivial or obvious pattern
- ❌ Already covered by existing skill or Context7

**{{ORCHESTRATOR_NAME}} Decision:**
- If YES → Proceed to Step 3
- If NO → Store in agent memory instead (lower-priority learning)

### Step 3: Skill Creation
**Who:** {{ORCHESTRATOR_NAME}} (using skill-creator guidance)
**What:** Create the skill file

**Process:**
1. Reference `skill-creator/SKILL.md` for best practices
2. Create new skill directory in `.claude/skills/`
3. Write `skill.md` with:
   - Frontmatter (name, description, triggers)
   - Concise content (only what Claude doesn't know)
   - Appropriate freedom level (high/medium/low)
   - Examples if needed
4. Verify skill is discoverable

### Step 4: Integration
**Who:** {{ORCHESTRATOR_NAME}}
**What:** Make skill available and document

**Actions:**
- Skill auto-discovered by Claude Code
- Update documentation if needed
- Notify relevant agents (optional)

---

## Alternative: Claudeception-Driven

**Claudeception** can also create skills from its learning extraction process:

1. Claudeception reviews session learnings
2. Identifies patterns worth codifying
3. Creates skill using skill-creator guidance
4. Skill added to Huxley library

**Benefit:** Automated skill creation from actual work patterns

---

## Skill Quality Standards

### Frontmatter Required
```yaml
---
name: skill-name
description: Clear description including when to use (triggers)
allowed-tools: [list of tools if restricted]
---
```

### Content Principles
1. **Concise is key** - Context window is a public good
2. **Challenge each paragraph** - Does Claude really need this?
3. **Prefer examples over explanations** - Show, don't tell
4. **Appropriate freedom** - Match specificity to task fragility

### Degrees of Freedom

**High freedom (text instructions):**
- Multiple valid approaches
- Context-dependent decisions
- Heuristic guidance

**Medium freedom (pseudocode with parameters):**
- Preferred pattern exists
- Some variation acceptable
- Configuration affects behavior

**Low freedom (specific scripts):**
- Operations are fragile
- Consistency critical
- Specific sequence required

---

## Examples of Good vs Bad Skills

### ✅ GOOD: Worth Creating

**Pattern:** "OAuth2 refresh token rotation with Supabase RLS integration"
- ✅ Non-obvious (specific integration pattern)
- ✅ Reusable (any auth implementation)
- ✅ Procedural (step-by-step workflow)
- ✅ Saves context (avoids re-explaining pattern each time)

**Pattern:** "N8N workflow validation before deployment"
- ✅ Prevents errors (fragile operations)
- ✅ Reusable (every N8N workflow)
- ✅ Specific checklist (low freedom appropriate)

### ❌ BAD: Don't Create

**Pattern:** "How to write a for loop in Python"
- ❌ Trivial (Claude already knows this)
- ❌ Not Huxley-specific

**Pattern:** "Fixed typo in README for Project X"
- ❌ One-off (not reusable)
- ❌ No procedural value

**Pattern:** "General React best practices"
- ❌ Already covered by `react-best-practices` community skill
- ❌ Would duplicate existing knowledge

---

## Maintenance

### Skill Deprecation
If a skill becomes obsolete or unused:
1. Mark as deprecated in frontmatter
2. Document replacement (if any)
3. Keep for 30 days
4. Remove if confirmed unused

### Skill Updates
When patterns evolve:
1. {{ORCHESTRATOR_NAME}} or BOSS updates skill content
2. Increment version if frontmatter supports it
3. Document changes

---

## Summary

**Who creates skills:**
- {{ORCHESTRATOR_NAME}} (primary)
- BOSS (strategic oversight)
- Claudeception (automated from learnings)

**Who discovers patterns:**
- All specialist agents (report to {{ORCHESTRATOR_NAME}})

**Why centralized:**
- Quality control
- Strategic curation
- Prevents skill sprawl

**How to create:**
- Reference skill-creator/SKILL.md
- Follow quality standards
- Apply appropriate freedom level
- Keep concise

---

*This protocol ensures Huxley skills remain high-quality, strategically valuable, and well-curated.*
