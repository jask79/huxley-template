# Njalla Integration

Privacy-focused domain registrar integration for Huxley.

## Overview

[Njalla](https://njal.la/) is a privacy-oriented domain registration service. Unlike traditional registrars, Njalla acts as a privacy shield - they own the domain on your behalf while you retain full control.

**Use Cases:**
- Domain registration and renewal
- DNS record management
- Privacy-preserving domain ownership
- Programmatic domain operations via API

## Authentication

### API Token Location

Stored in macOS Keychain:
- **Service:** `njalla-api`
- **Account:** `huxley`

### Storing the Token

```bash
security add-generic-password -s njalla-api -a huxley -w <YOUR_TOKEN> -U
```

### Retrieving the Token

```python
from global.integrations.njalla.njalla_client import NjallaClient
client = NjallaClient()  # Auto-loads token from Keychain
```

Or directly:
```bash
security find-generic-password -s njalla-api -a huxley -w
```

## API Reference

### Endpoint
```
POST https://njal.la/api/1/
Content-Type: application/json
Authorization: Njalla <token>
```

### Protocol
JSON-RPC 2.0 format:
```json
{
  "jsonrpc": "2.0",
  "method": "method-name",
  "params": { ... },
  "id": 1
}
```

### Available Methods

#### Domain Operations

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `list-domains` | none | `domains: []` | List all registered domains |
| `get-domain` | `domain: string` | Domain details | Get specific domain info |
| `add-domain` | `domain: string, years: int` | `task: string` | Register new domain |
| `renew-domain` | `domain: string, years: int` | `task: string` | Renew existing domain |
| `edit-domain` | `domain: string, ...settings` | Updated domain | Modify domain settings |

#### DNS Record Operations

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `list-records` | `domain: string` | `records: []` | List DNS records |
| `add-record` | `domain, name, type, content, ttl` | Record object | Add DNS record |
| `edit-record` | `id: int, content, ttl` | Record object | Update DNS record |
| `remove-record` | `domain: string, id: int` | none | Delete DNS record |

#### Domain Settings

Available settings for `edit-domain`:
- `mailforwarding: boolean` - Enable/disable mail forwarding
- `dnssec: boolean` - Enable/disable DNSSEC
- `lock: boolean` - Lock domain transfers
- `nameservers: []` - Custom nameservers (empty = Njalla's)
- `contacts: {}` - Custom WHOIS contact IDs

### DNS Record Types

Supported types: `A`, `AAAA`, `MX`, `TXT`, `CNAME`, `NS`, `SRV`, `CAA`, `TLSA`, `REDIRECT`

## Agent Ownership

**Primary:** 🏛️ Backend Developer

Backend Dev is responsible for:
- Domain registration and renewal
- DNS record configuration
- Coordinating DNS between Njalla and Cloudflare
- Domain-related deployment infrastructure

## Security Considerations

1. **API Token Protection:** Token is stored encrypted in macOS Keychain
2. **Privacy:** Njalla shields ownership info - do not expose in logs
3. **Rate Limiting:** API has rate limits on clearnet access
4. **Task-Based Operations:** Registration/renewal return task IDs - poll `check-task` for completion

## Related Resources

- [QUICK_START.md](./QUICK_START.md) - Common operations guide
- [njalla_client.py](./njalla_client.py) - Python client wrapper
- Community libraries:
  - [Node.js client](https://github.com/romualdr/node-njalla-dns)
  - [Go library](https://pkg.go.dev/github.com/evanstechblog/gonjalla)
  - [Terraform provider](https://registry.terraform.io/providers/Sighery/njalla/latest/docs)
