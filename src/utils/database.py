"""
Database service layer for MicroVM Sandbox.
Provides state management across instances with PostgreSQL integration.
"""

import asyncio
import logging
import os
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from dataclasses import dataclass, asdict

# Optional database imports
try:
    import asyncpg
    from asyncpg import Pool, Connection
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    # Create dummy classes for type hints
    class Pool:
        pass
    class Connection:
        pass

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    class redis:
        @staticmethod
        def from_url(*args, **kwargs):
            return None

from .config import get_config

logger = logging.getLogger(__name__)


@dataclass
class VMInstanceState:
    """VM instance state for database storage."""
    name: str
    os_type: str
    state: str
    vcpus: int
    memory_mb: int
    disk_size_gb: Optional[int] = None
    template_name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_boot_time: Optional[datetime] = None
    boot_time_ms: Optional[int] = None
    network_config: Optional[Dict[str, Any]] = None
    resource_allocation: Optional[Dict[str, Any]] = None


@dataclass
class VMSnapshot:
    """VM snapshot information for database storage."""
    vm_name: str
    name: str
    description: Optional[str] = None
    file_path: str = ""
    file_size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    parent_snapshot_name: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class DatabaseService:
    """Database service for state management."""
    
    def __init__(self):
        self.config = get_config()
        self.postgres_pool: Optional[Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        
        # Database configuration
        self.database_url = os.getenv("DATABASE_URL", "postgresql://microvm:microvm@localhost:5432/microvm")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        # Connection pool settings
        self.min_pool_size = int(os.getenv("DB_MIN_POOL_SIZE", "5"))
        self.max_pool_size = int(os.getenv("DB_MAX_POOL_SIZE", "20"))
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        
        # Cache settings
        self.cache_ttl = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes
    
    async def initialize(self):
        """Initialize database connections."""
        logger.info("Initializing database connections...")
        
        if not ASYNCPG_AVAILABLE:
            logger.warning("PostgreSQL client not available - install asyncpg package")
            self.postgres_pool = None
        else:
            try:
                # Initialize PostgreSQL connection pool
                self.postgres_pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=self.min_pool_size,
                    max_size=self.max_pool_size,
                    command_timeout=self.pool_timeout
                )
                
                # Test PostgreSQL connection
                async with self.postgres_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                
                logger.info("PostgreSQL connection pool initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize PostgreSQL pool: {e}")
                self.postgres_pool = None
        
        if not REDIS_AVAILABLE:
            logger.warning("Redis client not available - install redis package")
            self.redis_client = None
        else:
            try:
                # Initialize Redis connection
                self.redis_client = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=30,
                    socket_connect_timeout=30,
                    health_check_interval=30
                )
                
                # Test Redis connection
                await self.redis_client.ping()
                
                logger.info("Redis connection initialized successfully")
                
            except Exception as e:
                logger.warning(f"Failed to initialize Redis connection: {e}")
                self.redis_client = None
    
    async def close(self):
        """Close database connections."""
        logger.info("Closing database connections...")
        
        if self.postgres_pool:
            await self.postgres_pool.close()
            self.postgres_pool = None
        
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
        
        logger.info("Database connections closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool."""
        if not self.postgres_pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.postgres_pool.acquire() as conn:
            yield conn
    
    # VM Instance Management
    
    async def save_vm_instance(self, vm_state: VMInstanceState) -> bool:
        """Save or update VM instance state."""
        try:
            async with self.get_connection() as conn:
                # Check if VM exists
                existing = await conn.fetchrow(
                    "SELECT id FROM vm_instances WHERE name = $1",
                    vm_state.name
                )
                
                if existing:
                    # Update existing VM
                    await conn.execute("""
                        UPDATE vm_instances SET
                            os_type = $2,
                            state = $3,
                            vcpus = $4,
                            memory_mb = $5,
                            disk_size_gb = $6,
                            template_name = $7,
                            config = $8,
                            updated_at = NOW(),
                            last_boot_time = $9,
                            boot_time_ms = $10,
                            network_config = $11,
                            resource_allocation = $12
                        WHERE name = $1
                    """,
                        vm_state.name,
                        vm_state.os_type,
                        vm_state.state,
                        vm_state.vcpus,
                        vm_state.memory_mb,
                        vm_state.disk_size_gb,
                        vm_state.template_name,
                        json.dumps(vm_state.config) if vm_state.config else None,
                        vm_state.last_boot_time,
                        vm_state.boot_time_ms,
                        json.dumps(vm_state.network_config) if vm_state.network_config else None,
                        json.dumps(vm_state.resource_allocation) if vm_state.resource_allocation else None
                    )
                else:
                    # Insert new VM
                    await conn.execute("""
                        INSERT INTO vm_instances (
                            name, os_type, state, vcpus, memory_mb, disk_size_gb,
                            template_name, config, last_boot_time, boot_time_ms,
                            network_config, resource_allocation
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                        vm_state.name,
                        vm_state.os_type,
                        vm_state.state,
                        vm_state.vcpus,
                        vm_state.memory_mb,
                        vm_state.disk_size_gb,
                        vm_state.template_name,
                        json.dumps(vm_state.config) if vm_state.config else None,
                        vm_state.last_boot_time,
                        vm_state.boot_time_ms,
                        json.dumps(vm_state.network_config) if vm_state.network_config else None,
                        json.dumps(vm_state.resource_allocation) if vm_state.resource_allocation else None
                    )
                
                # Invalidate cache
                await self._invalidate_cache(f"vm_instance:{vm_state.name}")
                await self._invalidate_cache("vm_instances:all")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to save VM instance {vm_state.name}: {e}")
            return False
    
    async def get_vm_instance(self, vm_name: str) -> Optional[VMInstanceState]:
        """Get VM instance state by name."""
        try:
            # Try cache first
            cached = await self._get_cache(f"vm_instance:{vm_name}")
            if cached:
                data = json.loads(cached)
                return VMInstanceState(**data)
            
            async with self.get_connection() as conn:
                row = await conn.fetchrow("""
                    SELECT name, os_type, state, vcpus, memory_mb, disk_size_gb,
                           template_name, config, created_at, updated_at,
                           last_boot_time, boot_time_ms, network_config, resource_allocation
                    FROM vm_instances WHERE name = $1
                """, vm_name)
                
                if not row:
                    return None
                
                vm_state = VMInstanceState(
                    name=row['name'],
                    os_type=row['os_type'],
                    state=row['state'],
                    vcpus=row['vcpus'],
                    memory_mb=row['memory_mb'],
                    disk_size_gb=row['disk_size_gb'],
                    template_name=row['template_name'],
                    config=json.loads(row['config']) if row['config'] else None,
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    last_boot_time=row['last_boot_time'],
                    boot_time_ms=row['boot_time_ms'],
                    network_config=json.loads(row['network_config']) if row['network_config'] else None,
                    resource_allocation=json.loads(row['resource_allocation']) if row['resource_allocation'] else None
                )
                
                # Cache the result
                await self._set_cache(f"vm_instance:{vm_name}", json.dumps(asdict(vm_state)))
                
                return vm_state
                
        except Exception as e:
            logger.error(f"Failed to get VM instance {vm_name}: {e}")
            return None
    
    async def list_vm_instances(self, state_filter: Optional[str] = None) -> List[VMInstanceState]:
        """List all VM instances, optionally filtered by state."""
        try:
            # Try cache first
            cache_key = f"vm_instances:all:{state_filter or 'all'}"
            cached = await self._get_cache(cache_key)
            if cached:
                data = json.loads(cached)
                return [VMInstanceState(**item) for item in data]
            
            async with self.get_connection() as conn:
                if state_filter:
                    rows = await conn.fetch("""
                        SELECT name, os_type, state, vcpus, memory_mb, disk_size_gb,
                               template_name, config, created_at, updated_at,
                               last_boot_time, boot_time_ms, network_config, resource_allocation
                        FROM vm_instances WHERE state = $1
                        ORDER BY created_at DESC
                    """, state_filter)
                else:
                    rows = await conn.fetch("""
                        SELECT name, os_type, state, vcpus, memory_mb, disk_size_gb,
                               template_name, config, created_at, updated_at,
                               last_boot_time, boot_time_ms, network_config, resource_allocation
                        FROM vm_instances
                        ORDER BY created_at DESC
                    """)
                
                vm_instances = []
                for row in rows:
                    vm_state = VMInstanceState(
                        name=row['name'],
                        os_type=row['os_type'],
                        state=row['state'],
                        vcpus=row['vcpus'],
                        memory_mb=row['memory_mb'],
                        disk_size_gb=row['disk_size_gb'],
                        template_name=row['template_name'],
                        config=json.loads(row['config']) if row['config'] else None,
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        last_boot_time=row['last_boot_time'],
                        boot_time_ms=row['boot_time_ms'],
                        network_config=json.loads(row['network_config']) if row['network_config'] else None,
                        resource_allocation=json.loads(row['resource_allocation']) if row['resource_allocation'] else None
                    )
                    vm_instances.append(vm_state)
                
                # Cache the result
                await self._set_cache(cache_key, json.dumps([asdict(vm) for vm in vm_instances]))
                
                return vm_instances
                
        except Exception as e:
            logger.error(f"Failed to list VM instances: {e}")
            return []
    
    async def delete_vm_instance(self, vm_name: str) -> bool:
        """Delete VM instance from database."""
        try:
            async with self.get_connection() as conn:
                result = await conn.execute(
                    "DELETE FROM vm_instances WHERE name = $1",
                    vm_name
                )
                
                # Invalidate cache
                await self._invalidate_cache(f"vm_instance:{vm_name}")
                await self._invalidate_cache("vm_instances:all")
                
                return result == "DELETE 1"
                
        except Exception as e:
            logger.error(f"Failed to delete VM instance {vm_name}: {e}")
            return False
    
    # Snapshot Management
    
    async def save_vm_snapshot(self, snapshot: VMSnapshot) -> bool:
        """Save VM snapshot information."""
        try:
            async with self.get_connection() as conn:
                # Get VM ID first
                vm_row = await conn.fetchrow(
                    "SELECT id FROM vm_instances WHERE name = $1",
                    snapshot.vm_name
                )
                
                if not vm_row:
                    logger.error(f"VM {snapshot.vm_name} not found for snapshot")
                    return False
                
                vm_id = vm_row['id']
                
                # Get parent snapshot ID if specified
                parent_id = None
                if snapshot.parent_snapshot_name:
                    parent_row = await conn.fetchrow(
                        "SELECT id FROM vm_snapshots WHERE vm_id = $1 AND name = $2",
                        vm_id, snapshot.parent_snapshot_name
                    )
                    if parent_row:
                        parent_id = parent_row['id']
                
                # Insert or update snapshot
                await conn.execute("""
                    INSERT INTO vm_snapshots (
                        vm_id, name, description, file_path, file_size_bytes,
                        checksum, parent_snapshot_id, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (vm_id, name) DO UPDATE SET
                        description = EXCLUDED.description,
                        file_path = EXCLUDED.file_path,
                        file_size_bytes = EXCLUDED.file_size_bytes,
                        checksum = EXCLUDED.checksum,
                        parent_snapshot_id = EXCLUDED.parent_snapshot_id,
                        metadata = EXCLUDED.metadata
                """,
                    vm_id,
                    snapshot.name,
                    snapshot.description,
                    snapshot.file_path,
                    snapshot.file_size_bytes,
                    snapshot.checksum,
                    parent_id,
                    json.dumps(snapshot.metadata) if snapshot.metadata else None
                )
                
                # Invalidate cache
                await self._invalidate_cache(f"vm_snapshots:{snapshot.vm_name}")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to save snapshot {snapshot.name} for VM {snapshot.vm_name}: {e}")
            return False
    
    async def get_vm_snapshots(self, vm_name: str) -> List[VMSnapshot]:
        """Get all snapshots for a VM."""
        try:
            # Try cache first
            cache_key = f"vm_snapshots:{vm_name}"
            cached = await self._get_cache(cache_key)
            if cached:
                data = json.loads(cached)
                return [VMSnapshot(**item) for item in data]
            
            async with self.get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT s.name, s.description, s.file_path, s.file_size_bytes,
                           s.checksum, s.created_at, s.metadata, p.name as parent_name
                    FROM vm_snapshots s
                    JOIN vm_instances v ON s.vm_id = v.id
                    LEFT JOIN vm_snapshots p ON s.parent_snapshot_id = p.id
                    WHERE v.name = $1
                    ORDER BY s.created_at DESC
                """, vm_name)
                
                snapshots = []
                for row in rows:
                    snapshot = VMSnapshot(
                        vm_name=vm_name,
                        name=row['name'],
                        description=row['description'],
                        file_path=row['file_path'],
                        file_size_bytes=row['file_size_bytes'],
                        checksum=row['checksum'],
                        parent_snapshot_name=row['parent_name'],
                        created_at=row['created_at'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else None
                    )
                    snapshots.append(snapshot)
                
                # Cache the result
                await self._set_cache(cache_key, json.dumps([asdict(s) for s in snapshots]))
                
                return snapshots
                
        except Exception as e:
            logger.error(f"Failed to get snapshots for VM {vm_name}: {e}")
            return []
    
    async def delete_vm_snapshot(self, vm_name: str, snapshot_name: str) -> bool:
        """Delete a VM snapshot."""
        try:
            async with self.get_connection() as conn:
                result = await conn.execute("""
                    DELETE FROM vm_snapshots
                    WHERE id IN (
                        SELECT s.id FROM vm_snapshots s
                        JOIN vm_instances v ON s.vm_id = v.id
                        WHERE v.name = $1 AND s.name = $2
                    )
                """, vm_name, snapshot_name)
                
                # Invalidate cache
                await self._invalidate_cache(f"vm_snapshots:{vm_name}")
                
                return result == "DELETE 1"
                
        except Exception as e:
            logger.error(f"Failed to delete snapshot {snapshot_name} for VM {vm_name}: {e}")
            return False
    
    # Cache Management
    
    async def _get_cache(self, key: str) -> Optional[str]:
        """Get value from cache."""
        if not self.redis_client:
            return None
        
        try:
            return await self.redis_client.get(key)
        except Exception as e:
            logger.debug(f"Cache get failed for key {key}: {e}")
            return None
    
    async def _set_cache(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.set(key, value, ex=ttl or self.cache_ttl)
            return True
        except Exception as e:
            logger.debug(f"Cache set failed for key {key}: {e}")
            return False
    
    async def _invalidate_cache(self, pattern: str) -> bool:
        """Invalidate cache entries matching pattern."""
        if not self.redis_client:
            return False
        
        try:
            keys = await self.redis_client.keys(f"{pattern}*")
            if keys:
                await self.redis_client.delete(*keys)
            return True
        except Exception as e:
            logger.debug(f"Cache invalidation failed for pattern {pattern}: {e}")
            return False
    
    # Utility Methods
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            async with self.get_connection() as conn:
                vm_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_vms,
                        COUNT(*) FILTER (WHERE state = 'running') as running_vms,
                        COUNT(*) FILTER (WHERE state = 'stopped') as stopped_vms,
                        COUNT(*) FILTER (WHERE os_type = 'linux') as linux_vms,
                        COUNT(*) FILTER (WHERE os_type = 'windows') as windows_vms,
                        AVG(boot_time_ms) as avg_boot_time_ms,
                        SUM(memory_mb) as total_memory_mb,
                        SUM(vcpus) as total_vcpus
                    FROM vm_instances
                """)
                
                snapshot_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_snapshots,
                        SUM(file_size_bytes) as total_snapshot_size,
                        AVG(file_size_bytes) as avg_snapshot_size
                    FROM vm_snapshots
                """)
                
                return {
                    "vm_statistics": dict(vm_stats) if vm_stats else {},
                    "snapshot_statistics": dict(snapshot_stats) if snapshot_stats else {},
                    "cache_enabled": self.redis_client is not None,
                    "database_connected": self.postgres_pool is not None
                }
                
        except Exception as e:
            logger.error(f"Failed to get database statistics: {e}")
            return {}


# Global database service instance
_database_service: Optional[DatabaseService] = None


async def get_database_service() -> DatabaseService:
    """Get global database service instance."""
    global _database_service
    if _database_service is None:
        _database_service = DatabaseService()
        await _database_service.initialize()
    return _database_service


async def close_database_service():
    """Close global database service."""
    global _database_service
    if _database_service is not None:
        await _database_service.close()
        _database_service = None