# Huxley MCP Security Baseline

**Version:** 1.0  
**Last Updated:** 2025-08-11  
**Purpose:** Codified baseline access controls for each role type with security-first defaults

> **Status:** Aspirational baseline — the helper scripts named below (`tools/emergency_mcp_disable.sh`, `tools/validate_mcp_security.py`, `tools/daily_audit.sh`) are not implemented in this template; treat the phase checklists as a to-do list, not shipped features.

---

## 🎯 **Security Principles**

### **1. Least Privilege**
- Each role gets minimal necessary permissions
- No "kitchen sink" access grants
- Explicit deny takes precedence over implicit allow

### **2. Lane-Based Security**
- **Standard Mode**: Relaxed for rapid iteration, basic safety nets
- **Comprehensive Mode**: Strict controls, mandatory security audit

### **3. Defense in Depth**
- Global profile controls (base permissions)
- Capsule-level overrides (fine-tuning)  
- Agent validation (tool requirement checking)

---

## 🔐 **Role-Based Access Control Matrix**

### **Automation Role Pack**

#### **Standard Mode Defaults**
```json
{
  "profile": "automation_fast",
  "required_tools": [
    "filesystem"
  ],
  "allowed_tools": [
    "git",
    "applescript", 
    "n8n",
    "http"
  ],
  "restricted_tools": [
    "xcodebuild",
    "ios-sim",
    "shadcn-ui", 
    "shopify",
    "deployment-tools"
  ],
  "security_controls": {
    "network_access": "limited",
    "file_write_scope": "capsule_only",
    "system_access": "applescript_only"
  }
}
```

#### **Comprehensive Mode Defaults**
```json
{
  "profile": "automation_deep",
  "required_tools": [
    "filesystem",
    "git"
  ],
  "allowed_tools": [
    "applescript",
    "n8n", 
    "http",
    "keychain-presence"
  ],
  "restricted_tools": [
    "xcodebuild",
    "ios-sim",
    "shadcn-ui",
    "shopify"
  ],
  "security_controls": {
    "network_access": "audited",
    "file_write_scope": "capsule_only", 
    "system_access": "sandboxed",
    "mandatory_reviews": ["security-auditor", "code-reviewer"]
  }
}
```

---

### **Web Development Role Pack**

#### **Standard Mode Defaults**
```json
{
  "profile": "webdev_fast", 
  "required_tools": [
    "filesystem"
  ],
  "allowed_tools": [
    "git",
    "http",
    "shadcn-ui"
  ],
  "restricted_tools": [
    "applescript",
    "n8n",
    "xcodebuild",
    "ios-sim",
    "deployment-tools"
  ],
  "security_controls": {
    "network_access": "frontend_only",
    "file_write_scope": "src_directory",
    "deployment": "manual_only"
  }
}
```

#### **Comprehensive Mode Defaults**  
```json
{
  "profile": "webdev_deep",
  "required_tools": [
    "filesystem",
    "git", 
    "http"
  ],
  "allowed_tools": [
    "shadcn-ui",
    "shopify",
    "cms",
    "keychain-presence"
  ],
  "restricted_tools": [
    "applescript",
    "n8n",
    "xcodebuild", 
    "ios-sim"
  ],
  "security_controls": {
    "network_access": "full_stack",
    "file_write_scope": "project_tree",
    "deployment": "ci_cd_pipeline",
    "mandatory_reviews": ["security-auditor"],
    "security_headers": "required",
    "dependency_scanning": "required"
  }
}
```

---

### **Apple Apps Role Pack**

#### **Standard Mode Defaults**
```json
{
  "profile": "apple_fast",
  "required_tools": [
    "filesystem"
  ], 
  "allowed_tools": [
    "git",
    "xcodebuild",
    "ios-sim"
  ],
  "restricted_tools": [
    "applescript",
    "n8n", 
    "http",
    "shadcn-ui",
    "shopify"
  ],
  "security_controls": {
    "network_access": "none",
    "file_write_scope": "src_directory", 
    "signing": "development_only"
  }
}
```

#### **Comprehensive Mode Defaults**
```json
{
  "profile": "apple_deep",
  "required_tools": [
    "filesystem",
    "git",
    "xcodebuild"
  ],
  "allowed_tools": [
    "ios-sim",
    "keychain-presence"
  ],
  "restricted_tools": [
    "applescript", 
    "n8n",
    "shadcn-ui",
    "shopify"
  ],
  "security_controls": {
    "network_access": "https_only",
    "file_write_scope": "project_tree",
    "signing": "distribution_ready",
    "mandatory_reviews": ["security-auditor", "test-automator"],
    "app_store_compliance": "required",
    "privacy_manifest": "required"
  }
}
```

---

## ⚠️ **High-Risk Tool Classifications**

### **Tier 1: System Level (Highest Risk)**
- `applescript`: Full macOS automation capabilities
- `filesystem`: File system read/write access
- `keychain-presence`: Access to stored secrets

**Control Requirements:**
- Explicit grant required
- Audit trail mandatory
- Lane-specific restrictions

### **Tier 2: Network Access (High Risk)**  
- `http`: Outbound network requests
- `shopify`: E-commerce platform access
- `cms`: Content management systems

**Control Requirements:**
- Network activity logging
- Endpoint validation
- Rate limiting

### **Tier 3: Development Tools (Medium Risk)**
- `xcodebuild`: iOS/macOS compilation
- `ios-sim`: iOS simulator control
- `git`: Version control operations

**Control Requirements:**
- Scope validation
- Repository access controls

### **Tier 4: UI Frameworks (Lower Risk)**
- `shadcn-ui`: UI component library
- `n8n`: Workflow automation platform

**Control Requirements:**
- Usage monitoring
- Template validation

