from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
from pydantic import BaseModel

from src.core.network_manager import NetworkManager

router = APIRouter()
network_manager = NetworkManager()


class PortForwardRequest(BaseModel):
    guest_port: int
    host_port: int = None


@router.get("/interfaces")
async def list_network_interfaces() -> Dict[str, List[Dict[str, str]]]:
    try:
        interfaces = await network_manager.list_network_interfaces()
        return {"interfaces": interfaces}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list network interfaces: {str(e)}"
        )


@router.get("/vm/{vm_name}")
async def get_vm_network_info(vm_name: str) -> Dict[str, Any]:
    try:
        network_info = await network_manager.get_vm_network_info(vm_name)
        if not network_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' network interface not found"
            )
        return network_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get VM network info: {str(e)}"
        )


@router.post("/vm/{vm_name}/port-forward")
async def create_port_forward(vm_name: str, request: PortForwardRequest) -> Dict[str, Any]:
    try:
        host_port = await network_manager.allocate_port_forward(vm_name, request.guest_port)
        return {
            "vm_name": vm_name,
            "guest_port": request.guest_port,
            "host_port": host_port,
            "message": f"Port forward created: host:{host_port} -> {vm_name}:{request.guest_port}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create port forward: {str(e)}"
        )


@router.delete("/vm/{vm_name}/port-forward/{guest_port}")
async def remove_port_forward(vm_name: str, guest_port: int) -> Dict[str, str]:
    try:
        await network_manager.remove_port_forward(vm_name, guest_port)
        return {"message": f"Port forward removed for {vm_name}:{guest_port}"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove port forward: {str(e)}"
        )


@router.post("/setup")
async def setup_bridge_network() -> Dict[str, str]:
    try:
        await network_manager.setup_bridge_network()
        return {"message": "Bridge network setup completed"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to setup bridge network: {str(e)}"
        )


@router.post("/teardown")
async def teardown_bridge_network() -> Dict[str, str]:
    try:
        await network_manager.teardown_bridge_network()
        return {"message": "Bridge network torn down"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to teardown bridge network: {str(e)}"
        )