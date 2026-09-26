#!/usr/bin/env python3
"""
Huxley Task Manager
Persistent task tracking across capsules with smart routing and CRUD operations.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import uuid
import yaml


class TaskManager:
    """Manage persistent tasks for Huxley capsules."""

    # Smart capsule routing keywords (from {{ORCHESTRATOR_NAME}} Navigation Intelligence)
    CAPSULE_KEYWORDS = {
        # Placeholder routing table: one entry per capsule you create.
        'huxley-core': ['system', 'builder', 'framework', 'core', 'governance', 'tools'],
        'example-mobile-capsule': ['mobile', 'ios', 'android', 'app', 'swift', 'react native', 'xcode'],
        'example-web-capsule': ['store', 'shop', 'website', 'checkout', 'ecommerce', 'landing page'],
        'example-automation-capsule': ['automation', 'workflow', 'script', 'shortcut', 'cron'],
    }

    def __init__(self, catalyst_root: Path = None):
        """Initialize task manager with Huxley root."""
        self.catalyst_root = catalyst_root or Path(__file__).parent.parent
        self.capsules_dir = self.catalyst_root / "capsules"

    def _get_task_file(self, capsule: str) -> Path:
        """Get the tasks.json file path for a capsule."""
        capsule_dir = self.capsules_dir / capsule
        if not capsule_dir.exists():
            raise ValueError(f"Capsule '{capsule}' does not exist")

        return capsule_dir / "tasks.json"

    def _load_tasks(self, capsule: str) -> List[Dict[str, Any]]:
        """Load tasks from capsule's tasks.json."""
        task_file = self._get_task_file(capsule)
        if not task_file.exists():
            return []

        with open(task_file, 'r') as f:
            data = json.load(f)
            # New structure: {metadata: ..., tasks: [...], archived_tasks: [], queue: {...}}
            # Old structure: just a list of tasks
            if isinstance(data, dict):
                return data.get('tasks', [])
            else:
                # Legacy format (plain list)
                return data

    def _save_tasks(self, capsule: str, tasks: List[Dict[str, Any]]):
        """Save tasks to capsule's tasks.json."""
        capsule_dir = self.capsules_dir / capsule
        task_file = capsule_dir / "tasks.json"

        # Load existing file to preserve structure (metadata, queue config, archived_tasks)
        if task_file.exists():
            with open(task_file, 'r') as f:
                try:
                    data = json.load(f)
                    # Handle legacy format (plain list)
                    if isinstance(data, list):
                        data = {
                            'metadata': {
                                'version': '1.0',
                                'capsule': capsule,
                                'last_updated': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                                'task_count': 0,
                                'active_count': 0,
                                'completed_count': 0
                            },
                            'tasks': [],
                            'archived_tasks': [],
                            'queue': {
                                'enabled': True,
                                'auto_assign': False,
                                'priority_threshold': 'medium'
                            }
                        }
                except json.JSONDecodeError:
                    data = None
        else:
            data = None

        # Create new structure if needed
        if data is None:
            data = {
                'metadata': {
                    'version': '1.0',
                    'capsule': capsule,
                    'last_updated': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    'task_count': 0,
                    'active_count': 0,
                    'completed_count': 0
                },
                'tasks': [],
                'archived_tasks': [],
                'queue': {
                    'enabled': True,
                    'auto_assign': False,
                    'priority_threshold': 'medium'
                }
            }

        # Update tasks and metadata
        data['tasks'] = tasks
        data['metadata']['last_updated'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        data['metadata']['task_count'] = len(tasks) + len(data.get('archived_tasks', []))
        data['metadata']['active_count'] = len([t for t in tasks if t['status'] != 'completed'])
        data['metadata']['completed_count'] = len([t for t in tasks if t['status'] == 'completed']) + len(data.get('archived_tasks', []))

        with open(task_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def suggest_capsule(self, description: str) -> Optional[str]:
        """Suggest a capsule based on task description keywords."""
        description_lower = description.lower()
        scores = {}

        for capsule, keywords in self.CAPSULE_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in description_lower)
            if score > 0:
                scores[capsule] = score

        if scores:
            # Return capsule with highest score
            return max(scores, key=scores.get)
        return None

    def add_task(
        self,
        capsule: str,
        description: str,
        priority: str = "medium",
        tags: List[str] = None,
        dependencies: List[str] = None,
        assigned_agent: str = None,
        source: str = "manual",
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Add a new task to a capsule.

        Args:
            capsule: Capsule name
            description: Task description
            priority: low, medium, high
            tags: Optional list of tags
            dependencies: Optional list of task IDs this depends on
            assigned_agent: Optional agent name
            source: How task was created (manual, telegram, api, etc.)
            notes: Additional notes

        Returns:
            Created task object
        """
        tasks = self._load_tasks(capsule)

        task = {
            "id": str(uuid.uuid4())[:8],
            "description": description,
            "status": "pending",
            "priority": priority,
            "created": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "updated": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "assigned_agent": assigned_agent,
            "dependencies": dependencies or [],
            "tags": tags or [],
            "source": source,
            "notes": notes,
            "completed_at": None
        }

        tasks.append(task)
        self._save_tasks(capsule, tasks)

        return task

    def list_tasks(
        self,
        capsule: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        List tasks with optional filtering.

        Args:
            capsule: Filter by specific capsule (None = all capsules)
            status: Filter by status (pending, in_progress, completed)
            priority: Filter by priority (low, medium, high)
            tags: Filter by tags (must match any tag)

        Returns:
            Dictionary mapping capsule name to list of tasks
        """
        results = {}

        # Determine which capsules to check
        if capsule:
            capsules = [capsule]
        else:
            # All capsules with tasks.yaml or tasks.json
            capsules = [
                d.name for d in self.capsules_dir.iterdir()
                if d.is_dir() and ((d / "tasks.yaml").exists() or (d / "tasks.json").exists())
            ]

        for cap in capsules:
            tasks = self._load_tasks(cap)

            # Apply filters
            filtered = tasks
            if status:
                filtered = [t for t in filtered if t["status"] == status]
            if priority:
                filtered = [t for t in filtered if t["priority"] == priority]
            if tags:
                filtered = [t for t in filtered if any(tag in t["tags"] for tag in tags)]

            if filtered:
                results[cap] = filtered

        return results

    def get_task(self, capsule: str, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task by ID."""
        tasks = self._load_tasks(capsule)
        for task in tasks:
            if task["id"] == task_id:
                return task
        return None

    def update_task(
        self,
        capsule: str,
        task_id: str,
        **updates
    ) -> Optional[Dict[str, Any]]:
        """
        Update task fields.

        Args:
            capsule: Capsule name
            task_id: Task ID
            **updates: Fields to update (status, priority, description, etc.)

        Returns:
            Updated task or None if not found
        """
        tasks = self._load_tasks(capsule)

        for task in tasks:
            if task["id"] == task_id:
                # Update allowed fields
                allowed_fields = {
                    'description', 'status', 'priority', 'tags',
                    'dependencies', 'assigned_agent', 'notes'
                }
                for key, value in updates.items():
                    if key in allowed_fields:
                        task[key] = value

                task["updated"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

                # Set completion time if status changed to completed
                if updates.get('status') == 'completed' and task["completed_at"] is None:
                    task["completed_at"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

                self._save_tasks(capsule, tasks)
                return task

        return None

    def complete_task(self, capsule: str, task_id: str) -> Optional[Dict[str, Any]]:
        """Mark a task as completed."""
        return self.update_task(capsule, task_id, status="completed")

    def delete_task(self, capsule: str, task_id: str) -> bool:
        """Delete a task."""
        tasks = self._load_tasks(capsule)
        original_length = len(tasks)
        tasks = [t for t in tasks if t["id"] != task_id]

        if len(tasks) < original_length:
            self._save_tasks(capsule, tasks)
            return True
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall task statistics across all capsules."""
        all_tasks = self.list_tasks()

        total = 0
        by_status = {"pending": 0, "in_progress": 0, "completed": 0}
        by_priority = {"low": 0, "medium": 0, "high": 0}
        by_capsule = {}

        for capsule, tasks in all_tasks.items():
            by_capsule[capsule] = len(tasks)
            for task in tasks:
                total += 1
                by_status[task["status"]] = by_status.get(task["status"], 0) + 1
                by_priority[task["priority"]] = by_priority.get(task["priority"], 0) + 1

        return {
            "total": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "by_capsule": by_capsule
        }

    def migrate_from_yaml(self, capsule: str) -> bool:
        """
        Migrate a capsule from tasks.yaml to tasks.json.

        Args:
            capsule: Capsule name to migrate

        Returns:
            True if migration successful, False if no YAML file exists
        """
        capsule_dir = self.capsules_dir / capsule
        if not capsule_dir.exists():
            raise ValueError(f"Capsule '{capsule}' does not exist")

        yaml_file = capsule_dir / "tasks.yaml"
        json_file = capsule_dir / "tasks.json"

        if not yaml_file.exists():
            return False

        # Load from YAML
        import yaml
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)

        # Save as JSON
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Backup and remove old YAML file
        backup_file = capsule_dir / "tasks.yaml.backup"
        yaml_file.rename(backup_file)

        return True

    def migrate_all_from_yaml(self) -> Dict[str, bool]:
        """
        Migrate all capsules from tasks.yaml to tasks.json.

        Returns:
            Dictionary mapping capsule name to migration success status
        """
        results = {}

        for capsule_dir in self.capsules_dir.iterdir():
            if capsule_dir.is_dir() and (capsule_dir / "tasks.yaml").exists():
                capsule_name = capsule_dir.name
                try:
                    success = self.migrate_from_yaml(capsule_name)
                    results[capsule_name] = success
                except Exception as e:
                    print(f"Error migrating {capsule_name}: {e}", file=sys.stderr)
                    results[capsule_name] = False

        return results


def main():
    """CLI interface for task manager."""
    import argparse

    parser = argparse.ArgumentParser(description="Huxley Task Manager")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Add task
    add_parser = subparsers.add_parser('add', help='Add a new task')
    add_parser.add_argument('capsule', help='Capsule name')
    add_parser.add_argument('description', help='Task description')
    add_parser.add_argument('--priority', choices=['low', 'medium', 'high'], default='medium')
    add_parser.add_argument('--tags', nargs='+', help='Tags')
    add_parser.add_argument('--agent', help='Assigned agent')
    add_parser.add_argument('--notes', help='Additional notes', default='')

    # List tasks
    list_parser = subparsers.add_parser('list', help='List tasks')
    list_parser.add_argument('--capsule', help='Filter by capsule')
    list_parser.add_argument('--status', choices=['pending', 'in_progress', 'completed'])
    list_parser.add_argument('--priority', choices=['low', 'medium', 'high'])
    list_parser.add_argument('--tags', nargs='+', help='Filter by tags')

    # Update task
    update_parser = subparsers.add_parser('update', help='Update a task')
    update_parser.add_argument('capsule', help='Capsule name')
    update_parser.add_argument('task_id', help='Task ID')
    update_parser.add_argument('--status', choices=['pending', 'in_progress', 'completed'])
    update_parser.add_argument('--priority', choices=['low', 'medium', 'high'])
    update_parser.add_argument('--description', help='New description')
    update_parser.add_argument('--agent', help='Assigned agent')

    # Complete task
    complete_parser = subparsers.add_parser('complete', help='Mark task as completed')
    complete_parser.add_argument('capsule', help='Capsule name')
    complete_parser.add_argument('task_id', help='Task ID')

    # Delete task
    delete_parser = subparsers.add_parser('delete', help='Delete a task')
    delete_parser.add_argument('capsule', help='Capsule name')
    delete_parser.add_argument('task_id', help='Task ID')

    # Statistics
    subparsers.add_parser('stats', help='Show task statistics')

    # Suggest capsule
    suggest_parser = subparsers.add_parser('suggest', help='Suggest capsule for task description')
    suggest_parser.add_argument('description', help='Task description')

    # Migrate to YAML
    migrate_parser = subparsers.add_parser('migrate', help='Migrate tasks from JSON to YAML')
    migrate_parser.add_argument('capsule', nargs='?', help='Capsule name (omit to migrate all)')
    migrate_parser.add_argument('--all', action='store_true', help='Migrate all capsules')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    tm = TaskManager()

    if args.command == 'add':
        task = tm.add_task(
            args.capsule,
            args.description,
            priority=args.priority,
            tags=args.tags,
            assigned_agent=args.agent,
            notes=args.notes
        )
        print(f"✅ Added task {task['id']} to {args.capsule}")
        print(f"   {task['description']}")

    elif args.command == 'list':
        tasks = tm.list_tasks(
            capsule=args.capsule,
            status=args.status,
            priority=args.priority,
            tags=args.tags
        )

        if not tasks:
            print("No tasks found")
            return

        for capsule, task_list in tasks.items():
            print(f"\n📦 {capsule}")
            for task in task_list:
                status_icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}
                priority_icon = {"low": "🔵", "medium": "🟡", "high": "🔴"}
                print(f"  {status_icon[task['status']]} {priority_icon[task['priority']]} [{task['id']}] {task['description']}")
                if task.get('assigned_agent'):
                    print(f"     → Assigned: {task['assigned_agent']}")
                if task.get('tags'):
                    print(f"     → Tags: {', '.join(task['tags'])}")

    elif args.command == 'update':
        updates = {}
        if args.status:
            updates['status'] = args.status
        if args.priority:
            updates['priority'] = args.priority
        if args.description:
            updates['description'] = args.description
        if args.agent:
            updates['assigned_agent'] = args.agent

        task = tm.update_task(args.capsule, args.task_id, **updates)
        if task:
            print(f"✅ Updated task {task['id']}")
        else:
            print(f"❌ Task {args.task_id} not found in {args.capsule}")

    elif args.command == 'complete':
        task = tm.complete_task(args.capsule, args.task_id)
        if task:
            print(f"✅ Completed task {task['id']}: {task['description']}")
        else:
            print(f"❌ Task {args.task_id} not found in {args.capsule}")

    elif args.command == 'delete':
        if tm.delete_task(args.capsule, args.task_id):
            print(f"✅ Deleted task {args.task_id}")
        else:
            print(f"❌ Task {args.task_id} not found in {args.capsule}")

    elif args.command == 'stats':
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
        print(f"\nBy Capsule:")
        for capsule, count in stats['by_capsule'].items():
            print(f"  📦 {capsule}: {count}")

    elif args.command == 'suggest':
        suggestion = tm.suggest_capsule(args.description)
        if suggestion:
            print(f"💡 Suggested capsule: {suggestion}")
        else:
            print("❓ No clear capsule match found. Please specify manually.")

    elif args.command == 'migrate':
        if args.all or not args.capsule:
            # Migrate all capsules
            print("🔄 Migrating all capsules from JSON to YAML...")
            results = tm.migrate_all_capsules()

            if not results:
                print("✅ No capsules need migration (all using YAML)")
                return

            successful = [cap for cap, success in results.items() if success]
            failed = [cap for cap, success in results.items() if not success]

            if successful:
                print(f"\n✅ Successfully migrated {len(successful)} capsule(s):")
                for capsule in successful:
                    print(f"   📦 {capsule}")

            if failed:
                print(f"\n❌ Failed to migrate {len(failed)} capsule(s):")
                for capsule in failed:
                    print(f"   📦 {capsule}")

        else:
            # Migrate specific capsule
            print(f"🔄 Migrating {args.capsule} from JSON to YAML...")
            try:
                success = tm.migrate_capsule(args.capsule)
                if success:
                    print(f"✅ Successfully migrated {args.capsule}")
                    print(f"   Old file backed up as tasks.json.backup")
                else:
                    print(f"⚠️  No tasks.json found for {args.capsule}")
            except Exception as e:
                print(f"❌ Migration failed: {e}", file=sys.stderr)


if __name__ == '__main__':
    main()
