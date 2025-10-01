"""
Security utilities for input validation, sanitization, and security enforcement.
"""

import re
import hashlib
import secrets
import base64
import hmac
import os
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime, timedelta
import ipaddress
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Custom exception for security-related errors."""
    pass


class InputValidator:
    """Input validation and sanitization utilities."""
    
    # Regex patterns for validation
    VM_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,31}$')
    SNAPSHOT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$')
    USER_ID_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_@.-]{0,255}$')
    COMMAND_SAFE_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_./=:@]+$')
    
    # Dangerous characters and strings
    DANGEROUS_CHARS = ['<', '>', '&', '"', "'", ';', '|', '`', '$', '(', ')']
    DANGEROUS_COMMANDS = [
        'rm -rf', 'format', 'del /q', 'shutdown', 'reboot', 'halt',
        'mkfs', 'fdisk', 'dd if=', 'wget', 'curl', 'nc ', 'netcat'
    ]
    
    @classmethod
    def validate_vm_name(cls, name: str) -> str:
        """Validate and sanitize VM name."""
        if not isinstance(name, str):
            raise SecurityError("VM name must be a string")
        
        name = name.strip()
        if not name:
            raise SecurityError("VM name cannot be empty")
        
        if len(name) > 32:
            raise SecurityError("VM name cannot exceed 32 characters")
        
        if not cls.VM_NAME_PATTERN.match(name):
            raise SecurityError(
                "VM name can only contain alphanumeric characters, "
                "hyphens, and underscores, and must start with alphanumeric"
            )
        
        return name
    
    @classmethod
    def validate_snapshot_name(cls, name: str) -> str:
        """Validate and sanitize snapshot name."""
        if not isinstance(name, str):
            raise SecurityError("Snapshot name must be a string")
        
        name = name.strip()
        if not name:
            raise SecurityError("Snapshot name cannot be empty")
        
        if len(name) > 64:
            raise SecurityError("Snapshot name cannot exceed 64 characters")
        
        if not cls.SNAPSHOT_NAME_PATTERN.match(name):
            raise SecurityError(
                "Snapshot name can only contain alphanumeric characters, "
                "hyphens, underscores, and dots, and must start with alphanumeric"
            )
        
        return name
    
    @classmethod
    def validate_user_id(cls, user_id: str) -> str:
        """Validate and sanitize user ID."""
        if not isinstance(user_id, str):
            raise SecurityError("User ID must be a string")
        
        user_id = user_id.strip()
        if not user_id:
            raise SecurityError("User ID cannot be empty")
        
        if len(user_id) > 256:
            raise SecurityError("User ID cannot exceed 256 characters")
        
        if not cls.USER_ID_PATTERN.match(user_id):
            raise SecurityError(
                "User ID contains invalid characters. "
                "Only alphanumeric, @, ., -, and _ are allowed"
            )
        
        return user_id
    
    @classmethod
    def validate_ip_address(cls, ip: str) -> str:
        """Validate IP address format."""
        try:
            validated_ip = ipaddress.ip_address(ip.strip())
            return str(validated_ip)
        except ValueError as e:
            raise SecurityError(f"Invalid IP address format: {e}")
    
    @classmethod
    def validate_port(cls, port: Union[int, str]) -> int:
        """Validate port number."""
        try:
            port_num = int(port)
            if not (1 <= port_num <= 65535):
                raise SecurityError("Port must be between 1 and 65535")
            return port_num
        except (ValueError, TypeError):
            raise SecurityError("Port must be a valid integer")
    
    @classmethod
    def validate_path(cls, path: str, allow_absolute: bool = False) -> str:
        """Validate and sanitize file path."""
        if not isinstance(path, str):
            raise SecurityError("Path must be a string")
        
        path = path.strip()
        if not path:
            raise SecurityError("Path cannot be empty")
        
        # Check for path traversal attempts
        if '..' in path or '~' in path:
            raise SecurityError("Path traversal attempts are not allowed")
        
        # Check for dangerous characters
        for char in ['<', '>', '|', '?', '*', '"']:
            if char in path:
                raise SecurityError(f"Path contains invalid character: {char}")
        
        # Validate absolute vs relative paths
        if os.path.isabs(path) and not allow_absolute:
            raise SecurityError("Absolute paths are not allowed")
        
        # Normalize path
        try:
            normalized = os.path.normpath(path)
            if normalized != path and '..' in normalized:
                raise SecurityError("Invalid path structure")
            return normalized
        except Exception as e:
            raise SecurityError(f"Path validation failed: {e}")
    
    @classmethod
    def sanitize_command(cls, command: str) -> str:
        """Sanitize command for safe execution."""
        if not isinstance(command, str):
            raise SecurityError("Command must be a string")
        
        command = command.strip()
        if not command:
            raise SecurityError("Command cannot be empty")
        
        # Check for dangerous commands
        command_lower = command.lower()
        for dangerous_cmd in cls.DANGEROUS_COMMANDS:
            if dangerous_cmd in command_lower:
                raise SecurityError(f"Dangerous command detected: {dangerous_cmd}")
        
        # Check for dangerous characters
        for char in cls.DANGEROUS_CHARS:
            if char in command:
                raise SecurityError(f"Command contains dangerous character: {char}")
        
        # Validate against safe pattern
        if not cls.COMMAND_SAFE_PATTERN.match(command):
            raise SecurityError("Command contains invalid characters")
        
        return command
    
    @classmethod
    def validate_resource_limits(cls, vcpus: int, memory_mb: int) -> tuple[int, int]:
        """Validate VM resource limits."""
        if not isinstance(vcpus, int) or vcpus < 1:
            raise SecurityError("vCPUs must be a positive integer")
        
        if vcpus > 32:
            raise SecurityError("vCPUs cannot exceed 32")
        
        if not isinstance(memory_mb, int) or memory_mb < 64:
            raise SecurityError("Memory must be at least 64 MB")
        
        if memory_mb > 32768:  # 32 GB
            raise SecurityError("Memory cannot exceed 32 GB")
        
        return vcpus, memory_mb


class CredentialManager:
    """Secure credential management with encryption."""
    
    def __init__(self, master_key: Optional[bytes] = None):
        """Initialize credential manager."""
        if master_key:
            self._fernet = Fernet(master_key)
        else:
            self._fernet = None
    
    @staticmethod
    def generate_master_key() -> bytes:
        """Generate a new master key for encryption."""
        return Fernet.generate_key()
    
    @staticmethod
    def derive_key_from_password(password: str, salt: bytes) -> bytes:
        """Derive encryption key from password."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt_credential(self, credential: str) -> str:
        """Encrypt a credential string."""
        if not self._fernet:
            raise SecurityError("Credential manager not initialized with master key")
        
        encrypted = self._fernet.encrypt(credential.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_credential(self, encrypted_credential: str) -> str:
        """Decrypt a credential string."""
        if not self._fernet:
            raise SecurityError("Credential manager not initialized with master key")
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_credential.encode())
            decrypted = self._fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            raise SecurityError(f"Failed to decrypt credential: {e}")
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate a secure session token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, bytes]:
        """Hash password with salt."""
        if salt is None:
            salt = secrets.token_bytes(32)
        
        pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return base64.urlsafe_b64encode(pwdhash).decode(), salt
    
    @staticmethod
    def verify_password(password: str, hash_str: str, salt: bytes) -> bool:
        """Verify password against hash."""
        try:
            expected_hash = base64.urlsafe_b64decode(hash_str.encode())
            actual_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
            return hmac.compare_digest(expected_hash, actual_hash)
        except Exception:
            return False


