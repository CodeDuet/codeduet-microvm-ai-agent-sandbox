"""Performance tests for resource usage monitoring."""

import asyncio
import pytest
import time
import psutil
import statistics
from typing import List, Dict, Any, Optional

from src.core.vm_manager import VMManager
from src.core.resource_manager import ResourceManager
from src.utils.config import Config
from src.api.models.vm import VMRequest


class TestResourceUsagePerformance:
    """Test resource usage and monitoring performance."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup test environment."""
        self.config = Config()
        self.vm_manager = VMManager(self.config)
        self.resource_manager = ResourceManager(self.config)
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
    async def test_host_resource_monitoring_overhead(self):
        """Test overhead of host resource monitoring."""
        # Measure baseline performance
        baseline_samples = []
        for _ in range(10):
            start_time = time.time()
            await asyncio.sleep(0.1)  # Simulate work
            end_time = time.time()
            baseline_samples.append(end_time - start_time)
        
        baseline_avg = statistics.mean(baseline_samples)
        
        # Measure performance with monitoring
        monitoring_samples = []
        for _ in range(10):
            start_time = time.time()
            
            # Get resource metrics (this should have minimal overhead)
            host_metrics = await self.resource_manager.get_host_metrics()
            
            await asyncio.sleep(0.1)  # Simulate work
            end_time = time.time()
            monitoring_samples.append(end_time - start_time)
        
        monitoring_avg = statistics.mean(monitoring_samples)
        overhead = monitoring_avg - baseline_avg
        overhead_percent = (overhead / baseline_avg) * 100
        
        print(f"Resource monitoring overhead:")
        print(f"  Baseline: {baseline_avg*1000:.2f}ms")
        print(f"  With monitoring: {monitoring_avg*1000:.2f}ms")
        print(f"  Overhead: {overhead*1000:.2f}ms ({overhead_percent:.1f}%)")
        
        # Monitoring overhead should be minimal (<5%)
        assert overhead_percent < 5.0, f"Resource monitoring overhead too high: {overhead_percent:.1f}%"

    @pytest.mark.asyncio
    async def test_vm_resource_tracking_accuracy(self):
        """Test accuracy of VM resource tracking."""
        vm_name = "perf-resource-tracking"
        self.test_vms.append(vm_name)
        
        # Create VM with known resource allocation
        vm_request = VMRequest(
            name=vm_name,
            os_type="linux",
            vcpus=2,
            memory_mb=512
        )
        
        await self.vm_manager.create_vm(vm_request)
        await self.vm_manager.start_vm(vm_name)
        
        # Wait for VM to stabilize
        await asyncio.sleep(10)
        
        # Get VM metrics
        vm_metrics = await self.resource_manager.get_vm_metrics(vm_name)
        
        print(f"VM resource tracking:")
        print(f"  Allocated vCPUs: {vm_request.vcpus}")
        print(f"  Tracked vCPUs: {vm_metrics.vcpus}")
        print(f"  Allocated memory: {vm_request.memory_mb}MB")
        print(f"  Tracked memory: {vm_metrics.memory_allocated_mb}MB")
        
        # Tracked resources should match allocation
        assert vm_metrics.vcpus == vm_request.vcpus
        assert vm_metrics.memory_allocated_mb == vm_request.memory_mb
        
        # Memory usage should be reasonable (not zero, not exceeding allocation)
        assert 0 < vm_metrics.memory_used_mb <= vm_request.memory_mb
        
        # CPU usage should be measurable
        assert vm_metrics.cpu_usage_percent >= 0

    @pytest.mark.asyncio
    async def test_resource_limit_enforcement(self):
        """Test resource limit enforcement performance."""
        # Test CPU limit enforcement
        vm_name = "perf-cpu-limit"
        self.test_vms.append(vm_name)
        
        vm_request = VMRequest(
            name=vm_name,
            os_type="linux",
            vcpus=1,
            memory_mb=256,
            cpu_limit_percent=50  # Limit to 50% CPU
        )
        
        await self.vm_manager.create_vm(vm_request)
        await self.vm_manager.start_vm(vm_name)
        
        # Wait for VM to be ready
        await asyncio.sleep(10)
        
        # Run CPU-intensive task
        cpu_task = "yes > /dev/null &"  # CPU-intensive background task
        await self.vm_manager.execute_command(vm_name, cpu_task)
        
        # Monitor CPU usage over time
        cpu_samples = []
        for _ in range(10):
            await asyncio.sleep(2)
            metrics = await self.resource_manager.get_vm_metrics(vm_name)
            cpu_samples.append(metrics.cpu_usage_percent)
        
        avg_cpu = statistics.mean(cpu_samples)
        max_cpu = max(cpu_samples)
        
        print(f"CPU limit enforcement:")
        print(f"  CPU limit: 50%")
        print(f"  Average CPU usage: {avg_cpu:.1f}%")
        print(f"  Max CPU usage: {max_cpu:.1f}%")
        
        # CPU usage should respect the limit (with some tolerance)
        assert max_cpu <= 70, f"CPU limit not enforced: {max_cpu:.1f}% > 70%"

    @pytest.mark.asyncio
    async def test_memory_limit_enforcement(self):
        """Test memory limit enforcement."""
        vm_name = "perf-memory-limit"
        self.test_vms.append(vm_name)
        
        vm_request = VMRequest(
            name=vm_name,
            os_type="linux",
            vcpus=1,
            memory_mb=256
        )
        
        await self.vm_manager.create_vm(vm_request)
        await self.vm_manager.start_vm(vm_name)
        
        # Wait for VM to be ready
        await asyncio.sleep(10)
        
        # Try to allocate memory approaching the limit
        # Allocate 200MB in a VM with 256MB limit
        memory_test = """
        python3 -c "
        import time
        data = bytearray(200 * 1024 * 1024)  # 200MB
        time.sleep(5)
        print('Memory allocated successfully')
        "
        """
        
        result = await self.vm_manager.execute_command(vm_name, memory_test)
        
        # Command should complete (memory within limits)
        assert result.exit_code == 0, "Memory allocation within limits failed"
        
        # Check actual memory usage
        metrics = await self.resource_manager.get_vm_metrics(vm_name)
        
        print(f"Memory limit enforcement:")
        print(f"  Memory limit: {vm_request.memory_mb}MB")
        print(f"  Memory used: {metrics.memory_used_mb}MB")
        print(f"  Memory usage: {metrics.memory_usage_percent:.1f}%")
        
        # Memory usage should be within limits
        assert metrics.memory_used_mb <= vm_request.memory_mb

    @pytest.mark.asyncio
    async def test_resource_scaling_performance(self):
        """Test performance of resource scaling operations."""
        vm_name = "perf-scaling"
        self.test_vms.append(vm_name)
        
        # Create VM with initial resources
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
        
        # Test memory scaling
        start_time = time.time()
        await self.resource_manager.resize_vm_memory(vm_name, 1024)  # Scale to 1GB
        memory_scale_time = time.time() - start_time
        
        # Verify scaling
        metrics = await self.resource_manager.get_vm_metrics(vm_name)
        assert metrics.memory_allocated_mb == 1024
        
        print(f"Resource scaling performance:")
        print(f"  Memory scaling time: {memory_scale_time:.2f}s")
        
        # Scaling should be relatively fast
        assert memory_scale_time < 10.0, f"Memory scaling too slow: {memory_scale_time:.2f}s"

    @pytest.mark.asyncio
    async def test_system_resource_pressure_handling(self):
        """Test system behavior under resource pressure."""
        # Create multiple VMs to increase resource pressure
        vm_count = 5
        vm_names = [f"perf-pressure-{i}" for i in range(vm_count)]
        self.test_vms.extend(vm_names)
        
        # Record initial system state
        initial_metrics = await self.resource_manager.get_host_metrics()
        
        # Create VMs with significant resource allocation
        create_tasks = []
        for vm_name in vm_names:
            vm_request = VMRequest(
                name=vm_name,
                os_type="linux",
                vcpus=2,
                memory_mb=512
            )
            create_tasks.append(self.vm_manager.create_vm(vm_request))
        
        await asyncio.gather(*create_tasks)
        
        # Start VMs
        start_tasks = [self.vm_manager.start_vm(vm_name) for vm_name in vm_names]
        await asyncio.gather(*start_tasks)
        
        # Wait for VMs to stabilize
        await asyncio.sleep(15)
        
        # Run resource-intensive tasks on all VMs
        task_commands = [
            self.vm_manager.execute_command(vm_name, "stress --cpu 1 --timeout 10s")
            for vm_name in vm_names
        ]
        
        start_time = time.time()
        await asyncio.gather(*task_commands, return_exceptions=True)
        execution_time = time.time() - start_time
        
        # Get final system state
        final_metrics = await self.resource_manager.get_host_metrics()
        
        print(f"System resource pressure test:")
        print(f"  Initial CPU usage: {initial_metrics.cpu_usage_percent:.1f}%")
        print(f"  Final CPU usage: {final_metrics.cpu_usage_percent:.1f}%")
        print(f"  Initial memory usage: {initial_metrics.memory_usage_percent:.1f}%")
        print(f"  Final memory usage: {final_metrics.memory_usage_percent:.1f}%")
        print(f"  Stress test execution time: {execution_time:.2f}s")
        
        # System should remain responsive under pressure
        assert execution_time < 20.0, f"System too slow under pressure: {execution_time:.2f}s"
        
        # System should not be completely overwhelmed
        assert final_metrics.cpu_usage_percent < 95.0, "System CPU overwhelmed"
        assert final_metrics.memory_usage_percent < 95.0, "System memory overwhelmed"

    @pytest.mark.asyncio
    async def test_resource_monitoring_scalability(self):
        """Test scalability of resource monitoring with many VMs."""
        vm_count = 10
        vm_names = [f"perf-monitor-{i}" for i in range(vm_count)]
        self.test_vms.extend(vm_names)
        
        # Create and start VMs
        for vm_name in vm_names:
            vm_request = VMRequest(
                name=vm_name,
                os_type="linux",
                vcpus=1,
                memory_mb=256
            )
            await self.vm_manager.create_vm(vm_request)
            await self.vm_manager.start_vm(vm_name)
        
        # Wait for VMs to be ready
        await asyncio.sleep(20)
        
        # Test monitoring performance with all VMs
        monitoring_times = []
        
        for _ in range(5):
            start_time = time.time()
            
            # Get metrics for all VMs
            metric_tasks = [
                self.resource_manager.get_vm_metrics(vm_name) 
                for vm_name in vm_names
            ]
            all_metrics = await asyncio.gather(*metric_tasks)
            
            end_time = time.time()
            monitoring_time = end_time - start_time
            monitoring_times.append(monitoring_time)
        
        avg_monitoring_time = statistics.mean(monitoring_times)
        time_per_vm = avg_monitoring_time / vm_count
        
        print(f"Resource monitoring scalability:")
        print(f"  {vm_count} VMs monitored in {avg_monitoring_time:.3f}s")
        print(f"  Average time per VM: {time_per_vm*1000:.1f}ms")
        
        # Monitoring should scale efficiently
        assert avg_monitoring_time < 2.0, f"Monitoring too slow: {avg_monitoring_time:.3f}s"
        assert time_per_vm < 0.1, f"Per-VM monitoring overhead too high: {time_per_vm*1000:.1f}ms"
        
        # Verify all metrics were collected
        assert len(all_metrics) == vm_count
        assert all(metrics is not None for metrics in all_metrics)

    @pytest.mark.asyncio
    async def test_resource_optimization_effectiveness(self):
        """Test effectiveness of resource optimization algorithms."""
        # Create VMs with different resource patterns
        vm_configs = [
            {"name": "high-cpu", "vcpus": 4, "memory_mb": 512},
            {"name": "high-memory", "vcpus": 1, "memory_mb": 1024},
            {"name": "balanced", "vcpus": 2, "memory_mb": 512},
            {"name": "minimal", "vcpus": 1, "memory_mb": 256}
        ]
        
        vm_names = []
        for config in vm_configs:
            vm_name = f"perf-opt-{config['name']}"
            vm_names.append(vm_name)
            self.test_vms.append(vm_name)
            
            vm_request = VMRequest(
                name=vm_name,
                os_type="linux",
                vcpus=config["vcpus"],
                memory_mb=config["memory_mb"]
            )
            
            await self.vm_manager.create_vm(vm_request)
            await self.vm_manager.start_vm(vm_name)
        
        # Wait for VMs to stabilize
        await asyncio.sleep(15)
        
        # Get baseline resource usage
        baseline_metrics = {}
        for vm_name in vm_names:
            metrics = await self.resource_manager.get_vm_metrics(vm_name)
            baseline_metrics[vm_name] = metrics
        
        # Run optimization
        start_time = time.time()
        optimization_result = await self.resource_manager.optimize_resources()
        optimization_time = time.time() - start_time
        
        # Get post-optimization metrics
        optimized_metrics = {}
        for vm_name in vm_names:
            metrics = await self.resource_manager.get_vm_metrics(vm_name)
            optimized_metrics[vm_name] = metrics
        
        print(f"Resource optimization test:")
        print(f"  Optimization time: {optimization_time:.2f}s")
        print(f"  Optimization result: {optimization_result}")
        
        # Optimization should complete quickly
        assert optimization_time < 30.0, f"Resource optimization too slow: {optimization_time:.2f}s"
        
        # Calculate efficiency improvements
        total_cpu_before = sum(m.cpu_usage_percent for m in baseline_metrics.values())
        total_cpu_after = sum(m.cpu_usage_percent for m in optimized_metrics.values())
        
        if total_cpu_before > 0:
            cpu_efficiency = (total_cpu_before - total_cpu_after) / total_cpu_before * 100
            print(f"  CPU efficiency improvement: {cpu_efficiency:.1f}%")
        
        # Optimization should not negatively impact performance significantly
        for vm_name in vm_names:
            before = baseline_metrics[vm_name]
            after = optimized_metrics[vm_name]
            
            # Memory allocation should not decrease (VMs need their allocated memory)
            assert after.memory_allocated_mb >= before.memory_allocated_mb * 0.9
            
            # CPU allocation should remain reasonable
            assert after.vcpus >= before.vcpus * 0.5