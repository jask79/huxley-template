#!/usr/bin/env python3
"""
Memory Learning Bridge - Connects Code Review findings to Agent Memory System
Analyzes review patterns and stores learnings for future agent improvements

Required quality.db schema:
    CREATE TABLE reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        review_type TEXT NOT NULL,
        triggers TEXT,
        findings TEXT,  -- JSON: {"critical": [...], "major": [...], "minor": [...]}
        duration_ms INTEGER,
        commit_hash TEXT,
        mode TEXT
    );
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from collections import Counter
from typing import Dict, List, Any, Optional

# Get Huxley root from environment
CATALYST_ROOT = os.environ.get('CATALYST_ROOT', '{{CATALYST_ROOT}}')

# Memory integration (reuse from hooks)
sys.path.insert(0, str(Path(CATALYST_ROOT) / 'global/claude-config/hooks'))
from utils.memory_integration import get_memory_integration


class MemoryLearningBridge:
    """Bridges code review findings to agent memory for learning."""

    def __init__(self):
        self.quality_db = Path(CATALYST_ROOT) / 'monitoring' / 'quality.db'
        self.memory = get_memory_integration()
        self._verify_schema()

    def _verify_schema(self):
        """Verify quality.db has required schema."""
        if not self.quality_db.exists():
            print(f"⚠️  quality.db not found at {self.quality_db}")
            return

        try:
            conn = sqlite3.connect(str(self.quality_db))
            cursor = conn.cursor()

            # Check if reviews table exists with required columns
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reviews'")
            if not cursor.fetchone():
                print("⚠️  'reviews' table not found in quality.db")
                conn.close()
                return

            # Check for required columns
            cursor.execute("PRAGMA table_info(reviews)")
            columns = {row[1] for row in cursor.fetchall()}
            required = {'timestamp', 'findings', 'review_type'}

            if not required.issubset(columns):
                missing = required - columns
                print(f"⚠️  Missing required columns in reviews table: {missing}")

            conn.close()
        except Exception as e:
            print(f"⚠️  Schema verification failed: {e}")

    def analyze_recent_reviews(self, days: int = 7) -> Dict[str, Any]:
        """
        Analyze recent code reviews to identify patterns.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary of patterns found
        """
        conn = sqlite3.connect(str(self.quality_db))
        cursor = conn.cursor()

        # Query recent reviews
        cursor.execute('''
            SELECT findings, review_type, mode, timestamp
            FROM reviews
            WHERE timestamp >= datetime('now', ?)
            ORDER BY timestamp DESC
        ''', (f'-{days} days',))

        reviews = cursor.fetchall()
        conn.close()

        if not reviews:
            return {"patterns": [], "anti_patterns": []}

        # Aggregate findings
        all_critical = []
        all_major = []
        all_minor = []

        for findings_json, review_type, mode, timestamp in reviews:
            try:
                findings = json.loads(findings_json)
                all_critical.extend(findings.get('critical', []))
                all_major.extend(findings.get('major', []))
                all_minor.extend(findings.get('minor', []))
            except json.JSONDecodeError:
                continue

        # Identify recurring issues (anti-patterns)
        recurring_issues = self._identify_recurring_issues(
            all_critical + all_major + all_minor
        )

        # Calculate success rate
        total_reviews = len(reviews)
        clean_reviews = len([r for r in reviews if self._is_clean_review(r[0])])
        success_rate = clean_reviews / total_reviews if total_reviews > 0 else 0.0

        return {
            "total_reviews": total_reviews,
            "success_rate": success_rate,
            "recurring_issues": recurring_issues,
            "critical_count": len(all_critical),
            "major_count": len(all_major),
            "minor_count": len(all_minor)
        }

    def _is_clean_review(self, findings_json: str) -> bool:
        """Check if review had no critical/major findings."""
        try:
            findings = json.loads(findings_json)
            return (
                len(findings.get('critical', [])) == 0 and
                len(findings.get('major', [])) == 0
            )
        except json.JSONDecodeError:
            return False

    def _identify_recurring_issues(self, all_findings: List[str]) -> List[Dict[str, Any]]:
        """
        Identify issues that appear multiple times.

        Args:
            all_findings: List of finding messages

        Returns:
            List of recurring issues with counts
        """
        # Pattern matching with longer context (100 chars) for better grouping
        issue_patterns = Counter()

        for finding in all_findings:
            # Extract pattern (first 100 chars or until first newline)
            # This preserves more context for better differentiation
            pattern = finding.split('\n')[0][:100].strip()
            if pattern:
                issue_patterns[pattern] += 1

        # Return patterns that appear more than once
        recurring = [
            {"pattern": pattern, "count": count}
            for pattern, count in issue_patterns.items()
            if count > 1
        ]

        return sorted(recurring, key=lambda x: x['count'], reverse=True)

    def store_anti_patterns(self, agent_name: str = "Code Reviewer") -> int:
        """
        Store recurring anti-patterns in agent memory.

        Args:
            agent_name: Name of the agent to associate patterns with

        Returns:
            Number of anti-patterns stored
        """
        analysis = self.analyze_recent_reviews(days=30)  # Look back 30 days

        stored_count = 0

        # Store recurring issues as anti-patterns
        for issue in analysis.get('recurring_issues', [])[:10]:  # Top 10
            if issue['count'] < 3:  # Only store if seen 3+ times
                continue

            content = f"Anti-pattern: {issue['pattern']}"
            context = f"Observed {issue['count']} times in last 30 days"

            # Store anti-pattern memory
            memory_id = self.memory.create_memory_for_agent(
                agent_name=agent_name,
                content=content,
                context=context,
                impact_score=0.8,  # High impact - anti-patterns are important
                tags=["anti-pattern", "code-quality", "recurring-issue"],
                memory_type="anti-pattern"
            )

            if memory_id:
                stored_count += 1
                print(f"✅ Stored anti-pattern: {issue['pattern'][:50]}...")

        return stored_count

    def store_success_patterns(self, agent_name: str = "Code Reviewer") -> int:
        """
        Store successful review patterns when success rate is high.

        Args:
            agent_name: Name of the agent

        Returns:
            Number of success patterns stored
        """
        analysis = self.analyze_recent_reviews(days=7)

        success_rate = analysis.get('success_rate', 0.0)

        if success_rate < 0.8:  # Only store if 80%+ success rate
            return 0

        # Store success pattern
        content = f"High code quality maintained: {success_rate*100:.1f}% clean reviews"
        context = f"Over {analysis['total_reviews']} reviews in last 7 days"

        memory_id = self.memory.create_memory_for_agent(
            agent_name=agent_name,
            content=content,
            context=context,
            impact_score=0.9,  # Very high impact
            tags=["success-pattern", "code-quality", "high-performance"],
            memory_type="pattern"
        )

        if memory_id:
            print(f"✅ Stored success pattern: {success_rate*100:.1f}% success rate")
            return 1

        return 0


def main():
    """Analyze recent reviews and store learnings."""
    bridge = MemoryLearningBridge()

    print("🧠 Analyzing recent code reviews for learning patterns...\n")

    # Get analysis summary
    analysis = bridge.analyze_recent_reviews(days=30)

    print(f"📊 Analysis Summary (30 days):")
    print(f"   Total reviews: {analysis['total_reviews']}")
    print(f"   Success rate: {analysis['success_rate']*100:.1f}%")
    print(f"   Critical issues: {analysis['critical_count']}")
    print(f"   Major issues: {analysis['major_count']}")
    print(f"   Recurring patterns: {len(analysis['recurring_issues'])}")
    print()

    # Store anti-patterns
    print("💾 Storing anti-patterns in agent memory...")
    anti_pattern_count = bridge.store_anti_patterns()
    print(f"   Stored {anti_pattern_count} anti-patterns")
    print()

    # Store success patterns
    print("💾 Storing success patterns in agent memory...")
    success_count = bridge.store_success_patterns()
    print(f"   Stored {success_count} success patterns")
    print()

    print("✅ Memory learning bridge complete!")


if __name__ == "__main__":
    main()
