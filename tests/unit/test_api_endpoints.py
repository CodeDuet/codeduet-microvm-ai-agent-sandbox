import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from src.api.server import app


class TestHealthEndpoints:
    def test_root_endpoint(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "MicroVM Sandbox API"
        assert data["version"] == "0.1.0"

    def test_health_check(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "microvm-sandbox"
        assert data["version"] == "0.1.0"


class TestSystemEndpoints:
    def test_system_info(self, client: TestClient):
        response = client.get("/api/v1/system/info")
        assert response.status_code == 200
        data = response.json()
        assert "platform" in data
        assert "python_version" in data
        assert "cpu_count" in data
        assert "memory" in data
        assert "disk" in data

    def test_system_metrics(self, client: TestClient):
        response = client.get("/api/v1/system/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "cpu_percent" in data
        assert "memory_percent" in data
        assert "disk_percent" in data
        assert "boot_time" in data


class TestVMEndpoints:
    @patch('src.core.vm_manager.VMManager.create_vm')
    def test_create_vm_success(self, mock_create, client: TestClient, sample_vm_config):
        from src.api.models.vm import VMInfo, VMState
        from datetime import datetime
        
        mock_vm_info = VMInfo(
            name=sample_vm_config["name"],
            state=VMState.CREATING,
            vcpus=sample_vm_config["vcpus"],
            memory_mb=sample_vm_config["memory_mb"],
            os_type=sample_vm_config["os_type"],
            template=sample_vm_config["template"],
            guest_agent=sample_vm_config["guest_agent"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata=sample_vm_config["metadata"]
        )
        mock_create.return_value = mock_vm_info
        
        response = client.post("/api/v1/vms/", json=sample_vm_config)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_vm_config["name"]
        assert data["state"] == "creating"

    @patch('src.core.vm_manager.VMManager.list_vms')
    def test_list_vms(self, mock_list, client: TestClient):
        mock_list.return_value = []
        
        response = client.get("/api/v1/vms/")
        assert response.status_code == 200
        data = response.json()
        assert "vms" in data
        assert isinstance(data["vms"], list)

    @patch('src.core.vm_manager.VMManager.get_vm')
    def test_get_vm_not_found(self, mock_get, client: TestClient):
        mock_get.return_value = None
        
        response = client.get("/api/v1/vms/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"]

    def test_create_vm_validation_error(self, client: TestClient):
        invalid_config = {"name": ""}  # Invalid empty name
        
        response = client.post("/api/v1/vms/", json=invalid_config)
        assert response.status_code == 422  # Validation error


class TestSnapshotEndpoints:
    @patch('src.core.snapshot_manager.SnapshotManager.list_snapshots')
    def test_list_snapshots(self, mock_list, client: TestClient):
        mock_list.return_value = []
        
        response = client.get("/api/v1/snapshots/test-vm")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)