from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from src.api.models.vm import SnapshotCreateRequest, SnapshotResponse
from src.core.snapshot_manager import SnapshotManager

router = APIRouter()
snapshot_manager = SnapshotManager()


@router.post("/cleanup")
async def cleanup_old_snapshots(
    days_old: Optional[int] = Query(None, description="Clean snapshots older than specified days")
) -> Dict[str, Any]:
    """Clean up old snapshots across all VMs."""
    try:
        result = await snapshot_manager.cleanup_old_snapshots(days_old)
        return {
            "message": "Snapshot cleanup completed",
            "statistics": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup snapshots: {str(e)}"
        )


@router.get("/statistics")
async def get_snapshot_statistics() -> Dict[str, Any]:
    """Get comprehensive snapshot statistics."""
    try:
        stats = await snapshot_manager.get_snapshot_statistics()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get snapshot statistics: {str(e)}"
        )


@router.post("/{vm_name}", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    vm_name: str, 
    snapshot_request: SnapshotCreateRequest,
    incremental: bool = Query(False, description="Create incremental snapshot"),
    parent_snapshot: Optional[str] = Query(None, description="Parent snapshot for incremental backup")
) -> SnapshotResponse:
    try:
        snapshot_info = await snapshot_manager.create_snapshot(
            vm_name, 
            snapshot_request.name, 
            snapshot_request.description,
            incremental=incremental,
            parent_snapshot=parent_snapshot
        )
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


@router.post("/{vm_name}/{snapshot_name}/verify")
async def verify_snapshot(vm_name: str, snapshot_name: str) -> Dict[str, Any]:
    """Verify snapshot integrity."""
    try:
        result = await snapshot_manager.verify_snapshot_integrity(vm_name, snapshot_name)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify snapshot: {str(e)}"
        )