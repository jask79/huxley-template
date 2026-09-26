#!/usr/bin/env python3
"""
Huxley Task Loader
Display pending tasks at session startup or on demand.
"""

import sys
from pathlib import Path
from task_manager import TaskManager


def display_task_summary(verbose: bool = False):
    """Display a summary of pending tasks across all capsules."""
    tm = TaskManager()

    # Get all pending tasks
    pending_tasks = tm.list_tasks(status="pending")
    in_progress_tasks = tm.list_tasks(status="in_progress")

    if not pending_tasks and not in_progress_tasks:
        print("✨ No pending tasks. Ready to work!")
        return

    print("\n📋 Huxley Task Queue\n")

    # Show in-progress tasks first
    if in_progress_tasks:
        print("🔄 In Progress:")
        for capsule, tasks in in_progress_tasks.items():
            print(f"\n  📦 {capsule}")
            for task in tasks:
                priority_icon = {"low": "🔵", "medium": "🟡", "high": "🔴"}
                print(f"    {priority_icon[task['priority']]} [{task['id']}] {task['description']}")
                if verbose:
                    if task.get('assigned_agent'):
                        print(f"       → Agent: {task['assigned_agent']}")
                    if task.get('tags'):
                        print(f"       → Tags: {', '.join(task['tags'])}")
                    if task.get('dependencies'):
                        print(f"       → Depends on: {', '.join(task['dependencies'])}")

    # Show pending tasks
    if pending_tasks:
        print("\n⏳ Pending:")
        for capsule, tasks in pending_tasks.items():
            high_priority = [t for t in tasks if t['priority'] == 'high']
            medium_priority = [t for t in tasks if t['priority'] == 'medium']
            low_priority = [t for t in tasks if t['priority'] == 'low']

            print(f"\n  📦 {capsule} ({len(tasks)} task{'s' if len(tasks) > 1 else ''})")

            # Show high priority first
            for task in high_priority:
                print(f"    🔴 [{task['id']}] {task['description']}")
                if verbose:
                    if task.get('assigned_agent'):
                        print(f"       → Agent: {task['assigned_agent']}")
                    if task.get('tags'):
                        print(f"       → Tags: {', '.join(task['tags'])}")

            # Then medium
            for task in medium_priority:
                print(f"    🟡 [{task['id']}] {task['description']}")
                if verbose:
                    if task.get('assigned_agent'):
                        print(f"       → Agent: {task['assigned_agent']}")
                    if task.get('tags'):
                        print(f"       → Tags: {', '.join(task['tags'])}")

            # Then low
            for task in low_priority:
                print(f"    🔵 [{task['id']}] {task['description']}")
                if verbose:
                    if task.get('assigned_agent'):
                        print(f"       → Agent: {task['assigned_agent']}")
                    if task.get('tags'):
                        print(f"       → Tags: {', '.join(task['tags'])}")

    # Show summary
    total_pending = sum(len(tasks) for tasks in pending_tasks.values())
    total_in_progress = sum(len(tasks) for tasks in in_progress_tasks.values())

    print(f"\n💡 Total: {total_in_progress} in progress, {total_pending} pending")
    print(f"   Use: task-manager list --capsule <name> for details")
    print(f"   Use: task-manager complete <capsule> <task-id> to mark done\n")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Load and display Huxley tasks")
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed task information')
    parser.add_argument('--stats', action='store_true', help='Show statistics instead of task list')

    args = parser.parse_args()

    if args.stats:
        from task_manager import TaskManager
        tm = TaskManager()
        stats = tm.get_statistics()
        print(f"\n📊 Huxley Task Statistics")
        print(f"\nTotal Tasks: {stats['total']}")
        print(f"\nBy Status:")
        print(f"  ⏳ Pending: {stats['by_status']['pending']}")
        print(f"  🔄 In Progress: {stats['by_status']['in_progress']}")
        print(f"  ✅ Completed: {stats['by_status']['completed']}")
        print(f"\nBy Priority:")
        print(f"  🔴 High: {stats['by_priority']['high']}")
        print(f"  🟡 Medium: {stats['by_priority']['medium']}")
        print(f"  🔵 Low: {stats['by_priority']['low']}")
        if stats['by_capsule']:
            print(f"\nBy Capsule:")
            for capsule, count in sorted(stats['by_capsule'].items()):
                print(f"  📦 {capsule}: {count}")
        print()
    else:
        display_task_summary(verbose=args.verbose)


if __name__ == '__main__':
    main()
