import pytest
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch, call
import json

from src.core.snapshot_manager import SnapshotManager
from src.api.models.vm import SnapshotInfo


@pytest.fixture
def mock_ch_client():
    """Mock Cloud Hypervisor client."""
    client = AsyncMock()
    client.snapshot_vm = AsyncMock(return_value={"status": "success"})
    client.restore_vm = AsyncMock(return_value={"status": "success"})
    return client


@pytest.fixture
def temp_snapshots_dir():
    """Create temporary directory for snapshots."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def snapshot_manager(temp_snapshots_dir):
    """Create SnapshotManager with temporary directory."""
    manager = SnapshotManager()
    manager.snapshots_dir = temp_snapshots_dir / "snapshots"
    manager.snapshots_dir.mkdir(parents=True, exist_ok=True)
    return manager


@pytest.mark.asyncio
class TestSnapshotManager:
    async def test_create_snapshot_success(self, snapshot_manager, mock_ch_client):
        """Test successful snapshot creation."""
        vm_name = "test-vm"
        snapshot_name = "test-snapshot"
        description = "Test snapshot"
        
        # Create a mock snapshot file
        snapshot_dir = snapshot_manager.snapshots_dir / vm_name / snapshot_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_file = snapshot_dir / "snapshot.bin"
        snapshot_file.write_bytes(b"fake snapshot data")
        
        with patch('src.core.snapshot_manager.CloudHypervisorClient', return_value=mock_ch_client):
            result = await snapshot_manager.create_snapshot(vm_name, snapshot_name, description)
        
        # Verify the result
        assert result.name == snapshot_name
        assert result.vm_name == vm_name
        assert result.description == description
        assert result.size_bytes > 0
        
        # Verify Cloud Hypervisor API was called
        mock_ch_client.snapshot_vm.assert_called_once()
        
        # Verify metadata file was created
        metadata_file = snapshot_dir / "metadata.json"
        assert metadata_file.exists()
        
        with open(metadata_file) as f:
            metadata = json.load(f)
            assert metadata["name"] == snapshot_name
            assert metadata["vm_name"] == vm_name
            assert "checksum" in metadata
            assert metadata["incremental"] is False

    async def test_create_incremental_snapshot(self, snapshot_manager, mock_ch_client):
        """Test incremental snapshot creation."""
        vm_name = "test-vm"
        snapshot_name = "incremental-snapshot"
        parent_snapshot = "base-snapshot"
        
        # Create a mock snapshot file
        snapshot_dir = snapshot_manager.snapshots_dir / vm_name / snapshot_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_file = snapshot_dir / "snapshot.bin"
        snapshot_file.write_bytes(b"incremental snapshot data")
        
        with patch('src.core.snapshot_manager.CloudHypervisorClient', return_value=mock_ch_client):
            result = await snapshot_manager.create_snapshot(
                vm_name, snapshot_name, incremental=True, parent_snapshot=parent_snapshot
            )
        
        # Verify metadata includes incremental information
        metadata_file = snapshot_dir / "metadata.json"
        with open(metadata_file) as f:
            metadata = json.load(f)
            assert metadata["incremental"] is True
            assert metadata["parent_snapshot"] == parent_snapshot

    async def test_create_snapshot_ch_failure(self, snapshot_manager, mock_ch_client):
        """Test snapshot creation when Cloud Hypervisor fails."""
        vm_name = "test-vm"
        snapshot_name = "failing-snapshot"
        
        # Make Cloud Hypervisor fail
        mock_ch_client.snapshot_vm.side_effect = Exception("CH API error")
        
        with patch('src.core.snapshot_manager.CloudHypervisorClient', return_value=mock_ch_client):
            with pytest.raises(Exception, match="CH API error"):
                await snapshot_manager.create_snapshot(vm_name, snapshot_name)
        
        # Verify cleanup happened - directory should not exist
        snapshot_dir = snapshot_manager.snapshots_dir / vm_name / snapshot_name
        assert not snapshot_dir.exists()

    async def test_list_snapshots(self, snapshot_manager):
        """Test listing snapshots for a VM."""
        vm_name = "test-vm"
        
        # Create multiple snapshot directories with metadata
        snapshot_names = ["snapshot1", "snapshot2", "snapshot3"]
        created_times = []
        
        for i, snapshot_name in enumerate(snapshot_names):
            snapshot_dir = snapshot_manager.snapshots_dir / vm_name / snapshot_name
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            
            # Create metadata with different creation times
            created_at = datetime.now() - timedelta(hours=i)
            created_times.append(created_at)
            
            metadata = {
                "name": snapshot_name,
                "vm_name": vm_name,
                "description": f"Test snapshot {i+1}",
                "created_at": created_at.isoformat(),
                "size_bytes": 1000 + i * 100
            }
            
            metadata_file = snapshot_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f)
        
        # List snapshots
        snapshots = await snapshot_manager.list_snapshots(vm_name)
        
        # Verify results (should be sorted by creation time, newest first)
        assert len(snapshots) == 3
        assert snapshots[0].name == "snapshot1"  # Most recent
        assert snapshots[1].name == "snapshot2"
        assert snapshots[2].name == "snapshot3"  # Oldest

    async def test_list_snapshots_no_vm(self, snapshot_manager):
        """Test listing snapshots for non-existent VM."""
        snapshots = await snapshot_manager.list_snapshots("non-existent-vm")
        assert snapshots == []

    async def test_restore_snapshot_success(self, snapshot_manager, mock_ch_client):
        """Test successful snapshot restoration."""
        vm_name = "test-vm"
        snapshot_name = "test-snapshot"
        
        # Create snapshot directory and file
        snapshot_dir = snapshot_manager.snapshots_dir / vm_name / snapshot_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_file = snapshot_dir / "snapshot.bin"
        snapshot_file.write_bytes(b"snapshot data")
        
        with patch('src.core.snapshot_manager.CloudHypervisorClient', return_value=mock_ch_client):
            await snapshot_manager.restore_snapshot(vm_name, snapshot_name)
        
        # Verify Cloud Hypervisor API was called
        mock_ch_client.restore_vm.assert_called_once_with(str(snapshot_file))

    async def test_restore_snapshot_not_found(self, snapshot_manager):
        """Test restoring non-existent snapshot."""
        with pytest.raises(ValueError, match="Snapshot 'non-existent' not found"):
            await snapshot_manager.restore_snapshot("test-vm", "non-existent")

    async def test_delete_snapshot_success(self, snapshot_manager):
        """Test successful snapshot deletion."""
        vm_name = "test-vm"
        snapshot_name = "test-snapshot"
        
        # Create snapshot directory
        snapshot_dir = snapshot_manager.snapshots_dir / vm_name / snapshot_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Create some files
        (snapshot_dir / "snapshot.bin").write_bytes(b"data")
        (snapshot_dir / "metadata.json").write_text("{}")
        
        # Delete snapshot
        await snapshot_manager.delete_snapshot(vm_name, snapshot_name)
        
        # Verify deletion
        assert not snapshot_dir.exists()

    async def test_delete_snapshot_not_found(self, snapshot_manager):
        """Test deleting non-existent snapshot."""
        with pytest.raises(ValueError, match="Snapshot 'non-existent' not found"):
            await snapshot_manager.delete_snapshot("test-vm", "non-existent")

    async def test_enforce_snapshot_limits(self, snapshot_manager):
        """Test snapshot limit enforcement."""
        vm_name = "test-vm"
        snapshot_manager.max_snapshots_per_vm = 3
        
        # Create 5 snapshots
        for i in range(5):
            snapshot_name = f"snapshot{i}"
            snapshot_dir = snapshot_manager.snapshots_dir / vm_name / snapshot_name
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            
            # Create metadata with different creation times
            created_at = datetime.now() - timedelta(hours=5-i)  # Oldest first
            metadata = {
                "name": snapshot_name,
                "vm_name": vm_name,
                "description": f"Test snapshot {i}",
                "created_at": created_at.isoformat(),
                "size_bytes": 1000
            }
            
            metadata_file = snapshot_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f)
        
        # Trigger limit enforcement
        await snapshot_manager._enforce_snapshot_limits(vm_name)
        
        # Should have only 2 snapshots left (max - 1, because we're creating one more)
        remaining_snapshots = await snapshot_manager.list_snapshots(vm_name)
        assert len(remaining_snapshots) == 2
        
        # Should keep the newest ones
        assert remaining_snapshots[0].name == "snapshot4"
        assert remaining_snapshots[1].name == "snapshot3"

    async def test_cleanup_old_snapshots(self, snapshot_manager):
        """Test cleanup of old snapshots."""
        # Create old and new snapshots
        vm_names = ["vm1", "vm2"]
        
        for vm_name in vm_names:
            # Old snapshot (40 days old)
            old_snapshot_dir = snapshot_manager.snapshots_dir / vm_name / "old-snapshot"
            old_snapshot_dir.mkdir(parents=True, exist_ok=True)
            old_metadata = {
                "name": "old-snapshot",
                "vm_name": vm_name,
                "description": "Old snapshot",
                "created_at": (datetime.now() - timedelta(days=40)).isoformat(),
                "size_bytes": 1000
            }
            with open(old_snapshot_dir / "metadata.json", 'w') as f:
                json.dump(old_metadata, f)
            
            # New snapshot (5 days old)
            new_snapshot_dir = snapshot_manager.snapshots_dir / vm_name / "new-snapshot"
            new_snapshot_dir.mkdir(parents=True, exist_ok=True)
            new_metadata = {
                "name": "new-snapshot",
                "vm_name": vm_name,
                "description": "New snapshot",
                "created_at": (datetime.now() - timedelta(days=5)).isoformat(),
                "size_bytes": 1000
            }
            with open(new_snapshot_dir / "metadata.json", 'w') as f:
                json.dump(new_metadata, f)
        
        # Cleanup snapshots older than 30 days
        result = await snapshot_manager.cleanup_old_snapshots(days_old=30)
        
        # Should have removed 2 old snapshots
        assert result["removed"] == 2
        assert result["errors"] == 0
        
        # Verify old snapshots are gone and new ones remain
        for vm_name in vm_names:
            remaining_snapshots = await snapshot_manager.list_snapshots(vm_name)
            assert len(remaining_snapshots) == 1
            assert remaining_snapshots[0].name == "new-snapshot"

    async def test_verify_snapshot_integrity_valid(self, snapshot_manager):
        """Test snapshot integrity verification for valid snapshot."""
        vm_name = "test-vm"
        snapshot_name = "test-snapshot"
        
        # Create snapshot with known data
        snapshot_dir = snapshot_manager.snapshots_dir / vm_name / snapshot_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        test_data = b"test snapshot data"
        snapshot_file = snapshot_dir / "snapshot.bin"
        snapshot_file.write_bytes(test_data)
        
        # Calculate checksum
        import hashlib
        expected_checksum = hashlib.sha256(test_data).hexdigest()
        
        # Create metadata with checksum
        metadata = {
            "name": snapshot_name,
            "vm_name": vm_name,
            "checksum": expected_checksum,
            "created_at": datetime.now().isoformat(),
            "size_bytes": len(test_data)
        }
        
        metadata_file = snapshot_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f)
        
        # Verify integrity
        result = await snapshot_manager.verify_snapshot_integrity(vm_name, snapshot_name)
        
        assert result["valid"] is True
        assert result["stored_checksum"] == expected_checksum
        assert result["current_checksum"] == expected_checksum
        assert result["size_bytes"] == len(test_data)

    async def test_verify_snapshot_integrity_corrupted(self, snapshot_manager):
        """Test snapshot integrity verification for corrupted snapshot."""
        vm_name = "test-vm"
        snapshot_name = "test-snapshot"
        
        # Create snapshot directory
        snapshot_dir = snapshot_manager.snapshots_dir / vm_name / snapshot_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Create snapshot file with different data than metadata
        snapshot_file = snapshot_dir / "snapshot.bin"
        snapshot_file.write_bytes(b"corrupted data")
        
        # Create metadata with different checksum
        metadata = {
            "name": snapshot_name,
            "vm_name": vm_name,
            "checksum": "different_checksum",
            "created_at": datetime.now().isoformat(),
            "size_bytes": 100
        }
        
        metadata_file = snapshot_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f)
        
        # Verify integrity
        result = await snapshot_manager.verify_snapshot_integrity(vm_name, snapshot_name)
        
        assert result["valid"] is False
        assert "Checksum mismatch" in result["error"]
        assert result["stored_checksum"] == "different_checksum"

    async def test_get_snapshot_statistics(self, snapshot_manager):
        """Test getting snapshot statistics."""
        # Create snapshots for multiple VMs
        vm_data = [
            ("vm1", ["snap1", "snap2"], [1000, 2000]),
            ("vm2", ["snap3"], [1500]),
        ]
        
        total_snapshots = 0
        total_size = 0
        
        for vm_name, snapshot_names, sizes in vm_data:
            for snapshot_name, size in zip(snapshot_names, sizes):
                snapshot_dir = snapshot_manager.snapshots_dir / vm_name / snapshot_name
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                
                created_at = datetime.now() - timedelta(hours=total_snapshots)
                metadata = {
                    "name": snapshot_name,
                    "vm_name": vm_name,
                    "description": f"Test snapshot",
                    "created_at": created_at.isoformat(),
                    "size_bytes": size
                }
                
                metadata_file = snapshot_dir / "metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f)
                
                total_snapshots += 1
                total_size += size
        
        # Get statistics
        stats = await snapshot_manager.get_snapshot_statistics()
        
        assert stats["total_snapshots"] == 3
        assert stats["total_size_bytes"] == 4500
        assert stats["vms_with_snapshots"] == 2
        assert "vm1" in stats["vms"]
        assert "vm2" in stats["vms"]
        assert stats["vms"]["vm1"]["count"] == 2
        assert stats["vms"]["vm2"]["count"] == 1

    async def test_calculate_file_checksum(self, snapshot_manager, temp_snapshots_dir):
        """Test file checksum calculation."""
        test_file = temp_snapshots_dir / "test_file.bin"
        test_data = b"test data for checksum"
        test_file.write_bytes(test_data)
        
        # Calculate checksum
        checksum = await snapshot_manager._calculate_file_checksum(test_file)
        
        # Verify against known checksum
        import hashlib
        expected_checksum = hashlib.sha256(test_data).hexdigest()
        assert checksum == expected_checksum