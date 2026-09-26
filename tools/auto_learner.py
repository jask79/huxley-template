#!/usr/bin/env python3
"""
Auto-Learning File Watcher for Huxley
Automatically detects file changes and triggers ML model updates
"""

import os
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Set, Any
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CapsuleFileHandler(FileSystemEventHandler):
    """File system event handler for capsule changes"""
    
    def __init__(self, auto_learner):
        self.auto_learner = auto_learner
        self.last_update = {}
        self.debounce_delay = 5  # 5 seconds to avoid too frequent updates
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # Only track certain file types
        path = Path(event.src_path)
        if self._should_track_file(path):
            self._handle_file_change(path, 'modified')
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if self._should_track_file(path):
            self._handle_file_change(path, 'created')
    
    def _should_track_file(self, path: Path) -> bool:
        """Check if file should be tracked for learning"""
        # Track source code files
        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.swift', '.java', '.go', '.rs', '.php', '.rb'}
        
        # Track config files
        config_files = {'package.json', 'requirements.txt', 'Pipfile', 'Cargo.toml', 'go.mod', 'requirements.yaml'}
        
        # Track documentation
        doc_extensions = {'.md', '.rst', '.txt'}
        
        return (
            path.suffix.lower() in code_extensions or
            path.name in config_files or
            (path.suffix.lower() in doc_extensions and 'spec' in str(path))
        )
    
    def _handle_file_change(self, path: Path, change_type: str):
        """Handle file change event with debouncing"""
        now = time.time()
        file_key = str(path)
        
        # Debounce to avoid excessive updates
        if file_key in self.last_update:
            if now - self.last_update[file_key] < self.debounce_delay:
                return
        
        self.last_update[file_key] = now
        
        # Find capsule for this file
        capsule_name = self.auto_learner._find_capsule_for_file(path)
        if capsule_name:
            self.auto_learner._update_capsule_metrics(capsule_name, path, change_type)
            logger.debug(f"File {change_type}: {path.name} in capsule {capsule_name}")

