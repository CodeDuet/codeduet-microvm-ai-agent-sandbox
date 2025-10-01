import pytest
import asyncio
import httpx
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from src.core.ch_client import CloudHypervisorClient


@pytest.fixture
def ch_client():
    with patch("src.core.ch_client.get_settings") as mock_settings:
        mock_settings.return_value.cloud_hypervisor.api_socket_dir = "/tmp/test-sockets"
        mock_settings.return_value.cloud_hypervisor.binary_path = "/usr/local/bin/cloud-hypervisor"
        return CloudHypervisorClient("test-vm")


@pytest.fixture
def vm_config():
    return {
        "vcpus": 2,
        "memory_mb": 512,
        "kernel": "test-kernel",
        "rootfs": "test-rootfs",
        "boot_args": "console=ttyS0",
        "network": {"enabled": True}
    }


@pytest.mark.asyncio
async def test_start_hypervisor_success(ch_client, vm_config):
    with patch("asyncio.create_subprocess_exec") as mock_subprocess, \
         patch.object(ch_client, "_wait_for_api_socket", new_callable=AsyncMock), \
         patch("httpx.AsyncClient") as mock_client:
        
        mock_process = AsyncMock()
        mock_process.poll.return_value = None
        mock_subprocess.return_value = mock_process
        ch_client.process = mock_process
        
        await ch_client.start_hypervisor(vm_config)
        
        mock_subprocess.assert_called_once()
        assert ch_client.http_client is not None


@pytest.mark.asyncio
async def test_start_hypervisor_already_running(ch_client, vm_config):
    mock_process = Mock()
    mock_process.poll.return_value = None
    ch_client.process = mock_process
    
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        await ch_client.start_hypervisor(vm_config)
        
        # Should not create new process if already running
        mock_subprocess.assert_not_called()
        assert ch_client.process == mock_process


@pytest.mark.asyncio
async def test_create_vm_success(ch_client, vm_config):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"status": "created"}
    
    mock_http_client = AsyncMock()
    mock_http_client.put.return_value = mock_response
    ch_client.http_client = mock_http_client
    
    result = await ch_client.create_vm(vm_config)
    
    assert result == {"status": "created"}
    mock_http_client.put.assert_called_once_with("/api/v1/vm.create", json=ch_client._build_vm_config(vm_config))


@pytest.mark.asyncio
async def test_create_vm_no_http_client(ch_client, vm_config):
    with patch.object(ch_client, "start_hypervisor", new_callable=AsyncMock) as mock_start:
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"status": "created"}
        
        mock_http_client = AsyncMock()
        mock_http_client.put.return_value = mock_response
        
        # Simulate start_hypervisor setting up http_client
        async def setup_client(*args):
            ch_client.http_client = mock_http_client
        
        mock_start.side_effect = setup_client
        
        result = await ch_client.create_vm(vm_config)
        
        mock_start.assert_called_once_with(vm_config)
        assert result == {"status": "created"}


@pytest.mark.asyncio
async def test_boot_vm_success(ch_client):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"status": "booted"}
    
    mock_http_client = AsyncMock()
    mock_http_client.put.return_value = mock_response
    ch_client.http_client = mock_http_client
    
    result = await ch_client.boot_vm()
    
    assert result == {"status": "booted"}
    mock_http_client.put.assert_called_once_with("/api/v1/vm.boot")


@pytest.mark.asyncio
async def test_boot_vm_no_http_client(ch_client):
    with pytest.raises(RuntimeError, match="Cloud Hypervisor not started"):
        await ch_client.boot_vm()


@pytest.mark.asyncio
async def test_shutdown_vm_success(ch_client):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"status": "shutdown"}
    
    mock_http_client = AsyncMock()
    mock_http_client.put.return_value = mock_response
    ch_client.http_client = mock_http_client
    
    result = await ch_client.shutdown_vm()
    
    assert result == {"status": "shutdown"}
    mock_http_client.put.assert_called_once_with("/api/v1/vm.shutdown")


@pytest.mark.asyncio
async def test_pause_vm_success(ch_client):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"status": "paused"}
    
    mock_http_client = AsyncMock()
    mock_http_client.put.return_value = mock_response
    ch_client.http_client = mock_http_client
    
    result = await ch_client.pause_vm()
    
    assert result == {"status": "paused"}
    mock_http_client.put.assert_called_once_with("/api/v1/vm.pause")


@pytest.mark.asyncio
async def test_resume_vm_success(ch_client):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"status": "resumed"}
    
    mock_http_client = AsyncMock()
    mock_http_client.put.return_value = mock_response
    ch_client.http_client = mock_http_client
    
    result = await ch_client.resume_vm()
    
    assert result == {"status": "resumed"}
    mock_http_client.put.assert_called_once_with("/api/v1/vm.resume")


@pytest.mark.asyncio
async def test_resize_vm_success(ch_client):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"status": "resized"}
    
    mock_http_client = AsyncMock()
    mock_http_client.put.return_value = mock_response
    ch_client.http_client = mock_http_client
    
    result = await ch_client.resize_vm(new_vcpus=4, new_memory_mb=1024)
    
    assert result == {"status": "resized"}
    expected_config = {
        "desired_vcpus": 4,
        "desired_ram": 1024 * 1024 * 1024
    }
    mock_http_client.put.assert_called_once_with("/api/v1/vm.resize", json=expected_config)


@pytest.mark.asyncio
async def test_resize_vm_no_parameters(ch_client):
    mock_http_client = AsyncMock()
    ch_client.http_client = mock_http_client
    
    with pytest.raises(ValueError, match="Must specify either new_vcpus or new_memory_mb"):
        await ch_client.resize_vm()


