---
name: youtube-api
description: YouTube Data API v3 and Analytics integration for channel management, video upload, comments, and analytics
when: Managing YouTube channels, uploading videos, checking analytics, moderating comments, YouTube OAuth setup
allowed-tools:
  - Bash
  - Read
metadata:
  version: "1.0.0"
  authority: "{{ORCHESTRATOR_NAME}}"
  script: "tools/youtube-api/youtube-api.py"
  scope: "YouTube Data API v3 + YouTube Analytics API"
  last_updated: "2026-02-20"
---

# YouTube API Integration Skill

## Purpose
YouTube CLI covering channel management, video upload, comments, and analytics via YouTube Data API v3 and YouTube Analytics API. OAuth2 token management with Keychain storage. No third-party dependencies.

## Primary Agents
- **{{ORCHESTRATOR_NAME}}** (authority) -- Can invoke directly
- **CMO** -- YouTube content strategy, analytics, ad integration
- **Automator** -- n8n workflow integration with YouTube APIs

## Prerequisites
- OAuth credentials in macOS Keychain (`google-oauth-client-id`, `google-oauth-client-secret`)
- Authenticated via `youtube-api.py auth login` (stores refresh token in Keychain)
- GCP Project: `project-c00690bc-f17d-4837-bc7` ("Huxley Digital")

## Quick Reference

```bash
# Auth
python3 tools/youtube-api/youtube-api.py auth login      # OAuth flow (opens browser)
python3 tools/youtube-api/youtube-api.py auth status     # Check token validity
python3 tools/youtube-api/youtube-api.py auth refresh    # Refresh access token

# Channels
python3 tools/youtube-api/youtube-api.py channel info    # Authenticated channel details
python3 tools/youtube-api/youtube-api.py channel list    # List accessible channels

# Videos
python3 tools/youtube-api/youtube-api.py video list [--max N]                # List videos
python3 tools/youtube-api/youtube-api.py video get VIDEO_ID                  # Video details
python3 tools/youtube-api/youtube-api.py video upload FILE --title T [--description D] [--tags T] [--privacy public|private|unlisted]

# Comments
python3 tools/youtube-api/youtube-api.py comments list VIDEO_ID [--limit N]  # List comments
python3 tools/youtube-api/youtube-api.py comments reply COMMENT_ID --text T  # Reply

# Analytics
python3 tools/youtube-api/youtube-api.py analytics channel [--start-date D] [--end-date D]
python3 tools/youtube-api/youtube-api.py analytics video VIDEO_ID [--start-date D] [--end-date D]
```

## Output Flags
- `--json` -- JSON output (default is table)
- `--dry-run` -- Preview mutations without executing
- `--verbose` -- Debug logging

## OAuth Scopes
`youtube.readonly`, `youtube.upload`, `youtube.force-ssl`, `yt-analytics.readonly`

## Token Storage (Keychain)
| Key | Purpose |
|-----|---------|
| `google-oauth-client-id` | OAuth client ID |
| `google-oauth-client-secret` | OAuth client secret |
| `google-youtube-refresh-token` | Persistent refresh token |
| `google-youtube-access-token` | Short-lived access token |
