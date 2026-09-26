# Docker & Container Management

Development, build optimization, registry management, and container orchestration.

## Docker Development (Local Services)

### Docker Compose Example

```yaml
# docker-compose.yml - Multi-service local environment
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    volumes:
      - .:/app
      - /app/node_modules
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=development
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/app_dev
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: npm run dev

  db:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=app_dev
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

volumes:
  postgres_data:
  redis_data:
```

### Common Docker Compose Commands

```bash
docker compose up -d              # Start all services
docker compose logs -f app        # View logs
docker compose exec app npm run migrate  # Execute in container
docker compose up -d --build      # Rebuild after changes
docker compose down               # Stop and remove
docker compose down -v            # Remove including volumes (DESTRUCTIVE)
docker compose stats              # Resource usage
```

### Development Workflow

```bash
# 1. Start fresh environment
docker compose down -v && docker compose up -d

# 2. Run migrations
docker compose exec app npm run migrate

# 3. Seed development data
docker compose exec app npm run seed

# 4. Watch logs
docker compose logs -f

# 5. Shell into container
docker compose exec app sh
```

---

## Docker Build Optimization

### Multi-Stage Dockerfile (Node.js)

```dockerfile
# Stage 1: Dependencies
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production && npm cache clean --force

# Stage 2: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm ci && npm run build && npm prune --production

# Stage 3: Runtime
FROM node:20-alpine AS runtime
WORKDIR /app

# Security: Run as non-root user
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001

COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nodejs:nodejs /app/package.json ./

USER nodejs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

CMD ["node", "dist/server.js"]
```

### Multi-Stage Dockerfile (Python)

```dockerfile
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Stage: Dependencies
FROM base AS deps
RUN apt-get update && apt-get install -y --no-install-recommends gcc postgresql-client && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage: Runtime
FROM base AS runtime
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
COPY --chown=appuser:appuser . .
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build Commands

```bash
docker build -t myapp:latest .                    # Standard build
docker build --no-cache -t myapp:latest .         # Clean build
docker build --target development -t myapp:dev .  # Specific stage
docker buildx build --platform linux/amd64,linux/arm64 -t myapp:latest .  # Multi-platform
```

### .dockerignore

```
node_modules
npm-debug.log
.git
.env
.env.*
dist
coverage
.DS_Store
*.log
.vscode
.idea
```

---

## Registry Management

### Tagging Strategy

```bash
# Version tagging
docker tag myapp:latest myapp:1.2.3
docker tag myapp:latest myapp:1.2
docker tag myapp:latest myapp:1

# Environment tagging
docker tag myapp:latest myapp:production

# Git commit tagging
docker tag myapp:latest myapp:$(git rev-parse --short HEAD)
```

### Registry Operations

```bash
# Docker Hub
docker login
docker push username/myapp:latest

# GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
docker tag myapp:latest ghcr.io/username/myapp:latest
docker push ghcr.io/username/myapp:latest

# AWS ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/myapp:latest
```

---

## Container Security

### Security Scanning

```bash
# Docker Scout
docker scout cves myapp:latest

# Trivy
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image myapp:latest

# Snyk
snyk container test myapp:latest
```

### Security Best Practices

```dockerfile
# 1. Use specific base image versions (not 'latest')
FROM node:20.11.0-alpine3.19

# 2. Run as non-root user
USER nodejs

# 3. Use read-only root filesystem (in compose)
# read_only: true

# 4. Drop capabilities
# cap_drop: [ALL]
# cap_add: [NET_BIND_SERVICE]
```

---

## Cleanup & Maintenance

```bash
docker container prune -f          # Remove unused containers
docker image prune -a -f           # Remove unused images
docker volume prune -f             # Remove unused volumes
docker system prune -a --volumes   # Full cleanup (CAUTION)
docker system df                   # View disk usage
```

### Resource Limits

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
    restart: unless-stopped
```

---

## Troubleshooting

```bash
docker logs -f container_name          # View logs
docker logs --tail 100 container_name  # Last 100 lines
docker inspect container_name          # Full container info
docker exec -it container_name sh      # Shell access
docker top container_name              # Processes
docker stats container_name            # Resource usage
docker port container_name             # Port mappings
docker cp container_name:/app/logs/error.log ./  # Copy files
docker diff container_name             # Filesystem changes

# Health check debugging
docker exec container_name curl http://localhost:3000/health
docker inspect --format='{{json .State.Health}}' container_name | jq
```

---

## macOS Considerations

```yaml
# Performance optimization
services:
  app:
    volumes:
      - .:/app:delegated  # macOS optimization
      - /app/node_modules # Exclude from sync
```

**Recommended Docker Desktop settings:**
- CPUs: 4-6 cores
- Memory: 8-12 GB
- Swap: 2-4 GB
- Disk: 100+ GB

**File watching issues:**
```dockerfile
ENV CHOKIDAR_USEPOLLING=true
```

---

## When to Use Docker

**Use for:**
- Multi-service development (DB + Redis + Queue + App)
- Consistent dev/prod parity
- Dependency isolation
- Quick onboarding
- CI/CD pipelines
- Microservices

**Consider alternatives for:**
- Simple single-service apps
- macOS-specific development (Xcode/Swift)
- Heavy GUI applications
- Performance-sensitive dev work
