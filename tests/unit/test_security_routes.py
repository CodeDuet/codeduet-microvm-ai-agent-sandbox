"""
Unit tests for security API routes.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

from src.api.routes.security import router
from src.api.middleware.auth import (
    AuthenticationManager, AuthConfig, TokenData
)
from src.core.security_manager import SecurityManager
from src.utils.audit import AuditLogger
from src.utils.security_scanner import VulnerabilityScanner


@pytest.fixture
def mock_auth_manager():
    """Mock authentication manager."""
    mock = Mock(spec=AuthenticationManager)
    mock.config = AuthConfig(
        jwt_secret="test-secret",
        token_expire_minutes=60
    )
    return mock


@pytest.fixture
def mock_security_manager():
    """Mock security manager."""
    mock = Mock(spec=SecurityManager)
    mock.get_security_status = AsyncMock(return_value={
        'firewall_initialized': True,
        'namespace_isolation': True,
        'monitoring_enabled': True,
        'policies_count': 5
    })
    return mock


@pytest.fixture
def mock_audit_logger():
    """Mock audit logger."""
    mock = Mock(spec=AuditLogger)
    mock.log_authentication = AsyncMock()
    mock.log_resource_access = AsyncMock()
    mock.log_configuration_change = AsyncMock()
    mock.get_audit_report = AsyncMock(return_value={
        'report_period': {
            'start': '2024-01-01T00:00:00',
            'end': '2024-01-31T23:59:59'
        },
        'summary': {
            'total_events': 150,
            'events_by_type': {
                'authentication': 50,
                'vm_operation': 75,
                'security_violation': 2
            }
        }
    })
    mock.get_statistics = Mock(return_value={
        'statistics': {
            'total_events': 150,
            'events_by_type': {'authentication': 50}
        },
        'configuration': {
            'retention_days': 2555,
            'encryption_enabled': True
        }
    })
    return mock


@pytest.fixture
def mock_token_data():
    """Mock token data for authenticated user."""
    return TokenData(
        user_id="test_user",
        email="test@example.com",
        roles=["admin"],
        permissions=["*"],
        expires_at=datetime.utcnow() + timedelta(hours=1),
        session_id="test_session_123"
    )


@pytest.fixture
def test_client():
    """Create test client with mocked dependencies."""
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    
    return TestClient(app)


class TestAuthenticationEndpoints:
    """Test authentication endpoints."""
    
    def test_login_success(self, test_client, mock_auth_manager, mock_token_data):
        """Test successful login."""
        # Mock successful authentication
        mock_auth_manager.authenticate_user.return_value = mock_token_data
        mock_auth_manager.create_jwt_token.return_value = "test.jwt.token"
        
        with patch('src.api.routes.security.Depends') as mock_depends:
            mock_depends.return_value = mock_auth_manager
            
            response = test_client.post("/api/v1/security/auth/login", json={
                "user_id": "test_user",
                "password": "StrongPassword123!"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["access_token"] == "test.jwt.token"
            assert data["user_id"] == "test_user"
            assert "admin" in data["roles"]
    
    def test_login_invalid_credentials(self, test_client, mock_auth_manager):
        """Test login with invalid credentials."""
        from src.utils.security import SecurityError
        
        # Mock authentication failure
        mock_auth_manager.authenticate_user.side_effect = SecurityError("Invalid credentials")
        
        with patch('src.api.routes.security.Depends') as mock_depends:
            mock_depends.return_value = mock_auth_manager
            
            response = test_client.post("/api/v1/security/auth/login", json={
                "user_id": "test_user",
                "password": "wrong_password"
            })
            
            assert response.status_code == 401
            assert "Invalid credentials" in response.json()["detail"]
    
    def test_logout_success(self, test_client, mock_auth_manager, mock_token_data):
        """Test successful logout."""
        mock_auth_manager.invalidate_session.return_value = True
        
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.Depends') as mock_depends:
                mock_get_user.return_value = mock_token_data
                mock_depends.return_value = mock_auth_manager
                
                response = test_client.post("/api/v1/security/auth/logout")
                
                assert response.status_code == 200
                assert "Logged out successfully" in response.json()["message"]


class TestUserManagementEndpoints:
    """Test user management endpoints."""
    
    def test_create_user_success(self, test_client, mock_auth_manager, mock_audit_logger, mock_token_data):
        """Test successful user creation."""
        mock_auth_manager.create_user.return_value = True
        
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.require_permission') as mock_require_perm:
                with patch('src.api.routes.security.Depends') as mock_depends:
                    mock_get_user.return_value = mock_token_data
                    mock_require_perm.return_value = lambda: True
                    mock_depends.side_effect = [mock_auth_manager, mock_audit_logger]
                    
                    response = test_client.post("/api/v1/security/users", json={
                        "user_id": "new_user",
                        "email": "new@example.com",
                        "password": "StrongPassword123!",
                        "roles": ["user"]
                    })
                    
                    assert response.status_code == 200
                    assert "User new_user created successfully" in response.json()["message"]
    
    def test_create_user_failure(self, test_client, mock_auth_manager, mock_audit_logger, mock_token_data):
        """Test user creation failure."""
        mock_auth_manager.create_user.return_value = False
        
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.require_permission') as mock_require_perm:
                with patch('src.api.routes.security.Depends') as mock_depends:
                    mock_get_user.return_value = mock_token_data
                    mock_require_perm.return_value = lambda: True
                    mock_depends.side_effect = [mock_auth_manager, mock_audit_logger]
                    
                    response = test_client.post("/api/v1/security/users", json={
                        "user_id": "new_user",
                        "email": "new@example.com",
                        "password": "weak",  # Weak password
                        "roles": ["user"]
                    })
                    
                    assert response.status_code == 400
                    assert "Failed to create user" in response.json()["detail"]


class TestSecurityStatusEndpoints:
    """Test security status endpoints."""
    
    def test_get_security_status(self, test_client, mock_security_manager, mock_token_data):
        """Test security status retrieval."""
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.get_security_manager') as mock_get_sm:
                mock_get_user.return_value = mock_token_data
                mock_get_sm.return_value = mock_security_manager
                
                response = test_client.get("/api/v1/security/status")
                
                assert response.status_code == 200
                data = response.json()
                assert data["firewall_enabled"] is True
                assert data["isolation_enabled"] is True
                assert data["audit_logging_enabled"] is True
                assert data["security_level"] == "ENHANCED"


class TestFirewallEndpoints:
    """Test firewall management endpoints."""
    
    def test_create_firewall_rule(self, test_client, mock_security_manager, mock_audit_logger, mock_token_data):
        """Test firewall rule creation."""
        # Mock firewall manager
        mock_firewall_manager = Mock()
        mock_firewall_manager.add_port_forwarding_rule = AsyncMock(return_value=True)
        mock_security_manager.isolation_manager.firewall_manager = mock_firewall_manager
        
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.require_permission') as mock_require_perm:
                with patch('src.api.routes.security.Depends') as mock_depends:
                    mock_get_user.return_value = mock_token_data
                    mock_require_perm.return_value = lambda: True
                    mock_depends.side_effect = [mock_security_manager, mock_audit_logger]
                    
                    response = test_client.post("/api/v1/security/firewall/rules", json={
                        "vm_name": "test-vm",
                        "rule_type": "port_forward",
                        "protocol": "tcp",
                        "dest_ip": "192.168.100.10",
                        "source_port": 8080,
                        "dest_port": 80
                    })
                    
                    assert response.status_code == 200
                    assert "Firewall rule created for VM test-vm" in response.json()["message"]
    
    def test_remove_firewall_rules(self, test_client, mock_security_manager, mock_audit_logger, mock_token_data):
        """Test firewall rule removal."""
        # Mock firewall manager
        mock_firewall_manager = Mock()
        mock_firewall_manager.remove_vm_rules = AsyncMock(return_value=True)
        mock_security_manager.isolation_manager.firewall_manager = mock_firewall_manager
        
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.require_permission') as mock_require_perm:
                with patch('src.api.routes.security.Depends') as mock_depends:
                    mock_get_user.return_value = mock_token_data
                    mock_require_perm.return_value = lambda: True
                    mock_depends.side_effect = [mock_security_manager, mock_audit_logger]
                    
                    response = test_client.delete("/api/v1/security/firewall/rules/test-vm")
                    
                    assert response.status_code == 200
                    assert "Firewall rules removed for VM test-vm" in response.json()["message"]


class TestIsolationEndpoints:
    """Test VM isolation endpoints."""
    
    def test_create_isolation_policy(self, test_client, mock_security_manager, mock_audit_logger, mock_token_data):
        """Test isolation policy creation."""
        # Mock isolation manager
        mock_isolation_manager = Mock()
        mock_isolation_manager.create_vm_network_policy = AsyncMock(return_value=True)
        mock_security_manager.isolation_manager = mock_isolation_manager
        
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.require_permission') as mock_require_perm:
                with patch('src.api.routes.security.Depends') as mock_depends:
                    mock_get_user.return_value = mock_token_data
                    mock_require_perm.return_value = lambda: True
                    mock_depends.side_effect = [mock_security_manager, mock_audit_logger]
                    
                    response = test_client.post("/api/v1/security/isolation/policy", json={
                        "vm_name": "test-vm",
                        "isolation_level": "strict",
                        "allowed_vms": ["trusted-vm"],
                        "allowed_networks": ["192.168.1.0/24"],
                        "blocked_ports": [23, 135]
                    })
                    
                    assert response.status_code == 200
                    assert "Isolation policy created for VM test-vm" in response.json()["message"]
    
    def test_get_isolation_status(self, test_client, mock_security_manager, mock_token_data):
        """Test isolation status retrieval."""
        # Mock isolation status
        mock_isolation_manager = Mock()
        mock_isolation_manager.get_isolation_status = AsyncMock(return_value={
            'vm_name': 'test-vm',
            'firewall_rules_count': 5,
            'namespace_isolation': True,
            'cgroup_isolation': True
        })
        mock_security_manager.isolation_manager = mock_isolation_manager
        
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.get_security_manager') as mock_get_sm:
                mock_get_user.return_value = mock_token_data
                mock_get_sm.return_value = mock_security_manager
                
                response = test_client.get("/api/v1/security/isolation/status/test-vm")
                
                assert response.status_code == 200
                data = response.json()
                assert data["vm_name"] == "test-vm"
                assert data["firewall_rules_count"] == 5


class TestAuditEndpoints:
    """Test audit and compliance endpoints."""
    
    def test_generate_audit_report(self, test_client, mock_audit_logger, mock_token_data):
        """Test audit report generation."""
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.require_permission') as mock_require_perm:
                with patch('src.api.routes.security.get_audit_logger') as mock_get_al:
                    mock_get_user.return_value = mock_token_data
                    mock_require_perm.return_value = lambda: True
                    mock_get_al.return_value = mock_audit_logger
                    
                    response = test_client.post("/api/v1/security/audit/report", json={
                        "start_date": "2024-01-01T00:00:00",
                        "end_date": "2024-01-31T23:59:59",
                        "event_types": ["authentication", "vm_operation"],
                        "user_id": "test_user"
                    })
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "report_period" in data
                    assert "summary" in data
    
    def test_get_audit_statistics(self, test_client, mock_audit_logger, mock_token_data):
        """Test audit statistics retrieval."""
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.require_permission') as mock_require_perm:
                with patch('src.api.routes.security.get_audit_logger') as mock_get_al:
                    mock_get_user.return_value = mock_token_data
                    mock_require_perm.return_value = lambda: True
                    mock_get_al.return_value = mock_audit_logger
                    
                    response = test_client.get("/api/v1/security/audit/statistics")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "statistics" in data
                    assert "configuration" in data


class TestSecurityPolicyEndpoints:
    """Test security policy management endpoints."""
    
    def test_update_security_policy(self, test_client, mock_audit_logger, mock_token_data):
        """Test security policy update."""
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.require_permission') as mock_require_perm:
                with patch('src.api.routes.security.get_audit_logger') as mock_get_al:
                    mock_get_user.return_value = mock_token_data
                    mock_require_perm.return_value = lambda: True
                    mock_get_al.return_value = mock_audit_logger
                    
                    response = test_client.put("/api/v1/security/policy", json={
                        "max_concurrent_vms": 25,
                        "max_vm_memory_mb": 4096,
                        "max_vm_vcpus": 4,
                        "require_authentication": True,
                        "session_timeout_minutes": 30,
                        "enable_rate_limiting": True,
                        "blocked_commands": ["rm -rf", "format"]
                    })
                    
                    assert response.status_code == 200
                    assert "Security policy updated successfully" in response.json()["message"]


class TestVulnerabilityScanningEndpoints:
    """Test vulnerability scanning endpoints."""
    
    def test_run_vulnerability_scan(self, test_client, mock_audit_logger, mock_token_data):
        """Test vulnerability scan execution."""
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.require_permission') as mock_require_perm:
                with patch('src.api.routes.security.get_audit_logger') as mock_get_al:
                    mock_get_user.return_value = mock_token_data
                    mock_require_perm.return_value = lambda: True
                    mock_get_al.return_value = mock_audit_logger
                    
                    response = test_client.post("/api/v1/security/scan/vulnerability", 
                                              params={"vm_name": "test-vm"})
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "scan_id" in data
                    assert data["target"] == "test-vm"
                    assert data["status"] == "completed"
                    assert "recommendations" in data


class TestSecurityMiddleware:
    """Test security middleware integration."""
    
    def test_authentication_required(self, test_client):
        """Test that authentication is required for protected endpoints."""
        # Try to access protected endpoint without authentication
        response = test_client.get("/api/v1/security/status")
        
        # Should return 401 or 403 (depending on FastAPI configuration)
        assert response.status_code in [401, 403, 422]  # 422 for validation error
    
    def test_permission_required(self, test_client, mock_token_data):
        """Test that proper permissions are required."""
        # Mock user with limited permissions
        limited_user = TokenData(
            user_id="limited_user",
            email="limited@example.com",
            roles=["readonly"],
            permissions=["vm:read"],
            expires_at=datetime.utcnow() + timedelta(hours=1),
            session_id="limited_session"
        )
        
        with patch('src.api.routes.security.get_current_user') as mock_get_user:
            with patch('src.api.routes.security.require_permission') as mock_require_perm:
                mock_get_user.return_value = limited_user
                
                # Mock permission check to fail
                def mock_perm_check():
                    raise HTTPException(status_code=403, detail="Permission denied")
                
                mock_require_perm.return_value = mock_perm_check
                
                response = test_client.post("/api/v1/security/users", json={
                    "user_id": "new_user",
                    "email": "new@example.com",
                    "password": "StrongPassword123!",
                    "roles": ["user"]
                })
                
                assert response.status_code == 403


@pytest.mark.asyncio
async def test_security_routes_integration():
    """Integration test for security routes."""
    # This test verifies that security routes work together correctly
    
    from fastapi import FastAPI
    from src.api.routes.security import router
    
    app = FastAPI()
    app.include_router(router)
    
    # Test that the router is properly configured
    assert router.prefix == "/api/v1/security"
    assert "security" in router.tags
    
    # Check that all expected routes are registered
    route_paths = [route.path for route in router.routes]
    
    expected_paths = [
        "/auth/login",
        "/auth/logout",
        "/users",
        "/status",
        "/firewall/rules",
        "/firewall/rules/{vm_name}",
        "/isolation/policy",
        "/isolation/status/{vm_name}",
        "/audit/report",
        "/audit/statistics",
        "/policy",
        "/scan/vulnerability"
    ]
    
    for expected_path in expected_paths:
        assert expected_path in route_paths or any(
            expected_path in path for path in route_paths
        ), f"Missing route: {expected_path}"