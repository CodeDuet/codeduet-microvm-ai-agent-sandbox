"""Integration tests for VM lifecycle operations."""

import asyncio
import pytest
import httpx
from pathlib import Path
import tempfile
import shutil
import yaml
import time
from typing import Dict, Any

from src.core.vm_manager import VMManager
from src.core.ch_client import CloudHypervisorClient
from src.core.network_manager import NetworkManager
from src.core.snapshot_manager import SnapshotManager
from src.utils.config import get_config
from src.api.models.vm import VMRequest, VMInfo


class TestVMLifecycle:
    """Test complete VM lifecycle operations."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test environment."""
        self.config = get_config()
        self.vm_manager = VMManager(self.config)
        self.network_manager = NetworkManager(self.config)
        self.snapshot_manager = SnapshotManager(self.config)
        
        # Create temporary directory for test artifacts
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_vms = []
        
        yield
        
        # Cleanup
        await self.cleanup_test_vms()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def cleanup_test_vms(self):
        """Cleanup all test VMs."""
        for vm_name in self.test_vms:
            try:
                await self.vm_manager.stop_vm(vm_name)
                await self.vm_manager.delete_vm(vm_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_linux_vm_full_lifecycle(self):
        """Test complete Linux VM lifecycle."""
        vm_name = "test-linux-vm"
        self.test_vms.append(vm_name)
        
        # Create VM
        vm_request = VMRequest(
            name=vm_name,
            os_type="linux",
            vcpus=2,
            memory_mb=512,
            template="linux-default"
        )
        
        vm_info = await self.vm_manager.create_vm(vm_request)
        assert vm_info.name == vm_name
        assert vm_info.status == "created"
        
        # Start VM
        await self.vm_manager.start_vm(vm_name)
        vm_info = await self.vm_manager.get_vm_info(vm_name)
        assert vm_info.status == "running"
        
        # Wait for boot
        await asyncio.sleep(5)
        
        # Test VM is responsive
        assert await self._wait_for_vm_ready(vm_name, timeout=30)
        
        # Stop VM
        await self.vm_manager.stop_vm(vm_name)
        vm_info = await self.vm_manager.get_vm_info(vm_name)
        assert vm_info.status == "stopped"
        
        # Restart VM
        await self.vm_manager.start_vm(vm_name)
        vm_info = await self.vm_manager.get_vm_info(vm_name)
        assert vm_info.status == "running"
        
        # Delete VM
        await self.vm_manager.delete_vm(vm_name)
        
        # Verify VM is gone
        with pytest.raises(Exception):
            await self.vm_manager.get_vm_info(vm_name)

    @pytest.mark.asyncio
    async def test_windows_vm_full_lifecycle(self):
        """Test complete Windows VM lifecycle."""
        vm_name = "test-windows-vm"
        self.test_vms.append(vm_name)
        
        # Create VM
        vm_request = VMRequest(
            name=vm_name,
            os_type="windows",
            vcpus=4,
            memory_mb=2048,
            template="windows-default"
        )
        
        vm_info = await self.vm_manager.create_vm(vm_request)
        assert vm_info.name == vm_name
        assert vm_info.status == "created"
        
        # Start VM
        await self.vm_manager.start_vm(vm_name)
        vm_info = await self.vm_manager.get_vm_info(vm_name)
        assert vm_info.status == "running"
        
        # Test VM is responsive (Windows takes longer to boot)
        assert await self._wait_for_vm_ready(vm_name, timeout=60)
        
        # Stop and delete VM
        await self.vm_manager.stop_vm(vm_name)
        await self.vm_manager.delete_vm(vm_name)

    @pytest.mark.asyncio
    async def test_vm_snapshot_restore_lifecycle(self):
        """Test VM snapshot and restore operations."""
        vm_name = "test-snapshot-vm"
        snapshot_name = "test-snapshot"
        self.test_vms.append(vm_name)
        
        # Create and start VM
        vm_request = VMRequest(
            name=vm_name,
            os_type="linux",
            vcpus=2,
            memory_mb=512
        )
        
        await self.vm_manager.create_vm(vm_request)
        await self.vm_manager.start_vm(vm_name)
        
        # Wait for VM to be ready
        assert await self._wait_for_vm_ready(vm_name, timeout=30)
        
        # Create snapshot
        snapshot_info = await self.snapshot_manager.create_snapshot(vm_name, snapshot_name)
        assert snapshot_info.name == snapshot_name
        assert snapshot_info.vm_name == vm_name
        
        # Verify snapshot exists
        snapshots = await self.snapshot_manager.list_snapshots(vm_name)
        assert len(snapshots) == 1
        assert snapshots[0].name == snapshot_name
        
        # Stop VM
        await self.vm_manager.stop_vm(vm_name)
        
        # Restore from snapshot
        await self.snapshot_manager.restore_snapshot(vm_name, snapshot_name)
        
        # Start restored VM
        await self.vm_manager.start_vm(vm_name)
        assert await self._wait_for_vm_ready(vm_name, timeout=30)
        
        # Delete snapshot
        await self.snapshot_manager.delete_snapshot(vm_name, snapshot_name)
        snapshots = await self.snapshot_manager.list_snapshots(vm_name)
        assert len(snapshots) == 0

    @pytest.mark.asyncio
    async def test_concurrent_vm_operations(self):
        """Test concurrent VM operations."""
        vm_names = [f"test-concurrent-vm-{i}" for i in range(3)]
        self.test_vms.extend(vm_names)
        
        # Create VMs concurrently
        create_tasks = []
        for vm_name in vm_names:
            vm_request = VMRequest(
                name=vm_name,
                os_type="linux",
                vcpus=1,
                memory_mb=256
            )
            create_tasks.append(self.vm_manager.create_vm(vm_request))
        
        vm_infos = await asyncio.gather(*create_tasks)
        assert len(vm_infos) == 3
        
        # Start VMs concurrently
        start_tasks = [self.vm_manager.start_vm(vm_name) for vm_name in vm_names]
        await asyncio.gather(*start_tasks)
        
        # Verify all VMs are running
        for vm_name in vm_names:
            vm_info = await self.vm_manager.get_vm_info(vm_name)
            assert vm_info.status == "running"
        
        # Stop VMs concurrently
        stop_tasks = [self.vm_manager.stop_vm(vm_name) for vm_name in vm_names]
        await asyncio.gather(*stop_tasks)
        
        # Delete VMs concurrently
        delete_tasks = [self.vm_manager.delete_vm(vm_name) for vm_name in vm_names]
        await asyncio.gather(*delete_tasks)

    @pytest.mark.asyncio
    async def test_vm_resource_management(self):
        """Test VM resource allocation and monitoring."""
        vm_name = "test-resource-vm"
        self.test_vms.append(vm_name)
        
        # Create VM with specific resources
        vm_request = VMRequest(
            name=vm_name,
            os_type="linux",
            vcpus=4,
            memory_mb=1024
        )
        
        vm_info = await self.vm_manager.create_vm(vm_request)
        assert vm_info.vcpus == 4
        assert vm_info.memory_mb == 1024
        
        # Start VM and get resource usage
        await self.vm_manager.start_vm(vm_name)
        
        # Wait for VM to stabilize
        await asyncio.sleep(10)
        
        # Get resource metrics
        metrics = await self.vm_manager.get_vm_metrics(vm_name)
        assert metrics.cpu_usage >= 0
        assert metrics.memory_usage > 0
        assert metrics.memory_usage <= vm_info.memory_mb * 1024 * 1024  # Convert MB to bytes

    @pytest.mark.asyncio
    async def test_vm_network_connectivity(self):
        """Test VM network connectivity."""
        vm_name = "test-network-vm"
        self.test_vms.append(vm_name)
        
        # Create VM with networking
        vm_request = VMRequest(
            name=vm_name,
            os_type="linux",
            vcpus=2,
            memory_mb=512,
            network_config={
                "bridge": "chbr0",
                "ip": "192.168.200.100"
            }
        )
        
        vm_info = await self.vm_manager.create_vm(vm_request)
        await self.vm_manager.start_vm(vm_name)
        
        # Wait for VM to be ready
        assert await self._wait_for_vm_ready(vm_name, timeout=30)
        
        # Test network connectivity
        network_info = await self.network_manager.get_vm_network_info(vm_name)
        assert network_info.ip_address == "192.168.200.100"
        assert network_info.bridge_name == "chbr0"
        
        # Test ping connectivity
        ping_result = await self.network_manager.ping_vm(vm_name)
        assert ping_result.success

    async def _wait_for_vm_ready(self, vm_name: str, timeout: int = 30) -> bool:
        """Wait for VM to be ready and responsive."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check if VM is responding
                vm_info = await self.vm_manager.get_vm_info(vm_name)
                if vm_info.status == "running":
                    # Try to ping the VM
                    ping_result = await self.network_manager.ping_vm(vm_name)
                    if ping_result.success:
                        return True
            except Exception:
                pass
            
            await asyncio.sleep(2)
        
        return False


class TestGuestCommunication:
    """Test guest communication operations."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test environment."""
        self.config = get_config()
        self.vm_manager = VMManager(self.config)
        self.test_vms = []
        
        yield
        
        # Cleanup
        for vm_name in self.test_vms:
            try:
                await self.vm_manager.stop_vm(vm_name)
                await self.vm_manager.delete_vm(vm_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_linux_guest_command_execution(self):
        """Test command execution in Linux guest."""
        vm_name = "test-linux-guest"
        self.test_vms.append(vm_name)
        
        # Create and start VM
        vm_request = VMRequest(
            name=vm_name,
            os_type="linux",
            vcpus=2,
            memory_mb=512
        )
        
        await self.vm_manager.create_vm(vm_request)
        await self.vm_manager.start_vm(vm_name)
        
        # Wait for guest agent to be ready
        await asyncio.sleep(15)
        
        # Execute command
        result = await self.vm_manager.execute_command(vm_name, "echo 'Hello from guest'")
        assert result.exit_code == 0
        assert "Hello from guest" in result.stdout

    @pytest.mark.asyncio
    async def test_windows_guest_command_execution(self):
        """Test command execution in Windows guest."""
        vm_name = "test-windows-guest"
        self.test_vms.append(vm_name)
        
        # Create and start VM
        vm_request = VMRequest(
            name=vm_name,
            os_type="windows",
            vcpus=4,
            memory_mb=2048
        )
        
        await self.vm_manager.create_vm(vm_request)
        await self.vm_manager.start_vm(vm_name)
        
        # Wait for guest agent to be ready (Windows takes longer)
        await asyncio.sleep(45)
        
        # Execute PowerShell command
        result = await self.vm_manager.execute_command(vm_name, "Write-Host 'Hello from Windows guest'")
        assert result.exit_code == 0
        assert "Hello from Windows guest" in result.stdout

    @pytest.mark.asyncio
    async def test_file_transfer_operations(self):
        """Test file upload and download operations."""
        vm_name = "test-file-transfer"
        self.test_vms.append(vm_name)
        
        # Create and start VM
        vm_request = VMRequest(
            name=vm_name,
            os_type="linux",
            vcpus=2,
            memory_mb=512
        )
        
        await self.vm_manager.create_vm(vm_request)
        await self.vm_manager.start_vm(vm_name)
        
        # Wait for guest agent
        await asyncio.sleep(15)
        
        # Test file upload
        test_content = "This is a test file content"
        remote_path = "/tmp/test_file.txt"
        
        await self.vm_manager.upload_file(vm_name, test_content.encode(), remote_path)
        
        # Verify file exists
        result = await self.vm_manager.execute_command(vm_name, f"cat {remote_path}")
        assert result.exit_code == 0
        assert test_content in result.stdout
        
        # Test file download
        downloaded_content = await self.vm_manager.download_file(vm_name, remote_path)
        assert downloaded_content.decode() == test_content


class TestAPIIntegration:
    """Test API integration scenarios."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test environment."""
        self.base_url = "http://localhost:8000"
        self.client = httpx.AsyncClient()
        self.test_vms = []
        
        yield
        
        # Cleanup
        for vm_name in self.test_vms:
            try:
                await self.client.delete(f"{self.base_url}/api/v1/vms/{vm_name}")
            except Exception:
                pass
        
        await self.client.aclose()

    @pytest.mark.asyncio
    async def test_api_vm_lifecycle(self):
        """Test VM lifecycle through API."""
        vm_name = "test-api-vm"
        self.test_vms.append(vm_name)
        
        # Create VM via API
        vm_data = {
            "name": vm_name,
            "os_type": "linux",
            "vcpus": 2,
            "memory_mb": 512,
            "template": "linux-default"
        }
        
        response = await self.client.post(f"{self.base_url}/api/v1/vms", json=vm_data)
        assert response.status_code == 201
        vm_info = response.json()
        assert vm_info["name"] == vm_name
        
        # Start VM via API
        response = await self.client.post(f"{self.base_url}/api/v1/vms/{vm_name}/start")
        assert response.status_code == 200
        
        # Get VM status
        response = await self.client.get(f"{self.base_url}/api/v1/vms/{vm_name}")
        assert response.status_code == 200
        vm_info = response.json()
        assert vm_info["status"] == "running"
        
        # Stop VM via API
        response = await self.client.post(f"{self.base_url}/api/v1/vms/{vm_name}/stop")
        assert response.status_code == 200
        
        # Delete VM via API
        response = await self.client.delete(f"{self.base_url}/api/v1/vms/{vm_name}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test API error handling scenarios."""
        # Test creating VM with invalid config
        invalid_vm_data = {
            "name": "invalid-vm",
            "os_type": "invalid-os",
            "vcpus": -1,
            "memory_mb": 0
        }
        
        response = await self.client.post(f"{self.base_url}/api/v1/vms", json=invalid_vm_data)
        assert response.status_code == 422
        
        # Test operating on non-existent VM
        response = await self.client.get(f"{self.base_url}/api/v1/vms/non-existent-vm")
        assert response.status_code == 404
        
        # Test starting non-existent VM
        response = await self.client.post(f"{self.base_url}/api/v1/vms/non-existent-vm/start")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_api_authentication(self):
        """Test API authentication requirements."""
        # Test accessing protected endpoint without auth
        response = await self.client.get(f"{self.base_url}/api/v1/vms")
        # Should either work (if auth disabled) or return 401
        assert response.status_code in [200, 401]
        
        if response.status_code == 401:
            # Test with invalid token
            headers = {"Authorization": "Bearer invalid-token"}
            response = await self.client.get(f"{self.base_url}/api/v1/vms", headers=headers)
            assert response.status_code == 401