@pytest.mark.asyncio
async def test_snapshot_vm_success(ch_client):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"status": "snapshot_created"}
    
    mock_http_client = AsyncMock()
    mock_http_client.put.return_value = mock_response
    ch_client.http_client = mock_http_client
    
    result = await ch_client.snapshot_vm("/tmp/snapshot.bin")
    
    assert result == {"status": "snapshot_created"}
    expected_config = {"destination_url": "file:///tmp/snapshot.bin"}
    mock_http_client.put.assert_called_once_with("/api/v1/vm.snapshot", json=expected_config)


@pytest.mark.asyncio
async def test_restore_vm_success(ch_client):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"status": "restored"}
    
    mock_http_client = AsyncMock()
    mock_http_client.put.return_value = mock_response
    ch_client.http_client = mock_http_client
    
    result = await ch_client.restore_vm("/tmp/snapshot.bin")
    
    assert result == {"status": "restored"}
    expected_config = {"source_url": "file:///tmp/snapshot.bin"}
    mock_http_client.put.assert_called_once_with("/api/v1/vm.restore", json=expected_config)


@pytest.mark.asyncio
async def test_get_vm_info_success(ch_client):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"cpu_usage": 50, "memory_usage": 256}
    
    mock_http_client = AsyncMock()
    mock_http_client.get.return_value = mock_response
    ch_client.http_client = mock_http_client
    
    result = await ch_client.get_vm_info()
    
    assert result == {"cpu_usage": 50, "memory_usage": 256}
    mock_http_client.get.assert_called_once_with("/api/v1/vm.info")


@pytest.mark.asyncio
async def test_get_vm_counters_success(ch_client):
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"rx_bytes": 1024, "tx_bytes": 2048}
    
    mock_http_client = AsyncMock()
    mock_http_client.get.return_value = mock_response
    ch_client.http_client = mock_http_client
    
    result = await ch_client.get_vm_counters()
    
    assert result == {"rx_bytes": 1024, "tx_bytes": 2048}
    mock_http_client.get.assert_called_once_with("/api/v1/vm.counters")


@pytest.mark.asyncio
async def test_stop_hypervisor_success(ch_client):
    mock_process = Mock()
    mock_process.poll.return_value = None
    mock_process.wait = AsyncMock(return_value=None)
    mock_process.terminate = Mock()
    ch_client.process = mock_process
    
    mock_http_client = AsyncMock()
    ch_client.http_client = mock_http_client
    
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.unlink") as mock_unlink:
        
        await ch_client.stop_hypervisor()
        
        mock_http_client.aclose.assert_called_once()
        mock_process.terminate.assert_called_once()
        mock_unlink.assert_called_once()
        assert ch_client.http_client is None


@pytest.mark.asyncio
async def test_stop_hypervisor_force_kill(ch_client):
    mock_process = Mock()
    mock_process.poll.return_value = None
    mock_process.wait = AsyncMock()
    mock_process.terminate = Mock()
    mock_process.kill = Mock()
    ch_client.process = mock_process
    
    with patch("pathlib.Path.exists", return_value=False), \
         patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
        
        await ch_client.stop_hypervisor()
        
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()


def test_build_vm_config_basic(ch_client):
    vm_config = {
        "vcpus": 2,
        "memory_mb": 512,
        "rootfs": "/path/to/rootfs.ext4"
    }
    
    result = ch_client._build_vm_config(vm_config)
    
    expected = {
        "cpus": {"boot_vcpus": 2, "max_vcpus": 2},
        "memory": {"size": 512 * 1024 * 1024, "mergeable": False, "hotplug_method": "virtio-mem"},
        "disks": [{"path": "/path/to/rootfs.ext4"}]
    }
    
    assert result == expected


def test_build_vm_config_with_network(ch_client):
    vm_config = {
        "vcpus": 2,
        "memory_mb": 512,
        "rootfs": "/path/to/rootfs.ext4",
        "network": {"enabled": True, "mac": "02:fc:00:00:00:01"}
    }
    
    result = ch_client._build_vm_config(vm_config)
    
    assert "net" in result
    assert result["net"][0]["tap"] == "tap-test-vm"
    assert result["net"][0]["mac"] == "02:fc:00:00:00:01"


def test_build_vm_config_with_devices(ch_client):
    vm_config = {
        "vcpus": 2,
        "memory_mb": 512,
        "devices": {
            "block": [
                {"path": "/rootfs.ext4", "read_only": False, "direct": True},
                {"path": "/data.ext4", "read_only": True}
            ],
            "serial": {"enabled": True, "file": "/tmp/serial.log"}
        },
        "guest_agent": {"enabled": True}
    }
    
    result = ch_client._build_vm_config(vm_config)
    
    assert len(result["disks"]) == 2
    assert result["disks"][0]["path"] == "/rootfs.ext4"
    assert result["disks"][0]["direct"] is True
    assert result["disks"][1]["readonly"] is True
    assert result["serial"]["mode"] == "File"
    assert result["serial"]["file"] == "/tmp/serial.log"
    assert result["vsock"]["cid"] == 3


@pytest.mark.asyncio
async def test_wait_for_api_socket_success(ch_client):
    with patch("pathlib.Path.exists", return_value=True), \
         patch("httpx.AsyncClient") as mock_client_class:
        
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        await ch_client._wait_for_api_socket(timeout=1)
        
        mock_client.get.assert_called_once_with("/api/v1/vm.ping")
        mock_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_wait_for_api_socket_timeout(ch_client):
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(TimeoutError, match="API socket not available after 1 seconds"):
            await ch_client._wait_for_api_socket(timeout=1)