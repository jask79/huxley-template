/**
 * Audit Trail for Mesh Communications
 * Logs all agent-to-agent communication attempts to quality.db
 */

import Database from 'better-sqlite3';

const DB_PATH = process.env.CATALYST_QUALITY_DB || '{{CATALYST_ROOT}}/monitoring/quality.db';

let db: Database.Database | null = null;

/**
 * Get database connection (singleton)
 */
export function getDatabase(): Database.Database {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    console.error(`[Mesh Coordinator] Connected to quality.db at ${DB_PATH}`);
  }
  return db;
}

/**
 * Log a mesh communication request
 */
export interface MeshCommunicationLog {
  from_agent: string;
  to_agent: string;
  request_type: string;
  context: string;
  urgency: 'blocking' | 'nice_to_have' | 'fyi';
  session_id: string;
  status: 'allowed' | 'blocked';
  block_reason?: string;
}

export function logMeshCommunication(log: MeshCommunicationLog): void {
  const db = getDatabase();

  const stmt = db.prepare(`
    INSERT INTO mesh_communications (
      from_agent,
      to_agent,
      request_type,
      context,
      urgency,
      session_id,
      status,
      block_reason,
      timestamp
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
  `);

  stmt.run(
    log.from_agent,
    log.to_agent,
    log.request_type,
    log.context,
    log.urgency,
    log.session_id,
    log.status,
    log.block_reason || null
  );
}

/**
 * Log a status broadcast
 */
export interface StatusBroadcastLog {
  from_agent: string;
  status: string;
  message: string;
  session_id?: string;
}

export function logStatusBroadcast(log: StatusBroadcastLog): void {
  const db = getDatabase();

  const stmt = db.prepare(`
    INSERT INTO mesh_communications (
      from_agent,
      to_agent,
      request_type,
      context,
      urgency,
      session_id,
      status,
      timestamp
    ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
  `);

  stmt.run(
    log.from_agent,
    'broadcast',
    'status_update',
    log.message,
    'fyi',
    log.session_id || 'none',
    log.status
  );
}

/**
 * Get recent mesh communications
 */
export interface GetMeshActivityParams {
  limit?: number;
  since?: string; // ISO timestamp
}

export function getMeshActivity(params: GetMeshActivityParams): Array<Record<string, unknown>> {
  const db = getDatabase();
  const limit = params.limit || 50;

  let query = `
    SELECT
      id,
      from_agent,
      to_agent,
      request_type,
      context,
      urgency,
      session_id,
      status,
      block_reason,
      timestamp
    FROM mesh_communications
  `;

  const queryParams: unknown[] = [];

  if (params.since) {
    query += ` WHERE timestamp >= ?`;
    queryParams.push(params.since);
  }

  query += ` ORDER BY timestamp DESC LIMIT ?`;
  queryParams.push(limit);

  const stmt = db.prepare(query);
  const rows = stmt.all(...queryParams);

  return rows as Array<Record<string, unknown>>;
}

/**
 * Close database connection
 */
export function closeDatabase(): void {
  if (db) {
    db.close();
    db = null;
  }
}
