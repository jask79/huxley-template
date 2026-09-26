/**
 * Database module for Huxley task management
 * Provides SQLite database connection and query methods
 */

import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export interface Task {
  id: string;
  parent_id: string | null;
  description: string;
  status: 'pending' | 'in_progress' | 'blocked' | 'completed' | 'archived';
  priority: 'low' | 'medium' | 'high' | 'critical';
  capsule: string;
  assigned_agent: string | null;
  source: 'manual' | 'telegram' | 'api' | 'automation' | 'dependency';
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  estimate_hours: number | null;
  actual_hours: number | null;
  tags: string; // JSON array
  notes: string | null;
  framework: string; // JSON object
}

export interface TaskDependency {
  id: number;
  task_id: string;
  depends_on_task_id: string;
  dependency_type: 'required' | 'blocks' | 'related';
  created_at: string;
}

export interface Document {
  id: number;
  file_path: string;
  file_hash: string;
  file_size: number | null;
  mime_type: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskDocument {
  id: number;
  task_id: string;
  document_id: number;
  link_type: 'spec' | 'research' | 'reference' | 'output';
  created_at: string;
}

export interface TaskTreeNode extends Task {
  parent_description: string | null;
  child_count: number;
  dependency_count: number;
  children?: TaskTreeNode[];
  dependencies?: TaskDependency[];
}

/**
 * Database connection and query interface
 */
export class TaskDatabase {
  private db: Database.Database;
  private dbPath: string;

