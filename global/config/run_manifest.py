#!/usr/bin/env python3
"""
Huxley Run Manifest Management
Standardized run tracking and replay functionality
"""

import json
import hashlib
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import uuid

# Import paths configuration
try:
    from .paths import paths, config
except ImportError:
    # Fallback for standalone usage
    import importlib.util
    import sys
    from pathlib import Path
    
    config_dir = Path(__file__).parent
    spec = importlib.util.spec_from_file_location("paths_config", config_dir / "paths.py")
    paths_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(paths_module)
    paths = paths_module.paths
    config = paths_module.config

class RunManifest:
    """Huxley Run Manifest for tracking execution artifacts"""
    
    SCHEMA_VERSION = "1.0.0"
    
    def __init__(self, capsule_name: str, run_id: Optional[str] = None):
        self.capsule_name = capsule_name
        self.run_id = run_id or self._generate_run_id()
        
        # Initialize manifest structure
        self.manifest = {
            "schema_version": self.SCHEMA_VERSION,
            "run_id": self.run_id,
            "capsule": {
                "name": capsule_name,
                "version": "1.0.0",  # Default, should be overridden
                "path": str(paths.capsules / capsule_name)
            },
            "execution": {
                "started_at": datetime.now().isoformat(),
                "status": "running"
            },
            "environment": self._capture_environment(),
            "inputs": {},
            "outputs": {
                "artifacts": [],
                "logs": {},
                "metrics": {}
            },
            "reproducibility": self._capture_reproducibility_info(),
            "validation": {
                "dod_checks": [],
                "test_results": {}
            },
            "metadata": {
                "created_by": "Huxley",
                "tags": [],
                "notes": "",
                "related_runs": []
            }
        }
        
        # Runtime tracking
        self._start_time = time.time()
        self._resource_baseline = self._capture_resource_baseline()
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID with timestamp and random component"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = str(uuid.uuid4())[:8]
        return f"{timestamp}_{random_suffix}"
    
    def _capture_environment(self) -> Dict[str, Any]:
        """Capture execution environment information"""
        return {
            "system": {
                "platform": platform.platform(),
                "python_version": sys.version,
                "builder_version": "1.0.0",  # TODO: Get from version file
                "architecture": platform.machine(),
                "hostname": platform.node()
            },
            "variables": self._safe_env_vars(),
            "working_directory": str(Path.cwd())
        }
    
    def _safe_env_vars(self) -> Dict[str, str]:
        """Capture safe environment variables (no secrets)"""
        safe_vars = {}
        safe_prefixes = ['BUILDER_', 'PATH', 'HOME', 'USER', 'LANG', 'TERM']
        
        for key, value in os.environ.items():
            # Only include safe variables
            if any(key.startswith(prefix) for prefix in safe_prefixes):
                # Exclude potential secrets
                if not any(secret in key.upper() for secret in ['KEY', 'SECRET', 'TOKEN', 'PASS']):
                    safe_vars[key] = value
        
        return safe_vars
    
    def _capture_reproducibility_info(self) -> Dict[str, Any]:
        """Capture information needed for reproducible runs"""
        repro_info = {
            "random_seed": None,  # Set by caller if needed
            "git_commit": None,
            "builder_checksum": None
        }
        
        # Try to get git commit
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'],
                                  cwd=paths.base, capture_output=True, text=True)
            if result.returncode == 0:
                repro_info["git_commit"] = result.stdout.strip()
        except Exception:
            pass

        # Calculate Huxley checksum
        try:
            repro_info["builder_checksum"] = self._calculate_builder_checksum()
        except Exception:
            pass
        
        return repro_info
    
    def _calculate_builder_checksum(self) -> str:
        """Calculate checksum of key Huxley files"""
        hasher = hashlib.sha256()
        
        # Key files that affect execution
        key_files = [
            paths.base / "CLAUDE.md",
            paths.config / "paths.py",
            paths.base / "global" / "schemas" / "run_manifest.json"
        ]
        
        for file_path in key_files:
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    hasher.update(f.read())
        
        return hasher.hexdigest()[:16]  # Truncated for readability
    
    def _capture_resource_baseline(self) -> Dict[str, float]:
        """Capture baseline resource usage"""
        try:
            import psutil
            process = psutil.Process()
            return {
                "cpu_percent": process.cpu_percent(),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "start_time": time.time()
            }
        except ImportError:
            return {}
    
    def set_capsule_info(self, version: str = None, lane: str = None):
        """Set capsule version and lane information"""
        if version:
            self.manifest["capsule"]["version"] = version
        if lane:
            self.manifest["capsule"]["lane"] = lane
    
    def add_input_files(self, file_paths: List[Union[str, Path]]):
        """Add input files with integrity hashes"""
        input_files = []
        
        for file_path in file_paths:
            path = Path(file_path)
            if path.exists():
                file_hash = self._calculate_file_hash(path)
                stat = path.stat()
                
                input_files.append({
                    "path": str(path),
                    "hash": file_hash,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        self.manifest["inputs"]["files"] = input_files
    
    def add_input_parameters(self, parameters: Dict[str, Any]):
        """Add input parameters"""
        self.manifest["inputs"]["parameters"] = parameters
    
    def capture_dependencies(self):
        """Capture current dependency versions"""
        deps = {}
        
        # Python packages
        try:
            from importlib.metadata import distributions
            installed_packages = {dist.metadata["Name"]: dist.version
                                for dist in distributions()}
            deps["python_packages"] = installed_packages
        except Exception:
            pass
        
        # NPM packages (if package.json exists)
        package_json = paths.base / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    package_data = json.load(f)
                    deps["npm_packages"] = package_data.get("dependencies", {})
            except Exception:
                pass
        
        self.manifest["inputs"]["dependencies"] = deps
    
    def add_artifact(self, file_path: Union[str, Path], artifact_type: str = "other", 
                    description: str = ""):
        """Add output artifact"""
        path = Path(file_path)
        
        artifact = {
            "path": str(path),
            "type": artifact_type,
            "description": description
        }
        
        if path.exists():
            artifact["hash"] = self._calculate_file_hash(path)
            artifact["size"] = path.stat().st_size
        
        self.manifest["outputs"]["artifacts"].append(artifact)
    
    def set_log_paths(self, stdout_path: str = None, stderr_path: str = None, 
                     combined_path: str = None):
        """Set paths to log files"""
        logs = {}
        if stdout_path:
            logs["stdout_path"] = stdout_path
        if stderr_path:
            logs["stderr_path"] = stderr_path  
        if combined_path:
            logs["combined_path"] = combined_path
        
        self.manifest["outputs"]["logs"].update(logs)
    
    def add_structured_log(self, level: str, message: str, source: str = "", 
                          data: Dict[str, Any] = None):
        """Add structured log entry"""
        if "structured_logs" not in self.manifest["outputs"]["logs"]:
            self.manifest["outputs"]["logs"]["structured_logs"] = []
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "source": source,
            "data": data or {}
        }
        
        self.manifest["outputs"]["logs"]["structured_logs"].append(log_entry)
    
    def add_dod_check(self, name: str, status: str, message: str = "", 
                     details: Dict[str, Any] = None):
        """Add Definition of Done check result"""
        check = {
            "name": name,
            "status": status,
            "message": message,
            "details": details or {}
        }
        
        self.manifest["validation"]["dod_checks"].append(check)
    
    def set_test_results(self, total: int = 0, passed: int = 0, failed: int = 0, 
                        skipped: int = 0, coverage_percent: float = None):
        """Set test execution results"""
        test_results = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped
        }
        
        if coverage_percent is not None:
            test_results["coverage_percent"] = coverage_percent
        
        self.manifest["validation"]["test_results"] = test_results
    
    def finish_execution(self, exit_code: int = 0, status: str = "completed"):
        """Finalize execution tracking"""
        end_time = time.time()
        
        self.manifest["execution"].update({
            "ended_at": datetime.now().isoformat(),
            "duration_ms": int((end_time - self._start_time) * 1000),
            "exit_code": exit_code,
            "status": status
        })
        
        # Capture final resource metrics
        self._capture_final_metrics()
    
    def _capture_final_metrics(self):
        """Capture final resource usage metrics"""
        try:
            import psutil
            process = psutil.Process()
            
            if self._resource_baseline:
                baseline = self._resource_baseline
                current_memory = process.memory_info().rss / 1024 / 1024
                
                metrics = {
                    "cpu_usage_percent": process.cpu_percent(),
                    "memory_peak_mb": max(baseline.get("memory_mb", 0), current_memory),
                    "execution_time_seconds": time.time() - baseline.get("start_time", 0)
                }
                
                self.manifest["outputs"]["metrics"] = metrics
        except ImportError:
            pass
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()[:16]  # Truncated for readability
    
    def get_run_directory(self) -> Path:
        """Get the run directory for this execution"""
        capsule_path = paths.capsules / self.capsule_name
        run_dir = capsule_path / "runs" / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
    
    def save_manifest(self, custom_path: Optional[Path] = None) -> Path:
        """Save manifest to disk"""
        if custom_path:
            manifest_path = custom_path
        else:
            run_dir = self.get_run_directory()
            manifest_path = run_dir / "manifest.json"
        
        # Ensure directory exists
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write manifest
        with open(manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2, default=str)
        
        return manifest_path
    
    def to_dict(self) -> Dict[str, Any]:
        """Return manifest as dictionary"""
        return self.manifest.copy()
    
    def to_json(self) -> str:
        """Return manifest as JSON string"""
        return json.dumps(self.manifest, indent=2, default=str)
    
    @classmethod
    def load_manifest(cls, manifest_path: Path) -> 'RunManifest':
        """Load manifest from file"""
        with open(manifest_path) as f:
            data = json.load(f)
        
        # Create instance
        instance = cls(data["capsule"]["name"], data["run_id"])
        instance.manifest = data
        
        return instance
    
    @classmethod
    def list_runs(cls, capsule_name: str) -> List[Dict[str, Any]]:
        """List all runs for a capsule"""
        capsule_path = paths.capsules / capsule_name
        runs_dir = capsule_path / "runs"
        
        if not runs_dir.exists():
            return []
        
        runs = []
        for run_dir in runs_dir.iterdir():
            if run_dir.is_dir():
                manifest_path = run_dir / "manifest.json"
                if manifest_path.exists():
                    try:
                        manifest = cls.load_manifest(manifest_path)
                        runs.append({
                            "run_id": manifest.run_id,
                            "started_at": manifest.manifest["execution"]["started_at"],
                            "status": manifest.manifest["execution"].get("status", "unknown"),
                            "duration_ms": manifest.manifest["execution"].get("duration_ms"),
                            "manifest_path": str(manifest_path)
                        })
                    except Exception:
                        continue
        
        # Sort by start time, most recent first
        runs.sort(key=lambda x: x["started_at"], reverse=True)
        return runs


def validate_manifest(manifest_data: Dict[str, Any]) -> List[str]:
    """Validate manifest against schema"""
    import jsonschema
    
    schema_path = paths.base / "global" / "schemas" / "run_manifest.json"
    
    try:
        with open(schema_path) as f:
            schema = json.load(f)
        
        jsonschema.validate(manifest_data, schema)
        return []  # No errors
        
    except jsonschema.ValidationError as e:
        return [str(e)]
    except FileNotFoundError:
        return ["Schema file not found"]
    except Exception as e:
        return [f"Validation error: {e}"]