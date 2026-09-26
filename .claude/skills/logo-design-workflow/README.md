# Strategic Logo Design Workflow

## Overview

A multi-agent skill system for strategic logo design following the **Double Diamond methodology**. Unlike one-shot logo generation, this workflow ensures proper graphic design methodology with discovery, exploration, iteration, and refinement phases.

## The Gap This Fills

Most AI logo tools generate everything in one pass. Professional logo design follows a structured process:

| Phase | Double Diamond | Agent | Skill |
|-------|---------------|-------|-------|
| **Discover** | Divergent research | Brand Specialist | `brand-discovery` |
| **Define** | Convergent positioning | Brand Specialist | `brand-discovery` |
| **Develop** | Divergent exploration | Graphic Designer | `visual-exploration` |
| **Deliver** | Convergent refinement | UI Designer + Graphic Designer | `brand-delivery` |

## Workflow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    STRATEGIC LOGO DESIGN                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PHASE 1: DISCOVER + DEFINE (Brand Specialist)                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • Discovery brief intake                                 │   │
│  │ • Competitive landscape analysis                         │   │
│  │ • Brand positioning definition                           │   │
│  │ • Creative direction moodboard                           │   │
│  │ • Checkpoint: Strategic Foundation Approval              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓                                  │
│  PHASE 2: DEVELOP (Graphic Designer)                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • Visual concept generation (3-5 directions)             │   │
│  │ • Typography exploration                                 │   │
│  │ • Symbol/mark sketching                                  │   │
│  │ • Color palette development                              │   │
│  │ • Iterative refinement (2-3 rounds)                      │   │
│  │ • Checkpoint: Visual Direction Approval                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓                                  │
│  PHASE 3: DELIVER (UI Designer + Graphic Designer)              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • Final mark refinement                                  │   │
│  │ • Logo system creation (lockups, variants)               │   │
│  │ • Design token generation                                │   │
│  │ • Brand DNA integration                                  │   │
│  │ • Usage guidelines                                       │   │
│  │ • Checkpoint: Final Brand Mark Approval                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Skills in This Workflow

### 1. `brand-discovery` (Brand Specialist)
**Phases:** Discover + Define
- Discovery brief creation
- Competitor analysis
- Brand archetype identification
- Positioning statement
- Creative direction moodboard
- Deliverable: `discovery-brief.md` + `creative-direction.md`

### 2. `visual-exploration` (Graphic Designer)
**Phase:** Develop
- Receives creative direction from Brand Specialist
- Generates 3-5 distinct visual concepts
- Typography + symbol + color exploration
- Iterative refinement with feedback loops
- Deliverable: Concept presentations with rationale

### 3. `brand-delivery` (UI Designer + Graphic Designer)
**Phase:** Deliver
- Final mark selection and polish
- Logo system (horizontal, vertical, icon, monochrome)
- Design token extraction (colors, typography)
- Brand DNA JSON generation
- Usage guidelines documentation
- Deliverable: Complete brand mark system

## Invocation

### Full Workflow ({{ORCHESTRATOR_NAME}} Orchestration)
```
"Design a strategic logo for [project]"
→ {{ORCHESTRATOR_NAME}} coordinates all three phases with checkpoints
```

### Phase-Specific Invocation
```
"Run brand discovery for [project]"
→ Brand Specialist executes discovery skill

"Explore visual concepts based on the discovery brief"
→ Graphic Designer executes visual-exploration skill

"Finalize the logo system and integrate with brand DNA"
→ UI Designer + Graphic Designer execute brand-delivery skill
```

## Checkpoint Gates

Each phase has an approval checkpoint before proceeding:

1. **Strategic Foundation Approval** - Confirm positioning and direction before visual work
2. **Visual Direction Approval** - Select concept(s) to refine before delivery
3. **Final Brand Mark Approval** - Sign off on complete logo system

These gates prevent wasted iteration and ensure alignment at each stage.

## Integration with Brand Specialist

The Brand Specialist agent already maintains `brand-dna.json` and conducts brand audits. This workflow:
- **Inputs from Brand Specialist:** Existing brand DNA (if evolving), capsule context
- **Outputs to Brand Specialist:** New/updated brand DNA, logo assets for brand library

## Methodology References

This workflow incorporates best practices from:
- **Double Diamond** (British Design Council) - Divergent/convergent thinking phases
- **Brand Archetypes** (Jung/Mark & Pearson) - Personality positioning
- **Design Thinking** (IDEO) - Human-centered iteration
- **Anthropic's Design Elevation** - Quality gates and iterative self-critique

## File Structure

```
.claude/skills/logo-design-workflow/
├── README.md                    # This file
├── brand-discovery.md           # Brand Specialist skill
├── visual-exploration.md        # Graphic Designer skill
└── brand-delivery.md            # UI Designer + Graphic Designer skill
```