class SecurityPolicy:
    """Security policy enforcement."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize security policy."""
        self.config = config
        self.max_concurrent_vms = config.get('max_concurrent_vms', 50)
        self.max_vm_memory = config.get('max_vm_memory_mb', 8192)
        self.max_vm_vcpus = config.get('max_vm_vcpus', 8)
        self.allowed_networks = config.get('allowed_networks', [])
        self.blocked_commands = config.get('blocked_commands', [])
        self.require_authentication = config.get('require_authentication', True)
        self.session_timeout = config.get('session_timeout_minutes', 60)
    
    def validate_vm_creation(self, vm_config: Dict[str, Any], user_id: str) -> bool:
        """Validate VM creation against security policy."""
        # Check resource limits
        vcpus = vm_config.get('vcpus', 1)
        memory_mb = vm_config.get('memory_mb', 512)
        
        if vcpus > self.max_vm_vcpus:
            raise SecurityError(f"vCPUs exceed policy limit: {self.max_vm_vcpus}")
        
        if memory_mb > self.max_vm_memory:
            raise SecurityError(f"Memory exceeds policy limit: {self.max_vm_memory} MB")
        
        # Additional policy checks can be added here
        return True
    
    def validate_command_execution(self, command: str, user_id: str) -> bool:
        """Validate command execution against security policy."""
        command_lower = command.lower()
        for blocked_cmd in self.blocked_commands:
            if blocked_cmd.lower() in command_lower:
                raise SecurityError(f"Command blocked by policy: {blocked_cmd}")
        
        return True
    
    def validate_network_access(self, ip_address: str, port: int, user_id: str) -> bool:
        """Validate network access against security policy."""
        if self.allowed_networks:
            ip = ipaddress.ip_address(ip_address)
            allowed = False
            for network in self.allowed_networks:
                if ip in ipaddress.ip_network(network):
                    allowed = True
                    break
            
            if not allowed:
                raise SecurityError(f"Network access denied: {ip_address}")
        
        return True


