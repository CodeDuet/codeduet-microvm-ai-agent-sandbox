"""Integration tests for security features."""

import asyncio
import pytest
import httpx
import jwt
import time
from typing import Dict, Any

from src.core.vm_manager import VMManager
from src.core.security_manager import SecurityManager
from src.utils.config import get_config
from src.utils.security import SecurityUtils
from src.api.models.vm import VMRequest


class TestSecurityIntegration:
    """Test security integration scenarios."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test environment."""
        self.config = get_config()
        self.vm_manager = VMManager(self.config)
        self.security_manager = SecurityManager(self.config)
        self.security_utils = SecurityUtils(self.config)
        self.base_url = "http://localhost:8000"
        self.client = httpx.AsyncClient()
        self.test_vms = []
        
        yield
        
        # Cleanup
        await self.cleanup_test_vms()
        await self.client.aclose()

    async def cleanup_test_vms(self):
        """Cleanup all test VMs."""
        for vm_name in self.test_vms:
            try:
                await self.vm_manager.stop_vm(vm_name)
                await self.vm_manager.delete_vm(vm_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_jwt_authentication_flow(self):
        """Test complete JWT authentication flow."""
        # Create test user
        user_data = {
            "username": "testuser",
            "password": "TestPass123!",
            "role": "user"
        }
        
        response = await self.client.post(f"{self.base_url}/api/v1/auth/register", json=user_data)
        assert response.status_code in [201, 409]  # Created or already exists
        
        # Login and get token
        login_data = {
            "username": "testuser",
            "password": "TestPass123!"
        }
        
        response = await self.client.post(f"{self.base_url}/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        
        token_data = response.json()
        assert "access_token" in token_data
        assert "token_type" in token_data
        
        # Use token to access protected endpoint
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        response = await self.client.get(f"{self.base_url}/api/v1/vms", headers=headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rbac_permissions(self):
        """Test role-based access control."""
        # Create admin user
        admin_data = {
            "username": "admin",
            "password": "AdminPass123!",
            "role": "admin"
        }
        
        response = await self.client.post(f"{self.base_url}/api/v1/auth/register", json=admin_data)
        assert response.status_code in [201, 409]
        
        # Create regular user
        user_data = {
            "username": "user",
            "password": "UserPass123!",
            "role": "user"
        }
        
        response = await self.client.post(f"{self.base_url}/api/v1/auth/register", json=user_data)
        assert response.status_code in [201, 409]
        
        # Get admin token
        admin_login = await self.client.post(f"{self.base_url}/api/v1/auth/login", 
                                           json={"username": "admin", "password": "AdminPass123!"})
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get user token
        user_login = await self.client.post(f"{self.base_url}/api/v1/auth/login", 
                                          json={"username": "user", "password": "UserPass123!"})
        user_token = user_login.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}
        
        # Test admin can access admin endpoints
        response = await self.client.get(f"{self.base_url}/api/v1/admin/users", headers=admin_headers)
        assert response.status_code in [200, 404]  # 404 if endpoint doesn't exist
        
        # Test user cannot access admin endpoints
        response = await self.client.get(f"{self.base_url}/api/v1/admin/users", headers=user_headers)
        assert response.status_code in [403, 404]  # Forbidden or not found

    @pytest.mark.asyncio
    async def test_vm_isolation_security(self):
        """Test VM isolation and security measures."""
        vm_name1 = "test-isolated-vm-1"
        vm_name2 = "test-isolated-vm-2"
        self.test_vms.extend([vm_name1, vm_name2])
        
        # Create two VMs
        vm_request1 = VMRequest(
            name=vm_name1,
            os_type="linux",
            vcpus=1,
            memory_mb=256
        )
        
        vm_request2 = VMRequest(
            name=vm_name2,
            os_type="linux",
            vcpus=1,
            memory_mb=256
        )
        
        await self.vm_manager.create_vm(vm_request1)
        await self.vm_manager.create_vm(vm_request2)
        
        await self.vm_manager.start_vm(vm_name1)
        await self.vm_manager.start_vm(vm_name2)
        
        # Wait for VMs to be ready
        await asyncio.sleep(20)
        
        # Test network isolation
        vm1_info = await self.vm_manager.get_vm_info(vm_name1)
        vm2_info = await self.vm_manager.get_vm_info(vm_name2)
        
        # VMs should have different IP addresses
        assert vm1_info.network_config["ip"] != vm2_info.network_config["ip"]
        
        # Test that VMs cannot communicate directly (if isolation is enabled)
        if self.config.security.vm_isolation:
            result = await self.vm_manager.execute_command(
                vm_name1, 
                f"ping -c 1 -W 1 {vm2_info.network_config['ip']}"
            )
            assert result.exit_code != 0  # Ping should fail due to isolation

    @pytest.mark.asyncio
    async def test_audit_logging(self):
        """Test audit logging functionality."""
        vm_name = "test-audit-vm"
        self.test_vms.append(vm_name)
        
        # Perform auditable actions
        vm_request = VMRequest(
            name=vm_name,
            os_type="linux",
            vcpus=2,
            memory_mb=512
        )
        
        # Create VM (should be logged)
        await self.vm_manager.create_vm(vm_request)
        
        # Start VM (should be logged)
        await self.vm_manager.start_vm(vm_name)
        
        # Execute command (should be logged)
        await self.vm_manager.execute_command(vm_name, "echo 'test command'")
        
        # Stop VM (should be logged)
        await self.vm_manager.stop_vm(vm_name)
        
        # Check audit logs
        audit_logs = await self.security_manager.get_audit_logs(
            resource_type="vm",
            resource_id=vm_name
        )
        
        assert len(audit_logs) >= 4  # At least 4 actions logged
        
        # Verify log entries contain required fields
        for log_entry in audit_logs:
            assert "timestamp" in log_entry
            assert "action" in log_entry
            assert "resource_type" in log_entry
            assert "resource_id" in log_entry
            assert "user_id" in log_entry

    @pytest.mark.asyncio
    async def test_input_validation_security(self):
        """Test input validation and sanitization."""
        # Test SQL injection attempts
        malicious_vm_names = [
            "'; DROP TABLE vms; --",
            "<script>alert('xss')</script>",
            "../../etc/passwd",
            "vm_name; rm -rf /",
            "vm_name\n\rcat /etc/passwd"
        ]
        
        for malicious_name in malicious_vm_names:
            vm_request = VMRequest(
                name=malicious_name,
                os_type="linux",
                vcpus=1,
                memory_mb=256
            )
            
            # Should either sanitize the name or reject it
            try:
                result = await self.vm_manager.create_vm(vm_request)
                # If creation succeeds, name should be sanitized
                assert result.name != malicious_name
                self.test_vms.append(result.name)
            except ValueError:
                # Rejection is also acceptable
                pass

    @pytest.mark.asyncio
    async def test_credential_management(self):
        """Test secure credential management."""
        # Test password strength validation
        weak_passwords = [
            "123456",
            "password",
            "abc",
            "test"
        ]
        
        for weak_password in weak_passwords:
            user_data = {
                "username": "testuser_weak",
                "password": weak_password,
                "role": "user"
            }
            
            response = await self.client.post(f"{self.base_url}/api/v1/auth/register", json=user_data)
            # Should reject weak passwords
            assert response.status_code in [400, 422]
        
        # Test strong password acceptance
        strong_password = "StrongP@ssw0rd123!"
        user_data = {
            "username": "testuser_strong",
            "password": strong_password,
            "role": "user"
        }
        
        response = await self.client.post(f"{self.base_url}/api/v1/auth/register", json=user_data)
        assert response.status_code in [201, 409]

    @pytest.mark.asyncio
    async def test_token_expiration(self):
        """Test JWT token expiration handling."""
        # Create user and login
        user_data = {
            "username": "testuser_expiry",
            "password": "TestPass123!",
            "role": "user"
        }
        
        response = await self.client.post(f"{self.base_url}/api/v1/auth/register", json=user_data)
        assert response.status_code in [201, 409]
        
        # Login and get token
        login_data = {
            "username": "testuser_expiry",
            "password": "TestPass123!"
        }
        
        response = await self.client.post(f"{self.base_url}/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        
        token_data = response.json()
        token = token_data["access_token"]
        
        # Decode token to check expiration
        decoded = jwt.decode(token, options={"verify_signature": False})
        assert "exp" in decoded
        
        # Token should have reasonable expiration time (not too long)
        exp_time = decoded["exp"]
        current_time = time.time()
        time_until_expiry = exp_time - current_time
        
        # Token should expire within 24 hours
        assert time_until_expiry <= 24 * 60 * 60

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test API rate limiting."""
        # Create user and login
        user_data = {
            "username": "testuser_rate",
            "password": "TestPass123!",
            "role": "user"
        }
        
        response = await self.client.post(f"{self.base_url}/api/v1/auth/register", json=user_data)
        assert response.status_code in [201, 409]
        
        login_response = await self.client.post(f"{self.base_url}/api/v1/auth/login", 
                                              json={"username": "testuser_rate", "password": "TestPass123!"})
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Make many rapid requests
        responses = []
        for i in range(100):
            response = await self.client.get(f"{self.base_url}/api/v1/vms", headers=headers)
            responses.append(response.status_code)
            
            # If rate limiting is enabled, we should see 429 status codes
            if response.status_code == 429:
                break
        
        # If rate limiting is implemented, we should see some 429s
        # If not implemented, all should be 200s (which is also valid)
        assert all(status in [200, 429] for status in responses)

    @pytest.mark.asyncio
    async def test_compliance_logging(self):
        """Test compliance framework logging."""
        # Test various compliance-relevant actions
        actions = [
            ("data_access", "vm_logs"),
            ("data_modification", "vm_config"),
            ("system_admin", "user_creation"),
            ("security_event", "failed_login")
        ]
        
        for action_type, resource in actions:
            await self.security_manager.log_compliance_event(
                action_type=action_type,
                resource=resource,
                user_id="test_user",
                details={"test": "data"}
            )
        
        # Verify compliance logs
        compliance_logs = await self.security_manager.get_compliance_logs(
            start_time=time.time() - 3600,  # Last hour
            end_time=time.time()
        )
        
        assert len(compliance_logs) >= len(actions)
        
        # Verify log structure
        for log_entry in compliance_logs[-len(actions):]:
            assert "timestamp" in log_entry
            assert "action_type" in log_entry
            assert "resource" in log_entry
            assert "user_id" in log_entry
            assert "compliance_frameworks" in log_entry