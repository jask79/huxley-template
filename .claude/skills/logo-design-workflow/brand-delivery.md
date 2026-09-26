# Brand Delivery Skill

**Agents:** 📐 UI Designer (lead) + 🎨 Graphic Designer (support)
**Phase:** Deliver (Double Diamond)
**Purpose:** Finalize logo system and integrate with design infrastructure

---

## Skill Overview

This skill guides the convergent delivery phase of logo design. Working from the Graphic Designer's approved visual direction, create a complete logo system ready for production use and integrated with Huxley brand infrastructure.

**This phase transforms a concept into a system:**
- Single logo → Complete logo family
- Visual direction → Design tokens
- Approved concept → Brand DNA integration
- Design files → Usage guidelines

---

## Prerequisites

Before beginning brand delivery, confirm you have:

- [ ] Approved visual direction from Graphic Designer
- [ ] Complete design specifications (typography, colors, forms)
- [ ] Strategic foundation documents (archetype, positioning)
- [ ] Stakeholder approval on visual direction
- [ ] Clear delivery requirements (platforms, applications)

**If any of these are missing, request them before starting delivery work.**

---

## Phase: DELIVER (Convergent Finalization)

### Stage 1: Final Mark Refinement

**Polish the approved concept to production quality.**

#### Refinement Checklist

```markdown
## Final Mark Refinement

### Typography Polish
- [ ] Letterform spacing optimized (tracking/kerning)
- [ ] Optical adjustments made (visual vs. mathematical centering)
- [ ] Custom modifications documented
- [ ] Font licensing verified

### Shape Polish
- [ ] Vector paths clean and optimized
- [ ] Anchor points minimized
- [ ] Curves smooth and intentional
- [ ] Grid alignment verified

### Color Polish
- [ ] Primary palette finalized
- [ ] Color values verified across color spaces (hex, RGB, HSL, CMYK)
- [ ] Accessibility contrast ratios checked
- [ ] Color reproduction tested (print simulation)

### Balance & Proportion
- [ ] Visual weight balanced
- [ ] Negative space intentional
- [ ] Optical illusions corrected
- [ ] Scale relationships defined
```

### Stage 2: Logo System Creation

**Build the complete logo family.**

#### Logo Lockups

```markdown
## Logo System: [Brand Name]

### Primary Lockup
- **Use case:** Default logo for most applications
- **Orientation:** [horizontal/stacked]
- **Components:** [symbol + wordmark / wordmark only / etc.]
[Image]

### Secondary Lockup
- **Use case:** Alternative orientation for space constraints
- **Orientation:** [vertical/horizontal]
[Image]

### Symbol Only
- **Use case:** Favicon, app icon, small applications
- **Minimum size:** [Xpx]
- **Clear space:** [X times symbol height]
[Image]

### Wordmark Only
- **Use case:** When symbol recognition not needed
- **Minimum size:** [Xpx]
[Image]
```

#### Logo Variants

```markdown
## Logo Variants

### Color Versions
| Version | Primary | Secondary | Background |
|---------|---------|-----------|------------|
| Full Color | [hex] | [hex] | Light |
| Full Color (Dark BG) | [hex] | [hex] | Dark |
| Monochrome | [hex] | - | Light |
| Monochrome (Dark BG) | [hex] | - | Dark |
| Single Color | Black | - | Light |
| Single Color Reversed | White | - | Dark |

### Application Versions
- **Digital:** RGB color space, 72-150 DPI
- **Print:** CMYK color space, 300 DPI minimum
- **Merchandise:** Pantone spot colors specified

### Size Variants
- **Favicon:** 16x16, 32x32 (simplified if needed)
- **App Icon:** 1024x1024 (iOS/Android)
- **Social:** Profile sizes per platform
- **Large Format:** Vector for unlimited scaling
```

#### Clear Space & Sizing

```markdown
## Logo Specifications

### Clear Space
Minimum clear space around logo = [X] (where X = [reference unit])

┌─────────────────────────┐
│          X              │
│    ┌───────────┐        │
│ X  │   LOGO    │  X     │
│    └───────────┘        │
│          X              │
└─────────────────────────┘

### Minimum Sizes
| Application | Minimum Width | Minimum Height |
|-------------|---------------|----------------|
| Digital (primary) | Xpx | Xpx |
| Digital (symbol only) | Xpx | Xpx |
| Print (primary) | Xmm | Xmm |
| Print (symbol only) | Xmm | Xmm |
```

