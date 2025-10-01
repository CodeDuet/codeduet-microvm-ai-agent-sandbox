"""Performance tests for VM boot times."""

import asyncio
import pytest
import time
import statistics
from typing import List, Dict, Any

from src.core.vm_manager import VMManager
from src.utils.config import Config
from src.api.models.vm import VMRequest


class TestBootPerformance:
    """Test VM boot time performance."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test environment."""
        self.config = Config()
        self.vm_manager = VMManager(self.config)
        self.test_vms = []
        
        yield
        
        # Cleanup
        await self.cleanup_test_vms()

    async def cleanup_test_vms(self):
        """Cleanup all test VMs."""
        for vm_name in self.test_vms:
            try:
                await self.vm_manager.stop_vm(vm_name)
                await self.vm_manager.delete_vm(vm_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_linux_boot_time_single_vm(self):
        """Test single Linux VM boot time."""
        vm_name = "perf-linux-boot"
        self.test_vms.append(vm_name)
        
        # Create VM
        vm_request = VMRequest(
            name=vm_name,
            os_type="linux",
            vcpus=2,
            memory_mb=512,
            template="linux-default"
        )
        
        await self.vm_manager.create_vm(vm_request)
        
        # Measure boot time
        start_time = time.time()
        await self.vm_manager.start_vm(vm_name)
        
        # Wait for VM to be responsive
        await self._wait_for_vm_ready(vm_name)
        end_time = time.time()
        
        boot_time = end_time - start_time
        
        # Assert boot time is under target (3 seconds)
        assert boot_time < 3.0, f"Linux boot time {boot_time:.2f}s exceeds 3s target"
        
        print(f"Linux VM boot time: {boot_time:.2f} seconds")

    @pytest.mark.asyncio
    async def test_windows_boot_time_single_vm(self):
        """Test single Windows VM boot time."""
        vm_name = "perf-windows-boot"
        self.test_vms.append(vm_name)
        
        # Create VM
        vm_request = VMRequest(
            name=vm_name,
            os_type="windows",
            vcpus=4,
            memory_mb=2048,
            template="windows-default"
        )
        
        await self.vm_manager.create_vm(vm_request)
        
        # Measure boot time
        start_time = time.time()
        await self.vm_manager.start_vm(vm_name)
        
        # Wait for VM to be responsive
        await self._wait_for_vm_ready(vm_name, timeout=60)
        end_time = time.time()
        
        boot_time = end_time - start_time
        
        # Assert boot time is under target (10 seconds)
        assert boot_time < 10.0, f"Windows boot time {boot_time:.2f}s exceeds 10s target"
        
        print(f"Windows VM boot time: {boot_time:.2f} seconds")

    @pytest.mark.asyncio
    async def test_linux_boot_time_multiple_samples(self):
        """Test Linux VM boot time consistency across multiple samples."""
        boot_times = []
        
        for i in range(5):
            vm_name = f"perf-linux-sample-{i}"
            self.test_vms.append(vm_name)
            
            vm_request = VMRequest(
                name=vm_name,
                os_type="linux",
                vcpus=2,
                memory_mb=512
            )
            
            await self.vm_manager.create_vm(vm_request)
            
            start_time = time.time()
            await self.vm_manager.start_vm(vm_name)
            await self._wait_for_vm_ready(vm_name)
            end_time = time.time()
            
            boot_time = end_time - start_time
            boot_times.append(boot_time)
            
            # Clean up immediately to free resources
            await self.vm_manager.stop_vm(vm_name)
            await self.vm_manager.delete_vm(vm_name)
            self.test_vms.remove(vm_name)
        
        # Calculate statistics
        avg_boot_time = statistics.mean(boot_times)
        max_boot_time = max(boot_times)
        min_boot_time = min(boot_times)
        std_dev = statistics.stdev(boot_times) if len(boot_times) > 1 else 0
        
        print(f"Linux boot time statistics:")
        print(f"  Average: {avg_boot_time:.2f}s")
        print(f"  Min: {min_boot_time:.2f}s")
        print(f"  Max: {max_boot_time:.2f}s")
        print(f"  Std Dev: {std_dev:.2f}s")
        
        # Assert performance requirements
        assert avg_boot_time < 3.0, f"Average boot time {avg_boot_time:.2f}s exceeds 3s target"
        assert max_boot_time < 5.0, f"Max boot time {max_boot_time:.2f}s exceeds 5s tolerance"
        assert std_dev < 1.0, f"Boot time variance {std_dev:.2f}s too high"

    @pytest.mark.asyncio
    async def test_concurrent_boot_performance(self):
        """Test boot time performance with concurrent VM starts."""
        vm_count = 5
        vm_names = [f"perf-concurrent-{i}" for i in range(vm_count)]
        self.test_vms.extend(vm_names)
        
        # Create all VMs first
        create_tasks = []
        for vm_name in vm_names:
            vm_request = VMRequest(
                name=vm_name,
                os_type="linux",
                vcpus=1,
                memory_mb=256
            )
            create_tasks.append(self.vm_manager.create_vm(vm_request))
        
        await asyncio.gather(*create_tasks)
        
        # Start all VMs concurrently and measure time
        start_time = time.time()
        start_tasks = [self.vm_manager.start_vm(vm_name) for vm_name in vm_names]
        await asyncio.gather(*start_tasks)
        
        # Wait for all VMs to be ready
        ready_tasks = [self._wait_for_vm_ready(vm_name) for vm_name in vm_names]
        await asyncio.gather(*ready_tasks)
        end_time = time.time()
        
        total_time = end_time - start_time
        avg_time_per_vm = total_time / vm_count
        
        print(f"Concurrent boot performance:")
        print(f"  Total time for {vm_count} VMs: {total_time:.2f}s")
        print(f"  Average time per VM: {avg_time_per_vm:.2f}s")
        
        # Concurrent boot should be more efficient than sequential
        # Allow some overhead but not linear scaling
        assert total_time < vm_count * 2.0, f"Concurrent boot time {total_time:.2f}s too slow"

    @pytest.mark.asyncio
    async def test_boot_time_with_different_resources(self):
        """Test boot time impact of different resource allocations."""
        test_configs = [
            {"vcpus": 1, "memory_mb": 128, "name": "minimal"},
            {"vcpus": 2, "memory_mb": 512, "name": "standard"},
            {"vcpus": 4, "memory_mb": 1024, "name": "high"},
            {"vcpus": 8, "memory_mb": 2048, "name": "maximum"}
        ]
        
        boot_times = {}
        
        for config in test_configs:
            vm_name = f"perf-resource-{config['name']}"
            self.test_vms.append(vm_name)
            
            vm_request = VMRequest(
                name=vm_name,
                os_type="linux",
                vcpus=config["vcpus"],
                memory_mb=config["memory_mb"]
            )
            
            await self.vm_manager.create_vm(vm_request)
            
            start_time = time.time()
            await self.vm_manager.start_vm(vm_name)
            await self._wait_for_vm_ready(vm_name)
            end_time = time.time()
            
            boot_time = end_time - start_time
            boot_times[config["name"]] = boot_time
            
            print(f"{config['name']} config ({config['vcpus']} vCPU, {config['memory_mb']}MB): {boot_time:.2f}s")
        
        # Boot time should not dramatically increase with more resources
        # (within reasonable limits)
        assert boot_times["maximum"] < boot_times["minimal"] * 2.0, \
            "High-resource VM takes too much longer to boot"

    async def _wait_for_vm_ready(self, vm_name: str, timeout: int = 30) -> bool:
        """Wait for VM to be ready and responsive."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                vm_info = await self.vm_manager.get_vm_info(vm_name)
                if vm_info.status == "running":
                    # Additional check - try to execute a simple command
                    result = await self.vm_manager.execute_command(vm_name, "echo ready")
                    if result.exit_code == 0:
                        return True
            except Exception:
                pass
            
            await asyncio.sleep(0.5)
        
        raise TimeoutError(f"VM {vm_name} did not become ready within {timeout}s")


class TestShutdownPerformance:
    """Test VM shutdown time performance."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test environment."""
        self.config = Config()
        self.vm_manager = VMManager(self.config)
        self.test_vms = []
        
        yield
        
        # Cleanup
        await self.cleanup_test_vms()

    async def cleanup_test_vms(self):
        """Cleanup all test VMs."""
        for vm_name in self.test_vms:
            try:
                await self.vm_manager.stop_vm(vm_name)
                await self.vm_manager.delete_vm(vm_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_graceful_shutdown_time(self):
        """Test graceful shutdown time."""
        vm_name = "perf-shutdown"
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
        await asyncio.sleep(10)
        
        # Measure shutdown time
        start_time = time.time()
        await self.vm_manager.stop_vm(vm_name)
        end_time = time.time()
        
        shutdown_time = end_time - start_time
        
        # Graceful shutdown should be fast
        assert shutdown_time < 5.0, f"Shutdown time {shutdown_time:.2f}s too slow"
        
        print(f"Graceful shutdown time: {shutdown_time:.2f} seconds")

    @pytest.mark.asyncio
    async def test_force_shutdown_time(self):
        """Test force shutdown time."""
        vm_name = "perf-force-shutdown"
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
        await asyncio.sleep(10)
        
        # Measure force shutdown time
        start_time = time.time()
        await self.vm_manager.force_stop_vm(vm_name)
        end_time = time.time()
        
        shutdown_time = end_time - start_time
        
        # Force shutdown should be very fast
        assert shutdown_time < 2.0, f"Force shutdown time {shutdown_time:.2f}s too slow"
        
        print(f"Force shutdown time: {shutdown_time:.2f} seconds")