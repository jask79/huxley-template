#!/bin/bash

# Mesh Coordinator MCP Server Startup Script

export CATALYST_QUALITY_DB="${CATALYST_QUALITY_DB:-{{CATALYST_ROOT}}/monitoring/quality.db}"

exec node {{CATALYST_ROOT}}/tools/mesh-coordinator/dist/index.js