### Stage 3: Design Token Generation

**Extract design system tokens from brand mark.**

#### Color Tokens

```json
{
  "brand": {
    "colors": {
      "primary": {
        "value": "#XXXXXX",
        "description": "Primary brand color from logo"
      },
      "secondary": {
        "value": "#XXXXXX",
        "description": "Secondary brand color"
      },
      "accent": {
        "value": "#XXXXXX",
        "description": "Accent color for emphasis"
      }
    },
    "backgrounds": {
      "light": {
        "value": "#XXXXXX",
        "description": "Light background for dark logo"
      },
      "dark": {
        "value": "#XXXXXX",
        "description": "Dark background for light logo"
      }
    }
  }
}
```

#### Typography Tokens

```json
{
  "brand": {
    "typography": {
      "logo": {
        "family": "Font Name",
        "weight": 600,
        "letterSpacing": "0.02em",
        "description": "Typography used in logo wordmark"
      },
      "headings": {
        "family": "Font Name",
        "weights": [600, 700],
        "description": "Heading typography derived from brand"
      },
      "body": {
        "family": "Font Name",
        "weights": [400, 500],
        "description": "Body typography complementing brand"
      }
    }
  }
}
```

### Stage 4: Brand DNA Integration

**Update Huxley brand infrastructure.**

#### Brand DNA Update

```json
{
  "version": "X.X.X",
  "brand": {
    "name": "[Brand Name]",
    "tagline": "[Tagline]"
  },
  "logo": {
    "primary": "/assets/logo/primary.svg",
    "symbol": "/assets/logo/symbol.svg",
    "wordmark": "/assets/logo/wordmark.svg",
    "variants": {
      "dark": "/assets/logo/primary-dark.svg",
      "monochrome": "/assets/logo/primary-mono.svg"
    },
    "favicon": "/assets/logo/favicon.svg",
    "appIcon": "/assets/logo/app-icon.png"
  },
  "colors": {
    "primary": "#XXXXXX",
    "secondary": "#XXXXXX",
    "accent": "#XXXXXX",
    "neutral": {
      "50": "#XXXXXX",
      "100": "#XXXXXX",
      "900": "#XXXXXX"
    }
  },
  "typography": {
    "headings": {
      "family": "Font Name",
      "weights": [600, 700]
    },
    "body": {
      "family": "Font Name",
      "weights": [400, 500]
    }
  },
  "voice": {
    "adjectives": ["[adj1]", "[adj2]", "[adj3]"],
    "tone": "[Tone description]"
  }
}
```

### Stage 5: Usage Guidelines

**Document proper and improper usage.**

#### Do's and Don'ts

```markdown
## Logo Usage Guidelines

### Correct Usage
- Use provided logo files (don't recreate)
- Maintain minimum clear space
- Use approved color variants
- Scale proportionally
- Place on appropriate backgrounds

### Incorrect Usage
- [ ] Don't stretch or distort
- [ ] Don't rotate
- [ ] Don't change colors outside approved variants
- [ ] Don't add effects (shadows, gradients, etc.)
- [ ] Don't place on busy backgrounds
- [ ] Don't crop or mask parts of the logo
- [ ] Don't outline or stroke the logo
- [ ] Don't rearrange logo elements

### Background Guidelines
| Logo Version | Acceptable Backgrounds |
|--------------|----------------------|
| Full Color | White, light neutrals |
| Dark Mode | Dark neutrals, black |
| Monochrome | Solid colors with contrast |

### Co-Branding Rules
- Logo must be equal or larger size than partner logos
- Minimum separation of [X] between logos
- Use monochrome version when multiple logos present
```

---

## Checkpoint: Final Brand Mark Approval

**Before finalizing delivery, confirm:**

- [ ] All logo lockups approved
- [ ] All variants reviewed and approved
- [ ] Specifications documented
- [ ] Design tokens verified
- [ ] Brand DNA integration tested
- [ ] Usage guidelines complete
- [ ] Stakeholder final sign-off

**Approval Required:** Final stakeholder approval before assets are considered production-ready

---

## Deliverables

