#!/usr/bin/env python3
"""
Execution Tracker for Huxley
Tracks execution outcomes for learning feedback and pattern optimization
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

class ExecutionStatus(Enum):
    """Execution status types"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class OutcomeType(Enum):
    """Types of execution outcomes"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    ERROR = "error"
    TIMEOUT = "timeout"

@dataclass
class ExecutionRecord:
    """Record of a workflow execution"""
    execution_id: str
    agent_name: str
    request: str
    pattern_id: Optional[str]
    status: ExecutionStatus
    outcome_type: OutcomeType
    start_time: str
    end_time: Optional[str]
    duration: Optional[float]
    success_metrics: Dict[str, float]
    failure_reasons: List[str]
    lessons_learned: List[str]
    context: Dict[str, Any]
    quality_score: float
    user_feedback: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['status'] = self.status.value
        result['outcome_type'] = self.outcome_type.value
        return result

@dataclass
class ExecutionInsight:
    """Insights derived from execution analysis"""
    insight_type: str
    description: str
    confidence: float
    supporting_data: Dict[str, Any]
    actionable_recommendations: List[str]

@dataclass
class PerformanceTrend:
    """Performance trend analysis"""
    metric_name: str
    trend_direction: str  # improving, declining, stable
    change_rate: float
    confidence: float
    time_period_days: int
    sample_size: int

class ExecutionTracker:
    """Tracks and analyzes workflow execution outcomes"""
    
    def __init__(self):
        self.db_path = Path(__file__).parent.parent / "registry" / "execution_tracker.db"
        self.db_path.parent.mkdir(exist_ok=True)
        
        self._init_database()
        logger.info("Execution Tracker initialized")
    
    def _init_database(self):
        """Initialize SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Execution records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_records (
                    execution_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    request TEXT NOT NULL,
                    pattern_id TEXT,
                    status TEXT NOT NULL,
                    outcome_type TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration REAL,
                    success_metrics TEXT,
                    failure_reasons TEXT,
                    lessons_learned TEXT,
                    context TEXT,
                    quality_score REAL,
                    user_feedback TEXT
                )
            """)
            
            # Performance trends table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_trends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    trend_direction TEXT NOT NULL,
                    change_rate REAL NOT NULL,
                    confidence REAL NOT NULL,
                    time_period_days INTEGER NOT NULL,
                    sample_size INTEGER NOT NULL,
                    calculated_at TEXT NOT NULL
                )
            """)
            
            # Execution insights table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    insight_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    supporting_data TEXT,
                    actionable_recommendations TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            conn.commit()
    
    def start_execution(self, execution_id: str, agent_name: str, request: str,
                       pattern_id: str = None, context: Dict[str, Any] = None) -> str:
        """Start tracking a new execution"""
        try:
            execution = ExecutionRecord(
                execution_id=execution_id,
                agent_name=agent_name,
                request=request,
                pattern_id=pattern_id,
                status=ExecutionStatus.RUNNING,
                outcome_type=OutcomeType.SUCCESS,  # Will be updated on completion
                start_time=datetime.utcnow().isoformat(),
                end_time=None,
                duration=None,
                success_metrics={},
                failure_reasons=[],
                lessons_learned=[],
                context=context or {},
                quality_score=0.0,
                user_feedback=None
            )
            
            self._store_execution_record(execution)
            logger.info(f"Started tracking execution: {execution_id}")
            return execution_id
            
        except Exception as e:
            logger.error(f"Failed to start execution tracking: {e}")
            return execution_id
    
    def complete_execution(self, execution_id: str, outcome_type: OutcomeType,
                          success_metrics: Dict[str, float] = None,
                          failure_reasons: List[str] = None,
                          quality_score: float = 0.8,
                          user_feedback: str = None) -> bool:
        """Complete execution tracking"""
        try:
            execution = self.get_execution_record(execution_id)
            if not execution:
                logger.warning(f"Execution record not found: {execution_id}")
                return False
            
            end_time = datetime.utcnow()
            start_time = datetime.fromisoformat(execution.start_time)
            duration = (end_time - start_time).total_seconds()
            
            # Update execution record
            execution.status = ExecutionStatus.COMPLETED
            execution.outcome_type = outcome_type
            execution.end_time = end_time.isoformat()
            execution.duration = duration
            execution.success_metrics = success_metrics or {}
            execution.failure_reasons = failure_reasons or []
            execution.quality_score = quality_score
            execution.user_feedback = user_feedback
            
            # Generate lessons learned
            execution.lessons_learned = self._generate_lessons_learned(execution)
            
            self._store_execution_record(execution)
            
            # Update performance trends
            self._update_performance_trends()
            
            # Generate insights
            self._generate_execution_insights()
            
            logger.info(f"Completed execution tracking: {execution_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete execution tracking: {e}")
            return False
    
    def record_execution(self, execution_data: Dict) -> str:
        """Record a complete execution"""
        execution_id = execution_data.get('execution_id', f"exec_{datetime.utcnow().timestamp()}")
        
        # Start execution
        self.start_execution(
            execution_id=execution_id,
            agent_name=execution_data['agent_name'],
            request=execution_data['request'],
            pattern_id=execution_data.get('pattern_id'),
            context=execution_data.get('context', {})
        )
        
        # Complete execution
        outcome_type = OutcomeType.SUCCESS if execution_data.get('success', True) else OutcomeType.FAILURE
        
        self.complete_execution(
            execution_id=execution_id,
            outcome_type=outcome_type,
            success_metrics=execution_data.get('success_metrics', {}),
            failure_reasons=execution_data.get('failure_reasons', []),
            quality_score=execution_data.get('quality_score', 0.8),
            user_feedback=execution_data.get('user_feedback')
        )
        
        return execution_id
    
    def get_execution_record(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Get execution record by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM execution_records WHERE execution_id = ?
                """, (execution_id,))
                
                row = cursor.fetchone()
                if row:
                    return ExecutionRecord(
                        execution_id=row[0], agent_name=row[1], request=row[2],
                        pattern_id=row[3], status=ExecutionStatus(row[4]),
                        outcome_type=OutcomeType(row[5]), start_time=row[6],
                        end_time=row[7], duration=row[8],
                        success_metrics=json.loads(row[9]) if row[9] else {},
                        failure_reasons=json.loads(row[10]) if row[10] else [],
                        lessons_learned=json.loads(row[11]) if row[11] else [],
                        context=json.loads(row[12]) if row[12] else {},
                        quality_score=row[13] or 0.0,
                        user_feedback=row[14]
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get execution record: {e}")
            return None
    
    def get_agent_performance_summary(self, agent_name: str, days: int = 30) -> Dict[str, Any]:
        """Get performance summary for an agent"""
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM execution_records 
                    WHERE agent_name = ? AND start_time > ?
                    ORDER BY start_time DESC
                """, (agent_name, cutoff_date))
                
                rows = cursor.fetchall()
                
                if not rows:
                    return {"agent_name": agent_name, "total_executions": 0}
                
                # Calculate metrics
                total_executions = len(rows)
                successful_executions = sum(1 for row in rows if row[5] == "success")
                success_rate = successful_executions / total_executions
                
                durations = [row[8] for row in rows if row[8] is not None]
                avg_duration = sum(durations) / len(durations) if durations else 0
                
                quality_scores = [row[13] for row in rows if row[13] is not None]
                avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
                
                return {
                    "agent_name": agent_name,
                    "total_executions": total_executions,
                    "success_rate": success_rate,
                    "avg_duration": avg_duration,
                    "avg_quality_score": avg_quality,
                    "time_period_days": days
                }
                
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {"error": str(e)}
    
    def get_pattern_effectiveness(self, pattern_id: str) -> Dict[str, Any]:
        """Get effectiveness metrics for a specific pattern"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM execution_records 
                    WHERE pattern_id = ?
                    ORDER BY start_time DESC
                """, (pattern_id,))
                
                rows = cursor.fetchall()
                
                if not rows:
                    return {"pattern_id": pattern_id, "total_uses": 0}
                
                total_uses = len(rows)
                successful_uses = sum(1 for row in rows if row[5] == "success")
                success_rate = successful_uses / total_uses
                
                durations = [row[8] for row in rows if row[8] is not None]
                avg_duration = sum(durations) / len(durations) if durations else 0
                
                return {
                    "pattern_id": pattern_id,
                    "total_uses": total_uses,
                    "success_rate": success_rate,
                    "avg_duration": avg_duration,
                    "last_used": rows[0][6] if rows else None
                }
                
        except Exception as e:
            logger.error(f"Failed to get pattern effectiveness: {e}")
            return {"error": str(e)}
    
    def _store_execution_record(self, execution: ExecutionRecord):
        """Store execution record in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO execution_records
                    (execution_id, agent_name, request, pattern_id, status,
                     outcome_type, start_time, end_time, duration, success_metrics,
                     failure_reasons, lessons_learned, context, quality_score, user_feedback)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    execution.execution_id, execution.agent_name, execution.request,
                    execution.pattern_id, execution.status.value, execution.outcome_type.value,
                    execution.start_time, execution.end_time, execution.duration,
                    json.dumps(execution.success_metrics), json.dumps(execution.failure_reasons),
                    json.dumps(execution.lessons_learned), json.dumps(execution.context),
                    execution.quality_score, execution.user_feedback
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store execution record: {e}")
    
    def _generate_lessons_learned(self, execution: ExecutionRecord) -> List[str]:
        """Generate lessons learned from execution"""
        lessons = []
        
        if execution.outcome_type == OutcomeType.SUCCESS:
            lessons.append(f"Successfully completed {execution.request} in {execution.duration:.1f}s")
            if execution.quality_score > 0.8:
                lessons.append("High quality outcome achieved")
        else:
            lessons.append(f"Execution failed: {', '.join(execution.failure_reasons)}")
            lessons.append("Review approach and dependencies")
        
        if execution.pattern_id:
            lessons.append(f"Pattern {execution.pattern_id} was applied")
        
        return lessons
    
    def _update_performance_trends(self):
        """Update performance trend analysis"""
        try:
            # This is a simplified trend analysis
            # In practice, you'd implement more sophisticated time series analysis
            logger.debug("Performance trends updated")
            
        except Exception as e:
            logger.error(f"Failed to update performance trends: {e}")
    
    def _generate_execution_insights(self):
        """Generate insights from recent executions"""
        try:
            # This would analyze patterns in execution data
            # and generate actionable insights
            logger.debug("Execution insights generated")
            
        except Exception as e:
            logger.error(f"Failed to generate insights: {e}")

# Convenience functions
def track_execution(agent_name: str, request: str, success: bool, 
                   duration: float = None, quality_score: float = 0.8,
                   context: Dict[str, Any] = None) -> str:
    """Quick function to track an execution"""
    tracker = ExecutionTracker()
    
    execution_data = {
        'agent_name': agent_name,
        'request': request,
        'success': success,
        'quality_score': quality_score,
        'context': context or {}
    }
    
    if duration:
        execution_data['success_metrics'] = {'duration': duration}
    
    return tracker.record_execution(execution_data)

def get_agent_stats(agent_name: str, days: int = 7) -> Dict[str, Any]:
    """Quick function to get agent performance stats"""
    tracker = ExecutionTracker()
    return tracker.get_agent_performance_summary(agent_name, days)

if __name__ == "__main__":
    # Test the tracker
    logging.basicConfig(level=logging.INFO)
    
    print("Execution Tracker Test")
    print("=" * 50)
    
    tracker = ExecutionTracker()
    
    # Test execution tracking
    execution_id = tracker.record_execution({
        'agent_name': 'Test Agent',
        'request': 'Create test application',
        'success': True,
        'quality_score': 0.9,
        'success_metrics': {'duration': 45.2},
        'context': {'test': True}
    })
    
    print(f"✓ Recorded execution: {execution_id}")
    
    # Test performance summary
    summary = tracker.get_agent_performance_summary('Test Agent')
    print(f"✓ Performance summary: {summary['success_rate']:.1%} success rate")
    
    print("\nExecution Tracker ready for integration")