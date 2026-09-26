#!/usr/bin/env python3
"""
Huxley Task Management CLI

Command-line interface for task CRUD operations, search, and document linking.
"""

import sys
import json
import argparse
from typing import Optional, List
from datetime import datetime

# Add services to path
sys.path.insert(0, '{{CATALYST_ROOT}}/api')

from services.task_manager import TaskManager
from services.document_linker import DocumentLinker
from services.search_service import SearchService


def format_task(task: dict, verbose: bool = False) -> str:
    """
    Format task for terminal output.

    Args:
        task: Task dict
        verbose: Show full details

    Returns:
        Formatted string
    """
    # Priority emoji
    priority_emoji = {
        'low': '🔵',
        'medium': '🟡',
        'high': '🔴',
        'critical': '💥'
    }

    # Status emoji
    status_emoji = {
        'pending': '⏳',
        'in_progress': '🔄',
        'blocked': '🚫',
        'completed': '✅',
        'archived': '📦'
    }

    output = []
    output.append(f"{status_emoji.get(task['status'], '•')} {priority_emoji.get(task['priority'], '•')} [{task['id']}] {task['description']}")

    if verbose:
        output.append(f"   Capsule: {task['capsule']}")
        output.append(f"   Status: {task['status']} | Priority: {task['priority']}")

        if task.get('assigned_agent'):
            output.append(f"   Assigned: {task['assigned_agent']}")

        if task.get('tags'):
            tags_str = ', '.join(task['tags'])
            output.append(f"   Tags: {tags_str}")

        if task.get('notes'):
            notes_preview = task['notes'][:100] + '...' if len(task['notes']) > 100 else task['notes']
            output.append(f"   Notes: {notes_preview}")

        output.append(f"   Created: {task['created_at']}")

        if task.get('children'):
            output.append(f"   Children: {len(task['children'])}")

        if task.get('dependencies'):
            output.append(f"   Dependencies: {len(task['dependencies'])}")

    return '\n'.join(output)


