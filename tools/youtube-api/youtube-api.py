#!/usr/bin/env python3
"""YouTube API CLI - OAuth2 auth, channel management, video upload."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Google API imports
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

KEYCHAIN_KEYS = {
    "client_id": "google-oauth-client-id",
    "client_secret": "google-oauth-client-secret",
    "refresh_token": "google-youtube-refresh-token",
    "access_token": "google-youtube-access-token",
}


def keychain_get(service):
    """Read a value from macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", "huxley", "-w"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def keychain_set(service, value):
    """Store a value in macOS Keychain."""
    subprocess.run(
        ["security", "add-generic-password", "-s", service, "-a", "huxley", "-w", value, "-U"],
        capture_output=True, check=True,
    )


def resolve_keychain_key(key_name, profile="default"):
    """Resolve a KEYCHAIN_KEYS entry to the actual keychain service name.

    client_id and client_secret are shared (same GCP project).
    refresh_token and access_token get a profile suffix for non-default profiles.
    """
    base = KEYCHAIN_KEYS[key_name]
    if key_name in ("client_id", "client_secret"):
        return base
    if profile == "default":
        return base
    return f"{base}-{profile}"


def get_credentials(profile="default"):
    """Get valid OAuth2 credentials, refreshing if needed."""
    client_id = keychain_get(resolve_keychain_key("client_id", profile))
    client_secret = keychain_get(resolve_keychain_key("client_secret", profile))
    refresh_token = keychain_get(resolve_keychain_key("refresh_token", profile))

    if not client_id or not client_secret:
        print("ERROR: OAuth client ID/secret not found in Keychain.")
        print("Run: security add-generic-password -s 'google-oauth-client-id' -a 'huxley' -w '<ID>'")
        sys.exit(1)

    if not refresh_token:
        login_hint = f"youtube-api.py --profile {profile} auth login" if profile != "default" else "youtube-api.py auth login"
        print(f"ERROR: No refresh token. Run '{login_hint}' first.")
        sys.exit(1)

    access_key = resolve_keychain_key("access_token", profile)
    creds = Credentials(
        token=keychain_get(access_key),
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )

    if not creds.valid:
        creds.refresh(Request())
        keychain_set(access_key, creds.token)

    return creds


def get_youtube(profile="default"):
    """Build authenticated YouTube API service."""
    return build("youtube", "v3", credentials=get_credentials(profile))


# ── Auth Commands ──────────────────────────────────────────────

def auth_login(args):
    """Run OAuth2 login flow (opens browser)."""
    profile = args.profile
    client_id = keychain_get(resolve_keychain_key("client_id", profile))
    client_secret = keychain_get(resolve_keychain_key("client_secret", profile))

    if not client_id or not client_secret:
        print("ERROR: OAuth client ID/secret not found in Keychain.")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=8085, prompt="consent", access_type="offline")

    keychain_set(resolve_keychain_key("refresh_token", profile), creds.refresh_token)
    keychain_set(resolve_keychain_key("access_token", profile), creds.token)

    print(f"Login successful! Tokens stored in Keychain (profile: {profile}).")


def auth_status(args):
    """Check if authentication is valid."""
    try:
        creds = get_credentials(args.profile)
        print(f"Authenticated: {'YES' if creds.valid else 'NO (needs refresh)'}")
        print(f"Token expiry: {creds.expiry}")
    except Exception as e:
        print(f"Not authenticated: {e}")


# ── Channel Commands ──────────────────────────────────────────

def channel_list(args):
    """List accessible channels."""
    yt = get_youtube(args.profile)
    resp = yt.channels().list(part="snippet,statistics", mine=True).execute()

    for ch in resp.get("items", []):
        print(f"Channel: {ch['snippet']['title']}")
        print(f"  ID: {ch['id']}")
        print(f"  Subscribers: {ch['statistics'].get('subscriberCount', 'hidden')}")
        print(f"  Videos: {ch['statistics']['videoCount']}")
        print(f"  Views: {ch['statistics']['viewCount']}")
        print()

    if args.json:
        print(json.dumps(resp, indent=2))


def channel_info(args):
    """Show authenticated channel details."""
    channel_list(args)


# ── Video Commands ──────────────────────────────────────────

def video_list(args):
    """List channel videos."""
    yt = get_youtube(args.profile)
    channels = yt.channels().list(part="contentDetails", mine=True).execute()
    uploads_id = channels["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    resp = yt.playlistItems().list(
        part="snippet", playlistId=uploads_id, maxResults=args.max
    ).execute()

    for item in resp.get("items", []):
        snippet = item["snippet"]
        print(f"{snippet['resourceId']['videoId']}  {snippet['title']}")
        print(f"  Published: {snippet['publishedAt']}")
        print()

    if args.json:
        print(json.dumps(resp, indent=2))


