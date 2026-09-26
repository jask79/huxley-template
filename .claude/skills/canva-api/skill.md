# Canva Connect API CLI

**Tool:** `tools/canva_api.py`
**Version:** 0.1.0
**Dependencies:** Python stdlib only (no pip packages)
**Token store:** `~/.canva-catalyst/tokens.json` (600 permissions)

## Overview

Full-coverage CLI for the Canva Connect API (12 groups, 43 subcommands). Covers designs, exports, imports, assets, brand templates, autofill, comments, folders, resize, editing transactions, and user management. OAuth 2.0 with PKCE authentication. Colored terminal output with `--json` machine-readable mode.

## Credentials

Environment variables: `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`

Loaded from (in priority order):
1. `capsules/example-digital-capsule/.env`
2. Huxley root `.env`
3. macOS Keychain (service: `canva-client-id` / `canva-client-secret`, account: `canva`)
4. Environment variables

## Quick Start

```bash
# Authenticate (opens browser for OAuth)
python3 tools/canva_api.py auth login

# Check auth status
python3 tools/canva_api.py auth status

# List designs
python3 tools/canva_api.py designs list --limit 10

# Export a design as PNG
python3 tools/canva_api.py exports create DESIGN_ID --format png --wait
```

## All Subcommands

### Auth (`auth`)
| Command | Description |
|---------|-------------|
| `auth login` | Run OAuth 2.0 PKCE flow (opens browser, callback on port 3003) |
| `auth logout` | Revoke tokens and delete local token store |
| `auth status` | Show current authentication status, token expiry, scopes |
| `auth refresh` | Force token refresh using stored refresh token |
| `auth introspect` | Validate current token via OAuth introspection endpoint |

### Designs (`designs`)
| Command | Description |
|---------|-------------|
| `designs list` | List user's designs. `--query`, `--limit`, `--all`, `--continuation`, `--ownership`, `--sort-by` |
| `designs create` | Create new design. `--title`, `--design-type`, `--width`, `--height` |
| `designs get <id>` | Get design metadata |
| `designs pages <id>` | List pages in a design |
| `designs export-formats <id>` | List available export formats |

### Editing (`edit`)
| Command | Description |
|---------|-------------|
| `edit start <design_id>` | Start an editing transaction, returns transaction ID |
| `edit perform <tx_id>` | Perform operations. `--ops-file` or stdin JSON |
| `edit commit <tx_id>` | Commit editing transaction |
| `edit cancel <tx_id>` | Cancel editing transaction |

### Exports (`exports`)
| Command | Description |
|---------|-------------|
| `exports create <id>` | Create export job. `--format` (pdf/png/jpg/gif/pptx/mp4), `--pages`, `--quality`, `--wait` |
| `exports get <id>` | Get export job status and download URLs. `--wait` |

### Imports (`imports`)
| Command | Description |
|---------|-------------|
| `imports url` | Import design from URL. `--url`, `--title`, `--wait` |
| `imports get <id>` | Get import job status. `--url-import`, `--wait` |

### Assets (`assets`)
| Command | Description |
|---------|-------------|
| `assets get <id>` | Get asset metadata (name, tags, MIME, thumbnail) |
| `assets update <id>` | Update asset. `--name`, `--tags` (comma-separated) |
| `assets delete <id>` | Delete asset (moves to trash). Supports `--dry-run` |
| `assets upload-url` | Upload asset from URL. `--url`, `--name`, `--wait` |
| `assets upload-status <id>` | Get upload job status. `--url-upload` |

### Autofill (`autofill`) -- Enterprise
| Command | Description |
|---------|-------------|
| `autofill create <template_id>` | Create autofill job. `--data-file` or stdin JSON, `--title`, `--wait` |
| `autofill get <id>` | Get autofill job status |

### Brand Templates (`templates`) -- Enterprise
| Command | Description |
|---------|-------------|
| `templates list` | List brand templates. `--query`, `--limit`, `--all` |
| `templates get <id>` | Get template metadata |
| `templates dataset <id>` | Get template dataset (required fields for autofill) |

### Comments (`comments`)
| Command | Description |
|---------|-------------|
| `comments create <design_id>` | Create thread. `--message`, `--page`, `--x`, `--y` |
| `comments get <design_id> <thread_id>` | Get comment thread |
| `comments reply <design_id> <thread_id>` | Reply to thread. `--message` |
| `comments list-replies <design_id> <thread_id>` | List replies. `--limit` |

### Folders (`folders`)
| Command | Description |
|---------|-------------|
| `folders create` | Create folder. `--name`, `--parent-id` |
| `folders get <id>` | Get folder details |
| `folders update <id>` | Rename folder. `--name` |
| `folders delete <id>` | Delete folder. Supports `--dry-run` |
| `folders items <id>` | List folder contents. `--limit`, `--all` |
| `folders move` | Move item. `--item-id`, `--to-folder-id`. Supports `--dry-run` |

### Resize (`resize`) -- Pro
| Command | Description |
|---------|-------------|
| `resize create <design_id>` | Create resize job. `--width`, `--height`, `--design-type`, `--wait` |
| `resize get <id>` | Get resize job status |

### Users (`users`)
| Command | Description |
|---------|-------------|
| `users me` | Get current user ID and team ID |
| `users capabilities` | List API capabilities |
| `users profile` | Get user display name and profile |

## Global Flags

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output (for agent consumption) |
| `--verbose` / `-v` | Debug logging |
| `--dry-run` | Show what would be done (for destructive operations) |
| `--wait` | Poll async jobs until completion (exports, imports, resize, uploads) |
| `--timeout N` | Wait timeout in seconds (default: 120) |
| `--poll-interval N` | Poll interval in seconds (default: 2) |

## Common Patterns

### Export design to PNG and download
```bash
python3 tools/canva_api.py exports create DESIGN_ID --format png --wait --json | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['urls'][0])"
```

### Bulk list all designs
```bash
python3 tools/canva_api.py designs list --all --json
```

### Autofill a brand template
```bash
echo '{"headline": {"type": "text", "text": "Sale!"}}' | \
  python3 tools/canva_api.py autofill create TEMPLATE_ID --wait
```

### Create folder and move design into it
```bash
FOLDER=$(python3 tools/canva_api.py folders create --name "Campaign" --json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
python3 tools/canva_api.py folders move --item-id DESIGN_ID --to-folder-id $FOLDER
```

## Agent Wiring

| Agent | Use Cases |
|-------|-----------|
| **Graphic Designer** | Export designs to various formats, upload assets, manage design assets |
| **CMO** | Brand template autofill for campaign materials, bulk design operations |
| **Brand Specialist** | Brand template management, design consistency audits, folder organization |
| **Automator** | Scheduled exports, bulk operations via `--json` mode, pipeline integration |

## Architecture Notes

- **OAuth 2.0 + PKCE**: SHA-256 code challenge, local callback server on port 3003
- **Auto-refresh**: Tokens expire in ~4 hours, auto-refreshed on 401 or pre-expiry check
- **Rate limiting**: Exponential backoff on 429, configurable retry (3 attempts default)
- **Async jobs**: Export, import, resize, upload all use job polling pattern with `--wait`
- **Token storage**: `~/.canva-catalyst/tokens.json` with 600 file permissions
- **Port**: 3002 (registered in `global/config/port-registry.yaml` under `oauth` section)
