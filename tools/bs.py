#!/usr/bin/env python3
"""
Huxley Capsule Versioning & History Tool (bs.py)
Zero dependencies, offline, idempotent capsule lifecycle management.
"""

import argparse
import datetime
import fnmatch
import json
import os
import pathlib
import shutil
import subprocess
import sys
import textwrap
from typing import List, Optional, Dict, Any


class CapsuleVersioner:
    """Local versioning system for Huxley capsules"""
    
    def __init__(self, capsule_root: pathlib.Path = None):
        self.root = pathlib.Path(capsule_root or pathlib.Path.cwd())
        self.capsule_name = self.root.name
        self.versions_dir = self.root / "versions"
        self.tools_dir = self.root / "tools"
        self.docs_dir = self.root / "docs"
        self.scripts_dir = self.root / "scripts"
        
        # Core files
        self.bsignore_file = self.root / ".bsignore"
        self.changelog_file = self.root / "changelog.md"
        self.decision_journal_file = self.root / "decision_journal.md"
        self.maintenance_log_file = self.root / "maintenance_log.md"
        
        # Doc templates
        self.prd_file = self.docs_dir / "prd.md"
        self.dod_file = self.docs_dir / "dod.md"
        self.ops_baseline_file = self.docs_dir / "ops_baseline.md"
        
        # Scripts
        self.post_checkpoint_script = self.scripts_dir / "post_checkpoint.sh"
        
        # Configuration from environment
        self.retain_count = int(os.getenv('BS_RETAIN_COUNT', 10))
        self.retain_days = int(os.getenv('BS_RETAIN_DAYS', 30))
        self.no_auto_cleanup = os.getenv('BS_NO_AUTO_CLEANUP', '').lower() in ('1', 'true', 'yes')
        
        # Always ignore these patterns (hardcoded security)
        self.hardcoded_ignores = [
            '.git/',
            'versions/',
            'node_modules/',
            '__pycache__/',
            '.DS_Store',
            '.env',
            '.env.*',
            'secrets.*',
            '*.key',
            '*.pem'
        ]
    
    def print_message(self, message: str, level: str = "info"):
        """Print formatted message"""
        prefix = {
            "info": "ℹ️ ",
            "success": "✅ ",
            "warning": "⚠️ ",
            "error": "❌ "
        }.get(level, "")
        print(f"{prefix}{message}")
    
    def is_git_repo(self) -> bool:
        """Check if current directory is a git repository"""
        return (self.root / ".git").exists()
    
    def run_git_command(self, cmd: List[str], capture_output: bool = True) -> Optional[str]:
        """Run git command safely, return output or None on failure"""
        try:
            result = subprocess.run(
                ["git"] + cmd,
                cwd=self.root,
                capture_output=capture_output,
                text=True,
                check=True
            )
            return result.stdout.strip() if capture_output else None
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.print_message(f"Git command failed: {e}", "warning")
            return None
    
    def load_ignore_patterns(self) -> List[str]:
        """Load ignore patterns from .bsignore and hardcoded list"""
        patterns = self.hardcoded_ignores.copy()
        
        if self.bsignore_file.exists():
            try:
                with open(self.bsignore_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            patterns.append(line)
            except Exception as e:
                self.print_message(f"Error reading .bsignore: {e}", "warning")
        
        return patterns
    
    def should_ignore(self, file_path: pathlib.Path, patterns: List[str]) -> bool:
        """Check if file should be ignored based on patterns"""
        relative_path = str(file_path.relative_to(self.root))
        
        for pattern in patterns:
            # Direct match
            if fnmatch.fnmatch(relative_path, pattern):
                return True
            # Directory match
            if pattern.endswith('/') and relative_path.startswith(pattern):
                return True
            # Basename match
            if fnmatch.fnmatch(file_path.name, pattern):
                return True
        
        return False
    
    def create_snapshot_name(self, label: Optional[str] = None) -> str:
        """Generate snapshot directory name"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if label:
            # Sanitize label for filesystem
            clean_label = "".join(c for c in label if c.isalnum() or c in ".-_")
            return f"{timestamp}_{clean_label}"
        return timestamp
    
    def get_author_name(self) -> str:
        """Get author name from git or default to {{USER_NAME}}"""
        if self.is_git_repo():
            name = self.run_git_command(["config", "user.name"])
            if name:
                return name
        return "{{USER_NAME}}"
    
    def auto_cleanup_snapshots(self):
        """Automatically clean up old snapshots based on retention policy"""
        if self.no_auto_cleanup:
            return
        
        if not self.versions_dir.exists():
            return
        
        # Get all snapshots sorted by creation time
        snapshots = []
        for item in self.versions_dir.iterdir():
            if item.is_dir():
                stat = item.stat()
                is_tagged = "_v" in item.name or any(
                    c in item.name for c in "vV" if item.name.count(c) == 1
                )
                snapshots.append({
                    'path': item,
                    'name': item.name,
                    'mtime': stat.st_mtime,
                    'is_tagged': is_tagged
                })
        
        # Sort by modification time (newest first)
        snapshots.sort(key=lambda x: x['mtime'], reverse=True)
        
        # Separate tagged from untagged
        tagged_snapshots = [s for s in snapshots if s['is_tagged']]
        untagged_snapshots = [s for s in snapshots if not s['is_tagged']]
        
        # Keep recent untagged snapshots
        cutoff_time = datetime.datetime.now().timestamp() - (self.retain_days * 24 * 3600)
        
        to_keep = []
        to_remove = []
        
        # Always keep tagged snapshots
        to_keep.extend(tagged_snapshots)
        
        # Keep recent untagged by count and time
        for i, snapshot in enumerate(untagged_snapshots):
            if i < self.retain_count or snapshot['mtime'] > cutoff_time:
                to_keep.append(snapshot)
            else:
                to_remove.append(snapshot)
        
        # Safety check - never leave less than 3 snapshots
        if len(to_keep) < 3 and len(snapshots) >= 3:
            needed = 3 - len(to_keep)
            rescued = to_remove[:needed]
            to_keep.extend(rescued)
            to_remove = to_remove[needed:]
        
        # Remove old snapshots
        removed_count = 0
        for snapshot in to_remove:
            try:
                shutil.rmtree(snapshot['path'])
                removed_count += 1
            except Exception as e:
                self.print_message(f"Failed to remove {snapshot['name']}: {e}", "warning")
        
        if removed_count > 0:
            kept_tagged = len(tagged_snapshots)
            kept_recent = len([s for s in to_keep if not s['is_tagged']])
            self.print_message(
                f"Cleaned up {removed_count} old snapshots, kept {len(to_keep)} "
                f"({kept_tagged} tagged, {kept_recent} recent)", 
                "info"
            )
    
    def init_command(self):
        """Initialize capsule versioning structure"""
        self.print_message(f"Initializing versioning for capsule: {self.capsule_name}")
        
        # Create directories
        dirs_to_create = [self.versions_dir, self.tools_dir, self.docs_dir, self.scripts_dir]
        for dir_path in dirs_to_create:
            dir_path.mkdir(exist_ok=True)
        
        # Create .gitkeep for versions directory
        gitkeep_file = self.versions_dir / ".gitkeep"
        if not gitkeep_file.exists():
            gitkeep_file.touch()
        
        # Create __init__.py for tools
        init_file = self.tools_dir / "__init__.py"
        if not init_file.exists():
            init_file.touch()
        
        # Create .bsignore with defaults
        if not self.bsignore_file.exists():
            bsignore_content = """# Build artifacts
dist/
build/
*.log
*.cache
*.tmp

# Data & large assets
data/raw/
data/tmp/
*.mp4
*.mov
*.zip

# Secrets & local configs (defense in depth)
.env
.env.*
secrets.*
*.pem
*.key

# VCS & system
.git/
.DS_Store
__pycache__/
versions/

# Automatic cleanup: keeps last 10 checkpoints + tagged versions forever
# Override with: BS_RETAIN_DAYS=60 or BS_RETAIN_COUNT=20
"""
            with open(self.bsignore_file, 'w') as f:
                f.write(bsignore_content)
            self.print_message("Created .bsignore with sensible defaults")
        
        # Create markdown files (only if missing)
        markdown_files = {
            self.changelog_file: "# Changelog\n\n",
            self.decision_journal_file: "# Decision Journal\n\n",
            self.maintenance_log_file: "# Maintenance Log\n\n"
        }
        
        for file_path, content in markdown_files.items():
            if not file_path.exists():
                with open(file_path, 'w') as f:
                    f.write(content)
                self.print_message(f"Created {file_path.name}")
        
        # Create doc templates (only if missing)
        if not self.prd_file.exists():
            prd_content = f"""# Product Requirements (PRD)

**Capsule:** {self.capsule_name}  
**Problem:**  
**Objectives (ranked):**  
1.  
2.  

**Users/Stakeholders:**  
**Success Metrics:**  
**Scope (in):**  
**Out of Scope:**  
**Constraints/Assumptions:**  
**Dependencies:**  
**Risks & Mitigations:**  
**Milestones:**  
"""
            with open(self.prd_file, 'w') as f:
                f.write(prd_content)
            self.print_message("Created docs/prd.md template")
        
        if not self.dod_file.exists():
            dod_content = """# Definition of Done (DoD)

## standard DoD (if applicable)
- Working end-to-end demo
- Minimal docs in README
- Decision logged in decision_journal.md

## standard DoD (if applicable)
- Tests pass & basic CI plan (even if manual)
- Docs: PRD complete, ops_baseline set
- Rollout plan & rollback noted

## Evidence checklist
- Links to outputs/artifacts
- Screenshots or logs

## Sign-off
- Approver: {{USER_NAME}} or Number-2 agent
- Date:
"""
            with open(self.dod_file, 'w') as f:
                f.write(dod_content)
            self.print_message("Created docs/dod.md template")
        
        if not self.ops_baseline_file.exists():
            ops_content = """# Operational Baseline

**Uptime/Run cadence:**  
**Error budget / failure thresholds:**  
**Maintenance triggers:** (e.g., upstream API changes, failure rate >2%/7 days)  
**Improvement triggers:** (e.g., >15% efficiency gain possible)  
**Review cadence:** (e.g., quarterly)  
**Monitoring/logs location:**  
"""
            with open(self.ops_baseline_file, 'w') as f:
                f.write(ops_content)
            self.print_message("Created docs/ops_baseline.md template")
        
        # Create post-checkpoint hook
        if not self.post_checkpoint_script.exists():
            hook_content = """#!/usr/bin/env bash
# no-op hook; user can add notifications or local backups here
exit 0
"""
            with open(self.post_checkpoint_script, 'w') as f:
                f.write(hook_content)
            self.post_checkpoint_script.chmod(0o755)
            self.print_message("Created scripts/post_checkpoint.sh hook")
        
        # Create README
        readme_file = self.root / "README_VERSIONING.md"
        if not readme_file.exists():
            readme_content = """# Capsule Versioning System

Quick reference for the local versioning system in this capsule.

## Common Commands

Initialize versioning (run once):
```bash
python tools/bs.py init
```

Save a checkpoint:
```bash
python tools/bs.py checkpoint --why "initial working demo" --level minor --label v0.2.0
```

See differences (if git available):
```bash
python tools/bs.py diff
```

Restore from a snapshot (dry run first):
```bash
python tools/bs.py restore --snapshot versions/20250814_150312_v0.2.0 --dry-run
python tools/bs.py restore --snapshot versions/20250814_150312_v0.2.0
```

Check status:
```bash
python tools/bs.py status
```

## Configuration

Environment variables (set in .env.local):
- `BS_RETAIN_COUNT=10` - Keep last N checkpoints
- `BS_RETAIN_DAYS=30` - Keep checkpoints from last N days  
- `BS_NO_AUTO_CLEANUP=1` - Disable automatic cleanup

## Files

- `.bsignore` - Patterns to exclude from snapshots
- `changelog.md` - Human-readable change log
- `decision_journal.md` - Decision reasoning and outcomes
- `maintenance_log.md` - Operational health entries
- `versions/` - Immutable snapshots (auto-cleaned)
- `scripts/post_checkpoint.sh` - Custom hook after checkpoint
"""
            with open(readme_file, 'w') as f:
                f.write(readme_content)
            self.print_message("Created README_VERSIONING.md")
        
        self.print_message("Initialization complete", "success")
    
    def checkpoint_command(self, why: str, level: str = "patch", label: Optional[str] = None):
        """Create a checkpoint snapshot"""
        if not why.strip():
            self.print_message("--why description is required", "error")
            sys.exit(1)
        
        # Create snapshot directory
        snapshot_name = self.create_snapshot_name(label)
        snapshot_dir = self.versions_dir / snapshot_name
        
        if snapshot_dir.exists():
            self.print_message(f"Snapshot {snapshot_name} already exists", "error")
            sys.exit(1)
        
        self.print_message(f"Creating checkpoint: {snapshot_name}")
        
        # Load ignore patterns
        ignore_patterns = self.load_ignore_patterns()
        
        # Create snapshot directory
        snapshot_dir.mkdir(parents=True)
        
        # Copy files (excluding ignored patterns)
        copied_files = 0
        skipped_files = 0
        
        for file_path in self.root.rglob("*"):
            if file_path.is_file():
                try:
                    if self.should_ignore(file_path, ignore_patterns):
                        skipped_files += 1
                        continue
                    
                    # Calculate relative path and create target
                    relative_path = file_path.relative_to(self.root)
                    target_path = snapshot_dir / relative_path
                    
                    # Ensure parent directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file with metadata
                    shutil.copy2(file_path, target_path)
                    copied_files += 1
                    
                except Exception as e:
                    self.print_message(f"Failed to copy {file_path}: {e}", "warning")
                    skipped_files += 1
        
        self.print_message(f"Copied {copied_files} files, skipped {skipped_files}", "info")
        
        # Update changelog
        author = self.get_author_name()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        changelog_entry = f"- {timestamp} [level: {level}] [label: {label or snapshot_name}] — WHY: {why} — BY: {author}\n"
        
        with open(self.changelog_file, 'a') as f:
            f.write(changelog_entry)
        
        # Update decision journal
        decision_entry = f"""## {timestamp} {label or snapshot_name}
**Context:**  
**Options considered (min 2):**  
**Choice & rationale:** {why}
**Predicted risks:**  
**Result (fill on next checkpoint):**  

"""
        
        with open(self.decision_journal_file, 'a') as f:
            f.write(decision_entry)
        
        # Git operations (if available)
        if self.is_git_repo():
            # Stage all changes
            if self.run_git_command(["add", "-A"], capture_output=False) is not None:
                # Commit
                commit_message = f"[checkpoint] {label or snapshot_name}: {why}"
                if self.run_git_command(["commit", "-m", commit_message], capture_output=False) is not None:
                    self.print_message("Created git commit", "success")
                    
                    # Create tag if label provided
                    if label:
                        tag_message = f"Checkpoint: {why}"
                        if self.run_git_command(["tag", "-a", label, "-m", tag_message], capture_output=False) is not None:
                            self.print_message(f"Created git tag: {label}", "success")
        
        # Run post-checkpoint hook
        if self.post_checkpoint_script.exists() and self.post_checkpoint_script.is_file():
            try:
                subprocess.run([str(self.post_checkpoint_script)], 
                             cwd=self.root, 
                             check=False,  # Don't fail on hook errors
                             capture_output=True)
            except Exception as e:
                self.print_message(f"Post-checkpoint hook warning: {e}", "warning")
        
        # Auto-cleanup old snapshots
        self.auto_cleanup_snapshots()
        
        self.print_message(f"Checkpoint created: {snapshot_name}", "success")
    
    def diff_command(self, since: Optional[str] = None):
        """Show diff of changes"""
        if not self.is_git_repo():
            self.print_message("Git not available; diff unsupported", "warning")
            return
        
        cmd = ["diff"]
        if since:
            cmd.extend([since, "HEAD"])
        else:
            cmd.append("HEAD~1")
        
        # Run git diff and print output directly
        try:
            subprocess.run(["git"] + cmd, cwd=self.root, check=True)
        except subprocess.CalledProcessError:
            self.print_message("No differences found or git diff failed", "info")
    
    def tag_command(self, label: str, why: str):
        """Create a git tag and update changelog"""
        if not self.is_git_repo():
            self.print_message("Git not available; cannot create tag", "error")
            sys.exit(1)
        
        if not why.strip():
            self.print_message("--why description is required", "error")
            sys.exit(1)
        
        # Create git tag
        tag_message = f"Tag: {why}"
        if self.run_git_command(["tag", "-a", label, "-m", tag_message], capture_output=False) is not None:
            # Update changelog
            author = self.get_author_name()
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            changelog_entry = f"- {timestamp} [level: tag] [label: {label}] — WHY: {why} — BY: {author}\n"
            
            with open(self.changelog_file, 'a') as f:
                f.write(changelog_entry)
            
            self.print_message(f"Created tag: {label}", "success")
        else:
            self.print_message("Failed to create tag", "error")
            sys.exit(1)
    
    def restore_command(self, snapshot: str, dry_run: bool = False):
        """Restore files from a snapshot"""
        snapshot_path = pathlib.Path(snapshot)
        if not snapshot_path.is_absolute():
            snapshot_path = self.root / snapshot_path
        
        if not snapshot_path.exists() or not snapshot_path.is_dir():
            self.print_message(f"Snapshot not found: {snapshot}", "error")
            sys.exit(1)
        
        # Load ignore patterns for safety
        ignore_patterns = self.load_ignore_patterns()
        
        # Collect files to restore
        files_to_restore = []
        files_to_skip = []
        
        for file_path in snapshot_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(snapshot_path)
                target_path = self.root / relative_path
                
                # Check if we should skip this file during restore
                if self.should_ignore(self.root / relative_path, ignore_patterns):
                    files_to_skip.append(str(relative_path))
                else:
                    files_to_restore.append((file_path, target_path, relative_path))
        
        if dry_run:
            self.print_message(f"Would restore {len(files_to_restore)} files:", "info")
            for _, _, rel_path in files_to_restore[:10]:  # Show first 10
                print(f"  {rel_path}")
            if len(files_to_restore) > 10:
                print(f"  ... and {len(files_to_restore) - 10} more")
            
            if files_to_skip:
                self.print_message(f"Would skip {len(files_to_skip)} sensitive/ignored files", "warning")
            return
        
        # Actually restore files
        restored_count = 0
        for source_path, target_path, rel_path in files_to_restore:
            try:
                # Ensure parent directory exists
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                shutil.copy2(source_path, target_path)
                print(f"  Restored: {rel_path}")
                restored_count += 1
                
            except Exception as e:
                self.print_message(f"Failed to restore {rel_path}: {e}", "warning")
        
        # Print skip summary
        for skipped in files_to_skip:
            print(f"  Skipped: {skipped} (sensitive/ignored)")
        
        self.print_message(f"Restore complete: {restored_count} files restored, {len(files_to_skip)} skipped", "success")
    
    def verify_command(self):
        """Run sanity checks on versioning setup"""
        issues = []
        
        # Check required directories
        required_dirs = [self.versions_dir, self.tools_dir, self.docs_dir]
        for dir_path in required_dirs:
            if not dir_path.exists():
                issues.append(f"Missing directory: {dir_path}")
        
        # Check required files
        required_files = [self.bsignore_file, self.changelog_file]
        for file_path in required_files:
            if not file_path.exists():
                issues.append(f"Missing file: {file_path}")
        
        # Test ignore patterns
        try:
            self.load_ignore_patterns()
        except Exception as e:
            issues.append(f"Invalid ignore patterns: {e}")
        
        # Check versions directory is writable
        if self.versions_dir.exists():
            try:
                test_file = self.versions_dir / ".write_test"
                test_file.touch()
                test_file.unlink()
            except Exception as e:
                issues.append(f"Versions directory not writable: {e}")
        
        if issues:
            self.print_message("Verification failed:", "error")
            for issue in issues:
                print(f"  ❌ {issue}")
            sys.exit(1)
        else:
            self.print_message("All checks passed", "success")
    
    def status_command(self):
        """Show current capsule status"""
        self.print_message(f"Capsule: {self.capsule_name}", "info")
        
        # Latest checkpoint
        if self.versions_dir.exists():
            snapshots = [d for d in self.versions_dir.iterdir() if d.is_dir()]
            if snapshots:
                latest = max(snapshots, key=lambda x: x.stat().st_mtime)
                self.print_message(f"Latest checkpoint: {latest.name}")
            else:
                self.print_message("No checkpoints found")
        else:
            self.print_message("Versioning not initialized")
        
        # Git status
        if self.is_git_repo():
            status_output = self.run_git_command(["status", "--porcelain"])
            if status_output:
                changed_files = len(status_output.strip().split('\n'))
                self.print_message(f"Pending changes: {changed_files} files")
            else:
                self.print_message("No pending changes")
        else:
            self.print_message("Not a git repository")
        
        # TODO count in docs
        todo_count = 0
        for doc_file in self.docs_dir.glob("*.md"):
            if doc_file.exists():
                try:
                    with open(doc_file, 'r') as f:
                        content = f.read()
                        todo_count += content.lower().count('todo')
                        todo_count += content.count('TODO')
                except Exception:
                    pass
        
        if todo_count > 0:
            self.print_message(f"Unresolved TODOs: {todo_count}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Huxley Capsule Versioning",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # init command
    init_parser = subparsers.add_parser('init', help='Initialize versioning structure')
    
    # checkpoint command
    checkpoint_parser = subparsers.add_parser('checkpoint', help='Create a checkpoint')
    checkpoint_parser.add_argument('--why', required=True, help='Description of changes')
    checkpoint_parser.add_argument('--level', choices=['patch', 'minor', 'major'], 
                                 default='patch', help='Change level')
    checkpoint_parser.add_argument('--label', help='Optional version label (e.g., v1.0.0)')
    
    # diff command
    diff_parser = subparsers.add_parser('diff', help='Show differences')
    diff_parser.add_argument('--since', help='Show diff since tag or commit')
    
    # tag command
    tag_parser = subparsers.add_parser('tag', help='Create a git tag')
    tag_parser.add_argument('--label', required=True, help='Tag name')
    tag_parser.add_argument('--why', required=True, help='Tag description')
    
    # restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from snapshot')
    restore_parser.add_argument('--snapshot', required=True, help='Snapshot directory name')
    restore_parser.add_argument('--dry-run', action='store_true', help='Show what would be restored')
    
    # verify command
    verify_parser = subparsers.add_parser('verify', help='Verify system integrity')
    
    # status command
    status_parser = subparsers.add_parser('status', help='Show current status')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize versioner
    versioner = CapsuleVersioner()
    
    # Dispatch commands
    try:
        if args.command == 'init':
            versioner.init_command()
        elif args.command == 'checkpoint':
            versioner.checkpoint_command(args.why, args.level, args.label)
        elif args.command == 'diff':
            versioner.diff_command(args.since)
        elif args.command == 'tag':
            versioner.tag_command(args.label, args.why)
        elif args.command == 'restore':
            versioner.restore_command(args.snapshot, args.dry_run)
        elif args.command == 'verify':
            versioner.verify_command()
        elif args.command == 'status':
            versioner.status_command()
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        versioner.print_message(f"Unexpected error: {e}", "error")
        sys.exit(1)


if __name__ == "__main__":
    main()