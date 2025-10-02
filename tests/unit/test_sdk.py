"""
Unit tests for py-microvm SDK.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from src.sdk import MicroVMManager, Sandbox
from src.sdk.models import (
    SandboxConfig, SandboxInfo, SandboxState, CommandResult, 
    FileTransferResult, SnapshotInfo, VNCInfo, SecurityContext, OSType
)
from src.sdk.exceptions import (
    MicroVMSDKError, SandboxNotFoundError, SandboxStateError,
    CommandExecutionError, FileTransferError, AuthenticationError, NetworkError
)


@pytest.fixture
def security_context():
    """Create test security context."""
    return SecurityContext(
        api_token="test-token",
        user_id="test-user",
        role="developer",
        permissions=["vm:create", "vm:start", "vm:stop"],
        audit_enabled=True
    )


@pytest.fixture
def sandbox_info():
    """Create test sandbox info."""
    return SandboxInfo(
        name="test-sandbox",
        state=SandboxState.RUNNING,
        vcpus=2,
        memory_mb=2048,
        os_type=OSType.LINUX,
        template="ai-agent",
        guest_agent=True,
        vnc_enabled=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata={"test": "value"},
        ip_address="192.168.1.100",
        vnc_port=5901,
        guest_agent_port=8080
    )


@pytest.fixture
def mock_http_client():
    """Create mock HTTP client."""
    client = AsyncMock()
    
    # Mock successful responses
    client.get.return_value.status_code = 200
    client.get.return_value.json.return_value = {"status": "ok"}
    client.post.return_value.status_code = 201
    client.post.return_value.json.return_value = {"id": "test-id"}
    client.delete.return_value.status_code = 204
    
    return client


class TestMicroVMManager:
    """Test MicroVMManager class."""
    
    @pytest.mark.asyncio
    async def test_manager_init(self, security_context):
        """Test manager initialization."""
        manager = MicroVMManager(
            api_url="http://test.local",
            security_context=security_context,
            timeout=60,
            max_retries=5
        )
        
        assert manager.api_url == "http://test.local"
        assert manager.security_context == security_context
        assert manager.timeout == 60
        assert manager.max_retries == 5
        assert manager._client is None
        assert manager._sandboxes == {}
    
    @pytest.mark.asyncio
    async def test_context_manager(self, security_context, mock_http_client):
        """Test async context manager."""
        manager = MicroVMManager(security_context=security_context)
        
        with patch('httpx.AsyncClient', return_value=mock_http_client):
            async with manager as mgr:
                assert mgr._client is not None
                assert mgr == manager
            
            # Should be cleaned up
            mock_http_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_init_client_success(self, security_context, mock_http_client):
        """Test successful client initialization."""
        manager = MicroVMManager(security_context=security_context)
        
        with patch('httpx.AsyncClient', return_value=mock_http_client):
            await manager._init_client()
            
            assert manager._client == mock_http_client
            mock_http_client.get.assert_called_once_with("/health")
    
    @pytest.mark.asyncio
    async def test_init_client_auth_failure(self, security_context, mock_http_client):
        """Test client initialization with auth failure."""
        manager = MicroVMManager(security_context=security_context)
        mock_http_client.get.return_value.status_code = 401
        
        with patch('httpx.AsyncClient', return_value=mock_http_client):
            with pytest.raises(AuthenticationError):
                await manager._init_client()
    
    @pytest.mark.asyncio
    async def test_start_sandbox_success(self, security_context, mock_http_client, sandbox_info):
        """Test successful sandbox creation."""
        manager = MicroVMManager(security_context=security_context)
        manager._client = mock_http_client
        
        # Mock API response
        mock_http_client.post.return_value.json.return_value = sandbox_info.model_dump()
        
        sandbox = await manager.start_sandbox("ai-agent", "test-sandbox")
        
        assert isinstance(sandbox, Sandbox)
        assert sandbox.name == "test-sandbox"
        assert sandbox.state == SandboxState.RUNNING
        assert "test-sandbox" in manager._sandboxes
    
    @pytest.mark.asyncio
    async def test_start_sandbox_with_config(self, security_context, mock_http_client, sandbox_info):
        """Test sandbox creation with custom config."""
        manager = MicroVMManager(security_context=security_context)
        manager._client = mock_http_client
        
        config = SandboxConfig(
            name="custom-sandbox",
            template="code-interpreter",
            vcpus=4,
            memory_mb=4096,
            vnc_enabled=True
        )
        
        mock_http_client.post.return_value.json.return_value = sandbox_info.model_dump()
        
        sandbox = await manager.start_sandbox(config=config)
        
        assert sandbox.info.template == "code-interpreter"
        mock_http_client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_sandboxes(self, security_context, mock_http_client, sandbox_info):
        """Test listing sandboxes."""
        manager = MicroVMManager(security_context=security_context)
        manager._client = mock_http_client
        
        mock_http_client.get.return_value.json.return_value = {
            "vms": [sandbox_info.model_dump()]
        }
        
        sandboxes = await manager.list_sandboxes()
        
        assert len(sandboxes) == 1
        assert sandboxes[0].name == "test-sandbox"
        mock_http_client.get.assert_called_once_with("/api/v1/vms")
    
    @pytest.mark.asyncio
    async def test_get_sandbox_existing(self, security_context, sandbox_info):
        """Test getting existing sandbox."""
        manager = MicroVMManager(security_context=security_context)
        sandbox = Sandbox(manager, sandbox_info)
        manager._sandboxes["test-sandbox"] = sandbox
        
        result = await manager.get_sandbox("test-sandbox")
        
        assert result == sandbox
    
    @pytest.mark.asyncio
    async def test_get_sandbox_not_found(self, security_context, mock_http_client):
        """Test getting non-existent sandbox."""
        manager = MicroVMManager(security_context=security_context)
        manager._client = mock_http_client
        mock_http_client.get.return_value.status_code = 404
        
        with pytest.raises(SandboxNotFoundError):
            await manager.get_sandbox("nonexistent")
    
    @pytest.mark.asyncio
    async def test_delete_sandbox(self, security_context, mock_http_client):
        """Test sandbox deletion."""
        manager = MicroVMManager(security_context=security_context)
        manager._client = mock_http_client
        manager._sandboxes["test-sandbox"] = Mock()
        
        await manager.delete_sandbox("test-sandbox")
        
        mock_http_client.delete.assert_called_once_with("/api/v1/vms/test-sandbox")
        assert "test-sandbox" not in manager._sandboxes


class TestSandbox:
    """Test Sandbox class."""
    
    @pytest.fixture
    def sandbox(self, security_context, sandbox_info):
        """Create test sandbox."""
        manager = MicroVMManager(security_context=security_context)
        manager._client = AsyncMock()
        return Sandbox(manager, sandbox_info)
    
    @pytest.mark.asyncio
    async def test_sandbox_context_manager(self, sandbox):
        """Test sandbox async context manager."""
        sandbox.start = AsyncMock()
        sandbox.destroy = AsyncMock()
        
        async with sandbox as sb:
            assert sb == sandbox
            sandbox.start.assert_called_once()
        
        sandbox.destroy.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_sandbox(self, sandbox):
        """Test starting sandbox."""
        sandbox.manager._client.post.return_value.status_code = 200
        sandbox.state = SandboxState.STOPPED
        
        await sandbox.start()
        
        assert sandbox.state == SandboxState.RUNNING
        sandbox.manager._client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_sandbox(self, sandbox):
        """Test stopping sandbox."""
        sandbox.manager._client.post.return_value.status_code = 200
        
        await sandbox.stop()
        
        assert sandbox.state == SandboxState.STOPPED
        sandbox.manager._client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_command_success(self, sandbox):
        """Test successful command execution."""
        response_data = {
            "success": True,
            "exit_code": 0,
            "stdout": "Hello World",
            "stderr": "",
            "error": None
        }
        sandbox.manager._client.post.return_value.status_code = 200
        sandbox.manager._client.post.return_value.json.return_value = response_data
        
        result = await sandbox.run_command("echo 'Hello World'")
        
        assert isinstance(result, CommandResult)
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "Hello World"
        assert result.output == "Hello World"
    
    @pytest.mark.asyncio
    async def test_run_command_failure(self, sandbox):
        """Test failed command execution."""
        response_data = {
            "success": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": "Command failed",
            "error": "Command failed"
        }
        sandbox.manager._client.post.return_value.status_code = 200
        sandbox.manager._client.post.return_value.json.return_value = response_data
        
        with pytest.raises(CommandExecutionError):
            await sandbox.run_command("false")
    
    @pytest.mark.asyncio
    async def test_run_command_wrong_state(self, sandbox):
        """Test command execution in wrong state."""
        sandbox.state = SandboxState.STOPPED
        
        with pytest.raises(SandboxStateError):
            await sandbox.run_command("echo 'test'")
    
    @pytest.mark.asyncio
    async def test_upload_file_success(self, sandbox, tmp_path):
        """Test successful file upload."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        response_data = {
            "success": True,
            "size": 12,
            "checksum": "abc123",
            "error": None
        }
        sandbox.manager._client.post.return_value.status_code = 200
        sandbox.manager._client.post.return_value.json.return_value = response_data
        
        result = await sandbox.upload_file(test_file, "/tmp/test.txt")
        
        assert isinstance(result, FileTransferResult)
        assert result.success is True
        assert result.size_bytes == 12
        assert result.checksum == "abc123"
    
    @pytest.mark.asyncio
    async def test_upload_file_not_found(self, sandbox):
        """Test upload of non-existent file."""
        with pytest.raises(FileTransferError):
            await sandbox.upload_file("/nonexistent/file.txt", "/tmp/test.txt")
    
    @pytest.mark.asyncio
    async def test_download_file_success(self, sandbox, tmp_path):
        """Test successful file download."""
        download_path = tmp_path / "downloaded.txt"
        sandbox.manager._client.post.return_value.status_code = 200
        sandbox.manager._client.post.return_value.content = b"downloaded content"
        
        result = await sandbox.download_file("/tmp/remote.txt", download_path)
        
        assert isinstance(result, FileTransferResult)
        assert result.success is True
        assert download_path.read_text() == "downloaded content"
    
    @pytest.mark.asyncio
    async def test_snapshot_success(self, sandbox):
        """Test successful snapshot creation."""
        snapshot_data = {
            "id": "snapshot-123",
            "name": "test-snapshot",
            "sandbox_name": "test-sandbox",
            "description": "Test snapshot",
            "size_bytes": 1024,
            "created_at": datetime.now().isoformat(),
            "metadata": {}
        }
        sandbox.manager._client.post.return_value.status_code = 201
        sandbox.manager._client.post.return_value.json.return_value = snapshot_data
        
        result = await sandbox.snapshot("test-snapshot", "Test snapshot")
        
        assert isinstance(result, SnapshotInfo)
        assert result.id == "snapshot-123"
        assert result.name == "test-snapshot"
    
    @pytest.mark.asyncio
    async def test_restore_success(self, sandbox):
        """Test successful snapshot restoration."""
        sandbox.manager._client.post.return_value.status_code = 200
        sandbox._update_info = AsyncMock()
        
        await sandbox.restore("snapshot-123")
        
        sandbox.manager._client.post.assert_called_once()
        sandbox._update_info.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_vnc_info(self, sandbox):
        """Test getting VNC information."""
        vnc_data = {
            "enabled": True,
            "host": "localhost",
            "port": 5901,
            "password": "secret",
            "web_url": "http://localhost:6080",
            "resolution": "1920x1080",
            "color_depth": 24
        }
        sandbox.manager._client.get.return_value.status_code = 200
        sandbox.manager._client.get.return_value.json.return_value = vnc_data
        
        result = await sandbox.get_vnc_info()
        
        assert isinstance(result, VNCInfo)
        assert result.enabled is True
        assert result.port == 5901
    
    @pytest.mark.asyncio
    async def test_take_screenshot_success(self, sandbox):
        """Test successful screenshot capture."""
        image_data = b"fake-png-data"
        sandbox.manager._client.get.return_value.status_code = 200
        sandbox.manager._client.get.return_value.content = image_data
        
        result = await sandbox.take_screenshot()
        
        assert result.success is True
        assert result.image_data == image_data
        assert result.image_format == "png"
    
    @pytest.mark.asyncio
    async def test_click_action(self, sandbox):
        """Test mouse click action."""
        sandbox.manager._client.post.return_value.status_code = 200
        
        result = await sandbox.click(100, 200, "left", False)
        
        assert result.success is True
        assert result.action_type == "click"
    
    @pytest.mark.asyncio
    async def test_type_text_action(self, sandbox):
        """Test keyboard typing action."""
        sandbox.manager._client.post.return_value.status_code = 200
        
        result = await sandbox.type_text("Hello World")
        
        assert result.success is True
        assert result.action_type == "type"
    
    @pytest.mark.asyncio
    async def test_scroll_action(self, sandbox):
        """Test scroll action."""
        sandbox.manager._client.post.return_value.status_code = 200
        
        result = await sandbox.scroll(100, 200, "down", 3)
        
        assert result.success is True
        assert result.action_type == "scroll"