def video_upload(args):
    """Upload a video to YouTube."""
    if not os.path.exists(args.file):
        print(f"ERROR: File not found: {args.file}")
        sys.exit(1)

    file_size = os.path.getsize(args.file)
    print(f"Uploading: {args.file} ({file_size / 1024 / 1024:.1f} MB)")
    print(f"Title: {args.title}")
    print(f"Privacy: {args.privacy}")

    if args.dry_run:
        print("[DRY RUN] Would upload with above settings.")
        return

    body = {
        "snippet": {
            "title": args.title,
            "description": args.description or "",
            "tags": args.tags.split(",") if args.tags else [],
            "categoryId": "10",  # Music
        },
        "status": {
            "privacyStatus": args.privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    yt = get_youtube(args.profile)
    media = MediaFileUpload(args.file, resumable=True, chunksize=10 * 1024 * 1024)

    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  Uploading... {pct}%")

    video_id = response["id"]
    print(f"\nUpload complete!")
    print(f"Video ID: {video_id}")
    print(f"URL: https://youtube.com/watch?v={video_id}")

    if args.json:
        print(json.dumps(response, indent=2))

    return video_id


def video_get(args):
    """Get video details."""
    yt = get_youtube(args.profile)
    resp = yt.videos().list(part="snippet,statistics,status", id=args.video_id).execute()

    for v in resp.get("items", []):
        print(f"Title: {v['snippet']['title']}")
        print(f"Views: {v['statistics'].get('viewCount', 0)}")
        print(f"Likes: {v['statistics'].get('likeCount', 0)}")
        print(f"Privacy: {v['status']['privacyStatus']}")
        print()

    if args.json:
        print(json.dumps(resp, indent=2))


def video_update(args):
    """Update a video's metadata (title, description, tags, category)."""
    yt = get_youtube(args.profile)

    # Fetch current video data
    resp = yt.videos().list(part="snippet", id=args.video_id).execute()
    items = resp.get("items", [])
    if not items:
        print(f"ERROR: Video not found: {args.video_id}")
        sys.exit(1)

    current_snippet = items[0]["snippet"]
    changes = {}

    # Build updated snippet, merging only provided fields
    updated_snippet = {
        "title": current_snippet["title"],
        "description": current_snippet.get("description", ""),
        "tags": current_snippet.get("tags", []),
        "categoryId": current_snippet.get("categoryId", "10"),
    }

    if args.title is not None:
        changes["title"] = (current_snippet["title"], args.title)
        updated_snippet["title"] = args.title

    if args.description is not None:
        changes["description"] = (
            current_snippet.get("description", "")[:80] + "...",
            args.description[:80] + "...",
        )
        updated_snippet["description"] = args.description

    if args.tags is not None:
        new_tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        changes["tags"] = (current_snippet.get("tags", []), new_tags)
        updated_snippet["tags"] = new_tags

    if args.category is not None:
        changes["categoryId"] = (current_snippet.get("categoryId", ""), args.category)
        updated_snippet["categoryId"] = args.category

    if not changes:
        print("No changes specified. Use --title, --description, --tags, or --category.")
        return

    # Show before/after for changed fields
    print(f"Video: {args.video_id}")
    print(f"Changes:")
    for field, (before, after) in changes.items():
        print(f"  {field}:")
        print(f"    Before: {before}")
        print(f"    After:  {after}")

    if args.dry_run:
        print("\n[DRY RUN] Would update with above changes.")
        return

    # Execute update — must include all snippet fields
    body = {
        "id": args.video_id,
        "snippet": updated_snippet,
    }
    result = yt.videos().update(part="snippet", body=body).execute()

    print(f"\nUpdate successful!")
    print(f"Title: {result['snippet']['title']}")

    if args.json:
        print(json.dumps(result, indent=2))


# ── Playlist Commands ──────────────────────────────────────────

def playlist_create(args):
    """Create a new playlist."""
    yt = get_youtube(args.profile)

    body = {
        "snippet": {
            "title": args.title,
            "description": args.description or "",
        },
        "status": {
            "privacyStatus": args.privacy,
        },
    }

    if args.dry_run:
        print(f"[DRY RUN] Would create playlist:")
        print(f"  Title: {args.title}")
        print(f"  Description: {args.description or '(none)'}")
        print(f"  Privacy: {args.privacy}")
        return

    result = yt.playlists().insert(part="snippet,status", body=body).execute()
    playlist_id = result["id"]

    print(f"Playlist created!")
    print(f"  ID: {playlist_id}")
    print(f"  Title: {result['snippet']['title']}")
    print(f"  URL: https://youtube.com/playlist?list={playlist_id}")

    if args.json:
        print(json.dumps(result, indent=2))


def playlist_add(args):
    """Add videos to a playlist."""
    yt = get_youtube(args.profile)

    if args.dry_run:
        print(f"[DRY RUN] Would add {len(args.video_ids)} video(s) to playlist {args.playlist_id}:")
        for vid in args.video_ids:
            print(f"  - {vid}")
        return

    for vid in args.video_ids:
        body = {
            "snippet": {
                "playlistId": args.playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": vid,
                },
            },
        }

        try:
            result = yt.playlistItems().insert(part="snippet", body=body).execute()
            print(f"Added {vid} to playlist {args.playlist_id} (position: {result['snippet'].get('position', '?')})")
        except Exception as e:
            print(f"ERROR adding {vid}: {e}")


# ── Comment Commands ──────────────────────────────────────────

def comment_post(args):
    """Post a top-level comment on a video."""
    yt = get_youtube(args.profile)

    if args.dry_run:
        print(f"[DRY RUN] Would post comment on video {args.video_id}:")
        print(f"  Text: {args.text}")
        return

    body = {
        "snippet": {
            "videoId": args.video_id,
            "topLevelComment": {
                "snippet": {
                    "textOriginal": args.text,
                },
            },
        },
    }

    result = yt.commentThreads().insert(part="snippet", body=body).execute()
    comment_id = result["id"]

    print(f"Comment posted!")
    print(f"  Comment ID: {comment_id}")
    print(f"  Video: {args.video_id}")
    print(f"  Text: {args.text[:100]}{'...' if len(args.text) > 100 else ''}")

    if args.json:
        print(json.dumps(result, indent=2))


# ── CLI Parser ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="YouTube API CLI")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument("--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--profile", default="default", help="Channel profile (e.g. my-channel)")

    sub = parser.add_subparsers(dest="command")

    # Auth
    auth = sub.add_parser("auth")
    auth_sub = auth.add_subparsers(dest="auth_action")
    auth_sub.add_parser("login")
    auth_sub.add_parser("status")
    auth_sub.add_parser("refresh")

    # Channel
    ch = sub.add_parser("channel")
    ch_sub = ch.add_subparsers(dest="channel_action")
    ch_sub.add_parser("info")
    ch_sub.add_parser("list")

    # Video
    vid = sub.add_parser("video")
    vid_sub = vid.add_subparsers(dest="video_action")

    vid_list = vid_sub.add_parser("list")
    vid_list.add_argument("--max", type=int, default=10)

    vid_get = vid_sub.add_parser("get")
    vid_get.add_argument("video_id")

    vid_upload = vid_sub.add_parser("upload")
    vid_upload.add_argument("file")
    vid_upload.add_argument("--title", required=True)
    vid_upload.add_argument("--description", default="")
    vid_upload.add_argument("--tags", default="")
    vid_upload.add_argument("--privacy", default="unlisted", choices=["public", "private", "unlisted"])

    vid_update = vid_sub.add_parser("update")
    vid_update.add_argument("video_id")
    vid_update.add_argument("--title", default=None, help="New title")
    vid_update.add_argument("--description", default=None, help="New description")
    vid_update.add_argument("--tags", default=None, help="Comma-separated tags")
    vid_update.add_argument("--category", default=None, help="Category ID (e.g. 10 for Music)")

    # Playlist
    pl = sub.add_parser("playlist")
    pl_sub = pl.add_subparsers(dest="playlist_action")

    pl_create = pl_sub.add_parser("create")
    pl_create.add_argument("--title", required=True)
    pl_create.add_argument("--description", default="")
    pl_create.add_argument("--privacy", default="public", choices=["public", "private", "unlisted"])

    pl_add = pl_sub.add_parser("add")
    pl_add.add_argument("playlist_id")
    pl_add.add_argument("video_ids", nargs="+", help="One or more video IDs to add")

    # Comment
    cmt = sub.add_parser("comment")
    cmt_sub = cmt.add_subparsers(dest="comment_action")

    cmt_post = cmt_sub.add_parser("post")
    cmt_post.add_argument("video_id")
    cmt_post.add_argument("--text", required=True, help="Comment text")

    args = parser.parse_args()

    # Print profile header for non-default profiles
    if args.profile != "default":
        print(f"[Profile: {args.profile}]")

    if args.command == "auth":
        if args.auth_action == "login":
            auth_login(args)
        elif args.auth_action == "status":
            auth_status(args)
        elif args.auth_action == "refresh":
            get_credentials(args.profile)
            print("Token refreshed.")
    elif args.command == "channel":
        if args.channel_action in ("info", "list"):
            channel_list(args)
    elif args.command == "video":
        if args.video_action == "list":
            video_list(args)
        elif args.video_action == "get":
            video_get(args)
        elif args.video_action == "upload":
            video_upload(args)
        elif args.video_action == "update":
            video_update(args)
    elif args.command == "playlist":
        if args.playlist_action == "create":
            playlist_create(args)
        elif args.playlist_action == "add":
            playlist_add(args)
        else:
            pl.print_help()
    elif args.command == "comment":
        if args.comment_action == "post":
            comment_post(args)
        else:
            cmt.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
