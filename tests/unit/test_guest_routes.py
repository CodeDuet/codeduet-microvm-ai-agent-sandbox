"""
Unit tests for guest API routes.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from src.api.server import app
from src.api.models.vm import OSType, VMState, VMInfo
from src.core.guest_client import GuestClientError


class TestGuestRoutes:
    """Test guest API routes."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_vm_info(self):
        """Create mock VM info."""
        return VMInfo(
            name="test-vm",
            state=VMState.RUNNING,
            vcpus=2,
            memory_mb=1024,
            os_type=OSType.LINUX,
            template="linux-default",
            guest_agent=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={}
        )
    
    def test_ping_guest_success(self, client, mock_vm_info):
        """Test successful guest ping."""
        mock_ping_response = {
            "success": True,
            "message": "pong",
            "agent_version": "1.0.0",
            "os": "linux"
        }
        
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.ping = AsyncMock(return_value=mock_ping_response)
            mock_get_client.return_value = mock_guest_client
            
            response = client.post("/api/v1/vms/test-vm/guest/ping")
            
            assert response.status_code == 200
            assert response.json() == mock_ping_response
    
    def test_ping_guest_vm_not_found(self, client):
        """Test ping with non-existent VM."""
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm:
            mock_get_vm.return_value = None
            
            response = client.post("/api/v1/vms/nonexistent/guest/ping")
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]
    
    def test_ping_guest_agent_disabled(self, client, mock_vm_info):
        """Test ping with guest agent disabled."""
        mock_vm_info.guest_agent = False
        
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm:
            mock_get_vm.return_value = mock_vm_info
            
            response = client.post("/api/v1/vms/test-vm/guest/ping")
            
            assert response.status_code == 400
            assert "not enabled" in response.json()["detail"]
    
    def test_ping_guest_communication_error(self, client, mock_vm_info):
        """Test ping with communication error."""
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.ping = AsyncMock(side_effect=GuestClientError("Connection failed"))
            mock_get_client.return_value = mock_guest_client
            
            response = client.post("/api/v1/vms/test-vm/guest/ping")
            
            assert response.status_code == 503
            assert "Guest communication failed" in response.json()["detail"]
    
    def test_execute_command_success(self, client, mock_vm_info):
        """Test successful command execution."""
        mock_response = {
            "success": True,
            "exit_code": 0,
            "stdout": "Hello World\n",
            "stderr": ""
        }
        
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.execute_command = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_guest_client
            
            request_data = {
                "command": "echo 'Hello World'",
                "timeout": 30
            }
            
            response = client.post("/api/v1/vms/test-vm/guest/execute", json=request_data)
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["exit_code"] == 0
            assert response_data["stdout"] == "Hello World\n"
    
    def test_execute_command_with_options(self, client, mock_vm_info):
        """Test command execution with additional options."""
        mock_response = {
            "success": True,
            "exit_code": 0,
            "stdout": "output",
            "stderr": ""
        }
        
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.execute_command = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_guest_client
            
            request_data = {
                "command": "ls -la",
                "timeout": 60,
                "working_dir": "/tmp",
                "env": {"TEST_VAR": "test_value"}
            }
            
            response = client.post("/api/v1/vms/test-vm/guest/execute", json=request_data)
            
            assert response.status_code == 200
            
            # Verify the client was called with correct parameters
            mock_guest_client.execute_command.assert_called_once_with(
                command="ls -la",
                timeout=60,
                working_dir="/tmp",
                env={"TEST_VAR": "test_value"}
            )
    
    def test_upload_file_success(self, client, mock_vm_info):
        """Test successful file upload."""
        mock_response = {
            "success": True,
            "path": "/tmp/test.txt",
            "size": 12,
            "checksum": "abc123"
        }
        
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.upload_file = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_guest_client
            
            request_data = {
                "local_path": "/host/test.txt",
                "remote_path": "/tmp/test.txt",
                "create_dirs": True,
                "mode": 644
            }
            
            response = client.post("/api/v1/vms/test-vm/guest/files/upload", json=request_data)
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["path"] == "/tmp/test.txt"
    
    def test_download_file_success(self, client, mock_vm_info):
        """Test successful file download."""
        mock_response = {
            "success": True,
            "path": "/tmp/test.txt",
            "size": 12,
            "checksum": "abc123"
        }
        
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.download_file = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_guest_client
            
            request_data = {
                "remote_path": "/tmp/test.txt",
                "local_path": "/host/test.txt",
                "max_size": 1048576
            }
            
            response = client.post("/api/v1/vms/test-vm/guest/files/download", json=request_data)
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
    
    def test_get_system_info_success(self, client, mock_vm_info):
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
        
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.get_system_info = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_guest_client
            
            response = client.get("/api/v1/vms/test-vm/guest/system-info")
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert "system_info" in response_data
    
    def test_get_process_list_success(self, client, mock_vm_info):
        """Test successful process list retrieval."""
        mock_response = {
            "success": True,
            "processes": [
                {"pid": 1, "name": "init", "cpu_percent": 0.0},
                {"pid": 2, "name": "kthreadd", "cpu_percent": 0.1}
            ]
        }
        
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.get_process_list = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_guest_client
            
            response = client.get("/api/v1/vms/test-vm/guest/processes")
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert len(response_data["processes"]) == 2
    
    def test_health_check_success(self, client, mock_vm_info):
        """Test successful health check."""
        mock_response = {
            "success": True,
            "health": {
                "agent_status": "healthy",
                "uptime": 3600.0,
                "memory_usage": 45.2
            }
        }
        
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.health_check = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_guest_client
            
            response = client.get("/api/v1/vms/test-vm/guest/health")
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["health"]["agent_status"] == "healthy"
    
    def test_shutdown_guest_success(self, client, mock_vm_info):
        """Test successful guest shutdown."""
        mock_response = {
            "success": True,
            "message": "Shutdown initiated"
        }
        
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.shutdown = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_guest_client
            
            request_data = {
                "force": False,
                "delay": 60
            }
            
            response = client.post("/api/v1/vms/test-vm/guest/shutdown", json=request_data)
            
            assert response.status_code == 200
            assert response.json() == mock_response
    
    def test_get_services_windows_only(self, client, mock_vm_info):
        """Test get services for Windows VM."""
        mock_vm_info.os_type = OSType.WINDOWS
        mock_response = {
            "success": True,
            "services": [
                {"name": "Spooler", "state": "Running"},
                {"name": "DHCP", "state": "Stopped"}
            ]
        }
        
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.get_services = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_guest_client
            
            response = client.get("/api/v1/vms/test-vm/guest/services")
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert len(response_data["services"]) == 2
    
    def test_get_services_linux_not_allowed(self, client, mock_vm_info):
        """Test get services fails for Linux VM."""
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm:
            mock_get_vm.return_value = mock_vm_info
            
            response = client.get("/api/v1/vms/test-vm/guest/services")
            
            assert response.status_code == 400
            assert "only available for Windows" in response.json()["detail"]
    
    def test_get_event_logs_windows_only(self, client, mock_vm_info):
        """Test get event logs for Windows VM."""
        mock_vm_info.os_type = OSType.WINDOWS
        mock_response = {
            "success": True,
            "events": [
                {"event_id": 1001, "source": "System", "message": "Test event"}
            ]
        }
        
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.get_event_logs = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_guest_client
            
            request_data = {
                "log_name": "Application",
                "max_events": 50
            }
            
            response = client.post("/api/v1/vms/test-vm/guest/event-logs", json=request_data)
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert len(response_data["events"]) == 1
    
    def test_get_event_logs_linux_not_allowed(self, client, mock_vm_info):
        """Test get event logs fails for Linux VM."""
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm:
            mock_get_vm.return_value = mock_vm_info
            
            request_data = {
                "log_name": "System",
                "max_events": 100
            }
            
            response = client.post("/api/v1/vms/test-vm/guest/event-logs", json=request_data)
            
            assert response.status_code == 400
            assert "only available for Windows" in response.json()["detail"]
    
    def test_guest_client_error_handling(self, client, mock_vm_info):
        """Test guest client error handling."""
        with patch('src.core.vm_manager.VMManager.get_vm', new_callable=AsyncMock) as mock_get_vm, \
             patch('src.core.guest_client.guest_manager.get_client') as mock_get_client:
            
            mock_get_vm.return_value = mock_vm_info
            mock_guest_client = Mock()
            mock_guest_client.execute_command = AsyncMock(side_effect=GuestClientError("Command failed"))
            mock_get_client.return_value = mock_guest_client
            
            request_data = {
                "command": "failing-command"
            }
            
            response = client.post("/api/v1/vms/test-vm/guest/execute", json=request_data)
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is False
            assert "Command failed" in response_data["error"]