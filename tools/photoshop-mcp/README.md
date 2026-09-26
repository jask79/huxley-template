# Huxley Photoshop MCP

**Drives Adobe Photoshop programmatically from {{ORCHESTRATOR_NAME}} + any MCP client.**

Built for Huxley's brand asset, thumbnail, and product photo workflows
(your visual-brand capsules).

- Transport: stdio (matches `tools/catalyst-mcp/`, etc.)
- MCP spec: 2025-06-18
- Photoshop bridge: ExtendScript-over-AppleScript (works on macOS, no plugin)
- Stack: TypeScript + `@modelcontextprotocol/sdk` + `zod`

**Status:** v1 — 16 tools registered by default (17 if `PHOTOSHOP_MCP_ALLOW_RAW_JSX=1`),
server boots and responds to MCP handshake + `tools/list` + `ps_is_running`. Live PS
execution validated against the bridge once Photoshop 2026 is open.

---

## Install

The server lives in this directory. From a fresh clone:

```bash
cd tools/photoshop-mcp
npm install
npm run build
```

Add it to the repo's top-level `.mcp.json` yourself once built — the template
ships five core servers and leaves this one opt-in.

### One-time macOS permissions

On first call, macOS will prompt for two permissions. Grant both:

1. **Automation** — Terminal/Claude Code → Adobe Photoshop 2026
   System Settings → Privacy & Security → Automation
2. **Apple Events** for the parent process (Terminal, iTerm, Claude Code)

If permissions get into a weird state, reset and re-prompt with:

```bash
tccutil reset AppleEvents
```

### Adobe Photoshop must be running

Every tool except `ps_is_running` short-circuits with a clear error if PS is
not open. Open Photoshop 2026 first.

The default app name is `Adobe Photoshop 2026`. Override per-machine with the
`PHOTOSHOP_APP_NAME` env var (already set in `.mcp.json`):

```json
"env": { "PHOTOSHOP_APP_NAME": "Adobe Photoshop 2025" }
```

The value is validated at startup against the strict regex
`^Adobe Photoshop( \d{4})?$`. Anything else is rejected — `PHOTOSHOP_APP_NAME`
flows into AppleScript so it MUST be sanitized.

---

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `PHOTOSHOP_APP_NAME` | `Adobe Photoshop 2026` | Which PS to drive. Validated against `^Adobe Photoshop( \d{4})?$`. |
| `PHOTOSHOP_MCP_ALLOW_RAW_JSX` | unset (off) | If set to `1`, registers the `ps_execute_jsx` escape-hatch tool. **SECURITY:** raw JSX is RCE-on-the-PS-host. Do NOT enable when serving untrusted clients. |
| `PHOTOSHOP_MCP_ALLOWED_ROOTS` | `~/Downloads:~/Pictures:~/Documents:$CATALYST_ROOT:/tmp` | Colon-separated list of absolute paths that `ps_batch_folder` accepts as input/output. Anything outside is rejected. |
| `CATALYST_ROOT` | inferred from install path | Used for default allowed-roots list and brand template lookup. |

---

## Tools (16 default, 17 with raw JSX)

### Health / preflight
- **`ps_is_running`** — checks PS process + reports version + active doc info

### Huxley value-add (the 12 from the architecture report)
- **`ps_select_subject`** — PS AI Select Subject (`autoCutout`)
- **`ps_remove_background`** — Select Subject → invert → delete (or apply mask)
- **`ps_match_color`** — match the active doc's color stats to a reference image
- **`ps_select_color_range`** — Color Range selection by sample point + fuzziness
- **`ps_place_smart_object`** — drop a file in as an EMBEDDED smart object (non-destructive). Linked smart objects are deferred to v2 (require a `placeLinked` descriptor — the previous `linked: true` option was silently broken and has been removed from the schema).
- **`ps_apply_curves`** — Curves adjustment by control points + channel
- **`ps_apply_levels`** — Levels (input/output black/white, gamma, channel)
- **`ps_apply_layer_style`** — drop shadow / stroke / outer glow on active layer
- **`ps_export_preset`** — multi-size export packs (Shopify, YT, IG)
- **`ps_apply_brand_template`** — render a JSON-defined template for a capsule
- **`ps_batch_folder`** — apply a tool sequence to every image in a folder