class AuditLogger:
    """Security audit logging system."""
    
    def __init__(self, log_file: Optional[str] = None):
        """Initialize audit logger."""
        self.logger = logging.getLogger('security_audit')
        if log_file:
            handler = logging.FileHandler(log_file)
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_authentication(self, user_id: str, success: bool, ip_address: str):
        """Log authentication attempts."""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(
            f"AUTH {status}: user={user_id}, ip={ip_address}, "
            f"timestamp={datetime.utcnow().isoformat()}"
        )
    
    def log_vm_operation(self, operation: str, vm_name: str, user_id: str, 
                        success: bool, details: str = ""):
        """Log VM operations."""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(
            f"VM_OP {status}: operation={operation}, vm={vm_name}, "
            f"user={user_id}, details={details}, "
            f"timestamp={datetime.utcnow().isoformat()}"
        )
    
    def log_command_execution(self, command: str, vm_name: str, user_id: str,
                            success: bool, output: str = ""):
        """Log command executions."""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(
            f"CMD_EXEC {status}: command={command[:100]}, vm={vm_name}, "
            f"user={user_id}, output_length={len(output)}, "
            f"timestamp={datetime.utcnow().isoformat()}"
        )
    
    def log_security_violation(self, violation_type: str, user_id: str,
                             details: str, ip_address: str = ""):
        """Log security violations."""
        self.logger.warning(
            f"SECURITY_VIOLATION: type={violation_type}, user={user_id}, "
            f"ip={ip_address}, details={details}, "
            f"timestamp={datetime.utcnow().isoformat()}"
        )
    
    def log_resource_access(self, resource_type: str, resource_id: str,
                          user_id: str, action: str):
        """Log resource access."""
        self.logger.info(
            f"RESOURCE_ACCESS: type={resource_type}, id={resource_id}, "
            f"user={user_id}, action={action}, "
            f"timestamp={datetime.utcnow().isoformat()}"
        )


class SecurityEnforcer:
    """Main security enforcement class."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize security enforcer."""
        self.validator = InputValidator()
        self.credential_manager = CredentialManager()
        self.policy = SecurityPolicy(config.get('security_policy', {}))
        self.audit_logger = AuditLogger(config.get('audit_log_file'))
        self.rate_limits = {}
        self.failed_attempts = {}
    
    def validate_and_sanitize_input(self, input_type: str, value: Any) -> Any:
        """Validate and sanitize input based on type."""
        if input_type == 'vm_name':
            return self.validator.validate_vm_name(value)
        elif input_type == 'snapshot_name':
            return self.validator.validate_snapshot_name(value)
        elif input_type == 'user_id':
            return self.validator.validate_user_id(value)
        elif input_type == 'ip_address':
            return self.validator.validate_ip_address(value)
        elif input_type == 'port':
            return self.validator.validate_port(value)
        elif input_type == 'path':
            return self.validator.validate_path(value)
        elif input_type == 'command':
            return self.validator.sanitize_command(value)
        else:
            raise SecurityError(f"Unknown input type: {input_type}")
    
    def check_rate_limit(self, user_id: str, operation: str, 
                        limit: int = 10, window_minutes: int = 1) -> bool:
        """Check rate limiting for operations."""
        now = datetime.utcnow()
        key = f"{user_id}:{operation}"
        
        if key not in self.rate_limits:
            self.rate_limits[key] = []
        
        # Clean old entries
        cutoff = now - timedelta(minutes=window_minutes)
        self.rate_limits[key] = [
            timestamp for timestamp in self.rate_limits[key]
            if timestamp > cutoff
        ]
        
        # Check limit
        if len(self.rate_limits[key]) >= limit:
            self.audit_logger.log_security_violation(
                "RATE_LIMIT_EXCEEDED", user_id,
                f"Operation: {operation}, Limit: {limit}/{window_minutes}min"
            )
            return False
        
        # Add current request
        self.rate_limits[key].append(now)
        return True
    
    def track_failed_attempt(self, user_id: str, ip_address: str) -> bool:
        """Track failed authentication attempts."""
        now = datetime.utcnow()
        key = f"{user_id}:{ip_address}"
        
        if key not in self.failed_attempts:
            self.failed_attempts[key] = []
        
        # Clean old entries (last hour)
        cutoff = now - timedelta(hours=1)
        self.failed_attempts[key] = [
            timestamp for timestamp in self.failed_attempts[key]
            if timestamp > cutoff
        ]
        
        self.failed_attempts[key].append(now)
        
        # Check if account should be locked (5 failures in 1 hour)
        if len(self.failed_attempts[key]) >= 5:
            self.audit_logger.log_security_violation(
                "ACCOUNT_LOCKOUT", user_id,
                f"5 failed attempts from {ip_address} in 1 hour"
            )
            return True
        
        return False
    
    def clear_failed_attempts(self, user_id: str, ip_address: str):
        """Clear failed attempts after successful authentication."""
        key = f"{user_id}:{ip_address}"
        if key in self.failed_attempts:
            del self.failed_attempts[key]