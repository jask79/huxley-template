# Huxley Developer Guide

**Version:** 2.0  
**Last Updated:** 2025-08-11  
**Audience:** New contributors, future maintainers, capsule creators

---

## 🎯 **Quick Start**

The Huxley system creates self-contained "capsules" that move ideas from ideation → design → build → deploy. Each capsule chooses a **lane** (standard for speed, standard for quality) and gets automatic **agent routing** based on domain.

### **Create Your First Capsule**
```bash
cd {{CATALYST_ROOT}}
python3 tools/trigger_planner.sh your-project-name automation standard
```

This creates a capsule with:
- Standard directory structure (`spec/`, `src/`, `runs/`, `ops/`, `docs/`)
- Automatic agent routing to `automation-specialist`
- Fast lane DoD validation
- Pre-configured MCP profile for automation tools

---

## 🏗️ **Capsule Lifecycle**

### **1. Creation Phase**
- **Template Selection**: Choose from 4 starter templates
  - `automation-starter`: n8n/AppleScript workflows (standard)
  - `web-dev-starter`: React/Next.js applications (standard)
  - `apple-app-starter`: iOS/macOS applications (standard)
  - `capsule-base`: Enhanced base with agent overrides

### **2. Development Phase**
- **Lane Detection Priority**: `capsule.json` → `requirements.yaml` → default `standard`
- **Agent Routing**: Automatic based on branch/domain
- **MCP Access**: Three-layer control (Profile → Capsule → Agent)
- **DoD Enforcement**: Lane-specific quality gates

### **3. Deployment Phase**
- **Immutability**: Once deployed, capsules are read-only
- **Versioning**: New iterations create new capsule versions
- **Event Logging**: Full lifecycle tracking in `registry/events.jsonl`

---

## 🤖 **Agent System**

### **Specialized Agents**
| Agent | Domain | Tools | Lane Preference |
|-------|--------|-------|-----------------|
| `automation-specialist` | n8n, AppleScript, workflows | applescript, n8n | standard |
| `frontend-specialist` | React, shadcn/ui, web UI | shadcn-ui, filesystem | standard |
| `backend-architect` | APIs, databases, architecture | filesystem, git, http | standard |
| `ios-specialist` | Swift, SwiftUI, iOS apps | xcodebuild, ios-sim | standard |
| `macos-specialist` | AppKit, macOS apps | xcodebuild, filesystem | standard |
| `devops-troubleshooter` | Production, debugging | filesystem, git, http | standard |
| `deployment-engineer` | CI/CD, Docker, IaC | filesystem, git, http | standard |
| `security-auditor` | OWASP, vulnerability assessment | filesystem, git | standard |
| `test-automator` | Test suites, CI integration | filesystem, git | standard |
| `javascript-pro` | Node.js, modern JavaScript | filesystem, git, http | both |
| `python-pro` | Python, data processing | filesystem, git, http | both |
| `code-reviewer` | Quality, security, best practices | filesystem, git | standard |

### **Agent Override Process**
Create `.claude/agents/` in your capsule to override default routing:

```bash
# Example: Force security-auditor for automation capsule
mkdir -p capsules/my-automation/.claude/agents/
echo "security-auditor" > capsules/my-automation/.claude/agents/primary.txt
echo "automation-specialist" > capsules/my-automation/.claude/agents/secondary.txt
```

### **Routing Rules**
1. **Branch Detection**: `automation` → `automation-specialist`, `web` → `frontend-specialist`
2. **Lane Enhancement**: `standard` adds `security-auditor` + `code-reviewer`
3. **Capsule Override**: `.claude/agents/` takes precedence
4. **MCP Validation**: Cross-check agent tool requirements vs. granted permissions

---

## 🔧 **MCP Configuration**

### **Three-Layer Access Control**

#### **Layer 1: Global Profiles**
Define in `ops/mcp.json`:
```json
{
  "profile": "webdev",
  "include": ["shadcn-ui", "shopify"],
  "exclude": ["applescript"]
}
```

**Available Profiles:**
- `default`: filesystem, git, http, keychain-presence, ccmem
- `webdev`: +shadcn-ui, shopify, cms
- `automation`: +n8n, applescript
- `apple`: +xcodebuild, ios-sim

