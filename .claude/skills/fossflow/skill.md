---
name: fossflow
description: |
  Generate and render isometric infrastructure diagrams using FossFLOW (open-source PWA).
  Supports AWS, GCP, Azure, and Kubernetes icon packs. Outputs JSON diagram files that can
  be opened at https://stan-smith.github.io/FossFLOW/ or in a local Docker instance.

  Use this skill when:
  1. User asks to "create an infrastructure diagram" or "diagram the architecture"
  2. User wants to visualize cloud infrastructure (AWS, GCP, Azure, K8s)
  3. User needs isometric network/system topology diagrams
  4. User says "fossflow" or "isometric diagram"
  5. User wants to export architecture as a visual diagram (complement to Mermaid for isometric style)
---

# FossFLOW — Isometric Infrastructure Diagrams

Generate beautiful isometric infrastructure diagrams programmatically via JSON. Diagrams can be opened in the FossFLOW web app or self-hosted Docker instance.

**Source:** https://github.com/stan-smith/FossFLOW
**Live app:** https://stan-smith.github.io/FossFLOW/
**Docker:** `docker run -p 80:80 -v $(pwd)/diagrams:/data/diagrams stnsmith/fossflow:latest`

## JSON Schema Reference

A FossFLOW diagram is a JSON file with this top-level structure:

```json
{
  "title": "My Infrastructure",
  "version": "1.0",
  "description": "Optional description",
  "icons": [],
  "colors": [],
  "items": [],
  "views": []
}
```

### Icons

Define the visual components available in the diagram. Use URLs from the isoflow icon sets or custom SVGs.

```json
{
  "id": "server-1",
  "name": "Web Server",
  "url": "https://isoflow.io/static/assets/icons/networking/server.svg",
  "collection": "isoflow",
  "isIsometric": true,
  "scale": 1.0
}
```

**Built-in icon packs** (use collection names): `isoflow` (core), `aws`, `gcp`, `azure`, `kubernetes`

**Common isoflow icon URLs:**
- Server: `https://isoflow.io/static/assets/icons/networking/server.svg`
- Block: `https://isoflow.io/static/assets/icons/networking/block.svg`

For cloud provider icons, reference the `@isoflow/isopacks` npm packages (aws, gcp, azure, kubernetes).

### Colors

Define reusable colors for connectors and rectangles:

```json
{ "id": "blue", "value": "#2196F3" }
```

### Items (Model Items)

Each item is a logical entity in your diagram. Items reference icons by ID:

```json
{
  "id": "web-server",
  "name": "Web Server",
  "description": "Handles HTTP requests",
  "icon": "server-1"
}
```

### Views

Views define the spatial layout. Each view contains positioned items, connectors, rectangles, and text boxes:

```json
{
  "id": "main-view",
  "name": "Main View",
  "description": "Infrastructure overview",
  "items": [
    { "id": "web-server", "tile": { "x": 5, "y": 3 }, "labelHeight": 1 }
  ],
  "connectors": [
    {
      "id": "conn-1",
      "description": "HTTPS",
      "color": "blue",
      "style": "SOLID",
      "lineType": "SINGLE",
      "showArrow": true,
      "anchors": [
        { "id": "a1", "ref": { "item": "web-server" } },
        { "id": "a2", "ref": { "item": "database" } }
      ]
    }
  ],
  "rectangles": [
    {
      "id": "vpc-zone",
      "color": "blue",
      "from": { "x": 0, "y": 0 },
      "to": { "x": 10, "y": 8 }
    }
  ],
  "textBoxes": [
    {
      "id": "label-1",
      "tile": { "x": 1, "y": 1 },
      "content": "VPC",
      "fontSize": 16
    }
  ]
}
```

### Connector Properties

