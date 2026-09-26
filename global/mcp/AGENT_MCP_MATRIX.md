# Agent-MCP Matrix

> **Status:** Legacy reference — this matrix predates the current 35-agent roster and names MCP servers that are not in `.mcp.json`. Treat it as a shape to copy, not as the shipped configuration.

This matrix shows which MCP servers each agent can utilize, enabling proper least-privilege access control and capsule configuration.

## Quick Reference

| Agent | Core MCPs | Optional MCPs | Profile Recommendation |
|-------|-----------|---------------|----------------------|
| **automation-specialist** | filesystem, n8n, applescript | git | `automation` |
| **shopify-specialist** | filesystem, shopify | git, http | `webdev` |  
| **frontend-specialist** | filesystem, shadcn-ui | git, http | `webdev` |
| **javascript-pro** | filesystem | git, http, shadcn-ui | `default` |
| **backend-architect** | filesystem, git | http | `default` |
| **devops-troubleshooter** | filesystem, git | http, ccmem | `default` |
| **deployment-engineer** | filesystem, git | http | `default` |
| **security-auditor** | filesystem | git, http | `default` |
| **test-automator** | filesystem | git, http | `default` |
| **python-pro** | filesystem | git, http | `default` |
| **code-reviewer** | filesystem, git | http | `default` |
| **iOS Dev** | filesystem, shadcn-ui | git, xcodebuild, ios-sim, snap-happy | `apple` |
| **macos-specialist** | filesystem | git, xcodebuild | `apple` |
| **data-analyst** | filesystem | git, http | `default` |
| **backend-specialist** | filesystem, git, context7 | supabase | `default` |
| **ui-ux-designer** | filesystem, builder-memory, context7 | shadcn-ui | `design` |

## Detailed Agent-MCP Mappings

### 🔧 Automation Agents

#### **automation-specialist**
- **Core MCPs**: `filesystem`, `n8n`, `applescript`
- **Use Case**: n8n workflow creation, macOS automation
- **Profile**: `automation`
- **Notes**: Requires both n8n and applescript for full functionality

### 🌐 Web Development Agents  

#### **shopify-specialist**
- **Core MCPs**: `filesystem`, `shopify`
- **Optional MCPs**: `git`, `http`
- **Use Case**: Shopify theme development, store management
- **Profile**: `webdev`
- **Notes**: Shopify MCP required for theme deployment

#### **shadcn-ui-server**
- **Server**: `shadcn-ui` (available in `webdev` profile)
- **Purpose**: Access to shadcn/ui component source code, demos, and metadata
- **Compatible Agents**: `frontend-specialist`, `javascript-pro`
- **Use Cases**: React component development, UI library integration
- **Notes**: Provides component source, examples, and documentation for shadcn/ui

#### **frontend-specialist (web)**
- **Core MCPs**: `filesystem`, `shadcn-ui`
- **Optional MCPs**: `git`, `http`
- **Use Case**: Modern React/Next.js frontend development with shadcn/ui components
- **Profile**: `webdev`
- **Notes**: shadcn-ui MCP provides direct access to component library source code and examples

#### **javascript-pro**  
- **Core MCPs**: `filesystem`
- **Optional MCPs**: `git`, `http`, `shadcn-ui`
- **Use Case**: Modern JavaScript/Node.js development, React component development
- **Profile**: `default`

### 🏗️ Backend & Infrastructure Agents

#### **backend-architect**
- **Core MCPs**: `filesystem`, `git`
- **Optional MCPs**: `http`
- **Use Case**: API design, database schema, system architecture  
- **Profile**: `default`
- **Notes**: Git integration for code repository management

#### **devops-troubleshooter**
- **Core MCPs**: `filesystem`, `git`
- **Optional MCPs**: `http`, `ccmem`
- **Use Case**: Production debugging, log analysis
- **Profile**: `default`
- **Notes**: May benefit from memory system for incident tracking

#### **deployment-engineer**
- **Core MCPs**: `filesystem`, `git`  
- **Optional MCPs**: `http`
- **Use Case**: CI/CD, Docker, Infrastructure as Code
- **Profile**: `default`
- **Notes**: Git essential for pipeline configuration

### 🛡️ Security & Quality Agents

#### **security-auditor**
- **Core MCPs**: `filesystem`
- **Optional MCPs**: `git`, `http`
- **Use Case**: OWASP compliance, vulnerability assessment
- **Profile**: `default`
- **Lane**: `standard` (enhanced security requirements)

#### **test-automator**
- **Core MCPs**: `filesystem`
- **Optional MCPs**: `git`, `http`  
- **Use Case**: Comprehensive test suites, CI integration
- **Profile**: `default`
- **Lane**: Both `standard` and `standard`

#### **code-reviewer**
- **Core MCPs**: `filesystem`, `git`
- **Optional MCPs**: `http`
- **Use Case**: Code quality analysis, security review, best practices enforcement
- **Profile**: `default`  
- **Lane**: Primarily `standard` (comprehensive reviews)

