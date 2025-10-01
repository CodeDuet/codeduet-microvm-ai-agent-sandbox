import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
from datetime import datetime

from src.core.vm_manager import VMManager
from src.api.models.vm import VMCreateRequest, VMState, OSType


@pytest.fixture
def vm_manager():
    with patch("src.core.vm_manager.get_settings") as mock_settings:
        mock_settings.return_value.cloud_hypervisor.api_socket_dir = "/tmp/test-sockets"
        return VMManager()


@pytest.fixture
def vm_create_request():
    return VMCreateRequest(
        name="test-vm",
        template="linux_default",
        vcpus=2,
        memory_mb=512,
        os_type=OSType.LINUX,
        guest_agent=True,
        metadata={"environment": "test"}
    )


@pytest.mark.asyncio
async def test_create_vm_success(vm_manager, vm_create_request):
    with patch("src.core.vm_manager.load_vm_template") as mock_load_template, \
         patch("src.core.vm_manager.CloudHypervisorClient") as mock_ch_client, \
         patch.object(vm_manager, "_save_vm_data", new_callable=AsyncMock) as mock_save:
        
        mock_load_template.return_value = {
            "vcpus": 2,
            "memory_mb": 512,
            "kernel": "test-kernel",
            "rootfs": "test-rootfs"
        }
        
        mock_client_instance = AsyncMock()
        mock_ch_client.return_value = mock_client_instance
        
        vm_info = await vm_manager.create_vm(vm_create_request)
        
        assert vm_info.name == "test-vm"
        assert vm_info.state == VMState.STOPPED
        assert vm_info.vcpus == 2
        assert vm_info.memory_mb == 512
        assert vm_info.os_type == OSType.LINUX
        assert vm_info.template == "linux_default"
        assert vm_info.guest_agent is True
        assert vm_info.metadata == {"environment": "test"}
        
        mock_client_instance.create_vm.assert_called_once()
        mock_save.assert_called()


@pytest.mark.asyncio
async def test_create_vm_duplicate_name(vm_manager, vm_create_request):
    vm_manager.vms["test-vm"] = Mock()
    
    with pytest.raises(ValueError, match="VM 'test-vm' already exists"):
        await vm_manager.create_vm(vm_create_request)


@pytest.mark.asyncio
async def test_create_vm_invalid_template(vm_manager, vm_create_request):
    with patch("src.core.vm_manager.load_vm_template", side_effect=FileNotFoundError):
        with pytest.raises(ValueError, match="Template 'linux_default' not found"):
            await vm_manager.create_vm(vm_create_request)


@pytest.mark.asyncio
async def test_start_vm_success(vm_manager):
    vm_info = Mock()
    vm_info.state = VMState.STOPPED
    vm_info.template = "linux_default"
    vm_info.vcpus = 2
    vm_info.memory_mb = 512
    
    with patch.object(vm_manager, "get_vm", return_value=vm_info), \
         patch("src.core.vm_manager.load_vm_template") as mock_load_template, \
         patch("src.core.vm_manager.CloudHypervisorClient") as mock_ch_client, \
         patch.object(vm_manager, "_save_vm_data", new_callable=AsyncMock):
        
        mock_load_template.return_value = {"vcpus": 2, "memory_mb": 512}
        mock_client_instance = AsyncMock()
        mock_ch_client.return_value = mock_client_instance
        
        await vm_manager.start_vm("test-vm")
        
        assert vm_info.state == VMState.RUNNING
        mock_client_instance.start_hypervisor.assert_called_once()
        mock_client_instance.boot_vm.assert_called_once()


@pytest.mark.asyncio
async def test_start_vm_not_found(vm_manager):
    with patch.object(vm_manager, "get_vm", return_value=None):
        with pytest.raises(ValueError, match="VM 'test-vm' not found"):
            await vm_manager.start_vm("test-vm")


@pytest.mark.asyncio
async def test_start_vm_already_running(vm_manager):
    vm_info = Mock()
    vm_info.state = VMState.RUNNING
    
    with patch.object(vm_manager, "get_vm", return_value=vm_info):
        with pytest.raises(ValueError, match="VM 'test-vm' is already running"):
            await vm_manager.start_vm("test-vm")


@pytest.mark.asyncio
async def test_stop_vm_success(vm_manager):
    vm_info = Mock()
    vm_info.state = VMState.RUNNING
    
    with patch.object(vm_manager, "get_vm", return_value=vm_info), \
         patch("src.core.vm_manager.CloudHypervisorClient") as mock_ch_client, \
         patch.object(vm_manager, "_save_vm_data", new_callable=AsyncMock):
        
        mock_client_instance = AsyncMock()
        mock_ch_client.return_value = mock_client_instance
        
        await vm_manager.stop_vm("test-vm")
        
        assert vm_info.state == VMState.STOPPED
        mock_client_instance.shutdown_vm.assert_called_once()
        mock_client_instance.stop_hypervisor.assert_called_once()