class TestModels:
    """Test SDK data models."""
    
    def test_sandbox_config_defaults(self):
        """Test SandboxConfig default values."""
        config = SandboxConfig(name="test", template="ai-agent")
        
        assert config.vcpus == 4
        assert config.memory_mb == 4096
        assert config.os_type == OSType.LINUX
        assert config.guest_agent is True
        assert config.vnc_enabled is False
        assert config.auto_start is True
        assert config.metadata == {}
    
    def test_command_result_output_property(self):
        """Test CommandResult output property."""
        # Test with stdout
        result1 = CommandResult(
            success=True,
            stdout="output text",
            stderr=None,
            timestamp=datetime.now()
        )
        assert result1.output == "output text"
        
        # Test with stderr when no stdout
        result2 = CommandResult(
            success=False,
            stdout=None,
            stderr="error text",
            timestamp=datetime.now()
        )
        assert result2.output == "error text"
        
        # Test with empty output
        result3 = CommandResult(
            success=True,
            stdout=None,
            stderr=None,
            timestamp=datetime.now()
        )
        assert result3.output == ""
    
    def test_security_context_validation(self):
        """Test SecurityContext validation."""
        context = SecurityContext(
            api_token="token123",
            user_id="user123",
            role="admin",
            permissions=["vm:create", "vm:delete"],
            audit_enabled=True
        )
        
        assert context.api_token == "token123"
        assert context.user_id == "user123"
        assert context.role == "admin"
        assert len(context.permissions) == 2
        assert context.audit_enabled is True


