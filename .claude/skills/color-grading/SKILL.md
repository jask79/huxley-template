# Color Grading Skill

Programmatic color grading with AI vision feedback for video production.

## Tool

`python3 tools/color_grader.py <subcommand> [options]`

## Global Flags

- `--json` — Machine-readable JSON output
- `--verbose` — Detailed logging to stderr

## Subcommands

### generate-lut — Generate .cube LUT from color parameters

```bash
# From manual parameters
python3 tools/color_grader.py generate-lut \
  --lift 0.02,0.0,-0.03 \
  --gamma 1.0,0.95,0.9 \
  --gain 1.05,1.0,0.98 \
  --saturation 1.2 \
  --hue-shift 5 \
  --temperature 5200 \
  --size 33 \
  --output /path/to/output.cube

# From a named creative look preset
python3 tools/color_grader.py generate-lut \
  --look cinematic-teal-orange \
  --output /path/to/output.cube
```

**Parameters:**
- `--lift R,G,B` — Shadow offset (-0.5 to 0.5), default 0,0,0
- `--gamma R,G,B` — Midtone power (0.1 to 5.0), default 1,1,1
- `--gain R,G,B` — Highlight multiplier (0 to 2.0), default 1,1,1
- `--saturation FLOAT` — Saturation factor, default 1.0
- `--hue-shift DEGREES` — Hue rotation, default 0
- `--temperature KELVIN` — Color temperature (2000-10000), default 5600
- `--size INT` — LUT cube size (17/33/64), default 33
- `--look NAME` — Use named preset instead of manual params

### cdl — Generate ASC CDL (Color Decision List)

```bash
python3 tools/color_grader.py cdl \
  --slope 1.1,1.0,0.95 \
  --offset 0.02,0.0,-0.01 \
  --power 1.0,1.0,1.05 \
  --saturation 1.0 \
  --output /path/to/output.cube
  # --format cdl  for XML output
```

CDL formula: `out = clamp((in * slope + offset) ^ power)`

### evaluate — Assess color grading quality

```bash
# Objective metrics only
python3 tools/color_grader.py evaluate \
  --frame /path/to/frame.png \
  --json

# With reference comparison
python3 tools/color_grader.py evaluate \
  --frame /path/to/frame.png \
  --reference /path/to/hero.png \
  --json

# With AI vision scoring (requires GEMINI_API_KEY)
python3 tools/color_grader.py evaluate \
  --frame /path/to/frame.png \
  --ai \
  --json

# With temporal consistency check
python3 tools/color_grader.py evaluate \
  --frame /path/to/frame.png \
  --previous-frame /path/to/prev.png \
  --json
```

**Metrics computed:**
- Clipping (blacks/whites percentage, pass if < 2%)
- Color cast (channel mean difference, pass if < 15)
- Contrast (5th-95th percentile range, pass if > 80)
- Saturation (mean HSV, pass if 30-200)
- Skin tones (hue/sat/lightness check if detected)
- Temporal consistency (luma diff vs previous frame)

### scopes — Generate scope visualizations

```bash
python3 tools/color_grader.py scopes \
  --frame /path/to/frame.png \
  --types waveform,vectorscope,parade,histogram \
  --output-dir ./scopes/
```

Generates PNG images: waveform, vectorscope, RGB parade, histogram.

### match — Match shot to reference frame

```bash
python3 tools/color_grader.py match \
  --source /path/to/source.png \
  --reference /path/to/hero.png \
  --method mkl \
  --output /path/to/corrective.cube
```

Methods: `mkl` (best quality, default), `reinhard`, `hm-mvgd-hm`

### grade — Full automated grading pipeline

```bash
# Full structured workflow
python3 tools/color_grader.py grade \
  --frame /path/to/frame.png \
  --workflow full \
  --max-iterations 10 \
  --threshold 85 \
  --output /path/to/final.cube \
  --output-frame /path/to/graded.png

# With reference-based grading
python3 tools/color_grader.py grade \
  --frame /path/to/frame.png \
  --reference /path/to/hero.png \
  --workflow full \
  --output final.cube

# Primary corrections only
python3 tools/color_grader.py grade \
  --frame /path/to/frame.png \
  --workflow primary-only \
  --output primary.cube

# Shot matching only
python3 tools/color_grader.py grade \
  --frame /path/to/frame.png \
  --reference /path/to/hero.png \
  --workflow match-only \
  --output match.cube
```

**Structured workflow order (full):**
1. Exposure correction (histogram centering)
2. White balance (color cast removal)
3. Contrast (tonal range expansion)
4. Saturation (target range adjustment)
5. Skin tones (if detected, verify acceptable range)
6. Creative look (if --look specified)
7. Shot matching (if --reference specified)

### looks — Creative look presets

```bash
# List all presets
python3 tools/color_grader.py looks list

# Preview a look on a frame
python3 tools/color_grader.py looks preview cinematic-teal-orange \
  --frame /path/to/frame.png \
  --output preview.png
```

**Built-in presets:** cinematic-teal-orange, clean-commercial, documentary-natural, social-vibrant, film-noir, warm-golden, cool-blue, bleach-bypass

### refs — Reference look bank

```bash
# Add approved frame to reference bank
python3 tools/color_grader.py refs add /path/to/frame.png \
  --name "hero-sunset" --tags outdoor,warm

# List references
python3 tools/color_grader.py refs list

# Show reference details
python3 tools/color_grader.py refs show hero-sunset
```

## Integration with DaVinci Resolve

The color grader generates LUTs (.cube files). Apply them in Resolve:
```bash
# Generate corrective LUT
python3 tools/color_grader.py grade --frame frame.png --output correction.cube

# Apply in Resolve
python3 tools/davinci_resolve.py color apply-lut --lut-path correction.cube
```

## Typical Agent Workflow

```bash
# 1. Extract frame from Resolve timeline
python3 tools/davinci_resolve.py render add --preset "Still Frame" --output /tmp/frame.png

# 2. Evaluate current state
python3 tools/color_grader.py evaluate --frame /tmp/frame.png --json

# 3. Auto-grade with structured workflow
python3 tools/color_grader.py grade \
  --frame /tmp/frame.png \
  --workflow full \
  --threshold 85 \
  --output /tmp/correction.cube \
  --output-frame /tmp/graded.png

# 4. Review graded frame quality
python3 tools/color_grader.py evaluate --frame /tmp/graded.png --json

# 5. Apply final LUT in Resolve
python3 tools/davinci_resolve.py color apply-lut --lut-path /tmp/correction.cube

# 6. Generate scopes for verification
python3 tools/color_grader.py scopes --frame /tmp/graded.png --output-dir /tmp/scopes/
```
