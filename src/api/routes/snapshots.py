from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
from src.api.models.vm import SnapshotCreateRequest, SnapshotResponse
from src.core.snapshot_manager import SnapshotManager

router = APIRouter()
snapshot_manager = SnapshotManager()


@router.post("/{vm_name}", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
async def create_snapshot(vm_name: str, snapshot_request: SnapshotCreateRequest) -> SnapshotResponse:
    try:
        snapshot_info = await snapshot_manager.create_snapshot(vm_name, snapshot_request.name)
        return SnapshotResponse(**snapshot_info.model_dump())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create snapshot: {str(e)}"
        )


@router.get("/{vm_name}")
async def list_snapshots(vm_name: str) -> List[SnapshotResponse]:
    try:
        snapshots = await snapshot_manager.list_snapshots(vm_name)
        return [SnapshotResponse(**snapshot.model_dump()) for snapshot in snapshots]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list snapshots: {str(e)}"
        )


@router.post("/{vm_name}/{snapshot_name}/restore")
async def restore_snapshot(vm_name: str, snapshot_name: str) -> Dict[str, str]:
    try:
        await snapshot_manager.restore_snapshot(vm_name, snapshot_name)
        return {"message": f"VM '{vm_name}' restored from snapshot '{snapshot_name}'"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore snapshot: {str(e)}"
        )


@router.delete("/{vm_name}/{snapshot_name}")
async def delete_snapshot(vm_name: str, snapshot_name: str) -> Dict[str, str]:
    try:
        await snapshot_manager.delete_snapshot(vm_name, snapshot_name)
        return {"message": f"Snapshot '{snapshot_name}' deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete snapshot: {str(e)}"
        )