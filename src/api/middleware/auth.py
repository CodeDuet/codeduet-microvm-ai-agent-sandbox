"""
Authentication and authorization middleware for the MicroVM API.
"""

import jwt
import hashlib
import hmac
import time
from typing import Dict, Optional, List, Callable, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging

from ...utils.security import SecurityError, CredentialManager, AuditLogger

logger = logging.getLogger(__name__)


class TokenData(BaseModel):
    """Token data model."""
    user_id: str
    email: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
    expires_at: datetime
    session_id: str


class UserInfo(BaseModel):
    """User information model."""
    user_id: str
    email: str
    roles: List[str]
    permissions: List[str]
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None


class AuthConfig(BaseModel):
    """Authentication configuration."""
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    token_expire_minutes: int = 60
    max_failed_attempts: int = 5
    lockout_duration_minutes: int = 30
    require_strong_passwords: bool = True
    session_timeout_minutes: int = 60
    enable_mfa: bool = False


class AuthenticationManager:
    """Manages user authentication and session handling."""
    
    def __init__(self, config: AuthConfig):
        """Initialize authentication manager."""
        self.config = config
        self.credential_manager = CredentialManager()
        self.audit_logger = AuditLogger()
        
        # In-memory stores (in production, use Redis or database)
        self.users: Dict[str, UserInfo] = {}
        self.sessions: Dict[str, TokenData] = {}
        self.failed_attempts: Dict[str, List[datetime]] = {}
        self.locked_accounts: Dict[str, datetime] = {}
        
        # Create default admin user
        self._create_default_admin()
    
    def _create_default_admin(self):
        """Create default admin user if none exists."""
        admin_id = "admin"
        if admin_id not in self.users:
            self.users[admin_id] = UserInfo(
                user_id=admin_id,
                email="admin@localhost",
                roles=["admin"],
                permissions=["*"],
                created_at=datetime.utcnow()
            )
            logger.info("Created default admin user")
    
    def create_user(self, user_id: str, email: str, password: str,
                   roles: List[str] = None, permissions: List[str] = None) -> bool:
        """Create a new user."""
        try:
            if user_id in self.users:
                raise SecurityError("User already exists")
            
            if self.config.require_strong_passwords:
                self._validate_password_strength(password)
            
            # Hash password
            password_hash, salt = self.credential_manager.hash_password(password)
            
            # Create user
            user = UserInfo(
                user_id=user_id,
                email=email,
                roles=roles or ["user"],
                permissions=permissions or ["vm:read", "vm:create"],
                created_at=datetime.utcnow()
            )
            
            self.users[user_id] = user
            
            # Store password separately (in production, use secure storage)
            setattr(user, '_password_hash', password_hash)
            setattr(user, '_password_salt', salt)
            
            self.audit_logger.log_resource_access(
                "user", user_id, "system", "created"
            )
            
            logger.info(f"Created user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create user {user_id}: {e}")
            return False
    
    def authenticate_user(self, user_id: str, password: str,
                         ip_address: str = "") -> Optional[TokenData]:
        """Authenticate user and return token data."""
        try:
            # Check if account is locked
            if self._is_account_locked(user_id):
                self.audit_logger.log_authentication(user_id, False, ip_address)
                raise SecurityError("Account is locked due to failed attempts")
            
            # Get user
            user = self.users.get(user_id)
            if not user or not user.is_active:
                self._record_failed_attempt(user_id, ip_address)
                raise SecurityError("Invalid credentials")
            
            # Verify password
            password_hash = getattr(user, '_password_hash', None)
            password_salt = getattr(user, '_password_salt', None)
            
            if not password_hash or not password_salt:
                self._record_failed_attempt(user_id, ip_address)
                raise SecurityError("Invalid credentials")
            
            if not self.credential_manager.verify_password(
                password, password_hash, password_salt
            ):
                self._record_failed_attempt(user_id, ip_address)
                raise SecurityError("Invalid credentials")
            
            # Clear failed attempts on successful login
            if user_id in self.failed_attempts:
                del self.failed_attempts[user_id]
            
            # Create token
            token_data = self._create_token_data(user)
            
            # Store session
            self.sessions[token_data.session_id] = token_data
            
            # Update last login
            user.last_login = datetime.utcnow()
            
            self.audit_logger.log_authentication(user_id, True, ip_address)
            logger.info(f"User authenticated: {user_id}")
            
            return token_data
            
        except SecurityError:
            raise
        except Exception as e:
            logger.error(f"Authentication error for {user_id}: {e}")
            raise SecurityError("Authentication failed")
    
    def _create_token_data(self, user: UserInfo) -> TokenData:
        """Create token data for authenticated user."""
        expires_at = datetime.utcnow() + timedelta(
            minutes=self.config.token_expire_minutes
        )
        
        session_id = self.credential_manager.generate_session_token()
        
        return TokenData(
            user_id=user.user_id,
            email=user.email,
            roles=user.roles,
            permissions=user.permissions,
            expires_at=expires_at,
            session_id=session_id
        )
    
    def create_jwt_token(self, token_data: TokenData) -> str:
        """Create JWT token from token data."""
        now = datetime.utcnow()
        payload = {
            "user_id": token_data.user_id,
            "email": token_data.email,
            "roles": token_data.roles,
            "permissions": token_data.permissions,
            "exp": token_data.expires_at.timestamp(),
            "session_id": token_data.session_id,
            "iat": now.timestamp(),
            "nbf": now.timestamp()  # Not before
        }
        
        return jwt.encode(
            payload,
            self.config.jwt_secret,
            algorithm=self.config.jwt_algorithm
        )
    
    def verify_jwt_token(self, token: str) -> Optional[TokenData]:
        """Verify JWT token and return token data."""
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm],
                leeway=10  # Allow 10 seconds leeway for clock skew
            )
            
            session_id = payload.get("session_id")
            if not session_id or session_id not in self.sessions:
                raise SecurityError("Invalid session")
            
            token_data = self.sessions[session_id]
            
            # Check if token is expired
            if datetime.utcnow() > token_data.expires_at:
                del self.sessions[session_id]
                raise SecurityError("Token expired")
            
            return token_data
            
        except jwt.ExpiredSignatureError:
            raise SecurityError("Token expired")
        except jwt.InvalidTokenError:
            raise SecurityError("Invalid token")
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise SecurityError("Token verification failed")
    
    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    def _validate_password_strength(self, password: str):
        """Validate password strength."""
        if len(password) < 8:
            raise SecurityError("Password must be at least 8 characters long")
        
        if not any(c.isupper() for c in password):
            raise SecurityError("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            raise SecurityError("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            raise SecurityError("Password must contain at least one digit")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            raise SecurityError("Password must contain at least one special character")
    
    def _is_account_locked(self, user_id: str) -> bool:
        """Check if account is locked."""
        if user_id in self.locked_accounts:
            lock_time = self.locked_accounts[user_id]
            unlock_time = lock_time + timedelta(
                minutes=self.config.lockout_duration_minutes
            )
            
            if datetime.utcnow() < unlock_time:
                return True
            else:
                # Unlock account
                del self.locked_accounts[user_id]
        
        return False
    
    def _record_failed_attempt(self, user_id: str, ip_address: str):
        """Record failed authentication attempt."""
        now = datetime.utcnow()
        
        if user_id not in self.failed_attempts:
            self.failed_attempts[user_id] = []
        
        self.failed_attempts[user_id].append(now)
        
        # Keep only recent attempts (last hour)
        cutoff = now - timedelta(hours=1)
        self.failed_attempts[user_id] = [
            attempt for attempt in self.failed_attempts[user_id]
            if attempt > cutoff
        ]
        
        # Lock account if too many failed attempts
        if len(self.failed_attempts[user_id]) >= self.config.max_failed_attempts:
            self.locked_accounts[user_id] = now
            self.audit_logger.log_security_violation(
                "ACCOUNT_LOCKED", user_id,
                f"Too many failed attempts from {ip_address}"
            )
            logger.warning(f"Account locked due to failed attempts: {user_id}")
        
        self.audit_logger.log_authentication(user_id, False, ip_address)


class AuthorizationManager:
    """Manages user authorization and permissions."""
    
    def __init__(self):
        """Initialize authorization manager."""
        self.role_permissions = {
            "admin": ["*"],
            "power_user": [
                "vm:*", "snapshot:*", "resource:read", "resource:allocate",
                "guest:*", "network:read", "system:read"
            ],
            "user": [
                "vm:read", "vm:create", "vm:delete", "vm:start", "vm:stop",
                "snapshot:read", "snapshot:create", "guest:execute",
                "guest:file_transfer", "system:read"
            ],
            "readonly": [
                "vm:read", "snapshot:read", "resource:read",
                "system:read", "guest:read"
            ]
        }
    
    def check_permission(self, user_permissions: List[str], 
                        required_permission: str) -> bool:
        """Check if user has required permission."""
        # Admin wildcard permission
        if "*" in user_permissions:
            return True
        
        # Check exact permission match
        if required_permission in user_permissions:
            return True
        
        # Check wildcard permissions
        for permission in user_permissions:
            if permission.endswith("*"):
                permission_prefix = permission[:-1]
                if required_permission.startswith(permission_prefix):
                    return True
        
        return False
    
    def get_role_permissions(self, role: str) -> List[str]:
        """Get permissions for a role."""
        return self.role_permissions.get(role, [])
    
    def expand_user_permissions(self, user_roles: List[str],
                              user_permissions: List[str]) -> List[str]:
        """Expand user permissions based on roles."""
        all_permissions = set(user_permissions)
        
        for role in user_roles:
            role_perms = self.get_role_permissions(role)
            all_permissions.update(role_perms)
        
        return list(all_permissions)


# FastAPI Dependencies
class AuthenticationBearer(HTTPBearer):
    """JWT Bearer authentication for FastAPI."""
    
    def __init__(self, auth_manager: AuthenticationManager):
        super().__init__()
        self.auth_manager = auth_manager
    
    async def __call__(self, request: Request) -> TokenData:
        """Authenticate request and return user data."""
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials required"
            )
        
        try:
            token_data = self.auth_manager.verify_jwt_token(credentials.credentials)
            
            # Add IP address to request state for audit logging
            request.state.user_ip = request.client.host if request.client else ""
            request.state.user_id = token_data.user_id
            
            return token_data
            
        except SecurityError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )


