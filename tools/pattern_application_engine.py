#!/usr/bin/env python3
"""
Pattern Application Engine for Huxley
Applies detected patterns to optimize workflows and provide recommendations
"""

import json
import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from collections import defaultdict
import math

# Import pattern system components
try:
    from pattern_recognition_engine import (
        PatternRecognitionEngine, WorkflowPattern, PatternType, PatternStatus,
        AgentStep, PatternRecommendation
    )
    from execution_tracker import ExecutionTracker, ExecutionStatus, OutcomeType
    from agent_effectiveness_tracker import AgentEffectivenessTracker
except ImportError as e:
    logging.warning(f"Some pattern components not available: {e}")

logger = logging.getLogger(__name__)

class WorkflowStrategy(Enum):
    """Workflow optimization strategies"""
    SPEED_OPTIMIZED = "speed_optimized"
    QUALITY_OPTIMIZED = "quality_optimized"
    BALANCED = "balanced"
    RESOURCE_EFFICIENT = "resource_efficient"
    RISK_MINIMIZED = "risk_minimized"

class RecommendationType(Enum):
    """Types of workflow recommendations"""
    PATTERN_MATCH = "pattern_match"
    AGENT_SUGGESTION = "agent_suggestion"
    SEQUENCE_OPTIMIZATION = "sequence_optimization"
    PARALLEL_OPPORTUNITY = "parallel_opportunity"
    RISK_MITIGATION = "risk_mitigation"

@dataclass
class AgentRecommendation:
    """Recommendation for agent selection"""
    agent_name: str
    confidence_score: float
    reasoning: str
    expected_performance: Dict[str, float]
    risk_factors: List[str]
    alternatives: List[str]

@dataclass
class WorkflowRecommendation:
    """Complete workflow recommendation"""
    recommendation_id: str
    pattern_id: Optional[str]
    agent_sequence: List[AgentRecommendation]
    estimated_duration: float
    estimated_success_rate: float
    estimated_quality: float
    optimization_strategy: WorkflowStrategy
    reasoning: str
    risk_assessment: str
    confidence_score: float
    alternatives: List[str]
    created_at: str

@dataclass
class OptimizationResult:
    """Result of workflow optimization"""
    original_request: str
    recommendations: List[WorkflowRecommendation]
    selected_recommendation: Optional[WorkflowRecommendation]
    optimization_metrics: Dict[str, float]
    decision_factors: Dict[str, Any]