### Foundational document ops (the value-add tools depend on these)
- **`ps_open_image`** — open an image file (absolute path)
- **`ps_save_document`** — save active doc (.psd, .png, .jpg, .tif, ...)
- **`ps_close_document`** — close active doc (defaults to discard changes)
- **`ps_resize_image`** — resize to width × height in pixels
- **`ps_execute_jsx`** — escape hatch — run arbitrary ExtendScript JSX. **Hidden by default** — set `PHOTOSHOP_MCP_ALLOW_RAW_JSX=1` to register. SECURITY: this runs arbitrary JSX inside Photoshop. Do not expose this MCP server to untrusted clients with this tool enabled.

---

## Built-in export presets

| Preset | Targets |
|---|---|
| `shopify-product` | 480x480, 1024x1024, 2048x2048 (PNG) |
| `yt-thumbnail` | 1280x720 (JPG q11) |
| `ig-square` | 1080x1080 (PNG) |
| `ig-story` | 1080x1920 (PNG) |

To add custom presets, drop a `src/templates/export-presets.json` matching
`ExportPreset[]` from `src/templates/registry.ts` — picked up at startup.

---

## Brand templates

Brand templates are JSON files describing a full canvas + layer stack +
optional export pack. They live per capsule:

```
capsules/<capsule>/photoshop-templates/<name>.json
```

The MCP resolves `ps_apply_brand_template(capsule, template, params)` to
that path.

### Template schema (sketch)

```jsonc
{
  "name": "thumbnail-base",
  "description": "Lo-fi mix YouTube thumbnail.",
  "canvas": {
    "width": 1280,
    "height": 720,
    "dpi": 72,
    "colorMode": "RGB",
    "backgroundColor": [10, 8, 14]
  },
  "layers": [
    { "type": "image", "source": "{params.background_image}", "fit": "fill" },
    {
      "type": "image",
      "source": "{params.brand_logo}",
      "smartObject": true,
      "x": 60, "y": 60, "scale": 0.5
    },
    {
      "type": "text",
      "content": "{params.title}",
      "fontName": "Helvetica-Bold",
      "fontSize": 110,
      "color": [255, 240, 230],
      "alignment": "CENTER",
      "x": 640, "y": 360
    }
  ],
  "export": [
    { "preset": "yt-thumbnail", "filename": "{params.slug}-thumb" }
  ]
}
```

### Layer types

- `image` — `source` (absolute path), `fit` (`fill | fit | none`), `smartObject` (bool), `x`, `y`, `scale`
- `text` — `content`, `fontName`, `fontSize`, `color: [R, G, B]`, `alignment` (`LEFT | CENTER | RIGHT`), `x`, `y`
- `fill` — `fillColor: [R, G, B]`, `fillOpacity`

### Placeholder substitution

`{key}` tokens in `source`, `content`, and export `filename` are replaced from
`params` at render time. Unmatched tokens are left as-is so missing params
produce visible markers, not silent breakage.

**Substitution surface (intentionally explicit):** only `layer.source`,
`layer.content`, and `template.export[*].filename` accept `{params}` tokens.
Other fields (`fontName`, color tuples, layout numbers) are NOT substituted.

**Param value validation:** every param value flows through a unicode-aware
allowlist regex that rejects control chars, line/paragraph separators
(U+2028/U+2029), and other ES3-string-terminating characters. Reject (do not
silently strip).

### Path containment

- `capsule` slug is validated against `^[a-z0-9-]+$`
- `template` name is validated against `^[a-z0-9_-]+$`
- Resolved template paths are asserted to stay within their base directory
- Export `outputDir` paths are asserted to contain every per-target file
- `ps_batch_folder` confines `inputDir` and any step `outputDir`/`referencePath` to `PHOTOSHOP_MCP_ALLOWED_ROOTS`

### Capsules seeded

