#!/usr/bin/env python3
"""
Subagent Work Verification Tool

MANDATORY: {{ORCHESTRATOR_NAME}} must run this after EVERY Task tool invocation.
Verifies that subagent's claimed deliverables actually exist and were modified.
Blocks reporting to {{USER_NAME}} until all work is verified or implemented.

Usage:
    verify_subagent_work.py --agent "AgentName" \\
        --modified "file1.tsx,file2.md" \\
        --created "brief.md,docs.md"
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

class SubagentVerification:
    """Verify subagent work and enforce completion before reporting."""

    def __init__(self, agent_name: str, base_dir: str = None):
        self.agent = agent_name
        self.base_dir = Path(base_dir or os.getcwd())
        self.verification_results = []
        self.timestamp = datetime.now().isoformat()

    def check_git_modified(self, filepath: Path) -> bool:
        """Check if file was modified recently using git status."""
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain', str(filepath)],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            # Modified files show as 'M' or 'A' in git status
            return bool(result.stdout.strip())
        except Exception as e:
            print(f"Warning: Could not check git status for {filepath}: {e}", file=sys.stderr)
            return False

    def verify_files_modified(self, file_paths: List[str]):
        """Check if claimed file modifications actually exist and were modified."""
        for path_str in file_paths:
            path = self.base_dir / path_str.strip()
            exists = path.exists()

            if exists:
                modified = self.check_git_modified(path)
                self.verification_results.append({
                    'type': 'modified',
                    'file': str(path),
                    'relative': path_str.strip(),
                    'exists': True,
                    'modified': modified,
                    'status': 'VERIFIED' if modified else 'STALE'
                })
            else:
                self.verification_results.append({
                    'type': 'modified',
                    'file': str(path),
                    'relative': path_str.strip(),
                    'exists': False,
                    'modified': False,
                    'status': 'MISSING'
                })

    def verify_files_created(self, file_paths: List[str]):
        """Check if claimed new files actually exist."""
        for path_str in file_paths:
            path = self.base_dir / path_str.strip()
            exists = path.exists()

            self.verification_results.append({
                'type': 'created',
                'file': str(path),
                'relative': path_str.strip(),
                'exists': exists,
                'status': 'VERIFIED' if exists else 'MISSING'
            })

    def generate_implementation_checklist(self) -> List[Dict[str, str]]:
        """Generate mandatory tasks for {{ORCHESTRATOR_NAME}} to complete."""
        checklist = []

        for result in self.verification_results:
            if result['status'] == 'MISSING':
                checklist.append({
                    'action': 'IMPLEMENT',
                    'type': result['type'],
                    'file': result['relative'],
                    'reason': f"Agent claimed to {result['type']} this file but it does not exist"
                })
            elif result['status'] == 'STALE':
                checklist.append({
                    'action': 'VERIFY_MANUAL',
                    'type': result['type'],
                    'file': result['relative'],
                    'reason': 'File exists but git does not show recent modifications'
                })

        return checklist

    def report(self) -> Dict[str, Any]:
        """Generate verification report - shows what needs implementation."""
        verified = [r for r in self.verification_results if r['status'] == 'VERIFIED']
        issues = [r for r in self.verification_results if r['status'] != 'VERIFIED']

        if issues:
            checklist = self.generate_implementation_checklist()
            return {
                'status': 'INCOMPLETE',
                'agent': self.agent,
                'timestamp': self.timestamp,
                'verified_count': len(verified),
                'issue_count': len(issues),
                'issues': issues,
                'mandatory_checklist': checklist,
                'blocking': True,
                'message': f'⚠️  Agent {self.agent} claimed work is INCOMPLETE - {len(issues)} items need implementation'
            }
        else:
            return {
                'status': 'VERIFIED',
                'agent': self.agent,
                'timestamp': self.timestamp,
                'verified_count': len(verified),
                'message': f'✅ All {len(verified)} claimed deliverables from {self.agent} verified'
            }

    def print_report(self):
        """Print formatted report to stdout."""
        report = self.report()

        print(f"\n{'='*70}")
        print(f"SUBAGENT WORK VERIFICATION REPORT")
        print(f"{'='*70}")
        print(f"Agent: {report['agent']}")
        print(f"Status: {report['status']}")
        print(f"Timestamp: {report['timestamp']}")
        print(f"Verified: {report['verified_count']} items")
        print(f"-"*70)

        if report['status'] == 'INCOMPLETE':
            print(f"⚠️  BLOCKING: {report['issue_count']} issues found\n")
            print("MANDATORY IMPLEMENTATION CHECKLIST:")
            for i, item in enumerate(report['mandatory_checklist'], 1):
                print(f"\n{i}. [{item['action']}] {item['file']}")
                print(f"   Type: {item['type']}")
                print(f"   Reason: {item['reason']}")

            print(f"\n{'='*70}")
            print("⛔ DO NOT REPORT TO {{USER_NAME}} UNTIL ALL ITEMS IMPLEMENTED")
            print(f"{'='*70}\n")
            return 1  # Exit code 1 = incomplete
        else:
            print(f"\n{report['message']}")
            print(f"{'='*70}")
            print("✅ VERIFIED - Safe to report completion to {{USER_NAME}}")
            print(f"{'='*70}\n")
            return 0  # Exit code 0 = success

def main():
    parser = argparse.ArgumentParser(
        description='Verify subagent work before reporting completion',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--agent', required=True, help='Name of the agent that did the work')
    parser.add_argument('--modified', help='Comma-separated list of files agent claimed to modify')
    parser.add_argument('--created', help='Comma-separated list of files agent claimed to create')
    parser.add_argument('--base-dir', help='Base directory for relative paths (default: cwd)')

    args = parser.parse_args()

    if not args.modified and not args.created:
        print("Error: Must specify at least one of --modified or --created", file=sys.stderr)
        return 2

    verifier = SubagentVerification(args.agent, args.base_dir)

    if args.modified:
        modified_files = [f.strip() for f in args.modified.split(',') if f.strip()]
        verifier.verify_files_modified(modified_files)

    if args.created:
        created_files = [f.strip() for f in args.created.split(',') if f.strip()]
        verifier.verify_files_created(created_files)

    return verifier.print_report()

if __name__ == '__main__':
    sys.exit(main())
