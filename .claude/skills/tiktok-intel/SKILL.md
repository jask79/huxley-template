---
name: tiktok-intel
description: TikTok competitive intelligence via browser scraping — trending content, top ads, hashtag analytics, search, competitor profiles, and TikTok Shop product research
when: TikTok trend research, competitor analysis, hashtag analysis, trending content discovery, ad competitive intelligence, TikTok search, profile analysis, TikTok Shop products
allowed-tools:
  - Bash
  - Read
metadata:
  version: "1.0.0"
  authority: "{{ORCHESTRATOR_NAME}}"
  script: "tools/tiktok-intel/cli.py"
  scope: "TikTok Creative Center scraping (no auth required)"
  last_updated: "2026-02-23"
  phase: "2"
---

# TikTok Intelligence Skill

## Purpose
Brand-agnostic competitive intelligence CLI that scrapes TikTok Creative Center and tiktok.com for trending hashtags, songs, creators, videos, top-performing ads, hashtag analytics, search results, competitor profiles, and TikTok Shop products. Complements the `tiktok` skill (API-based) with browser-based data collection that requires no credentials.

**No API keys or OAuth tokens required. All data sources are publicly accessible.**

## Primary Agents
- **CMO** — Trend research for content strategy, ad competitive analysis
- **Ecomm Bro** — Product/ad trend intelligence for e-commerce
- **Research Agent** — Competitive landscape analysis

## Prerequisites
- Python 3.10+
- Playwright + Chromium: `pip3 install playwright playwright-stealth && playwright install chromium`
- Install both packages with the command above before first use

## Quick Reference

### Global Flags
| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output |
| `--dry-run` | Preview without launching browser |
| `-v` / `--verbose` | Detailed logging |
| `--cache-ttl N` | Cache TTL in seconds (default: 3600) |
| `--no-cache` | Skip cache, scrape fresh |
| `--output-dir DIR` | Save JSON results to directory |
| `--no-headless` | Show browser window (debugging) |

### Phase 1 Commands (Creative Center)

#### Trending Content
```bash
# Trending hashtags (default)
python3 tools/tiktok-intel/cli.py trends --type hashtags --country US --json

# Trending songs in beauty industry
python3 tools/tiktok-intel/cli.py trends --type songs --industry beauty

# Trending creators
python3 tools/tiktok-intel/cli.py trends --type creators --country US --limit 50

# Trending videos
python3 tools/tiktok-intel/cli.py trends --type videos
```

#### Top Performing Ads
```bash
# Top ads sorted by reach
python3 tools/tiktok-intel/cli.py top-ads --sort reach --json

# Top conversion ads in specific region
python3 tools/tiktok-intel/cli.py top-ads --objective Conversions --region US

# Top ads sorted by CTR
python3 tools/tiktok-intel/cli.py top-ads --sort ctr --limit 10
```

#### Hashtag Analytics
```bash
# Detailed hashtag analysis
python3 tools/tiktok-intel/cli.py hashtags --hashtag ootd --json

# Hashtag analysis for specific country
python3 tools/tiktok-intel/cli.py hashtags --hashtag proteintok --country US
```

### Phase 2 Commands (tiktok.com Scraping)

#### Search Videos & Users
```bash
# Search for videos about a topic
python3 tools/tiktok-intel/cli.py search -q 'protein powder' --type video --limit 30

# Search for user profiles
python3 tools/tiktok-intel/cli.py search -q 'fitness influencer' --type user --json

# Default search (video type, 20 results)
python3 tools/tiktok-intel/cli.py search -q 'morning routine'
```

#### Competitor Profile Analysis
```bash
# Basic profile overview
python3 tools/tiktok-intel/cli.py competitor -u charlidamelio --json

# Profile with recent video engagement metrics
python3 tools/tiktok-intel/cli.py competitor -u therock --videos --limit 20

# Quick competitor check (strip @ automatically)
python3 tools/tiktok-intel/cli.py competitor -u @khaby.lame --videos
```

#### TikTok Shop Products
```bash
# Search shop products by keyword
python3 tools/tiktok-intel/cli.py shop-products -q 'skincare serum' --limit 30

# Browse specific shop inventory
python3 tools/tiktok-intel/cli.py shop-products --shop-id 12345 --json

# Product research with JSON output
python3 tools/tiktok-intel/cli.py shop-products -q 'wireless earbuds' --json
```

#### Cache Management
```bash
python3 tools/tiktok-intel/cli.py cache-clear
python3 tools/tiktok-intel/cli.py cache-stats
```

## Output Format (--json)
All commands return a consistent ScrapeResult envelope:
```json
{
  "command": "trends",
  "success": true,
  "data": [...],
  "count": 20,
  "filters": {"type": "hashtags", "country": "US"},
  "scraped_at": "2026-02-23T15:30:00Z",
  "cache_hit": false,
  "duration_ms": 4523,
  "errors": []
}
```

## Relationship to `tiktok` Skill
| | tiktok | tiktok-intel |
|---|---|---|
| Data source | HTTP APIs | Browser scraping |
| Auth | OAuth per brand | None (public) |
| Scope | Manage your TikTok | Research competitors/trends |
| Use together | Post content (tiktok) | Find what to post (tiktok-intel) |

## What This Skill Does NOT Handle
- TikTok account management (use `tiktok` skill)
- Posting or uploading content
- Any write operations on TikTok
- Comment/DM scraping (not planned)
- Live stream data collection (not planned)