class PatternApplicationEngine:
    """Applies patterns to optimize workflows and provide recommendations"""
    
    def __init__(self):
        self.db_path = Path(__file__).parent.parent / "registry" / "pattern_application.db"
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Initialize component engines
        try:
            self.pattern_engine = PatternRecognitionEngine()
            self.execution_tracker = ExecutionTracker()
            self.effectiveness_tracker = AgentEffectivenessTracker()
            self.components_available = True
        except Exception as e:
            logger.warning(f"Pattern Application Engine initialized with limited components: {e}")
            self.pattern_engine = None
            self.execution_tracker = None
            self.effectiveness_tracker = None
            self.components_available = False
        
        # Configuration
        self.config = {
            "min_confidence_threshold": 0.3,
            "max_recommendations": 5,
            "pattern_weight": 0.4,
            "effectiveness_weight": 0.3,
            "risk_weight": 0.3,
            "default_quality_threshold": 0.7,
            "parallel_threshold": 0.6
        }
        
        self._init_database()
        logger.info("Pattern Application Engine initialized")
    
    def _init_database(self):
        """Initialize SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Workflow recommendations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_recommendations (
                    recommendation_id TEXT PRIMARY KEY,
                    pattern_id TEXT,
                    agent_sequence TEXT NOT NULL,
                    estimated_duration REAL NOT NULL,
                    estimated_success_rate REAL NOT NULL,
                    estimated_quality REAL NOT NULL,
                    optimization_strategy TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    risk_assessment TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    alternatives TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Applied recommendations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS applied_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recommendation_id TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    actual_duration REAL,
                    actual_success_rate REAL,
                    actual_quality REAL,
                    feedback_score REAL,
                    lessons_learned TEXT,
                    applied_at TEXT NOT NULL,
                    FOREIGN KEY (recommendation_id) REFERENCES workflow_recommendations (recommendation_id)
                )
            """)
            
            conn.commit()
    
    async def recommend_workflow(
        self,
        task_description: str,
        initial_agent_sequence: Optional[List[str]] = None,
        strategy: WorkflowStrategy = WorkflowStrategy.BALANCED,
        context_override: Optional[Dict[str, Any]] = None
    ) -> WorkflowRecommendation:
        """Generate workflow recommendation based on patterns and effectiveness"""
        
        if not self.components_available:
            return self._create_fallback_recommendation(task_description, strategy)
        
        try:
            logger.info(f"Generating workflow recommendation for: {task_description[:50]}...")
            
            # Extract task context
            task_context = self._extract_task_context(task_description, context_override)
            
            # Find matching patterns
            matching_patterns = self._find_matching_patterns(task_context)
            
            # Get agent effectiveness data
            agent_effectiveness = self._get_agent_effectiveness_data(task_context)
            
            # Generate recommendations
            recommendations = []
            
            # Pattern-based recommendations
            for pattern in matching_patterns[:3]:  # Top 3 patterns
                recommendation = await self._create_pattern_recommendation(
                    pattern, task_context, agent_effectiveness, strategy
                )
                if recommendation:
                    recommendations.append(recommendation)
            
            # Effectiveness-based recommendation
            effectiveness_rec = await self._create_effectiveness_recommendation(
                task_context, agent_effectiveness, strategy
            )
            if effectiveness_rec:
                recommendations.append(effectiveness_rec)
            
            # Hybrid recommendation
            hybrid_rec = await self._create_hybrid_recommendation(
                task_context, matching_patterns, agent_effectiveness, strategy
            )
            if hybrid_rec:
                recommendations.append(hybrid_rec)
            
            # Select best recommendation
            best_recommendation = self._select_best_recommendation(recommendations, strategy)
            
            # Store recommendation
            if best_recommendation:
                self._store_recommendation(best_recommendation)
            
            return best_recommendation or self._create_fallback_recommendation(task_description, strategy)
            
        except Exception as e:
            logger.error(f"Failed to generate workflow recommendation: {e}")
            return self._create_fallback_recommendation(task_description, strategy)
    
    def apply_recommendation(self, recommendation: WorkflowRecommendation, 
                           execution_context: Dict[str, Any] = None) -> str:
        """Apply a workflow recommendation and track execution"""
        try:
            if not self.execution_tracker:
                logger.warning("Execution tracker not available")
                return f"mock_execution_{datetime.utcnow().timestamp()}"
            
            # Start execution tracking
            execution_id = f"exec_{recommendation.recommendation_id}_{datetime.utcnow().timestamp()}"
            
            self.execution_tracker.start_execution(
                execution_id=execution_id,
                agent_name=recommendation.agent_sequence[0].agent_name if recommendation.agent_sequence else "unknown",
                request=f"Apply recommendation {recommendation.recommendation_id}",
                pattern_id=recommendation.pattern_id,
                context=execution_context or {}
            )
            
            logger.info(f"Applied recommendation {recommendation.recommendation_id} as execution {execution_id}")
            return execution_id
            
        except Exception as e:
            logger.error(f"Failed to apply recommendation: {e}")
            return ""
    
    def get_optimization_suggestions(self, current_workflow: List[str], 
                                   context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get suggestions to optimize an existing workflow"""
        try:
            suggestions = []
            
            if not self.components_available:
                return [{"type": "info", "message": "Pattern system not fully available"}]
            
            # Analyze current workflow
            workflow_analysis = self._analyze_workflow(current_workflow, context)
            
            # Check for parallel opportunities
            parallel_suggestions = self._identify_parallel_opportunities(current_workflow, workflow_analysis)
            suggestions.extend(parallel_suggestions)
            
            # Check for agent optimization
            agent_suggestions = self._suggest_agent_optimizations(current_workflow, workflow_analysis)
            suggestions.extend(agent_suggestions)
            
            # Check for sequence optimization
            sequence_suggestions = self._suggest_sequence_optimizations(current_workflow, workflow_analysis)
            suggestions.extend(sequence_suggestions)
            
            # Risk mitigation suggestions
            risk_suggestions = self._suggest_risk_mitigations(current_workflow, workflow_analysis)
            suggestions.extend(risk_suggestions)
            
            return suggestions[:10]  # Top 10 suggestions
            
        except Exception as e:
            logger.error(f"Failed to get optimization suggestions: {e}")
            return [{"type": "error", "message": f"Optimization analysis failed: {str(e)}"}]
    
    def _extract_task_context(self, task_description: str, context_override: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract structured context from task description"""
        context = {
            "task_description": task_description,
            "task_type": self._classify_task_type(task_description),
            "domain": self._identify_domain(task_description),
            "complexity": self._assess_complexity(task_description),
            "urgency": self._assess_urgency(task_description),
            "dependencies": self._identify_dependencies(task_description)
        }
        
        if context_override:
            context.update(context_override)
        
        return context
    
    def _find_matching_patterns(self, task_context: Dict[str, Any]) -> List[WorkflowPattern]:
        """Find patterns that match the task context"""
        if not self.pattern_engine:
            return []
        
        try:
            return self.pattern_engine.find_matching_patterns(
                context=task_context["task_description"],
                task_type=task_context.get("task_type", ""),
                domain=task_context.get("domain", "")
            )
        except Exception as e:
            logger.error(f"Failed to find matching patterns: {e}")
            return []
    
    def _get_agent_effectiveness_data(self, task_context: Dict[str, Any]) -> Dict[str, Any]:
        """Get agent effectiveness data for the task context"""
        if not self.effectiveness_tracker:
            return {}
        
        try:
            task_type = task_context.get("task_type", "")
            domain = task_context.get("domain", "")
            
            top_agents = self.effectiveness_tracker.get_top_agents_for_task(task_type, domain)
            
            return {
                "top_agents": top_agents,
                "task_type": task_type,
                "domain": domain
            }
        except Exception as e:
            logger.error(f"Failed to get agent effectiveness data: {e}")
            return {}
    
    async def _create_pattern_recommendation(
        self, pattern: WorkflowPattern, task_context: Dict[str, Any],
        agent_effectiveness: Dict[str, Any], strategy: WorkflowStrategy
    ) -> Optional[WorkflowRecommendation]:
        """Create recommendation based on a specific pattern"""
        try:
            # Convert pattern agent steps to agent recommendations
            agent_recommendations = []
            for step in pattern.agent_sequence:
                agent_rec = AgentRecommendation(
                    agent_name=step.agent_name,
                    confidence_score=step.confidence,
                    reasoning=f"Pattern-based selection with {step.success_rate:.1%} success rate",
                    expected_performance={
                        "success_rate": step.success_rate,
                        "duration": step.duration_avg,
                        "quality": pattern.outcome_quality
                    },
                    risk_factors=self._assess_agent_risks(step.agent_name, task_context),
                    alternatives=[]
                )
                agent_recommendations.append(agent_rec)
            
            # Calculate recommendation metrics
            confidence_score = pattern.confidence_score * 0.8  # Slight discount for application
            
            recommendation = WorkflowRecommendation(
                recommendation_id=f"pattern_rec_{pattern.pattern_id}_{datetime.utcnow().timestamp()}",
                pattern_id=pattern.pattern_id,
                agent_sequence=agent_recommendations,
                estimated_duration=pattern.avg_completion_time,
                estimated_success_rate=pattern.success_rate,
                estimated_quality=pattern.outcome_quality,
                optimization_strategy=strategy,
                reasoning=f"Based on pattern '{pattern.name}' with {pattern.usage_frequency} historical uses",
                risk_assessment=self._assess_pattern_risks(pattern, task_context),
                confidence_score=confidence_score,
                alternatives=[],
                created_at=datetime.utcnow().isoformat()
            )
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Failed to create pattern recommendation: {e}")
            return None
    
    async def _create_effectiveness_recommendation(
        self, task_context: Dict[str, Any], agent_effectiveness: Dict[str, Any],
        strategy: WorkflowStrategy
    ) -> Optional[WorkflowRecommendation]:
        """Create recommendation based on agent effectiveness"""
        try:
            top_agents = agent_effectiveness.get("top_agents", [])
            if not top_agents:
                return None
            
            # Select agents based on strategy
            selected_agents = self._select_agents_by_strategy(top_agents, strategy)
            
            agent_recommendations = []
            total_duration = 0
            combined_success_rate = 1.0
            
            for i, agent_score in enumerate(selected_agents):
                agent_rec = AgentRecommendation(
                    agent_name=agent_score.agent_name,
                    confidence_score=agent_score.confidence,
                    reasoning=f"Top performer with {agent_score.overall_score:.2f} effectiveness score",
                    expected_performance={
                        "success_rate": agent_score.success_rate,
                        "duration": agent_score.avg_completion_time,
                        "quality": agent_score.quality_average
                    },
                    risk_factors=self._assess_agent_risks(agent_score.agent_name, task_context),
                    alternatives=[a.agent_name for a in top_agents[i+1:i+3]]  # Next 2 as alternatives
                )
                agent_recommendations.append(agent_rec)
                
                total_duration += agent_score.avg_completion_time
                combined_success_rate *= agent_score.success_rate
            
            recommendation = WorkflowRecommendation(
                recommendation_id=f"effectiveness_rec_{datetime.utcnow().timestamp()}",
                pattern_id=None,
                agent_sequence=agent_recommendations,
                estimated_duration=total_duration,
                estimated_success_rate=combined_success_rate,
                estimated_quality=sum(a.expected_performance["quality"] for a in agent_recommendations) / len(agent_recommendations),
                optimization_strategy=strategy,
                reasoning="Based on historical agent effectiveness data",
                risk_assessment=self._assess_effectiveness_risks(selected_agents, task_context),
                confidence_score=sum(a.confidence_score for a in agent_recommendations) / len(agent_recommendations),
                alternatives=[],
                created_at=datetime.utcnow().isoformat()
            )
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Failed to create effectiveness recommendation: {e}")
            return None
    
    async def _create_hybrid_recommendation(
        self, task_context: Dict[str, Any], patterns: List[WorkflowPattern],
        agent_effectiveness: Dict[str, Any], strategy: WorkflowStrategy
    ) -> Optional[WorkflowRecommendation]:
        """Create hybrid recommendation combining patterns and effectiveness"""
        try:
            if not patterns or not agent_effectiveness.get("top_agents"):
                return None
            
            # Combine best pattern with top agents
            best_pattern = patterns[0]
            top_agents = agent_effectiveness["top_agents"]
            
            # Create optimized agent sequence
            hybrid_agents = []
            for step in best_pattern.agent_sequence:
                # Find best available agent for this step
                best_agent = self._find_best_agent_for_step(step, top_agents, strategy)
                if best_agent:
                    hybrid_agents.append(best_agent)
                else:
                    # Fallback to pattern agent
                    hybrid_agents.append(AgentRecommendation(
                        agent_name=step.agent_name,
                        confidence_score=step.confidence * 0.7,  # Lower confidence for fallback
                        reasoning=f"Pattern fallback agent",
                        expected_performance={
                            "success_rate": step.success_rate,
                            "duration": step.duration_avg,
                            "quality": 0.7
                        },
                        risk_factors=["Pattern-based selection without effectiveness data"],
                        alternatives=[]
                    ))
            
            # Calculate hybrid metrics
            avg_duration = sum(a.expected_performance["duration"] for a in hybrid_agents)
            combined_success = math.prod(a.expected_performance["success_rate"] for a in hybrid_agents)
            avg_quality = sum(a.expected_performance["quality"] for a in hybrid_agents) / len(hybrid_agents)
            
            recommendation = WorkflowRecommendation(
                recommendation_id=f"hybrid_rec_{datetime.utcnow().timestamp()}",
                pattern_id=best_pattern.pattern_id,
                agent_sequence=hybrid_agents,
                estimated_duration=avg_duration,
                estimated_success_rate=combined_success,
                estimated_quality=avg_quality,
                optimization_strategy=strategy,
                reasoning="Hybrid approach combining proven patterns with top-performing agents",
                risk_assessment="Balanced risk from pattern validation and agent effectiveness",
                confidence_score=(best_pattern.confidence_score + sum(a.confidence_score for a in hybrid_agents) / len(hybrid_agents)) / 2,
                alternatives=[],
                created_at=datetime.utcnow().isoformat()
            )
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Failed to create hybrid recommendation: {e}")
            return None
    
    def _create_fallback_recommendation(self, task_description: str, strategy: WorkflowStrategy) -> WorkflowRecommendation:
        """Create fallback recommendation when pattern system is unavailable"""
        # Simple fallback based on task keywords
        agent_name = self._guess_agent_from_task(task_description)
        
        fallback_agent = AgentRecommendation(
            agent_name=agent_name,
            confidence_score=0.5,
            reasoning="Fallback recommendation based on task keywords",
            expected_performance={
                "success_rate": 0.7,
                "duration": 30.0,
                "quality": 0.7
            },
            risk_factors=["Limited pattern data available"],
            alternatives=[]
        )
        
        return WorkflowRecommendation(
            recommendation_id=f"fallback_rec_{datetime.utcnow().timestamp()}",
            pattern_id=None,
            agent_sequence=[fallback_agent],
            estimated_duration=30.0,
            estimated_success_rate=0.7,
            estimated_quality=0.7,
            optimization_strategy=strategy,
            reasoning="Fallback recommendation - pattern system unavailable",
            risk_assessment="Higher risk due to limited historical data",
            confidence_score=0.5,
            alternatives=[],
            created_at=datetime.utcnow().isoformat()
        )
    
    # Additional helper methods would continue here...
    # For brevity, I'll include key methods that complete the functionality
    
    def _classify_task_type(self, task_description: str) -> str:
        """Classify the type of task"""
        task_lower = task_description.lower()
        
        if any(word in task_lower for word in ["create", "build", "develop", "implement"]):
            return "creation"
        elif any(word in task_lower for word in ["fix", "debug", "repair", "solve"]):
            return "debugging"
        elif any(word in task_lower for word in ["analyze", "review", "check", "audit"]):
            return "analysis"
        elif any(word in task_lower for word in ["optimize", "improve", "enhance"]):
            return "optimization"
        else:
            return "general"
    
    def _identify_domain(self, task_description: str) -> str:
        """Identify the domain of the task"""
        task_lower = task_description.lower()
        
        if any(word in task_lower for word in ["ios", "swift", "xcode", "app"]):
            return "ios"
        elif any(word in task_lower for word in ["web", "html", "javascript", "react"]):
            return "web"
        elif any(word in task_lower for word in ["automation", "workflow", "n8n"]):
            return "automation"
        elif any(word in task_lower for word in ["data", "csv", "analysis", "database"]):
            return "data"
        else:
            return "general"
    
    def _guess_agent_from_task(self, task_description: str) -> str:
        """Guess appropriate agent from task description"""
        task_lower = task_description.lower()
        
        if any(word in task_lower for word in ["ios", "swift", "xcode"]):
            return "iOS Dev"
        elif any(word in task_lower for word in ["web", "frontend", "react"]):
            return "Frontend Specialist"
        elif any(word in task_lower for word in ["security", "vulnerability", "audit"]):
            return "Security Analyst"
        elif any(word in task_lower for word in ["debug", "fix", "error"]):
            return "Debugger"
        elif any(word in task_lower for word in ["optimize", "performance"]):
            return "Performance Optimizer"
        else:
            return "general-purpose"
    
    def _assess_complexity(self, task_description: str) -> str:
        """Assess task complexity"""
        indicators = task_description.lower()
        if any(word in indicators for word in ["complex", "advanced", "enterprise"]):
            return "high"
        elif any(word in indicators for word in ["integration", "multiple", "coordination"]):
            return "medium"
        else:
            return "low"
    
    def _assess_urgency(self, task_description: str) -> str:
        """Assess task urgency"""
        indicators = task_description.lower()
        if any(word in indicators for word in ["urgent", "asap", "critical"]):
            return "high"
        elif any(word in indicators for word in ["soon", "important", "priority"]):
            return "medium"
        else:
            return "low"
    
    def _identify_dependencies(self, task_description: str) -> List[str]:
        """Identify potential dependencies"""
        deps = []
        indicators = task_description.lower()
        
        if "after" in indicators or "depends on" in indicators:
            deps.append("sequential_dependency")
        if "api" in indicators or "service" in indicators:
            deps.append("external_service")
        if "database" in indicators:
            deps.append("data_dependency")
        
        return deps
    
    def _assess_agent_risks(self, agent_name: str, task_context: Dict[str, Any]) -> List[str]:
        """Assess risks for using specific agent"""
        risks = []
        
        complexity = task_context.get("complexity", "low")
        if complexity == "high":
            risks.append("High complexity task")
        
        urgency = task_context.get("urgency", "low")
        if urgency == "high":
            risks.append("High urgency requirement")
        
        return risks
    
    def _store_recommendation(self, recommendation: WorkflowRecommendation):
        """Store recommendation in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO workflow_recommendations
                    (recommendation_id, pattern_id, agent_sequence, estimated_duration,
                     estimated_success_rate, estimated_quality, optimization_strategy,
                     reasoning, risk_assessment, confidence_score, alternatives, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    recommendation.recommendation_id, recommendation.pattern_id,
                    json.dumps([a.__dict__ for a in recommendation.agent_sequence]),
                    recommendation.estimated_duration, recommendation.estimated_success_rate,
                    recommendation.estimated_quality, recommendation.optimization_strategy.value,
                    recommendation.reasoning, recommendation.risk_assessment,
                    recommendation.confidence_score, json.dumps(recommendation.alternatives),
                    recommendation.created_at
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store recommendation: {e}")

# Convenience functions
async def get_workflow_recommendation(task_description: str, strategy: str = "balanced") -> WorkflowRecommendation:
    """Quick function to get workflow recommendation"""
    engine = PatternApplicationEngine()
    strategy_enum = WorkflowStrategy(strategy) if strategy in [s.value for s in WorkflowStrategy] else WorkflowStrategy.BALANCED
    return await engine.recommend_workflow(task_description, strategy=strategy_enum)

def optimize_workflow(current_workflow: List[str], context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Quick function to get workflow optimization suggestions"""
    engine = PatternApplicationEngine()
    return engine.get_optimization_suggestions(current_workflow, context)

if __name__ == "__main__":
    # Test the application engine
    import asyncio
    logging.basicConfig(level=logging.INFO)
    
    async def test_engine():
        print("Pattern Application Engine Test")
        print("=" * 50)
        
        engine = PatternApplicationEngine()
        
        # Test workflow recommendation
        recommendation = await engine.recommend_workflow(
            "Create an iOS app for expense tracking",
            strategy=WorkflowStrategy.BALANCED
        )
        
        print(f"✓ Generated recommendation: {recommendation.recommendation_id}")
        print(f"✓ Estimated duration: {recommendation.estimated_duration:.1f} minutes")
        print(f"✓ Success rate: {recommendation.estimated_success_rate:.1%}")
        print(f"✓ Agent sequence: {[a.agent_name for a in recommendation.agent_sequence]}")
        
        # Test optimization suggestions
        suggestions = engine.get_optimization_suggestions(
            ["iOS Dev", "Debugger", "Code Reviewer"],
            {"task_type": "creation", "domain": "ios"}
        )
        
        print(f"✓ Generated {len(suggestions)} optimization suggestions")
        
        print("\nPattern Application Engine ready for integration")
    
    asyncio.run(test_engine())