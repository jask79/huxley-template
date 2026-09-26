/**
 * MCP Resources implementation for Huxley task management
 */

import { getDatabase } from './database.js';

/**
 * Resource handlers
 */
export const resources = {
  /**
   * List all available resources
   */
  list: () => {
    return {
      resources: [
        {
          uri: 'catalyst://tasks/active',
          name: 'Active Tasks (All Capsules)',
          description: 'All active tasks across all capsules',
          mimeType: 'application/json',
        },
        {
          uri: 'catalyst://tasks/active/{capsule}',
          name: 'Active Tasks (Specific Capsule)',
          description: 'Active tasks for a specific capsule',
          mimeType: 'application/json',
        },
        {
          uri: 'catalyst://tasks/blocked',
          name: 'Blocked Tasks',
          description: 'All tasks with blocked status',
          mimeType: 'application/json',
        },
        {
          uri: 'catalyst://tasks/{task_id}/context',
          name: 'Task Context',
          description: 'Full context for a specific task including dependencies and documents',
          mimeType: 'application/json',
        },
      ],
    };
  },

  /**
   * Read a specific resource
   */
  read: (uri: string) => {
    const db = getDatabase();

    // Parse URI
    const match = uri.match(/^catalyst:\/\/tasks\/(.+)$/);
    if (!match) {
      throw new Error(`Invalid resource URI: ${uri}`);
    }

    const path = match[1];

    // Active tasks (all capsules)
    if (path === 'active') {
      const tasks = db.getActiveTasks();
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify({
              capsule: 'all',
              count: tasks.length,
              tasks: tasks.map(task => ({
                id: task.id,
                description: task.description,
                status: task.status,
                priority: task.priority,
                capsule: task.capsule,
                assigned_agent: task.assigned_agent,
                tags: JSON.parse(task.tags),
                created_at: task.created_at,
                updated_at: task.updated_at,
              })),
            }, null, 2),
          },
        ],
      };
    }

    // Active tasks (specific capsule)
    const activeMatch = path.match(/^active\/(.+)$/);
    if (activeMatch) {
      const capsule = activeMatch[1];
      const tasks = db.getActiveTasks(capsule);
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify({
              capsule,
              count: tasks.length,
              tasks: tasks.map(task => ({
                id: task.id,
                description: task.description,
                status: task.status,
                priority: task.priority,
                assigned_agent: task.assigned_agent,
                tags: JSON.parse(task.tags),
                created_at: task.created_at,
                updated_at: task.updated_at,
              })),
            }, null, 2),
          },
        ],
      };
    }

    // Blocked tasks
    if (path === 'blocked') {
      const tasks = db.getBlockedTasks();
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify({
              count: tasks.length,
              tasks: tasks.map(task => ({
                id: task.id,
                description: task.description,
                priority: task.priority,
                capsule: task.capsule,
                assigned_agent: task.assigned_agent,
                tags: JSON.parse(task.tags),
                notes: task.notes,
                created_at: task.created_at,
                updated_at: task.updated_at,
              })),
            }, null, 2),
          },
        ],
      };
    }

    // Task context
    const contextMatch = path.match(/^([^\/]+)\/context$/);
    if (contextMatch) {
      const taskId = contextMatch[1];
      const context = db.getTaskContext(taskId);

      if (!context) {
        throw new Error(`Task not found: ${taskId}`);
      }

      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify({
              task: {
                id: context.task.id,
                description: context.task.description,
                status: context.task.status,
                priority: context.task.priority,
                capsule: context.task.capsule,
                assigned_agent: context.task.assigned_agent,
                tags: JSON.parse(context.task.tags),
                notes: context.task.notes,
                created_at: context.task.created_at,
                updated_at: context.task.updated_at,
                completed_at: context.task.completed_at,
              },
              dependencies: context.dependencies.map(dep => ({
                depends_on_task_id: dep.depends_on_task_id,
                dependency_type: dep.dependency_type,
              })),
              documents: context.documents.map(doc => ({
                file_path: doc.file_path,
                link_type: doc.link_type,
                mime_type: doc.mime_type,
                file_size: doc.file_size,
                updated_at: doc.updated_at,
              })),
              children: context.children.map(child => ({
                id: child.id,
                description: child.description,
                status: child.status,
                priority: child.priority,
              })),
            }, null, 2),
          },
        ],
      };
    }

    throw new Error(`Unknown resource path: ${path}`);
  },
};
