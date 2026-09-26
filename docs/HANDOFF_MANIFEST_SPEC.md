# Agent Handoff Manifest Specification

**Version:** 1.0.0
**Purpose:** Standardized data format for multi-agent workflows in Huxley

---

## Overview

This specification defines a structured manifest format for agent-to-agent handoffs in iOS development workflows. Each agent produces a manifest that the next agent consumes, enabling deterministic integration without guessing file locations or formats.

## Directory Structure

```
docs/
├── handoffs/                    # Root directory for all handoffs
│   ├── ui-designer/             # UI Designer deliverables
│   │   ├── manifest.json        # UI Designer manifest
│   │   ├── wireframes/          # Text-based wireframes
│   │   ├── screenshots/         # SwiftUI previews screenshots
│   │   └── validation/          # Validation proof-of-work
│   ├── mobile-dev/              # Mobile Dev deliverables
│   │   ├── manifest.json        # Mobile Dev manifest
│   │   ├── screenshots/         # Simulator screenshots
│   │   ├── validation/          # Validation proof-of-work
│   │   └── test-reports/        # Test results
│   └── backend-dev/             # Backend Dev deliverables
│       ├── manifest.json        # Backend Dev manifest
│       └── api-docs/            # API documentation
```

---

## Manifest Format

### Base Manifest Structure

All manifests follow this base structure:

```json
{
  "version": "1.0.0",
  "agent": "ui-designer|mobile-dev|backend-dev",
  "timestamp": "2025-10-27T20:00:00Z",
  "project": {
    "name": "MyApp",
    "scheme": "MyApp",
    "path": "/path/to/project"
  },
  "status": "completed|in_progress|blocked",
  "deliverables": {
    // Agent-specific deliverables
  },
  "validation": {
    // Validation proof-of-work
  },
  "next_agent": "mobile-dev|backend-dev|null"
}
```

---

## UI Designer Manifest

**Location:** `docs/handoffs/ui-designer/manifest.json`

```json
{
  "version": "1.0.0",
  "agent": "ui-designer",
  "timestamp": "2025-10-27T20:00:00Z",
  "project": {
    "name": "MyApp",
    "scheme": "MyApp",
    "path": "/path/to/MyApp.xcodeproj"
  },
  "status": "completed",
  "deliverables": {
    "wireframes": [
      {
        "screen": "LoginView",
        "file": "docs/handoffs/ui-designer/wireframes/login.md",
        "user_flow": "docs/handoffs/ui-designer/wireframes/auth_flow.mermaid"
      },
      {
        "screen": "DashboardView",
        "file": "docs/handoffs/ui-designer/wireframes/dashboard.md",
        "user_flow": "docs/handoffs/ui-designer/wireframes/dashboard_flow.mermaid"
      }
    ],
    "swiftui_views": [
      {
        "view": "LoginView",
        "file": "src/Views/LoginView.swift",
        "preview_screenshot": "docs/handoffs/ui-designer/screenshots/login_preview.png"
      },
      {
        "view": "DashboardView",
        "file": "src/Views/DashboardView.swift",
        "preview_screenshot": "docs/handoffs/ui-designer/screenshots/dashboard_preview.png"
      }
    ],
    "design_system": [
      {
        "file": "src/DesignSystem/Colors.swift",
        "type": "colors"
      },
      {
        "file": "src/DesignSystem/Typography.swift",
        "type": "typography"
      },
      {
        "file": "src/DesignSystem/Spacing.swift",
        "type": "spacing"
      }
    ],
    "animations": [
      {
        "screen": "LoginView",
        "animation": "fade_in",
        "description": "Login button fade-in on appear",
        "spec_file": "docs/handoffs/ui-designer/animations/login_fade_in.md"
      }
    ]
  },
  "validation": {
    "manifest_file": "docs/handoffs/ui-designer/validation/validation_manifest.json",
    "tools_used": ["grid_overlay", "ruler", "color_picker", "device_bezel", "screen_recorder"],
    "results": [
      {
        "screen": "LoginView",
        "grid_compliance": "pass",
        "measurements": "pass",
        "colors": "pass",
        "handoff_screenshot": "docs/handoffs/ui-designer/validation/login_handoff.png",
        "animation_demo": "docs/handoffs/ui-designer/validation/login_animation.gif"
      }
    ],
    "checklist": {
      "wireframes_complete": true,
      "swiftui_implemented": true,
      "grid_verified": true,
      "measurements_verified": true,
      "colors_verified": true,
      "animations_documented": true,
      "handoff_screenshots": true
    }
  },
  "next_agent": "mobile-dev",
  "handoff_notes": "All screens designed and validated. Mobile Dev can proceed with ViewModels and backend integration."
}
```

---

## Mobile Dev Manifest

**Location:** `docs/handoffs/mobile-dev/manifest.json`

