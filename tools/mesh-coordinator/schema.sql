-- Mesh Communications Table Schema
-- Stores all agent-to-agent communication attempts for audit trail

CREATE TABLE IF NOT EXISTS mesh_communications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_agent TEXT NOT NULL,
  to_agent TEXT NOT NULL,
  request_type TEXT NOT NULL,
  context TEXT NOT NULL,
  urgency TEXT NOT NULL CHECK(urgency IN ('blocking', 'nice_to_have', 'fyi')),
  session_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('allowed', 'blocked', 'completed', 'in_progress', 'blocked', 'fyi')),
  block_reason TEXT,
  timestamp DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_mesh_communications_from_agent ON mesh_communications(from_agent);
CREATE INDEX IF NOT EXISTS idx_mesh_communications_to_agent ON mesh_communications(to_agent);
CREATE INDEX IF NOT EXISTS idx_mesh_communications_session_id ON mesh_communications(session_id);
CREATE INDEX IF NOT EXISTS idx_mesh_communications_timestamp ON mesh_communications(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_mesh_communications_status ON mesh_communications(status);

-- Example queries for {{ORCHESTRATOR_NAME}} oversight:

-- Get all mesh communications in the last 24 hours
-- SELECT * FROM mesh_communications WHERE timestamp >= datetime('now', '-1 day') ORDER BY timestamp DESC;

-- Get all blocked requests
-- SELECT * FROM mesh_communications WHERE status = 'blocked' ORDER BY timestamp DESC;

-- Get communications for a specific session
-- SELECT * FROM mesh_communications WHERE session_id = 'mesh-1234567890-abc123' ORDER BY timestamp;

-- Get all requests from a specific agent
-- SELECT * FROM mesh_communications WHERE from_agent = '🎨 Frontend Developer' ORDER BY timestamp DESC;

-- Get communication stats by agent
-- SELECT from_agent, COUNT(*) as request_count, SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) as blocked_count FROM mesh_communications GROUP BY from_agent;