class AutoLearner:
    """Automatic learning system for Huxley"""
    
    def __init__(self):
        self.catalyst_root = Path("{{CATALYST_ROOT}}")
        self.capsules_dir = self.catalyst_root / "capsules"
        self.observer = None
        self.running = False
        
        # Track capsule metrics
        self.capsule_metrics = {}
        self.load_capsule_metrics()
        
        logger.info("Auto-learner initialized")
    
    def start_watching(self):
        """Start watching for file changes"""
        if not self.capsules_dir.exists():
            logger.warning("Capsules directory not found")
            return
        
        self.observer = Observer()
        handler = CapsuleFileHandler(self)
        
        # Watch all capsule directories recursively
        self.observer.schedule(handler, str(self.capsules_dir), recursive=True)
        
        self.observer.start()
        self.running = True
        
        logger.info(f"Auto-learner watching: {self.capsules_dir}")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_watching()
    
    def stop_watching(self):
        """Stop watching for file changes"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
        
        self.running = False
        self.save_capsule_metrics()
        logger.info("Auto-learner stopped")
    
    def _find_capsule_for_file(self, file_path: Path) -> str:
        """Find which capsule a file belongs to"""
        try:
            # Find the capsule directory by walking up from the file
            for parent in file_path.parents:
                if parent.parent == self.capsules_dir:
                    return parent.name
            return None
        except:
            return None
    
    def _update_capsule_metrics(self, capsule_name: str, file_path: Path, change_type: str):
        """Update metrics for a capsule based on file changes"""
        if capsule_name not in self.capsule_metrics:
            self.capsule_metrics[capsule_name] = {
                'files_created': 0,
                'files_modified': 0,
                'src_files': 0,
                'test_files': 0,
                'doc_files': 0,
                'config_files': 0,
                'last_activity': datetime.now().isoformat(),
                'file_types': set(),
                'complexity_indicators': {
                    'total_lines': 0,
                    'function_count': 0,
                    'import_count': 0
                }
            }
        
        metrics = self.capsule_metrics[capsule_name]
        
        # Update change counters
        if change_type == 'created':
            metrics['files_created'] += 1
        elif change_type == 'modified':
            metrics['files_modified'] += 1
        
        # Categorize file
        self._categorize_file(file_path, metrics)
        
        # Update complexity indicators
        self._analyze_file_complexity(file_path, metrics)
        
        # Update timestamp
        metrics['last_activity'] = datetime.now().isoformat()
        
        # Trigger learning update
        self._trigger_learning_update(capsule_name)
    
    def _categorize_file(self, file_path: Path, metrics: Dict[str, Any]):
        """Categorize file and update metrics"""
        path_str = str(file_path).lower()
        
        if '/src/' in path_str:
            metrics['src_files'] += 1
        elif '/test' in path_str or 'test' in file_path.name.lower():
            metrics['test_files'] += 1
        elif '/doc' in path_str or file_path.suffix in {'.md', '.rst'}:
            metrics['doc_files'] += 1
        elif file_path.name in {'package.json', 'requirements.txt', 'Pipfile', 'Cargo.toml'}:
            metrics['config_files'] += 1
        
        # Track file types
        if isinstance(metrics['file_types'], set):
            metrics['file_types'].add(file_path.suffix)
        else:
            metrics['file_types'] = set([file_path.suffix])
    
    def _analyze_file_complexity(self, file_path: Path, metrics: Dict[str, Any]):
        """Analyze file for complexity indicators"""
        try:
            if file_path.exists() and file_path.is_file():
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\n')
                
                # Update line count
                metrics['complexity_indicators']['total_lines'] += len(lines)
                
                # Count functions (simple heuristic)
                for line in lines:
                    line_stripped = line.strip().lower()
                    if (line_stripped.startswith('def ') or 
                        line_stripped.startswith('function ') or
                        'func ' in line_stripped):
                        metrics['complexity_indicators']['function_count'] += 1
                    
                    if (line_stripped.startswith('import ') or
                        line_stripped.startswith('from ') or
                        line_stripped.startswith('#include')):
                        metrics['complexity_indicators']['import_count'] += 1
                        
        except Exception as e:
            logger.debug(f"Failed to analyze {file_path}: {e}")
    
    def _trigger_learning_update(self, capsule_name: str):
        """Trigger ML model update for capsule"""
        try:
            from capsule_pipeline_engine import PipelineEngine
            
            # Load pipeline to get capsule context
            pipeline = PipelineEngine()
            
            if capsule_name in pipeline.capsules:
                context = pipeline.capsules[capsule_name]
                
                # Create learning data from current metrics
                learning_data = {
                    'capsule_name': capsule_name,
                    'capsule_type': context.metadata.get('type', 'general'),
                    'current_state': context.current_state.value,
                    'auto_metrics': self.capsule_metrics[capsule_name],
                    'last_updated': datetime.now().isoformat(),
                    'learning_trigger': 'file_change'
                }
                
                # Update ML models
                self._update_ml_models(learning_data)
                
                # Update performance analytics
                self._update_performance_analytics(capsule_name, learning_data)
                
        except Exception as e:
            logger.warning(f"Failed to trigger learning update: {e}")
    
    def _update_ml_models(self, learning_data: Dict[str, Any]):
        """Update ML models with file-based learning data"""
        try:
            from ml_prediction_engine import MLPredictionEngine
            
            # Convert metrics to ML features
            auto_metrics = learning_data['auto_metrics']
            
            ml_features = {
                'capsule_name': learning_data['capsule_name'],
                'capsule_type': learning_data['capsule_type'],
                'src_file_count': auto_metrics.get('src_files', 0),
                'test_file_count': auto_metrics.get('test_files', 0),
                'total_lines': auto_metrics.get('complexity_indicators', {}).get('total_lines', 0),
                'function_count': auto_metrics.get('complexity_indicators', {}).get('function_count', 0),
                'file_change_activity': auto_metrics.get('files_created', 0) + auto_metrics.get('files_modified', 0),
                'estimated_complexity': self._estimate_complexity_from_metrics(auto_metrics),
                'learning_source': 'file_watcher'
            }
            
            ml_engine = MLPredictionEngine()
            ml_engine.add_real_data(ml_features)
            
            logger.debug(f"Updated ML models with file metrics for {learning_data['capsule_name']}")
            
        except Exception as e:
            logger.warning(f"Failed to update ML models: {e}")
    
    def _update_performance_analytics(self, capsule_name: str, learning_data: Dict[str, Any]):
        """Update performance analytics with file metrics"""
        try:
            from performance_analytics import PerformanceAnalytics
            
            analytics = PerformanceAnalytics()
            auto_metrics = learning_data['auto_metrics']
            
            # Record development activity metrics
            activity_score = (
                auto_metrics.get('files_created', 0) * 2 +
                auto_metrics.get('files_modified', 0) +
                auto_metrics.get('src_files', 0) * 3
            )
            
            analytics.record_metric(
                capsule_name=capsule_name,
                metric_type='development_activity_score',
                value=activity_score,
                metadata={
                    'files_created': auto_metrics.get('files_created', 0),
                    'files_modified': auto_metrics.get('files_modified', 0),
                    'src_files': auto_metrics.get('src_files', 0),
                    'auto_recorded': True,
                    'source': 'file_watcher'
                }
            )
            
            # Record complexity metrics
            complexity = auto_metrics.get('complexity_indicators', {})
            if complexity.get('total_lines', 0) > 0:
                analytics.record_metric(
                    capsule_name=capsule_name,
                    metric_type='code_complexity_lines',
                    value=complexity['total_lines'],
                    metadata=complexity
                )
            
        except Exception as e:
            logger.warning(f"Failed to update performance analytics: {e}")
    
    def _estimate_complexity_from_metrics(self, auto_metrics: Dict[str, Any]) -> float:
        """Estimate complexity score from file metrics"""
        complexity = 1.0  # Base complexity
        
        # Add complexity based on file counts
        complexity += auto_metrics.get('src_files', 0) * 0.5
        complexity += auto_metrics.get('config_files', 0) * 0.3
        
        # Add complexity based on code metrics
        complexity_indicators = auto_metrics.get('complexity_indicators', {})
        complexity += complexity_indicators.get('function_count', 0) * 0.1
        complexity += complexity_indicators.get('import_count', 0) * 0.05
        
        # Add complexity based on file types
        file_types = auto_metrics.get('file_types', set())
        if isinstance(file_types, (set, list)):
            complexity += len(file_types) * 0.2
        
        return min(complexity, 10.0)  # Cap at 10
    
    def load_capsule_metrics(self):
        """Load saved capsule metrics"""
        metrics_path = self.catalyst_root / "registry/auto_learner_metrics.json"
        
        if metrics_path.exists():
            try:
                with open(metrics_path, 'r') as f:
                    saved_metrics = json.load(f)
                
                # Convert file_types back to sets
                for capsule_name, metrics in saved_metrics.items():
                    if 'file_types' in metrics:
                        metrics['file_types'] = set(metrics['file_types'])
                
                self.capsule_metrics = saved_metrics
                logger.debug(f"Loaded metrics for {len(saved_metrics)} capsules")
                
            except Exception as e:
                logger.warning(f"Failed to load saved metrics: {e}")
    
    def save_capsule_metrics(self):
        """Save capsule metrics"""
        metrics_path = self.catalyst_root / "registry/auto_learner_metrics.json"
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Convert sets to lists for JSON serialization
            save_metrics = {}
            for capsule_name, metrics in self.capsule_metrics.items():
                save_metrics[capsule_name] = dict(metrics)
                if 'file_types' in save_metrics[capsule_name]:
                    save_metrics[capsule_name]['file_types'] = list(save_metrics[capsule_name]['file_types'])
            
            with open(metrics_path, 'w') as f:
                json.dump(save_metrics, f, indent=2)
            
            logger.debug(f"Saved metrics for {len(save_metrics)} capsules")
            
        except Exception as e:
            logger.warning(f"Failed to save metrics: {e}")
    
    def get_capsule_summary(self, capsule_name: str) -> Dict[str, Any]:
        """Get learning summary for a capsule"""
        if capsule_name not in self.capsule_metrics:
            return {"message": "No learning data available"}
        
        metrics = self.capsule_metrics[capsule_name]
        
        return {
            "capsule": capsule_name,
            "development_activity": {
                "files_created": metrics.get('files_created', 0),
                "files_modified": metrics.get('files_modified', 0),
                "last_activity": metrics.get('last_activity', 'Never')
            },
            "code_structure": {
                "source_files": metrics.get('src_files', 0),
                "test_files": metrics.get('test_files', 0),
                "doc_files": metrics.get('doc_files', 0),
                "config_files": metrics.get('config_files', 0)
            },
            "complexity_indicators": metrics.get('complexity_indicators', {}),
            "estimated_complexity": self._estimate_complexity_from_metrics(metrics),
            "file_types": list(metrics.get('file_types', set())) if isinstance(metrics.get('file_types'), set) else metrics.get('file_types', [])
        }


def main():
    """CLI interface for auto-learner"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-Learning File Watcher")
    parser.add_argument("command", choices=["start", "summary", "metrics"],
                       help="Command to execute")
    parser.add_argument("--capsule", help="Capsule name for summary")
    
    args = parser.parse_args()
    
    learner = AutoLearner()
    
    if args.command == "start":
        print("Starting auto-learner...")
        print("Press Ctrl+C to stop")
        learner.start_watching()
    
    elif args.command == "summary":
        if args.capsule:
            summary = learner.get_capsule_summary(args.capsule)
            print(json.dumps(summary, indent=2))
        else:
            print("Error: --capsule required for summary")
    
    elif args.command == "metrics":
        print("CAPSULE LEARNING METRICS:")
        for capsule_name in learner.capsule_metrics:
            summary = learner.get_capsule_summary(capsule_name)
            print(f"\n{capsule_name}:")
            print(f"  Activity: {summary['development_activity']['files_created']} created, "
                  f"{summary['development_activity']['files_modified']} modified")
            print(f"  Structure: {summary['code_structure']['source_files']} src files, "
                  f"{summary['code_structure']['test_files']} tests")
            print(f"  Complexity: {summary['estimated_complexity']:.1f}/10")


if __name__ == "__main__":
    main()