### 🍎 Apple Development Agents

#### **iOS Dev**
- **Core MCPs**: `filesystem`, `shadcn-ui`
- **Optional MCPs**: `git`, `xcodebuild`, `ios-sim`, `snap-happy`
- **Use Case**: Native iOS app development with comprehensive UI/UX design
- **Profile**: `apple`
- **Notes**: Apple-specific tools for build/deploy + UI component libraries for mobile-first design

#### **macos-specialist**  
- **Core MCPs**: `filesystem`
- **Optional MCPs**: `git`, `xcodebuild`
- **Use Case**: Native macOS app development
- **Profile**: `apple`
- **Notes**: Xcode integration for Mac apps

### 💻 Language Specialists

#### **python-pro**
- **Core MCPs**: `filesystem`
- **Optional MCPs**: `git`, `http`
- **Use Case**: Advanced Python development, async patterns
- **Profile**: `default`

#### **data-analyst**
- **Core MCPs**: `filesystem`
- **Optional MCPs**: `git`, `http`
- **Use Case**: Data analysis, visualization, ML pipelines
- **Profile**: `default`

#### **backend-specialist**
- **Core MCPs**: `filesystem`, `git`, `context7`
- **Optional MCPs**: `supabase`
- **Use Case**: Backend API development, database design, Supabase integration
- **Profile**: `default`
- **Notes**: Context7 provides language/framework expertise; Supabase MCP for database work
- **Specializations**:
  - RESTful API design and implementation
  - PostgreSQL/Supabase schema design and migrations
  - Row Level Security (RLS) policy architecture
  - TypeScript type generation from database schemas
  - Backend performance optimization and scaling

### 🎨 Design Agents

#### **ui-ux-designer**
- **Core MCPs**: `filesystem`, `builder-memory`, `context7`
- **Optional MCPs**: `shadcn-ui`
- **Use Case**: User research, wireframes, design systems, component specifications
- **Profile**: `design`
- **Notes**: Uses 🎨 gen-ui output style for visual deliverables; Context7 for researching UI libraries
- **Specializations**:
  - User-centered design and research
  - Design system creation (colors, typography, spacing, components)
  - Accessibility standards (WCAG 2.1 AA)
  - Interactive prototypes with gen-ui output style
  - Handoff documentation for Frontend/Mobile/macOS Dev
  - Figma Community research for design workflow

## MCP Profile Recommendations

### **default** Profile
**MCPs**: `filesystem`, `git`, `http`, `keychain-presence`, `ccmem`
**Best For**: General development, backend services, security analysis, testing
**Agents**: 8 agents use this profile

### **automation** Profile  
**MCPs**: default + `n8n`
**Best For**: Workflow automation, process optimization
**Agents**: `automation-specialist`

### **webdev** Profile
**MCPs**: default + `shopify`, `cms`  
**Best For**: E-commerce development, CMS integration
**Agents**: `shopify-specialist`

### **apple** Profile
**MCPs**: default + `xcodebuild`, `ios-sim`, `shadcn-ui`, `snap-happy`
**Best For**: iOS/macOS app development with comprehensive UI/UX design
**Agents**: `iOS Dev`, `macos-specialist`

### **design** Profile
**MCPs**: default + `context7`, `shadcn-ui` (optional)
**Best For**: UI/UX design work, design systems, component specifications
**Agents**: `ui-ux-designer`

## Least Privilege Validation

### Excessive MCP Grant Patterns

**⚠️ Common Over-Grants:**
- Granting `n8n` to non-automation capsules
- Providing `shopify` access to backend-only projects
- Including `apple` tools for web development
- Exposing `xcodebuild` to data analysis projects

### **Validation Rules**
1. **Agent Declaration Match**: Warn if capsule grants MCP not declared in any active agent
2. **Profile Alignment**: Suggest appropriate profile based on detected agents
3. **Unused Grant Detection**: Flag MCPs granted but not needed by any agent
4. **Security Boundary**: Ensure standard projects don't over-grant to standard agents

### **Planner Integration**
The planner system validates MCP grants against agent needs:
```bash
WARN slug=example msg=excessive_mcp_grants=["shopify","n8n"] agents_need=["filesystem","git"]
```

## Best Practices

### **Capsule Configuration**
1. **Start Minimal**: Begin with `default` profile, add only needed MCPs
2. **Agent-Driven**: Configure MCPs based on agents your capsule actually uses  
3. **Profile Selection**: Choose profile that matches your primary use case
4. **Explicit Override**: Use `include`/`exclude` for specific customizations

### **Security Guidelines**  
- **Automation Isolation**: Don't grant `n8n` unless building workflows
- **Production Boundaries**: Limit sensitive MCPs in production environments
- **Audit Trail**: Monitor MCP usage patterns in planner logs
- **Regular Review**: Periodically audit MCP grants vs actual agent usage

This matrix enables precise MCP access control while maintaining Huxley's principle of least privilege.