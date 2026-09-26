#!/usr/bin/env python3
"""
Temporal Memory MCP Server for Huxley

Adds time-range querying to Huxley's memory system. Enables {{ORCHESTRATOR_NAME}} to answer
questions like "what did we decide about X three weeks ago?" by searching
across decisions, patterns, and indexed conversation/session documents.

Transport: stdio
Database: registry/pattern_learning.db (SQLite, auto-created if missing)
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CATALYST_ROOT = Path(os.environ.get(
    "CATALYST_ROOT",
    Path(__file__).resolve().parent.parent.parent,  # tools/memory/../../
))
DB_PATH = CATALYST_ROOT / "registry" / "pattern_learning.db"
CONVERSATIONS_DIR = CATALYST_ROOT / "memory" / "conversations"
CAPSULE_SESSIONS_DIR = CATALYST_ROOT / "memory" / "capsule-sessions"

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _get_conn() -> sqlite3.Connection:
    """Return a connection to the SQLite database, creating dirs if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they don't already exist."""
    cur = conn.cursor()

    # decisions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            decision_text TEXT NOT NULL,
            context TEXT,
            agent_name TEXT,
            capsule TEXT,
            tags TEXT,
            created_at TEXT NOT NULL,
            session_id TEXT
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_decisions_created_at
        ON decisions(created_at)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_decisions_topic
        ON decisions(topic)
    """)

    # document_index table (for conversation & session files)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_index (
            doc_path TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            mtime_epoch REAL NOT NULL,
            modified_at TEXT NOT NULL,
            summary TEXT,
            indexed_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_index_modified_at
        ON document_index(modified_at)
    """)

    # Index on existing patterns table if it exists
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='patterns'"
    )
    if cur.fetchone():
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_created_at
            ON patterns(created_at)
        """)

    conn.commit()


def _index_markdown_files(conn: sqlite3.Connection) -> int:
    """Scan conversation and capsule-session markdown files into document_index.

    Idempotent: skips files whose mtime hasn't changed since last index.
    Returns the number of newly indexed / updated files.
    """
    indexed = 0
    now_iso = datetime.now().isoformat()

    dirs_to_scan = [
        (CONVERSATIONS_DIR, "conversation"),
        (CAPSULE_SESSIONS_DIR, "capsule_session"),
    ]

    for directory, doc_type in dirs_to_scan:
        if not directory.is_dir():
            continue
        for md_file in directory.glob("*.md"):
            if not md_file.is_file():
                continue
            mtime = md_file.stat().st_mtime

            # Check if already indexed with same mtime
            row = conn.execute(
                "SELECT mtime_epoch FROM document_index WHERE doc_path = ?",
                (str(md_file),),
            ).fetchone()
            if row and abs(row["mtime_epoch"] - mtime) < 0.01:
                continue  # unchanged

            # Read first ~500 chars as summary
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
                summary = text[:500].strip()
            except Exception:
                summary = ""

            modified_at = datetime.fromtimestamp(mtime).isoformat()

            conn.execute(
                """
                INSERT OR REPLACE INTO document_index
                    (doc_path, filename, doc_type, mtime_epoch, modified_at, summary, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(md_file),
                    md_file.name,
                    doc_type,
                    mtime,
                    modified_at,
                    summary,
                    now_iso,
                ),
            )
            indexed += 1

    conn.commit()
    return indexed


