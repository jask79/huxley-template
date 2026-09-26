/**
 * MCP Tools implementation for Huxley task management
 */

import { z } from 'zod';
import { getDatabase } from './database.js';
import crypto from 'crypto';

// Validation schemas
const CreateTaskSchema = z.object({
  title: z.string().min(1).describe('Task title/description'),
  description: z.string().optional().describe('Detailed description or notes'),
  priority: z.enum(['low', 'medium', 'high', 'critical']).default('medium').describe('Task priority level'),
  parent_id: z.string().optional().describe('Parent task ID for hierarchical tasks'),
  capsule: z.string().min(1).describe('Capsule name (e.g., "example-mobile-capsule", "example-media-capsule")'),
  assigned_agent: z.string().optional().describe('Agent emoji+name (e.g., "📱 Mobile Dev")'),
  dependencies: z.array(z.string()).optional().describe('Array of task IDs this depends on'),
  tags: z.array(z.string()).optional().describe('Tags for categorization'),
});

const UpdateTaskStatusSchema = z.object({
  task_id: z.string().min(1).describe('Task ID to update'),
  status: z.enum(['pending', 'in_progress', 'blocked', 'completed', 'archived']).describe('New status'),
  description: z.string().optional().describe('Optional updated description'),
});

const GetTaskTreeSchema = z.object({
  root_id: z.string().optional().describe('Root task ID (omit for top-level tasks)'),
  capsule: z.string().optional().describe('Filter by capsule name'),
});

const SearchTasksSchema = z.object({
  query: z.string().min(1).describe('Search query (full-text search)'),
  status: z.string().optional().describe('Filter by status'),
  capsule: z.string().optional().describe('Filter by capsule'),
  limit: z.number().min(1).max(100).default(10).describe('Maximum results to return'),
});

const LinkDocumentSchema = z.object({
  task_id: z.string().min(1).describe('Task ID to link document to'),
  file_path: z.string().min(1).describe('Absolute path to document file'),
  link_type: z.enum(['spec', 'research', 'reference', 'output']).describe('Type of document link'),
});

/**
 * Generate a unique task ID
 */
function generateTaskId(): string {
  return 'task-' + crypto.randomBytes(4).toString('hex');
}

/**
 * Tool handlers
 */