def cmd_create(args):
    """Create new task."""
    try:
        tags = args.tags.split(',') if args.tags else []

        task = TaskManager.create_task(
            description=args.description,
            capsule=args.capsule,
            status=args.status,
            priority=args.priority,
            parent_id=args.parent_id,
            assigned_agent=args.agent,
            source='manual',
            tags=tags,
            notes=args.notes,
            estimate_hours=args.estimate
        )

        print(f"✅ Task created: {task['id']}")
        print(format_task(task, verbose=True))

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_get(args):
    """Get task by ID."""
    try:
        task = TaskManager.get_task(
            args.task_id,
            include_children=not args.no_children,
            include_dependencies=not args.no_deps
        )

        if not task:
            print(f"❌ Task not found: {args.task_id}", file=sys.stderr)
            sys.exit(1)

        if args.json:
            print(json.dumps(task, indent=2))
        else:
            print(format_task(task, verbose=True))

            # Show children
            if task.get('children'):
                print("\n📁 Children:")
                for child in task['children']:
                    print(f"  {format_task(child)}")

            # Show dependencies
            if task.get('dependencies'):
                print("\n🔗 Dependencies:")
                for dep in task['dependencies']:
                    print(f"  {format_task(dep)} ({dep['dependency_type']})")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_update(args):
    """Update task."""
    try:
        updates = {}

        if args.description:
            updates['description'] = args.description
        if args.status:
            updates['status'] = args.status
        if args.priority:
            updates['priority'] = args.priority
        if args.agent:
            updates['assigned_agent'] = args.agent
        if args.tags:
            updates['tags'] = args.tags.split(',')
        if args.notes:
            updates['notes'] = args.notes
        if args.estimate:
            updates['estimate_hours'] = args.estimate
        if args.actual:
            updates['actual_hours'] = args.actual

        if not updates:
            print("❌ No update fields provided", file=sys.stderr)
            sys.exit(1)

        task = TaskManager.update_task(args.task_id, **updates)

        print(f"✅ Task updated: {task['id']}")
        print(format_task(task, verbose=True))

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_delete(args):
    """Delete task."""
    try:
        if not args.yes:
            response = input(f"Delete task {args.task_id}? This will cascade to children (y/N): ")
            if response.lower() != 'y':
                print("❌ Cancelled")
                return

        deleted = TaskManager.delete_task(args.task_id)

        if deleted:
            print(f"✅ Task deleted: {args.task_id}")
        else:
            print(f"❌ Task not found: {args.task_id}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    """List tasks with filters."""
    try:
        tasks = TaskManager.list_tasks(
            capsule=args.capsule,
            status=args.status,
            priority=args.priority,
            assigned_agent=args.agent,
            parent_id=args.parent_id,
            limit=args.limit,
            offset=args.offset
        )

        if not tasks:
            print("No tasks found")
            return

        print(f"Found {len(tasks)} tasks:\n")

        for task in tasks:
            print(format_task(task, verbose=args.verbose))

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_tree(args):
    """Show task tree."""
    try:
        tree = TaskManager.get_task_tree(
            root_task_id=args.root,
            capsule=args.capsule
        )

        if not tree:
            print("No tasks found")
            return

        def print_tree(tasks, indent=0):
            """Recursively print task tree."""
            for task in tasks:
                prefix = "  " * indent + ("└─ " if indent > 0 else "")
                print(f"{prefix}{format_task(task)}")
                if task.get('children'):
                    print_tree(task['children'], indent + 1)

        print_tree(tree)

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_search(args):
    """Search tasks."""
    try:
        results = SearchService.search_tasks(
            query=args.query,
            capsule=args.capsule,
            status=args.status,
            priority=args.priority,
            assigned_agent=args.agent,
            limit=args.limit
        )

        if not results:
            print(f"No results found for: {args.query}")
            return

        print(f"Found {len(results)} results:\n")

        for result in results:
            print(format_task(result, verbose=args.verbose))
            if result.get('snippet'):
                print(f"   Snippet: {result['snippet']}")
            if result.get('relevance_score'):
                print(f"   Score: {result['relevance_score']:.2f}")
            print()

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_link_doc(args):
    """Link document to task."""
    try:
        link = DocumentLinker.link_document_to_task(
            task_id=args.task_id,
            file_path=args.file_path,
            link_type=args.link_type
        )

        print(f"✅ Document linked: {link['file_path']}")
        print(f"   Type: {link['link_type']}")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_add_dep(args):
    """Add task dependency."""
    try:
        dep = TaskManager.add_dependency(
            task_id=args.task_id,
            depends_on_task_id=args.depends_on,
            dependency_type=args.dep_type
        )

        print(f"✅ Dependency added:")
        print(f"   {dep['task_id']} depends on {dep['depends_on_task_id']} ({dep['dependency_type']})")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Huxley Task Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create new task')
    create_parser.add_argument('description', help='Task description')
    create_parser.add_argument('capsule', help='Capsule name')
    create_parser.add_argument('--status', default='pending', choices=['pending', 'in_progress', 'blocked', 'completed', 'archived'])
    create_parser.add_argument('--priority', default='medium', choices=['low', 'medium', 'high', 'critical'])
    create_parser.add_argument('--parent-id', help='Parent task ID')
    create_parser.add_argument('--agent', help='Assigned agent')
    create_parser.add_argument('--tags', help='Comma-separated tags')
    create_parser.add_argument('--notes', help='Additional notes')
    create_parser.add_argument('--estimate', type=float, help='Estimated hours')

    # Get command
    get_parser = subparsers.add_parser('get', help='Get task by ID')
    get_parser.add_argument('task_id', help='Task ID')
    get_parser.add_argument('--no-children', action='store_true', help='Exclude children')
    get_parser.add_argument('--no-deps', action='store_true', help='Exclude dependencies')
    get_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # Update command
    update_parser = subparsers.add_parser('update', help='Update task')
    update_parser.add_argument('task_id', help='Task ID')
    update_parser.add_argument('--description', help='Updated description')
    update_parser.add_argument('--status', choices=['pending', 'in_progress', 'blocked', 'completed', 'archived'])
    update_parser.add_argument('--priority', choices=['low', 'medium', 'high', 'critical'])
    update_parser.add_argument('--agent', help='Assigned agent')
    update_parser.add_argument('--tags', help='Comma-separated tags')
    update_parser.add_argument('--notes', help='Additional notes')
    update_parser.add_argument('--estimate', type=float, help='Estimated hours')
    update_parser.add_argument('--actual', type=float, help='Actual hours')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete task')
    delete_parser.add_argument('task_id', help='Task ID')
    delete_parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')

    # List command
    list_parser = subparsers.add_parser('list', help='List tasks')
    list_parser.add_argument('--capsule', help='Filter by capsule')
    list_parser.add_argument('--status', help='Filter by status')
    list_parser.add_argument('--priority', help='Filter by priority')
    list_parser.add_argument('--agent', help='Filter by assigned agent')
    list_parser.add_argument('--parent-id', help='Filter by parent ID')
    list_parser.add_argument('--limit', type=int, default=50, help='Maximum results')
    list_parser.add_argument('--offset', type=int, default=0, help='Pagination offset')
    list_parser.add_argument('-v', '--verbose', action='store_true', help='Show full details')

    # Tree command
    tree_parser = subparsers.add_parser('tree', help='Show task tree')
    tree_parser.add_argument('--root', help='Specific root task ID')
    tree_parser.add_argument('--capsule', help='Filter by capsule')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search tasks')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--capsule', help='Filter by capsule')
    search_parser.add_argument('--status', help='Filter by status')
    search_parser.add_argument('--priority', help='Filter by priority')
    search_parser.add_argument('--agent', help='Filter by assigned agent')
    search_parser.add_argument('--limit', type=int, default=20, help='Maximum results')
    search_parser.add_argument('-v', '--verbose', action='store_true', help='Show full details')

    # Link document command
    link_parser = subparsers.add_parser('link-doc', help='Link document to task')
    link_parser.add_argument('task_id', help='Task ID')
    link_parser.add_argument('file_path', help='Path to document')
    link_parser.add_argument('--link-type', default='reference', choices=['spec', 'research', 'reference', 'output'])

    # Add dependency command
    dep_parser = subparsers.add_parser('add-dep', help='Add task dependency')
    dep_parser.add_argument('task_id', help='Task ID')
    dep_parser.add_argument('depends_on', help='Task ID this depends on')
    dep_parser.add_argument('--dep-type', default='required', choices=['required', 'blocks', 'related'])

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to command handler
    commands = {
        'create': cmd_create,
        'get': cmd_get,
        'update': cmd_update,
        'delete': cmd_delete,
        'list': cmd_list,
        'tree': cmd_tree,
        'search': cmd_search,
        'link-doc': cmd_link_doc,
        'add-dep': cmd_add_dep
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
