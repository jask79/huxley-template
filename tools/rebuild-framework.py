#!/usr/bin/env python3
"""
Rebuild Framework Tool - Regenerates all capsule framework files

Performs comprehensive framework rebuild including:
1. Sync patterns from agent-memory MCP server
2. Generate context/patterns.md from memory.yaml
3. Query quality.db for metrics
4. Auto-detect skills in .claude/skills/
5. Parse .mcp.json for MCP configurations
6. Compute health score
7. Generate CLAUDE.md
8. Generate docs/SPECIFICATIONS.md

Usage:
    python3 tools/rebuild-framework.py example-social-capsule
    python3 tools/rebuild-framework.py --all
    python3 tools/rebuild-framework.py example-social-capsule --dry-run
    python3 tools/rebuild-framework.py example-social-capsule -v
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    print("Error: PyYAML required. Install with: pip install pyyaml")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None  # Will warn when needed


# =============================================================================
# Constants
# =============================================================================

CATALYST_ROOT = Path("{{CATALYST_ROOT}}")
QUALITY_DB_PATH = CATALYST_ROOT / "monitoring" / "quality.db"
CAPSULES_DIR = CATALYST_ROOT / "capsules"
TEMPLATES_DIR = CATALYST_ROOT / "recipes" / "framework-templates"

AGENT_MEMORY_ENDPOINT = "http://localhost:8090"
AGENT_MEMORY_SSE_ENDPOINT = f"{AGENT_MEMORY_ENDPOINT}/sse"


# =============================================================================
# Utility Classes
# =============================================================================

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


class Logger:
    """Simple logger with verbosity control"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def success(self, msg: str):
        print(f"  {Colors.GREEN}✓{Colors.END} {msg}")

    def warning(self, msg: str):
        print(f"  {Colors.YELLOW}⚠{Colors.END} {msg}")

    def error(self, msg: str):
        print(f"  {Colors.RED}✗{Colors.END} {msg}")

    def info(self, msg: str):
        if self.verbose:
            print(f"  {Colors.BLUE}ℹ{Colors.END} {msg}")

    def debug(self, msg: str):
        if self.verbose:
            print(f"  {Colors.CYAN}→{Colors.END} {msg}")


# =============================================================================
# Agent Memory Sync
# =============================================================================