export const tools = {
  /**
   * Create a new task
   */
  create_task: {
    description: 'Create a new task in the Huxley task management system',
    inputSchema: {
      type: 'object',
      properties: {
        title: {
          type: 'string',
          description: 'Task title/description',
        },
        description: {
          type: 'string',
          description: 'Detailed description or notes',
        },
        priority: {
          type: 'string',
          enum: ['low', 'medium', 'high', 'critical'],
          description: 'Task priority level',
          default: 'medium',
        },
        parent_id: {
          type: 'string',
          description: 'Parent task ID for hierarchical tasks',
        },
        capsule: {
          type: 'string',
          description: 'Capsule name (e.g., "example-mobile-capsule", "example-media-capsule")',
        },
        assigned_agent: {
          type: 'string',
          description: 'Agent emoji+name (e.g., "📱 Mobile Dev")',
        },
        dependencies: {
          type: 'array',
          items: { type: 'string' },
          description: 'Array of task IDs this depends on',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Tags for categorization',
        },
      },
      required: ['title', 'capsule'],
    } as const,
    handler: async (args: unknown) => {
      const validated = CreateTaskSchema.parse(args);
      const db = getDatabase();

      const taskId = generateTaskId();

      const task = db.createTask({
        id: taskId,
        description: validated.title,
        priority: validated.priority,
        capsule: validated.capsule,
        parent_id: validated.parent_id,
        assigned_agent: validated.assigned_agent,
        tags: validated.tags,
        notes: validated.description,
        source: 'api',
      });

      // Add dependencies if provided
      if (validated.dependencies && validated.dependencies.length > 0) {
        const stmt = db['db'].prepare(`
          INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
          VALUES (?, ?, 'required')
        `);

        for (const depId of validated.dependencies) {
          stmt.run(taskId, depId);
        }
      }

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              success: true,
              task_id: taskId,
              task: {
                id: task.id,
                description: task.description,
                status: task.status,
                priority: task.priority,
                capsule: task.capsule,
                assigned_agent: task.assigned_agent,
                created_at: task.created_at,
              },
            }, null, 2),
          },
        ],
      };
    },
  },

  /**
   * Update task status
   */
  update_task_status: {
    description: 'Update the status of an existing task',
    inputSchema: {
      type: 'object',
      properties: {
        task_id: {
          type: 'string',
          description: 'Task ID to update',
        },
        status: {
          type: 'string',
          enum: ['pending', 'in_progress', 'blocked', 'completed', 'archived'],
          description: 'New status',
        },
        description: {
          type: 'string',
          description: 'Optional updated description',
        },
      },
      required: ['task_id', 'status'],
    } as const,
    handler: async (args: unknown) => {
      const validated = UpdateTaskStatusSchema.parse(args);
      const db = getDatabase();

      const task = db.updateTaskStatus(
        validated.task_id,
        validated.status,
        validated.description
      );

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              success: true,
              task: {
                id: task.id,
                description: task.description,
                status: task.status,
                priority: task.priority,
                capsule: task.capsule,
                updated_at: task.updated_at,
                completed_at: task.completed_at,
              },
            }, null, 2),
          },
        ],
      };
    },
  },

  /**
   * Get task tree
   */
  get_task_tree: {
    description: 'Get hierarchical task tree structure with optional filtering',
    inputSchema: {
      type: 'object',
      properties: {
        root_id: {
          type: 'string',
          description: 'Root task ID (omit for top-level tasks)',
        },
        capsule: {
          type: 'string',
          description: 'Filter by capsule name',
        },
      },
    } as const,
    handler: async (args: unknown) => {
      const validated = GetTaskTreeSchema.parse(args);
      const db = getDatabase();

      const tree = db.getTaskTree(validated.root_id, validated.capsule);

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              success: true,
              count: tree.length,
              tree,
            }, null, 2),
          },
        ],
      };
    },
  },

  /**
   * Search tasks
   */
  search_tasks: {
    description: 'Search tasks using full-text search with optional filters',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query (full-text search)',
        },
        status: {
          type: 'string',
          description: 'Filter by status',
        },
        capsule: {
          type: 'string',
          description: 'Filter by capsule',
        },
        limit: {
          type: 'number',
          description: 'Maximum results to return',
          default: 10,
          minimum: 1,
          maximum: 100,
        },
      },
      required: ['query'],
    } as const,
    handler: async (args: unknown) => {
      const validated = SearchTasksSchema.parse(args);
      const db = getDatabase();

      const results = db.searchTasks(validated.query, {
        status: validated.status,
        capsule: validated.capsule,
        limit: validated.limit,
      });

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              success: true,
              count: results.length,
              query: validated.query,
              results: results.map(task => ({
                id: task.id,
                description: task.description,
                status: task.status,
                priority: task.priority,
                capsule: task.capsule,
                assigned_agent: task.assigned_agent,
                tags: JSON.parse(task.tags),
                created_at: task.created_at,
              })),
            }, null, 2),
          },
        ],
      };
    },
  },

  /**
   * Link document to task
   */
  link_document: {
    description: 'Link a document (spec, research, reference, output) to a task',
    inputSchema: {
      type: 'object',
      properties: {
        task_id: {
          type: 'string',
          description: 'Task ID to link document to',
        },
        file_path: {
          type: 'string',
          description: 'Absolute path to document file',
        },
        link_type: {
          type: 'string',
          enum: ['spec', 'research', 'reference', 'output'],
          description: 'Type of document link',
        },
      },
      required: ['task_id', 'file_path', 'link_type'],
    } as const,
    handler: async (args: unknown) => {
      const validated = LinkDocumentSchema.parse(args);
      const db = getDatabase();

      const documentId = db.linkDocument(
        validated.task_id,
        validated.file_path,
        validated.link_type
      );

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              success: true,
              document_id: documentId,
              task_id: validated.task_id,
              file_path: validated.file_path,
              link_type: validated.link_type,
            }, null, 2),
          },
        ],
      };
    },
  },
};
