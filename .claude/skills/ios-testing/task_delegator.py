#!/usr/bin/env python3
"""
Task Delegator for iOS Testing Loop
Handles delegation to Mobile Dev agent via Claude Code Task tool
"""

import json
import subprocess
import sys
from pathlib import Path


def run_testing_loop(project_path: str, scheme: str, simulator: str, max_iterations: int, mode: str):
    """Run the iOS testing loop and handle delegation"""

    # Set environment variable to indicate automated mode
    import os
    os.environ['CLAUDE_CODE_SESSION'] = '1'
    os.environ['AUTOMATED_MODE'] = '1'

    ruby_script = Path(__file__).parent.parent.parent.parent / 'tools' / 'ios_testing_loop.rb'

    cmd = [
        'ruby', str(ruby_script),
        '--simulator', simulator,
        '--max-iterations', str(max_iterations),
        '--mode', mode,
        project_path,
        scheme
    ]

    print(f"🚀 Starting iOS testing loop...")
    print(f"   Project: {project_path}")
    print(f"   Scheme: {scheme}")
    print(f"   Simulator: {simulator}")
    print(f"   Max iterations: {max_iterations}")
    print("")

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Print stdout and stderr
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Check exit code
    if result.returncode == 0:
        print("✅ Testing loop completed successfully!")
        return True
    elif result.returncode == 42:
        # Delegation needed
        print("🤖 Delegation to Mobile Dev agent required")
        return handle_delegation(result.stdout)
    else:
        print(f"❌ Testing loop failed with exit code {result.returncode}")
        return False


def handle_delegation(stdout: str):
    """Handle delegation to Mobile Dev agent"""

    # Extract diagnostic bundle path from stdout
    import re
    bundle_match = re.search(r'Diagnostic bundle created at: (.+)', stdout)
    if not bundle_match:
        print("❌ Could not find diagnostic bundle path in output")
        return False

    bundle_path = bundle_match.group(1).strip()
    delegation_signal = Path(bundle_path) / 'DELEGATION_NEEDED.json'

    if not delegation_signal.exists():
        print(f"❌ Delegation signal file not found: {delegation_signal}")
        return False

    # Read delegation context
    with open(delegation_signal) as f:
        delegation = json.load(f)

    context_file = delegation['context_file']
    prompt = delegation['prompt']

    print("")
    print("=" * 80)
    print("INVOKING MOBILE DEV AGENT")
    print("=" * 80)
    print("")

    # For now, print the prompt and context file location
    # The actual Task tool invocation needs to happen from within Claude Code session
    print(f"📋 Context file: {context_file}")
    print(f"📦 Diagnostic bundle: {bundle_path}")
    print("")
    print("🤖 Prompt for Mobile Dev agent:")
    print(prompt)
    print("")
    print("=" * 80)
    print("")

    # Write a marker file that tells the calling agent to invoke Task tool
    task_request = Path(bundle_path) / 'TASK_INVOCATION_NEEDED.json'
    with open(task_request, 'w') as f:
        json.dump({
            'subagent_type': 'Mobile Dev',
            'description': f'Fix iOS build/runtime issues (iteration {delegation.get("iteration", "N/A")})',
            'prompt': prompt,
            'context_file': context_file,
            'diagnostic_bundle': bundle_path,
            'timestamp': delegation['timestamp']
        }, f, indent=2)

    print(f"✅ Task invocation request saved to: {task_request}")
    print("")
    print("👉 Next steps:")
    print("   1. Review the diagnostic bundle")
    print("   2. Invoke Mobile Dev agent with the prompt above")
    print("   3. Mobile Dev will analyze issues and apply fixes")
    print("   4. Re-run ios-testing skill to verify fixes")
    print("")

    return False  # Return False to signal that manual intervention is needed


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='iOS Testing Loop with Task Delegation')
    parser.add_argument('project_path', help='Path to .xcodeproj or .xcworkspace')
    parser.add_argument('scheme', help='Xcode scheme name')
    parser.add_argument('--simulator', default='iPhone 16', help='Simulator name')
    parser.add_argument('--max-iterations', type=int, default=10, help='Max iterations')
    parser.add_argument('--mode', choices=['quick', 'debug', 'test'], default='debug', help='Testing mode')

    args = parser.parse_args()

    success = run_testing_loop(
        args.project_path,
        args.scheme,
        args.simulator,
        args.max_iterations,
        args.mode
    )

    sys.exit(0 if success else 1)