---

## 🛡️ **Security Controls Implementation**

### **MCP Profile Enforcement**
Create enforced profile configurations at `{{CATALYST_ROOT}}/global/security/mcp_profiles/`:

```bash
# Automation Standard Mode Profile
cat > automation_fast.json <<EOF
{
  "name": "automation_fast",
  "base_profile": "default", 
  "include": ["filesystem", "git", "applescript", "n8n", "http"],
  "exclude": ["xcodebuild", "ios-sim", "shadcn-ui", "shopify"],
  "max_concurrent_requests": 10,
  "audit_level": "basic"
}
EOF
```

### **Automatic Validation Script**
Create `tools/validate_mcp_security.py`:

```python
#!/usr/bin/env python3
"""
MCP Security Baseline Validator
Checks capsule MCP configurations against security baselines
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

class MCPSecurityValidator:
    def __init__(self):
        self.base_dir = Path("{{CATALYST_ROOT}}")
        self.security_dir = self.base_dir / "global" / "security" / "mcp_profiles"
        
    def load_security_baseline(self, role: str, lane: str) -> Dict:
        """Load security baseline for role and lane"""
        profile_name = f"{role}_{lane}"
        profile_file = self.security_dir / f"{profile_name}.json"
        
        if profile_file.exists():
            with open(profile_file) as f:
                return json.load(f)
        return {}
    
    def validate_capsule_mcp(self, capsule_path: Path) -> Tuple[bool, List[str]]:
        """Validate capsule MCP config against baseline"""
        mcp_file = capsule_path / "ops" / "mcp.json"
        violations = []
        
        if not mcp_file.exists():
            return True, ["No MCP config found - using defaults"]
            
        with open(mcp_file) as f:
            mcp_config = json.load(f)
            
        # Detect role and lane from capsule
        role = self.detect_role(capsule_path)
        lane = self.detect_lane(capsule_path)
        
        baseline = self.load_security_baseline(role, lane)
        if not baseline:
            return True, ["No security baseline found"]
            
        # Check for excessive permissions
        granted_tools = set(mcp_config.get("include", []))
        restricted_tools = set(baseline.get("restricted_tools", []))
        
        violations_found = granted_tools.intersection(restricted_tools)
        for tool in violations_found:
            violations.append(f"Restricted tool granted: {tool}")
            
        return len(violations) == 0, violations
        
    def detect_role(self, capsule_path: Path) -> str:
        """Detect role from capsule structure"""
        # Implementation would analyze capsule.json, branch, etc.
        return "automation"  # Placeholder
        
    def detect_lane(self, capsule_path: Path) -> str:
        """Detect lane from capsule configuration"""
        # Implementation would check capsule.json, requirements.yaml
        return "standard"  # Placeholder

if __name__ == "__main__":
    validator = MCPSecurityValidator()
    # Validate all production capsules
    capsules_dir = Path("{{CATALYST_ROOT}}") / "capsules"
    
    for capsule_path in capsules_dir.iterdir():
        if capsule_path.is_dir():
            valid, violations = validator.validate_capsule_mcp(capsule_path)
            status = "✅ PASS" if valid else "❌ FAIL"
            print(f"{status} {capsule_path.name}")
            for violation in violations:
                print(f"  - {violation}")
```

### **Daily Security Audit Integration**
Add to `tools/daily_audit.sh`:

```bash
# STEP: MCP Security Validation
log_step "STEP: Validating MCP security baselines"
if [[ -f "$TOOLS_DIR/validate_mcp_security.py" ]]; then
    python3 "$TOOLS_DIR/validate_mcp_security.py" >> "$LOG_FILE" 2>&1 || \
        log_step "⚠️ MCP security violations found"
else
    log_step "⚠️ MCP security validator not found"
fi
```

---

## 📊 **Security Metrics & Monitoring**

### **Key Security Indicators**
- **Over-Privileged Capsules**: Count of capsules with excessive MCP grants
- **Baseline Violations**: Capsules failing security baseline checks
- **Audit Coverage**: Percentage of standard capsules with security review
- **Tool Usage Patterns**: Anomalous tool access patterns

### **Security Dashboard Widgets**
Add to Huxley dashboard:
- MCP permission heat map by role/lane
- Security violation trends over time
- High-risk tool usage statistics  
- Compliance rate by capsule type

### **Alerting Thresholds**
- **Critical**: Tier 1 tools granted in standard without explicit approval
- **Warning**: Tier 2 tools granted without audit trail
- **Info**: New tool types introduced without baseline update

---

## 🚨 **Incident Response**

### **Security Violation Response**
1. **Immediate**: Revoke excessive permissions  
2. **Investigation**: Review audit logs for misuse
3. **Remediation**: Update capsule MCP configuration
4. **Prevention**: Strengthen baseline controls

### **Emergency Access Procedures**
- **Kill Switch**: Disable all MCP servers (`tools/emergency_mcp_disable.sh`)
- **Audit Mode**: Enable comprehensive logging for investigation
- **Restoration**: Validated step-by-step re-enablement

---

## 📋 **Implementation Checklist**

### **Phase 1: Foundation** ✅
- [x] Document security baselines per role/lane
- [x] Create MCP profile templates  
- [x] Define tool risk classifications

### **Phase 2: Enforcement** 
- [ ] Create security profile JSON files
- [ ] Implement validation script
- [ ] Integrate with daily audit
- [ ] Add security dashboard widgets

### **Phase 3: Monitoring**
- [ ] Set up alerting thresholds
- [ ] Create security metrics collection
- [ ] Implement incident response procedures
- [ ] Regular security baseline reviews

---

This security baseline ensures Huxley operates with appropriate access controls while maintaining development velocity through lane-appropriate restrictions.