def _time_range_filter(
    time_range: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[str, str]:
    """Convert a time_range keyword into (start_iso, end_iso)."""
    now = datetime.now()
    end_iso = end_date or now.isoformat()

    if time_range == "custom" and start_date:
        return (start_date, end_iso)

    deltas = {
        "last_week": timedelta(weeks=1),
        "last_month": timedelta(days=30),
        "last_3_months": timedelta(days=90),
    }
    delta = deltas.get(time_range, timedelta(days=30))
    start_iso = start_date or (now - delta).isoformat()
    return (start_iso, end_iso)


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("temporal-memory")


@mcp.tool()
def search_memories_temporal(
    query: str,
    time_range: str = "last_month",
    start_date: str = "",
    end_date: str = "",
    agent_name: str = "",
    limit: int = 10,
) -> str:
    """Search memories across decisions, patterns, and documents filtered by time range.

    Args:
        query: Search term to match against memory content.
        time_range: One of "last_week", "last_month", "last_3_months", "custom".
        start_date: ISO date for custom range start (used when time_range="custom").
        end_date: ISO date for custom range end (optional, defaults to now).
        agent_name: Filter by agent name (optional).
        limit: Maximum results to return (default 10).

    Returns:
        JSON array of matching memories sorted newest-first with source, timestamp, content.
    """
    conn = _get_conn()
    _ensure_tables(conn)
    _index_markdown_files(conn)

    start_iso, end_iso = _time_range_filter(
        time_range,
        start_date or None,
        end_date or None,
    )
    q_like = f"%{query}%"
    results: list[dict] = []

    # --- Search decisions ---
    sql_decisions = """
        SELECT decision_id, topic, decision_text, context, agent_name, capsule,
               tags, created_at, 'decisions' AS source
        FROM decisions
        WHERE created_at BETWEEN ? AND ?
          AND (topic LIKE ? OR decision_text LIKE ? OR context LIKE ?)
    """
    params_decisions: list = [start_iso, end_iso, q_like, q_like, q_like]
    if agent_name:
        sql_decisions += " AND agent_name = ?"
        params_decisions.append(agent_name)
    sql_decisions += " ORDER BY created_at DESC LIMIT ?"
    params_decisions.append(limit)

    for row in conn.execute(sql_decisions, params_decisions):
        results.append({
            "source": "decisions",
            "id": row["decision_id"],
            "topic": row["topic"],
            "content": row["decision_text"],
            "context": row["context"],
            "agent_name": row["agent_name"],
            "capsule": row["capsule"],
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "timestamp": row["created_at"],
        })

    # --- Search patterns (if table exists) ---
    has_patterns = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='patterns'"
    ).fetchone()
    if has_patterns:
        sql_patterns = """
            SELECT pattern_id, pattern_type, pattern_data, context_tags,
                   created_at, 'patterns' AS source
            FROM patterns
            WHERE created_at BETWEEN ? AND ?
              AND (pattern_data LIKE ? OR context_tags LIKE ?)
            ORDER BY created_at DESC LIMIT ?
        """
        for row in conn.execute(sql_patterns, [start_iso, end_iso, q_like, q_like, limit]):
            results.append({
                "source": "patterns",
                "id": row["pattern_id"],
                "type": row["pattern_type"],
                "content": row["pattern_data"],
                "tags": row["context_tags"],
                "timestamp": row["created_at"],
            })

    # --- Search document_index ---
    sql_docs = """
        SELECT doc_path, filename, doc_type, modified_at, summary,
               'document_index' AS source
        FROM document_index
        WHERE modified_at BETWEEN ? AND ?
          AND (filename LIKE ? OR summary LIKE ?)
        ORDER BY modified_at DESC LIMIT ?
    """
    for row in conn.execute(sql_docs, [start_iso, end_iso, q_like, q_like, limit]):
        results.append({
            "source": "document_index",
            "filename": row["filename"],
            "doc_type": row["doc_type"],
            "path": row["doc_path"],
            "summary": row["summary"][:300] if row["summary"] else "",
            "timestamp": row["modified_at"],
        })

    conn.close()

    # Sort all results newest-first, then cap at limit
    results.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    results = results[:limit]

    return json.dumps(results, indent=2)


@mcp.tool()
def get_decisions_timeline(topic: str, days_back: int = 30) -> str:
    """Get a chronological timeline of decisions and related documents for a topic.

    Args:
        topic: Topic string to search for.
        days_back: How many days to look back (default 30).

    Returns:
        JSON array of decisions and documents sorted chronologically (oldest first).
    """
    conn = _get_conn()
    _ensure_tables(conn)
    _index_markdown_files(conn)

    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
    q_like = f"%{topic}%"
    results: list[dict] = []

    # Decisions matching topic
    for row in conn.execute(
        """
        SELECT decision_id, topic, decision_text, context, agent_name,
               capsule, tags, created_at
        FROM decisions
        WHERE created_at >= ?
          AND (topic LIKE ? OR decision_text LIKE ? OR context LIKE ?)
        ORDER BY created_at ASC
        """,
        [cutoff, q_like, q_like, q_like],
    ):
        results.append({
            "source": "decision",
            "id": row["decision_id"],
            "topic": row["topic"],
            "content": row["decision_text"],
            "context": row["context"],
            "agent_name": row["agent_name"],
            "capsule": row["capsule"],
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "timestamp": row["created_at"],
        })

    # Documents matching topic
    for row in conn.execute(
        """
        SELECT doc_path, filename, doc_type, modified_at, summary
        FROM document_index
        WHERE modified_at >= ?
          AND (filename LIKE ? OR summary LIKE ?)
        ORDER BY modified_at ASC
        """,
        [cutoff, q_like, q_like],
    ):
        results.append({
            "source": "document",
            "filename": row["filename"],
            "doc_type": row["doc_type"],
            "path": row["doc_path"],
            "summary": row["summary"][:300] if row["summary"] else "",
            "timestamp": row["modified_at"],
        })

    conn.close()

    # Merge and sort chronologically (oldest first)
    results.sort(key=lambda r: r.get("timestamp", ""))

    return json.dumps(results, indent=2)