#### **Layer 2: Capsule Intent**
Capsule-specific include/exclude overrides global profile

#### **Layer 3: Agent Contracts**
Each agent declares required tools in agent definition files

### **MCP Configuration Examples**

**Automation Capsule:**
```json
{
  "profile": "automation",
  "include": ["n8n", "applescript", "filesystem"],
  "exclude": ["shopify", "cms"]
}
```

**Web Development Capsule:**
```json
{
  "profile": "webdev", 
  "include": ["shadcn-ui", "filesystem", "git", "http"],
  "exclude": ["xcodebuild", "ios-sim"]
}
```

**Security-First Capsule:**
```json
{
  "profile": "default",
  "include": ["filesystem", "git"],
  "exclude": ["http", "applescript", "n8n"]
}
```

---

## 🛤️ **Lane & Branch System**

### **Lane Detection Priority**
1. **capsule.json** `lane` field (explicit)
2. **requirements.yaml** `lane` field (fallback)  
3. **standard** (default for safety)

### **Lane-Specific DoD**

#### **Standard Mode DoD**
- ✅ Basic functionality working
- ✅ Minimal documentation (README stub)
- ✅ No critical errors or exceptions
- ⚠️ Manual testing acceptable
- ⚠️ Security review optional

#### **Comprehensive Mode DoD**
- ✅ Production-ready standards
- ✅ Comprehensive documentation & handoff guide
- ✅ >80% test coverage with automated tests
- ✅ Security audit completed
- ✅ Performance benchmarks established
- ✅ Integration tests passing
- ✅ Error handling and logging implemented

### **Branch Routing**
Branch names automatically route to domain specialists:
- `automation/*` → `automation-specialist`
- `web/*` → `frontend-specialist`  
- `ios/*` → `ios-specialist`
- `macos/*` → `macos-specialist`
- `backend/*` → `backend-architect`
- `ops/*` → `devops-troubleshooter`

---

## 📊 **Event Logging & Observability**

### **Standard Event Format**
All events logged to `registry/events.jsonl`:
```json
{
  "timestamp": "2025-08-11T15:57:30.455412",
  "slug": "webapp-deep-test", 
  "event": "capsule_activated",
  "level": "INFO",
  "metadata": {"lane": "standard", "agent": "frontend-specialist"}
}
```

### **Event Types**
- `capsule_activated`: Capsule creation/activation
- `capsule_completed`: Capsule deployment
- `agent_routed`: Agent assignment
- `mcp_granted`: MCP permission granted
- `dod_validated`: DoD check passed/failed
- `build_started`: Build process initiated
- `build_completed`: Build process finished

### **Health Monitoring**
- **Real-time**: `tools/system_health_rollup.py`
- **Daily Summary**: `tools/advisor_rollup.py`
- **Dashboard**: `registry/dashboard/index.html`

---

## 🔐 **Security & Access Control**

### **Principle of Least Privilege**
- Each capsule requests minimal necessary MCP permissions
- Agent tool declarations validated against grants
- Automatic detection of excessive permissions

### **Security by Lane**
- **Standard Mode**: Relaxed controls for rapid iteration
- **Comprehensive Mode**: Full security audit required in DoD

### **Sensitive Data Handling**
- Use `[PRIVATE]` prefix for data that shouldn't persist in MCP memory
- Store secrets in macOS Keychain via `keychain-presence` MCP
- Never commit API keys or credentials to capsule repos

---

## 🧠 **Memory & Context Management**

### **Hybrid Memory Architecture**
- **CLAUDE.md**: Static system context (always loaded)
- **CCMem MCP**: Dynamic memory via builder-memory server
- **Session Context**: `global/session_context.md`
- **System State**: `global/system_state.md`

### **Privacy Controls**
- **Memory Location**: `~/.claude/mcp-data/builder-memory.json`
- **Backup System**: `tools/memory/backup_memory.sh` (10 retention limit)
- **Kill Switch**: `tools/memory/clear_memory.sh` (complete wipe)
- **Private Tag**: `[PRIVATE]` keeps data session-local only

---

## 🚀 **Common Workflows**

