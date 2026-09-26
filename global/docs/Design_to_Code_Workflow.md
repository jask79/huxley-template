# Design-to-Code Workflow: Huxley Design Studio

> **Not shipped:** this workflow references a `capsules/design-system` capsule (Plasmic + tldraw + Docusaurus) that the template does not include. Create that capsule first, or read this document as a blueprint for your own design-system setup.

**Purpose:** Complete guide for UI/UX design workflow in Huxley using the Huxley Design Studio.

**For Mobile Apps:** See `Mobile_App_Workflow.md` for complete Native iOS and React Native workflows.

---

## Huxley Design Studio

**PRIMARY:** Huxley uses a unified local design environment combining Plasmic Studio, tldraw canvases, and Docusaurus documentation.

### System Components

**Huxley Design Studio** (`https://design-studio.localhost`)
- **Plasmic Studio** (`/studio`) - Visual component builder with drag-and-drop
- **App Flow Canvas** (`/canvas`) - tldraw for screen flows and wireframing
- **Mood Board** (`/moodboard`) - tldraw for visual inspiration collection
- **Design System Docs** (`/design-system`) - Docusaurus documentation
- **Component Library** (`/components`) - React component preview

**Backend Services:**
- PostgreSQL 15 - Per-capsule databases
- Plasmic Backend (port 3003) - Visual builder API
- Next.js Shell (port 3000) - Studio interface
- Docusaurus (port 3001) - Documentation
- ChromaDB (port 8000) - Semantic search
- Caddy - HTTPS gateway

### Why This Works
- ✅ **Local-first** - No cloud dependencies, works offline
- ✅ **Open-source** - Built on Plasmic, tldraw, Docusaurus
- ✅ **Agent-readable** - Plain files (JSON, MDX, TSX)
- ✅ **Multi-platform export** - React, SwiftUI, Shopify Liquid, Static HTML
- ✅ **Semantic search** - Vector embeddings for component discovery
- ✅ **Per-capsule isolation** - Dedicated databases per project
- ✅ **Design token sync** - Bidirectional token synchronization
- ✅ **Zero cost** - Fully self-hosted

### Quick Start

```bash
# Start Design Studio
cd {{CATALYST_ROOT}}/capsules/design-system
npm run dev:all

# Access at https://design-studio.localhost
```

---

## Design Workflow

### Phase 1: Inspiration (Mood Board + Research)

**📐 UI Designer:**
- Open Mood Board (`https://design-studio.localhost/moodboard`)
- Upload reference images (drag & drop)
- Add color swatches and typography samples
- Annotate with notes and ideas
- Save canvas (auto-saves to localStorage, export to `.tldr`)
- Research on Mobbin, Dribbble, Pinterest for additional references

### Phase 2: Design System Creation (Design Tokens)

**📐 UI Designer:**
- Edit `capsules/design-system/tokens/design-language.json`
- Define brand colors from mood board inspiration
- Specify typography (fonts, sizes, weights, line heights)
- Set spacing system (8px grid)
- Configure shadows and border radius
- Changes auto-sync to Plasmic Studio via token sync service

**Example Design Tokens:**
```json
{
  "colors": {
    "primary": { "500": "#00D9FF" },
    "secondary": { "500": "#FF3B6F" },
    "success": { "500": "#00F5A0" }
  },
  "typography": {
    "heading": { "family": "Poppins", "weight": "800" },
    "body": { "family": "Inter", "weight": "400" }
  },
  "spacing": {
    "base": "8px",
    "xs": "4px",
    "sm": "8px",
    "md": "16px",
    "lg": "24px"
  }
}
```

### Phase 3: App Flow Design (Canvas)

**📐 UI Designer:**
- Open App Flow Canvas (`https://design-studio.localhost/canvas`)
- Draw screen rectangles
- Add navigation arrows
- Label screens and user flows
- Annotate interactions and states
- Save canvas (auto-saves, export to `.tldr`)

### Phase 4: Component Design (Plasmic Studio)

**📐 UI Designer:**
- Open Plasmic Studio (`https://design-studio.localhost/studio`)
- Create components with drag-and-drop interface
- Apply design tokens (colors, typography, spacing)
- Build variants (primary, secondary, disabled, etc.)
- Design states (default, hover, active, loading)
- Visual preview updates in real-time

### Phase 5: Component Export (Multi-Platform)

**📐 UI Designer OR 🎨 Frontend Dev:**

**React/Next.js Export:**
```bash
# Export all components to React
curl -X POST https://design-studio.localhost/api/export/project \
  -H "Content-Type: application/json" \
  -d '{"adapter": "react", "capsule": "default"}'

# Output: capsules/design-system/generated/react/
```

**SwiftUI Export (for iOS):**
```bash
# Export to SwiftUI
curl -X POST https://design-studio.localhost/api/export/project \
  -H "Content-Type: application/json" \
  -d '{"adapter": "swiftui", "capsule": "default"}'

# Output: capsules/design-system/generated/ios/
```

**Shopify Liquid Export:**
```bash
# Export to Shopify
curl -X POST https://design-studio.localhost/api/export/project \
  -H "Content-Type: application/json" \
  -d '{"adapter": "liquid", "capsule": "default"}'

# Output: capsules/design-system/generated/shopify/
```

