#!/usr/bin/env python3
"""
Run Artifact Specification - Standardized manifest schema for Huxley capsule runs
Enables autopsy, replay, dependency tracking, and cross-run analysis
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json
import pathlib

@dataclass
class RunInput:
    """Input specification for a run"""
    name: str
    value: Any
    source: str  # 'env', 'file', 'user', 'config'
    sensitive: bool = False

@dataclass
class RunOutput:
    """Output specification for a run"""
    name: str
    path: str
    size_bytes: Optional[int] = None
    content_type: Optional[str] = None
    success: bool = True

@dataclass
class RunStage:
    """Individual stage within a run"""
    name: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[int] = None
    exit_code: Optional[int] = None
    status: str = "running"  # 'pending', 'running', 'success', 'failed', 'skipped'
    command: Optional[str] = None
    log_path: Optional[str] = None
    error_message: Optional[str] = None

@dataclass
class RunDependency:
    """External dependency used during run"""
    name: str
    type: str  # 'mcp', 'api', 'tool', 'service', 'file'
    version: Optional[str] = None
    endpoint: Optional[str] = None
    status: str = "available"  # 'available', 'degraded', 'unavailable'

@dataclass
class RunEnvironment:
    """Environment capture for reproducibility"""
    python_version: Optional[str] = None
    working_directory: str = ""
    environment_variables: Dict[str, str] = None
    system_info: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.environment_variables is None:
            self.environment_variables = {}

@dataclass
class RunManifest:
    """Complete run manifest for Huxley capsules"""
    # Identity
    run_id: str
    capsule_name: str
    capsule_version: str
    lane: str  # 'fast', 'deep'
    
    # Timing
    start_time: str
    end_time: Optional[str] = None
    total_duration_ms: Optional[int] = None
    
    # Status
    status: str = "running"  # 'pending', 'running', 'success', 'failed', 'cancelled'
    exit_code: Optional[int] = None
    success: bool = False
    
    # Context
    trigger: str = "manual"  # 'manual', 'scheduled', 'webhook', 'dependency'
    user: Optional[str] = None
    commit_hash: Optional[str] = None
    
    # Specifications
    inputs: List[RunInput] = None
    outputs: List[RunOutput] = None
    stages: List[RunStage] = None
    dependencies: List[RunDependency] = None
    environment: RunEnvironment = None
    
    # Results
    error_summary: Optional[str] = None
    warning_count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.inputs is None:
            self.inputs = []
        if self.outputs is None:
            self.outputs = []
        if self.stages is None:
            self.stages = []
        if self.dependencies is None:
            self.dependencies = []
        if self.environment is None:
            self.environment = RunEnvironment()
        if self.metadata is None:
            self.metadata = {}
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper serialization"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RunManifest':
        """Create from dictionary"""
        # Convert nested dataclasses
        if 'inputs' in data:
            data['inputs'] = [RunInput(**inp) for inp in data['inputs']]
        if 'outputs' in data:
            data['outputs'] = [RunOutput(**out) for out in data['outputs']]
        if 'stages' in data:
            data['stages'] = [RunStage(**stage) for stage in data['stages']]
        if 'dependencies' in data:
            data['dependencies'] = [RunDependency(**dep) for dep in data['dependencies']]
        if 'environment' in data:
            data['environment'] = RunEnvironment(**data['environment'])
        
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'RunManifest':
        """Create from JSON string"""
        return cls.from_dict(json.loads(json_str))
    
    def save(self, file_path: Union[str, pathlib.Path]):
        """Save manifest to file"""
        path = pathlib.Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            f.write(self.to_json())
    
    @classmethod
    def load(cls, file_path: Union[str, pathlib.Path]) -> 'RunManifest':
        """Load manifest from file"""
        with open(file_path, 'r') as f:
            return cls.from_json(f.read())
    
    def add_stage(self, name: str, command: str = None) -> RunStage:
        """Add a new stage and return it for tracking"""
        stage = RunStage(
            name=name,
            start_time=datetime.now().isoformat(),
            command=command
        )
        self.stages.append(stage)
        return stage
    
    def complete_stage(self, stage_name: str, exit_code: int = 0, 
                      error_message: str = None):
        """Complete a stage with results"""
        for stage in self.stages:
            if stage.name == stage_name:
                stage.end_time = datetime.now().isoformat()
                stage.exit_code = exit_code
                stage.status = "success" if exit_code == 0 else "failed"
                if error_message:
                    stage.error_message = error_message
                
                # Calculate duration
                if stage.start_time:
                    start = datetime.fromisoformat(stage.start_time)
                    end = datetime.fromisoformat(stage.end_time)
                    stage.duration_ms = int((end - start).total_seconds() * 1000)
                break
    
    def complete_run(self, exit_code: int = 0, error_summary: str = None):
        """Complete the entire run"""
        self.end_time = datetime.now().isoformat()
        self.exit_code = exit_code
        self.success = exit_code == 0
        self.status = "success" if self.success else "failed"
        
        if error_summary:
            self.error_summary = error_summary
        
        # Calculate total duration
        if self.start_time:
            start = datetime.fromisoformat(self.start_time)
            end = datetime.fromisoformat(self.end_time)
            self.total_duration_ms = int((end - start).total_seconds() * 1000)

def create_run_manifest(capsule_name: str, lane: str = "deep", 
                       trigger: str = "manual", user: str = None) -> RunManifest:
    """Create a new run manifest with default values"""
    run_id = f"{capsule_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    return RunManifest(
        run_id=run_id,
        capsule_name=capsule_name,
        capsule_version="1.0",  # Could be read from capsule.json
        lane=lane,
        start_time=datetime.now().isoformat(),
        trigger=trigger,
        user=user
    )