```json
{
  "version": "1.0.0",
  "agent": "mobile-dev",
  "timestamp": "2025-10-27T21:00:00Z",
  "project": {
    "name": "MyApp",
    "scheme": "MyApp",
    "path": "/path/to/MyApp.xcodeproj"
  },
  "status": "completed",
  "input_manifest": "docs/handoffs/ui-designer/manifest.json",
  "deliverables": {
    "viewmodels": [
      {
        "viewmodel": "LoginViewModel",
        "file": "src/ViewModels/LoginViewModel.swift",
        "view": "LoginView"
      },
      {
        "viewmodel": "DashboardViewModel",
        "file": "src/ViewModels/DashboardViewModel.swift",
        "view": "DashboardView"
      }
    ],
    "services": [
      {
        "service": "AuthService",
        "protocol": "src/Services/AuthServiceProtocol.swift",
        "mock": "src/Services/MockAuthService.swift",
        "real": "src/Services/RealAuthService.swift",
        "status": "mock_implemented"
      }
    ],
    "api_contract": {
      "file": "docs/handoffs/mobile-dev/api-contract.json",
      "endpoints": [
        {
          "path": "/auth/login",
          "method": "POST",
          "request": {
            "email": "string",
            "password": "string"
          },
          "response": {
            "accessToken": "string",
            "refreshToken": "string",
            "user": {
              "id": "string",
              "name": "string",
              "email": "string"
            }
          },
          "errors": [
            {
              "code": 401,
              "message": "Invalid credentials"
            }
          ]
        }
      ]
    },
    "tests": [
      {
        "file": "tests/ViewModels/LoginViewModelTests.swift",
        "type": "unit",
        "status": "passing",
        "coverage": "95%"
      },
      {
        "file": "tests/Services/MockAuthServiceTests.swift",
        "type": "integration",
        "status": "passing",
        "coverage": "100%"
      },
      {
        "file": "tests/UI/LoginFlowTests.swift",
        "type": "ui",
        "status": "passing",
        "coverage": "90%"
      }
    ]
  },
  "validation": {
    "manifest_file": "docs/handoffs/mobile-dev/validation/validation_manifest.json",
    "build_status": "success",
    "simulator_testing": {
      "status": "success",
      "iterations": 3,
      "devices": ["iPhone 16", "iPhone 16 Pro"],
      "ios_versions": ["iOS 18.0"]
    },
    "design_validation": {
      "tools_used": ["grid_overlay", "ruler", "color_picker", "device_bezel", "screen_recorder"],
      "results": [
        {
          "screen": "LoginView",
          "grid_compliance": "pass",
          "measurements": "pass",
          "colors": "pass",
          "handoff_screenshot": "docs/handoffs/mobile-dev/validation/login_final.png"
        }
      ]
    },
    "test_reports": [
      {
        "report": "docs/handoffs/mobile-dev/test-reports/unit_tests.xml",
        "type": "unit",
        "passed": 45,
        "failed": 0
      },
      {
        "report": "docs/handoffs/mobile-dev/test-reports/ui_tests.xml",
        "type": "ui",
        "passed": 12,
        "failed": 0
      }
    ],
    "checklist": {
      "viewmodels_implemented": true,
      "mock_services_implemented": true,
      "api_contract_defined": true,
      "all_tests_passing": true,
      "design_validated": true,
      "simulator_verified": true,
      "performance_tested": true
    }
  },
  "next_agent": "backend-dev",
  "handoff_notes": "Complete working app with mock APIs. Backend Dev should implement endpoints matching api-contract.json exactly."
}
```

---

## Backend Dev Manifest

**Location:** `docs/handoffs/backend-dev/manifest.json`

```json
{
  "version": "1.0.0",
  "agent": "backend-dev",
  "timestamp": "2025-10-27T22:00:00Z",
  "project": {
    "name": "MyApp API",
    "repository": "https://github.com/org/myapp-api",
    "path": "/path/to/myapp-api"
  },
  "status": "completed",
  "input_manifest": "docs/handoffs/mobile-dev/manifest.json",
  "deliverables": {
    "api_endpoints": [
      {
        "path": "/auth/login",
        "method": "POST",
        "implementation": "src/routes/auth.py",
        "contract_compliance": "exact_match",
        "tests": "tests/test_auth.py"
      }
    ],
    "database_schema": {
      "file": "migrations/001_initial_schema.sql",
      "status": "applied"
    },
    "api_documentation": {
      "file": "docs/handoffs/backend-dev/api-docs/openapi.yaml",
      "format": "OpenAPI 3.0"
    },
    "deployment": {
      "environment": "staging",
      "url": "https://api-staging.myapp.com",
      "status": "deployed"
    }
  },
  "validation": {
    "contract_compliance": {
      "status": "verified",
      "endpoints_matched": 5,
      "endpoints_total": 5
    },
    "integration_tests": {
      "status": "passing",
      "passed": 15,
      "failed": 0,
      "report": "docs/handoffs/backend-dev/test-reports/integration.xml"
    },
    "performance": {
      "endpoint": "/auth/login",
      "avg_response_time_ms": 45,
      "p95_response_time_ms": 120,
      "rps": 500
    },
    "security": {
      "authentication": "JWT",
      "authorization": "RBAC",
      "https": true,
      "rate_limiting": true
    },
    "checklist": {
      "endpoints_implemented": true,
      "contract_matched": true,
      "tests_passing": true,
      "deployed_to_staging": true,
      "security_reviewed": true,
      "performance_tested": true
    }
  },
  "next_agent": null,
  "handoff_notes": "API deployed to staging. Mobile Dev can now swap from MockAuthService to RealAuthService."
}
```

