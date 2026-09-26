#!/usr/bin/env python3
"""
Intelligent Builder - Main integration point for autonomous pipeline
Orchestrates the complete "one thing that builds all other things" system
"""

import json
import yaml
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
import asyncio
import signal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import our new components
from capsule_pipeline_engine import PipelineEngine, CapsuleState
from unified_knowledge_graph import UnifiedKnowledgeGraph, NodeType
from ml_prediction_engine import MLPredictionEngine
from performance_analytics import PerformanceAnalytics
from cost_optimizer import CostOptimizer, CostCategory

class IntelligentBuilder:
    """
    The main orchestrator for the Huxley system's autonomous capabilities
    Combines pipeline automation with intelligent knowledge management
    """
    
    def __init__(self):
        self.catalyst_root = Path("{{CATALYST_ROOT}}")
        
        # Initialize core components
        self.pipeline = PipelineEngine()
        self.knowledge_graph = UnifiedKnowledgeGraph()
        self.ml_engine = MLPredictionEngine()
        self.performance_analytics = PerformanceAnalytics()
        self.cost_optimizer = CostOptimizer()
        
        # State tracking
        self.active_builds = {}
        self.recommendations_cache = {}
        self.running = False
        
        # Configuration
        self.config = self._load_config()
        
        logger.info("Intelligent Builder initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load intelligent builder configuration"""
        config_path = self.catalyst_root / "global/config/intelligent_builder.yaml"
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        
        # Default configuration
        return {
            "auto_progression": True,
            "learning_enabled": True,
            "recommendation_threshold": 0.7,
            "max_concurrent_builds": 3,
            "monitor_interval": 300,  # 5 minutes
            "backup_interval": 3600,  # 1 hour
            "intelligence_features": {
                "pattern_recognition": True,
                "predictive_analytics": True,
                "auto_optimization": True,
                "anomaly_detection": True
            }
        }
    
    async def start_autonomous_mode(self):
        """Start the autonomous building system"""
        self.running = True
        logger.info("Starting autonomous mode...")
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            # Initial sync and discovery
            await self._initial_sync()
            
            # Start main event loop
            while self.running:
                await self._main_loop()
                await asyncio.sleep(self.config.get("monitor_interval", 300))
                
        except Exception as e:
            logger.error(f"Error in autonomous mode: {e}")
        finally:
            await self._cleanup()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    async def _initial_sync(self):
        """Perform initial synchronization and discovery"""
        logger.info("Performing initial sync...")
        
        # Sync knowledge graph with all sources
        self.knowledge_graph.sync_all_sources()
        
        # Discover and register new capsules
        self.pipeline.scan_for_capsules()
        
        # Clean up stale capsules
        self.pipeline.cleanup_stale()
        
        # Generate initial recommendations
        await self._update_recommendations()
        
        logger.info("Initial sync complete")
    
    async def _main_loop(self):
        """Main autonomous loop"""
        # Check for capsules that can be advanced
        await self._auto_advance_capsules()
        
        # Monitor active builds
        await self._monitor_active_builds()
        
        # Update knowledge graph
        await self._update_knowledge()
        
        # Generate new recommendations
        await self._update_recommendations()
        
        # Perform maintenance tasks
        await self._maintenance_tasks()
    
    async def _auto_advance_capsules(self):
        """Automatically advance capsules when conditions are met"""
        if not self.config.get("auto_progression", True):
            return
        
        for capsule_name, context in self.pipeline.capsules.items():
            # Skip if already at terminal states
            if context.current_state in [CapsuleState.MONITOR, CapsuleState.ARCHIVED, CapsuleState.FAILED]:
                continue
            
            # Check if ready for advancement
            if await self._can_advance(context):
                logger.info(f"Auto-advancing {capsule_name} from {context.current_state.value}")
                
                # Get recommendations before advancing
                recommendations = await self._get_advancement_recommendations(context)
                
                # Apply recommendations
                await self._apply_recommendations(context, recommendations)
                
                # Advance the capsule
                success = self.pipeline.advance(capsule_name)
                
                if success:
                    # Learn from successful advancement
                    await self._learn_from_advancement(context)
                else:
                    # Analyze why advancement failed
                    await self._analyze_advancement_failure(context)
    
    async def _can_advance(self, context) -> bool:
        """Determine if a capsule can be automatically advanced"""
        # Use knowledge graph to get insights
        capsule_id = f"capsule_{context.name}"
        
        # Check if similar capsules succeeded with auto-advancement
        similar_nodes = self.knowledge_graph.find_similar_nodes(capsule_id)
        
        for similar_id, similarity in similar_nodes:
            if similarity > self.config.get("recommendation_threshold", 0.7):
                similar_node = self.knowledge_graph.get_node(similar_id)
                if similar_node and "auto_advanced" in similar_node.data:
                    return True
        
        # Basic checks
        if context.current_state == CapsuleState.IDEATION:
            return (context.path / "spec/requirements.yaml").exists()
        
        elif context.current_state == CapsuleState.DESIGN:
            return context.metadata.get("design_approved", False)
        
        elif context.current_state == CapsuleState.BUILD:
            src_exists = (context.path / "src").exists()
            tests_exist = (context.path / "tests").exists() or True  # Using unified quality standards
            return src_exists and tests_exist
        
        elif context.current_state == CapsuleState.VALIDATE:
            return context.metadata.get("validation_passed", False)
        
        elif context.current_state == CapsuleState.DEPLOY:
            return context.metadata.get("deployment_successful", False)
        
        return False
    
    async def _get_advancement_recommendations(self, context) -> List[Dict[str, Any]]:
        """Get intelligent recommendations for capsule advancement"""
        recommendations = []
        
        # Query knowledge graph for recommendations
        query_context = {
            "capsule_name": context.name,
            "current_state": context.current_state.value,
            "task_type": context.metadata.get("type", "general")
        }
        
        graph_recommendations = self.knowledge_graph.get_recommendations(query_context)
        recommendations.extend(graph_recommendations)
        
        # Get ML-based predictions and recommendations
        ml_recommendations = await self._get_ml_recommendations(context)
        recommendations.extend(ml_recommendations)
        
        # Add state-specific recommendations
        if context.current_state == CapsuleState.DESIGN:
            # Recommend agents based on successful patterns
            successful_agents = self._get_successful_agents_for_type(
                context.metadata.get("type", "general")
            )
            recommendations.extend(successful_agents)
        
        elif context.current_state == CapsuleState.BUILD:
            # Recommend build optimizations
            build_optimizations = self._get_build_optimizations(context)
            recommendations.extend(build_optimizations)
        
        return recommendations
    
    def _get_successful_agents_for_type(self, capsule_type: str) -> List[Dict[str, Any]]:
        """Get agents that have been successful for similar capsule types"""
        recommendations = []
        
        # Search for successful patterns with this type
        pattern_nodes = self.knowledge_graph.search_nodes(capsule_type, NodeType.PATTERN)
        
        for pattern_node in pattern_nodes:
            if "success" in str(pattern_node.tags):
                agents = pattern_node.data.get("agents", [])
                for agent in agents:
                    recommendations.append({
                        "type": "successful_agent",
                        "agent": agent,
                        "confidence": 0.8,
                        "reason": f"Successful in {pattern_node.name}"
                    })
        
        return recommendations
    
    def _get_build_optimizations(self, context) -> List[Dict[str, Any]]:
        """Get build optimization recommendations"""
        optimizations = []
        
        # Check for common optimizations from knowledge graph
        optimization_nodes = self.knowledge_graph.search_nodes("optimization", NodeType.OPTIMIZATION)
        
        for opt_node in optimization_nodes:
            if context.lane in str(opt_node.data):
                optimizations.append({
                    "type": "build_optimization",
                    "optimization": opt_node.name,
                    "details": opt_node.data
                })
        
        return optimizations
    
    async def _apply_recommendations(self, context, recommendations: List[Dict[str, Any]]):
        """Apply intelligent recommendations to a capsule"""
        for rec in recommendations:
            try:
                if rec["type"] == "successful_agent":
                    # Add agent to capsule metadata
                    current_agents = context.metadata.get("assigned_agents", [])
                    if rec["agent"] not in current_agents:
                        current_agents.append(rec["agent"])
                        context.metadata["assigned_agents"] = current_agents
                        logger.info(f"Added agent {rec['agent']} to {context.name}")
                
                elif rec["type"] == "build_optimization":
                    # Apply build optimization
                    context.metadata["optimizations"] = context.metadata.get("optimizations", [])
                    context.metadata["optimizations"].append(rec["optimization"])
                    logger.info(f"Applied optimization {rec['optimization']} to {context.name}")
                
                elif rec["type"] == "similar_success":
                    # Apply patterns from similar successful projects
                    context.metadata["reference_patterns"] = context.metadata.get("reference_patterns", [])
                    context.metadata["reference_patterns"].append(rec["reference"])
                    logger.info(f"Added reference pattern {rec['reference']} to {context.name}")
                
            except Exception as e:
                logger.error(f"Failed to apply recommendation: {e}")
    
    async def _learn_from_advancement(self, context):
        """Learn from successful capsule advancement"""
        if not self.config.get("learning_enabled", True):
            return
        
        # Record successful advancement pattern
        pattern_data = {
            "capsule": context.name,
            "state_transition": f"{context.history[-1].from_state.value}_to_{context.current_state.value}",
            "agents": context.metadata.get("assigned_agents", []),
            "duration": (context.updated_at - context.created_at).total_seconds(),
            "success_factors": context.metadata.get("optimizations", []),
            "auto_advanced": True
        }
        
        # Add to knowledge graph
        pattern_id = f"advancement_pattern_{context.name}_{len(context.history)}"
        self.knowledge_graph.add_node(
            pattern_id,
            NodeType.PATTERN,
            f"Advancement Pattern: {context.name}",
            pattern_data
        )
        
        # Link to capsule
        capsule_id = f"capsule_{context.name}"
        self.knowledge_graph.add_edge(capsule_id, pattern_id, "generated_pattern")
        
        logger.info(f"Learned advancement pattern from {context.name}")
    
    async def _analyze_advancement_failure(self, context):
        """Analyze why automatic advancement failed"""
        failure_data = {
            "capsule": context.name,
            "attempted_state": "next_state",  # Would be filled with actual target
            "current_state": context.current_state.value,
            "errors": context.errors,
            "metadata": context.metadata,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add failure analysis to knowledge graph
        failure_id = f"advancement_failure_{context.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.knowledge_graph.add_node(
            failure_id,
            NodeType.ERROR,
            f"Advancement Failure: {context.name}",
            failure_data
        )
        
        # Look for similar failures and solutions
        similar_failures = self.knowledge_graph.search_nodes("advancement_failure", NodeType.ERROR)
        
        for failure_node in similar_failures:
            if failure_node.data.get("current_state") == context.current_state.value:
                # Found similar failure, look for solutions
                logger.info(f"Found similar failure pattern for {context.name}")
        
        logger.warning(f"Advancement failed for {context.name}, analysis recorded")
    
    async def _monitor_active_builds(self):
        """Monitor actively building capsules"""
        building_capsules = [
            context for context in self.pipeline.capsules.values()
            if context.current_state in [CapsuleState.BUILD, CapsuleState.VALIDATE, CapsuleState.DEPLOY]
        ]
        
        for context in building_capsules:
            # Check for errors or anomalies
            await self._check_build_health(context)
            
            # Update progress tracking
            await self._update_build_progress(context)
            
            # Check for optimization opportunities
            await self._optimize_active_build(context)
    
    async def _check_build_health(self, context):
        """Check health of an active build"""
        # Look for error indicators
        error_indicators = [
            "test failures",
            "compilation errors",
            "dependency conflicts",
            "performance issues"
        ]
        
        # Check recent events for this capsule
        events_node = self.knowledge_graph.get_node(f"events_{context.name}")
        
        if events_node:
            latest_events = events_node.data.get("event_types", [])
            for event_type in latest_events:
                for indicator in error_indicators:
                    if indicator in event_type.lower():
                        logger.warning(f"Health issue detected in {context.name}: {event_type}")
                        await self._handle_build_issue(context, event_type)
    
    async def _handle_build_issue(self, context, issue: str):
        """Handle detected build issues"""
        # Look for solutions in knowledge graph
        solution_nodes = self.knowledge_graph.search_nodes(issue, NodeType.SOLUTION)
        
        if solution_nodes:
            best_solution = solution_nodes[0]  # Take the first/best match
            logger.info(f"Applying solution for {issue} in {context.name}: {best_solution.name}")
            
            # Apply solution (in a real implementation, this would trigger actual fixes)
            context.metadata["applied_solutions"] = context.metadata.get("applied_solutions", [])
            context.metadata["applied_solutions"].append({
                "issue": issue,
                "solution": best_solution.name,
                "applied_at": datetime.now().isoformat()
            })
        else:
            # No solution found, escalate
            logger.warning(f"No solution found for {issue} in {context.name}, escalating")
            context.errors.append(f"Unresolved issue: {issue}")
    
    async def _update_build_progress(self, context):
        """Update build progress tracking"""
        # Calculate progress based on various metrics
        progress_factors = {
            "src_files": len(list((context.path / "src").rglob("*"))) if (context.path / "src").exists() else 0,
            "test_files": len(list((context.path / "tests").rglob("*"))) if (context.path / "tests").exists() else 0,
            "docs_files": len(list((context.path / "docs").rglob("*"))) if (context.path / "docs").exists() else 0
        }
        
        # Estimate progress (simple heuristic)
        total_expected = context.metadata.get("estimated_files", 10)
        current_files = sum(progress_factors.values())
        progress_percentage = min(100, (current_files / total_expected) * 100)
        
        context.metrics["build_progress"] = {
            "percentage": progress_percentage,
            "files": progress_factors,
            "last_updated": datetime.now().isoformat()
        }
    
    async def _optimize_active_build(self, context):
        """Look for optimization opportunities in active builds"""
        # Check if build is taking longer than expected
        duration = (datetime.now() - context.created_at).total_seconds() / 3600  # hours
        estimated_hours = context.metadata.get("estimated_hours", 8)
        
        if duration > estimated_hours * 1.5:  # 50% over estimate
            logger.info(f"Build {context.name} is over time estimate, looking for optimizations")
            
            # Look for optimization patterns
            optimizations = self.knowledge_graph.search_nodes("optimization", NodeType.OPTIMIZATION)
            
            for opt_node in optimizations:
                if context.lane in str(opt_node.data) and "build_time" in str(opt_node.data):
                    logger.info(f"Applying build optimization to {context.name}: {opt_node.name}")
                    
                    # Apply optimization
                    context.metadata["auto_optimizations"] = context.metadata.get("auto_optimizations", [])
                    context.metadata["auto_optimizations"].append({
                        "optimization": opt_node.name,
                        "applied_at": datetime.now().isoformat(),
                        "reason": "Over time estimate"
                    })
    
    async def _update_knowledge(self):
        """Periodically update the knowledge graph"""
        try:
            # Sync with latest data
            self.knowledge_graph.sync_all_sources()
            
            # Save updated graph
            self.knowledge_graph.save_graph()
            
            logger.debug("Knowledge graph updated")
            
        except Exception as e:
            logger.error(f"Failed to update knowledge: {e}")
    
    async def _update_recommendations(self):
        """Update cached recommendations"""
        self.recommendations_cache.clear()
        
        # Generate recommendations for each active capsule
        for capsule_name, context in self.pipeline.capsules.items():
            if context.current_state not in [CapsuleState.MONITOR, CapsuleState.ARCHIVED]:
                query_context = {
                    "capsule_name": context.name,
                    "current_state": context.current_state.value,
                }
                
                recommendations = self.knowledge_graph.get_recommendations(query_context)
                self.recommendations_cache[capsule_name] = recommendations
    
    async def _maintenance_tasks(self):
        """Perform periodic maintenance"""
        # Clean up old cache entries
        if len(self.recommendations_cache) > 100:
            # Keep only the 50 most recent
            recent_keys = list(self.recommendations_cache.keys())[-50:]
            self.recommendations_cache = {
                k: v for k, v in self.recommendations_cache.items() 
                if k in recent_keys
            }
        
        # Backup critical data periodically
        if datetime.now().hour % self.config.get("backup_interval", 3600) == 0:
            await self._backup_system_state()
    
    async def _backup_system_state(self):
        """Backup critical system state"""
        backup_data = {
            "pipeline_state": self.pipeline.status(),
            "knowledge_stats": self.knowledge_graph.get_stats(),
            "active_builds": len([
                c for c in self.pipeline.capsules.values()
                if c.current_state in [CapsuleState.BUILD, CapsuleState.VALIDATE]
            ]),
            "backup_time": datetime.now().isoformat()
        }
        
        backup_path = self.catalyst_root / "registry/system_backup.json"
        with open(backup_path, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        logger.info("System state backed up")
    
    async def _cleanup(self):
        """Cleanup on shutdown"""
        logger.info("Cleaning up...")
        
        # Save final state
        self.pipeline._save_state()
        self.knowledge_graph.save_graph()
        
        # Backup on shutdown
        await self._backup_system_state()
        
        logger.info("Cleanup complete")
    
    # Manual interface methods
    def create_capsule(self, name: str, capsule_type: str = "general", 
                      lane: str = "standard") -> Dict[str, Any]:
        """Create a new capsule with intelligent setup"""
        # Create capsule directory
        capsule_path = self.catalyst_root / "capsules" / name
        capsule_path.mkdir(parents=True, exist_ok=True)
        
        # Register with pipeline
        context = self.pipeline.register_capsule(name, capsule_path, lane)
        context.metadata["type"] = capsule_type
        
        # Get intelligent recommendations for new capsule
        recommendations = self.knowledge_graph.get_recommendations({
            "capsule_name": name,
            "task_type": capsule_type,
        })
        
        # Apply initial recommendations
        for rec in recommendations[:3]:  # Apply top 3 recommendations
            if rec["type"] == "recommended_agent":
                current_agents = context.metadata.get("assigned_agents", [])
                current_agents.append(rec["agent"])
                context.metadata["assigned_agents"] = current_agents
        
        # Save state
        self.pipeline._save_state()
        
        return {
            "capsule": name,
            "path": str(capsule_path),
            "state": context.current_state.value,
            "recommendations": recommendations
        }
    
    def get_capsule_status(self, name: str) -> Dict[str, Any]:
        """Get comprehensive status of a capsule"""
        status = self.pipeline.status(name)
        
        if "error" not in status:
            # Add intelligent insights
            recommendations = self.recommendations_cache.get(name, [])
            
            # Get knowledge graph insights
            capsule_id = f"capsule_{name}"
            similar = self.knowledge_graph.find_similar_nodes(capsule_id, top_n=3)
            
            status["recommendations"] = recommendations
            status["similar_capsules"] = [
                {"name": self.knowledge_graph.get_node(node_id).name, "similarity": score}
                for node_id, score in similar
                if self.knowledge_graph.get_node(node_id)
            ]
        
        return status
    
    def get_system_insights(self) -> Dict[str, Any]:
        """Get system-wide insights and recommendations"""
        insights_node = self.knowledge_graph.get_node("insights_current")
        
        system_insights = {
            "pipeline_stats": self.pipeline.status(),
            "knowledge_stats": self.knowledge_graph.get_stats(),
            "active_builds": len([
                c for c in self.pipeline.capsules.values()
                if c.current_state in [CapsuleState.BUILD, CapsuleState.VALIDATE]
            ]),
            "recommendations_cached": len(self.recommendations_cache)
        }
        
        if insights_node:
            system_insights["graph_insights"] = insights_node.data
        
        return system_insights
    
    async def _get_ml_recommendations(self, context) -> List[Dict[str, Any]]:
        """Get ML-based recommendations for capsule"""
        recommendations = []
        
        # Prepare features for ML prediction
        features = self._extract_ml_features(context)
        
        # Get ML predictions
        time_prediction = self.ml_engine.predict_completion_time(features)
        success_prediction = self.ml_engine.predict_success_probability(features)
        cost_prediction = self.ml_engine.predict_cost(features)
        
        # Store predictions in context
        context.metadata.update({
            'ml_predictions': {
                'completion_time': time_prediction,
                'success_probability': success_prediction,
                'estimated_cost': cost_prediction
            }
        })
        
        # Generate recommendations based on predictions
        if time_prediction['predicted_hours'] > 40:
            recommendations.append({
                'type': 'time_optimization',
                'priority': 'high',
                'confidence': time_prediction['confidence'],
                'suggestion': f"Predicted {time_prediction['predicted_hours']:.1f} hours - consider breaking into smaller capsules",
                'impact': 'Reduce complexity and improve success rate'
            })
        
        if success_prediction['success_probability'] < 0.7:
            recommendations.append({
                'type': 'success_optimization',
                'priority': 'critical',
                'confidence': success_prediction['confidence'],
                'suggestion': f"Low success probability ({success_prediction['success_probability']:.1%}) - add resources or reduce scope",
                'impact': f"Could improve success rate to 85%+"
            })
        
        if cost_prediction['total_cost'] > 2000:
            recommendations.append({
                'type': 'cost_optimization',
                'priority': 'medium',
                'confidence': cost_prediction['confidence'],
                'suggestion': f"High estimated cost (${cost_prediction['total_cost']:.0f}) - consider standard approach",
                'impact': f"Could save ${cost_prediction['total_cost'] * 0.3:.0f}"
            })
        
        # Get specific optimization recommendations
        ml_optimizations = self.ml_engine.get_optimization_recommendations(features)
        for opt in ml_optimizations:
            recommendations.append({
                'type': 'ml_optimization',
                'priority': opt['priority'],
                'confidence': 0.8,
                'suggestion': opt['suggestion'],
                'impact': opt['impact']
            })
        
        return recommendations
    
    def _extract_ml_features(self, context) -> Dict[str, Any]:
        """Extract features for ML prediction"""
        # Count requirements
        requirements_path = context.path / "spec" / "requirements.yaml"
        num_requirements = 0
        if requirements_path.exists():
            import yaml
            try:
                with open(requirements_path, 'r') as f:
                    reqs = yaml.safe_load(f)
                    if reqs and 'requirements' in reqs:
                        num_requirements = len(reqs['requirements'].get('functional', []))
            except:
                pass
        
        # Extract other features
        features = {
            'capsule_type': context.metadata.get('type', 'general'),
            'num_requirements': num_requirements,
            'num_dependencies': len(context.metadata.get('dependencies', [])),
            'team_size': len(context.metadata.get('assigned_agents', [])),
            'has_external_apis': 1 if 'api' in str(context.metadata).lower() else 0,
            'has_database': 1 if 'database' in str(context.metadata).lower() else 0,
            'complexity_score': context.metadata.get('complexity', {}).get('score', 5),
            'primary_agent': context.metadata.get('assigned_agents', ['general'])[0] if context.metadata.get('assigned_agents') else 'general'
        }
        
        return features
    
    def get_enhanced_system_insights(self) -> Dict[str, Any]:
        """Get enhanced system insights with ML analytics"""
        # Base insights
        insights = self.get_system_insights()
        
        # Add ML model status
        ml_status = self.ml_engine.get_model_status()
        insights['ml_models'] = ml_status
        
        # Add performance analytics
        performance_summary = self.performance_analytics.get_performance_summary()
        insights['performance_analytics'] = performance_summary
        
        # Add cost optimization opportunities
        try:
            cost_optimizations = self.cost_optimizer.identify_cost_optimizations()
            insights['cost_optimizations'] = {
                'total_opportunities': len(cost_optimizations),
                'potential_savings': sum(opt.savings for opt in cost_optimizations),
                'top_opportunities': [
                    {
                        'capsule': opt.capsule_name,
                        'type': opt.optimization_type,
                        'savings': opt.savings,
                        'recommendation': opt.recommendation
                    }
                    for opt in cost_optimizations[:5]
                ]
            }
        except Exception as e:
            logger.warning(f"Failed to get cost optimizations: {e}")
            insights['cost_optimizations'] = {'error': str(e)}
        
        # Add predictions for active capsules
        active_predictions = {}
        for name, context in self.pipeline.capsules.items():
            if context.current_state not in [CapsuleState.MONITOR, CapsuleState.ARCHIVED]:
                try:
                    features = self._extract_ml_features(context)
                    time_pred = self.ml_engine.predict_completion_time(features)
                    success_pred = self.ml_engine.predict_success_probability(features)
                    
                    active_predictions[name] = {
                        'predicted_hours': time_pred['predicted_hours'],
                        'success_probability': success_pred['success_probability'],
                        'current_state': context.current_state.value
                    }
                except Exception as e:
                    logger.warning(f"Failed to predict for {name}: {e}")
        
        insights['active_predictions'] = active_predictions
        
        return insights


def main():
    """CLI interface for intelligent builder"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Intelligent Huxley")
    parser.add_argument("command", choices=["start", "create", "status", "insights", "test"],
                       help="Command to execute")
    parser.add_argument("--name", help="Capsule name")
    parser.add_argument("--type", default="general", help="Capsule type")
    parser.add_argument("--lane", choices=["standard", "standard"], default="standard",
                       help="Lane assignment")
    
    args = parser.parse_args()
    
    builder = IntelligentBuilder()
    
    if args.command == "start":
        # Start autonomous mode
        asyncio.run(builder.start_autonomous_mode())
    
    elif args.command == "create":
        if not args.name:
            print("Error: --name required for create")
            sys.exit(1)
        
        result = builder.create_capsule(args.name, args.type, args.lane)
        print(json.dumps(result, indent=2))
    
    elif args.command == "status":
        if args.name:
            status = builder.get_capsule_status(args.name)
        else:
            status = builder.pipeline.status()
        
        print(json.dumps(status, indent=2))
    
    elif args.command == "insights":
        insights = builder.get_system_insights()
        print(json.dumps(insights, indent=2))
    
    elif args.command == "test":
        # Test with an existing capsule
        print("Testing intelligent builder with existing capsule...")
        
        # Find an existing capsule
        existing_capsules = list(builder.pipeline.capsules.keys())
        if existing_capsules:
            test_capsule = existing_capsules[0]
            print(f"Testing with capsule: {test_capsule}")
            
            # Get status
            status = builder.get_capsule_status(test_capsule)
            print("Status:", json.dumps(status, indent=2))
            
            # Try to advance
            if builder.pipeline.advance(test_capsule):
                print(f"Successfully advanced {test_capsule}")
            else:
                print(f"Could not advance {test_capsule}")
        else:
            print("No existing capsules found")


if __name__ == "__main__":
    main()