# JWT Security Guide for Huxley

## Overview

The Huxley system uses JWT (JSON Web Tokens) for secure authentication and authorization, with signing keys stored securely in the macOS Keychain rather than in configuration files or code.

## Key Storage Architecture

### Keychain Integration

All JWT signing keys are stored in the macOS Keychain using the `keychain_helper.py` module:

- **Global Keys**: `huxley.system.global.jwt_signing_key`
- **Capsule Keys**: `huxley.system.capsule.<capsule_id>.jwt_signing_key`

### Security Benefits

1. **No Secrets in Code**: Keys are never stored in configuration files or source code
2. **OS-Level Encryption**: macOS Keychain provides hardware-backed encryption
3. **Access Control**: Keys are protected by macOS security policies
4. **Capsule Isolation**: Each capsule can have its own signing key for isolation

## Usage

### Getting JWT Keys

```python
from keychain_helper import get_global_jwt_key, get_capsule_jwt_key

# Get global JWT key
global_key = get_global_jwt_key()

# Get capsule-specific JWT key  
capsule_key = get_capsule_jwt_key("my-capsule-id")
```

### Configuration Reference

In `global/security/mcp_auth_config.json`:

```json
{
  "authentication": {
    "jwt_signing_key_source": "keychain",
    "keychain_service": "huxley.system.global.jwt_signing_key"
  }
}
```

## Key Management Commands

### Generate New Keys

```bash
# Generate global key
python -c "from keychain_helper import keychain; keychain.generate_jwt_key()"

# Generate capsule-specific key
python -c "from keychain_helper import keychain; keychain.generate_jwt_key('my-capsule')"
```

### List Stored Keys

```bash
# List global keys
python -c "from keychain_helper import keychain; print(keychain.list_secrets())"

# List capsule keys
python -c "from keychain_helper import keychain; print(keychain.list_secrets('my-capsule'))"
```

### Manual Keychain Access

You can also use the macOS `security` command directly:

```bash
# View keychain entry (will prompt for password)
security find-generic-password -s "huxley.system.global.jwt_signing_key" -w

# Delete keychain entry
security delete-generic-password -s "huxley.system.global.jwt_signing_key"
```

## Security Best Practices

### 1. Key Rotation

Rotate JWT signing keys regularly:

```python
from keychain_helper import keychain

# Delete old key
keychain.delete_secret("jwt_signing_key")

# Generate new key
new_key = keychain.generate_jwt_key()
```

### 2. Capsule Isolation

Use capsule-specific keys for better isolation:

```python
# Each capsule gets its own key
for capsule_id in active_capsules:
    keychain.setup_capsule_secrets(capsule_id)
```

### 3. Access Logging

All keychain access is logged for security auditing:

```python
import logging
logging.getLogger('keychain_helper').setLevel(logging.INFO)
```

### 4. Backup and Recovery

**Important**: Keychain entries are tied to your macOS account. For production deployments:

1. **Export Keys**: Use the keychain helper to export keys to a secure backup location
2. **Team Access**: Consider using a shared keychain for team environments
3. **CI/CD**: Use environment variables or secure secret stores for automated deployments

```python
# Export key for backup (store securely!)
key = keychain.retrieve_secret("jwt_signing_key")
# Store in secure location outside of repository
```

## Troubleshooting

### Key Not Found

If you get "Key not found" errors:

```python
from keychain_helper import keychain

# Check if key exists
keys = keychain.list_secrets()
print("Available keys:", keys)

# Generate missing key
if "jwt_signing_key" not in keys:
    keychain.generate_jwt_key()
```

### Keychain Access Denied

If macOS denies access to the keychain:

1. Open **Keychain Access** app
2. Find the Huxley entries
3. Double-click and update access permissions
4. Add your application to the "Always Allow" list

### Development vs Production

**Development**:
- Keys are generated automatically on first use
- Individual developer keychains are acceptable

**Production**:
- Pre-generate keys during deployment
- Use shared keychain or external secret management
- Implement key rotation policies

## Migration from Config Files

If you previously stored keys in configuration files:

1. **Extract Keys**: Copy existing keys from config files
2. **Store in Keychain**: Use `keychain.store_secret()` to migrate
3. **Update Config**: Change config to reference keychain
4. **Remove Files**: Delete config files with embedded keys
5. **Verify**: Test authentication still works

```python
# Migration script example
from keychain_helper import keychain
import json

# Read old config
with open('old_config.json') as f:
    old_config = json.load(f)

# Migrate key to keychain
old_key = old_config['jwt_key']
keychain.store_secret('jwt_signing_key', old_key)

# Verify migration
new_key = keychain.retrieve_secret('jwt_signing_key')
assert new_key == old_key, "Migration failed"

print("✅ Key successfully migrated to keychain")
```

## Security Compliance

This approach provides:

- **FIPS 140-2 Level 1**: macOS Keychain meets federal security standards
- **Zero Secrets in Code**: No credentials in source control
- **Principle of Least Privilege**: Keys are scoped to specific services
- **Audit Trail**: All access is logged through macOS security framework
- **Encryption at Rest**: Keys are encrypted using hardware security features

For enterprise compliance, consider integrating with:
- HashiCorp Vault
- AWS Secrets Manager  
- Azure Key Vault
- Google Secret Manager

The `keychain_helper.py` module can be extended to support these backends while maintaining the same API.