---

## Validation Manifest (Shared Format)

**Location:** `docs/handoffs/{agent}/validation/validation_manifest.json`

```json
{
  "project": "MyApp",
  "agent": "ui-designer|mobile-dev",
  "validations": [
    {
      "timestamp": "2025-10-27T20:00:00Z",
      "iteration": 1,
      "screen": "LoginView",
      "screenshot": "docs/handoffs/ui-designer/screenshots/login_20251027_200000.png",
      "grid_overlay": "docs/handoffs/ui-designer/validation/grid_20251027_200000.png",
      "measurements": [
        {
          "label": "Logo top margin",
          "value": 44,
          "unit": "pt",
          "grid_compliance": "8px grid ✅"
        },
        {
          "label": "Button height",
          "value": 44,
          "unit": "pt",
          "grid_compliance": "8px grid ✅"
        },
        {
          "label": "Input spacing",
          "value": 16,
          "unit": "pt",
          "grid_compliance": "8px grid ✅"
        }
      ],
      "colors": [
        {
          "label": "Primary button",
          "color": "primaryBlue",
          "match": "exact",
          "contrast_ratio": 4.8,
          "wcag_aa": "pass"
        }
      ],
      "device_bezel": "docs/handoffs/ui-designer/validation/handoff_20251027_200000.png",
      "animation_demo": "docs/handoffs/ui-designer/validation/animation_20251027_200000.gif",
      "status": "success"
    }
  ]
}
```

---

## Usage Patterns

### UI Designer → Mobile Dev Handoff

1. **UI Designer creates:**
   - Wireframes in `docs/handoffs/ui-designer/wireframes/`
   - SwiftUI Views in `src/Views/`
   - Design System in `src/DesignSystem/`
   - Validation proof in `docs/handoffs/ui-designer/validation/`
   - Manifest: `docs/handoffs/ui-designer/manifest.json`

2. **Mobile Dev reads:**
   - `docs/handoffs/ui-designer/manifest.json`
   - Auto-discovers all files via manifest
   - No guessing file locations

### Mobile Dev → Backend Dev Handoff

1. **Mobile Dev creates:**
   - Mock Services + Protocol
   - API Contract: `docs/handoffs/mobile-dev/api-contract.json`
   - Tests and validation
   - Manifest: `docs/handoffs/mobile-dev/manifest.json`

2. **Backend Dev reads:**
   - `docs/handoffs/mobile-dev/manifest.json`
   - Implements endpoints matching `api-contract.json` exactly
   - No ambiguity about request/response shapes

### Backend Dev → Mobile Dev (Final Integration)

1. **Backend Dev creates:**
   - API Documentation
   - Staging URL
   - Manifest: `docs/handoffs/backend-dev/manifest.json`

2. **Mobile Dev reads:**
   - `docs/handoffs/backend-dev/manifest.json`
   - Swaps MockAuthService → RealAuthService
   - Updates Config.swift with staging URL

---

## Validation Requirements

### Every Manifest MUST Include:

✅ **version** - Manifest format version (semver)
✅ **agent** - Which agent created this
✅ **timestamp** - When was this created (ISO 8601)
✅ **project** - Project context
✅ **status** - Current status
✅ **deliverables** - What was delivered
✅ **validation** - Proof-of-work
✅ **next_agent** - Who receives this

### Validation Checklist (All Agents):

✅ All file paths in manifest are **absolute or relative to project root**
✅ All referenced files **exist** at time of manifest creation
✅ Manifest is **valid JSON** (no syntax errors)
✅ Status is one of: `completed`, `in_progress`, `blocked`
✅ Checklist in validation section has **all items marked true** (if status = completed)

---

## Tool Integration

### Read Manifest (For Next Agent)

```python
import json

# Mobile Dev reads UI Designer manifest
with open('docs/handoffs/ui-designer/manifest.json') as f:
    ui_manifest = json.load(f)

# Auto-discover all SwiftUI views
for view in ui_manifest['deliverables']['swiftui_views']:
    print(f"View: {view['view']}")
    print(f"File: {view['file']}")
    print(f"Screenshot: {view['preview_screenshot']}")
```

---

## Benefits

### Deterministic Integration

❌ **Before:** "Where did UI Designer put the screenshots?"
✅ **After:** Read manifest → all paths specified

### No Guessing

❌ **Before:** "Is the design system in src/ or DesignSystem/?"
✅ **After:** Manifest specifies exact path

### Validation Built-In

❌ **Before:** "Did UI Designer run the validation tools?"
✅ **After:** Manifest includes validation proof-of-work

### Automated Handoffs

❌ **Before:** Manual coordination between agents
✅ **After:** Next agent auto-reads previous manifest

### Contract Compliance

❌ **Before:** Backend implements different API shape than mobile expects
✅ **After:** api-contract.json is source of truth, verified in both manifests

---

**Version:** 1.0.0
**Status:** Implemented
**Last Updated:** 2025-10-27