| Property | Type | Values |
|----------|------|--------|
| `style` | enum | `SOLID`, `DOTTED`, `DASHED` |
| `lineType` | enum | `SINGLE`, `DOUBLE`, `DOUBLE_WITH_CIRCLE` |
| `showArrow` | boolean | Arrow at end of connector |
| `color` | string | References a color ID |
| `customColor` | string | Direct hex color (e.g., `#FF0000`) |
| `labels` | array | Flexible label positioning along path |

### Connector Labels (flexible positioning)

```json
{
  "id": "label-1",
  "text": "443/tcp",
  "position": 50,
  "height": 1,
  "showLine": true
}
```

`position` is a percentage (0-100) along the connector path.

## Workflow

### 1. Generate Diagram JSON

Build the JSON structure programmatically based on the architecture being documented:

```bash
# Write diagram JSON to file
cat > /tmp/my-infrastructure.json << 'DIAGRAM_EOF'
{
  "title": "Production Stack",
  "version": "1.0",
  "icons": [
    { "id": "srv", "name": "Server", "url": "https://isoflow.io/static/assets/icons/networking/server.svg" },
    { "id": "db", "name": "Database", "url": "https://isoflow.io/static/assets/icons/networking/block.svg" }
  ],
  "colors": [
    { "id": "green", "value": "#4CAF50" },
    { "id": "blue", "value": "#2196F3" }
  ],
  "items": [
    { "id": "web", "name": "Web Server", "icon": "srv" },
    { "id": "api", "name": "API Server", "icon": "srv" },
    { "id": "postgres", "name": "PostgreSQL", "icon": "db" }
  ],
  "views": [{
    "id": "overview",
    "name": "Overview",
    "items": [
      { "id": "web", "tile": { "x": 2, "y": 2 } },
      { "id": "api", "tile": { "x": 5, "y": 4 } },
      { "id": "postgres", "tile": { "x": 8, "y": 6 } }
    ],
    "connectors": [
      {
        "id": "c1", "description": "REST API", "color": "green", "style": "SOLID", "showArrow": true,
        "anchors": [{ "id": "a1", "ref": { "item": "web" } }, { "id": "a2", "ref": { "item": "api" } }]
      },
      {
        "id": "c2", "description": "SQL", "color": "blue", "style": "SOLID", "showArrow": true,
        "anchors": [{ "id": "a3", "ref": { "item": "api" } }, { "id": "a4", "ref": { "item": "postgres" } }]
      }
    ],
    "rectangles": [
      { "id": "r1", "color": "blue", "from": { "x": 0, "y": 0 }, "to": { "x": 10, "y": 8 } }
    ],
    "textBoxes": [
      { "id": "t1", "tile": { "x": 0, "y": 0 }, "content": "Production VPC", "fontSize": 14 }
    ]
  }]
}
DIAGRAM_EOF
```

### 2. Open in FossFLOW

**Option A — Web app:** Open https://stan-smith.github.io/FossFLOW/ and use Import to load the JSON file.

**Option B — Docker (persistent):**
```bash
docker compose -f /path/to/docker-compose.yml up -d
# Copy diagram to mounted volume
cp /tmp/my-infrastructure.json ./diagrams/
# Open http://localhost:3000
```

### 3. Isometric Grid Coordinate Tips

- The grid uses isometric projection with `{x, y}` coordinates
- Place items 2-3 units apart for readability
- Use rectangles to group related items (e.g., VPC boundaries, subnets)
- Connectors auto-route between item anchors
- Text boxes use the same coordinate system

## Complement to Pretty Mermaid

| Need | Use |
|------|-----|
| Quick flowcharts, sequence diagrams, ER diagrams | Pretty Mermaid (`.mmd` → SVG/ASCII) |
| Isometric infrastructure visualization with cloud icons | FossFLOW (JSON → interactive PWA) |
| Architecture documentation in markdown | Pretty Mermaid |
| Client-facing infrastructure presentations | FossFLOW |

Both tools are available. Choose based on the diagram style needed.
