---
name: youtube-intel
description: YouTube competitive intelligence toolkit — keyword research, SEO scoring, VPH tracking, competitor analysis, trend discovery, content ideation, channel auditing, and best posting times. Replaces VidIQ for personal use.
when: YouTube keyword research, SEO analysis, VPH tracking, competitor monitoring, trend discovery, content ideas, channel audit, best posting time, YouTube analytics
allowed-tools:
  - Bash
  - Read
metadata:
  version: "1.0.0"
  authority: "{{ORCHESTRATOR_NAME}}"
  script: "tools/youtube-intel/cli.py"
  scope: "YouTube Data API v3 (Service Account) + Analytics API (OAuth)"
  last_updated: "2026-02-24"
---

# YouTube Intel Skill

## Purpose
Personal YouTube intelligence toolkit that replaces VidIQ ($199/yr SaaS). Provides keyword competition analysis, SEO scoring, Views Per Hour tracking, competitor channel monitoring, trend discovery, AI-powered content ideation, channel health auditing, and optimal posting time analysis.

**Auth:** Service Account for most commands (automatic), OAuth for analytics (audit, besttime).

## Primary Agents
- **CMO** -- Content strategy, keyword research, trend analysis
- **Research Agent** -- Competitive landscape, keyword opportunity analysis

## Prerequisites
- Python 3.10+ (stdlib only, no pip packages required)
- Google Service Account credentials in macOS Keychain (configure before first use)
- Optional: OAuth refresh token for analytics commands (audit, besttime)

## Quick Reference

### Global Flags
| Flag | Description |
|------|-------------|
| `--debug` | Enable debug output with full tracebacks |

### Keyword Research
```bash
# Analyze a keyword's competition and opportunity
python3 tools/youtube-intel/cli.py keyword analyze "python tutorial"

# Side-by-side comparison of two keywords
python3 tools/youtube-intel/cli.py keyword compare "python tutorial" "javascript tutorial"

# Analyze more search results for higher confidence
python3 tools/youtube-intel/cli.py keyword analyze "4runner build" --results 30
```

**Output:** Competition score (0-100), opportunity score (0-100), volume proxy, difficulty label, signal breakdown (authority, view momentum, freshness, engagement), content gap detection, recommendation.

### SEO Scoring
```bash
# Full SEO score with factor breakdown
python3 tools/youtube-intel/cli.py seo score dQw4w9WgXcQ

# Score + heuristic improvement suggestions
python3 tools/youtube-intel/cli.py seo suggest dQw4w9WgXcQ

# Score + AI-powered suggestions (uses Claude API)
python3 tools/youtube-intel/cli.py seo suggest dQw4w9WgXcQ --ai
```

**Output:** Overall score (0-100), letter grade, 7-factor breakdown (title, description, captions, metadata, technical, tags, engagement), actionable suggestions.

### VPH Tracking
```bash
# Start tracking a video's Views Per Hour
python3 tools/youtube-intel/cli.py vph track dQw4w9WgXcQ

# Show VPH data for a tracked video
python3 tools/youtube-intel/cli.py vph dQw4w9WgXcQ

# List all tracked videos with latest VPH
python3 tools/youtube-intel/cli.py vph list

# Stop tracking
python3 tools/youtube-intel/cli.py vph untrack dQw4w9WgXcQ
```

### Competitor Intelligence
```bash
# Track a competitor channel
python3 tools/youtube-intel/cli.py competitor add @mkbhd

# List all tracked competitors
python3 tools/youtube-intel/cli.py competitor list

# Full competitor comparison report
python3 tools/youtube-intel/cli.py competitor report

# Stop tracking
python3 tools/youtube-intel/cli.py competitor remove @mkbhd
```

### Trend Discovery
```bash
# Mine YouTube autocomplete for trending topics
python3 tools/youtube-intel/cli.py trends "tech reviews"

# Go deeper (more autocomplete levels)
python3 tools/youtube-intel/cli.py trends "fitness" --depth 5
```

### Content Ideation
```bash
# Generate 10 video ideas (heuristic)
python3 tools/youtube-intel/cli.py ideas --niche "programming"

# AI-powered ideation (uses Claude API)
python3 tools/youtube-intel/cli.py ideas --niche "4runner build" --ai

# More ideas
python3 tools/youtube-intel/cli.py ideas --count 20 --niche "overlanding"
```

### Channel Audit (requires OAuth)
```bash
# Full channel health audit (last 28 days)
python3 tools/youtube-intel/cli.py audit

# Audit specific channel over custom period
python3 tools/youtube-intel/cli.py audit --channel UCxxxxxxxx --days 90
```

### Best Posting Time (requires OAuth)
```bash
# Find optimal posting windows
python3 tools/youtube-intel/cli.py besttime

# Custom analysis period
python3 tools/youtube-intel/cli.py besttime --days 90
```

### Poller Management
```bash
# Run one poll cycle manually
python3 tools/youtube-intel/cli.py poller run --mode vph

# Run both VPH and competitor polls
python3 tools/youtube-intel/cli.py poller run --mode all

# Dry run (no DB writes)
python3 tools/youtube-intel/cli.py poller run --mode vph --dry-run

# Check poller status and last run time
python3 tools/youtube-intel/cli.py poller status
```

## Auth Architecture

| Command Group | Auth Required | Auto? |
|---------------|---------------|-------|
| keyword, seo, vph, competitor, trends, ideas | Service Account | Yes (Keychain) |
| audit, besttime | OAuth + Service Account | OAuth needs `youtube-api.py auth login` |
| ideas --ai, seo suggest --ai | + Anthropic API key | Yes (Keychain) |

## Scoring Algorithms

- **Outlier Detection:** MAD-based z-scores, exponential decay velocity, engagement dimension, subscriber-normalized ratios
- **Keyword Competition:** 4-signal weighted (authority 0.20, momentum 0.30, freshness 0.25, engagement 0.25), independent opportunity axis
- **SEO Scoring:** Keyword-aware, 7 factors, pre/post-publish split, FactorScore dataclasses

## Database
- **Path:** `monitoring/youtube-intel.db` (SQLite, WAL mode)
- **Tables:** tracked_videos, vph_snapshots, competitors, competitor_snapshots, keyword_cache, video_seo_scores

## LaunchAgent (Automated Polling)
- **Plist:** `tools/youtube-intel/com.huxley.youtube-intel-poller.plist`
- **Schedule:** Hourly VPH polls
- **Install:** `cp tools/youtube-intel/com.huxley.youtube-intel-poller.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.huxley.youtube-intel-poller.plist`

## What This Skill Does NOT Handle
- Video uploading (use `youtube-api` skill)
- Comment management (use `youtube-api` skill)
- OAuth consent flow (run `youtube-api.py auth login` separately)
- YouTube Shorts-specific analytics (not yet implemented)