class PermissionChecker:
    """Permission checker dependency."""
    
    def __init__(self, required_permission: str):
        self.required_permission = required_permission
        self.auth_manager = AuthorizationManager()
    
    def __call__(self, token_data: TokenData = Depends()) -> bool:
        """Check if user has required permission."""
        expanded_permissions = self.auth_manager.expand_user_permissions(
            token_data.roles, token_data.permissions
        )
        
        if not self.auth_manager.check_permission(
            expanded_permissions, self.required_permission
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {self.required_permission}"
            )
        
        return True


# Global auth manager instance (will be initialized by the main app)
auth_manager: Optional[AuthenticationManager] = None
auth_bearer: Optional[AuthenticationBearer] = None


def init_auth(config: AuthConfig) -> tuple[AuthenticationManager, AuthenticationBearer]:
    """Initialize authentication system."""
    global auth_manager, auth_bearer
    
    auth_manager = AuthenticationManager(config)
    auth_bearer = AuthenticationBearer(auth_manager)
    
    logger.info("Authentication system initialized")
    return auth_manager, auth_bearer


def require_auth() -> Callable:
    """Dependency to require authentication."""
    return Depends(auth_bearer)


def require_permission(permission: str) -> Callable:
    """Dependency to require specific permission."""
    return Depends(PermissionChecker(permission))


def get_current_user(token_data: TokenData = Depends(require_auth)) -> TokenData:
    """Get current authenticated user."""
    return token_data