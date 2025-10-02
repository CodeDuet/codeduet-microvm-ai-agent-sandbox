"""
Unit tests for MicroVM client functionality.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime
import httpx

from microvm_client import (
    MicroVMClient, 
    VMInfo, 
    VMState, 
    CommandResult, 
    FileTransferResult,
    ValidationError,
    AuthenticationError,
    NetworkError,
    VMNotFoundError
)


class TestMicroVMClient:
    """Test MicroVM client functionality."""
    
    def test_init_https_enforcement(self):
        """Test HTTPS is enforced for non-localhost."""
        # Should allow HTTP for localhost
        client = MicroVMClient("http://localhost:8000")
        assert client.api_url == "http://localhost:8000"
        
        client = MicroVMClient("http://127.0.0.1:8000")
        assert client.api_url == "http://127.0.0.1:8000"
        
        # Should reject HTTP for other hosts
        with pytest.raises(ValidationError, match="HTTPS required"):
            MicroVMClient("http://example.com:8000")
    
    @pytest.mark.asyncio
    async def test_context_manager_auth_success(self):
        """Test successful authentication in context manager."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock successful health check
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            
            client = MicroVMClient("https://api.example.com", api_token="test-token")
            
            async with client:
                mock_client.get.assert_called_once_with("/health")
    
    @pytest.mark.asyncio
    async def test_context_manager_auth_failure(self):
        """Test authentication failure in context manager."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock auth failure
            mock_response = Mock()
            mock_response.status_code = 401
            mock_client.get.return_value = mock_response
            
            client = MicroVMClient("https://api.example.com", api_token="bad-token")
            
            with pytest.raises(AuthenticationError, match="Invalid API token"):
                async with client:
                    pass
    
    @pytest.mark.asyncio
    async def test_start_vm_success(self):
        """Test successful VM creation."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock responses
            health_response = Mock(status_code=200)
            vm_response = Mock(status_code=201)
            vm_response.json.return_value = {
                "id": "vm-123",
                "name": "test-vm",
                "state": "running",
                "template": "ai-agent",
                "vcpus": 4,
                "memory_mb": 4096,
                "ip_address": "192.168.1.100",
                "created_at": "2024-01-01T00:00:00Z"
            }
            
            mock_client.get.return_value = health_response
            mock_client.post.return_value = vm_response
            
            client = MicroVMClient("https://api.example.com")
            
            async with client:
                vm = await client.start_vm("ai-agent", {"vcpus": 4})
                
                assert vm.id == "vm-123"
                assert vm.state == VMState.RUNNING
                assert vm.template == "ai-agent"
                assert vm.vcpus == 4
                mock_client.post.assert_called_once_with(
                    "/api/v1/vms", 
                    json={"template": "ai-agent", "vcpus": 4}
                )
    
    @pytest.mark.asyncio
    async def test_start_vm_invalid_template(self):
        """Test VM creation with invalid template name."""
        client = MicroVMClient("https://api.example.com")
        
        with pytest.raises(ValidationError, match="Invalid template name"):
            await client.start_vm("invalid template name!")
    
    @pytest.mark.asyncio
    async def test_exec_command_success(self):
        """Test successful command execution."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock responses
            health_response = Mock(status_code=200)
            cmd_response = Mock(status_code=200)
            cmd_response.json.return_value = {
                "success": True,
                "exit_code": 0,
                "stdout": "Python 3.11.0",
                "stderr": "",
                "execution_time_ms": 150
            }
            
            mock_client.get.return_value = health_response
            mock_client.post.return_value = cmd_response
            
            client = MicroVMClient("https://api.example.com")
            
            async with client:
                result = await client.exec_command("vm-123", "python --version")
                
                assert result.success is True
                assert result.exit_code == 0
                assert result.stdout == "Python 3.11.0"
                assert result.execution_time_ms == 150
    
    @pytest.mark.asyncio
    async def test_exec_command_dangerous(self):
        """Test dangerous command is blocked."""
        client = MicroVMClient("https://api.example.com")
        
        with pytest.raises(ValidationError, match="forbidden pattern"):
            await client.exec_command("vm-123", "rm -rf /")
    
    @pytest.mark.asyncio
    async def test_exec_command_vm_not_found(self):
        """Test command execution with non-existent VM."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock responses
            health_response = Mock(status_code=200)
            cmd_response = Mock(status_code=404)
            
            mock_client.get.return_value = health_response
            mock_client.post.return_value = cmd_response
            
            client = MicroVMClient("https://api.example.com")
            
            async with client:
                with pytest.raises(VMNotFoundError):
                    await client.exec_command("non-existent", "echo test")
    
    @pytest.mark.asyncio
    async def test_upload_file_success(self):
        """Test successful file upload."""
        with patch('httpx.AsyncClient') as mock_client_class, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('builtins.open') as mock_open:
            
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock file size (1MB)
            mock_stat.return_value.st_size = 1024 * 1024
            
            # Mock file content
            mock_open.return_value.__enter__.return_value = Mock()
            
            # Mock responses
            health_response = Mock(status_code=200)
            upload_response = Mock(status_code=200)
            upload_response.json.return_value = {
                "success": True,
                "size_bytes": 1024 * 1024,
                "checksum": "abc123"
            }
            
            mock_client.get.return_value = health_response
            mock_client.post.return_value = upload_response
            
            client = MicroVMClient("https://api.example.com")
            
            async with client:
                result = await client.upload_file("vm-123", "test.py", "/tmp/test.py")
                
                assert result.success is True
                assert result.size_bytes == 1024 * 1024
                assert result.checksum == "abc123"
    
    @pytest.mark.asyncio
    async def test_upload_file_too_large(self):
        """Test file upload size limit."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('httpx.AsyncClient'):
            
            # Mock large file (20MB)
            mock_stat.return_value.st_size = 20 * 1024 * 1024
            
            client = MicroVMClient("https://api.example.com")
            
            with pytest.raises(ValidationError, match="File too large"):
                await client.upload_file("vm-123", "large.file", "/tmp/large.file")
    
    @pytest.mark.asyncio  
    async def test_upload_file_path_traversal(self):
        """Test path traversal protection in file upload."""
        with patch('httpx.AsyncClient'):
            client = MicroVMClient("https://api.example.com")
            
            with pytest.raises(ValidationError, match="traversal"):
                await client.upload_file("vm-123", "test.py", "../../../etc/passwd")
    
    @pytest.mark.asyncio
    async def test_destroy_vm_success(self):
        """Test successful VM destruction."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock responses
            health_response = Mock(status_code=200)
            delete_response = Mock(status_code=204)
            
            mock_client.get.return_value = health_response
            mock_client.delete.return_value = delete_response
            
            client = MicroVMClient("https://api.example.com")
            
            async with client:
                await client.destroy_vm("vm-123")
                
                mock_client.delete.assert_called_once_with("/api/v1/vms/vm-123")
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self):
        """Test network error handling."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock network error
            mock_client.get.side_effect = httpx.RequestError("Connection failed")
            
            client = MicroVMClient("https://api.example.com")
            
            with pytest.raises(NetworkError, match="Connection failed"):
                async with client:
                    pass