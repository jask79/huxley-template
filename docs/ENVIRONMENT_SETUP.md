# Huxley Environment Setup Guide

Quick guide for configuring Huxley environment variables.

## Quick Start

```bash
# 1. Copy the template
cp .env.example .env

# 2. Edit with your credentials
code .env  # or vim/nano

# 3. Generate secrets
openssl rand -hex 32  # For JWT/SESSION secrets
openssl rand -base64 32  # For encryption keys
```

## Required Variables

### Database
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_ANON_KEY` - Supabase anon/public key

### AI Provider (at least one)
- `ANTHROPIC_API_KEY` - Claude API key (primary provider)

### Security
- `JWT_SECRET` - Session token signing (generate with openssl)
- `SESSION_SECRET` - Session encryption key
- `API_KEY` - Huxley API authentication

## Getting Credentials

### Supabase
1. Go to [supabase.com](https://supabase.com)
2. Create/select project
3. Settings → API → Copy URL and anon key

### Anthropic
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. API Keys → Create Key
3. Copy key to `ANTHROPIC_API_KEY`

### OpenAI (Optional)
1. Go to [platform.openai.com](https://platform.openai.com)
2. API Keys → Create new secret key
3. Copy to `OPENAI_API_KEY`

## Generating Secrets

```bash
# JWT Secret (32 bytes hex)
openssl rand -hex 32

# Encryption Key (32 bytes base64)
openssl rand -base64 32

# API Key (24 bytes hex)
openssl rand -hex 24
```

## Security Best Practices

1. **Never commit .env files to git**
2. **Rotate secrets every 90 days**
3. **Use strong passwords (openssl rand)**
4. **Restrict file permissions:**
   ```bash
   chmod 600 .env
   ```

## Validation

Test your configuration:

```bash
# Check required variables
python3 tools/validate_env.py

# Test API connections
curl -H "x-api-key: $ANTHROPIC_API_KEY" https://api.anthropic.com/v1/messages
```

## Troubleshooting

### "Missing required environment variable"
```bash
# Verify .env file exists
ls -la .env

# Check variable is set
echo $ANTHROPIC_API_KEY

# Reload environment
export $(cat .env | grep -v '^#' | xargs)
```

### "Invalid API key"
- Verify key is correct in provider dashboard
- Regenerate if needed
- Check for trailing spaces/newlines

### Service won't start
```bash
# Check port conflicts
lsof -i :5050

# Kill conflicting process
kill -9 <PID>

# Or change port in .env
API_PORT=5051
```

## Reference

- Full variable list: See `.env.example`
- Service ports: See section "SERVICE PORTS" in .env.example
- Feature flags: See section "FEATURE FLAGS" in .env.example

