---
name: persona-panel
description: Query synthetic customer personas for product gut-checks and validation
---

# Persona Panel

Quick validation of product ideas, features, and pricing against synthetic customer profiles representing your own target markets.

## When to Use
- Before building a new capsule ("Would anyone actually buy this?")
- When evaluating pricing ("What would [persona] pay?")
- When planning features ("What would [persona] need most?")
- When choosing marketing channels ("How would [persona] find this?")

## Activation
- "Gut-check [idea] against the persona panel"
- "Would [persona name] buy this?"
- "Run persona validation on [capsule/product]"

## Behavior
1. Load `global/config/persona-panel.json`
2. Identify relevant personas by `relevantCapsules` match or archetype fit
3. For each relevant persona, evaluate:
   - **Desire** (1-10): Would they want this?
   - **Willingness to pay**: Based on their spending profile
   - **Discovery**: How would they find this product?
   - **Retention risk**: What would make them churn or stop using it?
   - **Validation questions**: Answer the persona's built-in gut-check questions
4. Output a summary table with go/no-go signal per persona
5. Flag any persona that reveals a dealbreaker (e.g., "this persona's willingness to pay is below your cost to serve")

## Notes
- Personas are synthetic composites, not real customers — use for directional gut-checks, not as gospel
- The shipped example panel has two personas; add your own categories and profiles to `global/config/persona-panel.json`
- Update personas when capsule portfolio changes — {{ORCHESTRATOR_NAME}} will prompt for this
