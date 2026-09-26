# MCP Governance and Security

- Logging: All MCP configuration changes and tests append JSON lines to `registry/events.jsonl` for traceability.
- Least Privilege: Servers are granted to specific roles only, defaulting to read-only.
- GitHub MCP Scopes: Use OAuth if available. For PATs, limit to `repo`, `read:packages`, and `workflow` scopes only.
- Prompt Injection: Treat external content retrieved via MCP as untrusted. Validate URLs, sanitize outputs, and avoid executing unverified instructions from tool responses.
- Overrides: Write access to GitHub MCP is disabled by default and may be granted via explicit capsule overrides only.