Each visual-brand capsule has a `photoshop-templates/` directory with a README
and (where it makes sense) a starter `thumbnail-base.json`:

- `capsules/<your-capsule>/photoshop-templates/` — one per visual-brand capsule

---

## Usage examples ({{ORCHESTRATOR_NAME}} prompts)

**Quick health check:**
> "Check if Photoshop is running."
→ `ps_is_running`

**Cutout a product photo:**
> "Open ~/Downloads/serum.jpg, remove the background, save the cutout to /tmp/serum-cut.png."
→ `ps_open_image` → `ps_remove_background` → `ps_save_document`

**Generate a channel mix thumbnail:**
> "Generate a channel thumbnail titled 'Midnight Rain' using /tmp/midnight-bg.png and write it to /tmp/thumbs/."
→ `ps_apply_brand_template(capsule="your-capsule", template="thumbnail-base", params={...}, outputDir="/tmp/thumbs")`

**Multi-size Shopify product export:**
> "Export the open document as a Shopify product set into /tmp/shopify with base name 'rosehip-serum'."
→ `ps_export_preset(preset="shopify-product", outputDir="/tmp/shopify", baseFilename="rosehip-serum")`

**Batch process a folder of product photos:**
> "Open every photo in /tmp/incoming, remove backgrounds, color-grade with curves, export at Shopify product preset to /tmp/processed."
→ `ps_batch_folder(...)` with a step sequence

---

## Troubleshooting

### "Photoshop is not running"
Open Photoshop 2026 (or whatever version, set `PHOTOSHOP_APP_NAME` to match).

### Tool hangs / 60s timeout
Photoshop is probably waiting on a modal dialog (file overwrite confirm, etc.).
Click through it on the Mac. The bridge always passes `DialogModes.NO` to PS
actions but some legacy paths still surface modals.

### "osascript failed"
Usually a permission issue. macOS will prompt the first time. Reset with:
```bash
tccutil reset AppleEvents
```

### Action descriptor errors
ActionManager is brittle across PS versions. The descriptors in
`src/bridge/descriptors.ts` are tuned for Photoshop 2026 (v27.x) but fall back
gracefully where possible. If a tool fails on a specific PS version, file an
issue with the exact PS version (`ps_is_running` reports it) and the tool
arguments you used.

### "ExtendScript ran the script but no result file was written"
The user script crashed before our wrapper could write the result file.
Wrap your `ps_execute_jsx` body in `try { ... } catch (e) { /* ... */ }` and
set `result = { error: e.message }` so we get a structured response.

---

## File layout

```
tools/photoshop-mcp/
├── package.json                      # catalyst-photoshop-mcp
├── tsconfig.json
├── start.sh                          # standalone launcher
├── README.md                         # you are here
├── src/
│   ├── index.ts                      # MCP server bootstrap (stdio)
│   ├── smoke.ts                      # standalone health-check probe
│   ├── bridge/
│   │   ├── extendscript.ts           # osascript injector + result IPC
│   │   ├── health.ts                 # ps_is_running internals
│   │   └── descriptors.ts            # ActionManager JSX builders
│   ├── tools/
│   │   ├── index.ts                  # tool registry
│   │   ├── types.ts                  # ToolDefinition + ToolContext
│   │   ├── health.ts                 # ps_is_running
│   │   ├── document.ts               # open/save/close/resize/exec_jsx
│   │   ├── ai-selection.ts           # select_subject/remove_bg/color_range
│   │   ├── match-color.ts            # match_color
│   │   ├── place-smart-object.ts     # place_smart_object
│   │   ├── color-grading.ts          # apply_curves / apply_levels
│   │   ├── layer-style.ts            # apply_layer_style
│   │   ├── export-preset.ts          # export_preset
│   │   ├── brand-template.ts         # apply_brand_template
│   │   └── batch-folder.ts           # batch_folder
│   └── templates/
│       ├── registry.ts               # ExportPreset + BrandTemplate registry
│       ├── shopify-product.json
│       ├── yt-thumbnail.json
│       ├── ig-square.json
│       └── ig-story.json
└── dist/                             # compiled output (gitignored)
```

---

