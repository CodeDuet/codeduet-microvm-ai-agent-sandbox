from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
import shutil

from src.api.models.vm import SnapshotInfo
from src.core.ch_client import CloudHypervisorClient
from src.utils.helpers import write_json_async, read_json_async
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SnapshotManager:
    def __init__(self):
        self.snapshots_dir = Path("data/snapshots")
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    async def create_snapshot(self, vm_name: str, snapshot_name: str) -> SnapshotInfo:
        logger.info(f"Creating snapshot '{snapshot_name}' for VM '{vm_name}'")
        
        snapshot_dir = self.snapshots_dir / vm_name / snapshot_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        snapshot_path = snapshot_dir / "snapshot.bin"
        
        # TODO: Create snapshot via Cloud Hypervisor
        # ch_client = CloudHypervisorClient(vm_name)
        # await ch_client.snapshot_vm(str(snapshot_path))
        
        # For now, create a dummy snapshot file
        snapshot_path.write_bytes(b"dummy snapshot data")
        
        snapshot_info = SnapshotInfo(
            name=snapshot_name,
            vm_name=vm_name,
            description="",
            created_at=datetime.now(),
            size_bytes=snapshot_path.stat().st_size if snapshot_path.exists() else 0
        )
        
        # Save snapshot metadata
        metadata_file = snapshot_dir / "metadata.json"
        await write_json_async(metadata_file, snapshot_info.model_dump())
        
        logger.info(f"Snapshot '{snapshot_name}' created for VM '{vm_name}'")
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
        
        # TODO: Restore VM via Cloud Hypervisor
        # ch_client = CloudHypervisorClient(vm_name)
        # await ch_client.restore_vm(str(snapshot_path))
        
        logger.info(f"VM '{vm_name}' restored from snapshot '{snapshot_name}'")

    async def delete_snapshot(self, vm_name: str, snapshot_name: str) -> None:
        logger.info(f"Deleting snapshot '{snapshot_name}' for VM '{vm_name}'")
        
        snapshot_dir = self.snapshots_dir / vm_name / snapshot_name
        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot '{snapshot_name}' not found for VM '{vm_name}'")
        
        shutil.rmtree(snapshot_dir)
        
        logger.info(f"Snapshot '{snapshot_name}' deleted for VM '{vm_name}'")