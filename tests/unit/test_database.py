"""
Unit tests for database service functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json

from src.utils.database import DatabaseService, VMInstanceState, VMSnapshot


class TestVMInstanceState:
    """Test VMInstanceState dataclass."""
    
    def test_vm_instance_state_creation(self):
        """Test creating a VM instance state."""
        vm_state = VMInstanceState(
            name="test-vm",
            os_type="linux",
            state="running",
            vcpus=2,
            memory_mb=1024,
            disk_size_gb=10,
            template_name="linux-default",
            config={"boot_args": "console=ttyS0"},
            network_config={"ip": "192.168.1.100"},
            resource_allocation={"cpu_quota": 50}
        )
        
        assert vm_state.name == "test-vm"
        assert vm_state.os_type == "linux"
        assert vm_state.state == "running"
        assert vm_state.vcpus == 2
        assert vm_state.memory_mb == 1024
        assert vm_state.disk_size_gb == 10
        assert vm_state.template_name == "linux-default"
        assert vm_state.config["boot_args"] == "console=ttyS0"
        assert vm_state.network_config["ip"] == "192.168.1.100"
        assert vm_state.resource_allocation["cpu_quota"] == 50


class TestVMSnapshot:
    """Test VMSnapshot dataclass."""
    
    def test_vm_snapshot_creation(self):
        """Test creating a VM snapshot."""
        snapshot = VMSnapshot(
            vm_name="test-vm",
            name="snapshot-1",
            description="Test snapshot",
            file_path="/app/snapshots/test-vm/snapshot-1.snap",
            file_size_bytes=1024000,
            checksum="sha256:abc123",
            parent_snapshot_name="base-snapshot",
            metadata={"type": "full", "compression": "gzip"}
        )
        
        assert snapshot.vm_name == "test-vm"
        assert snapshot.name == "snapshot-1"
        assert snapshot.description == "Test snapshot"
        assert snapshot.file_path.endswith("snapshot-1.snap")
        assert snapshot.file_size_bytes == 1024000
        assert snapshot.checksum == "sha256:abc123"
        assert snapshot.parent_snapshot_name == "base-snapshot"
        assert snapshot.metadata["type"] == "full"


class TestDatabaseService:
    """Test DatabaseService class."""
    
    @pytest.fixture
    async def db_service(self):
        """Create a DatabaseService instance for testing."""
        service = DatabaseService()
        # Mock the pool and clients
        service.postgres_pool = MagicMock()
        service.redis_client = MagicMock()
        return service
    
    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        conn = AsyncMock()
        return conn
    
    @pytest.fixture
    def sample_vm_state(self):
        """Create a sample VM state for testing."""
        return VMInstanceState(
            name="test-vm",
            os_type="linux",
            state="running",
            vcpus=2,
            memory_mb=1024,
            disk_size_gb=10,
            template_name="linux-default",
            config={"boot_args": "console=ttyS0"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            last_boot_time=datetime.now(),
            boot_time_ms=2500,
            network_config={"ip": "192.168.1.100"},
            resource_allocation={"cpu_quota": 50}
        )
    
    @pytest.fixture
    def sample_snapshot(self):
        """Create a sample snapshot for testing."""
        return VMSnapshot(
            vm_name="test-vm",
            name="snapshot-1",
            description="Test snapshot",
            file_path="/app/snapshots/test-vm/snapshot-1.snap",
            file_size_bytes=1024000,
            checksum="sha256:abc123",
            created_at=datetime.now(),
            metadata={"type": "full"}
        )
    
    @pytest.mark.asyncio
    async def test_save_vm_instance_new(self, db_service, mock_connection, sample_vm_state):
        """Test saving a new VM instance."""
        # Mock that VM doesn't exist
        mock_connection.fetchrow.return_value = None
        mock_connection.execute.return_value = None
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        db_service._invalidate_cache = AsyncMock()
        
        result = await db_service.save_vm_instance(sample_vm_state)
        
        assert result == True
        # Verify INSERT was called (not UPDATE)
        insert_call = mock_connection.execute.call_args_list[0]
        assert "INSERT INTO vm_instances" in insert_call[0][0]
        # Verify cache invalidation
        assert db_service._invalidate_cache.call_count == 2
    
    @pytest.mark.asyncio
    async def test_save_vm_instance_existing(self, db_service, mock_connection, sample_vm_state):
        """Test updating an existing VM instance."""
        # Mock that VM exists
        mock_connection.fetchrow.return_value = {"id": "uuid-123"}
        mock_connection.execute.return_value = None
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        db_service._invalidate_cache = AsyncMock()
        
        result = await db_service.save_vm_instance(sample_vm_state)
        
        assert result == True
        # Verify UPDATE was called (not INSERT)
        update_call = mock_connection.execute.call_args_list[0]
        assert "UPDATE vm_instances" in update_call[0][0]
    
    @pytest.mark.asyncio
    async def test_get_vm_instance_from_cache(self, db_service):
        """Test getting VM instance from cache."""
        cached_data = {
            "name": "test-vm",
            "os_type": "linux",
            "state": "running",
            "vcpus": 2,
            "memory_mb": 1024,
            "disk_size_gb": None,
            "template_name": None,
            "config": None,
            "created_at": None,
            "updated_at": None,
            "last_boot_time": None,
            "boot_time_ms": None,
            "network_config": None,
            "resource_allocation": None
        }
        
        db_service._get_cache = AsyncMock(return_value=json.dumps(cached_data))
        
        vm_state = await db_service.get_vm_instance("test-vm")
        
        assert vm_state is not None
        assert vm_state.name == "test-vm"
        assert vm_state.os_type == "linux"
        assert vm_state.state == "running"
        db_service._get_cache.assert_called_once_with("vm_instance:test-vm")
    
    @pytest.mark.asyncio
    async def test_get_vm_instance_from_db(self, db_service, mock_connection):
        """Test getting VM instance from database."""
        mock_row = {
            'name': 'test-vm',
            'os_type': 'linux',
            'state': 'running',
            'vcpus': 2,
            'memory_mb': 1024,
            'disk_size_gb': 10,
            'template_name': 'linux-default',
            'config': '{"boot_args": "console=ttyS0"}',
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'last_boot_time': datetime.now(),
            'boot_time_ms': 2500,
            'network_config': '{"ip": "192.168.1.100"}',
            'resource_allocation': '{"cpu_quota": 50}'
        }
        
        mock_connection.fetchrow.return_value = mock_row
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        db_service._get_cache = AsyncMock(return_value=None)  # No cache
        db_service._set_cache = AsyncMock()
        
        vm_state = await db_service.get_vm_instance("test-vm")
        
        assert vm_state is not None
        assert vm_state.name == "test-vm"
        assert vm_state.os_type == "linux"
        assert vm_state.config["boot_args"] == "console=ttyS0"
        assert vm_state.network_config["ip"] == "192.168.1.100"
        # Verify cache was set
        db_service._set_cache.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_vm_instance_not_found(self, db_service, mock_connection):
        """Test getting non-existent VM instance."""
        mock_connection.fetchrow.return_value = None
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        db_service._get_cache = AsyncMock(return_value=None)
        
        vm_state = await db_service.get_vm_instance("nonexistent-vm")
        
        assert vm_state is None
    
    @pytest.mark.asyncio
    async def test_list_vm_instances(self, db_service, mock_connection):
        """Test listing VM instances."""
        mock_rows = [
            {
                'name': 'vm1',
                'os_type': 'linux',
                'state': 'running',
                'vcpus': 2,
                'memory_mb': 1024,
                'disk_size_gb': None,
                'template_name': None,
                'config': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'last_boot_time': None,
                'boot_time_ms': None,
                'network_config': None,
                'resource_allocation': None
            },
            {
                'name': 'vm2',
                'os_type': 'windows',
                'state': 'stopped',
                'vcpus': 4,
                'memory_mb': 2048,
                'disk_size_gb': None,
                'template_name': None,
                'config': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'last_boot_time': None,
                'boot_time_ms': None,
                'network_config': None,
                'resource_allocation': None
            }
        ]
        
        mock_connection.fetch.return_value = mock_rows
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        db_service._get_cache = AsyncMock(return_value=None)
        db_service._set_cache = AsyncMock()
        
        vm_instances = await db_service.list_vm_instances()
        
        assert len(vm_instances) == 2
        assert vm_instances[0].name == "vm1"
        assert vm_instances[1].name == "vm2"
        assert vm_instances[0].os_type == "linux"
        assert vm_instances[1].os_type == "windows"
    
    @pytest.mark.asyncio
    async def test_list_vm_instances_with_filter(self, db_service, mock_connection):
        """Test listing VM instances with state filter."""
        mock_rows = [
            {
                'name': 'vm1',
                'os_type': 'linux',
                'state': 'running',
                'vcpus': 2,
                'memory_mb': 1024,
                'disk_size_gb': None,
                'template_name': None,
                'config': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'last_boot_time': None,
                'boot_time_ms': None,
                'network_config': None,
                'resource_allocation': None
            }
        ]
        
        mock_connection.fetch.return_value = mock_rows
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        db_service._get_cache = AsyncMock(return_value=None)
        db_service._set_cache = AsyncMock()
        
        vm_instances = await db_service.list_vm_instances(state_filter="running")
        
        assert len(vm_instances) == 1
        assert vm_instances[0].state == "running"
        # Verify the SQL query was called with the filter
        mock_connection.fetch.assert_called_once()
        sql_call = mock_connection.fetch.call_args[0][0]
        assert "WHERE state = $1" in sql_call
    
    @pytest.mark.asyncio
    async def test_delete_vm_instance(self, db_service, mock_connection):
        """Test deleting a VM instance."""
        mock_connection.execute.return_value = "DELETE 1"
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        db_service._invalidate_cache = AsyncMock()
        
        result = await db_service.delete_vm_instance("test-vm")
        
        assert result == True
        mock_connection.execute.assert_called_once()
        assert db_service._invalidate_cache.call_count == 2
    
    @pytest.mark.asyncio
    async def test_save_vm_snapshot(self, db_service, mock_connection, sample_snapshot):
        """Test saving a VM snapshot."""
        # Mock VM exists
        mock_connection.fetchrow.side_effect = [
            {"id": "vm-uuid-123"},  # VM lookup
            None  # Parent snapshot lookup (no parent)
        ]
        mock_connection.execute.return_value = None
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        db_service._invalidate_cache = AsyncMock()
        
        result = await db_service.save_vm_snapshot(sample_snapshot)
        
        assert result == True
        # Verify snapshot was inserted
        mock_connection.execute.assert_called_once()
        insert_call = mock_connection.execute.call_args[0][0]
        assert "INSERT INTO vm_snapshots" in insert_call
    
    @pytest.mark.asyncio
    async def test_save_vm_snapshot_with_parent(self, db_service, mock_connection):
        """Test saving a VM snapshot with parent."""
        snapshot = VMSnapshot(
            vm_name="test-vm",
            name="child-snapshot",
            parent_snapshot_name="parent-snapshot",
            file_path="/app/snapshots/test-vm/child.snap"
        )
        
        # Mock VM and parent snapshot exist
        mock_connection.fetchrow.side_effect = [
            {"id": "vm-uuid-123"},  # VM lookup
            {"id": "parent-uuid-456"}  # Parent snapshot lookup
        ]
        mock_connection.execute.return_value = None
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        db_service._invalidate_cache = AsyncMock()
        
        result = await db_service.save_vm_snapshot(snapshot)
        
        assert result == True
        # Verify both VM and parent lookups were performed
        assert mock_connection.fetchrow.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_vm_snapshots(self, db_service, mock_connection):
        """Test getting VM snapshots."""
        mock_rows = [
            {
                'name': 'snapshot-1',
                'description': 'First snapshot',
                'file_path': '/app/snapshots/test-vm/snapshot-1.snap',
                'file_size_bytes': 1024000,
                'checksum': 'sha256:abc123',
                'created_at': datetime.now(),
                'metadata': '{"type": "full"}',
                'parent_name': None
            },
            {
                'name': 'snapshot-2',
                'description': 'Second snapshot',
                'file_path': '/app/snapshots/test-vm/snapshot-2.snap',
                'file_size_bytes': 512000,
                'checksum': 'sha256:def456',
                'created_at': datetime.now(),
                'metadata': '{"type": "incremental"}',
                'parent_name': 'snapshot-1'
            }
        ]
        
        mock_connection.fetch.return_value = mock_rows
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        db_service._get_cache = AsyncMock(return_value=None)
        db_service._set_cache = AsyncMock()
        
        snapshots = await db_service.get_vm_snapshots("test-vm")
        
        assert len(snapshots) == 2
        assert snapshots[0].name == "snapshot-1"
        assert snapshots[1].name == "snapshot-2"
        assert snapshots[0].parent_snapshot_name is None
        assert snapshots[1].parent_snapshot_name == "snapshot-1"
        assert snapshots[0].metadata["type"] == "full"
        assert snapshots[1].metadata["type"] == "incremental"
    
    @pytest.mark.asyncio
    async def test_delete_vm_snapshot(self, db_service, mock_connection):
        """Test deleting a VM snapshot."""
        mock_connection.execute.return_value = "DELETE 1"
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        db_service._invalidate_cache = AsyncMock()
        
        result = await db_service.delete_vm_snapshot("test-vm", "snapshot-1")
        
        assert result == True
        mock_connection.execute.assert_called_once()
        db_service._invalidate_cache.assert_called_once_with("vm_snapshots:test-vm")
    
    @pytest.mark.asyncio
    async def test_cache_operations(self, db_service):
        """Test cache operations."""
        # Mock Redis client
        db_service.redis_client = AsyncMock()
        db_service.redis_client.get.return_value = "cached_value"
        db_service.redis_client.set.return_value = True
        db_service.redis_client.keys.return_value = ["key1", "key2"]
        db_service.redis_client.delete.return_value = 2
        
        # Test get cache
        value = await db_service._get_cache("test_key")
        assert value == "cached_value"
        db_service.redis_client.get.assert_called_once_with("test_key")
        
        # Test set cache
        result = await db_service._set_cache("test_key", "test_value", 600)
        assert result == True
        db_service.redis_client.set.assert_called_once_with("test_key", "test_value", ex=600)
        
        # Test invalidate cache
        result = await db_service._invalidate_cache("test_pattern")
        assert result == True
        db_service.redis_client.keys.assert_called_once_with("test_pattern*")
        db_service.redis_client.delete.assert_called_once_with("key1", "key2")
    
    @pytest.mark.asyncio
    async def test_cache_operations_no_redis(self, db_service):
        """Test cache operations when Redis is not available."""
        db_service.redis_client = None
        
        # Should gracefully handle missing Redis
        value = await db_service._get_cache("test_key")
        assert value is None
        
        result = await db_service._set_cache("test_key", "test_value")
        assert result == False
        
        result = await db_service._invalidate_cache("test_pattern")
        assert result == False
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, db_service, mock_connection):
        """Test getting database statistics."""
        vm_stats = {
            'total_vms': 10,
            'running_vms': 7,
            'stopped_vms': 3,
            'linux_vms': 6,
            'windows_vms': 4,
            'avg_boot_time_ms': 2500.5,
            'total_memory_mb': 20480,
            'total_vcpus': 40
        }
        
        snapshot_stats = {
            'total_snapshots': 25,
            'total_snapshot_size': 5368709120,  # 5GB
            'avg_snapshot_size': 214748364.8
        }
        
        mock_connection.fetchrow.side_effect = [vm_stats, snapshot_stats]
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        
        stats = await db_service.get_statistics()
        
        assert stats["vm_statistics"]["total_vms"] == 10
        assert stats["vm_statistics"]["running_vms"] == 7
        assert stats["snapshot_statistics"]["total_snapshots"] == 25
        assert stats["cache_enabled"] == True  # Redis client is mocked
        assert stats["database_connected"] == True  # Postgres pool is mocked
    
    @pytest.mark.asyncio
    async def test_error_handling(self, db_service, mock_connection):
        """Test error handling in database operations."""
        # Mock connection that raises an exception
        mock_connection.fetchrow.side_effect = Exception("Database error")
        
        # Mock the connection context manager
        async def mock_get_connection():
            yield mock_connection
        
        db_service.get_connection = mock_get_connection
        db_service._get_cache = AsyncMock(return_value=None)
        
        # Should handle errors gracefully
        vm_state = await db_service.get_vm_instance("test-vm")
        assert vm_state is None
        
        vm_instances = await db_service.list_vm_instances()
        assert vm_instances == []
        
        result = await db_service.save_vm_instance(VMInstanceState(
            name="test", os_type="linux", state="stopped", vcpus=1, memory_mb=512
        ))
        assert result == False