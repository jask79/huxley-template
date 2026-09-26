#!/usr/bin/env python3
"""
Huxley Environment Validation Script

Validates that all required environment variables are set correctly
and provides helpful feedback for missing or invalid values.
"""

import os
import sys
import re
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def print_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")

def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")

def print_header(msg):
    print(f"\n{BOLD}{msg}{RESET}")

# Required environment variables
REQUIRED_VARS = {
    'ANTHROPIC_API_KEY': {
        'pattern': r'^sk-ant-',
        'min_length': 40,
        'description': 'Anthropic Claude API key',
        'placeholder': 'sk-ant-your-key-here'
    },
    'JWT_SECRET': {
        'min_length': 32,
        'description': 'JWT signing secret',
        'placeholder': 'generate-a-strong-random-string-here'
    },
    'SESSION_SECRET': {
        'min_length': 32,
        'description': 'Session encryption secret',
        'placeholder': 'another-strong-random-string-here'
    },
    'GRAFANA_ADMIN_PASSWORD': {
        'min_length': 12,
        'description': 'Grafana admin password',
        'placeholder': 'secure-admin-password'
    }
}

# Optional but recommended
RECOMMENDED_VARS = {
    'SUPABASE_URL': {
        'pattern': r'https://.+\.supabase\.co',
        'description': 'Supabase project URL'
    },
    'SUPABASE_ANON_KEY': {
        'min_length': 100,
        'description': 'Supabase anon key'
    },
    'CATALYST_ROOT': {
        'description': 'Huxley root directory',
        'must_exist': True
    }
}

def check_placeholder(value, placeholder):
    """Check if value is still a placeholder"""
    placeholder_patterns = [
        'your-key-here',
        'your-project',
        'generate-a-strong',
        'another-strong',
        'secure-admin-password',
        'base64-encoded',
        'your-',
    ]
    return any(pattern in value.lower() for pattern in placeholder_patterns)

def validate_var(name, config):
    """Validate a single environment variable"""
    value = os.getenv(name)
    
    if not value:
        return False, "Not set"
    
    # Check for placeholder values
    if 'placeholder' in config and check_placeholder(value, config['placeholder']):
        return False, "Using placeholder value"
    
    # Check minimum length
    if 'min_length' in config and len(value) < config['min_length']:
        return False, f"Too short (minimum {config['min_length']} characters)"
    
    # Check pattern
    if 'pattern' in config and not re.match(config['pattern'], value):
        return False, f"Invalid format (should match {config['pattern']})"
    
    # Check path exists
    if config.get('must_exist') and not Path(value).exists():
        return False, f"Path does not exist: {value}"
    
    return True, "Valid"

def main():
    print_header("🔍 Huxley Environment Validation")
    
    # Check if .env file exists
    env_file = Path(os.getenv('CATALYST_ROOT', Path.cwd())) / '.env'
    if not env_file.exists():
        print_error(f".env file not found at {env_file}")
        print(f"\nCreate one by copying the template:")
        print(f"  cp .env.example .env")
        sys.exit(1)
    
    print_success(f"Found .env file: {env_file}")
    
    # Validate required variables
    print_header("Required Variables")
    required_valid = True
    
    for name, config in REQUIRED_VARS.items():
        valid, message = validate_var(name, config)
        
        if valid:
            print_success(f"{name}: {message}")
        else:
            print_error(f"{name}: {message}")
            print(f"   Description: {config['description']}")
            
            if 'pattern' in config:
                print(f"   Format: {config['pattern']}")
            
            if name in ['JWT_SECRET', 'SESSION_SECRET']:
                print(f"   Generate: openssl rand -hex 32")
            elif name == 'GRAFANA_ADMIN_PASSWORD':
                print(f"   Generate: openssl rand -base64 24")
            
            required_valid = False
    
    # Validate recommended variables
    print_header("Recommended Variables")
    recommended_count = 0
    
    for name, config in RECOMMENDED_VARS.items():
        valid, message = validate_var(name, config)
        
        if valid:
            print_success(f"{name}: {message}")
            recommended_count += 1
        else:
            print_warning(f"{name}: {message} (optional)")
    
    # Check for common mistakes
    print_header("Additional Checks")
    
    # Check for spaces in secrets
    for var in ['JWT_SECRET', 'SESSION_SECRET', 'ANTHROPIC_API_KEY']:
        value = os.getenv(var)
        if value and ' ' in value:
            print_warning(f"{var} contains spaces - this may cause issues")
    
    # Check CATALYST_ROOT
    catalyst_root = os.getenv('CATALYST_ROOT', os.getcwd())
    if Path(catalyst_root).exists():
        print_success(f"CATALYST_ROOT: {catalyst_root}")
    else:
        print_warning(f"CATALYST_ROOT not set, using: {catalyst_root}")
    
    # Check API port conflicts
    ports_in_use = []
    for port_var in ['API_PORT', 'ROUTER_PORT', 'GATEWAY_PORT', 'PORTAL_PORT']:
        port = os.getenv(port_var)
        if port:
            if port in ports_in_use:
                print_error(f"{port_var}: Port {port} already assigned")
            else:
                ports_in_use.append(port)
    
    if len(ports_in_use) > 0:
        print_success(f"No port conflicts detected")
    
    # Summary
    print_header("Summary")
    
    if required_valid:
        print_success("All required variables are valid!")
        print(f"✅ Recommended: {recommended_count}/{len(RECOMMENDED_VARS)} configured")
        sys.exit(0)
    else:
        print_error("Some required variables are missing or invalid")
        print("\nFix the issues above and run this script again:")
        print(f"  python3 {__file__}")
        sys.exit(1)

if __name__ == '__main__':
    main()