@pytest.mark.asyncio
async def test_pause_vm_success(vm_manager):
    vm_info = Mock()
    vm_info.state = VMState.RUNNING
    
    with patch.object(vm_manager, "get_vm", return_value=vm_info), \
         patch("src.core.vm_manager.CloudHypervisorClient") as mock_ch_client, \
         patch.object(vm_manager, "_save_vm_data", new_callable=AsyncMock):
        
        mock_client_instance = AsyncMock()
        mock_ch_client.return_value = mock_client_instance
        
        await vm_manager.pause_vm("test-vm")
        
        assert vm_info.state == VMState.PAUSED
        mock_client_instance.pause_vm.assert_called_once()


@pytest.mark.asyncio
async def test_resume_vm_success(vm_manager):
    vm_info = Mock()
    vm_info.state = VMState.PAUSED
    
    with patch.object(vm_manager, "get_vm", return_value=vm_info), \
         patch("src.core.vm_manager.CloudHypervisorClient") as mock_ch_client, \
         patch.object(vm_manager, "_save_vm_data", new_callable=AsyncMock):
        
        mock_client_instance = AsyncMock()
        mock_ch_client.return_value = mock_client_instance
        
        await vm_manager.resume_vm("test-vm")
        
        assert vm_info.state == VMState.RUNNING
        mock_client_instance.resume_vm.assert_called_once()


@pytest.mark.asyncio
async def test_delete_vm_success(vm_manager):
    vm_info = Mock()
    vm_info.state = VMState.STOPPED
    vm_manager.vms["test-vm"] = vm_info
    
    with patch.object(vm_manager, "get_vm", return_value=vm_info), \
         patch("src.core.vm_manager.CloudHypervisorClient") as mock_ch_client, \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.unlink") as mock_unlink:
        
        mock_client_instance = AsyncMock()
        mock_ch_client.return_value = mock_client_instance
        
        await vm_manager.delete_vm("test-vm")
        
        assert "test-vm" not in vm_manager.vms
        mock_client_instance.stop_hypervisor.assert_called_once()
        mock_unlink.assert_called_once()


@pytest.mark.asyncio
async def test_delete_running_vm(vm_manager):
    vm_info = Mock()
    vm_info.state = VMState.RUNNING
    vm_manager.vms["test-vm"] = vm_info
    
    with patch.object(vm_manager, "get_vm", return_value=vm_info), \
         patch.object(vm_manager, "stop_vm", new_callable=AsyncMock) as mock_stop, \
         patch("src.core.vm_manager.CloudHypervisorClient") as mock_ch_client, \
         patch("pathlib.Path.exists", return_value=False):
        
        mock_client_instance = AsyncMock()
        mock_ch_client.return_value = mock_client_instance
        
        await vm_manager.delete_vm("test-vm")
        
        mock_stop.assert_called_once_with("test-vm")
        assert "test-vm" not in vm_manager.vms


@pytest.mark.asyncio
async def test_get_vm_status_running(vm_manager):
    vm_info = Mock()
    vm_info.state = VMState.RUNNING
    vm_info.model_dump.return_value = {"name": "test-vm", "state": "running"}
    
    with patch.object(vm_manager, "get_vm", return_value=vm_info), \
         patch("src.core.vm_manager.CloudHypervisorClient") as mock_ch_client:
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get_vm_info.return_value = {"cpu_usage": 50}
        mock_client_instance.get_vm_counters.return_value = {"rx_bytes": 1024}
        mock_ch_client.return_value = mock_client_instance
        
        status = await vm_manager.get_vm_status("test-vm")
        
        assert "vm_info" in status
        assert "hypervisor_info" in status
        assert "counters" in status
        assert status["hypervisor_info"]["cpu_usage"] == 50
        assert status["counters"]["rx_bytes"] == 1024


@pytest.mark.asyncio
async def test_list_vms(vm_manager):
    mock_vm1 = Mock()
    mock_vm2 = Mock()
    vm_manager.vms = {"vm1": mock_vm1, "vm2": mock_vm2}
    
    with patch.object(vm_manager, "_load_all_vm_data", new_callable=AsyncMock):
        vms = await vm_manager.list_vms()
        
        assert len(vms) == 2
        assert mock_vm1 in vms
        assert mock_vm2 in vms