### **1. Create Automation Capsule**
```bash
# Fast iteration workflow
python3 tools/trigger_planner.sh instagram-carousel automation standard
cd capsules/instagram-carousel
# Edit spec/requirements.yaml with automation goals
# System auto-routes to automation-specialist with n8n/AppleScript tools
```

### **2. Create Web Application**
```bash
# Production-quality workflow  
python3 tools/trigger_planner.sh portfolio-site web standard
cd capsules/portfolio-site
# System auto-routes to frontend-specialist with React/shadcn-ui tools
# Full DoD validation including security audit and tests
```

### **3. Override Agent Routing**
```bash
# Force security review for standard mode capsule
mkdir -p capsules/my-capsule/.claude/agents/
echo "security-auditor" > capsules/my-capsule/.claude/agents/primary.txt
echo "automation-specialist" > capsules/my-capsule/.claude/agents/secondary.txt
```

### **4. Custom MCP Configuration**
```bash
# Minimal permissions for security-sensitive capsule
cat > capsules/secure-app/ops/mcp.json <<EOF
{
  "profile": "default",
  "include": ["filesystem", "git"],
  "exclude": ["http", "applescript", "n8n", "shopify"]
}
EOF
```

### **5. Monitor System Health**
```bash
# Check current system status
python3 tools/system_health_rollup.py

# View daily audit results  
ls registry/daily/status-*.json

# Open dashboard
open registry/dashboard/index.html
```

---

## 🔧 **Troubleshooting**

### **Agent Routing Issues**
- Check branch naming: `automation/my-task` routes to automation-specialist
- Verify `.claude/agents/` overrides if routing is unexpected
- Review agent tool requirements vs. MCP grants

### **MCP Permission Errors**  
- Check `ops/mcp.json` profile and include/exclude lists
- Verify agent tool declarations match granted permissions
- Use `tools/agents/agent_tools_check.py` for validation

### **DoD Validation Failures**
- Fast lane: Focus on basic functionality
- Deep lane: All quality gates must pass
- Check `spec/requirements.yaml` for lane specification

### **Context/Memory Issues**
- Memory status: `tools/memory/memory_status.sh`
- Reset memory: `tools/memory/clear_memory.sh`
- Backup/restore: `tools/memory/backup_memory.sh`

---

## 📚 **Reference Tables**

### **Template Comparison**
| Template | Lane | Domain | Primary Agent | MCP Profile |
|----------|------|--------|---------------|-------------|
| `automation-starter` | standard | Workflows | automation-specialist | automation |
| `web-dev-starter` | standard | Web Apps | frontend-specialist | webdev |
| `apple-app-starter` | standard | iOS/macOS | ios/macos-specialist | apple |
| `capsule-base` | configurable | Any | branch-based | default |

### **Directory Structure Reference**
```
capsules/my-project/
├── capsule.json           # Capsule metadata, lane specification
├── spec/
│   ├── requirements.yaml  # Project requirements, lane fallback
│   ├── system.md         # Architecture decisions
│   ├── test_plan.md      # Testing strategy
│   └── context.jsonl     # Historical context
├── src/                  # Source code
├── runs/                 # Execution logs, build artifacts
├── ops/
│   └── mcp.json         # MCP configuration
├── docs/                # Documentation
└── .claude/
    └── agents/          # Agent routing overrides
```

---

## 🎯 **Best Practices**

### **Capsule Creation**
1. Choose the right template for your domain
2. Specify lane explicitly in `capsule.json`
3. Configure MCP permissions minimally
4. Document requirements clearly in `spec/requirements.yaml`

### **Development**
1. Trust automatic agent routing unless you have specific needs
2. Override agents only when necessary via `.claude/agents/`
3. Follow lane-appropriate DoD standards
4. Log significant events for observability

### **Security**  
1. Use least privilege MCP configurations
2. Tag sensitive information with `[PRIVATE]`
3. Store secrets in Keychain, not capsule files
4. Run security audits for standard capsules

### **Maintenance**
1. Monitor daily audit results
2. Keep memory backups current
3. Update documentation as system evolves
4. Review event logs for system health

---

This guide provides the foundation for productive Huxley development. Refer to the PROJECT_COMPASS for architectural decisions and strategic direction.