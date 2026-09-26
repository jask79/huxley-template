#!/usr/bin/env python3
"""
Research Session Manager
Handles session state persistence, recovery, and lifecycle for Deep Research Agent
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import shutil

class ResearchSessionManager:
    def __init__(self, base_path: str = "{{CATALYST_ROOT}}"):
        self.base_path = Path(base_path)
        self.sessions_file = self.base_path / ".claude" / "research-sessions.json"
        self.index_file = self.base_path / ".claude" / "research-index.json"
        self.artifacts_root = self.base_path / "research" / "sources"
        self.logs_dir = self.base_path / "logs" / "research"
        
        # Ensure directories exist
        self.sessions_file.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts_root.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize session state
        self.sessions = self._load_sessions()
        self.index = self._load_index()
    
    def _load_sessions(self) -> Dict:
        """Load session state from persistence file"""
        if self.sessions_file.exists():
            with open(self.sessions_file, 'r') as f:
                return json.load(f)
        return {
            "session_tracking": {
                "current_session": None,
                "session_history": [],
                "max_sessions": 10
            }
        }
    
    def _load_index(self) -> Dict:
        """Load research index"""
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                return json.load(f)
        return {
            "research_index": {
                "last_updated": None,
                "total_research_items": 0,
                "categories": {}
            }
        }
    
    def start_session(self, topic: str, lane: str, template: str, 
                     requestor: str = "", priority: str = "medium") -> str:
        """Start a new research session"""
        session_id = f"{lane}-{datetime.now().strftime('%Y%m%d')}-{topic}-{uuid.uuid4().hex[:8]}"
        
        session_data = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "research_topic": topic,
            "template_used": template,
            "status": "active",
            "progress": {
                "search_iterations": 0,
                "sources_gathered": 0,
                "quality_score": 0.0,
                "start_time": datetime.now().isoformat(),
                "checkpoints": []
            },
            "artifacts": {
                "sources": [],
                "findings": {},
                "citations": []
            },
            "metadata": {
                "requestor": requestor,
                "priority": priority,
                "estimated_completion": self._estimate_completion(lane)
            }
        }
        
        # Create session artifact directory
        session_dir = self.artifacts_root / session_id
        for subdir in ["raw", "snapshots", "pdfs", "transcripts"]:
            (session_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        # Initialize artifact files
        self._init_artifact_files(session_dir)
        
        # Update session tracking
        self.sessions["session_tracking"]["current_session"] = session_id
        self.sessions["session_tracking"]["session_history"].insert(0, session_data)
        
        # Trim history if needed
        if len(self.sessions["session_tracking"]["session_history"]) > self.sessions["session_tracking"]["max_sessions"]:
            self.sessions["session_tracking"]["session_history"].pop()
        
        self._save_sessions()
        self._log_event("session_started", session_id, session_data)
        
        return session_id
    
    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session progress and artifacts"""
        session = self._find_session(session_id)
        if not session:
            return False
        
        # Update progress metrics
        if "progress" in updates:
            session["progress"].update(updates["progress"])
            
        # Add checkpoint if significant progress
        if "checkpoint" in updates:
            session["progress"]["checkpoints"].append({
                "time": datetime.now().isoformat(),
                "iteration": session["progress"]["search_iterations"],
                "sources": session["progress"]["sources_gathered"],
                "note": updates.get("checkpoint_note", "")
            })
        
        # Update artifacts
        if "artifacts" in updates:
            if "sources" in updates["artifacts"]:
                session["artifacts"]["sources"].extend(updates["artifacts"]["sources"])
            if "findings" in updates["artifacts"]:
                session["artifacts"]["findings"].update(updates["artifacts"]["findings"])
            if "citations" in updates["artifacts"]:
                session["artifacts"]["citations"].extend(updates["artifacts"]["citations"])
        
        # Save artifacts to files
        if "save_artifacts" in updates:
            self._save_artifacts(session_id, updates["save_artifacts"])
        
        self._save_sessions()
        self._log_event("session_updated", session_id, updates)
        
        return True
    
    def complete_session(self, session_id: str, quality_score: float, 
                        summary: Dict[str, Any]) -> bool:
        """Mark session as completed and update index"""
        session = self._find_session(session_id)
        if not session:
            return False
        
        session["status"] = "completed"
        session["progress"]["quality_score"] = quality_score
        session["progress"]["end_time"] = datetime.now().isoformat()
        session["summary"] = summary
        
        # Update research index
        self._update_index(session)
        
        # Clear current session if this was it
        if self.sessions["session_tracking"]["current_session"] == session_id:
            self.sessions["session_tracking"]["current_session"] = None
        
        self._save_sessions()
        self._save_index()
        self._log_event("session_completed", session_id, {"quality_score": quality_score})
        
        return True
    
    def fail_session(self, session_id: str, reason: str) -> bool:
        """Mark session as failed"""
        session = self._find_session(session_id)
        if not session:
            return False
        
        session["status"] = "failed"
        session["failure_reason"] = reason
        session["progress"]["end_time"] = datetime.now().isoformat()
        
        if self.sessions["session_tracking"]["current_session"] == session_id:
            self.sessions["session_tracking"]["current_session"] = None
        
        self._save_sessions()
        self._log_event("session_failed", session_id, {"reason": reason})
        
        return True
    
    def recover_session(self, session_id: str) -> Optional[Dict]:
        """Recover a paused or interrupted session"""
        session = self._find_session(session_id)
        if not session or session["status"] not in ["active", "paused"]:
            return None
        
        session["status"] = "active"
        session["progress"]["recovery_time"] = datetime.now().isoformat()
        self.sessions["session_tracking"]["current_session"] = session_id
        
        self._save_sessions()
        self._log_event("session_recovered", session_id, {})
        
        return session
    
    def pause_session(self, session_id: str) -> bool:
        """Pause an active session for later resumption"""
        session = self._find_session(session_id)
        if not session or session["status"] != "active":
            return False
        
        session["status"] = "paused"
        session["progress"]["pause_time"] = datetime.now().isoformat()
        
        if self.sessions["session_tracking"]["current_session"] == session_id:
            self.sessions["session_tracking"]["current_session"] = None
        
        self._save_sessions()
        self._log_event("session_paused", session_id, {})
        
        return True
    
    def get_current_session(self) -> Optional[Dict]:
        """Get the currently active session"""
        session_id = self.sessions["session_tracking"]["current_session"]
        if session_id:
            return self._find_session(session_id)
        return None
    
    def cleanup_old_sessions(self, retention_days: int = 90) -> int:
        """Archive old completed sessions"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        archived_count = 0
        
        for session in self.sessions["session_tracking"]["session_history"][:]:
            session_date = datetime.fromisoformat(session["timestamp"])
            if session_date < cutoff_date and session["status"] == "completed":
                # Archive the session
                self._archive_session(session)
                self.sessions["session_tracking"]["session_history"].remove(session)
                archived_count += 1
        
        if archived_count > 0:
            self._save_sessions()
            self._log_event("cleanup_performed", None, {"archived": archived_count})
        
        return archived_count
    
    # Helper methods
    def _find_session(self, session_id: str) -> Optional[Dict]:
        """Find a session by ID"""
        for session in self.sessions["session_tracking"]["session_history"]:
            if session["session_id"] == session_id:
                return session
        return None
    
    def _estimate_completion(self, lane: str) -> str:
        """Estimate completion time based on lane"""
        if lane == "standard":
            completion = datetime.now() + timedelta(hours=1)
        else:
            completion = datetime.now() + timedelta(hours=8)
        return completion.isoformat()
    
    def _init_artifact_files(self, session_dir: Path):
        """Initialize empty artifact files"""
        files = {
            "excerpts.json": {"excerpts": []},
            "claims.json": {"claims": []},
            "citations.json": {"citations": []},
            "notes.md": f"# Research Notes\\n\\nSession: {session_dir.name}\\n\\n",
            "quality_scores.json": {"overall_score": 0.0, "metrics": {}}
        }
        
        for filename, content in files.items():
            filepath = session_dir / filename
            if filename.endswith('.md'):
                filepath.write_text(content)
            else:
                with open(filepath, 'w') as f:
                    json.dump(content, f, indent=2)
    
    def _save_artifacts(self, session_id: str, artifacts: Dict[str, Any]):
        """Save artifacts to session directory"""
        session_dir = self.artifacts_root / session_id
        
        for artifact_type, data in artifacts.items():
            filepath = session_dir / f"{artifact_type}.json"
            if filepath.exists():
                with open(filepath, 'r') as f:
                    existing = json.load(f)
                if isinstance(existing, dict) and isinstance(data, dict):
                    existing.update(data)
                elif isinstance(existing, list) and isinstance(data, list):
                    existing.extend(data)
                data = existing
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
    
    def _update_index(self, session: Dict):
        """Update research index with completed session"""
        category = session.get("template_used", "unknown").replace(".md", "").split("/")[-1]
        
        index_entry = {
            "id": session["session_id"],
            "title": session["research_topic"],
            "type": category,
            "date_created": session["timestamp"],
            "date_completed": session["progress"].get("end_time"),
            "quality_score": session["progress"]["quality_score"],
            "source_count": session["progress"]["sources_gathered"],
            "artifact_path": str(self.artifacts_root / session["session_id"]),
            "capsule_associations": session.get("capsule_links", []),
            "decision_links": session.get("decision_links", []),
            "status": "completed",
            "tags": session.get("tags", [])
        }
        
        if category not in self.index["research_index"]["categories"]:
            self.index["research_index"]["categories"][category] = []
        
        self.index["research_index"]["categories"][category].append(index_entry)
        self.index["research_index"]["total_research_items"] += 1
        self.index["research_index"]["last_updated"] = datetime.now().isoformat()
    
    def _archive_session(self, session: Dict):
        """Archive a session to long-term storage"""
        archive_dir = self.base_path / "research" / "archives" / session["session_id"]
        session_dir = self.artifacts_root / session["session_id"]
        
        if session_dir.exists():
            shutil.move(str(session_dir), str(archive_dir))
    
    def _save_sessions(self):
        """Persist session state to file"""
        with open(self.sessions_file, 'w') as f:
            json.dump(self.sessions, f, indent=2)
    
    def _save_index(self):
        """Persist research index to file"""
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)
    
    def _log_event(self, event_type: str, session_id: Optional[str], data: Dict):
        """Log research events"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "session_id": session_id,
            "data": data
        }
        
        log_file = self.logs_dir / "events.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + "\\n")


if __name__ == "__main__":
    # Test the session manager
    manager = ResearchSessionManager()
    
    # Start a test session
    session_id = manager.start_session(
        topic="test-framework-analysis",
        lane="standard",
        template="technical-analysis",
        requestor="test",
        priority="low"
    )
    
    print(f"Started session: {session_id}")
    
    # Update progress
    manager.update_session(session_id, {
        "progress": {
            "search_iterations": 1,
            "sources_gathered": 3
        },
        "checkpoint": True,
        "checkpoint_note": "Initial search completed"
    })
    
    print(f"Updated session progress")
    
    # Complete session
    manager.complete_session(session_id, 0.85, {
        "key_findings": ["Framework is suitable", "Performance meets requirements"],
        "recommendations": ["Proceed with implementation"]
    })
    
    print(f"Completed session with quality score: 0.85")