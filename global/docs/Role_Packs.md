# Huxley Role Packs

**Version:** 1.0  
**Last Updated:** 2025-08-11  
**Purpose:** Standardized domain configurations for single-command capsule creation

> **Status:** Design document — `tools/create_role_pack.py` is not implemented in this template. Create capsules with `python3 tools/capsule_creator.py` and treat this file as the spec if you build the generator.

---

## 🎯 **Role Pack Overview**

Role packs bundle together:
- **Default Agents**: Domain-specific specialist routing
- **MCP Mappings**: Pre-configured tool access profiles  
- **Capsule Templates**: Pre-scaffolded directory structures
- **DoD Presets**: Lane-appropriate quality gates
- **Security Defaults**: Least-privilege access controls

---

## 🤖 **Automation Role Pack**

**Target Use Cases:** n8n workflows, AppleScript automation, macOS productivity, data processing pipelines

### **Default Configuration**
```json
{
  "pack_name": "automation",
  "lane_default": "standard",
  "primary_agent": "automation-specialist",
  "secondary_agents": ["python-pro", "javascript-pro"],
  "mcp_profile": "automation",
  "template": "automation-starter"
}
```

### **Agent Routing**
- **Primary**: `automation-specialist` (n8n, AppleScript, macOS workflows)
- **Secondary**: `python-pro` (data processing, API integration)
- **Comprehensive Mode Addition**: `code-reviewer` (quality assurance)

### **MCP Access Profile**
```json
{
  "base_profile": "automation",
  "included_tools": [
    "filesystem",
    "git", 
    "applescript",
    "n8n",
    "http",
    "keychain-presence"
  ],
  "excluded_tools": [
    "xcodebuild",
    "ios-sim", 
    "shadcn-ui",
    "shopify"
  ]
}
```

### **Template Structure**
```
automation-starter/
├── capsule.json          # lane: "standard", branch: "automation"
├── spec/
│   ├── requirements.yaml # automation-focused requirements template
│   └── workflow_spec.md  # n8n/AppleScript workflow documentation
├── src/
│   ├── workflows/        # n8n JSON exports
│   ├── scripts/          # AppleScript/shell scripts
│   └── config/          # Environment configuration
├── runs/                # Execution logs, test runs
├── ops/
│   └── mcp.json        # automation profile, minimal permissions
└── docs/
    └── automation_guide.md
```

### **DoD Presets**
- **Standard Mode**: Basic workflow functionality, manual testing, minimal docs
- **Comprehensive Mode**: Error handling, logging, automated tests, security review

### **Single Command Creation**
```bash
python3 tools/create_role_pack.py automation my-workflow-name [standard|standard]
```

---

## 🍎 **Apple Apps Role Pack**  

**Target Use Cases:** iOS apps, macOS applications, Swift/SwiftUI development, App Store deployment

### **Default Configuration**
```json
{
  "pack_name": "apple",
  "lane_default": "standard",
  "primary_agent": "ios-specialist", 
  "secondary_agents": ["macos-specialist", "security-auditor"],
  "mcp_profile": "apple",
  "template": "apple-app-starter"
}
```

### **Agent Routing**
- **Primary**: `ios-specialist` (Swift, SwiftUI, iOS development)
- **Secondary**: `macos-specialist` (AppKit, macOS applications)
- **Always Included**: `security-auditor`, `test-automator` (App Store requirements)

### **MCP Access Profile**
```json
{
  "base_profile": "apple",
  "included_tools": [
    "filesystem",
    "git",
    "xcodebuild", 
    "ios-sim",
    "keychain-presence",
    "http"
  ],
  "excluded_tools": [
    "n8n",
    "applescript",
    "shadcn-ui",
    "shopify"
  ]
}
```

### **Template Structure**
```
apple-app-starter/
├── capsule.json          # lane: "standard", branch: "ios"
├── spec/
│   ├── requirements.yaml # iOS/macOS app requirements
│   ├── app_architecture.md
│   └── app_store_checklist.md
├── src/
│   ├── iOS/             # iOS app source
│   ├── macOS/           # macOS app source (if applicable)
│   ├── Shared/          # Shared Swift code
│   └── Tests/           # Unit and UI tests
├── runs/                # Build logs, test results
├── ops/
│   ├── mcp.json        # apple profile
│   └── ci_config.yml   # GitHub Actions for iOS
└── docs/
    ├── development_guide.md
    └── deployment_guide.md
```

### **DoD Presets**
- **Standard Mode**: Basic app functionality, manual testing, App Store guidelines check
- **Comprehensive Mode**: Full test suite, performance profiling, security audit, App Store compliance

### **Single Command Creation**
```bash
python3 tools/create_role_pack.py apple my-ios-app [ios|macos] [standard|standard]
```

---

## 🌐 **Web Development Role Pack**

**Target Use Cases:** React applications, Next.js websites, full-stack web development, e-commerce

### **Default Configuration**
```json
{
  "pack_name": "webdev",
  "lane_default": "standard",
  "primary_agent": "frontend-specialist",
  "secondary_agents": ["backend-architect", "javascript-pro"],
  "mcp_profile": "webdev", 
  "template": "web-dev-starter"
}
```

### **Agent Routing**
- **Primary**: `frontend-specialist` (React, shadcn/ui, responsive design)
- **Secondary**: `backend-architect` (APIs, database design)
- **Comprehensive Mode Addition**: `security-auditor`, `test-automator`, `deployment-engineer`

