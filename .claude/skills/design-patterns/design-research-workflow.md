# Design Research Workflow

Research patterns, Figma workflow, and mobile component libraries.

## Figma Workflow

**Free tier:** 3 files for design work + unlimited Community browsing

**Use Figma Community for:**
- Browse UI kits (Apple iOS 26, Material Design 3)
- Study real-world app patterns
- Screenshot inspiration (doesn't count toward limit)

**Use your 3 files for:**
- Actual design mockups
- Component library creation
- Client presentations

## Mobile Inspiration Sources

**Top Tier:**
1. **Mobbin** (mobbin.com) - 300k+ mobile screenshots, searchable
2. **Screenlane** (screenlane.com) - Free, organized by pattern
3. **UI Sources** (uisources.com) - iOS/Android examples
4. **Refero** (refero.design) - By App Store category

**Showcases:**
- **Dribbble** - Filter by Mobile/iOS/Android
- **Behance** - Full case studies with process

**Real Apps:**
- App Store/Play Store competitor research
- Download and screenshot actual flows

## Research Workflow

```
1. GATHER (Define category → Search across sources)
   - Mobbin: "[category] dashboard"
   - Figma Community: "[category] UI kit"
   - Download top 3 competitor apps

2. ANALYZE
   - Screenshot 10-20 best examples
   - Annotate patterns, colors, layouts
   - WebSearch: "[category] UI trends 2025"

3. DESIGN SYSTEM
   - Document colors, typography, spacing
   - Reference inspiration sources

4. DESIGN IN FIGMA
   - Import base kit from Community
   - Customize with brand
   - Design all screens + states
```

## Mobile Component Libraries

**For React Native:**

| Library | Style | Use When |
|---------|-------|----------|
| **NativeBase** | Flexible | Default choice, most like shadcn/ui |
| **React Native Paper** | Material 3 | Android-first apps |
| **Tamagui** | Universal | Web + mobile same code |
| **gluestack-ui** | Copy-paste | shadcn-like philosophy |

**Design Handoff:**
```markdown
## Implementation Recommendations
### Library: NativeBase
- Theme with brand colors
- Customize button variants

### Custom Components (build from scratch):
- Hero stat card (unique gradient)
- Progress ring (custom animation)
```

## Brand Design Workflow

**80% themed library + 20% custom:**

1. **Define Brand** - Colors, typography, visual style
2. **Theme Library** - Apply brand to NativeBase/Paper/etc.
3. **Custom Components** - Build unique brand elements from primitives

**Custom component examples:**
- GlassmorphicCard (View + BlurView + LinearGradient)
- BrandedProgressRing (custom animation)
- Custom navigation with brand icons
