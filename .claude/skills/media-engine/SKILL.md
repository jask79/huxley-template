# Media Workflow Engine Skill

## Description
Configurable media production pipeline for image generation, editing, refinement, and variant creation. Uses YAML workflow templates with 4-layer config inheritance (base → template → capsule → runtime).

## Commands

### `/media generate` — Generate images from a workflow template
Generate images using a named workflow template with optional capsule overrides.

```bash
python3 {{CATALYST_ROOT}}/tools/media-engine/cli.py generate \
  --workflow <template-name> \
  --prompt "Your detailed prompt" \
  [--capsule /path/to/capsule/media-config.yaml] \
  [--output-name "filename"] \
  [--aspect-ratio "16:9"] \
  [--profile high-fidelity|fast-draft|batch-production]
```

**Available workflow templates:**
- `product-photography` — E-commerce product shots (4K, strict eval, autonomous)
- `social-content` — Social media graphics (2K, fast, high variant count)
- `character-series` — Consistent character across assets (4K, agent_in_loop, max refs)

### `/media refine` — Edit/refine an existing image
Apply edits to an existing image using the engine's evaluation loop.

```bash
python3 {{CATALYST_ROOT}}/tools/media-engine/cli.py refine \
  --input /path/to/image.png \
  --prompt "Edit instruction" \
  --workflow <template-name> \
  [--output-name "filename"]
```

### `/media variant` — Generate variants from a base image
Create multiple variations of an existing image.

```bash
python3 {{CATALYST_ROOT}}/tools/media-engine/cli.py variant \
  --input /path/to/image.png \
  --workflow <template-name> \
  --count 5 \
  [--variation-strength 0.3]
```

### `/media resolve` — Show resolved config (debugging)
Display the fully merged config from all 4 layers.

```bash
python3 {{CATALYST_ROOT}}/tools/media-engine/cli.py resolve \
  --workflow <template-name> \
  [--capsule /path/to/capsule/media-config.yaml]
```

## Workflow Templates

| Template | Best For | Resolution | Mode | Speed |
|----------|----------|-----------|------|-------|
| `product-photography` | E-commerce, catalogs | 4K | autonomous | Slower, high quality |
| `social-content` | Instagram, TikTok, Twitter | 2K | autonomous | Fast, high volume |
| `character-series` | Mascots, campaigns, series | 4K | agent_in_loop | Slower, max consistency |

## Profiles

| Profile | Resolution | Max Iterations | Threshold | Use Case |
|---------|-----------|---------------|-----------|----------|
| `high-fidelity` | 4K | 5 | 0.85 | Final production assets |
| `fast-draft` | 1K | 2 | 0.60 | Prototyping, brainstorming |
| `batch-production` | 2K | 3 | 0.75 | Volume output |

## Per-Capsule Configuration

Capsules can override any workflow parameter by creating a `media-config.yaml`:

```yaml
# capsules/my-project/media-config.yaml
extends: workflows/product-photography
profile: high-fidelity

overrides:
  consistency:
    reference_images: 8
    style_weight: 0.9
  refinement:
    evaluate_criteria:
      - custom_criterion_1
      - custom_criterion_2
  output:
    directory: capsules/my-project/generated/
```

## Refinement Modes

- **autonomous** — Engine runs the full generate→evaluate→iterate loop alone. Cheaper, faster, predictable.
- **agent_in_loop** — Engine generates, returns to agent for evaluation. Agent provides creative direction per iteration. More expensive, more creative.

## Output

All generated assets are saved to `generated-media/` (or capsule-specific directory) with:
- The image/video file
- A `.provenance.json` sidecar with full generation metadata
- Audit log entry at `tools/media-engine/eval/audit-log/audit.jsonl`

## Dependencies

- Python 3.10+
- PyYAML
- Existing `tools/image-gen/generate.sh` and `edit-image.sh`
- `GEMINI_API_KEY` in environment or macOS Keychain