### **MCP Access Profile**
```json
{
  "base_profile": "webdev",
  "included_tools": [
    "filesystem",
    "git",
    "http",
    "shadcn-ui",
    "shopify",
    "cms",
    "keychain-presence"
  ],
  "excluded_tools": [
    "applescript", 
    "n8n",
    "xcodebuild",
    "ios-sim"
  ]
}
```

### **Template Structure**
```
web-dev-starter/
├── capsule.json          # lane: "standard", branch: "web"
├── spec/
│   ├── requirements.yaml # web app requirements
│   ├── ui_mockups.md
│   ├── api_specification.md
│   └── deployment_plan.md
├── src/
│   ├── frontend/         # React/Next.js application
│   ├── backend/          # API server (if full-stack)
│   ├── shared/           # Shared utilities, types
│   └── tests/            # Frontend and API tests
├── runs/                # Build outputs, deployment logs
├── ops/
│   ├── mcp.json        # webdev profile
│   ├── docker-compose.yml
│   └── deployment/      # Vercel/Netlify configurations
└── docs/
    ├── user_guide.md
    └── technical_documentation.md
```

### **DoD Presets**
- **Standard Mode**: Working prototype, basic responsiveness, manual testing
- **Comprehensive Mode**: Production deployment, accessibility compliance, performance optimization, security headers

### **Single Command Creation**
```bash
python3 tools/create_role_pack.py webdev my-website [frontend|fullstack] [standard|standard]
```

---

## 🔧 **Role Pack Implementation**

### **Create Role Pack Script**
Create `tools/create_role_pack.py`:

```python
#!/usr/bin/env python3
"""
Single-command role pack capsule creation
Usage: python3 create_role_pack.py <pack> <name> [variant] [lane]
"""
import sys, json, shutil
from pathlib import Path

ROLE_PACKS = {
    "automation": {
        "template": "automation-starter",
        "agents": ["automation-specialist", "python-pro"],
        "mcp_profile": "automation", 
        "default_lane": "standard"
    },
    "apple": {
        "template": "apple-app-starter", 
        "agents": ["ios-specialist", "macos-specialist", "security-auditor"],
        "mcp_profile": "apple",
        "default_lane": "standard"
    },
    "webdev": {
        "template": "web-dev-starter",
        "agents": ["frontend-specialist", "backend-architect", "javascript-pro"], 
        "mcp_profile": "webdev",
        "default_lane": "standard"
    }
}

def create_capsule_from_pack(pack_name, capsule_name, variant=None, lane=None):
    pack = ROLE_PACKS.get(pack_name)
    if not pack:
        print(f"Unknown role pack: {pack_name}")
        return False
        
    # Use role pack defaults
    template = pack["template"]
    agents = pack["agents"]
    mcp_profile = pack["mcp_profile"] 
    lane = lane or pack["default_lane"]
    
    # Call existing template system with role pack configuration
    # This would integrate with existing trigger_planner.sh
    print(f"Creating {pack_name} capsule '{capsule_name}' in {lane}")
    print(f"Template: {template}, Agents: {agents}, MCP: {mcp_profile}")
    
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: create_role_pack.py <pack> <name> [variant] [lane]")
        sys.exit(1)
        
    pack_name = sys.argv[1]
    capsule_name = sys.argv[2] 
    variant = sys.argv[3] if len(sys.argv) > 3 else None
    lane = sys.argv[4] if len(sys.argv) > 4 else None
    
    create_capsule_from_pack(pack_name, capsule_name, variant, lane)
```

### **Integration with Existing System**
Role packs integrate with existing Huxley infrastructure:
- **Templates**: Extend current template system
- **Agent Routing**: Use existing agent routing logic
- **MCP Profiles**: Leverage current MCP configuration system
- **DoD Validation**: Apply existing lane-specific quality gates

### **Command Examples**
```bash
# Quick automation workflow
python3 tools/create_role_pack.py automation instagram-scraper standard

# Production iOS app  
python3 tools/create_role_pack.py apple expense-tracker ios standard

# Full-stack web application
python3 tools/create_role_pack.py webdev portfolio-site fullstack standard
```

---

## 🔐 **Security Defaults by Role**

### **Automation Pack Security**
- **Standard Mode**: Filesystem + git + http only
- **Comprehensive Mode**: Add security audit, code review
- **Restricted**: No iOS tools, no e-commerce tools

### **Apple Pack Security**  
- **Standard Mode**: Development tools only, no network access
- **Comprehensive Mode**: Full toolchain, mandatory security audit
- **Restricted**: No automation tools, no web tools

### **Web Development Pack Security**
- **Standard Mode**: Frontend tools + http, no server access
- **Comprehensive Mode**: Full stack + deployment, security headers required
- **Restricted**: No system automation, no iOS tools

---

## 📊 **Role Pack Metrics**

Each role pack tracks:
- **Creation Time**: Target <60 seconds from command to working capsule
- **Success Rate**: Percentage of successful deployments
- **DoD Compliance**: Lane-specific quality gate pass rates
- **Agent Routing Accuracy**: Correct specialist assignment
- **Security Incidents**: Access control violations

---

This role pack system enables **single-command capsule creation** with domain-appropriate defaults while maintaining Huxley's flexibility and security principles.