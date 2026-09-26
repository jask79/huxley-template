#!/usr/bin/env python3
"""
Huxley Inbox Sync - Automated capsule import from iCloud

Shortcut-mode JSON schema for iOS integration:
{
  "slug": "kebab-case",
  "files": [
    {"path":"spec/requirements.yaml","content":"<yaml>"},
    {"path":"spec/system.md","content":"<md>"},
    {"path":"spec/test_plan.md","content":"<md>"},
    {"path":"spec/context.jsonl","content":"<jsonl>"},
    {"path":"spec/market_validation.md","content":"<md, optional>"}
  ]
}
"""

import argparse
import json
import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class HuxleyInboxSync:
    def __init__(self, dry_run=False, verbose=False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.catalyst_root = Path("{{CATALYST_ROOT}}")
        self.inbox_path = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Huxley Inbox"
        self.capsules_path = self.catalyst_root / "capsules"
        self.registry_path = self.catalyst_root / "registry"
        self.tools_path = self.catalyst_root / "tools"
        
        # Ensure directories exist
        for path in [self.catalyst_root, self.capsules_path, self.registry_path, self.tools_path]:
            path.mkdir(exist_ok=True)
        for subdir in ["recipes", "sandbox"]:
            (self.catalyst_root / subdir).mkdir(exist_ok=True)
        
        self.inbox_path.mkdir(exist_ok=True)
        (self.inbox_path / "Processed").mkdir(exist_ok=True)
        
        # Setup logging
        log_file = self.registry_path / "inbox-sync.log"
        log_level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='[%(asctime)s] %(levelname)s %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        if self.dry_run:
            self.logger.info("DRY RUN MODE: No files will be moved or modified")

    def is_icloud_placeholder(self, file_path: Path) -> bool:
        """Check if file is an iCloud placeholder (.icloud file or zero-length temp)"""
        if not file_path.exists():
            return False
        
        # Check for .icloud extension
        if file_path.name.endswith('.icloud'):
            return True
        
        # Check for zero-length files that might be syncing
        try:
            if file_path.stat().st_size == 0:
                return True
        except OSError:
            return True
        
        return False

    def has_icloud_placeholders(self, spec_path: Path) -> bool:
        """Check if any files in spec directory are iCloud placeholders"""
        if not spec_path.exists():
            return False
        
        for file_path in spec_path.rglob("*"):
            if file_path.is_file() and self.is_icloud_placeholder(file_path):
                return True
        return False

    def compute_spec_hash(self, spec_path: Path) -> str:
        """Compute SHA256 hash of all spec files concatenated"""
        if not spec_path.exists():
            return ""
        
        hasher = hashlib.sha256()
        spec_files = sorted(spec_path.rglob("*"))
        
        for file_path in spec_files:
            if file_path.is_file() and not self.is_icloud_placeholder(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        hasher.update(file_path.relative_to(spec_path).as_posix().encode())
                        hasher.update(f.read())
                except Exception as e:
                    self.logger.warning(f"Could not read {file_path} for hash: {e}")
        
        return hasher.hexdigest()

    def validate_spec_structure(self, spec_path: Path) -> bool:
        """Validate that spec directory contains required requirements.yaml"""
        requirements_file = spec_path / "requirements.yaml"
        return requirements_file.exists() and not self.is_icloud_placeholder(requirements_file)

    def detect_lane(self, spec_path: Path) -> str:
        """Detect lane from spec/requirements.yaml; returns lane string or ''."""
        req = spec_path / "requirements.yaml"
        if not req.exists():
            return ""
        text = ""
        try:
            text = req.read_text(encoding="utf-8")
        except Exception:
            return ""
        # Try quick regex parse for 'lane: value'
        m = re.search(r"^\s*lane\s*:\s*([A-Za-z0-9_\-]+)\s*$", text, re.MULTILINE)
        if m:
            return m.group(1)
        # Try nested under project.lane
        m = re.search(r"^\s*project:\s*(?:\n|\r\n)([\s\S]*?)^(\S|$)", text, re.MULTILINE)
        if m:
            proj = m.group(1)
            m2 = re.search(r"^\s*lane\s*:\s*([A-Za-z0-9_\-]+)\s*$", proj, re.MULTILINE)
            if m2:
                return m2.group(1)
        return ""

    def validate_lane(self, lane: str) -> bool:
        """Return True if lane is allowed."""
        return lane in {"standard", "standard"}

    def process_json_drop(self, json_file: Path, slug: str) -> bool:
        """Process a JSON drop file and materialize spec files"""
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            if data.get('slug') != slug:
                self.logger.warning(f"slug={slug} msg=JSON slug mismatch: {data.get('slug')}")
                return False
            
            spec_dir = json_file.parent / "spec"
            spec_dir.mkdir(exist_ok=True)
            
            for file_info in data.get('files', []):
                file_path = spec_dir / file_info['path'].replace('spec/', '')
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(file_info['content'])
            
            self.logger.info(f"slug={slug} msg=Materialized {len(data.get('files', []))} files from JSON")
            return True
            
        except Exception as e:
            self.logger.error(f"slug={slug} msg=Failed to process JSON drop: {e}")
            return False

    def create_capsule_skeleton(self, slug: str):
        """Create capsule directory structure if it doesn't exist"""
        capsule_path = self.capsules_path / slug
        
        for subdir in ["spec", "src", "runs", "docs", "ops"]:
            (capsule_path / subdir).mkdir(parents=True, exist_ok=True)

    def update_registry(self, slug: str, source: str, files: List[str], status: str, spec_hash: str = ""):
        """Update the imported.json registry file atomically"""
        registry_file = self.registry_path / "imported.json"
        
        # Load existing registry
        registry = {}
        if registry_file.exists():
            try:
                with open(registry_file, 'r') as f:
                    registry = json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load registry: {e}")
        
        # Update entry
        registry[slug] = {
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "files": files,
            "hash": spec_hash,
            "status": status
        }
        
        # Atomic write
        temp_file = registry_file.with_suffix('.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(registry, f, indent=2)
            temp_file.replace(registry_file)
        except Exception as e:
            self.logger.error(f"Failed to update registry: {e}")
            if temp_file.exists():
                temp_file.unlink()

    def run_capsule_hook(self, capsule_path: Path):
        """Run optional capsule creation hook"""
        hook_script = self.tools_path / "on_capsule_created.sh"
        if hook_script.exists() and hook_script.is_file():
            try:
                result = subprocess.run([str(hook_script), str(capsule_path)], 
                                     check=False, timeout=30, capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info(f"Hook script completed successfully for {capsule_path.name}")
                else:
                    self.logger.warning(f"Hook script returned {result.returncode}: {result.stderr.strip()}")
            except Exception as e:
                self.logger.warning(f"Hook script failed: {e}")

    def process_zip_file(self, zip_path: Path, slug: str) -> bool:
        """Process a ZIP file containing spec data"""
        try:
            # Check if ZIP is fully downloaded (not a placeholder)
            if self.is_icloud_placeholder(zip_path):
                self.logger.info(f"slug={slug} msg=ZIP still downloading, skipping")
                return False
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Extract ZIP
                with zipfile.ZipFile(zip_path, 'r') as zip_file:
                    zip_file.extractall(temp_path)
                
                # Look for spec directory
                spec_path = temp_path / "spec"
                if not spec_path.exists():
                    self.logger.error(f"slug={slug} msg=ZIP missing spec/ directory")
                    return False
                
                if not self.validate_spec_structure(spec_path):
                    self.logger.error(f"slug={slug} msg=ZIP spec/ missing requirements.yaml")
                    return False
                
                return self.import_spec(slug, spec_path, f"zip:{zip_path.name}")
                
        except Exception as e:
            self.logger.error(f"slug={slug} msg=Failed to process ZIP: {e}")
            return False

    def process_folder(self, folder_path: Path, slug: str) -> bool:
        """Process a folder containing spec data"""
        # Check for JSON drop first
        json_file = folder_path / f"{slug}.json"
        if json_file.exists():
            if not self.process_json_drop(json_file, slug):
                return False
        
        spec_path = folder_path / "spec"
        if not spec_path.exists():
            self.logger.error(f"slug={slug} msg=Folder missing spec/ directory")
            return False
        
        # Check for iCloud placeholders
        if self.has_icloud_placeholders(spec_path):
            self.logger.info(f"slug={slug} msg=Skipping due to iCloud placeholders")
            return False
        
        if not self.validate_spec_structure(spec_path):
            self.logger.error(f"slug={slug} msg=Folder spec/ missing requirements.yaml")
            return False

        # Lane/schema validation (non-destructive): invalid lane -> ERROR and skip
        lane = self.detect_lane(spec_path)
        if lane and not self.validate_lane(lane):
            self.logger.error(f"slug={slug} msg=Invalid lane '{lane}' in requirements.yaml; expected one of standard, standard")
            try:
                self.update_registry(slug, f"folder:{folder_path.name}", [], "error")
            except Exception:
                pass
            return False
        
        return self.import_spec(slug, spec_path, f"folder:{folder_path.name}")

    def import_spec(self, slug: str, spec_path: Path, source: str) -> bool:
        """Import spec files into capsule"""
        try:
            if self.dry_run:
                self.logger.info(f"slug={slug} msg=DRY RUN: Would import from {source}")
                
                # Still compute hashes for comparison
                new_hash = self.compute_spec_hash(spec_path)
                dest_spec_path = self.capsules_path / slug / "spec"
                current_hash = self.compute_spec_hash(dest_spec_path) if dest_spec_path.exists() else ""
                
                if current_hash == new_hash and current_hash != "":
                    self.logger.info(f"slug={slug} msg=DRY RUN: No changes detected, would skip import")
                else:
                    spec_files = [str(f.relative_to(spec_path)) for f in spec_path.rglob("*") if f.is_file()]
                    self.logger.info(f"slug={slug} msg=DRY RUN: Would import {len(spec_files)} files")
                    if self.verbose:
                        for file_path in spec_files:
                            self.logger.debug(f"slug={slug} msg=DRY RUN: Would import {file_path}")
                
                return True
            
            # Create capsule skeleton
            self.create_capsule_skeleton(slug)
            
            dest_spec_path = self.capsules_path / slug / "spec"
            
            # Compute hashes for idempotency
            new_hash = self.compute_spec_hash(spec_path)
            current_hash = self.compute_spec_hash(dest_spec_path)
            
            if current_hash == new_hash and current_hash != "":
                self.logger.info(f"slug={slug} msg=No changes detected, skipping import")
                return True
            
            # MOVE spec files (prefer move over copy)
            if dest_spec_path.exists():
                shutil.rmtree(dest_spec_path)
            shutil.copytree(spec_path, dest_spec_path)
            
            # List imported files
            imported_files = [str(f.relative_to(dest_spec_path)) 
                            for f in dest_spec_path.rglob("*") if f.is_file()]
            
            if self.verbose:
                for file_path in imported_files:
                    self.logger.debug(f"slug={slug} msg=Imported file: {file_path}")
            
            # Update registry with hash
            self.update_registry(slug, source, imported_files, "success", new_hash)
            
            # Run hook
            self.run_capsule_hook(self.capsules_path / slug)
            
            self.logger.info(f"slug={slug} msg=Imported spec to capsules/{slug}")
            return True
            
        except Exception as e:
            error_msg = f"Import failed for {slug}: {e}"
            self.logger.error(f"slug={slug} msg=Import failed: {e}")
            self.log_alert("ERROR", error_msg)
            self.send_notification("Import Failed", f"Failed to import {slug}")
            self.update_registry(slug, source, [], "error")
            return False

    def mark_processed(self, item_path: Path, slug: str):
        """Mark inbox item as processed with timestamped archiving"""
        if self.dry_run:
            self.logger.info(f"slug={slug} msg=DRY RUN: Would move {item_path.name} to Processed/")
            return
            
        processed_dir = self.inbox_path / "Processed"
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        try:
            if item_path.is_file():
                # For files (ZIPs), move to Processed/
                if item_path.name.endswith('.zip'):
                    dest_path = processed_dir / item_path.name
                else:
                    dest_path = processed_dir / f"{slug}-{timestamp}.json"
                shutil.move(str(item_path), str(dest_path))
                if self.verbose:
                    self.logger.debug(f"slug={slug} msg=Moved file to {dest_path}")
            else:
                # For folders, move to timestamped directory in Processed/
                dest_path = processed_dir / f"{slug}-{timestamp}"
                shutil.move(str(item_path), str(dest_path))
                if self.verbose:
                    self.logger.debug(f"slug={slug} msg=Moved folder to {dest_path}")
        except FileNotFoundError:
            # Likely already moved by a previous run; log and continue
            self.logger.warning(f"slug={slug} msg=Processed item not found on move (likely already moved); skipping archive")

    def scan_inbox(self):
        """Scan inbox for new items and process them"""
        self.logger.info("Starting inbox scan")
        
        if not self.inbox_path.exists():
            self.logger.warning("Inbox directory does not exist")
            return
        
        processed_count = 0
        
        for item in self.inbox_path.iterdir():
            if item.name in ["Processed", ".DS_Store"]:
                continue
            
            # Extract slug from filename
            if item.is_file() and item.name.endswith('.zip'):
                slug = item.stem
            elif item.is_dir():
                slug = item.name
            else:
                continue
            
            # Validate slug format (kebab-case, ≤ 40 chars)
            if not slug.replace('-', '').replace('_', '').isalnum() or len(slug) > 40:
                self.logger.warning(f"slug={slug} msg=Invalid slug format")
                continue
            
            try:
                success = False
                
                if item.is_file() and item.name.endswith('.zip'):
                    self.logger.info(f"slug={slug} msg=Processing ZIP file")
                    success = self.process_zip_file(item, slug)
                elif item.is_dir():
                    self.logger.info(f"slug={slug} msg=Processing folder")
                    success = self.process_folder(item, slug)
                
                if success:
                    self.mark_processed(item, slug)
                    processed_count += 1
                    
            except Exception as e:
                self.logger.error(f"slug={slug} msg=Unexpected error: {e}")
        
        self.logger.info(f"Inbox scan complete, processed {processed_count} items")

    def send_notification(self, title: str, message: str):
        """Send macOS notification for failures"""
        try:
            subprocess.run([
                'osascript', '-e', 
                f'display notification "{message}" with title "Huxley Inbox" subtitle "{title}"'
            ], check=False, timeout=10)
        except Exception:
            pass  # Fail silently if notification doesn't work

    def log_alert(self, level: str, message: str):
        """Log alert to separate alerts file"""
        try:
            alerts_file = self.registry_path / "alerts.log"
            with open(alerts_file, 'a') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] {level.upper()}: {message}\n")
        except Exception:
            pass  # Fail silently if alert logging doesn't work

    def run(self):
        """Main entry point"""
        try:
            self.scan_inbox()
        except Exception as e:
            error_msg = f"Fatal error in inbox sync: {e}"
            self.logger.error(error_msg)
            self.log_alert("ERROR", error_msg)
            self.send_notification("Fatal Error", str(e))
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Huxley Inbox Sync - Import capsules from iCloud',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 inbox_sync.py                 # Normal operation
  python3 inbox_sync.py --dry-run       # Preview what would be imported
  python3 inbox_sync.py --verbose       # Detailed logging
  python3 inbox_sync.py --dry-run --verbose  # Preview with details
        """
    )
    
    parser.add_argument('--dry-run', 
                       action='store_true', 
                       help='Show what would be imported without making changes')
    parser.add_argument('--verbose', '-v',
                       action='store_true', 
                       help='Enable verbose logging with file-by-file details')
    
    args = parser.parse_args()
    
    try:
        sync = HuxleyInboxSync(dry_run=args.dry_run, verbose=args.verbose)
        sync.run()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
