# Huxley Tools Directory

**Purpose:** Centralized collection of tools that power the Huxley system's "build everything" mission.

## Quick Reference

### 🎯 **Most Used Tools**
- `bs.py` - Capsule versioning and history (checkpoint/diff/restore)

### 🏗️ **Core Operations**
| Tool | Purpose | Usage |
|------|---------|-------|
| `bs.py` | Capsule versioning, checkpoints and restore | `python3 tools/bs.py status` |
| `intelligent_builder.py` | Core building logic | Imported by other tools |
| `capsule_pipeline_engine.py` | Capsule lifecycle | Imported by other tools |

### 📦 **Capsule Management**
| Tool | Purpose |
|------|---------|
| `validate_capsules.sh` | Verify capsule integrity |
| `standardize_capsules.sh` | Apply consistent structure |

### 🔐 **Security & Secrets**
| Tool | Purpose |
|------|---------|
| `secretctl.py` | Env-var secret presence checks (has / get / preflight) |
| `scan_secrets.sh` | Detect exposed secrets |
| `preflight_secrets.sh` | Pre-deployment security checks |

### 🧠 **Memory & Context**
| Tool | Purpose |
|------|---------|
| `memory/memory_status.sh` | Check MCP memory health |
| `memory/backup_memory.sh` | Export memory data |
| `memory/clear_memory.sh` | Reset memory (kill-switch) |
| `memory/setup_memory.sh` | Initialize memory system |

### 🔧 **System Maintenance**
| Tool | Purpose |
|------|---------|
| `fix_perms.sh` | Repair file permissions |
| `snapshot.sh` | Create system snapshots |

### 🔌 **MCP Integration**
| Tool | Purpose |
|------|---------|
| `mcp_audit.sh` | MCP server health check |
| `mcp_auto_configurator.py` | Auto-configure MCP servers |
| `consolidate_mcps.py` | Merge MCP configurations |

### 📊 **Analytics & Monitoring**
| Tool | Purpose |
|------|---------|
| `performance_analytics.py` | Performance monitoring |
| `cost_optimizer.py` | Resource optimization |
| `system_health_rollup.py` | Health metrics |

### 🚀 **Agent Framework**
| Tool | Purpose |
|------|---------|
| `unified_knowledge_graph.py` | Knowledge management |

## 🚦 **Usage Guidelines**

### **Before Running Any Tool:**
1. Ensure `CATALYST_ROOT` environment variable is set
2. Run from Huxley root directory: `{{CATALYST_ROOT}}`
3. Check tool permissions: `chmod +x tool_name.sh`

### **Common Patterns:**
```bash
# Set environment
export CATALYST_ROOT="{{CATALYST_ROOT}}"
cd $CATALYST_ROOT



# Check system health
./tools/memory/memory_status.sh
```

### **Tool Dependencies:**
- **Python tools**: Require Python 3.8+, may need `pip install -r requirements.txt`
- **Shell scripts**: Require bash, jq, and other standard Unix tools  
- **MCP tools**: Require active MCP server configuration

## 🔄 **Maintenance Notes**

### **Weekly Tasks:**
- Clean up backup files with `find tools/ -name "*.backup" -delete`
- Review `tools/*.log` files for issues

### **Monthly Tasks:**
- Reorganize tools directory (planned improvement)
- Update documentation for new tools
- Archive obsolete tools

## 📝 **Contributing New Tools**

### **Naming Convention:**
- **Python scripts**: `tool_name.py` 
- **Shell scripts**: `tool_name.sh`
- **Executable**: Always set `chmod +x`

### **Required Headers:**
```python
#!/usr/bin/env python3
"""
Tool description and purpose
"""
from common.logger import setup_logging
logger = setup_logging("tool_name")
```

```bash
#!/bin/bash
# Tool description and purpose
set -e
```

### **Documentation:**
- Add tool to this README
- Include usage examples
- Document dependencies
- Add to appropriate category

---

*Last updated: $(date) - Auto-generated from Huxley audit*