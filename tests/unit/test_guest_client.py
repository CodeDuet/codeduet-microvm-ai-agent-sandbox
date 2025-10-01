"""
Unit tests for guest client functionality.
"""

import pytest
import asyncio
import json
import tempfile
import os
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from pathlib import Path

from src.core.guest_client import GuestClient, GuestManager, GuestClientError
from src.api.models.vm import OSType


class TestGuestClient:
    """Test guest client functionality."""
    
    @pytest.fixture
    def linux_client(self):
        """Create a Linux guest client."""
        return GuestClient("test-vm", OSType.LINUX)
    
    @pytest.fixture
    def windows_client(self):
        """Create a Windows guest client."""
        return GuestClient("test-vm", OSType.WINDOWS)
    
    @pytest.mark.asyncio
    async def test_ping_success(self, linux_client):
        """Test successful ping operation."""
        mock_response = {
            "success": True,
            "message": "pong",
            "agent_version": "1.0.0",
            "os": "linux"
        }
        
        with patch.object(linux_client, '_send_unix_socket', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            
            result = await linux_client.ping()
            
            assert result == mock_response
            mock_send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_command_success(self, linux_client):
        """Test successful command execution."""
        mock_response = {
            "success": True,
            "exit_code": 0,
            "stdout": "Hello World\n",
            "stderr": ""
        }
        
        with patch.object(linux_client, '_send_unix_socket', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            
            result = await linux_client.execute_command("echo 'Hello World'")
            
            assert result == mock_response
            mock_send.assert_called_once()
            
            # Check that the command was properly formatted
            call_args = mock_send.call_args[0][0]
            assert call_args["command"] == "execute"
            assert call_args["params"]["command"] == "echo 'Hello World'"
    
    @pytest.mark.asyncio
    async def test_execute_command_with_options(self, linux_client):
        """Test command execution with additional options."""
        mock_response = {
            "success": True,
            "exit_code": 0,
            "stdout": "output",
            "stderr": ""
        }
        
        with patch.object(linux_client, '_send_unix_socket', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            
            result = await linux_client.execute_command(
                "ls -la",
                timeout=60,
                working_dir="/tmp",
                env={"TEST_VAR": "test_value"}
            )
            
            assert result == mock_response
            call_args = mock_send.call_args[0][0]
            assert call_args["params"]["timeout"] == 60
            assert call_args["params"]["working_dir"] == "/tmp"
            assert call_args["params"]["env"]["TEST_VAR"] == "test_value"
    
    @pytest.mark.asyncio
    async def test_upload_file_success(self, linux_client):
        """Test successful file upload."""
        mock_response = {
            "success": True,
            "path": "/tmp/test.txt",
            "size": 12,
            "checksum": "abc123"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test content")
            temp_file_path = temp_file.name
        
        try:
            with patch.object(linux_client, '_send_unix_socket', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = mock_response
                
                result = await linux_client.upload_file(
                    temp_file_path,
                    "/tmp/test.txt",
                    create_dirs=True
                )
                
                assert result == mock_response
                call_args = mock_send.call_args[0][0]
                assert call_args["command"] == "upload_file"
                assert call_args["params"]["path"] == "/tmp/test.txt"
                assert call_args["params"]["create_dirs"] is True
                assert "content" in call_args["params"]
        finally:
            os.unlink(temp_file_path)
    
    @pytest.mark.asyncio
    async def test_upload_file_not_found(self, linux_client):
        """Test upload with non-existent file."""
        with pytest.raises(GuestClientError, match="Local file not found"):
            await linux_client.upload_file("/nonexistent/file.txt", "/tmp/test.txt")
    
    @pytest.mark.asyncio
    async def test_download_file_success(self, linux_client):
        """Test successful file download."""
        import base64
        import hashlib
        
        test_content = b"test file content"
        actual_checksum = hashlib.sha256(test_content).hexdigest()
        mock_response = {
            "success": True,
            "path": "/tmp/test.txt",
            "size": len(test_content),
            "content": base64.b64encode(test_content).decode('ascii'),
            "checksum": actual_checksum
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = os.path.join(temp_dir, "downloaded.txt")
            
            with patch.object(linux_client, '_send_unix_socket', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = mock_response
                
                result = await linux_client.download_file("/tmp/test.txt", local_path)
                
                assert result == mock_response
                assert os.path.exists(local_path)
                
                with open(local_path, 'rb') as f:
                    downloaded_content = f.read()
                assert downloaded_content == test_content
    
    @pytest.mark.asyncio
    async def test_get_system_info_success(self, linux_client):
        """Test successful system info retrieval."""
        mock_response = {
            "success": True,
            "system_info": {
                "hostname": "test-vm",
                "kernel": "Linux 5.4.0",
                "architecture": "x86_64",
                "uptime": 3600.0
            }
        }
        
        with patch.object(linux_client, '_send_unix_socket', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            
            result = await linux_client.get_system_info()
            
            assert result == mock_response
            call_args = mock_send.call_args[0][0]
            assert call_args["command"] == "get_system_info"
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, linux_client):
        """Test successful health check."""
        mock_response = {
            "success": True,
            "health": {
                "agent_status": "healthy",
                "uptime": 3600.0,
                "memory_usage": 45.2,
                "disk_usage": 23.1
            }
        }
        
        with patch.object(linux_client, '_send_unix_socket', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_response
            
            result = await linux_client.health_check()
            
            assert result == mock_response
            call_args = mock_send.call_args[0][0]
            assert call_args["command"] == "health_check"
    
    @pytest.mark.asyncio
    async def test_windows_specific_methods(self, windows_client):
        """Test Windows-specific methods."""
        mock_services_response = {
            "success": True,
            "services": [
                {"name": "Spooler", "state": "Running"},
                {"name": "DHCP", "state": "Stopped"}
            ]
        }
        
        mock_events_response = {
            "success": True,
            "events": [
                {"event_id": 1001, "source": "System", "message": "Test event"}
            ]
        }
        
        with patch.object(windows_client, '_send_named_pipe', new_callable=AsyncMock) as mock_send:
            # Test get_services
            mock_send.return_value = mock_services_response
            result = await windows_client.get_services()
            assert result == mock_services_response
            
            # Test get_event_logs
            mock_send.return_value = mock_events_response
            result = await windows_client.get_event_logs("Application", 50)
            assert result == mock_events_response
    
    @pytest.mark.asyncio
    async def test_windows_methods_on_linux_client(self, linux_client):
        """Test that Windows-specific methods raise errors on Linux clients."""
        with pytest.raises(GuestClientError, match="only available on Windows"):
            await linux_client.get_services()
        
        with pytest.raises(GuestClientError, match="only available on Windows"):
            await linux_client.get_event_logs()
    
    @pytest.mark.asyncio
    async def test_communication_error(self, linux_client):
        """Test communication error handling."""
        with patch.object(linux_client, '_send_unix_socket', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("Connection failed")
            
            with pytest.raises(GuestClientError, match="Communication failed"):
                await linux_client.ping()
    
    @pytest.mark.asyncio
    async def test_unix_socket_timeout(self, linux_client):
        """Test Unix socket timeout handling."""
        with patch('asyncio.open_unix_connection', new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(GuestClientError, match="Connection timeout"):
                await linux_client._send_unix_socket({"test": "message"})
    
    @pytest.mark.asyncio
    async def test_unix_socket_file_not_found(self, linux_client):
        """Test Unix socket file not found error."""
        with patch('asyncio.open_unix_connection', new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = FileNotFoundError()
            
            with pytest.raises(GuestClientError, match="Guest agent socket not found"):
                await linux_client._send_unix_socket({"test": "message"})


class TestGuestManager:
    """Test guest manager functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create a guest manager."""
        return GuestManager()
    
    def test_get_client_creates_new(self, manager):
        """Test that get_client creates a new client."""
        client = manager.get_client("test-vm", OSType.LINUX)
        
        assert isinstance(client, GuestClient)
        assert client.vm_name == "test-vm"
        assert client.os_type == OSType.LINUX
    
    def test_get_client_reuses_existing(self, manager):
        """Test that get_client reuses existing clients."""
        client1 = manager.get_client("test-vm", OSType.LINUX)
        client2 = manager.get_client("test-vm", OSType.LINUX)
        
        assert client1 is client2
    
    def test_get_client_different_vms(self, manager):
        """Test that different VMs get different clients."""
        client1 = manager.get_client("vm1", OSType.LINUX)
        client2 = manager.get_client("vm2", OSType.LINUX)
        
        assert client1 is not client2
    
    def test_get_client_different_os_types(self, manager):
        """Test that different OS types get different clients."""
        client1 = manager.get_client("test-vm", OSType.LINUX)
        client2 = manager.get_client("test-vm", OSType.WINDOWS)
        
        assert client1 is not client2
    
    def test_remove_client(self, manager):
        """Test client removal."""
        client = manager.get_client("test-vm", OSType.LINUX)
        assert len(manager.clients) == 1
        
        manager.remove_client("test-vm", OSType.LINUX)
        assert len(manager.clients) == 0
    
    @pytest.mark.asyncio
    async def test_ping_all(self, manager):
        """Test ping all clients."""
        # Create some clients
        manager.get_client("vm1", OSType.LINUX)
        manager.get_client("vm2", OSType.WINDOWS)
        
        mock_ping_response = {"success": True, "message": "pong"}
        
        with patch.object(GuestClient, 'ping', new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = mock_ping_response
            
            results = await manager.ping_all()
            
            assert len(results) == 2
            assert "vm1:linux" in results
            assert "vm2:windows" in results
            assert all(result == mock_ping_response for result in results.values())
    
    @pytest.mark.asyncio
    async def test_ping_all_with_errors(self, manager):
        """Test ping all with some clients failing."""
        # Create some clients
        manager.get_client("vm1", OSType.LINUX)
        manager.get_client("vm2", OSType.LINUX)
        
        def ping_side_effect(*args, **kwargs):
            # First call succeeds, second fails
            if not hasattr(ping_side_effect, 'call_count'):
                ping_side_effect.call_count = 0
            ping_side_effect.call_count += 1
            
            if ping_side_effect.call_count == 1:
                return {"success": True, "message": "pong"}
            else:
                raise GuestClientError("Connection failed")
        
        with patch.object(GuestClient, 'ping', new_callable=AsyncMock) as mock_ping:
            mock_ping.side_effect = ping_side_effect
            
            results = await manager.ping_all()
            
            assert len(results) == 2
            assert results["vm1:linux"]["success"] is True
            assert results["vm2:linux"]["success"] is False
            assert "Connection failed" in results["vm2:linux"]["error"]
    
    @pytest.mark.asyncio
    async def test_health_check_all(self, manager):
        """Test health check all clients."""
        manager.get_client("vm1", OSType.LINUX)
        
        mock_health_response = {
            "success": True,
            "health": {"agent_status": "healthy"}
        }
        
        with patch.object(GuestClient, 'health_check', new_callable=AsyncMock) as mock_health:
            mock_health.return_value = mock_health_response
            
            results = await manager.health_check_all()
            
            assert len(results) == 1
            assert results["vm1:linux"] == mock_health_response