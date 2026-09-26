# Higgsfield AI

**What:** Unified AI media generation gateway fronting 20+ image models and 16+ video models (Google Veo 3.1, Kling 3.0, Seedance 2.0, GPT Image, Grok, Flux, Nano Banana, plus Higgsfield's own Soul + Cinematic Studio stack). Includes Marketing Studio with brand kits, Soul ID character training, and DTC Ads Engine.

**Status:** bring your own Higgsfield plan — any tier works with the CLI. Authenticate with `higgs auth login`; nothing account-specific is stored in this repo.

---

## Account & CLI

- **Account:** your own Higgsfield login (`higgs auth login`; keep account details out of the repo)
- **Plan:** whichever tier you subscribe to — credit allowance, parallel-generation limits and unlocked models vary by plan; check `higgs account status`
- **CLI:** `higgs` or `higgsfield` (NOT `hf` — docs claim that alias works but it doesn't)
- **Install:** `npm install -g @higgsfield/cli`
- **Auth:** `higgs auth login` — MUST be run in a real Terminal tab, NOT via Claude Code `!` prefix (OAuth callback dies in subprocess context). Token persists across sessions.

---

## Common Commands

```bash
higgs account status                                # credits + plan
higgs model list --image                            # all image models
higgs model list --video                            # all video models
higgs model get <model_id>                          # see params for a model
higgs generate cost <model_id> --prompt "..."       # cost estimate (free, no credits)
higgs generate create <model_id> --prompt "..." --wait    # sync gen, returns URL
higgs upload create <file_path>                     # upload local image/video, get ID
higgs upload list --image                           # list uploaded media
higgs soul-id list                                  # trained character refs
higgs soul-id create --name X --soul-2 --image <id1> --image <id2> ...    # train Soul ID (needs 5-20 image IDs)
higgs marketing-studio brand-kits list              # brand kits
higgs marketing-studio brand-kits fetch --url https://example.com --wait  # create brand kit from website
higgs marketing-studio ad-formats list              # 40+ ad format presets (Hero Statement, Star Review, etc.)
higgs marketing-studio dtc-ads generate --prompt "..." --format-id <uuid> --brand-kit-id <uuid> --wait
```

---

## Proven Workflows

### Locked-character ad production (the unlock)

For character-consistent ads across multiple shots/scenes:

1. **Soul V2 still** — generate a still image of the trained character in any scene
   ```bash
   higgs generate create text2image_soul_v2 \
     --prompt "scene description" \
     --custom_reference_id <soul_id> \
     --aspect_ratio 9:16 --quality 2k --wait
   ```
2. **Kling 3.0 image-to-video** — animate the still
   ```bash
   higgs generate create kling3_0 \
     --prompt "subtle motion animation matching the image, [voiceover line]" \
     --image /path/to/still.png \
     --aspect_ratio 9:16 --duration 7 --sound on --wait
   ```
3. Optionally concatenate with ffmpeg for multi-scene ads.

### Brand-aware static images (DTC Ads Engine)
```bash
higgs marketing-studio dtc-ads generate \
  --prompt "hero shot description" \
  --format-id <preset_uuid> \
  --brand-kit-id <kit_uuid> \
  --quality medium --resolution 2k --aspect-ratio 9:16 --wait
```

---

## Cost Reference (per gen, 5-second video)

| Model | Std Mode | Notes |
|---|---|---|
| Veo 3.1 Lite | 8 credits | Google frontier, audio strong |
| Veo 3.1 (full) | ~12-15 | |
| **Kling 3.0** | **10 credits** | image-to-video costs ~14 for 7s |
| Cinematic Studio Video V2 | 7.5 credits | Higgsfield proprietary, genre param (action/spectacle/etc) |
| Seedance 1.5 Pro | 4.8 credits | Cheap, decent quality |
| Seedance 2.0 | 22.5 std / 17.5 fast | Highest leaderboard quality, but Disney/MPA legal pressure — avoid for long-term commits |
| Wan 2.7 | 7.5 credits | |
| Soul Cinematic image | 0.12 credits | Basically free |
| Soul V2 image w/ Soul ID ref | ~1-2 credits | More than base Soul, less than video |
| DTC Ads Engine image | 3 credits | Branded, format preset, brand kit applied |

---

## Gotchas (Hard-Earned Lessons)

1. **`hf` alias is broken.** Even the CLI's own error hints suggest `hf auth login` — doesn't exist. Always use `higgs` or `higgsfield`.
2. **NSFW false positives DO happen AND you get charged.** A completely clean prompt about a man at a laptop got flagged once — 14 credits sunk. If a prompt fails NSFW, simplify and retry with cleaner language.
3. **Kling 3.0 image-to-video flag is `--image`** — NOT `--start_image`, `--start-image`, `--media`, or `--medias`. Each of those errors. The generic `--image` global media flag is what populates Kling's `medias` array.
4. **Image-to-video on Kling costs more than text-to-video** at same duration (~14 vs 10 credits for 7-sec).
5. **AI voice mispronounces uncommon words and brand names.** Uncommon product words and brand names came out wrong on Kling. Fixes (least → most effort): phonetic spelling in prompt (e.g. `YOUR-brand`), restructure script to use on-screen text overlay instead, switch to Veo 3.1 (better native audio), or generate silent video + ElevenLabs VO in post.
6. **OAuth login MUST be in a real Terminal**, not Claude Code `!` prefix — callback dies in subprocess.
7. **Brand kits are URL-scrape only** — no manual entry. Useless for capsules without live websites (e.g., a pre-launch brand).
8. **Brand kits are lightweight** — name, tagline, logo, screenshot, industry. No color palette, no design tokens. Functions more as visual reference than design system.
9. **Aggressive post-purchase upsell with dark patterns** — the "$119 secret ultra add-on" is unlimited access to OLDER versions of models you'd never use (Kling 2.5, Seedance 1.0, Hailuo 2.3). Skip.
10. **Garbled fake-letter signage is the default** — any "futuristic city," "holographic signs," or "billboards" in a prompt produces gibberish glyphs that aren't real letters. Fix: explicitly append `NO text, NO signs, NO writing, NO letters, NO billboards anywhere in the scene` to the prompt. Kling honors the negative and the scene reads clean.
11. **For a hero character, frame them walking TOWARD camera in a medium close-up** with the environment in shallow-DOF bokeh. Wide tracking shots from behind/side bury the subject — you can't tell it's "a beautiful woman" at distance. Toward-camera + 85mm-lens language in the prompt = face/outfit read clearly.
12. **Kling 3.0 sometimes fades the subject out mid-clip (~5s into an 8s gen)** — treats the back half as a transition and the subject dissolves. Fix: add explicit anti-fade negatives + a "single continuous take" instruction to the prompt: `Single continuous unbroken take ... stays fully visible and in frame from start to finish ... NO fade, NO fade out, NO fade to black, NO dissolve, NO transition, NO cut`.
13. **Soul V2 accepts only ONE reference image** (`medias` max 1). To composite a person + a product (e.g. UGC "holding the product"), use a multi-image model instead — **Nano Banana Pro (`nano_banana_2`)** takes multiple `--image` inputs, up to 4K, and (being Gemini) preserves real label text well.
14. **Marketing Studio UGC talking-video generation is WEB-DASHBOARD ONLY** — not exposed in the CLI. The CLI (`higgs marketing-studio`) only *manages assets* (avatars, products, hooks, brand-kits) and generates DTC ad **images** (`dtc-ads generate`). The avatar+product+script→lip-synced video render must be done manually on higgsfield.ai.
15. **`marketing-studio products create --image <upload_id>` is broken (Method Not Allowed) in CLI v0.1.40.** Use `products fetch --url <product page>` instead — scrapes the product (incl. real label image) from a live web page. This is also why Marketing Studio UGC renders the brand label correctly: it uses the scraped real product image, not a hallucinated label.
16. **UGC brand-name mispronunciation fix:** TTS reads brand/product words literally. Spell them PHONETICALLY in the script field — "YourBrand" → `Your-Brand`. Lip-sync stays intact (you're only steering the voice). Fallback: have the avatar say "this product"/"this stuff" and let the on-screen label carry the branding.
17. **Creating a custom avatar from a local photo (working method):** `upload create <file>` → `upload list --image --json` to grab the CloudFront URL → `marketing-studio avatars create --name X --image <upload_id> --image-url "<cloudfront_url>" --pinned`. Pass **BOTH** `--image` (upload id) AND `--image-url` (CloudFront url) — `--image-url` alone intermittently fails with `body.avatars.0.media: Field required`, and `--image` alone fails with "URL must be from an allowed domain." Passing both reliably works.
18. **Marketing Studio ad presets (e.g. "Product Crash") override your script.** Selecting a visual ad-format preset populates the "Hook prompt" field with its own canned text, and the Hook prompt — NOT the script box — drives what the avatar says/does. For a talking UGC ad: remove the visual preset (× the pill), put your spoken line in the Hook prompt, and pick a talking-head UGC hook.
19. **Soul IDs inherit composition bias from training frames.** One Soul ID (trained on outdoor-café footage) keeps generating over-the-shoulder shots with a second person in frame, and "tripod shot, centered composition" wording produced a 3-panel triptych. Fix: explicit solo/interior language — `solo portrait ... the room is empty except for him` broke the pattern (attempt 5 of 5).
20. **Phonetic brand spelling works on Kling 3.0 dialogue** — `Your-Brand-Name` in the prompt produced correct pronunciation first try (verified). Confirms gotcha #16's fix applies to Kling video gens, not just Marketing Studio UGC scripts.

---

## Output Conventions

- **Eval outputs:** `/tmp/catalyst-screenshots/higgsfield-eval/` (temp, may be cleaned)
- **Archived production assets:** `capsules/<capsule>/creative/higgsfield/v<N>/` (permanent)
- **Brand kit downloads:** save logo + screenshot to capsule's brand assets dir
- **Soul ID training frames:** can be re-extracted from source videos via `ffmpeg -ss <time> -i source.mp4 -frames:v 1 frame.png`

---

