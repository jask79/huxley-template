-- YouTube Intel — SQLite Schema
-- Database: monitoring/youtube-intel.db

CREATE TABLE IF NOT EXISTS tracked_videos (
    video_id        TEXT PRIMARY KEY,
    channel_id      TEXT NOT NULL,
    title           TEXT NOT NULL,
    published_at    TEXT,
    added_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    tracking_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS vph_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        TEXT NOT NULL REFERENCES tracked_videos(video_id),
    view_count      INTEGER NOT NULL,
    snapshot_time   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_vph_video_time
    ON vph_snapshots(video_id, snapshot_time DESC);

CREATE TABLE IF NOT EXISTS competitors (
    channel_id      TEXT PRIMARY KEY,
    channel_name    TEXT NOT NULL,
    channel_handle  TEXT,
    added_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS competitor_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id      TEXT NOT NULL REFERENCES competitors(channel_id),
    subscriber_count INTEGER NOT NULL DEFAULT 0,
    video_count      INTEGER NOT NULL DEFAULT 0,
    view_count       INTEGER NOT NULL DEFAULT 0,
    snapshot_time    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_comp_snap_channel_time
    ON competitor_snapshots(channel_id, snapshot_time DESC);

CREATE TABLE IF NOT EXISTS keyword_cache (
    keyword         TEXT PRIMARY KEY,
    search_volume_proxy INTEGER NOT NULL DEFAULT 0,
    competition_score   REAL NOT NULL DEFAULT 0.0,
    related_terms       TEXT NOT NULL DEFAULT '[]',  -- JSON array
    cached_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS video_seo_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        TEXT NOT NULL,
    overall_score   REAL NOT NULL DEFAULT 0.0,
    breakdown       TEXT NOT NULL DEFAULT '{}',  -- JSON object
    scored_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_seo_video_time
    ON video_seo_scores(video_id, scored_at DESC);