class TestExceptions:
    """Test SDK exceptions."""
    
    def test_microvm_sdk_error_base(self):
        """Test base MicroVMSDKError."""
        error = MicroVMSDKError("Test error", {"code": 123})
        
        assert str(error) == "Test error (details: {'code': 123})"
        assert error.message == "Test error"
        assert error.details == {"code": 123}
    
    def test_sandbox_not_found_error(self):
        """Test SandboxNotFoundError."""
        error = SandboxNotFoundError("test-sandbox")
        
        assert "test-sandbox" in str(error)
        assert error.sandbox_name == "test-sandbox"
    
    def test_sandbox_state_error(self):
        """Test SandboxStateError."""
        error = SandboxStateError("test-sandbox", "stopped", "running")
        
        assert "test-sandbox" in str(error)
        assert "stopped" in str(error)
        assert "running" in str(error)
        assert error.current_state == "stopped"
        assert error.required_state == "running"
    
    def test_command_execution_error(self):
        """Test CommandExecutionError."""
        error = CommandExecutionError("python script.py", 1, "ImportError")
        
        assert "python script.py" in str(error)
        assert "exit code 1" in str(error)
        assert "ImportError" in str(error)
        assert error.command == "python script.py"
        assert error.exit_code == 1
        assert error.stderr == "ImportError"
    
    def test_file_transfer_error(self):
        """Test FileTransferError."""
        error = FileTransferError("upload", "/local/file.txt", "/remote/file.txt", "Permission denied")
        
        assert "upload" in str(error)
        assert "/local/file.txt" in str(error)
        assert "/remote/file.txt" in str(error)
        assert "Permission denied" in str(error)
        assert error.operation == "upload"