  constructor(dbPath?: string) {
    // Use environment variable or default path
    this.dbPath = dbPath || process.env.CATALYST_DB || '{{CATALYST_ROOT}}/tasks.db';

    // Ensure parent directory exists
    const dir = path.dirname(this.dbPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // Open database
    this.db = new Database(this.dbPath);
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('foreign_keys = ON');

    // Initialize schema if needed
    this.initializeSchema();

    console.error(`[Huxley MCP] Connected to database: ${this.dbPath}`);
  }

  /**
   * Initialize database schema from SQL file
   */
  private initializeSchema(): void {
    const schemaPath = path.resolve(__dirname, '../../../api/db/schema.sql');

    if (fs.existsSync(schemaPath)) {
      const schema = fs.readFileSync(schemaPath, 'utf-8');
      this.db.exec(schema);
      console.error('[Huxley MCP] Database schema initialized');
    } else {
      console.error('[Huxley MCP] Warning: schema.sql not found, assuming database is already initialized');
    }
  }

  /**
   * Get a task by ID
   */
  getTask(taskId: string): Task | undefined {
    const stmt = this.db.prepare('SELECT * FROM tasks WHERE id = ?');
    return stmt.get(taskId) as Task | undefined;
  }

  /**
   * Create a new task
   */
  createTask(task: {
    id: string;
    description: string;
    priority?: string;
    capsule: string;
    parent_id?: string;
    assigned_agent?: string;
    tags?: string[];
    notes?: string;
    source?: string;
  }): Task {
    const stmt = this.db.prepare(`
      INSERT INTO tasks (
        id, description, priority, capsule, parent_id, assigned_agent, tags, notes, source
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const tagsJson = JSON.stringify(task.tags || []);

    stmt.run(
      task.id,
      task.description,
      task.priority || 'medium',
      task.capsule,
      task.parent_id || null,
      task.assigned_agent || null,
      tagsJson,
      task.notes || null,
      task.source || 'manual'
    );

    const created = this.getTask(task.id);
    if (!created) {
      throw new Error('Failed to create task');
    }
    return created;
  }

  /**
   * Update task status
   */
  updateTaskStatus(taskId: string, status: string, description?: string): Task {
    const updates: string[] = ['status = ?'];
    const params: (string | null)[] = [status];

    if (description) {
      updates.push('description = ?');
      params.push(description);
    }

    if (status === 'completed') {
      updates.push("completed_at = datetime('now', 'utc')");
    }

    params.push(taskId);

    const stmt = this.db.prepare(`
      UPDATE tasks
      SET ${updates.join(', ')}
      WHERE id = ?
    `);

    stmt.run(...params);

    const updated = this.getTask(taskId);
    if (!updated) {
      throw new Error('Task not found');
    }
    return updated;
  }

  /**
   * Get task tree (hierarchical structure)
   */
  getTaskTree(rootId?: string, capsule?: string): TaskTreeNode[] {
    let query = `
      SELECT
        t.*,
        p.description as parent_description,
        (SELECT COUNT(*) FROM tasks WHERE parent_id = t.id) as child_count,
        (SELECT COUNT(*) FROM task_dependencies WHERE task_id = t.id) as dependency_count
      FROM tasks t
      LEFT JOIN tasks p ON t.parent_id = p.id
      WHERE 1=1
    `;

    const params: (string | null)[] = [];

    if (rootId) {
      query += ' AND t.parent_id = ?';
      params.push(rootId);
    } else {
      query += ' AND t.parent_id IS NULL';
    }

    if (capsule) {
      query += ' AND t.capsule = ?';
      params.push(capsule);
    }

    query += ' ORDER BY t.priority DESC, t.created_at ASC';

    const stmt = this.db.prepare(query);
    const tasks = stmt.all(...params) as TaskTreeNode[];

    // Recursively load children
    for (const task of tasks) {
      task.children = this.getTaskTree(task.id, capsule);
      task.dependencies = this.getTaskDependencies(task.id);
    }

    return tasks;
  }

  /**
   * Get task dependencies
   */
  getTaskDependencies(taskId: string): TaskDependency[] {
    const stmt = this.db.prepare(`
      SELECT * FROM task_dependencies
      WHERE task_id = ?
      ORDER BY created_at ASC
    `);
    return stmt.all(taskId) as TaskDependency[];
  }

  /**
   * Search tasks using full-text search
   */
  searchTasks(query: string, options?: {
    status?: string;
    capsule?: string;
    limit?: number;
  }): Task[] {
    const limit = options?.limit || 10;

    let sql = `
      SELECT t.*
      FROM tasks_fts fts
      JOIN tasks t ON fts.id = t.id
      WHERE fts MATCH ?
    `;

    const params: (string | number)[] = [query];

    if (options?.status) {
      sql += ' AND t.status = ?';
      params.push(options.status);
    }

    if (options?.capsule) {
      sql += ' AND t.capsule = ?';
      params.push(options.capsule);
    }

    sql += ' ORDER BY rank LIMIT ?';
    params.push(limit);

    const stmt = this.db.prepare(sql);
    return stmt.all(...params) as Task[];
  }

  /**
   * Link a document to a task
   */
  linkDocument(taskId: string, filePath: string, linkType: string): number {
    // Check if task exists
    const task = this.getTask(taskId);
    if (!task) {
      throw new Error('Task not found');
    }

    // Calculate file hash
    const fileHash = this.calculateFileHash(filePath);

    // Get or create document
    let document = this.getDocumentByPath(filePath);
    if (!document) {
      document = this.createDocument(filePath, fileHash);
    }

    // Create link
    const stmt = this.db.prepare(`
      INSERT INTO task_documents (task_id, document_id, link_type)
      VALUES (?, ?, ?)
      ON CONFLICT (task_id, document_id) DO UPDATE SET link_type = excluded.link_type
    `);

    stmt.run(taskId, document.id, linkType);

    return document.id;
  }

  /**
   * Get document by file path
   */
  private getDocumentByPath(filePath: string): Document | undefined {
    const stmt = this.db.prepare('SELECT * FROM documents WHERE file_path = ?');
    return stmt.get(filePath) as Document | undefined;
  }

  /**
   * Create a new document record
   */
  private createDocument(filePath: string, fileHash: string): Document {
    let fileSize: number | null = null;
    let mimeType: string | null = null;

    try {
      const stats = fs.statSync(filePath);
      fileSize = stats.size;

      // Simple mime type detection
      const ext = path.extname(filePath).toLowerCase();
      const mimeMap: Record<string, string> = {
        '.md': 'text/markdown',
        '.txt': 'text/plain',
        '.json': 'application/json',
        '.yaml': 'application/yaml',
        '.yml': 'application/yaml',
        '.pdf': 'application/pdf',
      };
      mimeType = mimeMap[ext] || 'application/octet-stream';
    } catch (err) {
      console.error(`[Huxley MCP] Warning: Could not stat file ${filePath}:`, err);
    }

    const stmt = this.db.prepare(`
      INSERT INTO documents (file_path, file_hash, file_size, mime_type)
      VALUES (?, ?, ?, ?)
    `);

    stmt.run(filePath, fileHash, fileSize, mimeType);

    const doc = this.getDocumentByPath(filePath);
    if (!doc) {
      throw new Error('Failed to create document');
    }
    return doc;
  }

  /**
   * Calculate SHA256 hash of a file
   */
  private calculateFileHash(filePath: string): string {
    try {
      const crypto = require('crypto');
      const content = fs.readFileSync(filePath);
      return crypto.createHash('sha256').update(content).digest('hex');
    } catch (err) {
      console.error(`[Huxley MCP] Warning: Could not hash file ${filePath}:`, err);
      return 'unknown';
    }
  }

  /**
   * Get active tasks for a capsule
   */
  getActiveTasks(capsule?: string): Task[] {
    let query = `
      SELECT * FROM tasks
      WHERE status NOT IN ('completed', 'archived')
    `;

    const params: string[] = [];

    if (capsule) {
      query += ' AND capsule = ?';
      params.push(capsule);
    }

    query += ' ORDER BY priority DESC, created_at ASC';

    const stmt = this.db.prepare(query);
    return stmt.all(...params) as Task[];
  }

  /**
   * Get all blocked tasks
   */
  getBlockedTasks(): Task[] {
    const stmt = this.db.prepare(`
      SELECT * FROM tasks
      WHERE status = 'blocked'
      ORDER BY priority DESC, created_at ASC
    `);
    return stmt.all() as Task[];
  }

  /**
   * Get task with full context (dependencies, documents)
   */
  getTaskContext(taskId: string): {
    task: Task;
    dependencies: TaskDependency[];
    documents: Array<Document & { link_type: string }>;
    children: Task[];
  } | null {
    const task = this.getTask(taskId);
    if (!task) {
      return null;
    }

    const dependencies = this.getTaskDependencies(taskId);

    const documents = this.db.prepare(`
      SELECT d.*, td.link_type
      FROM documents d
      JOIN task_documents td ON d.id = td.document_id
      WHERE td.task_id = ?
      ORDER BY td.created_at ASC
    `).all(taskId) as Array<Document & { link_type: string }>;

    const children = this.db.prepare(`
      SELECT * FROM tasks
      WHERE parent_id = ?
      ORDER BY priority DESC, created_at ASC
    `).all(taskId) as Task[];

    return {
      task,
      dependencies,
      documents,
      children
    };
  }

  /**
   * Close database connection
   */
  close(): void {
    this.db.close();
    console.error('[Huxley MCP] Database connection closed');
  }
}

// Export singleton instance
let dbInstance: TaskDatabase | null = null;

export function getDatabase(): TaskDatabase {
  if (!dbInstance) {
    dbInstance = new TaskDatabase();
  }
  return dbInstance;
}
