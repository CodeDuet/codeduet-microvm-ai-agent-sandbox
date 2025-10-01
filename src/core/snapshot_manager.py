from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import hashlib
import os
import asyncio
import json

from src.api.models.vm import SnapshotInfo
from src.core.ch_client import CloudHypervisorClient
from src.utils.helpers import write_json_async, read_json_async
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SnapshotManager:
    def __init__(self):
        self.snapshots_dir = Path("data/snapshots")
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.max_snapshots_per_vm = 10  # Configurable limit
        self.cleanup_older_than_days = 30  # Configurable cleanup policy

    async def create_snapshot(self, vm_name: str, snapshot_name: str, description: str = "", incremental: bool = False, parent_snapshot: Optional[str] = None) -> SnapshotInfo:
        logger.info(f"Creating {'incremental' if incremental else 'full'} snapshot '{snapshot_name}' for VM '{vm_name}'")
        
        # Check snapshot limits and cleanup if needed
        await self._enforce_snapshot_limits(vm_name)
        
        snapshot_dir = self.snapshots_dir / vm_name / snapshot_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        snapshot_path = snapshot_dir / "snapshot.bin"
        
        # Create snapshot via Cloud Hypervisor API
        ch_client = CloudHypervisorClient(vm_name)
        try:
            await ch_client.snapshot_vm(str(snapshot_path))
            logger.info(f"Snapshot data created at '{snapshot_path}'")
        except Exception as e:
            logger.error(f"Failed to create snapshot via Cloud Hypervisor: {e}")
            # Clean up on failure
            if snapshot_dir.exists():
                shutil.rmtree(snapshot_dir)
            raise
        
        # Calculate checksum for integrity verification
        checksum = await self._calculate_file_checksum(snapshot_path)
        
        snapshot_info = SnapshotInfo(
            name=snapshot_name,
            vm_name=vm_name,
            description=description,
            created_at=datetime.now(),
            size_bytes=snapshot_path.stat().st_size if snapshot_path.exists() else 0
        )
        
        # Enhanced metadata with checksum and parent info
        metadata = snapshot_info.model_dump()
        metadata.update({
            "checksum": checksum,
            "incremental": incremental,
            "parent_snapshot": parent_snapshot,
            "snapshot_version": "1.0"
        })
        
        # Save snapshot metadata
        metadata_file = snapshot_dir / "metadata.json"
        await write_json_async(metadata_file, metadata)
        
        logger.info(f"Snapshot '{snapshot_name}' created for VM '{vm_name}' (size: {snapshot_info.size_bytes} bytes, checksum: {checksum[:8]}...)")
        return snapshot_info

    async def list_snapshots(self, vm_name: str) -> List[SnapshotInfo]:
        vm_snapshots_dir = self.snapshots_dir / vm_name
        if not vm_snapshots_dir.exists():
            return []
        
        snapshots = []
        for snapshot_dir in vm_snapshots_dir.iterdir():
            if snapshot_dir.is_dir():
                metadata_file = snapshot_dir / "metadata.json"
                if metadata_file.exists():
                    data = await read_json_async(metadata_file)
                    snapshots.append(SnapshotInfo(**data))
        
        return sorted(snapshots, key=lambda s: s.created_at, reverse=True)

    async def restore_snapshot(self, vm_name: str, snapshot_name: str) -> None:
        logger.info(f"Restoring VM '{vm_name}' from snapshot '{snapshot_name}'")
        
        snapshot_dir = self.snapshots_dir / vm_name / snapshot_name
        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot '{snapshot_name}' not found for VM '{vm_name}'")
        
        snapshot_path = snapshot_dir / "snapshot.bin"
        if not snapshot_path.exists():
            raise ValueError(f"Snapshot data not found: {snapshot_path}")
        
        # Restore VM via Cloud Hypervisor API
        ch_client = CloudHypervisorClient(vm_name)
        try:
            await ch_client.restore_vm(str(snapshot_path))
            logger.info(f"VM '{vm_name}' restored from snapshot '{snapshot_name}'")
        except Exception as e:
            logger.error(f"Failed to restore VM from snapshot: {e}")
            raise

    async def delete_snapshot(self, vm_name: str, snapshot_name: str) -> None:
        logger.info(f"Deleting snapshot '{snapshot_name}' for VM '{vm_name}'")
        
        snapshot_dir = self.snapshots_dir / vm_name / snapshot_name
        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot '{snapshot_name}' not found for VM '{vm_name}'")
        
        shutil.rmtree(snapshot_dir)
        
        logger.info(f"Snapshot '{snapshot_name}' deleted for VM '{vm_name}'")

    async def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        
        def read_chunks(file_path: Path):
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    yield chunk
        
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: [sha256_hash.update(chunk) for chunk in read_chunks(file_path)])
        
        return sha256_hash.hexdigest()

    async def _enforce_snapshot_limits(self, vm_name: str) -> None:
        """Enforce snapshot limits per VM by cleaning up old snapshots."""
        snapshots = await self.list_snapshots(vm_name)
        
        if len(snapshots) >= self.max_snapshots_per_vm:
            # Sort by creation time and remove oldest
            snapshots_to_remove = sorted(snapshots, key=lambda s: s.created_at)[:-self.max_snapshots_per_vm + 1]
            
            for snapshot in snapshots_to_remove:
                try:
                    await self.delete_snapshot(vm_name, snapshot.name)
                    logger.info(f"Auto-removed old snapshot '{snapshot.name}' to enforce limits")
                except Exception as e:
                    logger.warning(f"Failed to auto-remove snapshot '{snapshot.name}': {e}")

    async def cleanup_old_snapshots(self, days_old: Optional[int] = None) -> Dict[str, int]:
        """Clean up snapshots older than specified days across all VMs."""
        cutoff_days = days_old or self.cleanup_older_than_days
        cutoff_date = datetime.now() - timedelta(days=cutoff_days)
        cleanup_stats = {"removed": 0, "errors": 0}
        
        if not self.snapshots_dir.exists():
            return cleanup_stats
        
        for vm_dir in self.snapshots_dir.iterdir():
            if vm_dir.is_dir():
                vm_name = vm_dir.name
                try:
                    snapshots = await self.list_snapshots(vm_name)
                    old_snapshots = [s for s in snapshots if s.created_at < cutoff_date]
                    
                    for snapshot in old_snapshots:
                        try:
                            await self.delete_snapshot(vm_name, snapshot.name)
                            cleanup_stats["removed"] += 1
                            logger.info(f"Cleaned up old snapshot '{snapshot.name}' for VM '{vm_name}'")
                        except Exception as e:
                            cleanup_stats["errors"] += 1
                            logger.error(f"Failed to cleanup snapshot '{snapshot.name}': {e}")
                            
                except Exception as e:
                    cleanup_stats["errors"] += 1
                    logger.error(f"Failed to process snapshots for VM '{vm_name}': {e}")
        
        logger.info(f"Snapshot cleanup completed: {cleanup_stats['removed']} removed, {cleanup_stats['errors']} errors")
        return cleanup_stats

    async def verify_snapshot_integrity(self, vm_name: str, snapshot_name: str) -> Dict[str, Any]:
        """Verify snapshot integrity using stored checksum."""
        snapshot_dir = self.snapshots_dir / vm_name / snapshot_name
        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot '{snapshot_name}' not found for VM '{vm_name}'")
        
        metadata_file = snapshot_dir / "metadata.json"
        snapshot_path = snapshot_dir / "snapshot.bin"
        
        if not metadata_file.exists() or not snapshot_path.exists():
            return {"valid": False, "error": "Missing snapshot files"}
        
        try:
            metadata = await read_json_async(metadata_file)
            stored_checksum = metadata.get("checksum")
            
            if not stored_checksum:
                return {"valid": False, "error": "No checksum in metadata"}
            
            current_checksum = await self._calculate_file_checksum(snapshot_path)
            
            is_valid = stored_checksum == current_checksum
            result = {
                "valid": is_valid,
                "stored_checksum": stored_checksum,
                "current_checksum": current_checksum,
                "size_bytes": snapshot_path.stat().st_size
            }
            
            if not is_valid:
                result["error"] = "Checksum mismatch - snapshot may be corrupted"
                
            return result
            
        except Exception as e:
            return {"valid": False, "error": f"Verification failed: {str(e)}"}

    async def get_snapshot_statistics(self) -> Dict[str, Any]:
        """Get comprehensive snapshot statistics."""
        stats = {
            "total_snapshots": 0,
            "total_size_bytes": 0,
            "vms_with_snapshots": 0,
            "oldest_snapshot": None,
            "newest_snapshot": None,
            "vms": {}
        }
        
        if not self.snapshots_dir.exists():
            return stats
        
        oldest_date = None
        newest_date = None
        
        for vm_dir in self.snapshots_dir.iterdir():
            if vm_dir.is_dir():
                vm_name = vm_dir.name
                vm_snapshots = await self.list_snapshots(vm_name)
                
                if vm_snapshots:
                    stats["vms_with_snapshots"] += 1
                    vm_total_size = sum(s.size_bytes for s in vm_snapshots)
                    stats["vms"][vm_name] = {
                        "count": len(vm_snapshots),
                        "total_size_bytes": vm_total_size,
                        "oldest": min(s.created_at for s in vm_snapshots),
                        "newest": max(s.created_at for s in vm_snapshots)
                    }
                    
                    stats["total_snapshots"] += len(vm_snapshots)
                    stats["total_size_bytes"] += vm_total_size
                    
                    # Track global oldest/newest
                    vm_oldest = stats["vms"][vm_name]["oldest"]
                    vm_newest = stats["vms"][vm_name]["newest"]
                    
                    if oldest_date is None or vm_oldest < oldest_date:
                        oldest_date = vm_oldest
                    if newest_date is None or vm_newest > newest_date:
                        newest_date = vm_newest
        
        stats["oldest_snapshot"] = oldest_date
        stats["newest_snapshot"] = newest_date
        
        return stats