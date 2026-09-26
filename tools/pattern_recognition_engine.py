#!/usr/bin/env python3
"""
Pattern Recognition Engine for Huxley
Detects and analyzes workflow patterns from multi-agent interactions
"""

import json
import logging
import sqlite3
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from collections import defaultdict, Counter
import sys

# Import existing components
try:
    from context_intelligence_engine import ContextIntelligenceEngine, ContextType
    from context_analyzer import ContextAnalyzer
    from agent_effectiveness_tracker import AgentEffectivenessTracker
except ImportError as e:
    logging.warning(f"Some dependencies not available: {e}")

logger = logging.getLogger(__name__)

class PatternType(Enum):
    """Types of workflow patterns"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ITERATIVE = "iterative"
    ESCALATION = "escalation"
    RECOVERY = "recovery"
    CONTEXT_DEPENDENT = "context_dependent"

class PatternStatus(Enum):
    """Pattern lifecycle status"""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"
    VALIDATED = "validated"

@dataclass
class AgentStep:
    """Individual step in a workflow pattern"""
    agent_name: str
    action_type: str
    duration_avg: float
    success_rate: float
    dependencies: List[str]
    outputs: List[str]
    confidence: float = 0.8
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class WorkflowPattern:
    """Core workflow pattern representation"""
    pattern_id: str
    pattern_type: PatternType
    name: str
    description: str
    agent_sequence: List[AgentStep]
    success_rate: float
    avg_completion_time: float
    context_triggers: List[str]
    outcome_quality: float
    usage_frequency: int
    confidence_score: float
    status: PatternStatus
    created_at: str
    last_updated: str
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['pattern_type'] = self.pattern_type.value
        result['status'] = self.status.value
        result['agent_sequence'] = [step.to_dict() for step in self.agent_sequence]
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowPattern':
        data['pattern_type'] = PatternType(data['pattern_type'])
        data['status'] = PatternStatus(data['status'])
        data['agent_sequence'] = [AgentStep(**step) for step in data['agent_sequence']]
        return cls(**data)

@dataclass
class FailureMode:
    """Pattern failure analysis"""
    failure_type: str
    frequency: int
    impact_score: float
    recovery_strategy: str
    context: Dict[str, Any]

@dataclass
class PatternMetrics:
    """Pattern effectiveness metrics"""
    pattern_id: str
    executions_count: int
    success_rate: float
    failure_modes: List[FailureMode]
    resource_efficiency: float
    user_satisfaction: float
    improvement_trend: float
    contextual_performance: Dict[str, float]
    last_calculated: str

@dataclass
class PatternRecommendation:
    """Pattern application recommendation"""
    pattern_id: str
    confidence_score: float
    estimated_success_rate: float
    estimated_duration: float
    reasoning: str
    alternatives: List[str]
    risk_factors: List[str]

class PatternRecognitionEngine:
    """Core pattern recognition and analysis engine"""
    
    def __init__(self):
        self.db_path = Path(__file__).parent.parent / "registry" / "pattern_recognition.db"
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Initialize components
        try:
            self.context_engine = ContextIntelligenceEngine()
            self.context_analyzer = ContextAnalyzer()
            self.effectiveness_tracker = AgentEffectivenessTracker()
            self.components_available = True
        except Exception as e:
            logger.warning(f"Pattern Recognition initialized without full components: {e}")
            self.context_engine = None
            self.context_analyzer = None
            self.effectiveness_tracker = None
            self.components_available = False
        
        # Pattern analysis configuration
        self.config = {
            "min_pattern_frequency": 3,
            "min_success_rate": 0.6,
            "lookback_days": 30,
            "sequence_min_length": 2,
            "sequence_max_length": 6,
            "confidence_threshold": 0.7
        }
        
        # Setup database
        self._init_database()
        
        logger.info("Pattern Recognition Engine initialized")
    
    def _init_database(self):
        """Initialize SQLite database for pattern storage"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Patterns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    pattern_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    agent_sequence TEXT NOT NULL,
                    success_rate REAL NOT NULL,
                    avg_completion_time REAL NOT NULL,
                    context_triggers TEXT,
                    outcome_quality REAL NOT NULL,
                    usage_frequency INTEGER NOT NULL,
                    confidence_score REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    tags TEXT
                )
            """)
            
            # Pattern executions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    success BOOLEAN,
                    outcome_quality REAL,
                    context TEXT,
                    agents_used TEXT,
                    duration REAL,
                    failure_reason TEXT,
                    FOREIGN KEY (pattern_id) REFERENCES workflow_patterns (pattern_id)
                )
            """)
            
            # Pattern metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id TEXT NOT NULL,
                    metric_date TEXT NOT NULL,
                    executions_count INTEGER NOT NULL,
                    success_rate REAL NOT NULL,
                    resource_efficiency REAL NOT NULL,
                    user_satisfaction REAL NOT NULL,
                    improvement_trend REAL NOT NULL,
                    contextual_performance TEXT,
                    FOREIGN KEY (pattern_id) REFERENCES workflow_patterns (pattern_id)
                )
            """)
            
            conn.commit()
    
    def detect_patterns(self, lookback_days: int = None) -> List[WorkflowPattern]:
        """Main pattern detection pipeline"""
        if not self.components_available:
            logger.warning("Pattern detection requires full component availability")
            return []
        
        lookback_days = lookback_days or self.config["lookback_days"]
        
        try:
            logger.info(f"Starting pattern detection for last {lookback_days} days")
            
            # Get historical workflow data
            workflow_data = self._extract_workflow_data(lookback_days)
            
            if not workflow_data:
                logger.info("No workflow data available for pattern detection")
                return []
            
            # Detect different types of patterns
            sequential_patterns = self._detect_sequential_patterns(workflow_data)
            parallel_patterns = self._detect_parallel_patterns(workflow_data)
            iterative_patterns = self._detect_iterative_patterns(workflow_data)
            recovery_patterns = self._detect_recovery_patterns(workflow_data)
            
            # Combine all patterns
            all_patterns = sequential_patterns + parallel_patterns + iterative_patterns + recovery_patterns
            
            # Filter and validate patterns
            validated_patterns = self._validate_patterns(all_patterns, workflow_data)
            
            # Store new patterns
            for pattern in validated_patterns:
                self._store_pattern(pattern)
            
            logger.info(f"Detected {len(validated_patterns)} workflow patterns")
            return validated_patterns
            
        except Exception as e:
            logger.error(f"Pattern detection failed: {e}")
            return []
    
    def _extract_workflow_data(self, lookback_days: int) -> List[Dict[str, Any]]:
        """Extract workflow execution data from context engine"""
        if not self.context_engine:
            return []
        
        try:
            # Get relevant context entities from specified time period
            cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
            
            with sqlite3.connect(self.context_engine.db_path) as conn:
                cursor = conn.cursor()
                
                # Get agent interactions and outcomes
                cursor.execute("""
                    SELECT * FROM context_entities 
                    WHERE created_at > ? 
                    AND (type = 'agent_interaction' OR type = 'outcome')
                    ORDER BY created_at ASC
                """, (cutoff_date.isoformat(),))
                
                rows = cursor.fetchall()
                
                workflow_data = []
                for row in rows:
                    entity_data = {
                        'id': row[0],
                        'type': row[1],
                        'content': json.loads(row[2]),
                        'created_at': row[4],
                        'source_agent': row[8]
                    }
                    workflow_data.append(entity_data)
                
                return workflow_data
                
        except Exception as e:
            logger.error(f"Failed to extract workflow data: {e}")
            return []
    
    def _detect_sequential_patterns(self, workflow_data: List[Dict[str, Any]]) -> List[WorkflowPattern]:
        """Detect sequential agent collaboration patterns"""
        patterns = []
        
        # Group interactions by session
        sessions = defaultdict(list)
        for item in workflow_data:
            if item['type'] == 'agent_interaction':
                content = item['content']
                session_id = content.get('metadata', {}).get('session_id', 'unknown')
                sessions[session_id].append({
                    'agent': item['source_agent'],
                    'timestamp': item['created_at'],
                    'task': content.get('user_input', ''),
                    'response': content.get('agent_response', ''),
                    'metadata': content.get('metadata', {})
                })
        
        # Analyze sequences within sessions
        for session_id, interactions in sessions.items():
            if len(interactions) < self.config["sequence_min_length"]:
                continue
            
            # Sort by timestamp
            interactions.sort(key=lambda x: x['timestamp'])
            
            # Extract agent sequences
            agent_sequence = [interaction['agent'] for interaction in interactions]
            
            # Look for repeated subsequences
            sequences = self._find_subsequences(agent_sequence)
            
            for sequence in sequences:
                if len(sequence) >= self.config["sequence_min_length"]:
                    pattern = self._create_sequential_pattern(sequence, interactions, workflow_data)
                    if pattern:
                        patterns.append(pattern)
        
        return self._deduplicate_patterns(patterns)
    
    def _detect_parallel_patterns(self, workflow_data: List[Dict[str, Any]]) -> List[WorkflowPattern]:
        """Detect parallel agent collaboration patterns"""
        patterns = []
        
        # Group by time windows
        time_windows = self._group_by_time_windows(workflow_data, window_minutes=10)
        
        for window_start, interactions in time_windows.items():
            if len(interactions) < 2:
                continue
            
            # Find simultaneous agent activities
            agents_in_window = set(item['source_agent'] for item in interactions if item['source_agent'])
            
            if len(agents_in_window) >= 2:
                pattern = self._create_parallel_pattern(agents_in_window, interactions, workflow_data)
                if pattern:
                    patterns.append(pattern)
        
        return self._deduplicate_patterns(patterns)
    
    def _detect_iterative_patterns(self, workflow_data: List[Dict[str, Any]]) -> List[WorkflowPattern]:
        """Detect iterative refinement patterns"""
        patterns = []
        
        # Look for repeated agent interactions with refinement
        agent_cycles = defaultdict(list)
        
        for item in workflow_data:
            if item['type'] == 'agent_interaction':
                agent = item['source_agent']
                content = item['content']
                task_type = content.get('user_input', '').lower()
                
                # Look for refinement keywords
                refinement_keywords = ['fix', 'improve', 'refine', 'update', 'modify', 'adjust']
                if any(keyword in task_type for keyword in refinement_keywords):
                    agent_cycles[agent].append(item)
        
        # Analyze cycles for patterns
        for agent, cycles in agent_cycles.items():
            if len(cycles) >= 3:  # At least 3 iterations
                pattern = self._create_iterative_pattern(agent, cycles, workflow_data)
                if pattern:
                    patterns.append(pattern)
        
        return patterns
    
    def _detect_recovery_patterns(self, workflow_data: List[Dict[str, Any]]) -> List[WorkflowPattern]:
        """Detect failure recovery patterns"""
        patterns = []
        
        # Find failure outcomes followed by recovery attempts
        failures = []
        recoveries = []
        
        for item in workflow_data:
            if item['type'] == 'outcome':
                content = item['content']
                if not content.get('success', True):
                    failures.append(item)
                elif content.get('success', False) and item['created_at'] > failures[-1]['created_at'] if failures else False:
                    recoveries.append((failures[-1] if failures else None, item))
        
        # Analyze recovery patterns
        for failure, recovery in recoveries:
            if failure:
                pattern = self._create_recovery_pattern(failure, recovery, workflow_data)
                if pattern:
                    patterns.append(pattern)
        
        return patterns
    
    def _find_subsequences(self, sequence: List[str]) -> List[List[str]]:
        """Find repeated subsequences in agent sequence"""
        subsequences = []
        min_len = self.config["sequence_min_length"]
        max_len = min(self.config["sequence_max_length"], len(sequence))
        
        for length in range(min_len, max_len + 1):
            for i in range(len(sequence) - length + 1):
                subseq = sequence[i:i + length]
                
                # Count occurrences
                count = 0
                for j in range(len(sequence) - length + 1):
                    if sequence[j:j + length] == subseq:
                        count += 1
                
                if count >= self.config["min_pattern_frequency"]:
                    subsequences.append(subseq)
        
        return subsequences
    
    def _group_by_time_windows(self, workflow_data: List[Dict[str, Any]], window_minutes: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        """Group workflow data by time windows"""
        windows = defaultdict(list)
        
        for item in workflow_data:
            timestamp = datetime.fromisoformat(item['created_at'])
            window_start = timestamp.replace(minute=(timestamp.minute // window_minutes) * window_minutes, second=0, microsecond=0)
            windows[window_start.isoformat()].append(item)
        
        return dict(windows)
    
    def _create_sequential_pattern(self, sequence: List[str], interactions: List[Dict[str, Any]], workflow_data: List[Dict[str, Any]]) -> Optional[WorkflowPattern]:
        """Create a sequential workflow pattern"""
        try:
            pattern_id = f"seq_{hash('->'.join(sequence))}"
            
            # Build agent steps
            agent_steps = []
            for agent in sequence:
                agent_interactions = [i for i in interactions if i['agent'] == agent]
                
                if agent_interactions:
                    avg_duration = 30.0  # Default, could be calculated from metadata
                    success_rate = 0.8   # Default, could be calculated from outcomes
                    
                    step = AgentStep(
                        agent_name=agent,
                        action_type="sequential_task",
                        duration_avg=avg_duration,
                        success_rate=success_rate,
                        dependencies=[sequence[i-1]] if sequence.index(agent) > 0 else [],
                        outputs=["task_completion"],
                        confidence=0.8
                    )
                    agent_steps.append(step)
            
            # Calculate pattern metrics
            success_rate = self._calculate_pattern_success_rate(sequence, workflow_data)
            avg_completion_time = sum(step.duration_avg for step in agent_steps)
            
            pattern = WorkflowPattern(
                pattern_id=pattern_id,
                pattern_type=PatternType.SEQUENTIAL,
                name=f"Sequential: {' → '.join(sequence)}",
                description=f"Sequential workflow pattern involving {len(sequence)} agents",
                agent_sequence=agent_steps,
                success_rate=success_rate,
                avg_completion_time=avg_completion_time,
                context_triggers=self._extract_context_triggers(interactions),
                outcome_quality=success_rate,
                usage_frequency=len([i for i in interactions if i['agent'] in sequence]),
                confidence_score=min(0.9, success_rate + 0.1),
                status=PatternStatus.EXPERIMENTAL,
                created_at=datetime.utcnow().isoformat(),
                last_updated=datetime.utcnow().isoformat(),
                tags=["sequential", "multi-agent"]
            )
            
            return pattern
            
        except Exception as e:
            logger.error(f"Failed to create sequential pattern: {e}")
            return None
    
    def _create_parallel_pattern(self, agents: Set[str], interactions: List[Dict[str, Any]], workflow_data: List[Dict[str, Any]]) -> Optional[WorkflowPattern]:
        """Create a parallel workflow pattern"""
        try:
            pattern_id = f"par_{hash('&'.join(sorted(agents)))}"
            
            # Build agent steps for parallel execution
            agent_steps = []
            for agent in sorted(agents):
                step = AgentStep(
                    agent_name=agent,
                    action_type="parallel_task",
                    duration_avg=25.0,  # Parallel tasks might be faster
                    success_rate=0.75,
                    dependencies=[],  # No dependencies in parallel
                    outputs=["parallel_result"],
                    confidence=0.7
                )
                agent_steps.append(step)
            
            pattern = WorkflowPattern(
                pattern_id=pattern_id,
                pattern_type=PatternType.PARALLEL,
                name=f"Parallel: {' & '.join(sorted(agents))}",
                description=f"Parallel workflow pattern with {len(agents)} simultaneous agents",
                agent_sequence=agent_steps,
                success_rate=0.75,
                avg_completion_time=max(step.duration_avg for step in agent_steps),
                context_triggers=self._extract_context_triggers(interactions),
                outcome_quality=0.75,
                usage_frequency=len(interactions),
                confidence_score=0.7,
                status=PatternStatus.EXPERIMENTAL,
                created_at=datetime.utcnow().isoformat(),
                last_updated=datetime.utcnow().isoformat(),
                tags=["parallel", "multi-agent", "simultaneous"]
            )
            
            return pattern
            
        except Exception as e:
            logger.error(f"Failed to create parallel pattern: {e}")
            return None
    
    def _create_iterative_pattern(self, agent: str, cycles: List[Dict[str, Any]], workflow_data: List[Dict[str, Any]]) -> Optional[WorkflowPattern]:
        """Create an iterative refinement pattern"""
        try:
            pattern_id = f"iter_{hash(agent + '_refinement')}"
            
            # Single agent in iterative cycles
            step = AgentStep(
                agent_name=agent,
                action_type="iterative_refinement",
                duration_avg=20.0,
                success_rate=0.85,  # Iterative patterns often improve over iterations
                dependencies=[agent],  # Self-dependency for iteration
                outputs=["refined_result"],
                confidence=0.8
            )
            
            pattern = WorkflowPattern(
                pattern_id=pattern_id,
                pattern_type=PatternType.ITERATIVE,
                name=f"Iterative: {agent} Refinement",
                description=f"Iterative refinement pattern with {agent}",
                agent_sequence=[step],
                success_rate=0.85,
                avg_completion_time=step.duration_avg * len(cycles),
                context_triggers=["refinement", "improvement", "iteration"],
                outcome_quality=0.9,  # Iterative patterns often produce higher quality
                usage_frequency=len(cycles),
                confidence_score=0.8,
                status=PatternStatus.EXPERIMENTAL,
                created_at=datetime.utcnow().isoformat(),
                last_updated=datetime.utcnow().isoformat(),
                tags=["iterative", "refinement", "quality-improvement"]
            )
            
            return pattern
            
        except Exception as e:
            logger.error(f"Failed to create iterative pattern: {e}")
            return None
    
    def _create_recovery_pattern(self, failure: Dict[str, Any], recovery: Dict[str, Any], workflow_data: List[Dict[str, Any]]) -> Optional[WorkflowPattern]:
        """Create a failure recovery pattern"""
        try:
            failed_agent = failure.get('source_agent', 'unknown')
            recovery_agent = recovery.get('source_agent', 'unknown')
            
            pattern_id = f"rec_{hash(failed_agent + '_' + recovery_agent)}"
            
            # Build recovery sequence
            agent_steps = [
                AgentStep(
                    agent_name=recovery_agent,
                    action_type="failure_recovery",
                    duration_avg=35.0,  # Recovery might take longer
                    success_rate=0.7,   # Recovery success rate
                    dependencies=[],
                    outputs=["recovered_result"],
                    confidence=0.6
                )
            ]
            
            pattern = WorkflowPattern(
                pattern_id=pattern_id,
                pattern_type=PatternType.RECOVERY,
                name=f"Recovery: {failed_agent} → {recovery_agent}",
                description=f"Failure recovery pattern from {failed_agent} to {recovery_agent}",
                agent_sequence=agent_steps,
                success_rate=0.7,
                avg_completion_time=35.0,
                context_triggers=["failure", "error", "recovery"],
                outcome_quality=0.65,
                usage_frequency=1,
                confidence_score=0.6,
                status=PatternStatus.EXPERIMENTAL,
                created_at=datetime.utcnow().isoformat(),
                last_updated=datetime.utcnow().isoformat(),
                tags=["recovery", "failure-handling", "resilience"]
            )
            
            return pattern
            
        except Exception as e:
            logger.error(f"Failed to create recovery pattern: {e}")
            return None
    
    def _calculate_pattern_success_rate(self, sequence: List[str], workflow_data: List[Dict[str, Any]]) -> float:
        """Calculate success rate for a pattern"""
        # Count successful vs failed outcomes for this sequence
        successes = 0
        total = 0
        
        for item in workflow_data:
            if item['type'] == 'outcome' and item.get('source_agent') in sequence:
                total += 1
                if item['content'].get('success', False):
                    successes += 1
        
        return (successes / total) if total > 0 else 0.7  # Default assumption
    
    def _extract_context_triggers(self, interactions: List[Dict[str, Any]]) -> List[str]:
        """Extract context triggers from interactions"""
        triggers = set()
        
        for interaction in interactions:
            task = interaction.get('task', '').lower()
            
            # Extract key action words
            action_words = ['create', 'build', 'fix', 'debug', 'analyze', 'review', 'optimize', 'deploy']
            for word in action_words:
                if word in task:
                    triggers.add(word)
            
            # Extract domain words
            domain_words = ['ios', 'web', 'frontend', 'backend', 'database', 'api', 'security']
            for word in domain_words:
                if word in task:
                    triggers.add(word)
        
        return list(triggers)
    
    def _validate_patterns(self, patterns: List[WorkflowPattern], workflow_data: List[Dict[str, Any]]) -> List[WorkflowPattern]:
        """Validate and filter patterns based on quality criteria"""
        validated = []
        
        for pattern in patterns:
            # Check minimum success rate
            if pattern.success_rate < self.config["min_success_rate"]:
                continue
            
            # Check minimum usage frequency
            if pattern.usage_frequency < self.config["min_pattern_frequency"]:
                continue
            
            # Check confidence threshold
            if pattern.confidence_score < self.config["confidence_threshold"]:
                continue
            
            validated.append(pattern)
        
        return validated
    
    def _deduplicate_patterns(self, patterns: List[WorkflowPattern]) -> List[WorkflowPattern]:
        """Remove duplicate patterns"""
        unique_patterns = {}
        
        for pattern in patterns:
            # Create a signature based on agent sequence and type
            agent_names = [step.agent_name for step in pattern.agent_sequence]
            signature = f"{pattern.pattern_type.value}_{hash('_'.join(agent_names))}"
            
            if signature not in unique_patterns or pattern.success_rate > unique_patterns[signature].success_rate:
                unique_patterns[signature] = pattern
        
        return list(unique_patterns.values())
    
    def _store_pattern(self, pattern: WorkflowPattern):
        """Store pattern in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO workflow_patterns
                    (pattern_id, pattern_type, name, description, agent_sequence,
                     success_rate, avg_completion_time, context_triggers, outcome_quality,
                     usage_frequency, confidence_score, status, created_at, last_updated, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pattern.pattern_id,
                    pattern.pattern_type.value,
                    pattern.name,
                    pattern.description,
                    json.dumps([step.to_dict() for step in pattern.agent_sequence]),
                    pattern.success_rate,
                    pattern.avg_completion_time,
                    json.dumps(pattern.context_triggers),
                    pattern.outcome_quality,
                    pattern.usage_frequency,
                    pattern.confidence_score,
                    pattern.status.value,
                    pattern.created_at,
                    pattern.last_updated,
                    json.dumps(pattern.tags)
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store pattern {pattern.pattern_id}: {e}")
    
    def get_patterns(self, pattern_type: PatternType = None, status: PatternStatus = None, limit: int = 50) -> List[WorkflowPattern]:
        """Retrieve patterns from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM workflow_patterns"
                params = []
                
                conditions = []
                if pattern_type:
                    conditions.append("pattern_type = ?")
                    params.append(pattern_type.value)
                
                if status:
                    conditions.append("status = ?")
                    params.append(status.value)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY success_rate DESC, confidence_score DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                patterns = []
                for row in rows:
                    pattern_data = {
                        'pattern_id': row[0],
                        'pattern_type': row[1],
                        'name': row[2],
                        'description': row[3],
                        'agent_sequence': json.loads(row[4]),
                        'success_rate': row[5],
                        'avg_completion_time': row[6],
                        'context_triggers': json.loads(row[7]),
                        'outcome_quality': row[8],
                        'usage_frequency': row[9],
                        'confidence_score': row[10],
                        'status': row[11],
                        'created_at': row[12],
                        'last_updated': row[13],
                        'tags': json.loads(row[14]) if row[14] else []
                    }
                    
                    patterns.append(WorkflowPattern.from_dict(pattern_data))
                
                return patterns
                
        except Exception as e:
            logger.error(f"Failed to retrieve patterns: {e}")
            return []
    
    def find_matching_patterns(self, context: str, task_type: str = "", domain: str = "") -> List[PatternRecommendation]:
        """Find patterns matching given context"""
        try:
            # Get all active patterns
            patterns = self.get_patterns(status=PatternStatus.ACTIVE)
            if not patterns:
                patterns = self.get_patterns(status=PatternStatus.VALIDATED)
            
            recommendations = []
            
            for pattern in patterns:
                # Calculate match score
                match_score = self._calculate_pattern_match_score(pattern, context, task_type, domain)
                
                if match_score > 0.3:  # Minimum match threshold
                    recommendation = PatternRecommendation(
                        pattern_id=pattern.pattern_id,
                        confidence_score=match_score,
                        estimated_success_rate=pattern.success_rate,
                        estimated_duration=pattern.avg_completion_time,
                        reasoning=self._generate_recommendation_reasoning(pattern, match_score),
                        alternatives=[],  # Could be populated with similar patterns
                        risk_factors=self._assess_pattern_risks(pattern)
                    )
                    recommendations.append(recommendation)
            
            # Sort by confidence score
            recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
            
            return recommendations[:5]  # Top 5 recommendations
            
        except Exception as e:
            logger.error(f"Failed to find matching patterns: {e}")
            return []
    
    def _calculate_pattern_match_score(self, pattern: WorkflowPattern, context: str, task_type: str, domain: str) -> float:
        """Calculate how well a pattern matches the given context"""
        score = 0.0
        
        # Context trigger matching
        context_lower = context.lower()
        for trigger in pattern.context_triggers:
            if trigger.lower() in context_lower:
                score += 0.2
        
        # Task type matching
        if task_type:
            task_lower = task_type.lower()
            if any(trigger in task_lower for trigger in pattern.context_triggers):
                score += 0.3
        
        # Domain matching
        if domain:
            domain_lower = domain.lower()
            if any(tag == domain_lower for tag in pattern.tags):
                score += 0.2
        
        # Base pattern quality score
        quality_score = (pattern.success_rate + pattern.confidence_score) / 2
        score += quality_score * 0.3
        
        return min(1.0, score)
    
    def _generate_recommendation_reasoning(self, pattern: WorkflowPattern, match_score: float) -> str:
        """Generate reasoning for pattern recommendation"""
        reasons = []
        
        reasons.append(f"Pattern '{pattern.name}' has {pattern.success_rate:.1%} success rate")
        reasons.append(f"Average completion time: {pattern.avg_completion_time:.1f} minutes")
        reasons.append(f"Used {pattern.usage_frequency} times previously")
        
        if match_score > 0.8:
            reasons.append("Strong context match")
        elif match_score > 0.6:
            reasons.append("Good context match")
        else:
            reasons.append("Moderate context match")
        
        return "; ".join(reasons)
    
    def _assess_pattern_risks(self, pattern: WorkflowPattern) -> List[str]:
        """Assess risks associated with pattern"""
        risks = []
        
        if pattern.success_rate < 0.7:
            risks.append("Below average success rate")
        
        if pattern.avg_completion_time > 60:
            risks.append("Long completion time")
        
        if pattern.usage_frequency < 5:
            risks.append("Limited usage history")
        
        if pattern.status == PatternStatus.EXPERIMENTAL:
            risks.append("Experimental pattern")
        
        return risks
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get pattern recognition performance statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Count patterns by type and status
                cursor.execute("SELECT pattern_type, status, COUNT(*) FROM workflow_patterns GROUP BY pattern_type, status")
                pattern_counts = cursor.fetchall()
                
                # Total patterns
                cursor.execute("SELECT COUNT(*) FROM workflow_patterns")
                total_patterns = cursor.fetchone()[0]
                
                # Average success rate
                cursor.execute("SELECT AVG(success_rate) FROM workflow_patterns")
                avg_success_rate = cursor.fetchone()[0] or 0.0
                
                # Pattern executions
                cursor.execute("SELECT COUNT(*) FROM pattern_executions")
                total_executions = cursor.fetchone()[0]
                
                return {
                    "total_patterns": total_patterns,
                    "pattern_breakdown": dict([(f"{row[0]}_{row[1]}", row[2]) for row in pattern_counts]),
                    "average_success_rate": avg_success_rate,
                    "total_executions": total_executions,
                    "components_available": self.components_available,
                    "database_path": str(self.db_path)
                }
                
        except Exception as e:
            logger.error(f"Failed to get performance stats: {e}")
            return {"error": str(e)}

# Convenience functions
def detect_workflow_patterns(lookback_days: int = 30) -> List[WorkflowPattern]:
    """Quick function to detect workflow patterns"""
    engine = PatternRecognitionEngine()
    return engine.detect_patterns(lookback_days)

def find_patterns_for_task(context: str, task_type: str = "", domain: str = "") -> List[PatternRecommendation]:
    """Quick function to find patterns for a specific task"""
    engine = PatternRecognitionEngine()
    return engine.find_matching_patterns(context, task_type, domain)

if __name__ == "__main__":
    # Test the pattern recognition engine
    logging.basicConfig(level=logging.INFO)
    
    print("Pattern Recognition Engine Test")
    print("=" * 50)
    
    engine = PatternRecognitionEngine()
    
    # Test pattern detection
    patterns = engine.detect_patterns(lookback_days=7)
    print(f"✓ Detected {len(patterns)} workflow patterns")
    
    # Test pattern retrieval
    all_patterns = engine.get_patterns()
    print(f"✓ Retrieved {len(all_patterns)} stored patterns")
    
    # Test pattern matching
    recommendations = engine.find_matching_patterns(
        context="Create an iOS app for expense tracking",
        task_type="creation",
        domain="ios"
    )
    print(f"✓ Found {len(recommendations)} pattern recommendations")
    
    # Test performance stats
    stats = engine.get_performance_stats()
    print(f"✓ Performance stats: {stats['total_patterns']} patterns, {stats['total_executions']} executions")
    
    print("\nPattern Recognition Engine ready for integration")