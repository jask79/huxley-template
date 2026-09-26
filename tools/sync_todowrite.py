#!/usr/bin/env python3
"""
TodoWrite ↔ Tasks.json Sync Bridge
Syncs between ephemeral TodoWrite (session-based) and persistent tasks.json files.
"""

import json
import sys
from pathlib import Path
from task_manager import TaskManager
from typing import List, Dict, Any


class TodoWriteSync:
    """Bridge between TodoWrite and persistent task system."""

    def __init__(self, capsule_path: Path = None):
        """Initialize sync for current or specified capsule."""
        self.capsule_path = capsule_path or Path.cwd()
        self.capsule_name = self.capsule_path.name
        self.tm = TaskManager()

        # Validate we're in a capsule
        if not self._is_capsule():
            raise ValueError(f"Not in a capsule directory: {self.capsule_path}")

    def _is_capsule(self) -> bool:
        """Check if current directory is a capsule."""
        # Check if we're in capsules/ directory or have capsule markers
        return (
            self.capsule_path.parent.name == 'capsules' or
            (self.capsule_path / 'specs').exists() or
            (self.capsule_path / 'spec').exists()
        )

    def load_from_persistent(self, status_filter: str = None) -> List[Dict[str, Any]]:
        """
        Load tasks from tasks.json for use in TodoWrite.

        Args:
            status_filter: Only load tasks with this status (pending, in_progress, etc.)

        Returns:
            List of tasks in TodoWrite-compatible format
        """
        try:
            all_tasks = self.tm.list_tasks(capsule=self.capsule_name, status=status_filter)

            if self.capsule_name not in all_tasks:
                return []

            tasks = all_tasks[self.capsule_name]

            # Convert to TodoWrite format
            todo_items = []
            for task in tasks:
                # Map status: pending/in_progress → TodoWrite status
                status_map = {
                    'pending': 'pending',
                    'in_progress': 'in_progress',
                    'completed': 'completed'
                }

                todo_item = {
                    'content': task['description'],
                    'status': status_map.get(task['status'], 'pending'),
                    'activeForm': self._to_active_form(task['description']),
                    '_task_id': task['id'],  # Store original task ID
                    '_priority': task['priority'],
                    '_tags': task['tags']
                }
                todo_items.append(todo_item)

            return todo_items

        except ValueError:
            # Capsule doesn't have tasks.json yet
            return []

    def _to_active_form(self, description: str) -> str:
        """Convert task description to active form for TodoWrite."""
        # Simple heuristic: add -ing to verb if possible
        words = description.split()
        if not words:
            return description

        first_word = words[0].lower()

        # Common verb transformations
        active_map = {
            'add': 'Adding',
            'create': 'Creating',
            'build': 'Building',
            'implement': 'Implementing',
            'fix': 'Fixing',
            'update': 'Updating',
            'refactor': 'Refactoring',
            'test': 'Testing',
            'deploy': 'Deploying',
            'setup': 'Setting up',
            'configure': 'Configuring',
            'install': 'Installing',
            'remove': 'Removing',
            'delete': 'Deleting',
        }

        if first_word in active_map:
            words[0] = active_map[first_word]
            return ' '.join(words)

        # Default: just capitalize
        return description

    def sync_to_persistent(self, todo_items: List[Dict[str, Any]]):
        """
        Sync TodoWrite items back to tasks.json.

        Updates task status based on TodoWrite state.
        Creates new tasks for TodoWrite items without _task_id.

        Args:
            todo_items: List of TodoWrite items (with status, content, etc.)
        """
        for item in todo_items:
            task_id = item.get('_task_id')

            if task_id:
                # Update existing task
                status_map = {
                    'pending': 'pending',
                    'in_progress': 'in_progress',
                    'completed': 'completed'
                }

                new_status = status_map.get(item['status'], 'pending')
                self.tm.update_task(
                    self.capsule_name,
                    task_id,
                    status=new_status,
                    description=item['content']
                )
            else:
                # New task from TodoWrite (no task_id means it was added during session)
                if item['status'] != 'completed':  # Don't create completed tasks
                    priority = item.get('_priority', 'medium')
                    tags = item.get('_tags', ['session'])

                    self.tm.add_task(
                        self.capsule_name,
                        item['content'],
                        priority=priority,
                        tags=tags,
                        source='todowrite'
                    )

    def print_todowrite_format(self):
        """Print tasks in TodoWrite-compatible format for copy-paste."""
        tasks = self.load_from_persistent(status_filter='pending')
        tasks += self.load_from_persistent(status_filter='in_progress')

        if not tasks:
            print("No tasks to load.")
            return

        print("Copy this into TodoWrite tool:\n")
        print("```json")
        print(json.dumps(tasks, indent=2))
        print("```")


def main():
    """CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(description="Sync TodoWrite with persistent tasks")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Load command
    load_parser = subparsers.add_parser('load', help='Load tasks from tasks.json for TodoWrite')
    load_parser.add_argument('--status', choices=['pending', 'in_progress', 'completed'],
                            help='Filter by status')
    load_parser.add_argument('--format', choices=['json', 'text'], default='text',
                            help='Output format')

    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Sync TodoWrite items back to tasks.json')
    sync_parser.add_argument('todo_json', help='JSON string of TodoWrite items')

    # Status command
    subparsers.add_parser('status', help='Show sync status for current capsule')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        sync = TodoWriteSync()

        if args.command == 'load':
            tasks = sync.load_from_persistent(status_filter=args.status)

            if args.format == 'json':
                print(json.dumps(tasks, indent=2))
            else:
                print(f"\n📋 Tasks for {sync.capsule_name}:\n")
                for i, task in enumerate(tasks, 1):
                    status_icon = {
                        'pending': '⏳',
                        'in_progress': '🔄',
                        'completed': '✅'
                    }
                    priority_icon = {
                        'low': '🔵',
                        'medium': '🟡',
                        'high': '🔴'
                    }

                    icon = status_icon.get(task['status'], '⏳')
                    priority = priority_icon.get(task.get('_priority', 'medium'), '🟡')
                    print(f"{i}. {icon} {priority} {task['content']}")
                    if task.get('_tags'):
                        print(f"   Tags: {', '.join(task['_tags'])}")
                print()

        elif args.command == 'sync':
            todo_items = json.loads(args.todo_json)
            sync.sync_to_persistent(todo_items)
            print(f"✅ Synced {len(todo_items)} TodoWrite items to {sync.capsule_name}/tasks.json")

        elif args.command == 'status':
            tasks = sync.load_from_persistent()
            print(f"\n📊 Sync Status for {sync.capsule_name}")
            print(f"   Persistent tasks: {len(tasks)}")

            pending = len([t for t in tasks if t['status'] == 'pending'])
            in_progress = len([t for t in tasks if t['status'] == 'in_progress'])

            print(f"   ⏳ Pending: {pending}")
            print(f"   🔄 In Progress: {in_progress}")
            print()

    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