**Static HTML/CSS Export:**
```bash
# Export to static files
curl -X POST https://design-studio.localhost/api/export/project \
  -H "Content-Type: application/json" \
  -d '{"adapter": "static", "capsule": "default"}'

# Output: capsules/design-system/generated/static/
```

### Phase 6: Implementation Handoff

**🎨 Frontend Dev (web) OR 📱 Mobile Dev:**
- Receive exported components from Design Studio
- Review design system docs (`/design-system`)
- Import generated components into capsule codebase
- Theme component library with design tokens
- Build custom components for unique patterns
- Validate against Plasmic Studio previews

---

## Complete Example: Fitness Tracking App

### 1. Mood Board (Inspiration)
- Open `/moodboard`
- Upload Nike Run Club screenshots
- Add Strava color palette swatches
- Annotate "energetic, motivational" vibe
- Export to `capsules/design-system/moodboard/fitness-app.tldr`

### 2. Design Tokens
```json
{
  "colors": {
    "primary": { "500": "#00D9FF" },
    "secondary": { "500": "#FF3B6F" },
    "success": { "500": "#00F5A0" }
  },
  "typography": {
    "heading": { "family": "Poppins ExtraBold" },
    "body": { "family": "Inter" }
  },
  "spacing": { "base": "8px" }
}
```

### 3. App Flow Canvas
- Open `/canvas`
- Draw: Login → Dashboard → Workout → Stats
- Add navigation arrows
- Annotate: "Tab bar navigation with 4 tabs"
- Export to `capsules/design-system/canvases/fitness-flow.tldr`

### 4. Plasmic Studio (Components)
- Create components: DashboardCard, StatRing, WorkoutButton
- Apply design tokens
- Build variants: primary, secondary, disabled
- Preview in Studio

### 5. Export (React Native)
```bash
# Export to React components
curl -X POST https://design-studio.localhost/api/export/project \
  -d '{"adapter": "react", "capsule": "fitness-tracker"}'
```

### 6. Implement (Mobile Dev)
- Import components from `generated/react/`
- Theme NativeBase with design tokens
- Build custom: Hero stats card, Progress ring animation
- Integrate with app navigation

---

## Agent Collaboration

### 📐 UI Designer
- Collects inspiration in Mood Board (tldraw)
- Designs app flows in Canvas (tldraw)
- Creates design tokens (`tokens/design-language.json`)
- Builds components in Plasmic Studio
- Documents in Docusaurus
- Exports components for implementation

### 🎨 Frontend Dev (web apps)
- Receives exported React components
- Imports into Next.js/React app
- Themes shadcn/ui with design tokens
- Builds custom components as needed
- References Design Studio for visual validation

### 📱 Mobile Dev (mobile apps)
- Receives exported React/SwiftUI components
- Imports into React Native or iOS app
- Themes NativeBase (React Native) or native SwiftUI
- Builds custom components for platform-specific patterns
- References Design Studio and Apple/Google guidelines

### 🏛️ Backend Dev
- Accesses component API docs (`/design-system`)
- Reviews component props and data requirements
- Builds backend APIs to match component interfaces

---

## Design Studio Features

### Semantic Search (ChromaDB)
```bash
# Search components by natural language
curl -X POST https://design-studio.localhost/api/search/semantic \
  -d '{"query": "blue button with rounded corners", "limit": 10}'
```

### Design Token Sync
- Bidirectional sync between `tokens/design-language.json` and Plasmic database
- File watcher detects changes
- WebSocket broadcasts updates to all connected clients
- Conflict resolution with visual diff UI

### Per-Capsule Isolation
- Each capsule gets dedicated PostgreSQL database (`wab_${CAPSULE}`)
- Separate design systems per project
- No cross-capsule contamination
- Easy capsule switching in Studio UI

### Component Documentation
- Auto-generated API docs in Docusaurus
- MDX files with live component previews
- Usage examples and code snippets
- Design token references

---

## File Structure

```
capsules/design-system/
├── tokens/
│   └── design-language.json    # Master design tokens
├── moodboard/
│   ├── fitness-app.tldr         # Inspiration canvas
│   └── assets/                  # Reference images
├── canvases/
│   └── fitness-flow.tldr        # App flow diagrams
├── generated/                   # Exported components
│   ├── react/                   # React/Next.js
│   ├── ios/                     # SwiftUI
│   ├── shopify/                 # Liquid templates
│   └── static/                  # HTML/CSS
├── components/                  # React component library
├── docusaurus-docs/             # Documentation
└── plasmic-app/                 # Studio shell
```

---

## Cost Analysis

- Huxley Design Studio: $0/year (self-hosted, open-source)
- PostgreSQL: $0/year (local installation)
- ChromaDB: $0/year (local installation)
- Caddy: $0/year (open-source)
- Plasmic Platform: $0/year (AGPL-3.0 self-hosted)
- **Total: $0 with complete design-to-code workflow**

---

## Additional Resources

- **Complete Architecture:** `capsules/design-system/ARCHITECTURE.md`
- **Quick Start Guide:** `capsules/design-system/QUICKSTART.md`
- **Self-Hosting Guide:** `capsules/design-system/PLASMIC_SELF_HOSTING.md`
- **Mobile Workflows:** `global/docs/Mobile_App_Workflow.md`

---

*Design-to-Code Workflow Guide - Huxley Documentation*
