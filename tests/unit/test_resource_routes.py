"""
Unit tests for Resource Management API routes.

Tests cover:
- Resource allocation and deallocation endpoints
- Resource quota management endpoints
- System resource monitoring endpoints
- Resource optimization and scaling endpoints
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.routes.resources import router, get_resource_manager
from src.core.resource_manager import (
    ResourceManager,
    ResourceQuota,
    ResourceAllocation,
    SystemResourceUsage,
    ResourceRecommendation
)


@pytest.fixture
def app():
    """Create FastAPI app for testing."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_resource_manager():
    """Mock resource manager for testing."""
    mock_rm = AsyncMock(spec=ResourceManager)
    return mock_rm


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
def sample_quota():
    """Sample resource quota for testing."""
    return ResourceQuota(
        max_vcpus=4,
        max_memory_mb=2048,
        max_disk_gb=20,
        max_vms=5,
        priority=1
    )


class TestSystemUsageEndpoint:
    """Test system resource usage endpoint."""
    
    def test_get_system_usage_success(self, app, client, mock_resource_manager, sample_system_usage):
        """Test successful system usage retrieval."""
        mock_resource_manager.get_system_resources.return_value = sample_system_usage
        
        # Override dependency
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.get("/api/v1/resources/system/usage")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_vcpus"] == 8
        assert data["available_vcpus"] == 4
        assert data["used_vcpus"] == 4
        assert data["total_memory_mb"] == 8192
        assert data["cpu_usage_percent"] == 50.0
        assert data["load_average"] == [1.0, 1.2, 1.1]
        
        mock_resource_manager.get_system_resources.assert_called_once()
    
    def test_get_system_usage_error(self, app, client, mock_resource_manager):
        """Test system usage retrieval error."""
        mock_resource_manager.get_system_resources.side_effect = Exception("System error")
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.get("/api/v1/resources/system/usage")
        
        assert response.status_code == 500
        assert "Failed to get system usage" in response.json()["detail"]


