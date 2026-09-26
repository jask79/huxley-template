# Njalla Quick Start

Common operations for Huxley agents working with Njalla.

## Setup

```python
from global.integrations.njalla.njalla_client import NjallaClient

# Auto-loads API token from macOS Keychain (service: njalla-api, account: huxley)
client = NjallaClient()
```

## Common Operations

### List All Domains

```python
domains = client.list_domains()
for domain in domains:
    print(f"{domain['name']} - expires: {domain['expiry']}")
```

### Get Domain Details

```python
domain = client.get_domain("example.com")
print(f"Status: {domain['status']}")
print(f"Expiry: {domain['expiry']}")
print(f"Locked: {domain.get('locked', False)}")
```

### List DNS Records

```python
records = client.list_records("example.com")
for record in records:
    print(f"{record['type']} {record['name']} -> {record['content']}")
```

### Add DNS Record

```python
# A Record
client.add_record(
    domain="example.com",
    name="www",
    record_type="A",
    content="192.168.1.1",
    ttl=3600
)

# CNAME Record
client.add_record(
    domain="example.com",
    name="blog",
    record_type="CNAME",
    content="example.netlify.app",
    ttl=3600
)

# TXT Record (for verification)
client.add_record(
    domain="example.com",
    name="_verify",
    record_type="TXT",
    content="verification-code-here",
    ttl=300
)

# MX Record
client.add_record(
    domain="example.com",
    name="@",
    record_type="MX",
    content="10 mail.example.com",
    ttl=3600
)
```

### Update DNS Record

```python
# First get the record ID
records = client.list_records("example.com")
record = next(r for r in records if r['name'] == 'www' and r['type'] == 'A')

# Update it
client.edit_record(
    record_id=record['id'],
    content="192.168.1.2",
    ttl=3600
)
```

### Delete DNS Record

```python
client.remove_record(domain="example.com", record_id=12345)
```

### Register New Domain

```python
# Returns a task ID - registration is async
task = client.register_domain("newdomain.com", years=1)
print(f"Registration task: {task}")

# Check task status
status = client.check_task(task)
print(f"Status: {status}")
```

### Renew Domain

```python
task = client.renew_domain("example.com", years=1)
status = client.check_task(task)
```

### Update Domain Settings

```python
# Enable DNSSEC
client.edit_domain("example.com", dnssec=True)

# Lock domain transfers
client.edit_domain("example.com", lock=True)

# Set custom nameservers
client.edit_domain("example.com", nameservers=[
    "ns1.cloudflare.com",
    "ns2.cloudflare.com"
])

# Use Njalla's nameservers (empty list)
client.edit_domain("example.com", nameservers=[])
```

## Cloudflare + Njalla Workflow

When using Cloudflare for DNS (common pattern):

```python
# 1. Register domain at Njalla
task = client.register_domain("newproject.com", years=1)
client.wait_for_task(task)

# 2. Point to Cloudflare nameservers
client.edit_domain("newproject.com", nameservers=[
    "ns1.cloudflare.com",
    "ns2.cloudflare.com"
])

# 3. Configure DNS in Cloudflare (use Cloudflare API/dashboard)
# ... Backend Dev handles Cloudflare config separately
```

## Error Handling

```python
from global.integrations.njalla.njalla_client import NjallaClient, NjallaError

client = NjallaClient()

try:
    domain = client.get_domain("nonexistent.com")
except NjallaError as e:
    print(f"API Error: {e.code} - {e.message}")
```

## Retrieving Token Manually

If you need the raw token (not recommended - use client):

```bash
security find-generic-password -s njalla-api -a huxley -w
```

## CLI Usage

```bash
# Using the client directly
cd {{CATALYST_ROOT}}
python3 -c "
from global.integrations.njalla.njalla_client import NjallaClient
client = NjallaClient()
for d in client.list_domains():
    print(d['name'])
"
```

## Debugging

Enable verbose mode:
```python
client = NjallaClient(verbose=True)
# Will print request/response details
```

## Rate Limits

- Njalla rate-limits aggressive API usage
- Add delays between bulk operations
- Cache domain lists when possible
