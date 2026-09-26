#!/usr/bin/env python3
"""
Agent Effectiveness Tracker for Huxley
Tracks and analyzes agent performance and effectiveness
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

class EffectivenessMetric(Enum):
    """Types of effectiveness metrics"""
    SUCCESS_RATE = "success_rate"
    COMPLETION_TIME = "completion_time"
    QUALITY_SCORE = "quality_score"
    USER_SATISFACTION = "user_satisfaction"
    RESOURCE_EFFICIENCY = "resource_efficiency"

@dataclass
class AgentPerformanceRecord:
    """Performance record for an agent"""
    agent_name: str
    task_type: str
    domain: str
    success: bool
    completion_time: float
    quality_score: float
    user_satisfaction: float
    resource_usage: float
    context: Dict[str, Any]
    timestamp: str
    execution_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class EffectivenessScore:
    """Comprehensive effectiveness score"""
    agent_name: str
    overall_score: float
    success_rate: float
    avg_completion_time: float
    quality_average: float
    satisfaction_average: float
    efficiency_score: float
    confidence: float
    sample_size: int
    last_updated: str

@dataclass
class AgentInvocationRecord:
    """Tracks individual agent delegations prior to completion"""
    invocation_id: str
    agent_name: str
    task_description: str
    timestamp: str
    status: str
    context: Dict[str, Any]

class AgentEffectivenessTracker:
    """Tracks and analyzes agent effectiveness metrics"""
    
    def __init__(self):
        self.db_path = Path(__file__).parent.parent / "registry" / "agent_effectiveness.db"
        self.db_path.parent.mkdir(exist_ok=True)
        
        self._init_database()
        logger.info("Agent Effectiveness Tracker initialized")
    
    def _init_database(self):
        """Initialize SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Performance records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    completion_time REAL NOT NULL,
                    quality_score REAL NOT NULL,
                    user_satisfaction REAL NOT NULL,
                    resource_usage REAL NOT NULL,
                    context TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    execution_id TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_invocations (
                    invocation_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    task_description TEXT,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    context TEXT
                )
            """)
            
            # Effectiveness scores table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS effectiveness_scores (
                    agent_name TEXT PRIMARY KEY,
                    overall_score REAL NOT NULL,
                    success_rate REAL NOT NULL,
                    avg_completion_time REAL NOT NULL,
                    quality_average REAL NOT NULL,
                    satisfaction_average REAL NOT NULL,
                    efficiency_score REAL NOT NULL,
                    confidence REAL NOT NULL,
                    sample_size INTEGER NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)
            
            conn.commit()

    def record_agent_invocation(
        self,
        agent_name: str,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Record the start of an agent invocation and return tracking id"""
        invocation_id = f"invoke_{uuid.uuid4().hex}"
        timestamp = datetime.utcnow().isoformat()
        context_payload = context or {}

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO agent_invocations
                    (invocation_id, agent_name, task_description, timestamp, status, context)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invocation_id,
                        agent_name,
                        task_description,
                        timestamp,
                        "pending",
                        json.dumps(context_payload)
                    )
                )
                conn.commit()
        except Exception as exc:
            logger.error(f"Failed to record agent invocation: {exc}")

        return invocation_id

    def _update_invocation_status(
        self,
        invocation_id: Optional[str],
        status: str,
        updates: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update existing invocation record with new status/context"""
        if not invocation_id:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT context FROM agent_invocations WHERE invocation_id = ?",
                    (invocation_id,)
                )
                row = cursor.fetchone()

                if not row:
                    cursor.execute(
                        """
                        INSERT INTO agent_invocations
                        (invocation_id, agent_name, task_description, timestamp, status, context)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            invocation_id,
                            "unknown",
                            None,
                            datetime.utcnow().isoformat(),
                            status,
                            json.dumps(updates or {})
                        )
                    )
                else:
                    existing_context = {}
                    if row[0]:
                        try:
                            existing_context = json.loads(row[0])
                        except json.JSONDecodeError:
                            existing_context = {}

                    if updates:
                        existing_context.update(updates)

                    cursor.execute(
                        """
                        UPDATE agent_invocations
                        SET status = ?, context = ?
                        WHERE invocation_id = ?
                        """,
                        (status, json.dumps(existing_context), invocation_id)
                    )

                conn.commit()
        except Exception as exc:
            logger.error(f"Failed to update invocation {invocation_id}: {exc}")

    def mark_invocation_outcome(
        self,
        invocation_id: Optional[str],
        success: bool,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Public helper to close out an invocation without full performance record"""
        status = "completed" if success else "failed"
        updates = {"success": success}
        if metadata:
            updates.update(metadata)
        self._update_invocation_status(invocation_id, status=status, updates=updates)

    def record_performance(self, record: AgentPerformanceRecord):
        """Record agent performance"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO performance_records
                    (agent_name, task_type, domain, success, completion_time,
                     quality_score, user_satisfaction, resource_usage, context,
                     timestamp, execution_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.agent_name, record.task_type, record.domain,
                    record.success, record.completion_time, record.quality_score,
                    record.user_satisfaction, record.resource_usage,
                    json.dumps(record.context), record.timestamp, record.execution_id
                ))
                
                conn.commit()
                
                # Update effectiveness scores
                self._update_effectiveness_scores(record.agent_name)

                # Update invocation status if we have a matching execution/ invocation id
                self._update_invocation_status(
                    invocation_id=record.execution_id,
                    status="completed",
                    updates={
                        "success": record.success,
                        "completion_time": record.completion_time,
                        "quality_score": record.quality_score,
                        "user_satisfaction": record.user_satisfaction,
                        "resource_usage": record.resource_usage
                    }
                )
                
        except Exception as e:
            logger.error(f"Failed to record performance: {e}")
    
    def get_agent_effectiveness(self, agent_name: str) -> Optional[EffectivenessScore]:
        """Get effectiveness score for specific agent"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM effectiveness_scores WHERE agent_name = ?
                """, (agent_name,))
                
                row = cursor.fetchone()
                if row:
                    return EffectivenessScore(
                        agent_name=row[0], overall_score=row[1], success_rate=row[2],
                        avg_completion_time=row[3], quality_average=row[4],
                        satisfaction_average=row[5], efficiency_score=row[6],
                        confidence=row[7], sample_size=row[8], last_updated=row[9]
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get effectiveness: {e}")
            return None

    def get_all_agent_metrics(self) -> Dict[str, EffectivenessScore]:
        """Return effectiveness scores for all agents"""
        metrics: Dict[str, EffectivenessScore] = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM effectiveness_scores")
                rows = cursor.fetchall()
                
                for row in rows:
                    score = EffectivenessScore(
                        agent_name=row[0],
                        overall_score=row[1],
                        success_rate=row[2],
                        avg_completion_time=row[3],
                        quality_average=row[4],
                        satisfaction_average=row[5],
                        efficiency_score=row[6],
                        confidence=row[7],
                        sample_size=row[8],
                        last_updated=row[9]
                    )
                    metrics[score.agent_name] = score
        except Exception as exc:
            logger.error(f"Failed to fetch agent metrics: {exc}")
        
        return metrics
    
    def get_top_agents_for_task(self, task_type: str, domain: str = "", limit: int = 3) -> List[EffectivenessScore]:
        """Get top performing agents for a specific task type"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get agents who have handled this task type
                query = """
                    SELECT DISTINCT agent_name FROM performance_records 
                    WHERE task_type = ?
                """
                params = [task_type]
                
                if domain:
                    query += " AND domain = ?"
                    params.append(domain)
                
                cursor.execute(query, params)
                agent_names = [row[0] for row in cursor.fetchall()]
                
                # Get their effectiveness scores
                effectiveness_scores = []
                for agent_name in agent_names:
                    score = self.get_agent_effectiveness(agent_name)
                    if score:
                        effectiveness_scores.append(score)
                
                # Sort by overall score
                effectiveness_scores.sort(key=lambda x: x.overall_score, reverse=True)
                return effectiveness_scores[:limit]
                
        except Exception as e:
            logger.error(f"Failed to get top agents: {e}")
            return []
    
    def _update_effectiveness_scores(self, agent_name: str):
        """Update effectiveness scores for an agent"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get recent performance data (last 30 days)
                cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
                
                cursor.execute("""
                    SELECT * FROM performance_records 
                    WHERE agent_name = ? AND timestamp > ?
                    ORDER BY timestamp DESC
                """, (agent_name, cutoff_date))
                
                rows = cursor.fetchall()
                if not rows:
                    return
                
                # Calculate metrics
                total_records = len(rows)
                successes = sum(1 for row in rows if row[4])  # success column
                success_rate = successes / total_records
                
                completion_times = [row[5] for row in rows]  # completion_time column
                avg_completion_time = sum(completion_times) / len(completion_times)
                
                quality_scores = [row[6] for row in rows]  # quality_score column
                quality_average = sum(quality_scores) / len(quality_scores)
                
                satisfaction_scores = [row[7] for row in rows]  # user_satisfaction column
                satisfaction_average = sum(satisfaction_scores) / len(satisfaction_scores)
                
                resource_usage = [row[8] for row in rows]  # resource_usage column
                efficiency_score = 1.0 - (sum(resource_usage) / len(resource_usage))  # Lower usage = higher efficiency
                
                # Calculate overall score
                overall_score = (
                    success_rate * 0.3 +
                    quality_average * 0.25 +
                    satisfaction_average * 0.25 +
                    efficiency_score * 0.2
                )
                
                # Calculate confidence based on sample size
                confidence = min(1.0, total_records / 10.0)  # Full confidence at 10+ samples
                
                # Store effectiveness score
                effectiveness_score = EffectivenessScore(
                    agent_name=agent_name,
                    overall_score=overall_score,
                    success_rate=success_rate,
                    avg_completion_time=avg_completion_time,
                    quality_average=quality_average,
                    satisfaction_average=satisfaction_average,
                    efficiency_score=efficiency_score,
                    confidence=confidence,
                    sample_size=total_records,
                    last_updated=datetime.utcnow().isoformat()
                )
                
                cursor.execute("""
                    INSERT OR REPLACE INTO effectiveness_scores
                    (agent_name, overall_score, success_rate, avg_completion_time,
                     quality_average, satisfaction_average, efficiency_score,
                     confidence, sample_size, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    effectiveness_score.agent_name, effectiveness_score.overall_score,
                    effectiveness_score.success_rate, effectiveness_score.avg_completion_time,
                    effectiveness_score.quality_average, effectiveness_score.satisfaction_average,
                    effectiveness_score.efficiency_score, effectiveness_score.confidence,
                    effectiveness_score.sample_size, effectiveness_score.last_updated
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to update effectiveness scores: {e}")

# Convenience functions
def track_agent_performance(agent_name: str, task_type: str, domain: str,
                          success: bool, completion_time: float, quality_score: float = 0.8,
                          user_satisfaction: float = 0.8, resource_usage: float = 0.5,
                          context: Dict[str, Any] = None, execution_id: str = None) -> None:
    """Quick function to track agent performance"""
    tracker = AgentEffectivenessTracker()
    
    record = AgentPerformanceRecord(
        agent_name=agent_name,
        task_type=task_type,
        domain=domain,
        success=success,
        completion_time=completion_time,
        quality_score=quality_score,
        user_satisfaction=user_satisfaction,
        resource_usage=resource_usage,
        context=context or {},
        timestamp=datetime.utcnow().isoformat(),
        execution_id=execution_id or f"exec_{datetime.utcnow().timestamp()}"
    )
    
    tracker.record_performance(record)

def get_best_agent_for_task(task_type: str, domain: str = "") -> Optional[str]:
    """Quick function to get best agent for a task"""
    tracker = AgentEffectivenessTracker()
    top_agents = tracker.get_top_agents_for_task(task_type, domain, limit=1)
    return top_agents[0].agent_name if top_agents else None

if __name__ == "__main__":
    # Test the tracker
    logging.basicConfig(level=logging.INFO)
    
    print("Agent Effectiveness Tracker Test")
    print("=" * 50)
    
    tracker = AgentEffectivenessTracker()
    
    # Test recording performance
    test_record = AgentPerformanceRecord(
        agent_name="Test Agent",
        task_type="creation",
        domain="ios",
        success=True,
        completion_time=25.5,
        quality_score=0.9,
        user_satisfaction=0.85,
        resource_usage=0.3,
        context={"test": True},
        timestamp=datetime.utcnow().isoformat(),
        execution_id="test_exec_001"
    )
    
    tracker.record_performance(test_record)
    print("✓ Recorded test performance")
    
    # Test getting effectiveness
    effectiveness = tracker.get_agent_effectiveness("Test Agent")
    if effectiveness:
        print(f"✓ Agent effectiveness: {effectiveness.overall_score:.3f}")
    
    print("\nAgent Effectiveness Tracker ready for integration")