class TestResourceAllocationEndpoints:
    """Test resource allocation endpoints."""
    
    def test_allocate_resources_success(self, app, client, mock_resource_manager, sample_allocation, sample_quota):
        """Test successful resource allocation."""
        mock_resource_manager.get_quota.return_value = sample_quota
        mock_resource_manager.allocate_resources.return_value = True
        mock_resource_manager.get_allocation.return_value = sample_allocation
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        request_data = {
            "vcpus": 2,
            "memory_mb": 1024,
            "disk_gb": 10,
            "priority": 1
        }
        
        response = client.post("/api/v1/resources/allocate/test-vm", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["vm_name"] == "test-vm"
        assert data["vcpus"] == 2
        assert data["memory_mb"] == 1024
        assert data["disk_gb"] == 10
        
        mock_resource_manager.allocate_resources.assert_called_once()
        mock_resource_manager.get_allocation.assert_called_once_with("test-vm")
    
    def test_allocate_resources_failure(self, app, client, mock_resource_manager, sample_quota):
        """Test resource allocation failure."""
        mock_resource_manager.get_quota.return_value = sample_quota
        mock_resource_manager.allocate_resources.return_value = False
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        request_data = {
            "vcpus": 8,
            "memory_mb": 4096,
            "disk_gb": 50,
            "priority": 1
        }
        
        response = client.post("/api/v1/resources/allocate/test-vm", json=request_data)
        
        assert response.status_code == 400
        assert "insufficient resources" in response.json()["detail"]
    
    def test_allocate_resources_with_user_quota(self, app, client, mock_resource_manager, sample_allocation, sample_quota):
        """Test resource allocation with user quota."""
        mock_resource_manager.get_quota.return_value = sample_quota
        mock_resource_manager.allocate_resources.return_value = True
        mock_resource_manager.get_allocation.return_value = sample_allocation
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        request_data = {
            "vcpus": 2,
            "memory_mb": 1024,
            "disk_gb": 10,
            "priority": 1
        }
        
        response = client.post("/api/v1/resources/allocate/test-vm?user_id=test-user", json=request_data)
        
        assert response.status_code == 200
        mock_resource_manager.get_quota.assert_called_once_with("test-user")
    
    def test_deallocate_resources_success(self, app, client, mock_resource_manager):
        """Test successful resource deallocation."""
        mock_resource_manager.deallocate_resources.return_value = True
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.delete("/api/v1/resources/deallocate/test-vm")
        
        assert response.status_code == 200
        assert "Resources deallocated" in response.json()["message"]
        mock_resource_manager.deallocate_resources.assert_called_once_with("test-vm")
    
    def test_deallocate_resources_not_found(self, app, client, mock_resource_manager):
        """Test deallocation for non-existent VM."""
        mock_resource_manager.deallocate_resources.return_value = False
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.delete("/api/v1/resources/deallocate/non-existent-vm")
        
        assert response.status_code == 404
        assert "No resource allocation found" in response.json()["detail"]
    
    def test_list_allocations(self, app, client, mock_resource_manager, sample_allocation):
        """Test listing all allocations."""
        mock_resource_manager.list_allocations.return_value = [sample_allocation]
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.get("/api/v1/resources/allocations")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["vm_name"] == "test-vm"
        assert data[0]["vcpus"] == 2
    
    def test_get_allocation_success(self, app, client, mock_resource_manager, sample_allocation):
        """Test getting specific allocation."""
        mock_resource_manager.get_allocation.return_value = sample_allocation
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.get("/api/v1/resources/allocations/test-vm")
        
        assert response.status_code == 200
        data = response.json()
        assert data["vm_name"] == "test-vm"
        assert data["vcpus"] == 2
        assert data["memory_mb"] == 1024
    
    def test_get_allocation_not_found(self, app, client, mock_resource_manager):
        """Test getting non-existent allocation."""
        mock_resource_manager.get_allocation.return_value = None
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.get("/api/v1/resources/allocations/non-existent-vm")
        
        assert response.status_code == 404
        assert "No resource allocation found" in response.json()["detail"]


class TestUsageUpdateEndpoint:
    """Test VM usage update endpoint."""
    
    def test_update_vm_usage_success(self, app, client, mock_resource_manager):
        """Test successful usage update."""
        mock_resource_manager.update_vm_usage.return_value = True
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        request_data = {
            "cpu_usage_percent": 75.0,
            "memory_usage_percent": 80.0
        }
        
        response = client.put("/api/v1/resources/allocations/test-vm/usage", json=request_data)
        
        assert response.status_code == 200
        assert "Usage updated" in response.json()["message"]
        mock_resource_manager.update_vm_usage.assert_called_once_with(
            vm_name="test-vm",
            cpu_usage_percent=75.0,
            memory_usage_percent=80.0
        )
    
    def test_update_vm_usage_not_found(self, app, client, mock_resource_manager):
        """Test usage update for non-existent VM."""
        mock_resource_manager.update_vm_usage.return_value = False
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        request_data = {
            "cpu_usage_percent": 75.0,
            "memory_usage_percent": 80.0
        }
        
        response = client.put("/api/v1/resources/allocations/non-existent-vm/usage", json=request_data)
        
        assert response.status_code == 404
        assert "No resource allocation found" in response.json()["detail"]


class TestResourceResizeEndpoint:
    """Test VM resource resize endpoint."""
    
    def test_resize_vm_resources_success(self, app, client, mock_resource_manager, sample_allocation):
        """Test successful resource resize."""
        mock_resource_manager.resize_vm_resources.return_value = True
        
        # Create updated allocation with new values
        updated_allocation = ResourceAllocation(
            vm_name="test-vm",
            vcpus=4,
            memory_mb=2048,
            disk_gb=10,
            allocated_at=sample_allocation.allocated_at,
            last_updated=datetime.now(),
            priority=1,
            cpu_usage_percent=50.0,
            memory_usage_percent=60.0
        )
        mock_resource_manager.get_allocation.return_value = updated_allocation
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        request_data = {
            "new_vcpus": 4,
            "new_memory_mb": 2048
        }
        
        response = client.put("/api/v1/resources/allocations/test-vm/resize", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["vm_name"] == "test-vm"
        assert data["vcpus"] == 4
        assert data["memory_mb"] == 2048
        
        mock_resource_manager.resize_vm_resources.assert_called_once_with(
            vm_name="test-vm",
            new_vcpus=4,
            new_memory_mb=2048
        )
    
    def test_resize_vm_resources_failure(self, app, client, mock_resource_manager):
        """Test resource resize failure."""
        mock_resource_manager.resize_vm_resources.return_value = False
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        request_data = {
            "new_vcpus": 8,
            "new_memory_mb": 4096
        }
        
        response = client.put("/api/v1/resources/allocations/test-vm/resize", json=request_data)
        
        assert response.status_code == 400
        assert "Failed to resize VM resources" in response.json()["detail"]


class TestQuotaEndpoints:
    """Test quota management endpoints."""
    
    def test_set_user_quota_success(self, app, client, mock_resource_manager):
        """Test successful quota setting."""
        mock_resource_manager.set_quota.return_value = True
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        request_data = {
            "max_vcpus": 4,
            "max_memory_mb": 2048,
            "max_disk_gb": 20,
            "max_vms": 5,
            "priority": 1
        }
        
        response = client.post("/api/v1/resources/quotas/test-user", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["max_vcpus"] == 4
        assert data["max_memory_mb"] == 2048
        assert data["max_disk_gb"] == 20
        assert data["max_vms"] == 5
        assert data["priority"] == 1
        
        mock_resource_manager.set_quota.assert_called_once()
    
    def test_set_user_quota_failure(self, app, client, mock_resource_manager):
        """Test quota setting failure."""
        mock_resource_manager.set_quota.return_value = False
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        request_data = {
            "max_vcpus": 4,
            "max_memory_mb": 2048,
            "max_disk_gb": 20,
            "max_vms": 5,
            "priority": 1
        }
        
        response = client.post("/api/v1/resources/quotas/test-user", json=request_data)
        
        assert response.status_code == 500
        assert "Failed to set quota" in response.json()["detail"]
    
    def test_get_user_quota(self, app, client, mock_resource_manager, sample_quota):
        """Test getting user quota."""
        mock_resource_manager.get_quota.return_value = sample_quota
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.get("/api/v1/resources/quotas/test-user")
        
        assert response.status_code == 200
        data = response.json()
        assert data["max_vcpus"] == 4
        assert data["max_memory_mb"] == 2048
        assert data["max_disk_gb"] == 20
        assert data["max_vms"] == 5
        assert data["priority"] == 1
        
        mock_resource_manager.get_quota.assert_called_once_with("test-user")


class TestOptimizationEndpoints:
    """Test optimization and scaling endpoints."""
    
    def test_get_resource_recommendations(self, app, client, mock_resource_manager):
        """Test getting resource recommendations."""
        recommendations = [
            ResourceRecommendation(
                vm_name="test-vm",
                recommended_vcpus=4,
                recommended_memory_mb=2048,
                current_vcpus=2,
                current_memory_mb=1024,
                reason="VM overutilized",
                urgency="high",
                estimated_savings_percent=0.0
            )
        ]
        mock_resource_manager.get_resource_recommendations.return_value = recommendations
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.get("/api/v1/resources/recommendations")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["vm_name"] == "test-vm"
        assert data["recommendations"][0]["urgency"] == "high"
        assert "generated_at" in data
    
    def test_auto_scale_resources(self, app, client, mock_resource_manager):
        """Test automatic resource scaling."""
        mock_resource_manager.auto_scale_resources.return_value = ["test-vm-1", "test-vm-2"]
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.post("/api/v1/resources/auto-scale")
        
        assert response.status_code == 200
        data = response.json()
        assert data["scaled_vms"] == ["test-vm-1", "test-vm-2"]
        assert data["total_scaled"] == 2
        assert "timestamp" in data
        
        mock_resource_manager.auto_scale_resources.assert_called_once()


class TestMetricsEndpoint:
    """Test metrics endpoint."""
    
    def test_get_resource_metrics(self, app, client, mock_resource_manager, sample_allocation, sample_quota):
        """Test getting resource metrics."""
        metrics_data = {
            "system_usage": {
                "total_vcpus": 8,
                "used_vcpus": 4,
                "total_memory_mb": 8192,
                "used_memory_mb": 4096,
                "total_disk_gb": 500,
                "used_disk_gb": 200,
                "active_vms": 2,
                "cpu_usage_percent": 50.0,
                "memory_usage_percent": 50.0,
                "disk_usage_percent": 40.0,
                "load_average": [1.0, 1.2, 1.1]
            },
            "allocations": [
                {
                    "vm_name": "test-vm",
                    "vcpus": 2,
                    "memory_mb": 1024,
                    "disk_gb": 10,
                    "priority": 1,
                    "cpu_usage_percent": 50.0,
                    "memory_usage_percent": 60.0,
                    "allocated_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat()
                }
            ],
            "quotas": {
                "test-user": {
                    "max_vcpus": 4,
                    "max_memory_mb": 2048,
                    "max_disk_gb": 20,
                    "max_vms": 5,
                    "priority": 1
                }
            },
            "optimization_enabled": True,
            "scaling_enabled": True,
            "monitoring_enabled": True
        }
        
        mock_resource_manager.export_metrics.return_value = metrics_data
        
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.get("/api/v1/resources/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert data["system_usage"]["total_vcpus"] == 8
        assert len(data["allocations"]) == 1
        assert len(data["quotas"]) == 1
        assert data["optimization_enabled"] is True
        assert data["scaling_enabled"] is True
        assert data["monitoring_enabled"] is True


class TestControlEndpoints:
    """Test optimization and scaling control endpoints."""
    
    def test_enable_optimization(self, app, client, mock_resource_manager):
        """Test enabling optimization."""
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.post("/api/v1/resources/optimization/enable")
        
        assert response.status_code == 200
        assert "optimization enabled" in response.json()["message"]
        assert mock_resource_manager.optimization_enabled is True
    
    def test_disable_optimization(self, app, client, mock_resource_manager):
        """Test disabling optimization."""
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.post("/api/v1/resources/optimization/disable")
        
        assert response.status_code == 200
        assert "optimization disabled" in response.json()["message"]
        assert mock_resource_manager.optimization_enabled is False
    
    def test_enable_scaling(self, app, client, mock_resource_manager):
        """Test enabling scaling."""
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.post("/api/v1/resources/scaling/enable")
        
        assert response.status_code == 200
        assert "scaling enabled" in response.json()["message"]
        assert mock_resource_manager.scaling_enabled is True
    
    def test_disable_scaling(self, app, client, mock_resource_manager):
        """Test disabling scaling."""
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        response = client.post("/api/v1/resources/scaling/disable")
        
        assert response.status_code == 200
        assert "scaling disabled" in response.json()["message"]
        assert mock_resource_manager.scaling_enabled is False


class TestInputValidation:
    """Test input validation for API endpoints."""
    
    def test_allocate_resources_invalid_input(self, app, client, mock_resource_manager):
        """Test allocation with invalid input."""
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        # Test negative values
        request_data = {
            "vcpus": -1,
            "memory_mb": -512,
            "disk_gb": -10
        }
        
        response = client.post("/api/v1/resources/allocate/test-vm", json=request_data)
        assert response.status_code == 422  # Validation error
        
        # Test excessive values
        request_data = {
            "vcpus": 100,
            "memory_mb": 100000,
            "disk_gb": 10000
        }
        
        response = client.post("/api/v1/resources/allocate/test-vm", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_usage_update_invalid_input(self, app, client, mock_resource_manager):
        """Test usage update with invalid input."""
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        # Test negative percentage
        request_data = {
            "cpu_usage_percent": -10.0,
            "memory_usage_percent": 50.0
        }
        
        response = client.put("/api/v1/resources/allocations/test-vm/usage", json=request_data)
        assert response.status_code == 422  # Validation error
        
        # Test percentage over 100
        request_data = {
            "cpu_usage_percent": 150.0,
            "memory_usage_percent": 200.0
        }
        
        response = client.put("/api/v1/resources/allocations/test-vm/usage", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_quota_request_invalid_input(self, app, client, mock_resource_manager):
        """Test quota setting with invalid input."""
        app.dependency_overrides[get_resource_manager] = lambda: mock_resource_manager
        
        # Test zero/negative values
        request_data = {
            "max_vcpus": 0,
            "max_memory_mb": -1024,
            "max_disk_gb": 0,
            "max_vms": -5
        }
        
        response = client.post("/api/v1/resources/quotas/test-user", json=request_data)
        assert response.status_code == 422  # Validation error
        
        # Test excessive values
        request_data = {
            "max_vcpus": 100,
            "max_memory_mb": 100000,
            "max_disk_gb": 10000,
            "max_vms": 1000
        }
        
        response = client.post("/api/v1/resources/quotas/test-user", json=request_data)
        assert response.status_code == 422  # Validation error