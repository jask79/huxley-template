#!/usr/bin/env python3
"""
Memory Intelligence Bridge for Huxley
Connects MCP memory with context intelligence and pattern learning systems
"""

import json
import logging
import sqlite3
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib

# Setup paths
Huxley_root = Path(__file__).parent.parent
sys.path.append(str(Huxley_root / "tools"))
sys.path.append(str(Huxley_root / "global" / "rag"))

try:
    from context_intelligence_engine import ContextIntelligenceEngine, ContextEntity, ContextType, PrivacyLevel
    from chroma_integration import ChromaIntegration
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

logger = logging.getLogger(__name__)

@dataclass
class PatternLearning:
    """Pattern learning data structure"""
    pattern_id: str
    pattern_type: str
    pattern_data: Dict[str, Any]
    frequency: int
    effectiveness_score: float
    last_used: str
    context_tags: List[str]
    source_interactions: List[str]

class MemoryIntelligenceBridge:
    """Bridge between MCP memory, context intelligence, and pattern learning"""
    
    def __init__(self, Huxley_root: str = "{{CATALYST_ROOT}}"):
        self.Huxley_root = Path(Huxley_root)
        
        # MCP memory path
        self.mcp_memory_path = Path.home() / ".claude" / "mcp-data" / "builder-memory.json"
        
        # Context intelligence
        self.intelligence_engine = ContextIntelligenceEngine(str(self.Huxley_root))
        
        # Pattern learning database
        self.patterns_db_path = self.Huxley_root / "registry" / "pattern_learning.db"
        self.init_patterns_database()
        
        # Knowledge base tracking
        self.knowledge_docs = []
        self.pattern_cache = {}
        
        logger.info("Memory Intelligence Bridge initialized")
    
    def init_patterns_database(self):
        """Initialize pattern learning database"""
        self.patterns_db_path.parent.mkdir(exist_ok=True, parents=True)
        
        conn = sqlite3.connect(self.patterns_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patterns (
                pattern_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                pattern_data TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                effectiveness_score REAL DEFAULT 0.5,
                last_used TEXT NOT NULL,
                context_tags TEXT NOT NULL,
                source_interactions TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_docs (
                doc_id TEXT PRIMARY KEY,
                doc_path TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                last_indexed TEXT NOT NULL,
                relevance_score REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_metrics (
                search_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                results_count INTEGER NOT NULL,
                success BOOLEAN NOT NULL,
                response_time_ms INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def populate_mcp_memory(self):
        """Populate MCP memory with Huxley knowledge"""
        
        # Gather system knowledge
        system_knowledge = self._gather_system_knowledge()
        
        # Create comprehensive MCP memory structure
        mcp_data = {
            "entities": {
                "Huxley": {
                    "type": "system",
                    "observations": [
                        "Two-lane automation pipeline (standard vs standard)",
                        "Production capsules: 7 active, Test capsules: 18 (isolated)",
                        "Daily automation at 9:10 AM via LaunchAgent",
                        "Context preservation via CLAUDE.md + MCP memory",
                        "Framework structure: standards.yaml, product.yaml, specs/, context/",
                        "Agent collaboration with 8 high-priority MCP integrations",
                        "Governance framework with Green/Yellow/Red risk classification"
                    ]
                },
                "capsule_architecture": {
                    "type": "architecture",
                    "observations": [
                        "Self-contained project capsules with full lifecycle",
                        "Immutable once deployed for stability",
                        "Clean isolation between projects",
                        "Automated framework generation for new capsules"
                    ]
                },
                "agent_ecosystem": {
                    "type": "agents",
                    "observations": [
                        "{{ORCHESTRATOR_NAME}} as chief orchestration agent",
                        "Specialized agents for different technologies",
                        "Context persistence across sessions",
                        "Intelligent delegation based on task complexity"
                    ]
                },
                "memory_intelligence": {
                    "type": "intelligence",
                    "observations": [
                        "Pattern learning from user interactions",
                        "Context-aware search with ChromaDB backend",
                        "Cross-session persistence and learning",
                        "Governance-aware decision routing"
                    ]
                }
            },
            "relations": {},
            "observations": {},
            "patterns": system_knowledge.get("patterns", {}),
            "knowledge_base": system_knowledge.get("knowledge_base", {}),
            "search_history": system_knowledge.get("search_history", {}),
            "learning_metadata": {
                "last_updated": datetime.now().isoformat(),
                "pattern_count": len(system_knowledge.get("patterns", {})),
                "knowledge_doc_count": len(system_knowledge.get("knowledge_base", {})),
                "system_maturity": "operational"
            }
        }
        
        # Ensure MCP directory exists
        self.mcp_memory_path.parent.mkdir(exist_ok=True, parents=True)
        
        # Write enhanced MCP memory
        with open(self.mcp_memory_path, 'w') as f:
            json.dump(mcp_data, f, indent=2)
        
        logger.info(f"Populated MCP memory with {len(system_knowledge.get('patterns', {}))} patterns")
        return mcp_data
    
    def _gather_system_knowledge(self) -> Dict[str, Any]:
        """Gather comprehensive system knowledge"""
        
        patterns = {}
        knowledge_base = {}
        search_history = {}
        
        # Scan capsules for patterns
        capsules_dir = self.Huxley_root / "capsules"
        if capsules_dir.exists():
            for capsule_dir in capsules_dir.iterdir():
                if capsule_dir.is_dir():
                    patterns.update(self._extract_capsule_patterns(capsule_dir))
                    knowledge_base.update(self._index_capsule_knowledge(capsule_dir))
        
        # Scan tools for operational patterns  
        tools_dir = self.Huxley_root / "tools"
        if tools_dir.exists():
            patterns.update(self._extract_tools_patterns(tools_dir))
        
        # Load existing pattern learning data
        patterns.update(self._load_existing_patterns())
        
        return {
            "patterns": patterns,
            "knowledge_base": knowledge_base,
            "search_history": search_history
        }
    
    def _extract_capsule_patterns(self, capsule_dir: Path) -> Dict[str, Any]:
        """Extract patterns from capsule structure"""
        patterns = {}
        
        # Framework structure pattern
        if (capsule_dir / "standards.yaml").exists():
            patterns[f"framework_structure_{capsule_dir.name}"] = {
                "type": "architecture",
                "description": "Complete framework structure implementation",
                "frequency": 1,
                "effectiveness": 0.9,
                "context": ["capsule", "framework", "standards"]
            }
        
        # Technology stack patterns
        if (capsule_dir / "requirements.txt").exists():
            patterns[f"python_stack_{capsule_dir.name}"] = {
                "type": "technology",
                "description": "Python-based implementation",
                "frequency": 1,
                "effectiveness": 0.8,
                "context": ["python", "backend", "api"]
            }
        
        # Mobile development pattern
        if any(capsule_dir.glob("*.xcodeproj")):
            patterns[f"ios_development_{capsule_dir.name}"] = {
                "type": "technology",
                "description": "iOS app development pattern",
                "frequency": 1,
                "effectiveness": 0.85,
                "context": ["ios", "swift", "mobile"]
            }
        
        return patterns
    
    def _extract_tools_patterns(self, tools_dir: Path) -> Dict[str, Any]:
        """Extract operational patterns from tools"""
        patterns = {}
        
        # Automation patterns
        automation_scripts = list(tools_dir.glob("*.sh")) + list(tools_dir.glob("*.py"))
        if len(automation_scripts) > 10:
            patterns["high_automation"] = {
                "type": "operational",
                "description": "High degree of system automation",
                "frequency": len(automation_scripts),
                "effectiveness": 0.9,
                "context": ["automation", "tooling", "efficiency"]
            }
        
        # Memory management pattern
        memory_tools = list(tools_dir.glob("*memory*"))
        if memory_tools:
            patterns["memory_management"] = {
                "type": "operational", 
                "description": "Sophisticated memory management system",
                "frequency": len(memory_tools),
                "effectiveness": 0.8,
                "context": ["memory", "persistence", "intelligence"]
            }
        
        return patterns
    
    def _index_capsule_knowledge(self, capsule_dir: Path) -> Dict[str, Any]:
        """Index knowledge documents from capsule"""
        knowledge = {}
        
        # Documentation files
        doc_files = []
        for pattern in ["*.md", "*.yaml", "*.yml", "*.json"]:
            doc_files.extend(capsule_dir.glob(f"**/{pattern}"))
        
        for doc_file in doc_files:
            if doc_file.is_file() and doc_file.stat().st_size > 0:
                knowledge[str(doc_file.relative_to(self.Huxley_root))] = {
                    "type": "documentation",
                    "path": str(doc_file),
                    "size": doc_file.stat().st_size,
                    "last_modified": datetime.fromtimestamp(doc_file.stat().st_mtime).isoformat(),
                    "relevance": 0.7
                }
        
        return knowledge
    
    def _load_existing_patterns(self) -> Dict[str, Any]:
        """Load existing patterns from database"""
        patterns = {}
        
        if not self.patterns_db_path.exists():
            return patterns
        
        conn = sqlite3.connect(self.patterns_db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM patterns")
        rows = cursor.fetchall()
        
        for row in rows:
            pattern_id = row[0]
            patterns[pattern_id] = {
                "type": row[1],
                "data": json.loads(row[2]),
                "frequency": row[3],
                "effectiveness": row[4],
                "last_used": row[5],
                "context": json.loads(row[6])
            }
        
        conn.close()
        return patterns
    
    def learn_pattern(self, interaction_data: Dict[str, Any]) -> str:
        """Learn a new pattern from interaction"""
        
        # Generate pattern ID
        pattern_content = json.dumps(interaction_data, sort_keys=True)
        pattern_id = hashlib.md5(pattern_content.encode()).hexdigest()[:12]
        
        # Extract pattern type
        pattern_type = self._classify_interaction(interaction_data)
        
        # Store pattern in database
        conn = sqlite3.connect(self.patterns_db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        context_tags = self._extract_context_tags(interaction_data)
        
        cursor.execute('''
            INSERT OR REPLACE INTO patterns 
            (pattern_id, pattern_type, pattern_data, frequency, effectiveness_score, 
             last_used, context_tags, source_interactions, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            pattern_id, pattern_type, pattern_content, 1, 0.5,
            now, json.dumps(context_tags), json.dumps([interaction_data.get("id", "unknown")]),
            now, now
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Learned new pattern: {pattern_id} ({pattern_type})")
        return pattern_id
    
    def _classify_interaction(self, interaction_data: Dict[str, Any]) -> str:
        """Classify interaction type for pattern learning"""
        
        content = str(interaction_data).lower()
        
        if any(word in content for word in ["fix", "debug", "error", "issue"]):
            return "debugging"
        elif any(word in content for word in ["implement", "create", "build", "develop"]):
            return "development"
        elif any(word in content for word in ["test", "validate", "verify"]):
            return "testing"
        elif any(word in content for word in ["deploy", "release", "production"]):
            return "deployment"
        elif any(word in content for word in ["analyze", "review", "audit"]):
            return "analysis"
        else:
            return "general"
    
    def _extract_context_tags(self, interaction_data: Dict[str, Any]) -> List[str]:
        """Extract context tags from interaction"""
        
        content = str(interaction_data).lower()
        tags = []
        
        # Technology tags
        tech_keywords = {
            "python": ["python", "py", "pip", "django", "flask"],
            "javascript": ["javascript", "js", "node", "npm", "react"],
            "ios": ["ios", "swift", "xcode", "iphone", "ipad"],
            "web": ["html", "css", "web", "browser", "frontend"],
            "database": ["sql", "database", "db", "postgres", "mysql"],
            "api": ["api", "rest", "endpoint", "request", "response"]
        }
        
        for tag, keywords in tech_keywords.items():
            if any(keyword in content for keyword in keywords):
                tags.append(tag)
        
        # Action tags
        action_keywords = {
            "create": ["create", "build", "implement", "develop"],
            "fix": ["fix", "debug", "resolve", "solve"],
            "optimize": ["optimize", "improve", "enhance", "performance"],
            "test": ["test", "verify", "validate", "check"]
        }
        
        for tag, keywords in action_keywords.items():
            if any(keyword in content for keyword in keywords):
                tags.append(tag)
        
        return tags
    
    def search_patterns(self, query: str, context: List[str] = None) -> List[Dict[str, Any]]:
        """Search patterns with context awareness"""
        
        conn = sqlite3.connect(self.patterns_db_path)
        cursor = conn.cursor()
        
        # Search by context tags if provided
        if context:
            context_filter = "%" + "%".join(context) + "%"
            cursor.execute('''
                SELECT * FROM patterns 
                WHERE context_tags LIKE ? OR pattern_data LIKE ?
                ORDER BY effectiveness_score DESC, frequency DESC
                LIMIT 10
            ''', (context_filter, f"%{query}%"))
        else:
            cursor.execute('''
                SELECT * FROM patterns 
                WHERE pattern_data LIKE ?
                ORDER BY effectiveness_score DESC, frequency DESC
                LIMIT 10
            ''', (f"%{query}%",))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "pattern_id": row[0],
                "type": row[1],
                "data": json.loads(row[2]),
                "frequency": row[3],
                "effectiveness": row[4],
                "last_used": row[5],
                "context": json.loads(row[6])
            })
        
        conn.close()
        
        # Record search metrics
        self._record_search_metrics(query, len(results), len(results) > 0)
        
        return results
    
    def _record_search_metrics(self, query: str, results_count: int, success: bool):
        """Record search metrics for analysis"""
        
        conn = sqlite3.connect(self.patterns_db_path)
        cursor = conn.cursor()
        
        search_id = hashlib.md5(f"{query}{datetime.now()}".encode()).hexdigest()[:12]
        
        cursor.execute('''
            INSERT INTO search_metrics 
            (search_id, query, results_count, success, response_time_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (search_id, query, results_count, success, 100, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system metrics"""
        
        conn = sqlite3.connect(self.patterns_db_path)
        cursor = conn.cursor()
        
        # Pattern metrics
        cursor.execute("SELECT COUNT(*) FROM patterns")
        pattern_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM knowledge_docs")
        knowledge_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*), AVG(CAST(success AS INTEGER)) FROM search_metrics")
        search_row = cursor.fetchone()
        search_count = search_row[0] or 0
        search_success_rate = search_row[1] or 0.0
        
        conn.close()
        
        # MCP memory size
        mcp_size = 0
        if self.mcp_memory_path.exists():
            mcp_size = self.mcp_memory_path.stat().st_size
        
        return {
            "patterns_learned": pattern_count,
            "knowledge_documents": knowledge_count,
            "search_queries": search_count,
            "search_success_rate": f"{search_success_rate * 100:.1f}%",
            "mcp_memory_size_kb": round(mcp_size / 1024, 1),
            "system_maturity": "operational" if pattern_count > 50 else "developing",
            "last_updated": datetime.now().isoformat()
        }

def main():
    """Main function for CLI usage"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Memory Intelligence Bridge for Huxley")
    parser.add_argument("--populate", action="store_true", help="Populate MCP memory")
    parser.add_argument("--metrics", action="store_true", help="Show system metrics")
    parser.add_argument("--search", type=str, help="Search patterns")
    
    args = parser.parse_args()
    
    bridge = MemoryIntelligenceBridge()
    
    if args.populate:
        print("Populating MCP memory...")
        data = bridge.populate_mcp_memory()
        print(f"✅ Populated with {len(data.get('patterns', {}))} patterns")
    
    elif args.metrics:
        metrics = bridge.get_system_metrics()
        print("📊 System Metrics:")
        for key, value in metrics.items():
            print(f"  {key}: {value}")
    
    elif args.search:
        results = bridge.search_patterns(args.search)
        print(f"🔍 Found {len(results)} patterns:")
        for result in results:
            print(f"  - {result['pattern_id']} ({result['type']}) - {result['effectiveness']:.2f}")

if __name__ == "__main__":
    main()