#!/usr/bin/env python3
"""
MCP Authentication and Authorization Middleware
Implements secure access controls for Huxley MCP servers
"""

import json
import jwt
import time
import hmac
import hashlib
import logging
import asyncio
import secrets
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager
import ssl
import socket

@dataclass
class MCPUser:
    """MCP user with authentication and authorization info"""
    user_id: str
    username: str
    roles: List[str]
    permissions: List[str]
    mcp_servers: List[str]
    resource_limits: Dict[str, int]
    created_at: float
    last_accessed: float

@dataclass
class MCPSecurityContext:
    """Security context for MCP operations"""
    user: MCPUser
    operation: str
    resource: str
    server_name: str
    client_ip: str
    session_id: str

class MCPAuthenticationError(Exception):
    """Authentication failed"""
    pass

class MCPAuthorizationError(Exception):
    """Authorization denied"""  
    pass

class MCPSecurityManager:
    """Manages MCP authentication, authorization, and security controls"""
    
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or Path("{{CATALYST_ROOT}}/global/security/mcp_auth_config.json")
        self.config = self._load_config()
        
        # JWT configuration
        self.jwt_secret = self._generate_jwt_secret()
        self.jwt_algorithm = "HS256"
        
        # Security state
        self.active_sessions: Dict[str, MCPUser] = {}
        self.failed_attempts: Dict[str, List[float]] = {}
        self.banned_ips: Dict[str, float] = {}
        
        # Setup logging
        self.logger = self._setup_security_logging()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load MCP security configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)["mcp_security_config"]
        except FileNotFoundError:
            raise MCPAuthenticationError(f"Security config not found: {self.config_path}")
        except json.JSONDecodeError as e:
            raise MCPAuthenticationError(f"Invalid security config: {e}")
            
    def _generate_jwt_secret(self) -> str:
        """Generate or load JWT secret key"""
        secret_file = Path("{{CATALYST_ROOT}}/global/security/.jwt_secret")
        
        if secret_file.exists():
            return secret_file.read_text().strip()
        else:
            # Generate new secret
            secret = secrets.token_hex(32)
            secret_file.parent.mkdir(exist_ok=True)
            secret_file.write_text(secret)
            secret_file.chmod(0o600)  # Restrict permissions
            return secret
            
    def _setup_security_logging(self) -> logging.Logger:
        """Setup security audit logging"""
        logger = logging.getLogger("mcp_security")
        logger.setLevel(logging.INFO)
        
        # Create log directory
        log_config = self.config.get("audit_logging", {})
        log_file = Path(log_config.get("log_file", "/tmp/mcp_security.log"))
        log_file.parent.mkdir(exist_ok=True)
        
        # File handler with rotation
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s - %(funcName)s:%(lineno)d'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
        
    def authenticate_user(self, credentials: Dict[str, str]) -> str:
        """Authenticate user and return JWT token"""
        username = credentials.get("username")
        password = credentials.get("password") 
        client_ip = credentials.get("client_ip", "unknown")
        
        # Check if IP is banned
        if self._is_ip_banned(client_ip):
            self.logger.warning(f"Authentication attempt from banned IP: {client_ip}")
            raise MCPAuthenticationError("IP address is temporarily banned")
            
        # Rate limiting check
        if not self._check_rate_limit(client_ip):
            self.logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise MCPAuthenticationError("Rate limit exceeded")
        
        # Simulate user authentication (replace with real authentication)
        user_data = self._authenticate_credentials(username, password)
        
        if not user_data:
            self._record_failed_attempt(client_ip)
            self.logger.warning(f"Failed authentication attempt: {username} from {client_ip}")
            raise MCPAuthenticationError("Invalid credentials")
            
        # Generate JWT token
        payload = {
            "user_id": user_data["user_id"],
            "username": username,
            "roles": user_data["roles"],
            "permissions": user_data["permissions"],
            "mcp_servers": user_data["mcp_servers"],
            "resource_limits": user_data["resource_limits"],
            "iat": time.time(),
            "exp": time.time() + self.config["authentication"]["token_expiry"]
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        
        # Create user session
        user = MCPUser(
            user_id=user_data["user_id"],
            username=username,
            roles=user_data["roles"],
            permissions=user_data["permissions"],
            mcp_servers=user_data["mcp_servers"],
            resource_limits=user_data["resource_limits"],
            created_at=time.time(),
            last_accessed=time.time()
        )
        
        session_id = hashlib.sha256(f"{username}:{time.time()}".encode()).hexdigest()[:16]
        self.active_sessions[session_id] = user
        
        self.logger.info(f"Successful authentication: {username} from {client_ip}")
        return token
        
    def validate_token(self, token: str) -> MCPUser:
        """Validate JWT token and return user"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Create user from payload
            user = MCPUser(
                user_id=payload["user_id"],
                username=payload["username"],
                roles=payload["roles"],
                permissions=payload["permissions"],
                mcp_servers=payload["mcp_servers"],
                resource_limits=payload["resource_limits"],
                created_at=payload["iat"],
                last_accessed=time.time()
            )
            
            return user
            
        except jwt.ExpiredSignatureError:
            raise MCPAuthenticationError("Token has expired")
        except jwt.InvalidTokenError:
            raise MCPAuthenticationError("Invalid token")
            
    def authorize_operation(self, user: MCPUser, operation: str, resource: str, server_name: str) -> bool:
        """Check if user is authorized for operation"""
        
        # Check server access
        if server_name not in user.mcp_servers and "*" not in user.mcp_servers:
            self.logger.warning(f"Unauthorized server access: {user.username} -> {server_name}")
            return False
            
        # Check permissions
        required_permission = f"{operation}_{resource}"
        if required_permission not in user.permissions and "*" not in user.permissions:
            # Check for wildcard permissions
            operation_wildcard = f"{operation}_*"
            resource_wildcard = f"*_{resource}"
            
            if (operation_wildcard not in user.permissions and 
                resource_wildcard not in user.permissions and
                "*" not in user.permissions):
                
                self.logger.warning(f"Unauthorized operation: {user.username} -> {required_permission}")
                return False
                
        return True
        
    def create_security_context(self, user: MCPUser, operation: str, resource: str, 
                              server_name: str, client_ip: str = "unknown") -> MCPSecurityContext:
        """Create security context for operation"""
        
        session_id = hashlib.sha256(f"{user.username}:{time.time()}".encode()).hexdigest()[:16]
        
        context = MCPSecurityContext(
            user=user,
            operation=operation,
            resource=resource,
            server_name=server_name,
            client_ip=client_ip,
            session_id=session_id
        )
        
        # Log security context creation
        self.logger.info(
            f"Security context created: {user.username} -> {operation}:{resource} on {server_name}"
        )
        
        return context
        
    def _authenticate_credentials(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user credentials (implement with real auth system)"""

        # SECURITY WARNING: Dev-only mock auth — requires MCP_AUTH_DEV_MODE=1
        if not os.environ.get("MCP_AUTH_DEV_MODE"):
            raise MCPAuthenticationError(
                "Mock authentication is disabled. Set MCP_AUTH_DEV_MODE=1 for development or implement real auth."
            )

        mock_users = {
            "builder_user": {
                "user_id": "user_001",
                "password_hash": "mock_hash_user",
                "roles": ["capsule_user"],
                "permissions": ["read_capsule", "write_capsule_own", "execute_standard"],
                "mcp_servers": ["filesystem", "git", "http"],
                "resource_limits": {"max_concurrent_operations": 5, "max_memory_mb": 100}
            },
            "builder_admin": {
                "user_id": "admin_001", 
                "password_hash": "mock_hash_admin",
                "roles": ["capsule_admin"],
                "permissions": ["read_capsule", "write_capsule_any", "execute_standard", "manage_agents"],
                "mcp_servers": ["filesystem", "git", "http", "applescript", "n8n", "shadcn-ui"],
                "resource_limits": {"max_concurrent_operations": 20, "max_memory_mb": 500}
            }
        }
        
        user_data = mock_users.get(username)
        if user_data and self._verify_password(password, user_data["password_hash"]):
            return user_data
            
        return None
        
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash (implement proper hashing)"""
        # SECURITY WARNING: Dev-only mock verification — use proper hashing in production
        return hmac.compare_digest(password, "mock_password")
        
    def _is_ip_banned(self, client_ip: str) -> bool:
        """Check if IP address is banned"""
        if client_ip in self.banned_ips:
            ban_time = self.banned_ips[client_ip]
            ban_duration = self.config.get("intrusion_detection", {}).get("lockout_duration_minutes", 30) * 60
            
            if time.time() - ban_time < ban_duration:
                return True
            else:
                # Ban expired, remove from banned list
                del self.banned_ips[client_ip]
                
        return False
        
    def _check_rate_limit(self, client_ip: str) -> bool:
        """Check rate limiting for IP address"""
        rate_config = self.config.get("rate_limiting", {})
        if not rate_config.get("enabled", False):
            return True
            
        max_requests = rate_config.get("requests_per_minute", 60)
        window_seconds = 60
        
        current_time = time.time()
        
        # Clean old entries
        if client_ip in self.failed_attempts:
            self.failed_attempts[client_ip] = [
                attempt_time for attempt_time in self.failed_attempts[client_ip]
                if current_time - attempt_time < window_seconds
            ]
        
        # Check current request count
        attempt_count = len(self.failed_attempts.get(client_ip, []))
        return attempt_count < max_requests
        
    def _record_failed_attempt(self, client_ip: str):
        """Record failed authentication attempt"""
        current_time = time.time()
        
        if client_ip not in self.failed_attempts:
            self.failed_attempts[client_ip] = []
            
        self.failed_attempts[client_ip].append(current_time)
        
        # Check if should ban IP
        intrusion_config = self.config.get("intrusion_detection", {})
        max_failures = intrusion_config.get("max_failed_auth_attempts", 5)
        
        if len(self.failed_attempts[client_ip]) >= max_failures:
            self.banned_ips[client_ip] = current_time
            self.logger.warning(f"IP banned due to failed attempts: {client_ip}")

class MCPSecureServer:
    """Secure MCP server wrapper with authentication and TLS"""
    
    def __init__(self, security_manager: MCPSecurityManager, server_name: str):
        self.security_manager = security_manager
        self.server_name = server_name
        self.ssl_context = self._create_ssl_context()
        
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for TLS encryption"""
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        # Configure TLS version (minimum 1.3)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        
        # Load certificates (implement certificate loading)
        # context.load_cert_chain("server.crt", "server.key")
        
        return context
        
    @asynccontextmanager
    async def secure_operation(self, token: str, operation: str, resource: str, client_ip: str = "unknown"):
        """Secure context manager for MCP operations"""
        
        # Authenticate and authorize
        try:
            user = self.security_manager.validate_token(token)
            
            if not self.security_manager.authorize_operation(user, operation, resource, self.server_name):
                raise MCPAuthorizationError(f"Operation not authorized: {operation} on {resource}")
                
            # Create security context
            context = self.security_manager.create_security_context(
                user, operation, resource, self.server_name, client_ip
            )
            
            # Check resource limits
            self._enforce_resource_limits(user, operation)
            
            yield context
            
        except (MCPAuthenticationError, MCPAuthorizationError) as e:
            self.security_manager.logger.error(f"Security violation: {e}")
            raise
            
    def _enforce_resource_limits(self, user: MCPUser, operation: str):
        """Enforce user resource limits"""
        limits = user.resource_limits
        
        # Check concurrent operations (simplified implementation)
        if limits.get("max_concurrent_operations", -1) > 0:
            # Implementation would check actual concurrent operations
            pass
            
        # Check memory limits (simplified implementation) 
        if limits.get("max_memory_mb", -1) > 0:
            # Implementation would check actual memory usage
            pass

# Usage Example:
async def secure_mcp_operation_example():
    """Example of secure MCP operation"""
    
    security_manager = MCPSecurityManager()
    secure_server = MCPSecureServer(security_manager, "filesystem")
    
    # Authenticate user
    credentials = {
        "username": "builder_user",
        "password": "mock_password",
        "client_ip": "127.0.0.1"
    }
    
    try:
        token = security_manager.authenticate_user(credentials)
        
        # Perform secure operation
        async with secure_server.secure_operation(token, "read", "capsule", "127.0.0.1") as context:
            print(f"Secure operation authorized for user: {context.user.username}")
            # Perform actual MCP operation here
            
    except (MCPAuthenticationError, MCPAuthorizationError) as e:
        print(f"Security error: {e}")

if __name__ == "__main__":
    # Test the security system
    asyncio.run(secure_mcp_operation_example())