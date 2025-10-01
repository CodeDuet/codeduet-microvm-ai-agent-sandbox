"""Performance tests for concurrent VM operations."""

import asyncio
import pytest
import time
import psutil
import statistics
from typing import List, Dict, Any

from src.core.vm_manager import VMManager
from src.utils.config import Config
from src.api.models.vm import VMRequest


class TestConcurrentVMPerformance:
    """Test performance with concurrent VM operations."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test environment."""
        self.config = Config()
        self.vm_manager = VMManager(self.config)
        self.test_vms = []
        
        # Record initial system state
        self.initial_cpu_percent = psutil.cpu_percent(interval=1)
        self.initial_memory = psutil.virtual_memory()
        
        yield
        
        # Cleanup
        await self.cleanup_test_vms()

    async def cleanup_test_vms(self):
        """Cleanup all test VMs."""
        # Stop all VMs concurrently for faster cleanup
        stop_tasks = []
        for vm_name in self.test_vms:
            try:
                stop_tasks.append(self.vm_manager.stop_vm(vm_name))
            except Exception:
                pass
        
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        # Delete all VMs concurrently
        delete_tasks = []
        for vm_name in self.test_vms:
            try:
                delete_tasks.append(self.vm_manager.delete_vm(vm_name))
            except Exception:
                pass
        
        if delete_tasks:
            await asyncio.gather(*delete_tasks, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_concurrent_vm_creation(self):
        """Test concurrent VM creation performance."""
        vm_count = 10
        vm_names = [f"perf-create-{i}" for i in range(vm_count)]
        self.test_vms.extend(vm_names)
        
        # Create VMs concurrently
        start_time = time.time()
        create_tasks = []
        
        for vm_name in vm_names:
            vm_request = VMRequest(
                name=vm_name,
                os_type="linux",
                vcpus=1,
                memory_mb=256
            )
            create_tasks.append(self.vm_manager.create_vm(vm_request))
        
        results = await asyncio.gather(*create_tasks)
        end_time = time.time()
        
        creation_time = end_time - start_time
        avg_time_per_vm = creation_time / vm_count
        
        print(f"Concurrent VM creation performance:")
        print(f"  Created {vm_count} VMs in {creation_time:.2f}s")
        print(f"  Average time per VM: {avg_time_per_vm:.2f}s")
        
        # All VMs should be created successfully
        assert len(results) == vm_count
        assert all(vm.name in vm_names for vm in results)
        
        # Concurrent creation should be more efficient than sequential
        assert creation_time < vm_count * 1.0, "Concurrent creation too slow"

    @pytest.mark.asyncio
    async def test_concurrent_vm_startup(self):
        """Test concurrent VM startup performance."""
        vm_count = 8
        vm_names = [f"perf-startup-{i}" for i in range(vm_count)]
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
        
        # Start all VMs concurrently
        start_time = time.time()
        startup_tasks = [self.vm_manager.start_vm(vm_name) for vm_name in vm_names]
        await asyncio.gather(*startup_tasks)
        end_time = time.time()
        
        startup_time = end_time - start_time
        avg_time_per_vm = startup_time / vm_count
        
        print(f"Concurrent VM startup performance:")
        print(f"  Started {vm_count} VMs in {startup_time:.2f}s")
        print(f"  Average time per VM: {avg_time_per_vm:.2f}s")
        
        # Verify all VMs are running
        for vm_name in vm_names:
            vm_info = await self.vm_manager.get_vm_info(vm_name)
            assert vm_info.status == "running"
        
        # Concurrent startup should scale reasonably
        assert startup_time < vm_count * 2.0, "Concurrent startup too slow"

    @pytest.mark.asyncio
    async def test_maximum_concurrent_vms(self):
        """Test maximum number of concurrent VMs the system can handle."""
        max_vms = self.config.resources.max_vms or 50
        vm_count = min(max_vms, 20)  # Test up to 20 VMs for CI/CD compatibility
        
        vm_names = [f"perf-max-{i}" for i in range(vm_count)]
        self.test_vms.extend(vm_names)
        
        # Monitor system resources
        initial_memory = psutil.virtual_memory().used
        
        # Create and start VMs in batches to avoid overwhelming the system
        batch_size = 5
        successful_vms = []
        
        for i in range(0, vm_count, batch_size):
            batch_names = vm_names[i:i + batch_size]
            batch_tasks = []
            
            # Create batch
            for vm_name in batch_names:
                vm_request = VMRequest(
                    name=vm_name,
                    os_type="linux",
                    vcpus=1,
                    memory_mb=128  # Minimal memory to maximize VM count
                )
                batch_tasks.append(self.vm_manager.create_vm(vm_request))
            
            try:
                await asyncio.gather(*batch_tasks)
                
                # Start batch
                start_tasks = [self.vm_manager.start_vm(vm_name) for vm_name in batch_names]
                await asyncio.gather(*start_tasks)
                
                successful_vms.extend(batch_names)
                
                # Check system resources
                current_memory = psutil.virtual_memory()
                memory_usage_mb = (current_memory.used - initial_memory) / (1024 * 1024)
                
                print(f"Batch {i//batch_size + 1}: {len(successful_vms)} VMs running, "
                      f"Memory usage: {memory_usage_mb:.0f}MB, "
                      f"Memory percent: {current_memory.percent:.1f}%")
                
                # Stop if memory usage gets too high
                if current_memory.percent > 90:
                    print(f"Stopping at {len(successful_vms)} VMs due to high memory usage")
                    break
                
            except Exception as e:
                print(f"Failed to create/start batch at {len(successful_vms)} VMs: {e}")
                break
        
        print(f"Successfully ran {len(successful_vms)} concurrent VMs")
        
        # Should be able to run at least 10 VMs
        assert len(successful_vms) >= 10, f"Only managed {len(successful_vms)} concurrent VMs"
        
        # Calculate resource overhead
        final_memory = psutil.virtual_memory()
        memory_per_vm = (final_memory.used - initial_memory) / len(successful_vms) / (1024 * 1024)
        
        print(f"Average memory per VM: {memory_per_vm:.1f}MB")
        
        # Memory overhead should be reasonable
        assert memory_per_vm < 200, f"Memory overhead too high: {memory_per_vm:.1f}MB per VM"

    @pytest.mark.asyncio
    async def test_concurrent_command_execution(self):
        """Test concurrent command execution across multiple VMs."""
        vm_count = 5
        vm_names = [f"perf-cmd-{i}" for i in range(vm_count)]
        self.test_vms.extend(vm_names)
        
        # Create and start VMs
        for vm_name in vm_names:
            vm_request = VMRequest(
                name=vm_name,
                os_type="linux",
                vcpus=2,
                memory_mb=512
            )
            await self.vm_manager.create_vm(vm_request)
            await self.vm_manager.start_vm(vm_name)
        
        # Wait for all VMs to be ready
        await asyncio.sleep(15)
        
        # Execute commands concurrently
        command = "echo 'test command' && sleep 1 && echo 'command complete'"
        
        start_time = time.time()
        cmd_tasks = [
            self.vm_manager.execute_command(vm_name, command) 
            for vm_name in vm_names
        ]
        results = await asyncio.gather(*cmd_tasks)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        print(f"Concurrent command execution:")
        print(f"  Executed commands on {vm_count} VMs in {execution_time:.2f}s")
        
        # All commands should succeed
        assert len(results) == vm_count
        assert all(result.exit_code == 0 for result in results)
        
        # Concurrent execution should be faster than sequential
        # (Commands include 1s sleep, so concurrent should be ~1s, not vm_count seconds)
        assert execution_time < vm_count * 0.5, "Concurrent execution not efficient"

    @pytest.mark.asyncio
    async def test_vm_lifecycle_stress_test(self):
        """Stress test complete VM lifecycle operations."""
        cycles = 3
        vms_per_cycle = 5
        
        cycle_times = []
        
        for cycle in range(cycles):
            vm_names = [f"stress-cycle{cycle}-vm{i}" for i in range(vms_per_cycle)]
            
            start_time = time.time()
            
            # Create VMs
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
            
            # Start VMs
            start_tasks = [self.vm_manager.start_vm(vm_name) for vm_name in vm_names]
            await asyncio.gather(*start_tasks)
            
            # Execute commands
            cmd_tasks = [
                self.vm_manager.execute_command(vm_name, "echo 'stress test'") 
                for vm_name in vm_names
            ]
            await asyncio.gather(*cmd_tasks)
            
            # Stop VMs
            stop_tasks = [self.vm_manager.stop_vm(vm_name) for vm_name in vm_names]
            await asyncio.gather(*stop_tasks)
            
            # Delete VMs
            delete_tasks = [self.vm_manager.delete_vm(vm_name) for vm_name in vm_names]
            await asyncio.gather(*delete_tasks)
            
            end_time = time.time()
            cycle_time = end_time - start_time
            cycle_times.append(cycle_time)
            
            print(f"Stress test cycle {cycle + 1}: {cycle_time:.2f}s")
        
        avg_cycle_time = statistics.mean(cycle_times)
        max_cycle_time = max(cycle_times)
        
        print(f"Stress test summary:")
        print(f"  Average cycle time: {avg_cycle_time:.2f}s")
        print(f"  Max cycle time: {max_cycle_time:.2f}s")
        
        # Performance should be consistent across cycles
        assert max_cycle_time < avg_cycle_time * 1.5, "Performance degradation detected"
        
        # Each cycle should complete in reasonable time
        assert avg_cycle_time < 30.0, f"Stress test cycles too slow: {avg_cycle_time:.2f}s"

    @pytest.mark.asyncio
    async def test_resource_cleanup_after_load(self):
        """Test that resources are properly cleaned up after load testing."""
        vm_count = 10
        vm_names = [f"perf-cleanup-{i}" for i in range(vm_count)]
        
        # Record initial state
        initial_memory = psutil.virtual_memory()
        initial_cpu = psutil.cpu_percent(interval=1)
        
        # Create and run VMs
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
        
        # Start VMs
        start_tasks = [self.vm_manager.start_vm(vm_name) for vm_name in vm_names]
        await asyncio.gather(*start_tasks)
        
        # Record peak state
        await asyncio.sleep(5)
        peak_memory = psutil.virtual_memory()
        
        # Clean up VMs
        stop_tasks = [self.vm_manager.stop_vm(vm_name) for vm_name in vm_names]
        await asyncio.gather(*stop_tasks)
        
        delete_tasks = [self.vm_manager.delete_vm(vm_name) for vm_name in vm_names]
        await asyncio.gather(*delete_tasks)
        
        # Wait for cleanup
        await asyncio.sleep(5)
        
        # Record final state
        final_memory = psutil.virtual_memory()
        final_cpu = psutil.cpu_percent(interval=1)
        
        print(f"Resource cleanup test:")
        print(f"  Initial memory: {initial_memory.percent:.1f}%")
        print(f"  Peak memory: {peak_memory.percent:.1f}%")
        print(f"  Final memory: {final_memory.percent:.1f}%")
        
        # Memory should return close to initial levels
        memory_diff = abs(final_memory.percent - initial_memory.percent)
        assert memory_diff < 5.0, f"Memory not properly cleaned up: {memory_diff:.1f}% difference"
        
        # CPU should return to normal levels
        cpu_diff = abs(final_cpu - initial_cpu)
        assert cpu_diff < 20.0, f"CPU usage elevated after cleanup: {cpu_diff:.1f}% difference"