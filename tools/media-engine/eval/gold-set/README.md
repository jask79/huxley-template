# Gold Set - Evaluator Calibration

Ground truth images for calibrating the AI-powered quality evaluator.

## Structure

```
gold-set/
  good/   Known-good images (expected score >= 0.8)
  bad/    Known-bad images (expected score <= 0.3)
```

## Usage

Place known-good images in `good/` and known-bad images in `bad/`. These
will be used in a future phase to:

1. **Calibrate thresholds** - Run the evaluator against gold set images
   to find optimal quality_threshold values per workflow.
2. **Regression testing** - Verify that evaluator scoring remains stable
   across model updates and prompt changes.
3. **Criteria validation** - Check that evaluation criteria correctly
   differentiate good from bad outputs.

## What makes a "good" image?

- Correct composition and framing
- Proper lighting and color balance
- No visual artifacts, glitches, or distortions
- Text (if any) is legible and correctly spelled
- Matches the intended style/brand/character

## What makes a "bad" image?

- Obvious visual artifacts or glitches
- Incorrect anatomy, proportions, or physics
- Garbled or misspelled text
- Wrong aspect ratio or resolution
- Completely off-prompt (generated something unrelated)

## File naming

Use descriptive names to make calibration results easier to interpret:

```
good/product-hero-clean-lighting.png
good/character-portrait-consistent.png
bad/artifact-face-distortion.png
bad/text-garbled-logo.png
```
