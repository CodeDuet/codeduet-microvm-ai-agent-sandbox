from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
from src.api.models.vm import VMCreateRequest, VMResponse, VMListResponse
from src.core.vm_manager import VMManager

router = APIRouter()
vm_manager = VMManager()


@router.post("/", response_model=VMResponse, status_code=status.HTTP_201_CREATED)
async def create_vm(vm_request: VMCreateRequest) -> VMResponse:
    try:
        vm_info = await vm_manager.create_vm(vm_request)
        return VMResponse(**vm_info.model_dump())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create VM: {str(e)}"
        )


@router.get("/", response_model=VMListResponse)
async def list_vms() -> VMListResponse:
    try:
        vms = await vm_manager.list_vms()
        return VMListResponse(vms=vms)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list VMs: {str(e)}"
        )


@router.get("/{vm_name}", response_model=VMResponse)
async def get_vm(vm_name: str) -> VMResponse:
    try:
        vm_info = await vm_manager.get_vm(vm_name)
        if not vm_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' not found"
            )
        return VMResponse(**vm_info.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get VM: {str(e)}"
        )


@router.post("/{vm_name}/start")
async def start_vm(vm_name: str) -> Dict[str, str]:
    try:
        await vm_manager.start_vm(vm_name)
        return {"message": f"VM '{vm_name}' started successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start VM: {str(e)}"
        )


@router.post("/{vm_name}/stop")
async def stop_vm(vm_name: str) -> Dict[str, str]:
    try:
        await vm_manager.stop_vm(vm_name)
        return {"message": f"VM '{vm_name}' stopped successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop VM: {str(e)}"
        )


@router.delete("/{vm_name}")
async def delete_vm(vm_name: str) -> Dict[str, str]:
    try:
        await vm_manager.delete_vm(vm_name)
        return {"message": f"VM '{vm_name}' deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete VM: {str(e)}"
        )


@router.post("/{vm_name}/pause")
async def pause_vm(vm_name: str) -> Dict[str, str]:
    try:
        await vm_manager.pause_vm(vm_name)
        return {"message": f"VM '{vm_name}' paused successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause VM: {str(e)}"
        )


@router.post("/{vm_name}/resume")
async def resume_vm(vm_name: str) -> Dict[str, str]:
    try:
        await vm_manager.resume_vm(vm_name)
        return {"message": f"VM '{vm_name}' resumed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume VM: {str(e)}"
        )


@router.get("/{vm_name}/status")
async def get_vm_status(vm_name: str) -> Dict[str, Any]:
    try:
        status_info = await vm_manager.get_vm_status(vm_name)
        return status_info
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get VM status: {str(e)}"
        )