@mcp.tool()
def memory_stats() -> str:
    """Get aggregate statistics about the temporal memory system.

    Returns:
        JSON object with counts by time period, top topics, and active capsules.
    """
    conn = _get_conn()
    _ensure_tables(conn)
    _index_markdown_files(conn)

    now = datetime.now()
    periods = {
        "last_week": (now - timedelta(weeks=1)).isoformat(),
        "last_month": (now - timedelta(days=30)).isoformat(),
        "last_3_months": (now - timedelta(days=90)).isoformat(),
    }

    stats: dict = {}

    # Total decisions
    stats["total_decisions"] = conn.execute(
        "SELECT COUNT(*) FROM decisions"
    ).fetchone()[0]

    # Decisions by period
    stats["decisions_by_period"] = {}
    for label, cutoff in periods.items():
        stats["decisions_by_period"][label] = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE created_at >= ?", (cutoff,)
        ).fetchone()[0]

    # Total documents indexed
    stats["total_documents"] = conn.execute(
        "SELECT COUNT(*) FROM document_index"
    ).fetchone()[0]

    # Documents by period
    stats["documents_by_period"] = {}
    for label, cutoff in periods.items():
        stats["documents_by_period"][label] = conn.execute(
            "SELECT COUNT(*) FROM document_index WHERE modified_at >= ?", (cutoff,)
        ).fetchone()[0]

    # Patterns count (if table exists)
    has_patterns = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='patterns'"
    ).fetchone()
    if has_patterns:
        stats["total_patterns"] = conn.execute(
            "SELECT COUNT(*) FROM patterns"
        ).fetchone()[0]
    else:
        stats["total_patterns"] = 0

    # Top topics (from decisions)
    stats["top_topics"] = []
    for row in conn.execute(
        """
        SELECT topic, COUNT(*) as cnt
        FROM decisions
        GROUP BY topic
        ORDER BY cnt DESC
        LIMIT 10
        """
    ):
        stats["top_topics"].append({"topic": row[0], "count": row[1]})

    # Most active capsules
    stats["active_capsules"] = []
    for row in conn.execute(
        """
        SELECT capsule, COUNT(*) as cnt
        FROM decisions
        WHERE capsule IS NOT NULL AND capsule != ''
        GROUP BY capsule
        ORDER BY cnt DESC
        LIMIT 10
        """
    ):
        stats["active_capsules"].append({"capsule": row[0], "count": row[1]})

    # Grand total across all sources
    stats["grand_total"] = (
        stats["total_decisions"]
        + stats["total_documents"]
        + stats["total_patterns"]
    )

    conn.close()
    return json.dumps(stats, indent=2)


@mcp.tool()
def save_decision(
    topic: str,
    decision_text: str,
    context: str = "",
    agent_name: str = "",
    capsule: str = "",
    tags: list[str] | None = None,
) -> str:
    """Save a new decision to the temporal memory store.

    Args:
        topic: Short topic label for the decision.
        decision_text: The decision that was made.
        context: Additional context around the decision (optional).
        agent_name: Which agent made or recorded the decision (optional).
        capsule: Which capsule this decision relates to (optional).
        tags: List of string tags for categorization (optional).

    Returns:
        JSON object with the new decision_id and created_at timestamp.
    """
    conn = _get_conn()
    _ensure_tables(conn)

    decision_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    tags_json = json.dumps(tags) if tags else "[]"

    conn.execute(
        """
        INSERT INTO decisions
            (decision_id, topic, decision_text, context, agent_name,
             capsule, tags, created_at, session_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            decision_id,
            topic,
            decision_text,
            context or None,
            agent_name or None,
            capsule or None,
            tags_json,
            created_at,
            None,
        ),
    )
    conn.commit()
    conn.close()

    return json.dumps({
        "decision_id": decision_id,
        "created_at": created_at,
        "status": "saved",
    })


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def _startup() -> None:
    """Run on import: ensure tables exist and index documents."""
    conn = _get_conn()
    _ensure_tables(conn)
    indexed = _index_markdown_files(conn)
    conn.close()
    if indexed:
        import sys
        print(f"[temporal-memory] Indexed {indexed} document(s)", file=sys.stderr)


_startup()

if __name__ == "__main__":
    mcp.run(transport="stdio")
