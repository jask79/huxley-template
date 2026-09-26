#!/usr/bin/env node
/**
 * MCP Router - Dynamic MCP proxy for capsule-specific MCPs
 *
 * This acts as a single MCP server that Claude Code connects to,
 * but dynamically routes requests to capsule-specific MCPs based on
 * the current working directory.
 *
 * Architecture:
 * Claude Code → MCP Router → Active Capsule MCP Backend
 *
 * When navigation occurs, the router switches which backend MCP it proxies to.
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

class MCPRouter {
  constructor() {
    this.activeBackends = new Map(); // name -> process
    this.currentCapsule = null;
    this.contextFile = path.join(process.env.HOME, '.claude', '.{{ORCHESTRATOR_NAME_LOWER}}_context.json');

    // Start monitoring for capsule changes
    this.watchContext();
  }

  watchContext() {
    // Poll context file for capsule changes
    setInterval(() => {
      try {
        if (fs.existsSync(this.contextFile)) {
          const context = JSON.parse(fs.readFileSync(this.contextFile, 'utf8'));
          if (context.currentCapsule !== this.currentCapsule) {
            this.switchCapsule(context.currentCapsule);
          }
        }
      } catch (err) {
        // Context file doesn't exist yet or is malformed
      }
    }, 1000);
  }

  async switchCapsule(capsulePath) {
    console.error(`[MCP Router] Switching to capsule: ${capsulePath}`);
    this.currentCapsule = capsulePath;

    // Kill old backend processes
    for (const [name, proc] of this.activeBackends.entries()) {
      console.error(`[MCP Router] Stopping ${name}`);
      proc.kill();
    }
    this.activeBackends.clear();

    // Load new capsule's MCPs
    const mcpConfigPath = path.join(capsulePath, '.mcp.json');
    if (!fs.existsSync(mcpConfigPath)) {
      console.error(`[MCP Router] No .mcp.json found at ${mcpConfigPath}`);
      return;
    }

    const mcpConfig = JSON.parse(fs.readFileSync(mcpConfigPath, 'utf8'));

    for (const [name, config] of Object.entries(mcpConfig.mcpServers || {})) {
      console.error(`[MCP Router] Starting MCP: ${name}`);
      this.startBackend(name, config);
    }
  }

  startBackend(name, config) {
    const proc = spawn(config.command, config.args || [], {
      env: { ...process.env, ...(config.env || {}) },
      stdio: ['pipe', 'pipe', 'pipe']
    });

    proc.stderr.on('data', (data) => {
      console.error(`[${name}] ${data.toString()}`);
    });

    proc.on('exit', (code) => {
      console.error(`[MCP Router] ${name} exited with code ${code}`);
      this.activeBackends.delete(name);
    });

    this.activeBackends.set(name, proc);
  }

  async handleRequest(request) {
    // Route request to appropriate backend based on method/params
    const method = request.method;

    // For now, broadcast to all active backends and return first successful response
    // TODO: More intelligent routing based on method

    for (const [name, proc] of this.activeBackends.entries()) {
      try {
        proc.stdin.write(JSON.stringify(request) + '\n');
        // Wait for response (simplified - needs proper JSON-RPC handling)
        return await this.readResponse(proc.stdout);
      } catch (err) {
        console.error(`[MCP Router] Error routing to ${name}:`, err);
      }
    }

    return { jsonrpc: '2.0', id: request.id, error: { code: -32603, message: 'No backend available' } };
  }

  async readResponse(stream) {
    return new Promise((resolve) => {
      const rl = readline.createInterface({ input: stream });
      rl.once('line', (line) => {
        resolve(JSON.parse(line));
        rl.close();
      });
    });
  }

  async start() {
    // MCP Server stdio interface
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      terminal: false
    });

    console.error('[MCP Router] Started');

    rl.on('line', async (line) => {
      try {
        const request = JSON.parse(line);
        const response = await this.handleRequest(request);
        process.stdout.write(JSON.stringify(response) + '\n');
      } catch (err) {
        console.error('[MCP Router] Error:', err);
      }
    });
  }
}

// Start the router
const router = new MCPRouter();
router.start();