### 1. Logo Assets
```
/branding/[project]/assets/
├── logo/
│   ├── primary.svg
│   ├── primary.png (various sizes)
│   ├── primary-dark.svg
│   ├── symbol.svg
│   ├── symbol.png (various sizes)
│   ├── wordmark.svg
│   ├── monochrome.svg
│   └── favicon.svg
├── icons/
│   ├── app-icon-ios.png (1024x1024)
│   ├── app-icon-android.png
│   └── favicon-set/ (16, 32, 180, etc.)
└── social/
    ├── profile-facebook.png
    ├── profile-twitter.png
    ├── profile-linkedin.png
    └── cover-images/
```

### 2. Design Tokens
```
/branding/[project]/tokens/
├── colors.json
├── typography.json
├── spacing.json
└── brand-tokens.css (CSS variables)
```

### 3. Brand DNA
```
/branding/[project]/brand-dna.json
```
(Or update to global brand DNA if this is the primary brand)

### 4. Usage Guidelines
```
/branding/[project]/guidelines/
├── logo-usage.md
├── color-usage.md
├── typography-usage.md
└── examples/
    ├── correct-usage.png
    └── incorrect-usage.png
```

### 5. Implementation Reference
```
/branding/[project]/implementation/
├── tailwind-config-snippet.js
├── css-variables.css
├── figma-tokens.json (for Figma sync)
└── readme.md
```

---

## Handoff to Brand Specialist

**Final delivery to 🎯 Brand Specialist for brand governance:**

```markdown
## Brand Delivery Complete

### Delivered Assets
- Logo system: [X] lockups, [X] variants
- Design tokens: Colors, typography, spacing
- Brand DNA: Updated/created at [path]
- Guidelines: Usage documentation complete

### Integration Status
- [ ] Brand DNA integrated with Huxley design system
- [ ] Tokens exported for Tailwind/CSS/Figma
- [ ] Assets added to brand library
- [ ] Guidelines added to documentation

### Capsule Inheritance
- [ ] New brand DNA can be inherited by capsules
- [ ] Override patterns documented
- [ ] Migration guide provided (if updating existing brand)

### Maintenance Notes
- [Any special considerations for brand maintenance]
- [Version control recommendations]
- [Scheduled review cadence]
```

---

## Quality Gates

### Refinement Quality
- [ ] Typography optically adjusted, not just mathematically
- [ ] Vector paths clean and optimized
- [ ] Color values consistent across color spaces
- [ ] All refinements documented

### System Quality
- [ ] Complete logo family (all lockups and variants)
- [ ] Consistent sizing and clear space rules
- [ ] All file formats provided
- [ ] Technical requirements met

### Integration Quality
- [ ] Design tokens accurate and complete
- [ ] Brand DNA properly structured
- [ ] Capsule inheritance working
- [ ] Implementation references tested

### Documentation Quality
- [ ] Usage guidelines clear and comprehensive
- [ ] Do's and don'ts with visual examples
- [ ] Technical specs for developers
- [ ] Accessible to non-designers

---

## Collaboration: UI Designer + Graphic Designer

### UI Designer Leads
- Design token generation
- Brand DNA integration
- Implementation references
- Design system connection

### Graphic Designer Supports
- Final mark polish
- Asset export (all formats)
- Visual examples for guidelines
- Quality review of all variants

### Coordination Points
1. **Token Review:** Graphic Designer verifies colors match intent
2. **Asset Handoff:** Graphic Designer provides files, UI Designer integrates
3. **Guidelines Co-Creation:** Both contribute to usage documentation
4. **Final QA:** Both review complete delivery package

---

## Anti-Patterns to Avoid

**Refinement:**
- Skipping optical adjustments
- Not testing at actual use sizes
- Ignoring accessibility requirements
- Over-engineering for edge cases

**System Creation:**
- Missing critical variants
- Inconsistent naming conventions
- Incomplete file format coverage
- Undocumented decisions

**Integration:**
- Token values that don't match visual
- Brand DNA that doesn't validate
- Missing implementation references
- Broken capsule inheritance

**Documentation:**
- Guidelines nobody can follow
- Missing visual examples
- Technical-only (no context)
- Incomplete don'ts list

---

*This skill ensures the approved visual direction becomes a complete, production-ready brand system integrated with Huxley infrastructure. The UI Designer leads integration while the Graphic Designer ensures visual quality.*
