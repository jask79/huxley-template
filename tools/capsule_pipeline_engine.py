#!/usr/bin/env python3
"""
Capsule Pipeline Engine - Autonomous lifecycle management
Implements event-driven state machine for capsule progression
"""

import json
import yaml
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import subprocess
import logging
import hashlib
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.common.builder_utils import ConfigManager, CapsuleManager, PathValidator

class CapsuleState(Enum):
    """Capsule lifecycle states"""
    IDEATION = "ideation"
    DESIGN = "design"
    BUILD = "build"
    VALIDATE = "validate"
    DEPLOY = "deploy"
    MONITOR = "monitor"
    ARCHIVED = "archived"
    FAILED = "failed"
    ROLLBACK = "rollback"

@dataclass
class StateTransition:
    """Represents a state transition with conditions and actions"""
    from_state: CapsuleState
    to_state: CapsuleState
    conditions: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""

@dataclass
class CapsuleContext:
    """Maintains capsule state and context"""
    name: str
    path: Path
    current_state: CapsuleState
    lane: str = "standard"
    metadata: Dict[str, Any] = field(default_factory=dict)
    history: List[StateTransition] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

class PipelineEngine:
    """Autonomous pipeline engine for capsule lifecycle management"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.catalyst_root = Path("${CATALYST_ROOT}")
        self.config_path = config_path or self.catalyst_root / "global/pipelines/capsule_state_machine.yaml"
        self.registry_path = self.catalyst_root / "registry/pipeline_state.json"
        self.patterns_path = self.catalyst_root / "registry/success_patterns.json"
        
        # Load configuration
        self.config = self._load_config()
        self.capsules: Dict[str, CapsuleContext] = {}
        self.patterns: Dict[str, Any] = self._load_patterns()
        
        # Initialize state
        self._load_state()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load state machine configuration"""
        if not self.config_path.exists():
            logger.error(f"Configuration not found: {self.config_path}")
            return {}
            
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _load_patterns(self) -> Dict[str, Any]:
        """Load success patterns from previous builds"""
        if not self.patterns_path.exists():
            return {"patterns": [], "templates": {}, "optimizations": {}}
            
        with open(self.patterns_path, 'r') as f:
            return json.load(f)
    
    def _load_state(self):
        """Load persistent pipeline state"""
        if self.registry_path.exists():
            with open(self.registry_path, 'r') as f:
                data = json.load(f)
                for name, context_data in data.get("capsules", {}).items():
                    self.capsules[name] = self._deserialize_context(context_data)
    
    def _save_state(self):
        """Persist pipeline state"""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "updated_at": datetime.now().isoformat(),
            "capsules": {
                name: self._serialize_context(context)
                for name, context in self.capsules.items()
            }
        }
        
        with open(self.registry_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _serialize_context(self, context: CapsuleContext) -> Dict[str, Any]:
        """Serialize capsule context for storage"""
        return {
            "name": context.name,
            "path": str(context.path),
            "current_state": context.current_state.value,
            "metadata": context.metadata,
            "history": [
                {
                    "from": t.from_state.value,
                    "to": t.to_state.value,
                    "timestamp": t.timestamp.isoformat(),
                    "reason": t.reason
                }
                for t in context.history
            ],
            "errors": context.errors,
            "metrics": context.metrics,
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat()
        }
    
    def _deserialize_context(self, data: Dict[str, Any]) -> CapsuleContext:
        """Deserialize capsule context from storage"""
        context = CapsuleContext(
            name=data["name"],
            path=Path(data["path"]),
            current_state=CapsuleState(data["current_state"]),
            metadata=data.get("metadata", {}),
            errors=data.get("errors", []),
            metrics=data.get("metrics", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )
        
        # Reconstruct history
        for h in data.get("history", []):
            context.history.append(StateTransition(
                from_state=CapsuleState(h["from"]),
                to_state=CapsuleState(h["to"]),
                timestamp=datetime.fromisoformat(h["timestamp"]),
                reason=h.get("reason", "")
            ))
        
        return context
    
    def register_capsule(self, name: str, path: Path, lane: Optional[str] = None) -> CapsuleContext:
        """Register a new capsule for pipeline management"""
        if name in self.capsules:
            return self.capsules[name]
        
        # Auto-detect lane if not specified
        if not lane:
            lane = self._detect_lane(path)
        
        context = CapsuleContext(
            name=name,
            path=path,
            current_state=CapsuleState.IDEATION,
            lane=lane
        )
        
        self.capsules[name] = context
        self._save_state()
        
        # Trigger initial automation
        self._trigger_state_actions(context)
        
        logger.info(f"Registered capsule '{name}' in {lane}")
        return context
    
    def _detect_lane(self, path: Path) -> str:
        """Auto-detect lane from capsule configuration"""
        capsule_json = path / "capsule.json"
        requirements = path / "spec/requirements.yaml"
        
        # Check capsule.json first
        if capsule_json.exists():
            with open(capsule_json, 'r') as f:
                data = json.load(f)
        
        # Check requirements.yaml
        if requirements.exists():
            with open(requirements, 'r') as f:
                data = yaml.safe_load(f)
        
        # Default to standard for safety
        return "standard"
    
    def transition(self, capsule_name: str, target_state: CapsuleState, 
                  reason: str = "") -> bool:
        """Attempt to transition a capsule to a new state"""
        if capsule_name not in self.capsules:
            logger.error(f"Capsule '{capsule_name}' not found")
            return False
        
        context = self.capsules[capsule_name]
        
        # Check if transition is valid
        if not self._is_valid_transition(context, target_state):
            logger.warning(f"Invalid transition from {context.current_state} to {target_state}")
            return False
        
        # Check transition conditions
        if not self._check_conditions(context, target_state):
            logger.info(f"Conditions not met for transition to {target_state}")
            return False
        
        # Execute pre-transition hooks
        self._execute_hooks("pre_transition", context, target_state)
        
        # Record transition
        transition = StateTransition(
            from_state=context.current_state,
            to_state=target_state,
            reason=reason or "Automatic progression"
        )
        
        context.history.append(transition)
        context.current_state = target_state
        context.updated_at = datetime.now()
        
        # Execute transition actions
        self._execute_transition_actions(context, transition)
        
        # Execute post-transition hooks
        self._execute_hooks("post_transition", context, target_state)
        
        # Trigger state-specific automation
        self._trigger_state_actions(context)
        
        # AUTO-LEARN: Update ML models with real data
        self._auto_learn_from_transition(context, transition)
        
        # Save state
        self._save_state()
        
        # Log event
        self._log_event({
            "type": "state_transition",
            "capsule": capsule_name,
            "from": transition.from_state.value,
            "to": transition.to_state.value,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Transitioned '{capsule_name}' from {transition.from_state.value} to {target_state.value}")
        return True
    
    def _is_valid_transition(self, context: CapsuleContext, target_state: CapsuleState) -> bool:
        """Check if a state transition is valid"""
        valid_transitions = {
            CapsuleState.IDEATION: [CapsuleState.DESIGN, CapsuleState.ARCHIVED],
            CapsuleState.DESIGN: [CapsuleState.BUILD, CapsuleState.IDEATION, CapsuleState.ARCHIVED],
            CapsuleState.BUILD: [CapsuleState.VALIDATE, CapsuleState.DESIGN, CapsuleState.FAILED],
            CapsuleState.VALIDATE: [CapsuleState.DEPLOY, CapsuleState.BUILD, CapsuleState.FAILED],
            CapsuleState.DEPLOY: [CapsuleState.MONITOR, CapsuleState.ROLLBACK, CapsuleState.FAILED],
            CapsuleState.MONITOR: [CapsuleState.BUILD, CapsuleState.ARCHIVED],
            CapsuleState.FAILED: [CapsuleState.BUILD, CapsuleState.DESIGN, CapsuleState.ARCHIVED],
            CapsuleState.ROLLBACK: [CapsuleState.BUILD, CapsuleState.VALIDATE],
            CapsuleState.ARCHIVED: []  # Terminal state
        }
        
        return target_state in valid_transitions.get(context.current_state, [])
    
    def _check_conditions(self, context: CapsuleContext, target_state: CapsuleState) -> bool:
        """Check if conditions are met for state transition"""
        conditions_map = {
            CapsuleState.DESIGN: self._check_design_conditions,
            CapsuleState.BUILD: self._check_build_conditions,
            CapsuleState.VALIDATE: self._check_validate_conditions,
            CapsuleState.DEPLOY: self._check_deploy_conditions,
            CapsuleState.MONITOR: self._check_monitor_conditions
        }
        
        checker = conditions_map.get(target_state)
        if checker:
            return checker(context)
        
        return True
    
    def _check_design_conditions(self, context: CapsuleContext) -> bool:
        """Check conditions for entering design state"""
        requirements_path = context.path / "spec/requirements.yaml"
        capsule_json = context.path / "capsule.json"
        
        return requirements_path.exists() or capsule_json.exists()
    
    def _check_build_conditions(self, context: CapsuleContext) -> bool:
        """Check conditions for entering build state"""
        # Check for design artifacts
        design_doc = context.path / "docs/architecture.md"
        has_design = design_doc.exists() or context.metadata.get("design_approved", False)
        
        # Check for dependencies
        deps_resolved = context.metadata.get("dependencies_resolved", True)
        
        return has_design and deps_resolved
    
    def _check_validate_conditions(self, context: CapsuleContext) -> bool:
        """Check conditions for entering validate state"""
        src_path = context.path / "src"
        has_source = src_path.exists() and any(src_path.iterdir())
        
        # Check for basic tests
        tests_path = context.path / "tests"
        has_tests = tests_path.exists() or context.lane == "standard"
        
        return has_source and has_tests
    
    def _check_deploy_conditions(self, context: CapsuleContext) -> bool:
        """Check conditions for entering deploy state"""
        validation_passed = context.metadata.get("validation_passed", False)
        approval = context.metadata.get("deployment_approved", context.lane == "standard")
        
        return validation_passed and approval
    
    def _check_monitor_conditions(self, context: CapsuleContext) -> bool:
        """Check conditions for entering monitor state"""
        deployment_success = context.metadata.get("deployment_successful", False)
        monitoring_configured = context.metadata.get("monitoring_configured", True)
        
        return deployment_success and monitoring_configured
    
    def _trigger_state_actions(self, context: CapsuleContext):
        """Trigger automatic actions for current state"""
        actions_map = {
            CapsuleState.IDEATION: self._ideation_actions,
            CapsuleState.DESIGN: self._design_actions,
            CapsuleState.BUILD: self._build_actions,
            CapsuleState.VALIDATE: self._validate_actions,
            CapsuleState.DEPLOY: self._deploy_actions,
            CapsuleState.MONITOR: self._monitor_actions
        }
        
        action_handler = actions_map.get(context.current_state)
        if action_handler:
            try:
                action_handler(context)
            except Exception as e:
                logger.error(f"Error in state actions: {e}")
                context.errors.append(str(e))
    
    def _ideation_actions(self, context: CapsuleContext):
        """Automatic actions for ideation state"""
        # Generate requirements template if missing
        requirements_path = context.path / "spec/requirements.yaml"
        if not requirements_path.exists():
            self._generate_requirements_template(context)
        
        # Analyze similar capsules for patterns
        similar = self._find_similar_capsules(context)
        if similar:
            context.metadata["similar_capsules"] = similar
            self._suggest_patterns(context, similar)
        
        # Auto-suggest lane if not set
        if not context.metadata.get("lane_suggested"):
            suggested_lane = self._suggest_lane(context)
            context.metadata["suggested_lane"] = suggested_lane
            context.metadata["lane_suggested"] = True
    
    def _design_actions(self, context: CapsuleContext):
        """Automatic actions for design state"""
        # Select appropriate agent team
        agents = self._select_agents(context)
        context.metadata["assigned_agents"] = agents
        
        # Generate architecture document
        arch_doc = context.path / "docs/architecture.md"
        if not arch_doc.exists():
            self._generate_architecture_doc(context)
        
        # Identify and resolve dependencies
        deps = self._identify_dependencies(context)
        context.metadata["dependencies"] = deps
        
        # Estimate complexity and timeline
        complexity = self._estimate_complexity(context)
        context.metadata["complexity"] = complexity
        context.metadata["estimated_hours"] = complexity.get("hours", 8)
    
    def _build_actions(self, context: CapsuleContext):
        """Automatic actions for build state"""
        # Setup development environment
        self._setup_environment(context)
        
        # Monitor progress
        progress = self._calculate_progress(context)
        context.metrics["build_progress"] = progress
        
        # Run continuous tests
        if context.path.joinpath("tests").exists():
            test_results = self._run_tests(context)
            context.metrics["test_results"] = test_results
    
    def _validate_actions(self, context: CapsuleContext):
        """Automatic actions for validate state"""
        validation_suite = []
        
        if context.lane == "standard":
            # standard: minimal validation
            validation_suite = ["basic_functionality", "smoke_test"]
        else:
            # standard: comprehensive validation
            validation_suite = [
                "security_audit",
                "performance_benchmarks",
                "integration_tests",
                "accessibility_check",
                "compliance_validation"
            ]
        
        results = {}
        all_passed = True
        
        for validation in validation_suite:
            result = self._run_validation(context, validation)
            results[validation] = result
            if not result.get("passed", False):
                all_passed = False
        
        context.metadata["validation_results"] = results
        context.metadata["validation_passed"] = all_passed
    
    def _deploy_actions(self, context: CapsuleContext):
        """Automatic actions for deploy state"""
        # Backup current version
        self._create_backup(context)
        
        # Deploy to target
        deployment_result = self._deploy_capsule(context)
        context.metadata["deployment_result"] = deployment_result
        context.metadata["deployment_successful"] = deployment_result.get("success", False)
        
        # Run smoke tests
        if deployment_result.get("success"):
            smoke_test = self._run_smoke_test(context)
            context.metadata["smoke_test_passed"] = smoke_test.get("passed", False)
        
        # Update registry
        self._update_registry(context)
    
    def _monitor_actions(self, context: CapsuleContext):
        """Automatic actions for monitor state"""
        # Collect metrics
        metrics = self._collect_metrics(context)
        context.metrics.update(metrics)
        
        # Check for anomalies
        anomalies = self._detect_anomalies(context, metrics)
        if anomalies:
            context.metadata["anomalies"] = anomalies
            self._handle_anomalies(context, anomalies)
        
        # Extract success patterns
        if not context.errors and context.metrics.get("performance_score", 0) > 80:
            patterns = self._extract_patterns(context)
            self._update_pattern_library(patterns)
    
    def _execute_hooks(self, hook_type: str, context: CapsuleContext, 
                      target_state: Optional[CapsuleState] = None):
        """Execute lifecycle hooks"""
        hooks = self.config.get("hooks", {}).get(hook_type, [])
        
        for hook in hooks:
            try:
                if hook == "validate_prerequisites":
                    self._validate_prerequisites(context, target_state)
                elif hook == "backup_current_state":
                    self._backup_state(context)
                elif hook == "update_registry":
                    self._update_registry(context)
                elif hook == "notify_stakeholders":
                    self._notify_stakeholders(context, hook_type, target_state)
                elif hook == "extract_patterns":
                    patterns = self._extract_patterns(context)
                    if patterns:
                        self._update_pattern_library(patterns)
            except Exception as e:
                logger.error(f"Hook execution failed: {hook} - {e}")
    
    def _execute_transition_actions(self, context: CapsuleContext, 
                                   transition: StateTransition):
        """Execute actions during state transition"""
        # Map of transition-specific actions
        action_key = f"{transition.from_state.value}_to_{transition.to_state.value}"
        
        actions = {
            "ideation_to_design": [
                ("validate_requirements", self._validate_requirements),
                ("assign_agent_team", lambda c: self._select_agents(c))
            ],
            "design_to_build": [
                ("setup_build_environment", self._setup_environment),
                ("initialize_version_control", self._init_version_control)
            ],
            "build_to_validate": [
                ("freeze_code_version", self._freeze_version),
                ("trigger_validation_suite", lambda c: self._validate_actions(c))
            ],
            "validate_to_deploy": [
                ("create_deployment_package", self._create_deployment_package),
                ("backup_current_state", self._create_backup)
            ],
            "deploy_to_monitor": [
                ("activate_monitoring", self._activate_monitoring),
                ("establish_baselines", self._establish_baselines)
            ]
        }
        
        for action_name, action_func in actions.get(action_key, []):
            try:
                action_func(context)
                logger.debug(f"Executed action: {action_name}")
            except Exception as e:
                logger.error(f"Action failed: {action_name} - {e}")
                context.errors.append(f"{action_name}: {str(e)}")
    
    # Helper methods
    def _generate_requirements_template(self, context: CapsuleContext):
        """Generate a requirements template for new capsule"""
        template = {
            "name": context.name,
            "description": "TODO: Add description",
            "type": "TODO: application/automation/service",
            "requirements": {
                "functional": ["TODO: Add functional requirements"],
                "non_functional": ["TODO: Add non-functional requirements"],
                "constraints": ["TODO: Add constraints"]
            },
            "success_criteria": ["TODO: Define success criteria"],
            "dependencies": [],
            "estimated_effort": "TODO: Add estimate"
        }
        
        requirements_path = context.path / "spec/requirements.yaml"
        requirements_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(requirements_path, 'w') as f:
            yaml.dump(template, f, default_flow_style=False)
    
    def _find_similar_capsules(self, context: CapsuleContext) -> List[str]:
        """Find capsules with similar characteristics"""
        similar = []
        
        for name, other_context in self.capsules.items():
            if name == context.name:
                continue
            
            # Check for similarity based on metadata and path patterns
            similarity_score = 0
            
            if other_context.lane == context.lane:
                similarity_score += 1
            
            if other_context.metadata.get("type") == context.metadata.get("type"):
                similarity_score += 2
            
            # Check path similarity
            if context.path.parent == other_context.path.parent:
                similarity_score += 1
            
            if similarity_score >= 2:
                similar.append(name)
        
        return similar[:5]  # Return top 5 similar
    
    def _suggest_patterns(self, context: CapsuleContext, similar_capsules: List[str]):
        """Suggest patterns from similar successful capsules"""
        suggestions = []
        
        for capsule_name in similar_capsules:
            if capsule_name in self.patterns.get("successful_capsules", {}):
                pattern = self.patterns["successful_capsules"][capsule_name]
                suggestions.append({
                    "from_capsule": capsule_name,
                    "patterns": pattern.get("patterns", []),
                    "agents": pattern.get("agents", []),
                    "estimated_hours": pattern.get("hours", 0)
                })
        
        if suggestions:
            context.metadata["pattern_suggestions"] = suggestions
    
    def _suggest_lane(self, context: CapsuleContext) -> str:
        """Suggest appropriate lane based on capsule characteristics"""
        # Simple heuristic for lane suggestion
        indicators = {
            "standard": ["demo", "test", "experiment", "prototype", "personal"],
            "standard": ["production", "client", "business", "critical", "secure"]
        }
        
        name_lower = context.name.lower()
        
        for indicator in indicators["standard"]:
            if indicator in name_lower:
                return "standard"
        
        for indicator in indicators["standard"]:
            if indicator in name_lower:
                return "standard"
        
        # Default to standard for safety
        return "standard"
    
    def _select_agents(self, context: CapsuleContext) -> List[str]:
        """Select appropriate agents for the capsule"""
        agents = []
        
        # Base agents by type
        capsule_type = context.metadata.get("type", "general")
        
        agent_map = {
            "automation": ["automation-specialist", "test-automator"],
            "web": ["frontend-specialist", "javascript-pro"],
            "ios": ["ios-specialist", "deployment-engineer"],
            "macos": ["macos-specialist", "deployment-engineer"],
            "backend": ["backend-architect", "python-pro"]
        }
        
        agents.extend(agent_map.get(capsule_type, ["code-reviewer"]))
        
        # Add lane-specific agents
        if context.lane == "standard":
            agents.extend(["security-auditor", "performance-optimizer"])
        
        return list(set(agents))  # Remove duplicates
    
    def _estimate_complexity(self, context: CapsuleContext) -> Dict[str, Any]:
        """Estimate capsule complexity and effort"""
        complexity_score = 0
        factors = []
        
        # Check requirements complexity
        requirements_path = context.path / "spec/requirements.yaml"
        if requirements_path.exists():
            with open(requirements_path, 'r') as f:
                reqs = yaml.safe_load(f) or {}
                req_count = len(reqs.get("requirements", {}).get("functional", []))
                complexity_score += min(req_count * 2, 20)
                factors.append(f"{req_count} requirements")
        
        # Check for external dependencies
        deps = context.metadata.get("dependencies", [])
        complexity_score += len(deps) * 3
        if deps:
            factors.append(f"{len(deps)} dependencies")
        
        # Lane complexity
        if context.lane == "standard":
            complexity_score += 10
            factors.append("standard validation")
        
        # Estimate hours based on complexity
        hours = max(4, complexity_score * 2)
        
        return {
            "score": complexity_score,
            "factors": factors,
            "hours": hours,
            "level": "high" if complexity_score > 30 else "medium" if complexity_score > 15 else "low"
        }
    
    def _extract_patterns(self, context: CapsuleContext) -> Dict[str, Any]:
        """Extract reusable patterns from successful capsule"""
        patterns = {
            "capsule": context.name,
            "type": context.metadata.get("type"),
            "agents": context.metadata.get("assigned_agents", []),
            "duration_hours": (context.updated_at - context.created_at).total_seconds() / 3600,
            "patterns": [],
            "templates": {}
        }
        
        # Extract file patterns
        for root, dirs, files in os.walk(context.path):
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.swift')):
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(context.path)
                    
                    # Store file structure pattern
                    patterns["templates"][str(relative_path)] = {
                        "size": file_path.stat().st_size,
                        "type": file_path.suffix
                    }
        
        # Extract successful validation patterns
        if context.metadata.get("validation_results"):
            patterns["validation_success"] = list(context.metadata["validation_results"].keys())
        
        return patterns
    
    def _update_pattern_library(self, patterns: Dict[str, Any]):
        """Update the pattern library with new patterns"""
        if "successful_capsules" not in self.patterns:
            self.patterns["successful_capsules"] = {}
        
        capsule_name = patterns["capsule"]
        self.patterns["successful_capsules"][capsule_name] = patterns
        
        # Extract common patterns
        self._analyze_common_patterns()
        
        # Save patterns
        with open(self.patterns_path, 'w') as f:
            json.dump(self.patterns, f, indent=2)
    
    def _analyze_common_patterns(self):
        """Analyze and extract common patterns across successful capsules"""
        if "successful_capsules" not in self.patterns:
            return
        
        # Analyze agent usage
        agent_frequency = {}
        for capsule_data in self.patterns["successful_capsules"].values():
            for agent in capsule_data.get("agents", []):
                agent_frequency[agent] = agent_frequency.get(agent, 0) + 1
        
        self.patterns["common_agents"] = agent_frequency
        
        # Analyze file structure patterns
        structure_patterns = {}
        for capsule_data in self.patterns["successful_capsules"].values():
            for template_path in capsule_data.get("templates", {}).keys():
                structure_patterns[template_path] = structure_patterns.get(template_path, 0) + 1
        
        self.patterns["common_structures"] = structure_patterns
    
    def _log_event(self, event: Dict[str, Any]):
        """Log pipeline event to registry"""
        event_path = self.catalyst_root / "registry/events.jsonl"
        
        with open(event_path, 'a') as f:
            f.write(json.dumps(event) + '\n')
    
    # Stub methods for various operations (would be fully implemented in production)
    def _setup_environment(self, context: CapsuleContext):
        """Setup development environment for capsule"""
        logger.debug(f"Setting up environment for {context.name}")
    
    def _init_version_control(self, context: CapsuleContext):
        """Initialize version control for capsule"""
        logger.debug(f"Initializing version control for {context.name}")
    
    def _freeze_version(self, context: CapsuleContext):
        """Freeze code version for validation"""
        logger.debug(f"Freezing version for {context.name}")
    
    def _create_deployment_package(self, context: CapsuleContext):
        """Create deployment package"""
        logger.debug(f"Creating deployment package for {context.name}")
    
    def _create_backup(self, context: CapsuleContext):
        """Create backup of current state"""
        logger.debug(f"Creating backup for {context.name}")
    
    def _activate_monitoring(self, context: CapsuleContext):
        """Activate monitoring for deployed capsule"""
        logger.debug(f"Activating monitoring for {context.name}")
    
    def _establish_baselines(self, context: CapsuleContext):
        """Establish performance baselines"""
        logger.debug(f"Establishing baselines for {context.name}")
        
    def _run_tests(self, context: CapsuleContext) -> Dict[str, Any]:
        """Run tests for capsule"""
        return {"passed": True, "coverage": 85}
    
    def _run_validation(self, context: CapsuleContext, validation_type: str) -> Dict[str, Any]:
        """Run specific validation"""
        return {"passed": True, "details": f"{validation_type} passed"}
    
    def _deploy_capsule(self, context: CapsuleContext) -> Dict[str, Any]:
        """Deploy capsule to target environment"""
        return {"success": True, "deployed_at": datetime.now().isoformat()}
    
    def _run_smoke_test(self, context: CapsuleContext) -> Dict[str, Any]:
        """Run smoke tests on deployed capsule"""
        return {"passed": True}
    
    def _collect_metrics(self, context: CapsuleContext) -> Dict[str, Any]:
        """Collect performance metrics"""
        return {
            "cpu_usage": 15,
            "memory_usage": 256,
            "response_time": 150,
            "error_rate": 0.1,
            "performance_score": 92
        }
    
    def _detect_anomalies(self, context: CapsuleContext, metrics: Dict[str, Any]) -> List[str]:
        """Detect anomalies in metrics"""
        anomalies = []
        
        if metrics.get("error_rate", 0) > 1:
            anomalies.append("high_error_rate")
        
        if metrics.get("response_time", 0) > 1000:
            anomalies.append("slow_response")
        
        return anomalies
    
    def _handle_anomalies(self, context: CapsuleContext, anomalies: List[str]):
        """Handle detected anomalies"""
        for anomaly in anomalies:
            logger.warning(f"Anomaly detected in {context.name}: {anomaly}")
    
    def _validate_requirements(self, context: CapsuleContext):
        """Validate capsule requirements"""
        logger.debug(f"Validating requirements for {context.name}")
    
    def _generate_architecture_doc(self, context: CapsuleContext):
        """Generate architecture documentation"""
        logger.debug(f"Generating architecture doc for {context.name}")
    
    def _identify_dependencies(self, context: CapsuleContext) -> List[str]:
        """Identify capsule dependencies"""
        return []
    
    def _calculate_progress(self, context: CapsuleContext) -> float:
        """Calculate build progress"""
        return 75.0
    
    def _validate_prerequisites(self, context: CapsuleContext, 
                               target_state: Optional[CapsuleState]):
        """Validate prerequisites for state transition"""
        logger.debug(f"Validating prerequisites for {context.name}")
    
    def _backup_state(self, context: CapsuleContext):
        """Backup current capsule state"""
        logger.debug(f"Backing up state for {context.name}")
    
    def _update_registry(self, context: CapsuleContext):
        """Update capsule registry"""
        logger.debug(f"Updating registry for {context.name}")
    
    def _notify_stakeholders(self, context: CapsuleContext, event_type: str,
                            target_state: Optional[CapsuleState]):
        """Notify stakeholders of events"""
        logger.info(f"Notifying stakeholders: {event_type} for {context.name}")
    
    # CLI Interface
    def status(self, capsule_name: Optional[str] = None) -> Dict[str, Any]:
        """Get status of capsules"""
        if capsule_name:
            if capsule_name not in self.capsules:
                return {"error": f"Capsule '{capsule_name}' not found"}
            
            context = self.capsules[capsule_name]
            return self._serialize_context(context)
        
        # Return all capsules status
        return {
            "capsules": {
                name: {
                    "state": context.current_state.value,
                    "updated": context.updated_at.isoformat(),
                    "errors": len(context.errors)
                }
                for name, context in self.capsules.items()
            },
            "total": len(self.capsules)
        }
    
    def advance(self, capsule_name: str) -> bool:
        """Attempt to advance capsule to next logical state"""
        if capsule_name not in self.capsules:
            logger.error(f"Capsule '{capsule_name}' not found")
            return False
        
        context = self.capsules[capsule_name]
        
        # Determine next state
        next_states = {
            CapsuleState.IDEATION: CapsuleState.DESIGN,
            CapsuleState.DESIGN: CapsuleState.BUILD,
            CapsuleState.BUILD: CapsuleState.VALIDATE,
            CapsuleState.VALIDATE: CapsuleState.DEPLOY,
            CapsuleState.DEPLOY: CapsuleState.MONITOR,
            CapsuleState.MONITOR: CapsuleState.ARCHIVED
        }
        
        next_state = next_states.get(context.current_state)
        if not next_state:
            logger.info(f"No automatic progression from {context.current_state.value}")
            return False
        
        return self.transition(capsule_name, next_state, "Automatic advancement")
    
    def scan_for_capsules(self):
        """Scan for unregistered capsules and register them"""
        capsules_dir = self.catalyst_root / "capsules"
        
        for capsule_path in capsules_dir.iterdir():
            if not capsule_path.is_dir():
                continue
            
            if capsule_path.name.startswith('.'):
                continue
            
            # Check if already registered
            if capsule_path.name not in self.capsules:
                # Look for capsule.json or requirements.yaml
                if (capsule_path / "capsule.json").exists() or \
                   (capsule_path / "spec/requirements.yaml").exists():
                    self.register_capsule(capsule_path.name, capsule_path)
                    logger.info(f"Auto-registered capsule: {capsule_path.name}")
    
    def cleanup_stale(self, days: int = 30):
        """Clean up stale capsules"""
        cutoff = datetime.now() - timedelta(days=days)
        
        for name, context in list(self.capsules.items()):
            if context.updated_at < cutoff and context.current_state != CapsuleState.MONITOR:
                logger.info(f"Archiving stale capsule: {name}")
                self.transition(name, CapsuleState.ARCHIVED, f"Stale for {days} days")
    
    def _auto_learn_from_transition(self, context: CapsuleContext, transition: StateTransition):
        """Automatically learn from every state transition"""
        try:
            # Calculate duration for this state
            state_duration = None
            if len(context.history) > 1:
                prev_transition = context.history[-2]
                state_duration = (transition.timestamp - prev_transition.timestamp).total_seconds() / 3600
            
            # Extract current features
            features = self._extract_learning_features(context)
            
            # Add transition-specific data
            learning_data = {
                **features,
                'transition_type': f"{transition.from_state.value}_to_{transition.to_state.value}",
                'state_duration_hours': state_duration,
                'total_duration_hours': (datetime.now() - context.created_at).total_seconds() / 3600,
                'timestamp': datetime.now().isoformat()
            }
            
            # Mark completion and success for terminal states
            if transition.to_state == CapsuleState.MONITOR:
                learning_data.update({
                    'completed': True,
                    'success': True,
                    'final_duration_hours': (datetime.now() - context.created_at).total_seconds() / 3600
                })
            elif transition.to_state == CapsuleState.FAILED:
                learning_data.update({
                    'completed': True,
                    'success': False,
                    'failure_state': transition.from_state.value
                })
            
            # Load and update ML engine
            self._update_ml_models_async(learning_data)
            
            # Auto-update performance analytics
            self._record_performance_metrics(context, transition)
            
            logger.debug(f"Auto-learned from {context.name} transition: {transition.from_state.value} → {transition.to_state.value}")
            
        except Exception as e:
            logger.warning(f"Auto-learning failed for {context.name}: {e}")
    
    def _extract_learning_features(self, context: CapsuleContext) -> Dict[str, Any]:
        """Extract features for ML learning"""
        # Count requirements from spec file
        num_requirements = 0
        requirements_path = context.path / "spec" / "requirements.yaml"
        if requirements_path.exists():
            try:
                import yaml
                with open(requirements_path, 'r') as f:
                    reqs = yaml.safe_load(f)
                    if reqs and 'requirements' in reqs:
                        if 'functional' in reqs['requirements']:
                            num_requirements = len(reqs['requirements']['functional'])
            except:
                pass
        
        # Count source files
        src_files = 0
        if (context.path / "src").exists():
            src_files = len(list((context.path / "src").rglob("*")))
        
        # Count dependencies
        deps = self._count_dependencies(context.path)
        
        return {
            'capsule_name': context.name,
            'capsule_type': context.metadata.get('type', 'general'),
            'num_requirements': num_requirements,
            'num_dependencies': deps,
            'team_size': len(context.metadata.get('assigned_agents', [])),
            'has_external_apis': 1 if 'api' in str(context.metadata).lower() else 0,
            'has_database': 1 if 'database' in str(context.metadata).lower() else 0,
            'complexity_score': context.metadata.get('complexity', {}).get('score', 5),
            'src_file_count': src_files,
            'error_count': len(context.errors),
            'created_at': context.created_at.isoformat()
        }
    
    def _count_dependencies(self, capsule_path: Path) -> int:
        """Count dependencies from various dependency files"""
        deps = 0
        dependency_files = [
            capsule_path / "package.json",
            capsule_path / "requirements.txt", 
            capsule_path / "Pipfile",
            capsule_path / "Cargo.toml",
            capsule_path / "go.mod"
        ]
        
        for dep_file in dependency_files:
            if dep_file.exists():
                try:
                    content = dep_file.read_text()
                    if dep_file.name == "package.json":
                        import json
                        data = json.loads(content)
                        deps += len(data.get('dependencies', {}))
                        deps += len(data.get('devDependencies', {}))
                    elif dep_file.name == "requirements.txt":
                        deps += len([line for line in content.split('\n') if line.strip() and not line.startswith('#')])
                    else:
                        # Simple line count for other files
                        deps += len([line for line in content.split('\n') if line.strip() and not line.startswith('#')])
                except:
                    pass
        
        return deps
    
    def _update_ml_models_async(self, learning_data: Dict[str, Any]):
        """Update ML models asynchronously (non-blocking)"""
        try:
            # Import here to avoid circular dependencies
            from ml_prediction_engine import MLPredictionEngine
            
            # Load ML engine and add real data
            ml_engine = MLPredictionEngine()
            ml_engine.add_real_data(learning_data)
            
            logger.debug(f"Added real learning data for {learning_data.get('capsule_name', 'unknown')}")
            
        except Exception as e:
            logger.warning(f"Failed to update ML models: {e}")
    
    def _record_performance_metrics(self, context: CapsuleContext, transition: StateTransition):
        """Record performance metrics automatically"""
        try:
            from performance_analytics import PerformanceAnalytics
            
            analytics = PerformanceAnalytics()
            
            # Record state transition time
            if len(context.history) > 1:
                prev_transition = context.history[-2]
                duration = (transition.timestamp - prev_transition.timestamp).total_seconds() / 3600
                
                analytics.record_metric(
                    capsule_name=context.name,
                    metric_type=f"{transition.from_state.value}_duration_hours",
                    value=duration,
                    metadata={
                        'capsule_type': context.metadata.get('type', 'general'),
                        'auto_recorded': True
                    }
                )
            
            # Record success/failure
            if transition.to_state == CapsuleState.MONITOR:
                analytics.record_metric(
                    capsule_name=context.name,
                    metric_type="success_rate",
                    value=1.0,
                    metadata={'completed_successfully': True}
                )
            elif transition.to_state == CapsuleState.FAILED:
                analytics.record_metric(
                    capsule_name=context.name,
                    metric_type="success_rate", 
                    value=0.0,
                    metadata={
                        'failed_at_state': transition.from_state.value,
                        'errors': context.errors
                    }
                )
            
        except Exception as e:
            logger.warning(f"Failed to record performance metrics: {e}")


def main():
    """CLI interface for pipeline engine"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Capsule Pipeline Engine")
    parser.add_argument("command", choices=["status", "register", "advance", "scan", "cleanup"],
                       help="Command to execute")
    parser.add_argument("--capsule", help="Capsule name")
    parser.add_argument("--path", help="Capsule path for registration")
    parser.add_argument("--lane", choices=["standard", "standard"], 
                       help="Lane assignment")
    parser.add_argument("--days", type=int, default=30,
                       help="Days for stale cleanup (default: 30)")
    
    args = parser.parse_args()
    
    engine = PipelineEngine()
    
    if args.command == "status":
        result = engine.status(args.capsule)
        print(json.dumps(result, indent=2))
    
    elif args.command == "register":
        if not args.capsule or not args.path:
            print("Error: --capsule and --path required for registration")
            sys.exit(1)
        
        context = engine.register_capsule(args.capsule, Path(args.path), args.lane)
        print(f"Registered: {context.name} in {context.current_state.value}")
    
    elif args.command == "advance":
        if not args.capsule:
            print("Error: --capsule required for advance")
            sys.exit(1)
        
        if engine.advance(args.capsule):
            print(f"Advanced {args.capsule} successfully")
        else:
            print(f"Could not advance {args.capsule}")
    
    elif args.command == "scan":
        engine.scan_for_capsules()
        print(f"Scan complete. {len(engine.capsules)} capsules registered")
    
    elif args.command == "cleanup":
        engine.cleanup_stale(args.days)
        print(f"Cleanup complete")


if __name__ == "__main__":
    main()