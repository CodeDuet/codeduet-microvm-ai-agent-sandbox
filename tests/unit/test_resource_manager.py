"""
Unit tests for the Resource Manager.

Tests cover:
- Resource allocation and deallocation
- Resource limits and quotas enforcement
- System resource monitoring
- Resource optimization algorithms
- Automatic resource scaling
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import dataclass

from src.core.resource_manager import (
    ResourceManager,
    ResourceQuota,
    ResourceAllocation,
    SystemResourceUsage,
    ResourceRecommendation
)


@pytest.fixture
def mock_config():
    """Mock configuration for resource manager."""
    return {
        "resources": {
            "max_vcpus_per_vm": 8,
            "max_memory_per_vm": 8192,
            "max_disk_per_vm": 100,
            "max_vms": 50
        }
    }


@pytest.fixture
def resource_manager(mock_config):
    """Create a resource manager instance for testing."""
    return ResourceManager(mock_config)


@pytest.fixture
def sample_quota():
    """Sample resource quota for testing."""
    return ResourceQuota(
        max_vcpus=4,
        max_memory_mb=2048,
        max_disk_gb=20,
        max_vms=5,
        priority=1
    )


@pytest.fixture
def sample_allocation():
    """Sample resource allocation for testing."""
    return ResourceAllocation(
        vm_name="test-vm",
        vcpus=2,
        memory_mb=1024,
        disk_gb=10,
        allocated_at=datetime.now(),
        last_updated=datetime.now(),
        priority=1,
        cpu_usage_percent=50.0,
        memory_usage_percent=60.0
    )


@pytest.fixture
def sample_system_usage():
    """Sample system resource usage for testing."""
    return SystemResourceUsage(
        total_vcpus=8,
        available_vcpus=4,
        used_vcpus=4,
        total_memory_mb=8192,
        available_memory_mb=4096,
        used_memory_mb=4096,
        total_disk_gb=500,
        available_disk_gb=300,
        used_disk_gb=200,
        active_vms=2,
        cpu_usage_percent=50.0,
        memory_usage_percent=50.0,
        disk_usage_percent=40.0,
        load_average=[1.0, 1.2, 1.1],
        timestamp=datetime.now()
    )


class TestResourceManager:
    """Test cases for ResourceManager class."""
    
    def test_init(self, mock_config):
        """Test resource manager initialization."""
        rm = ResourceManager(mock_config)
        
        assert rm.system_limits.max_vcpus == 8
        assert rm.system_limits.max_memory_mb == 8192
        assert rm.system_limits.max_vms == 50
        assert rm.monitoring_enabled is True
        assert rm.optimization_enabled is True
        assert rm.scaling_enabled is True
        assert len(rm.allocations) == 0
        assert len(rm.quotas) == 0
    
    @patch('psutil.cpu_count')
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.getloadavg')
    async def test_get_system_resources(self, mock_loadavg, mock_disk, mock_memory, 
                                      mock_cpu_percent, mock_cpu_count, resource_manager):
        """Test getting system resource usage."""
        # Mock psutil responses
        mock_cpu_count.return_value = 8
        mock_cpu_percent.return_value = 50.0
        mock_memory.return_value = Mock(total=8589934592, available=4294967296)  # 8GB total, 4GB available
        mock_disk.return_value = Mock(total=536870912000, free=322122547200)  # 500GB total, 300GB free
        mock_loadavg.return_value = (1.0, 1.2, 1.1)
        
        usage = await resource_manager.get_system_resources()
        
        assert usage.total_vcpus == 8
        assert usage.available_vcpus == 8  # No allocations yet
        assert usage.used_vcpus == 0
        assert usage.total_memory_mb == 8192
        assert usage.cpu_usage_percent == 50.0
        assert usage.load_average == [1.0, 1.2, 1.1]
        assert len(resource_manager.usage_history) == 1
    
    async def test_allocate_resources_success(self, resource_manager):
        """Test successful resource allocation."""
        with patch.object(resource_manager, 'get_system_resources') as mock_get_system:
            mock_get_system.return_value = SystemResourceUsage(
                total_vcpus=8, available_vcpus=8, used_vcpus=0,
                total_memory_mb=8192, available_memory_mb=8192, used_memory_mb=0,
                total_disk_gb=500, available_disk_gb=500, used_disk_gb=0,
                active_vms=0, cpu_usage_percent=0, memory_usage_percent=0,
                disk_usage_percent=0, load_average=[0.5, 0.6, 0.7],
                timestamp=datetime.now()
            )
            
            success = await resource_manager.allocate_resources(
                vm_name="test-vm",
                vcpus=2,
                memory_mb=1024,
                disk_gb=10
            )
            
            assert success is True
            assert "test-vm" in resource_manager.allocations
            allocation = resource_manager.allocations["test-vm"]
            assert allocation.vcpus == 2
            assert allocation.memory_mb == 1024
            assert allocation.disk_gb == 10
    
    async def test_allocate_resources_insufficient_resources(self, resource_manager):
        """Test allocation failure due to insufficient resources."""
        with patch.object(resource_manager, 'get_system_resources') as mock_get_system:
            mock_get_system.return_value = SystemResourceUsage(
                total_vcpus=2, available_vcpus=1, used_vcpus=1,
                total_memory_mb=1024, available_memory_mb=512, used_memory_mb=512,
                total_disk_gb=50, available_disk_gb=5, used_disk_gb=45,
                active_vms=1, cpu_usage_percent=50, memory_usage_percent=50,
                disk_usage_percent=90, load_average=[1.0, 1.1, 1.2],
                timestamp=datetime.now()
            )
            
            success = await resource_manager.allocate_resources(
                vm_name="test-vm",
                vcpus=4,  # More than available
                memory_mb=2048,  # More than available
                disk_gb=20
            )
            
            assert success is False
            assert "test-vm" not in resource_manager.allocations
    
    async def test_allocate_resources_quota_exceeded(self, resource_manager, sample_quota):
        """Test allocation failure due to quota limits."""
        with patch.object(resource_manager, 'get_system_resources') as mock_get_system:
            mock_get_system.return_value = SystemResourceUsage(
                total_vcpus=8, available_vcpus=8, used_vcpus=0,
                total_memory_mb=8192, available_memory_mb=8192, used_memory_mb=0,
                total_disk_gb=500, available_disk_gb=500, used_disk_gb=0,
                active_vms=0, cpu_usage_percent=0, memory_usage_percent=0,
                disk_usage_percent=0, load_average=[0.5, 0.6, 0.7],
                timestamp=datetime.now()
            )
            
            success = await resource_manager.allocate_resources(
                vm_name="test-vm",
                vcpus=8,  # Exceeds quota max_vcpus=4
                memory_mb=1024,
                disk_gb=10,
                user_quota=sample_quota
            )
            
            assert success is False
            assert "test-vm" not in resource_manager.allocations
    
    async def test_allocate_resources_duplicate_vm(self, resource_manager, sample_allocation):
        """Test allocation failure for duplicate VM name."""
        resource_manager.allocations["test-vm"] = sample_allocation
        
        success = await resource_manager.allocate_resources(
            vm_name="test-vm",
            vcpus=2,
            memory_mb=1024,
            disk_gb=10
        )
        
        assert success is False
    
    async def test_deallocate_resources_success(self, resource_manager, sample_allocation):
        """Test successful resource deallocation."""
        resource_manager.allocations["test-vm"] = sample_allocation
        
        success = await resource_manager.deallocate_resources("test-vm")
        
        assert success is True
        assert "test-vm" not in resource_manager.allocations
    
    async def test_deallocate_resources_not_found(self, resource_manager):
        """Test deallocation failure for non-existent VM."""
        success = await resource_manager.deallocate_resources("non-existent-vm")
        
        assert success is False
    
    async def test_update_vm_usage_success(self, resource_manager, sample_allocation):
        """Test successful VM usage update."""
        resource_manager.allocations["test-vm"] = sample_allocation
        original_updated = sample_allocation.last_updated
        
        # Wait a bit to ensure timestamp changes
        await asyncio.sleep(0.01)
        
        success = await resource_manager.update_vm_usage(
            vm_name="test-vm",
            cpu_usage_percent=75.0,
            memory_usage_percent=80.0
        )
        
        assert success is True
        allocation = resource_manager.allocations["test-vm"]
        assert allocation.cpu_usage_percent == 75.0
        assert allocation.memory_usage_percent == 80.0
        assert allocation.last_updated > original_updated
    
    async def test_update_vm_usage_not_found(self, resource_manager):
        """Test usage update failure for non-existent VM."""
        success = await resource_manager.update_vm_usage(
            vm_name="non-existent-vm",
            cpu_usage_percent=50.0,
            memory_usage_percent=60.0
        )
        
        assert success is False
    
    async def test_resize_vm_resources_success(self, resource_manager, sample_allocation):
        """Test successful VM resource resize."""
        resource_manager.allocations["test-vm"] = sample_allocation
        
        with patch.object(resource_manager, 'get_system_resources') as mock_get_system:
            mock_get_system.return_value = SystemResourceUsage(
                total_vcpus=8, available_vcpus=6, used_vcpus=2,
                total_memory_mb=8192, available_memory_mb=7168, used_memory_mb=1024,
                total_disk_gb=500, available_disk_gb=490, used_disk_gb=10,
                active_vms=1, cpu_usage_percent=25, memory_usage_percent=12.5,
                disk_usage_percent=2, load_average=[0.5, 0.6, 0.7],
                timestamp=datetime.now()
            )
            
            success = await resource_manager.resize_vm_resources(
                vm_name="test-vm",
                new_vcpus=4,
                new_memory_mb=2048
            )
            
            assert success is True
            allocation = resource_manager.allocations["test-vm"]
            assert allocation.vcpus == 4
            assert allocation.memory_mb == 2048
    
    async def test_resize_vm_resources_insufficient_resources(self, resource_manager, sample_allocation):
        """Test resize failure due to insufficient resources."""
        resource_manager.allocations["test-vm"] = sample_allocation
        
        with patch.object(resource_manager, 'get_system_resources') as mock_get_system:
            mock_get_system.return_value = SystemResourceUsage(
                total_vcpus=4, available_vcpus=2, used_vcpus=2,
                total_memory_mb=2048, available_memory_mb=1024, used_memory_mb=1024,
                total_disk_gb=100, available_disk_gb=90, used_disk_gb=10,
                active_vms=1, cpu_usage_percent=50, memory_usage_percent=50,
                disk_usage_percent=10, load_average=[1.0, 1.1, 1.2],
                timestamp=datetime.now()
            )
            
            success = await resource_manager.resize_vm_resources(
                vm_name="test-vm",
                new_vcpus=8,  # More than available
                new_memory_mb=4096  # More than available
            )
            
            assert success is False
            # Original allocation should remain unchanged
            allocation = resource_manager.allocations["test-vm"]
            assert allocation.vcpus == 2
            assert allocation.memory_mb == 1024
    
    async def test_resize_vm_resources_not_found(self, resource_manager):
        """Test resize failure for non-existent VM."""
        success = await resource_manager.resize_vm_resources(
            vm_name="non-existent-vm",
            new_vcpus=4
        )
        
        assert success is False
    
    async def test_get_resource_recommendations(self, resource_manager, sample_allocation):
        """Test resource optimization recommendations."""
        # Add allocation with high usage
        high_usage_allocation = ResourceAllocation(
            vm_name="high-usage-vm",
            vcpus=2,
            memory_mb=1024,
            disk_gb=10,
            allocated_at=datetime.now(),
            last_updated=datetime.now(),
            priority=1,
            cpu_usage_percent=95.0,  # Over-utilized
            memory_usage_percent=90.0  # Over-utilized
        )
        
        # Add allocation with low usage
        low_usage_allocation = ResourceAllocation(
            vm_name="low-usage-vm",
            vcpus=4,
            memory_mb=2048,
            disk_gb=20,
            allocated_at=datetime.now(),
            last_updated=datetime.now(),
            priority=1,
            cpu_usage_percent=5.0,  # Under-utilized
            memory_usage_percent=10.0  # Under-utilized
        )
        
        resource_manager.allocations["high-usage-vm"] = high_usage_allocation
        resource_manager.allocations["low-usage-vm"] = low_usage_allocation
        
        with patch.object(resource_manager, 'get_system_resources') as mock_get_system:
            mock_get_system.return_value = SystemResourceUsage(
                total_vcpus=8, available_vcpus=2, used_vcpus=6,
                total_memory_mb=8192, available_memory_mb=5120, used_memory_mb=3072,
                total_disk_gb=500, available_disk_gb=470, used_disk_gb=30,
                active_vms=2, cpu_usage_percent=75, memory_usage_percent=37.5,
                disk_usage_percent=6, load_average=[2.0, 2.1, 2.2],
                timestamp=datetime.now()
            )
            
            recommendations = await resource_manager.get_resource_recommendations()
            
            assert len(recommendations) >= 1
            
            # Check for scale-up recommendation for high usage VM
            high_usage_rec = next((r for r in recommendations if r.vm_name == "high-usage-vm"), None)
            if high_usage_rec:
                assert high_usage_rec.urgency in ["critical", "high"]
                assert high_usage_rec.recommended_vcpus >= high_usage_allocation.vcpus or \
                       high_usage_rec.recommended_memory_mb >= high_usage_allocation.memory_mb
            
            # Check for scale-down recommendation for low usage VM
            low_usage_rec = next((r for r in recommendations if r.vm_name == "low-usage-vm"), None)
            if low_usage_rec:
                assert low_usage_rec.estimated_savings_percent > 0
    
    async def test_auto_scale_resources(self, resource_manager):
        """Test automatic resource scaling."""
        # Create a VM that needs scaling
        critical_allocation = ResourceAllocation(
            vm_name="critical-vm",
            vcpus=2,
            memory_mb=1024,
            disk_gb=10,
            allocated_at=datetime.now(),
            last_updated=datetime.now(),
            priority=1,
            cpu_usage_percent=95.0,
            memory_usage_percent=90.0
        )
        
        resource_manager.allocations["critical-vm"] = critical_allocation
        
        with patch.object(resource_manager, 'get_resource_recommendations') as mock_get_recs:
            mock_get_recs.return_value = [
                ResourceRecommendation(
                    vm_name="critical-vm",
                    recommended_vcpus=4,
                    recommended_memory_mb=2048,
                    current_vcpus=2,
                    current_memory_mb=1024,
                    reason="VM overutilized",
                    urgency="critical",
                    estimated_savings_percent=0.0
                )
            ]
            
            with patch.object(resource_manager, 'resize_vm_resources') as mock_resize:
                mock_resize.return_value = True
                
                scaled_vms = await resource_manager.auto_scale_resources()
                
                assert "critical-vm" in scaled_vms
                mock_resize.assert_called_once_with("critical-vm", 4, 2048)
    
    async def test_quota_management(self, resource_manager, sample_quota):
        """Test quota set and get operations."""
        # Set quota
        success = await resource_manager.set_quota("test-user", sample_quota)
        assert success is True
        
        # Get quota
        retrieved_quota = await resource_manager.get_quota("test-user")
        assert retrieved_quota.max_vcpus == sample_quota.max_vcpus
        assert retrieved_quota.max_memory_mb == sample_quota.max_memory_mb
        assert retrieved_quota.max_disk_gb == sample_quota.max_disk_gb
        assert retrieved_quota.max_vms == sample_quota.max_vms
        assert retrieved_quota.priority == sample_quota.priority
        
        # Get default quota for non-existent user
        default_quota = await resource_manager.get_quota("non-existent-user")
        assert default_quota == resource_manager.default_quota
    
    async def test_list_allocations(self, resource_manager, sample_allocation):
        """Test listing all allocations."""
        resource_manager.allocations["test-vm"] = sample_allocation
        resource_manager.allocations["test-vm-2"] = ResourceAllocation(
            vm_name="test-vm-2",
            vcpus=4,
            memory_mb=2048,
            disk_gb=20,
            allocated_at=datetime.now(),
            last_updated=datetime.now(),
            priority=2
        )
        
        allocations = await resource_manager.list_allocations()
        
        assert len(allocations) == 2
        vm_names = [alloc.vm_name for alloc in allocations]
        assert "test-vm" in vm_names
        assert "test-vm-2" in vm_names
    
    async def test_get_allocation(self, resource_manager, sample_allocation):
        """Test getting specific allocation."""
        resource_manager.allocations["test-vm"] = sample_allocation
        
        allocation = await resource_manager.get_allocation("test-vm")
        assert allocation is not None
        assert allocation.vm_name == "test-vm"
        assert allocation.vcpus == 2
        
        non_existent = await resource_manager.get_allocation("non-existent-vm")
        assert non_existent is None
    
    async def test_export_metrics(self, resource_manager, sample_allocation, sample_quota):
        """Test exporting resource metrics."""
        resource_manager.allocations["test-vm"] = sample_allocation
        resource_manager.quotas["test-user"] = sample_quota
        
        with patch.object(resource_manager, 'get_system_resources') as mock_get_system:
            mock_get_system.return_value = SystemResourceUsage(
                total_vcpus=8, available_vcpus=6, used_vcpus=2,
                total_memory_mb=8192, available_memory_mb=7168, used_memory_mb=1024,
                total_disk_gb=500, available_disk_gb=490, used_disk_gb=10,
                active_vms=1, cpu_usage_percent=25, memory_usage_percent=12.5,
                disk_usage_percent=2, load_average=[0.5, 0.6, 0.7],
                timestamp=datetime.now()
            )
            
            metrics = await resource_manager.export_metrics()
            
            assert "system_usage" in metrics
            assert "allocations" in metrics
            assert "quotas" in metrics
            assert "optimization_enabled" in metrics
            assert "scaling_enabled" in metrics
            assert "monitoring_enabled" in metrics
            
            assert len(metrics["allocations"]) == 1
            assert len(metrics["quotas"]) == 1
            assert metrics["optimization_enabled"] is True
            assert metrics["scaling_enabled"] is True
            assert metrics["monitoring_enabled"] is True
    
    def test_validation_methods(self, resource_manager, sample_quota):
        """Test internal validation methods."""
        # Test quota validation
        assert resource_manager._validate_against_quota(2, 1024, 10, sample_quota) is True
        assert resource_manager._validate_against_quota(8, 1024, 10, sample_quota) is False  # vcpus exceed quota
        assert resource_manager._validate_against_quota(2, 4096, 10, sample_quota) is False  # memory exceeds quota
        
        # Test system limits validation
        assert resource_manager._validate_against_system_limits(4, 2048, 50) is True
        assert resource_manager._validate_against_system_limits(16, 2048, 50) is False  # vcpus exceed system limits
        assert resource_manager._validate_against_system_limits(4, 16384, 50) is False  # memory exceeds system limits
        
        # Test resource availability
        system_usage = SystemResourceUsage(
            total_vcpus=8, available_vcpus=4, used_vcpus=4,
            total_memory_mb=8192, available_memory_mb=4096, used_memory_mb=4096,
            total_disk_gb=500, available_disk_gb=300, used_disk_gb=200,
            active_vms=2, cpu_usage_percent=50, memory_usage_percent=50,
            disk_usage_percent=40, load_average=[1.0, 1.1, 1.2],
            timestamp=datetime.now()
        )
        
        assert resource_manager._check_resource_availability(system_usage, 2, 2048, 50) is True
        assert resource_manager._check_resource_availability(system_usage, 8, 2048, 50) is False  # vcpus not available
        assert resource_manager._check_resource_availability(system_usage, 2, 8192, 50) is False  # memory not available
    
    def test_enable_disable_features(self, resource_manager):
        """Test enabling and disabling optimization and scaling features."""
        # Initially enabled
        assert resource_manager.optimization_enabled is True
        assert resource_manager.scaling_enabled is True
        
        # Disable features
        resource_manager.optimization_enabled = False
        resource_manager.scaling_enabled = False
        
        assert resource_manager.optimization_enabled is False
        assert resource_manager.scaling_enabled is False
        
        # Re-enable features
        resource_manager.optimization_enabled = True
        resource_manager.scaling_enabled = True
        
        assert resource_manager.optimization_enabled is True
        assert resource_manager.scaling_enabled is True


class TestResourceQuota:
    """Test cases for ResourceQuota dataclass."""
    
    def test_resource_quota_creation(self):
        """Test ResourceQuota creation and attributes."""
        quota = ResourceQuota(
            max_vcpus=4,
            max_memory_mb=2048,
            max_disk_gb=20,
            max_vms=5,
            priority=2
        )
        
        assert quota.max_vcpus == 4
        assert quota.max_memory_mb == 2048
        assert quota.max_disk_gb == 20
        assert quota.max_vms == 5
        assert quota.priority == 2


class TestResourceAllocation:
    """Test cases for ResourceAllocation dataclass."""
    
    def test_resource_allocation_creation(self):
        """Test ResourceAllocation creation and attributes."""
        now = datetime.now()
        allocation = ResourceAllocation(
            vm_name="test-vm",
            vcpus=2,
            memory_mb=1024,
            disk_gb=10,
            allocated_at=now,
            last_updated=now,
            priority=1,
            cpu_usage_percent=50.0,
            memory_usage_percent=60.0
        )
        
        assert allocation.vm_name == "test-vm"
        assert allocation.vcpus == 2
        assert allocation.memory_mb == 1024
        assert allocation.disk_gb == 10
        assert allocation.allocated_at == now
        assert allocation.last_updated == now
        assert allocation.priority == 1
        assert allocation.cpu_usage_percent == 50.0
        assert allocation.memory_usage_percent == 60.0


class TestSystemResourceUsage:
    """Test cases for SystemResourceUsage dataclass."""
    
    def test_system_resource_usage_creation(self):
        """Test SystemResourceUsage creation and attributes."""
        now = datetime.now()
        usage = SystemResourceUsage(
            total_vcpus=8,
            available_vcpus=4,
            used_vcpus=4,
            total_memory_mb=8192,
            available_memory_mb=4096,
            used_memory_mb=4096,
            total_disk_gb=500,
            available_disk_gb=300,
            used_disk_gb=200,
            active_vms=2,
            cpu_usage_percent=50.0,
            memory_usage_percent=50.0,
            disk_usage_percent=40.0,
            load_average=[1.0, 1.2, 1.1],
            timestamp=now
        )
        
        assert usage.total_vcpus == 8
        assert usage.available_vcpus == 4
        assert usage.used_vcpus == 4
        assert usage.total_memory_mb == 8192
        assert usage.available_memory_mb == 4096
        assert usage.used_memory_mb == 4096
        assert usage.active_vms == 2
        assert usage.cpu_usage_percent == 50.0
        assert usage.memory_usage_percent == 50.0
        assert usage.disk_usage_percent == 40.0
        assert usage.load_average == [1.0, 1.2, 1.1]
        assert usage.timestamp == now