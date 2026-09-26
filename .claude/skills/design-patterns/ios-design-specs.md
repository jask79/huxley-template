# iOS Design Specifications

Reference patterns for iOS app design - animations, gestures, navigation, and materials.

## Quick Reference

**External Documentation (Primary Sources):**
- Animation Patterns: `{{CATALYST_ROOT}}/global/docs/iOS_Animation_Patterns.md`
- Touch Interactions: `{{CATALYST_ROOT}}/global/docs/iOS_Touch_Interaction_Patterns.md`
- Navigation Architecture: `{{CATALYST_ROOT}}/global/docs/iOS_Navigation_Architecture.md`

---

## iOS Translucent Material Specifications

### Card with Background Material
- **Material**: UIBlurEffect with .systemMaterial style
- **Background**: .secondarySystemBackground or .tertiarySystemBackground
- **Corner Radius**: 12pt (standard), 16pt (large cards)
- **Padding**: 16pt (standard), 20pt (spacious)
- **Shadow**: system shadow with 0.15 opacity, 8pt blur, 2pt offset

### Typography Specifications
- **Dynamic Type Styles**: largeTitle, title1, title2, title3, headline, body, callout, subheadline, footnote, caption1, caption2
- **Weights**: Regular, Medium, Semibold, Bold (context-dependent)
- **Colors**: Use semantic colors (label, secondaryLabel, tertiaryLabel)
- **Minimum Contrast**: 4.5:1 for body text, 3:1 for large text (18pt+)

### Color System (Semantic Colors)
- **Labels**: label, secondaryLabel, tertiaryLabel, quaternaryLabel
- **Backgrounds**: systemBackground, secondarySystemBackground, tertiarySystemBackground
- **Fills**: systemFill, secondarySystemFill, tertiarySystemFill, quaternarySystemFill
- **Tint**: Use accent color (app-specific, user-customizable in Settings)
- **System Colors**: systemBlue, systemGreen, systemRed, systemOrange, etc. (adapt to modes)

### Motion & Interaction Defaults
- **Button Press**: Scale 0.95, 100ms spring animation
- **Sheet Presentation**: Modal slide up with dimmed background (300ms ease-out)
- **Navigation Transition**: Horizontal slide with fade (350ms ease-in-out)
- **Accessibility**: If reduce-motion enabled, use fade transitions instead of scale/slide

---

## Animation Specification Template

```markdown
## [Feature Name] Animation Specifications

### [Element] Animation

**Animation Type:** [Fade | Scale | Slide | Rotate | Spring | Custom]

**Timing:**
- Duration: [value in seconds, e.g., 0.3s]
- Easing: [Spring | Linear | Ease-in | Ease-out | Ease-in-out]
- Delay: [value in seconds, if applicable]

**Spring Parameters (if using spring):**
- Response: [0.3-0.6 typical]
- Damping Fraction: [0.5-1.0]
- Preset: [Snappy | Smooth | Bouncy | Gentle]

**From/To Values:**
- From: [initial state]
- To: [final state]

**Trigger:** [On appear | On tap | On scroll | On state change]

**Accessibility:**
- Reduce Motion Alternative: [Specify fade-only or instant transition]
```

---

## Gesture Specification Template

```markdown
## [Feature Name] Gesture Specifications

### [Element] Gesture

**Gesture Type:** [Tap | Long Press | Drag | Swipe | Pinch | Rotation]

**Interaction Pattern:**
- Primary Action: [What happens on completion]
- Cancel Behavior: [What happens if gesture is cancelled]

**Gesture Parameters:**
- Minimum Distance: [for swipe/drag, in points]
- Minimum Duration: [for long press, in seconds]

**Visual Feedback:**
- During Gesture: [Scale, opacity, position changes]
- On Success: [Completion animation]

**Haptic Feedback:**
- Type: [Impact (light/medium/heavy) | Selection | Notification]

**Accessibility:**
- Alternative Input: [VoiceOver action, keyboard equivalent]
```

---

## Navigation Specification Template

```markdown
## [App Name] Navigation Architecture

### Navigation Style
**Primary Pattern:** [Tab Bar | Side Menu | Navigation Stack | Modal Flow]

### [Screen Name] Navigation
**Navigation Type:** [Push | Sheet | Full Screen Cover]

**Transition:**
- Style: [Horizontal slide | Vertical slide | Fade]
- Duration: [value in seconds]

**Back Navigation:**
- Gesture: [Swipe from edge | Back button | Both]

**Deep Link:**
- URL Pattern: [e.g., myapp://screen/id]
```

---

## Apple HIG Compliance Checklist

**iOS Design Principles:**
- ✅ Clarity: Text legible at all sizes, icons precise
- ✅ Deference: Fluid motion, interface doesn't compete with content
- ✅ Depth: Visual layers convey hierarchy

**Platform Patterns (iOS 18+):**
- NavigationStack for hierarchical navigation
- TabBar: 5-item maximum with SF Symbols
- SF Symbols 7: 6,900+ symbols
- System Colors: Semantic colors adapting to modes
- Dynamic Type: Full text size range support
- Haptics: UIFeedbackGenerator patterns
- Materials: UIBlurEffect styles

**Accessibility Requirements:**
- VoiceOver labels on all interactive elements
- Dynamic Type support
- Reduce Motion alternatives
- Minimum 44x44pt touch targets
- Don't rely solely on color

---

## Handoff Checklist for Mobile Dev

Before handing off iOS design:
- [ ] Animation Specifications with timing and accessibility
- [ ] Gesture Specifications with haptics and visual feedback
- [ ] Navigation Architecture with transitions and deep linking
- [ ] User Flows as Mermaid diagrams
- [ ] Design System referencing iOS standards
- [ ] Component States (default, pressed, disabled, loading, error)
- [ ] Accessibility Requirements
- [ ] Edge Cases (empty, error, loading, offline states)