class AgentMemorySync:
    """Handles synchronization with agent-memory MCP server"""

    def __init__(self, logger: Logger):
        self.logger = logger
        self.endpoint = AGENT_MEMORY_ENDPOINT

    def is_available(self) -> bool:
        """Check if agent-memory server is available"""
        if requests is None:
            self.logger.warning("requests library not installed, cannot sync with agent-memory")
            return False

        try:
            response = requests.get(f"{self.endpoint}/health", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def search_memories(self, capsule_slug: str, tags: List[str] = None,
                        min_impact: float = 0.3, max_results: int = 50) -> List[Dict]:
        """Search agent-memory for patterns related to capsule"""
        if not self.is_available():
            return []

        try:
            # Build search query
            query_tags = [capsule_slug]
            if tags:
                query_tags.extend(tags)

            payload = {
                "method": "search_memories",
                "params": {
                    "query": capsule_slug,
                    "tags": query_tags,
                    "min_impact_score": min_impact,
                    "limit": max_results
                }
            }

            response = requests.post(
                f"{self.endpoint}/rpc",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("memories", [])
            else:
                self.logger.debug(f"Memory search returned {response.status_code}")
                return []

        except Exception as e:
            self.logger.debug(f"Memory search failed: {e}")
            return []

    def get_agent_memories(self, agent_name: str, memory_type: str = None) -> List[Dict]:
        """Get memories for a specific agent"""
        if not self.is_available():
            return []

        try:
            payload = {
                "method": "get_agent_memories",
                "params": {
                    "agent_name": agent_name,
                    "type": memory_type
                }
            }

            response = requests.post(
                f"{self.endpoint}/rpc",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("memories", [])
            return []

        except Exception as e:
            self.logger.debug(f"Get agent memories failed: {e}")
            return []

    def store_pending_memories(self, memories: List[Dict]) -> int:
        """Store pending memories to agent-memory"""
        if not self.is_available() or not memories:
            return 0

        stored = 0
        for memory in memories:
            try:
                payload = {
                    "method": "create_memory",
                    "params": memory
                }

                response = requests.post(
                    f"{self.endpoint}/rpc",
                    json=payload,
                    timeout=10
                )

                if response.status_code == 200:
                    stored += 1

            except Exception as e:
                self.logger.debug(f"Failed to store memory: {e}")

        return stored


# =============================================================================
# Quality DB Queries
# =============================================================================

class QualityDBReader:
    """Reads metrics from quality.db"""

    def __init__(self, db_path: Path, logger: Logger):
        self.db_path = db_path
        self.logger = logger

    def is_available(self) -> bool:
        """Check if quality.db exists and is readable"""
        return self.db_path.exists()

    def get_code_review_metrics(self, capsule_path: str) -> Dict[str, Any]:
        """Get code review metrics for a capsule"""
        if not self.is_available():
            return {}

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Pattern to match capsule files
            pattern = f"%{capsule_path}%"

            # Total reviews
            cursor.execute("""
                SELECT COUNT(*),
                       SUM(findings_critical),
                       SUM(findings_major),
                       SUM(findings_minor),
                       AVG(duration_ms),
                       MAX(timestamp)
                FROM reviews
                WHERE file_path LIKE ?
            """, (pattern,))

            row = cursor.fetchone()

            # Context level breakdown
            cursor.execute("""
                SELECT review_type, COUNT(*)
                FROM reviews
                WHERE file_path LIKE ?
                GROUP BY review_type
            """, (pattern,))

            context_levels = dict(cursor.fetchall())

            conn.close()

            return {
                "total": row[0] or 0,
                "by_context_level": {
                    "lightweight": context_levels.get("lightweight", 0),
                    "comprehensive": context_levels.get("comprehensive", 0)
                },
                "findings": {
                    "critical": row[1] or 0,
                    "major": row[2] or 0,
                    "minor": row[3] or 0
                },
                "average_duration_ms": int(row[4]) if row[4] else 0,
                "last_review_date": row[5]
            }

        except Exception as e:
            self.logger.debug(f"Failed to get code review metrics: {e}")
            return {}

    def get_debugging_metrics(self, capsule_path: str) -> Dict[str, Any]:
        """Get debugging session metrics for a capsule"""
        if not self.is_available():
            return {}

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            pattern = f"%{capsule_path}%"

            cursor.execute("""
                SELECT COUNT(*),
                       SUM(bugs_found),
                       SUM(bugs_fixed),
                       AVG(duration_ms)
                FROM debug_sessions
                WHERE file_path LIKE ?
            """, (pattern,))

            row = cursor.fetchone()
            conn.close()

            total = row[0] or 0
            bugs_found = row[1] or 0
            bugs_fixed = row[2] or 0

            return {
                "total": total,
                "bugs_found": bugs_found,
                "bugs_fixed": bugs_fixed,
                "success_rate": round(bugs_fixed / bugs_found, 2) if bugs_found > 0 else None,
                "average_resolution_time_ms": int(row[3]) if row[3] else 0
            }

        except Exception as e:
            self.logger.debug(f"Failed to get debugging metrics: {e}")
            return {}

    def get_benchmark_metrics(self, capsule_name: str) -> Dict[str, Any]:
        """Get benchmark run metrics if available"""
        if not self.is_available():
            return {}

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*),
                       SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END)
                FROM benchmark_runs br
                JOIN benchmark_tasks bt ON br.task_id = bt.task_id
                WHERE bt.domain = ?
            """, (capsule_name,))

            row = cursor.fetchone()
            conn.close()

            total = row[0] or 0
            passed = row[1] or 0

            return {
                "total": total,
                "passed": passed,
                "failed": row[2] or 0,
                "pass_rate": round(passed / total, 2) if total > 0 else None
            }

        except Exception as e:
            self.logger.debug(f"Failed to get benchmark metrics: {e}")
            return {}


# =============================================================================
# Skills Detection
# =============================================================================

class SkillsDetector:
    """Detects and parses skills from .claude/skills/ directory"""

    def __init__(self, logger: Logger):
        self.logger = logger

    def detect_skills(self, capsule_path: Path) -> List[Dict[str, Any]]:
        """Detect skills in capsule's .claude/skills/ directory"""
        skills_dir = capsule_path / ".claude" / "skills"

        if not skills_dir.exists():
            return []

        skills = []

        # Look for SKILL.md or skill.md files
        for skill_file in skills_dir.rglob("*[Ss][Kk][Ii][Ll][Ll].md"):
            skill_info = self._parse_skill_file(skill_file)
            if skill_info:
                skills.append(skill_info)

        return skills

    def _parse_skill_file(self, skill_path: Path) -> Optional[Dict[str, Any]]:
        """Parse a skill.md file for metadata"""
        try:
            content = skill_path.read_text()

            # Parse YAML frontmatter if present
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    try:
                        metadata = yaml.safe_load(parts[1])
                        if metadata:
                            return {
                                "name": metadata.get("name", skill_path.parent.name),
                                "description": metadata.get("description", ""),
                                "when": metadata.get("when", ""),
                                "path": str(skill_path.relative_to(skill_path.parents[3])),
                                "metadata": metadata.get("metadata", {})
                            }
                    except yaml.YAMLError:
                        pass

            # Fallback: extract name from first heading
            heading_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            name = heading_match.group(1) if heading_match else skill_path.parent.name

            return {
                "name": name,
                "description": "",
                "path": str(skill_path.relative_to(skill_path.parents[3]))
            }

        except Exception as e:
            self.logger.debug(f"Failed to parse skill file {skill_path}: {e}")
            return None


# =============================================================================
# MCP Config Parser
# =============================================================================

class MCPConfigParser:
    """Parses .mcp.json configuration files"""

    def __init__(self, logger: Logger):
        self.logger = logger

    def parse_mcp_config(self, capsule_path: Path) -> Dict[str, Any]:
        """Parse .mcp.json if it exists"""
        mcp_file = capsule_path / ".mcp.json"

        if not mcp_file.exists():
            return {"servers": [], "resources": []}

        try:
            with open(mcp_file) as f:
                config = json.load(f)

            servers = []
            resources = []

            # Parse mcpServers section
            mcp_servers = config.get("mcpServers", {})
            for name, server_config in mcp_servers.items():
                servers.append({
                    "name": name,
                    "command": server_config.get("command", ""),
                    "args": server_config.get("args", [])
                })

            return {
                "servers": servers,
                "resources": resources
            }

        except Exception as e:
            self.logger.debug(f"Failed to parse .mcp.json: {e}")
            return {"servers": [], "resources": []}


# =============================================================================
# Health Score Calculator
# =============================================================================

class HealthScoreCalculator:
    """Computes health score from various metrics"""

    def __init__(self, logger: Logger):
        self.logger = logger

    def compute_health_score(
        self,
        quality_metrics: Dict[str, Any],
        last_session: Optional[str],
        test_coverage: Optional[float],
        debugging_metrics: Dict[str, Any]
    ) -> float:
        """
        Compute health score (0.0 - 1.0) based on:
        - Recent activity: +0.2 if session in last 7 days
        - Quality: +0.3 based on code review pass rate
        - Tests: +0.2 if test coverage > 80%
        - Stability: +0.3 if no critical issues
        """
        score = 0.0

        # Recent activity (0.2)
        if last_session:
            try:
                session_date = datetime.fromisoformat(last_session.replace('Z', '+00:00'))
                if isinstance(session_date, datetime):
                    days_ago = (datetime.now(session_date.tzinfo) - session_date).days
                else:
                    days_ago = (datetime.now() - datetime.combine(session_date, datetime.min.time())).days

                if days_ago <= 7:
                    score += 0.2
                elif days_ago <= 30:
                    score += 0.1
            except (ValueError, TypeError):
                # Try simpler parsing
                try:
                    session_date = datetime.strptime(last_session[:10], "%Y-%m-%d")
                    days_ago = (datetime.now() - session_date).days
                    if days_ago <= 7:
                        score += 0.2
                    elif days_ago <= 30:
                        score += 0.1
                except:
                    pass

        # Quality based on code reviews (0.3)
        code_reviews = quality_metrics.get("code_reviews", {})
        total_reviews = code_reviews.get("total", 0)
        findings = code_reviews.get("findings", {})
        critical = findings.get("critical", 0)
        major = findings.get("major", 0)

        if total_reviews > 0:
            # Calculate quality ratio (fewer issues = higher score)
            issue_ratio = (critical * 3 + major) / total_reviews
            if issue_ratio < 0.5:
                score += 0.3
            elif issue_ratio < 1.0:
                score += 0.2
            elif issue_ratio < 2.0:
                score += 0.1
        else:
            # No reviews yet, neutral score
            score += 0.15

        # Test coverage (0.2)
        if test_coverage is not None:
            if test_coverage >= 80:
                score += 0.2
            elif test_coverage >= 60:
                score += 0.15
            elif test_coverage >= 40:
                score += 0.1
            elif test_coverage > 0:
                score += 0.05
        else:
            # No coverage data, neutral
            score += 0.1

        # Stability - no critical issues (0.3)
        debug_bugs_found = debugging_metrics.get("bugs_found", 0)
        debug_bugs_fixed = debugging_metrics.get("bugs_fixed", 0)

        if critical == 0:
            score += 0.2

            # Bonus for resolved bugs
            if debug_bugs_found > 0 and debug_bugs_fixed >= debug_bugs_found:
                score += 0.1
            elif debug_bugs_found == 0:
                score += 0.1
        elif critical <= 2:
            score += 0.1

        return round(min(score, 1.0), 2)


# =============================================================================
# File Generators
# =============================================================================

class PatternsMarkdownGenerator:
    """Generates context/patterns.md from memory.yaml"""

    def __init__(self, logger: Logger):
        self.logger = logger

    def generate(self, memory_data: Dict[str, Any], capsule_name: str) -> str:
        """Generate patterns.md content from memory data"""
        lines = [
            f"# Learned Patterns & Best Practices - {capsule_name}",
            "",
            "<!--",
            "AUTO-GENERATED FROM specs/memory.yaml",
            f"Generated: {datetime.now().isoformat()}",
            "Do not edit directly. Update specs/memory.yaml instead.",
            "Regenerate with: python3 tools/rebuild-framework.py <capsule>",
            "-->",
            "",
            f"This document captures proven patterns and best practices discovered during {capsule_name} development.",
            ""
        ]

        # Patterns section
        patterns = memory_data.get("patterns", [])
        if patterns:
            lines.append("## Development Patterns")
            lines.append("")

            for i, pattern in enumerate(patterns, 1):
                lines.append(f"### {i}. {pattern.get('name', 'Unnamed Pattern')}")
                lines.append("")

                if pattern.get('description'):
                    lines.append(f"**Pattern:** {pattern['description']}")
                    lines.append("")

                if pattern.get('code_example'):
                    lang = pattern.get('language', '')
                    lines.append(f"```{lang}")
                    lines.append(pattern['code_example'])
                    lines.append("```")
                    lines.append("")

                agent = pattern.get('agent', '')
                impact = pattern.get('impact_score', 0)
                if agent or impact:
                    lines.append(f"**Agent:** {agent} | **Impact:** {impact}")
                    lines.append("")

                tags = pattern.get('tags', [])
                if tags:
                    lines.append(f"**Tags:** {', '.join(tags)}")
                    lines.append("")

                lines.append("---")
                lines.append("")

        # Anti-patterns section
        anti_patterns = memory_data.get("anti_patterns", [])
        if anti_patterns:
            lines.append("## Anti-Patterns to Avoid")
            lines.append("")

            for anti in anti_patterns:
                name = anti.get('name', 'Unnamed Anti-Pattern')
                lines.append(f"### {name}")
                lines.append("")

                if anti.get('description'):
                    lines.append(f"**Problem:** {anti['description']}")
                    lines.append("")

                if anti.get('solution'):
                    lines.append(f"**Solution:** {anti['solution']}")
                    lines.append("")

                lines.append("---")
                lines.append("")

        # Procedures section
        procedures = memory_data.get("procedures", [])
        if procedures:
            lines.append("## Procedural Knowledge")
            lines.append("")

            for proc in procedures:
                name = proc.get('name', 'Unnamed Procedure')
                lines.append(f"### {name}")
                lines.append("")

                steps = proc.get('steps', [])
                for j, step in enumerate(steps, 1):
                    lines.append(f"{j}. {step}")

                lines.append("")
                lines.append("---")
                lines.append("")

        # Footer
        if not patterns and not anti_patterns and not procedures:
            lines.append("*No patterns recorded yet. Patterns will be populated from agent-memory during sessions.*")
            lines.append("")

        lines.append("---")
        lines.append(f"*Generated from `specs/memory.yaml` on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(lines)


class SpecificationsGenerator:
    """Generates docs/SPECIFICATIONS.md from YAML specs"""

    def __init__(self, logger: Logger):
        self.logger = logger

    def generate(self, capsule_path: Path, capsule_name: str) -> str:
        """Generate SPECIFICATIONS.md combining all YAML specs"""
        lines = [
            f"# {capsule_name} - Complete Specifications",
            "",
            "<!--",
            "AUTO-GENERATED FROM YAML SPECIFICATIONS",
            f"Generated: {datetime.now().isoformat()}",
            "Do not edit directly. Update YAML files instead.",
            "-->",
            "",
        ]

        # Load standards.yaml
        standards_path = capsule_path / "standards.yaml"
        if standards_path.exists():
            lines.append("## Quality Standards")
            lines.append("")
            try:
                with open(standards_path) as f:
                    standards = yaml.safe_load(f) or {}
                lines.append(self._yaml_to_markdown(standards, "standards"))
            except Exception as e:
                lines.append(f"*Error loading standards.yaml: {e}*")
            lines.append("")

        # Load product.yaml
        product_path = capsule_path / "product.yaml"
        if product_path.exists():
            lines.append("## Product Definition")
            lines.append("")
            try:
                with open(product_path) as f:
                    product = yaml.safe_load(f) or {}
                lines.append(self._yaml_to_markdown(product, "product"))
            except Exception as e:
                lines.append(f"*Error loading product.yaml: {e}*")
            lines.append("")

        # Load specs/current.yaml
        current_path = capsule_path / "specs" / "current.yaml"
        if current_path.exists():
            lines.append("## Current Specification")
            lines.append("")
            try:
                with open(current_path) as f:
                    current = yaml.safe_load(f) or {}
                lines.append(self._yaml_to_markdown(current, "spec"))
            except Exception as e:
                lines.append(f"*Error loading specs/current.yaml: {e}*")
            lines.append("")

        # Load specs/next.yaml if exists
        next_path = capsule_path / "specs" / "next.yaml"
        if next_path.exists():
            lines.append("## Next Version Specification")
            lines.append("")
            try:
                with open(next_path) as f:
                    next_spec = yaml.safe_load(f) or {}
                lines.append(self._yaml_to_markdown(next_spec, "next"))
            except Exception as e:
                lines.append(f"*Error loading specs/next.yaml: {e}*")
            lines.append("")

        lines.append("---")
        lines.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(lines)

    def _yaml_to_markdown(self, data: Dict, section_type: str, indent: int = 0) -> str:
        """Convert YAML data to readable markdown"""
        lines = []
        prefix = "  " * indent

        # Skip internal fields
        skip_keys = {"_schema_version", "_framework_version", "_sync", "_metadata"}

        for key, value in data.items():
            if key in skip_keys:
                continue

            display_key = key.replace("_", " ").title()

            if isinstance(value, dict):
                lines.append(f"{prefix}### {display_key}")
                lines.append("")
                lines.append(self._yaml_to_markdown(value, section_type, indent))
                lines.append("")
            elif isinstance(value, list):
                lines.append(f"{prefix}**{display_key}:**")
                for item in value:
                    if isinstance(item, dict):
                        for k, v in item.items():
                            lines.append(f"{prefix}- **{k}:** {v}")
                    else:
                        lines.append(f"{prefix}- {item}")
                lines.append("")
            else:
                if value is not None:
                    lines.append(f"{prefix}**{display_key}:** {value}")

        return "\n".join(lines)


# =============================================================================
# Main Framework Rebuilder
# =============================================================================

class FrameworkRebuilder:
    """Main class that orchestrates the framework rebuild"""

    def __init__(self, verbose: bool = False, dry_run: bool = False):
        self.verbose = verbose
        self.dry_run = dry_run
        self.logger = Logger(verbose)

        # Initialize components
        self.memory_sync = AgentMemorySync(self.logger)
        self.quality_db = QualityDBReader(QUALITY_DB_PATH, self.logger)
        self.skills_detector = SkillsDetector(self.logger)
        self.mcp_parser = MCPConfigParser(self.logger)
        self.health_calculator = HealthScoreCalculator(self.logger)
        self.patterns_generator = PatternsMarkdownGenerator(self.logger)
        self.specs_generator = SpecificationsGenerator(self.logger)

    def rebuild_capsule(self, capsule_name: str) -> bool:
        """Rebuild framework for a single capsule"""
        capsule_path = CAPSULES_DIR / capsule_name

        if not capsule_path.exists():
            self.logger.error(f"Capsule not found: {capsule_name}")
            return False

        print(f"\n{Colors.BOLD}Rebuilding framework for: {capsule_name}{Colors.END}")

        if self.dry_run:
            print(f"  {Colors.CYAN}[DRY RUN]{Colors.END} - No files will be modified")

        results = {
            "patterns_synced": 0,
            "anti_patterns_synced": 0,
            "skills_detected": 0,
            "mcp_servers": 0,
            "health_score": 0.0
        }

        # 1. Sync from Agent Memory
        results.update(self._sync_agent_memory(capsule_path, capsule_name))

        # 2. Generate context/patterns.md
        self._generate_patterns_md(capsule_path, capsule_name)

        # 3. Query quality.db for metrics
        quality_metrics = self._update_quality_metrics(capsule_path, capsule_name)

        # 4. Auto-detect skills
        results["skills_detected"] = self._detect_skills(capsule_path)

        # 5. Parse .mcp.json
        results["mcp_servers"] = self._parse_mcp_config(capsule_path)

        # 6. Compute health score
        results["health_score"] = self._compute_health_score(
            capsule_path, quality_metrics
        )

        # 7. Generate CLAUDE.md
        self._generate_claude_md(capsule_path)

        # 8. Generate docs/SPECIFICATIONS.md
        self._generate_specifications_md(capsule_path, capsule_name)

        # Summary
        print(f"\n{Colors.GREEN}Framework rebuild complete for {capsule_name}{Colors.END}")

        return True

    def _sync_agent_memory(self, capsule_path: Path, capsule_name: str) -> Dict[str, int]:
        """Step 1: Sync patterns from agent-memory"""
        memory_yaml_path = capsule_path / "specs" / "memory.yaml"

        # Ensure directory exists
        memory_yaml_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing memory.yaml or create default
        if memory_yaml_path.exists():
            with open(memory_yaml_path) as f:
                memory_data = yaml.safe_load(f) or {}
        else:
            memory_data = {
                "_sync": {
                    "canonical_source": "agent-memory",
                    "server_endpoint": "localhost:8090/sse",
                    "last_sync": None,
                    "sync_direction": "bidirectional",
                    "auto_sync_on_session_end": True
                },
                "query_config": {
                    "capsule_tag": capsule_name,
                    "additional_tags": [],
                    "max_results": 50,
                    "min_impact_score": 0.3
                },
                "patterns": [],
                "anti_patterns": [],
                "procedures": [],
                "pending_storage": [],
                "related_patterns": [],
                "_metadata": {
                    "created": datetime.now().isoformat(),
                    "schema_version": "2.0.0",
                    "total_patterns": 0,
                    "total_anti_patterns": 0,
                    "total_procedures": 0
                }
            }

        # Check if server is available
        if not self.memory_sync.is_available():
            self.logger.warning("Agent-memory server unavailable, skipping sync")
            # Still create/update memory.yaml with defaults if it doesn't exist
            if not memory_yaml_path.exists() and not self.dry_run:
                with open(memory_yaml_path, 'w') as f:
                    yaml.dump(memory_data, f, default_flow_style=False, sort_keys=False)
                self.logger.info("Created default specs/memory.yaml")
            return {"patterns_synced": 0, "anti_patterns_synced": 0}

        # Search for patterns
        query_config = memory_data.get("query_config", {})
        capsule_tag = query_config.get("capsule_tag", capsule_name)
        additional_tags = query_config.get("additional_tags", [])
        min_impact = query_config.get("min_impact_score", 0.3)
        max_results = query_config.get("max_results", 50)

        memories = self.memory_sync.search_memories(
            capsule_tag,
            tags=additional_tags,
            min_impact=min_impact,
            max_results=max_results
        )

        # Categorize memories
        patterns = []
        anti_patterns = []
        procedures = []

        for mem in memories:
            mem_type = mem.get("type", "semantic")
            if mem_type == "procedural":
                procedures.append(mem)
            elif "anti" in mem.get("name", "").lower() or "avoid" in mem.get("description", "").lower():
                anti_patterns.append(mem)
            else:
                patterns.append(mem)

        # Update memory.yaml
        memory_data["patterns"] = patterns
        memory_data["anti_patterns"] = anti_patterns
        memory_data["procedures"] = procedures
        memory_data["_sync"]["last_sync"] = datetime.now().isoformat()
        memory_data["_metadata"]["total_patterns"] = len(patterns)
        memory_data["_metadata"]["total_anti_patterns"] = len(anti_patterns)
        memory_data["_metadata"]["total_procedures"] = len(procedures)

        # Store pending memories
        pending = memory_data.get("pending_storage", [])
        stored = 0
        if pending and not self.dry_run:
            stored = self.memory_sync.store_pending_memories(pending)
            if stored > 0:
                memory_data["pending_storage"] = []

        # Write memory.yaml
        if not self.dry_run:
            with open(memory_yaml_path, 'w') as f:
                yaml.dump(memory_data, f, default_flow_style=False, sort_keys=False)

        total_patterns = len(patterns)
        total_anti = len(anti_patterns)

        if total_patterns > 0 or total_anti > 0:
            self.logger.success(f"Synced {total_patterns} patterns from agent-memory")
            if stored > 0:
                self.logger.success(f"Stored {stored} pending memories to agent-memory")
        else:
            self.logger.info("No patterns found in agent-memory for this capsule")

        return {
            "patterns_synced": total_patterns,
            "anti_patterns_synced": total_anti
        }

    def _generate_patterns_md(self, capsule_path: Path, capsule_name: str):
        """Step 2: Generate context/patterns.md"""
        memory_yaml_path = capsule_path / "specs" / "memory.yaml"
        patterns_md_path = capsule_path / "context" / "patterns.md"

        # Ensure directory exists
        patterns_md_path.parent.mkdir(parents=True, exist_ok=True)

        # Load memory.yaml
        if memory_yaml_path.exists():
            with open(memory_yaml_path) as f:
                memory_data = yaml.safe_load(f) or {}
        else:
            memory_data = {}

        # Generate markdown
        content = self.patterns_generator.generate(memory_data, capsule_name)

        # Count items for logging
        patterns_count = len(memory_data.get("patterns", []))
        anti_count = len(memory_data.get("anti_patterns", []))

        if not self.dry_run:
            with open(patterns_md_path, 'w') as f:
                f.write(content)

        self.logger.success(f"Generated context/patterns.md ({patterns_count} patterns, {anti_count} anti-patterns)")

    def _update_quality_metrics(self, capsule_path: Path, capsule_name: str) -> Dict[str, Any]:
        """Step 3: Update quality metrics from quality.db"""
        if not self.quality_db.is_available():
            self.logger.warning("quality.db unavailable, skipping metrics update")
            return {}

        # Get metrics
        code_reviews = self.quality_db.get_code_review_metrics(capsule_name)
        debugging = self.quality_db.get_debugging_metrics(capsule_name)
        validation = self.quality_db.get_benchmark_metrics(capsule_name)

        # Update standards.yaml
        standards_path = capsule_path / "standards.yaml"
        if standards_path.exists():
            with open(standards_path) as f:
                standards = yaml.safe_load(f) or {}

            standards["_quality_metrics"] = {
                "last_updated": datetime.now().isoformat(),
                "code_reviews": code_reviews,
                "debugging_sessions": debugging,
                "validation_runs": validation
            }

            if not self.dry_run:
                with open(standards_path, 'w') as f:
                    yaml.dump(standards, f, default_flow_style=False, sort_keys=False)

        # Update specs/current.yaml
        current_path = capsule_path / "specs" / "current.yaml"
        if current_path.exists():
            with open(current_path) as f:
                current = yaml.safe_load(f) or {}

            if "quality" not in current:
                current["quality"] = {}

            current["quality"]["_metrics"] = {
                "code_reviews": {
                    "total": code_reviews.get("total", 0),
                    "critical_issues": code_reviews.get("findings", {}).get("critical", 0),
                    "major_issues": code_reviews.get("findings", {}).get("major", 0),
                    "minor_issues": code_reviews.get("findings", {}).get("minor", 0),
                    "last_review": code_reviews.get("last_review_date")
                },
                "debugging_sessions": {
                    "total": debugging.get("total", 0),
                    "bugs_found": debugging.get("bugs_found", 0),
                    "bugs_fixed": debugging.get("bugs_fixed", 0)
                },
                "test_coverage": None  # Would need external tool to measure
            }

            if not self.dry_run:
                with open(current_path, 'w') as f:
                    yaml.dump(current, f, default_flow_style=False, sort_keys=False)

        total = code_reviews.get("total", 0) + debugging.get("total", 0)
        self.logger.success(f"Updated quality metrics from quality.db ({total} total records)")

        return {
            "code_reviews": code_reviews,
            "debugging_sessions": debugging,
            "validation_runs": validation
        }

    def _detect_skills(self, capsule_path: Path) -> int:
        """Step 4: Detect skills in .claude/skills/"""
        skills = self.skills_detector.detect_skills(capsule_path)

        if not skills:
            self.logger.info("No skills found in .claude/skills/")
            return 0

        # Update specs/current.yaml
        current_path = capsule_path / "specs" / "current.yaml"
        if current_path.exists():
            with open(current_path) as f:
                current = yaml.safe_load(f) or {}

            if "skills" not in current:
                current["skills"] = {}

            current["skills"]["provided"] = [
                {"name": s["name"], "path": s["path"]}
                for s in skills
            ]

            if not self.dry_run:
                with open(current_path, 'w') as f:
                    yaml.dump(current, f, default_flow_style=False, sort_keys=False)

        self.logger.success(f"Detected {len(skills)} skills in .claude/skills/")
        return len(skills)

    def _parse_mcp_config(self, capsule_path: Path) -> int:
        """Step 5: Parse .mcp.json"""
        mcp_config = self.mcp_parser.parse_mcp_config(capsule_path)
        servers = mcp_config.get("servers", [])

        if not servers:
            self.logger.info("No .mcp.json found or no servers configured")
            return 0

        # Update specs/current.yaml
        current_path = capsule_path / "specs" / "current.yaml"
        if current_path.exists():
            with open(current_path) as f:
                current = yaml.safe_load(f) or {}

            current["mcp_integration"] = {
                "config_path": ".mcp.json",
                "servers": [s["name"] for s in servers],
                "resources": mcp_config.get("resources", [])
            }

            if not self.dry_run:
                with open(current_path, 'w') as f:
                    yaml.dump(current, f, default_flow_style=False, sort_keys=False)

        self.logger.success(f"Parsed .mcp.json ({len(servers)} server(s) configured)")
        return len(servers)

    def _compute_health_score(self, capsule_path: Path, quality_metrics: Dict[str, Any]) -> float:
        """Step 6: Compute health score"""
        # Get last session from current.yaml
        current_path = capsule_path / "specs" / "current.yaml"
        last_session = None
        test_coverage = None

        if current_path.exists():
            with open(current_path) as f:
                current = yaml.safe_load(f) or {}

            auto = current.get("_auto", {})
            last_session = auto.get("last_session")

            quality = current.get("quality", {})
            metrics = quality.get("_metrics", {})
            test_coverage = metrics.get("test_coverage")

        # Compute score
        health_score = self.health_calculator.compute_health_score(
            quality_metrics,
            last_session,
            test_coverage,
            quality_metrics.get("debugging_sessions", {})
        )

        # Update specs/current.yaml
        if current_path.exists():
            with open(current_path) as f:
                current = yaml.safe_load(f) or {}

            current["_health_score"] = health_score

            if not self.dry_run:
                with open(current_path, 'w') as f:
                    yaml.dump(current, f, default_flow_style=False, sort_keys=False)

        self.logger.success(f"Computed health score: {health_score}")
        return health_score

    def _generate_claude_md(self, capsule_path: Path):
        """Step 7: Generate CLAUDE.md using existing generator"""
        import subprocess

        generator_path = CATALYST_ROOT / "tools" / "generate_claude_md.py"

        if not generator_path.exists():
            self.logger.warning("generate_claude_md.py not found, skipping CLAUDE.md generation")
            return

        if self.dry_run:
            self.logger.info("Would generate CLAUDE.md")
            return

        try:
            result = subprocess.run(
                ["python3", str(generator_path), str(capsule_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                self.logger.success("Generated CLAUDE.md")
            else:
                self.logger.warning(f"CLAUDE.md generation had issues: {result.stderr}")

        except subprocess.TimeoutExpired:
            self.logger.warning("CLAUDE.md generation timed out")
        except Exception as e:
            self.logger.warning(f"Failed to generate CLAUDE.md: {e}")

    def _generate_specifications_md(self, capsule_path: Path, capsule_name: str):
        """Step 8: Generate docs/SPECIFICATIONS.md"""
        docs_path = capsule_path / "docs"
        specs_md_path = docs_path / "SPECIFICATIONS.md"

        # Ensure docs directory exists
        docs_path.mkdir(parents=True, exist_ok=True)

        # Generate content
        content = self.specs_generator.generate(capsule_path, capsule_name)

        if not self.dry_run:
            with open(specs_md_path, 'w') as f:
                f.write(content)

        self.logger.success("Generated docs/SPECIFICATIONS.md")

    def rebuild_all(self) -> int:
        """Rebuild framework for all capsules"""
        if not CAPSULES_DIR.exists():
            print(f"{Colors.RED}Error: Capsules directory not found{Colors.END}")
            return 1

        capsules = [
            d.name for d in CAPSULES_DIR.iterdir()
            if d.is_dir() and not d.name.startswith('.')
        ]

        print(f"\n{Colors.BOLD}Rebuilding framework for {len(capsules)} capsules...{Colors.END}")

        success_count = 0
        for capsule in sorted(capsules):
            if self.rebuild_capsule(capsule):
                success_count += 1

        print(f"\n{Colors.BOLD}Summary: {success_count}/{len(capsules)} capsules rebuilt{Colors.END}")

        return 0 if success_count == len(capsules) else 1


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Rebuild capsule framework files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 tools/rebuild-framework.py example-social-capsule
  python3 tools/rebuild-framework.py --all
  python3 tools/rebuild-framework.py example-social-capsule --dry-run
  python3 tools/rebuild-framework.py example-social-capsule -v
        """
    )

    parser.add_argument(
        "capsule",
        nargs="?",
        help="Capsule name to rebuild (or use --all)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Rebuild all capsules"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    if not args.capsule and not args.all:
        parser.print_help()
        return 1

    rebuilder = FrameworkRebuilder(
        verbose=args.verbose,
        dry_run=args.dry_run
    )

    if args.all:
        return rebuilder.rebuild_all()
    else:
        # Handle both capsule name and full path
        capsule_name = args.capsule

        # If it's a path, extract the capsule name
        if "/" in capsule_name:
            capsule_path = Path(capsule_name)
            if capsule_path.exists():
                capsule_name = capsule_path.name

        success = rebuilder.rebuild_capsule(capsule_name)
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
