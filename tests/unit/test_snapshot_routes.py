import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from datetime import datetime

from src.api.server import app
from src.api.models.vm import SnapshotInfo


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_snapshot_manager():
    """Mock snapshot manager."""
    manager = AsyncMock()
    return manager


class TestSnapshotRoutes:
    def test_create_snapshot_success(self, client, mock_snapshot_manager):
        """Test successful snapshot creation via API."""
        vm_name = "test-vm"
        snapshot_data = {
            "name": "test-snapshot",
            "description": "Test snapshot description"
        }
        
        # Mock snapshot creation
        mock_snapshot_info = SnapshotInfo(
            name="test-snapshot",
            vm_name=vm_name,
            description="Test snapshot description",
            created_at=datetime.now(),
            size_bytes=1024
        )
        mock_snapshot_manager.create_snapshot.return_value = mock_snapshot_info
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.post(f"/api/v1/snapshots/{vm_name}", json=snapshot_data)
        
        assert response.status_code == 201
        result = response.json()
        assert result["name"] == "test-snapshot"
        assert result["vm_name"] == vm_name
        assert result["description"] == "Test snapshot description"
        
        # Verify the manager was called correctly
        mock_snapshot_manager.create_snapshot.assert_called_once_with(
            vm_name, "test-snapshot", "Test snapshot description",
            incremental=False, parent_snapshot=None
        )

    def test_create_incremental_snapshot(self, client, mock_snapshot_manager):
        """Test incremental snapshot creation via API."""
        vm_name = "test-vm"
        snapshot_data = {
            "name": "incremental-snapshot",
            "description": "Incremental snapshot"
        }
        
        mock_snapshot_info = SnapshotInfo(
            name="incremental-snapshot",
            vm_name=vm_name,
            description="Incremental snapshot",
            created_at=datetime.now(),
            size_bytes=512
        )
        mock_snapshot_manager.create_snapshot.return_value = mock_snapshot_info
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.post(
                f"/api/v1/snapshots/{vm_name}?incremental=true&parent_snapshot=base-snapshot",
                json=snapshot_data
            )
        
        assert response.status_code == 201
        
        # Verify the manager was called with incremental parameters
        mock_snapshot_manager.create_snapshot.assert_called_once_with(
            vm_name, "incremental-snapshot", "Incremental snapshot",
            incremental=True, parent_snapshot="base-snapshot"
        )

    def test_create_snapshot_failure(self, client, mock_snapshot_manager):
        """Test snapshot creation failure."""
        vm_name = "test-vm"
        snapshot_data = {
            "name": "failing-snapshot",
            "description": "This will fail"
        }
        
        # Mock failure
        mock_snapshot_manager.create_snapshot.side_effect = Exception("Creation failed")
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.post(f"/api/v1/snapshots/{vm_name}", json=snapshot_data)
        
        assert response.status_code == 500
        assert "Failed to create snapshot" in response.json()["detail"]

    def test_list_snapshots_success(self, client, mock_snapshot_manager):
        """Test listing snapshots via API."""
        vm_name = "test-vm"
        
        # Mock snapshot list
        mock_snapshots = [
            SnapshotInfo(
                name="snapshot1",
                vm_name=vm_name,
                description="First snapshot",
                created_at=datetime.now(),
                size_bytes=1024
            ),
            SnapshotInfo(
                name="snapshot2",
                vm_name=vm_name,
                description="Second snapshot",
                created_at=datetime.now(),
                size_bytes=2048
            )
        ]
        mock_snapshot_manager.list_snapshots.return_value = mock_snapshots
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.get(f"/api/v1/snapshots/{vm_name}")
        
        assert response.status_code == 200
        result = response.json()
        assert len(result) == 2
        assert result[0]["name"] == "snapshot1"
        assert result[1]["name"] == "snapshot2"
        
        mock_snapshot_manager.list_snapshots.assert_called_once_with(vm_name)

    def test_list_snapshots_failure(self, client, mock_snapshot_manager):
        """Test listing snapshots failure."""
        vm_name = "test-vm"
        
        # Mock failure
        mock_snapshot_manager.list_snapshots.side_effect = Exception("List failed")
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.get(f"/api/v1/snapshots/{vm_name}")
        
        assert response.status_code == 500
        assert "Failed to list snapshots" in response.json()["detail"]

    def test_restore_snapshot_success(self, client, mock_snapshot_manager):
        """Test snapshot restoration via API."""
        vm_name = "test-vm"
        snapshot_name = "test-snapshot"
        
        # Mock successful restore
        mock_snapshot_manager.restore_snapshot.return_value = None
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.post(f"/api/v1/snapshots/{vm_name}/{snapshot_name}/restore")
        
        assert response.status_code == 200
        result = response.json()
        assert "restored" in result["message"]
        
        mock_snapshot_manager.restore_snapshot.assert_called_once_with(vm_name, snapshot_name)

    def test_restore_snapshot_failure(self, client, mock_snapshot_manager):
        """Test snapshot restoration failure."""
        vm_name = "test-vm"
        snapshot_name = "missing-snapshot"
        
        # Mock failure
        mock_snapshot_manager.restore_snapshot.side_effect = Exception("Restore failed")
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.post(f"/api/v1/snapshots/{vm_name}/{snapshot_name}/restore")
        
        assert response.status_code == 500
        assert "Failed to restore snapshot" in response.json()["detail"]

    def test_delete_snapshot_success(self, client, mock_snapshot_manager):
        """Test snapshot deletion via API."""
        vm_name = "test-vm"
        snapshot_name = "test-snapshot"
        
        # Mock successful deletion
        mock_snapshot_manager.delete_snapshot.return_value = None
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.delete(f"/api/v1/snapshots/{vm_name}/{snapshot_name}")
        
        assert response.status_code == 200
        result = response.json()
        assert "deleted successfully" in result["message"]
        
        mock_snapshot_manager.delete_snapshot.assert_called_once_with(vm_name, snapshot_name)

    def test_delete_snapshot_failure(self, client, mock_snapshot_manager):
        """Test snapshot deletion failure."""
        vm_name = "test-vm"
        snapshot_name = "missing-snapshot"
        
        # Mock failure
        mock_snapshot_manager.delete_snapshot.side_effect = Exception("Delete failed")
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.delete(f"/api/v1/snapshots/{vm_name}/{snapshot_name}")
        
        assert response.status_code == 500
        assert "Failed to delete snapshot" in response.json()["detail"]

    def test_verify_snapshot_success(self, client, mock_snapshot_manager):
        """Test snapshot verification via API."""
        vm_name = "test-vm"
        snapshot_name = "test-snapshot"
        
        # Mock verification result
        verification_result = {
            "valid": True,
            "stored_checksum": "abc123",
            "current_checksum": "abc123",
            "size_bytes": 1024
        }
        mock_snapshot_manager.verify_snapshot_integrity.return_value = verification_result
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.post(f"/api/v1/snapshots/{vm_name}/{snapshot_name}/verify")
        
        assert response.status_code == 200
        result = response.json()
        assert result["valid"] is True
        assert result["stored_checksum"] == "abc123"
        
        mock_snapshot_manager.verify_snapshot_integrity.assert_called_once_with(vm_name, snapshot_name)

    def test_verify_snapshot_corrupted(self, client, mock_snapshot_manager):
        """Test verification of corrupted snapshot."""
        vm_name = "test-vm"
        snapshot_name = "corrupted-snapshot"
        
        # Mock verification result for corrupted snapshot
        verification_result = {
            "valid": False,
            "stored_checksum": "abc123",
            "current_checksum": "def456",
            "size_bytes": 1024,
            "error": "Checksum mismatch - snapshot may be corrupted"
        }
        mock_snapshot_manager.verify_snapshot_integrity.return_value = verification_result
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.post(f"/api/v1/snapshots/{vm_name}/{snapshot_name}/verify")
        
        assert response.status_code == 200
        result = response.json()
        assert result["valid"] is False
        assert "corrupted" in result["error"]

    def test_cleanup_old_snapshots_success(self, client, mock_snapshot_manager):
        """Test cleanup of old snapshots via API."""
        cleanup_result = {"removed": 5, "errors": 0}
        mock_snapshot_manager.cleanup_old_snapshots.return_value = cleanup_result
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.post("/api/v1/snapshots/cleanup?days_old=30")
        
        assert response.status_code == 200
        result = response.json()
        assert "cleanup completed" in result["message"]
        assert result["statistics"]["removed"] == 5
        
        mock_snapshot_manager.cleanup_old_snapshots.assert_called_once_with(30)

    def test_cleanup_old_snapshots_default_days(self, client, mock_snapshot_manager):
        """Test cleanup with default days parameter."""
        cleanup_result = {"removed": 3, "errors": 1}
        mock_snapshot_manager.cleanup_old_snapshots.return_value = cleanup_result
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.post("/api/v1/snapshots/cleanup")
        
        assert response.status_code == 200
        result = response.json()
        assert result["statistics"]["removed"] == 3
        assert result["statistics"]["errors"] == 1
        
        mock_snapshot_manager.cleanup_old_snapshots.assert_called_once_with(None)

    def test_get_snapshot_statistics_success(self, client, mock_snapshot_manager):
        """Test getting snapshot statistics via API."""
        stats = {
            "total_snapshots": 10,
            "total_size_bytes": 10240,
            "vms_with_snapshots": 3,
            "oldest_snapshot": "2023-01-01T00:00:00",
            "newest_snapshot": "2023-12-01T00:00:00",
            "vms": {
                "vm1": {"count": 5, "total_size_bytes": 5120},
                "vm2": {"count": 3, "total_size_bytes": 3072},
                "vm3": {"count": 2, "total_size_bytes": 2048}
            }
        }
        mock_snapshot_manager.get_snapshot_statistics.return_value = stats
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.get("/api/v1/snapshots/statistics")
        
        assert response.status_code == 200
        result = response.json()
        assert result["total_snapshots"] == 10
        assert result["vms_with_snapshots"] == 3
        assert len(result["vms"]) == 3
        
        mock_snapshot_manager.get_snapshot_statistics.assert_called_once()

    def test_get_snapshot_statistics_failure(self, client, mock_snapshot_manager):
        """Test statistics retrieval failure."""
        mock_snapshot_manager.get_snapshot_statistics.side_effect = Exception("Stats failed")
        
        with patch('src.api.routes.snapshots.snapshot_manager', mock_snapshot_manager):
            response = client.get("/api/v1/snapshots/statistics")
        
        assert response.status_code == 500
        assert "Failed to get snapshot statistics" in response.json()["detail"]

    def test_create_snapshot_invalid_data(self, client):
        """Test snapshot creation with invalid data."""
        vm_name = "test-vm"
        invalid_data = {
            "name": "",  # Empty name should fail validation
            "description": "Valid description"
        }
        
        response = client.post(f"/api/v1/snapshots/{vm_name}", json=invalid_data)
        
        # Should fail validation
        assert response.status_code == 422  # Unprocessable Entity