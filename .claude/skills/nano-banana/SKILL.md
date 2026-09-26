# Nano Banana CLI — Direct Gemini Image & Veo Video Generation

## Description
Direct CLI wrapper for Google's Gemini image generation and Veo 3.1 video generation APIs. Bypasses OpenRouter for zero-markup access using `GEMINI_API_KEY`. Supports text-to-image, image editing, text-to-video, image-to-video, video extension (chain up to 20 clips), reference images for character consistency, and cost estimation.

**Auth:** `GEMINI_API_KEY` environment variable (set it in your .env)
**Install:** `npm install -g @the-focus-ai/nano-banana` (install once, globally)
**Binary:** `nano-banana` (or `npx @the-focus-ai/nano-banana`)
**License:** MIT | **Source:** github.com/The-Focus-AI/nano-banana-cli

---

## Image Generation

```bash
# Generate image (Nano Banana Pro — best quality, default)
nano-banana "detailed prompt describing the image" --output {{CATALYST_ROOT}}/generated-media/filename.png

# Generate with Flash model (faster, cheaper)
nano-banana "prompt" --flash --output {{CATALYST_ROOT}}/generated-media/filename.png

# Specify model explicitly
nano-banana "prompt" --model gemini-2.0-flash --output {{CATALYST_ROOT}}/generated-media/filename.png

# Read prompt from file (for long/complex prompts)
nano-banana --prompt-file /path/to/prompt.md --output {{CATALYST_ROOT}}/generated-media/filename.png
```

### Image Models

| Model | Flag | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| `nano-banana-pro-preview` | (default) | 5-15s | State-of-the-art | Product photography, marketing, text-heavy |
| `gemini-2.0-flash` | `--flash` | 3-8s | Excellent | Fast iteration, social media, prototyping |

---

## Image Editing

```bash
# Edit an existing image with natural language
nano-banana "make the background a tropical beach sunset" --file /path/to/input.png --output {{CATALYST_ROOT}}/generated-media/edited.png

# Style transfer
nano-banana "convert to watercolor painting style" --file photo.jpg --output {{CATALYST_ROOT}}/generated-media/watercolor.png

# Object manipulation
nano-banana "remove the person in the background" --file portrait.png --output {{CATALYST_ROOT}}/generated-media/clean.png

# Text editing (best-in-class)
nano-banana "change the sign text to say HELLO WORLD" --file sign.png --output {{CATALYST_ROOT}}/generated-media/updated.png
```

---

## Video Generation (Veo 3.1)

```bash
# Premium quality video (Veo 3.1, 1080p, with audio)
nano-banana --video "A sunset over mountains, cinematic drone shot rising slowly" \
  --output {{CATALYST_ROOT}}/generated-media/sunset.mp4

# Fast/cheap video (Veo 3.1 Fast)
nano-banana --video "Product spinning on turntable" --video-fast \
  --output {{CATALYST_ROOT}}/generated-media/product.mp4

# No audio (cheaper)
nano-banana --video "Abstract flowing particles" --no-audio \
  --output {{CATALYST_ROOT}}/generated-media/particles.mp4

# 720p shorter duration (cheapest option)
nano-banana --video "Quick logo animation" --video-fast --no-audio --resolution 720p --duration 4 \
  --output {{CATALYST_ROOT}}/generated-media/logo_anim.mp4

# Portrait video (TikTok/Reels)
nano-banana --video "Person walking toward camera" --aspect 9:16 \
  --output {{CATALYST_ROOT}}/generated-media/portrait.mp4
```

### Video Models

| Model | Flag | Cost/Second | Audio | Notes |
|-------|------|------------|-------|-------|
| `veo-3.1-generate-preview` | (default) | $0.50 | Yes | Premium quality, 1080p |
| `veo-3.1-fast-generate-preview` | `--video-fast` | $0.10 | Yes | 5x cheaper, faster |
| `veo-2.0-generate-001` | `--video-model veo-2.0-generate-001` | $0.35 | No | Legacy, no audio |

### Video Options

| Option | Default | Values |
|--------|---------|--------|
| `--duration` | 8 | 4, 6, 8 (1080p requires 8) |
| `--aspect` | 16:9 | 16:9, 9:16 |
| `--resolution` | 1080p | 720p, 1080p |
| `--audio` / `--no-audio` | audio on | Toggle audio generation |
| `--seed` | random | Number for reproducibility |

### Estimated Video Costs

| Config | Estimated Cost |
|--------|---------------|
| Veo 3.1 Premium, 8s, with audio | $5.40 - $6.60 |
| Veo 3.1 Premium, 8s, no audio | $3.60 - $4.40 |
| Veo 3.1 Fast, 8s, with audio | $1.08 - $1.32 |
| Veo 3.1 Fast, 8s, no audio | $0.72 - $0.88 |
| Veo 3.1 Fast, 4s, no audio (cheapest) | $0.36 - $0.44 |

**Always use `--estimate-cost` to preview before generating:**
```bash
nano-banana --video "prompt" --estimate-cost
```

---

## Image-to-Video (Animate a Still Image)

```bash
# Animate an existing image
nano-banana --video "The character slowly turns and smiles" \
  --file /path/to/portrait.png \
  --output {{CATALYST_ROOT}}/generated-media/animated.mp4
```

---

## Video Extension (Chain Clips — up to 20)

Generate a video, then extend it with continuation footage. Each extension adds another segment.

```bash
# Generate initial video
nano-banana --video "A hiker approaches a mountain trail" \
  --output {{CATALYST_ROOT}}/generated-media/hike_01.mp4

# Extend with continuation (uses .uri sidecar file automatically)
nano-banana --video "The hiker begins climbing upward" \
  --extend {{CATALYST_ROOT}}/generated-media/hike_01.mp4 \
  --output {{CATALYST_ROOT}}/generated-media/hike_02.mp4

# Extend again (chain up to 20 times)
nano-banana --video "Reaching the summit, panoramic view reveals" \
  --extend {{CATALYST_ROOT}}/generated-media/hike_02.mp4 \
  --output {{CATALYST_ROOT}}/generated-media/hike_03.mp4
```

**Note:** Extension requires `--duration 8` and the `.uri` sidecar file from the previous generation.

---

## Reference Images (Character/Style Consistency in Video)

```bash
# Use up to 3 reference images for character consistency
nano-banana --video "The hero walks through a forest" \
  --reference /path/to/hero_front.png \
  --reference /path/to/hero_side.png \
  --output {{CATALYST_ROOT}}/generated-media/hero_forest.mp4
```

**Note:** Reference images require `--duration 8`.

---

## List Available Models

```bash
nano-banana --list-models
```

---

## Key Differences from generate.sh / generate-video.sh

| Feature | generate.sh | nano-banana | Advantage |
|---------|-------------|-------------|-----------|
| Image API | OpenRouter → Gemini | Direct Gemini API | No middleman markup |
| Image editing | edit-image.sh (OpenRouter) | `--file` flag (direct) | Simpler, no markup |
| Video provider | Sora 2 (OpenAI) | Veo 3.1 (Google) | Different style, cheaper fast mode |
| Video extension | Not supported | Chain up to 20 clips | Unique capability |
| Video ref images | Not supported | Up to 3 references | Character consistency |
| Image-to-video | Not supported | `--file` + `--video` | Animate stills |
| Cost estimation | Not available | `--estimate-cost` | Preview before spend |
| Audio control | Not available | `--audio` / `--no-audio` | Cost savings |

**These tools complement each other.** Use nano-banana for direct Gemini access and Veo video. Use generate.sh/generate-video.sh for OpenRouter routing and Sora 2 video.
