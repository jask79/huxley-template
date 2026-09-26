---
name: apple-provision
description: Automate Apple Developer portal provisioning via App Store Connect REST API. Registers bundle IDs, enables capabilities, manages certificates, and creates provisioning profiles.
when: Setting up a new iOS/macOS app, managing provisioning profiles, registering bundle IDs, creating signing certificates, enabling app capabilities, device registration
allowed-tools:
  - Bash
  - Read
metadata:
  version: "1.0.0"
  authority: "{{ORCHESTRATOR_NAME}}"
  script: "tools/apple_provision.py"
  scope: "Apple Developer portal provisioning automation"
  last_updated: "2026-02-05"
---

# Apple Provision Skill

## Purpose
Automate Apple Developer portal provisioning via the App Store Connect REST API. Replaces manual portal visits for bundle ID registration, capability management, certificate creation, and provisioning profile generation.

**No Fastlane required. No browser automation. Direct REST API.**

## Primary Agents
- **{{ORCHESTRATOR_NAME}}** (authority) — Can invoke directly
- **Mobile Developer** — For iOS app provisioning
- **macOS Dev** — For macOS app provisioning

## Prerequisites

### One-Time Setup (2 minutes)
1. Go to [App Store Connect](https://appstoreconnect.apple.com) > Users and Access > Integrations > Team Keys
2. Click "Generate API Key"
3. Set role to **Admin** (needed for provisioning access)
4. Download the `.p8` file (only downloadable ONCE — save it securely)
5. Note your **Key ID** and **Issuer ID**

### Environment Variables
```bash
export ASC_KEY_ID="YOUR_KEY_ID"           # From step 4 above
export ASC_ISSUER_ID="YOUR_ISSUER_ID"     # From App Store Connect
export ASC_KEY_PATH="/path/to/AuthKey.p8" # Path to downloaded .p8 file
# OR
export ASC_KEY_CONTENT="$(cat /path/to/AuthKey.p8)"  # Raw key content (full PEM text)
```

## Quick Reference

### Full Provisioning (Most Common)
```bash
python3 tools/apple_provision.py provision \
  --app-name "My App" \
  --bundle-id "com.example.myapp" \
  --capabilities push,siwa,app-groups \
  --platform ios
```

This single command:
1. Registers the bundle ID (or finds existing)
2. Enables requested capabilities
3. Creates/reuses signing certificates
4. Creates development + distribution provisioning profiles
5. Downloads and installs profiles locally

### Individual Operations
```bash
# Validate credentials
python3 tools/apple_provision.py preflight

# Bundle IDs
python3 tools/apple_provision.py list-bundle-ids
python3 tools/apple_provision.py register-bundle-id --identifier com.example.myapp --name "My App"

# Certificates
python3 tools/apple_provision.py list-certs
python3 tools/apple_provision.py list-certs --type IOS_DISTRIBUTION
python3 tools/apple_provision.py create-cert --type IOS_DEVELOPMENT

# Provisioning Profiles
python3 tools/apple_provision.py list-profiles
python3 tools/apple_provision.py list-profiles --type IOS_APP_STORE

# Devices
python3 tools/apple_provision.py list-devices
python3 tools/apple_provision.py register-device --name "My iPhone" --udid "00008XXX-XXXX"

# Capabilities
python3 tools/apple_provision.py list-capabilities --bundle-id com.example.myapp
python3 tools/apple_provision.py enable-capability --bundle-id com.example.myapp --capability push
```

### Output Options
```bash
--verbose / -v    # Detailed logging
--json            # JSON output (for programmatic use)
--dry-run         # Show what would happen without making changes
```

## Capability Mapping

| Friendly Name | Apple API Identifier |
|---------------|---------------------|
| `push` | PUSH_NOTIFICATIONS |
| `siwa` | SIGN_IN_WITH_APPLE |
| `app-groups` | APP_GROUPS |
| `icloud` | ICLOUD |
| `healthkit` | HEALTHKIT |
| `homekit` | HOMEKIT |
| `wallet` | WALLET |
| `siri` | SIRI |
| `maps` | MAPS |
| `game-center` | GAME_CENTER |
| `in-app-purchase` | IN_APP_PURCHASE |
| `associated-domains` | ASSOCIATED_DOMAINS |
| `nfc` | NFC_TAG_READING |
| `data-protection` | DATA_PROTECTION |
| `network-extensions` | NETWORK_EXTENSIONS |
| `access-wifi` | ACCESS_WIFI_INFORMATION |
| `autofill-credential` | AUTOFILL_CREDENTIAL_PROVIDER |

Use friendly names with `--capabilities` flag (comma-separated).

## Certificate Types

| Type | When to Use |
|------|------------|
| `IOS_DEVELOPMENT` | Local development builds |
| `IOS_DISTRIBUTION` | App Store + Ad Hoc distribution |
| `MAC_APP_DEVELOPMENT` | macOS development |
| `MAC_APP_DISTRIBUTION` | Mac App Store distribution |
| `MAC_INSTALLER_DISTRIBUTION` | macOS installer packages |
| `DEVELOPER_ID_APPLICATION` | macOS outside App Store |

## Profile Types

| Type | When to Use |
|------|------------|
| `IOS_APP_DEVELOPMENT` | Development builds (includes devices) |
| `IOS_APP_STORE` | App Store submission |
| `IOS_APP_ADHOC` | Ad Hoc distribution (includes devices) |
| `MAC_APP_DEVELOPMENT` | macOS development |
| `MAC_APP_STORE` | Mac App Store submission |
| `MAC_APP_DIRECT` | Developer ID distribution |

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| Missing ASC_KEY_ID | Env var not set | Export env vars per Prerequisites |
| 401 Unauthorized | Expired/invalid key | Verify .p8 file and key ID match |
| 403 Forbidden | Insufficient permissions | API key needs Admin or Developer role |
| 409 Conflict | Resource already exists | Tool handles this automatically (idempotent) |
| Certificate limit | Max 3 distribution certs | Reuse existing or revoke expired ones |

## What This Skill Does NOT Handle

These require the Apple Developer web portal (one-time or infrequent tasks):
- Apple Developer Program enrollment
- Creating the initial API key (.p8)
- Accepting updated license agreements
- Tax and banking information
- APNs authentication keys (use existing or create in portal)
- App Store Connect app record creation (use Fastlane `produce` if needed)

## Companion Skills
- `ios-device-deployment` — Deploy built apps to physical devices
- `ios-testing` — Test apps in simulator
