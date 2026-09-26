FROM node:20-alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Install router as root (needed for global npm install)
RUN npm install -g @musistudio/claude-code-router

# Use node user that already exists in node:20-alpine (UID 1000)
# Note: Running as root here because ccr needs to access config directory
# In production, consider using a named volume with proper permissions

# Clean up any existing PID files on start
RUN rm -f /root/.claude-code-router/.claude-code-router.pid

# Provide the host-style path used in configs so both host + container can share them
RUN mkdir -p {{HOME_DIR}} && ln -s /root/.claude-code-router {{HOME_DIR}}/.claude-code-router

EXPOSE 3456

# Use exec form and remove PID file before starting
CMD ["sh", "-c", "rm -f /root/.claude-code-router/.claude-code-router.pid && exec ccr start --no-daemon"]
