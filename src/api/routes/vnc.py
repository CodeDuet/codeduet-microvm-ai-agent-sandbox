"""
VNC API routes for MicroVM desktop access and control.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import base64

from src.core.vnc_manager import VNCManager
from src.core.vm_manager import VMManager
from src.utils.security import check_api_key, SecurityContext
from src.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/vnc", tags=["vnc"])

# Initialize managers
vnc_manager = VNCManager()
vm_manager = VMManager()


class VNCStartRequest(BaseModel):
    """Request to start VNC server for a VM."""
    vm_name: str = Field(..., description="Name of the VM")
    password: Optional[str] = Field(None, description="VNC password (auto-generated if not provided)")
    resolution: Optional[str] = Field("1920x1080", description="Screen resolution")
    color_depth: Optional[int] = Field(24, description="Color depth")
    performance_mode: Optional[str] = Field("balanced", description="Performance mode: speed, balanced, quality")


class VNCConnectionInfo(BaseModel):
    """VNC connection information."""
    vm_name: str
    display: int
    port: int
    password: str
    status: str
    vnc_type: str      # "guest" for Linux, "hypervisor" for Windows
    os_type: str       # "linux" or "windows"
    created_at: str
    connection_count: int
    last_activity: str


class ScreenshotRequest(BaseModel):
    """Request to take a screenshot."""
    vm_name: str = Field(..., description="Name of the VM")
    format: Optional[str] = Field("png", description="Image format: png, jpeg")


class MouseClickRequest(BaseModel):
    """Request to perform mouse click."""
    vm_name: str = Field(..., description="Name of the VM")
    x: int = Field(..., description="X coordinate")
    y: int = Field(..., description="Y coordinate")
    button: Optional[int] = Field(1, description="Mouse button: 1=left, 2=middle, 3=right")


class KeyCombinationRequest(BaseModel):
    """Request to send key combination."""
    vm_name: str = Field(..., description="Name of the VM")
    keys: str = Field(..., description="Key combination (e.g., 'ctrl+alt+t', 'alt+F4')")


class TypeTextRequest(BaseModel):
    """Request to type text."""
    vm_name: str = Field(..., description="Name of the VM")
    text: str = Field(..., description="Text to type")


@router.post("/start", response_model=VNCConnectionInfo)
async def start_vnc_server(
    request: VNCStartRequest,
    security_context: SecurityContext = Depends(check_api_key)
) -> VNCConnectionInfo:
    """
    Start VNC server for a VM.
    
    Creates a VNC server for desktop access to the specified VM.
    Requires the VM to be running and have GUI support.
    """
    try:
        # Verify VM exists and is running
        vm_info = await vm_manager.get_vm(request.vm_name)
        if not vm_info:
            raise HTTPException(status_code=404, detail=f"VM '{request.vm_name}' not found")
        
        if vm_info.state.value != "running":
            raise HTTPException(
                status_code=400, 
                detail=f"VM '{request.vm_name}' must be running to start VNC server"
            )
        
        # Get VM configuration to determine OS type
        from src.utils.config import load_vm_template
        vm_template = vm_info.template or "linux-default"
        vm_config = load_vm_template(vm_template)
        
        # Prepare VNC configuration
        vnc_config = {
            "password": request.password,
            "resolution": request.resolution,
            "color_depth": request.color_depth,
            "performance_mode": request.performance_mode
        }
        
        # Override with template VNC settings if present
        if "vnc_server" in vm_config:
            template_vnc = vm_config["vnc_server"]
            if not request.password and template_vnc.get("password"):
                vnc_config["password"] = template_vnc["password"]
            if template_vnc.get("port"):
                vnc_config["port"] = template_vnc["port"]
        
        # Start VNC server (pass vm_config to determine Windows vs Linux)
        session = await vnc_manager.start_vnc_server(request.vm_name, vnc_config, vm_config)
        
        # Return connection info
        return VNCConnectionInfo(
            vm_name=session.vm_name,
            display=session.display,
            port=session.port,
            password=session.password,
            status="running",
            vnc_type=session.vnc_type,
            os_type=session.os_type,
            created_at=session.created_at.isoformat(),
            connection_count=session.connection_count,
            last_activity=session.last_activity.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to start VNC server for VM '{request.vm_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_vnc_server(
    vm_name: str,
    security_context: SecurityContext = Depends(check_api_key)
) -> Dict[str, str]:
    """
    Stop VNC server for a VM.
    
    Terminates the VNC server and cleans up resources.
    """
    try:
        await vnc_manager.stop_vnc_server(vm_name)
        return {"status": "success", "message": f"VNC server stopped for VM '{vm_name}'"}
        
    except Exception as e:
        logger.error(f"Failed to stop VNC server for VM '{vm_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info/{vm_name}", response_model=Optional[VNCConnectionInfo])
async def get_vnc_info(
    vm_name: str,
    security_context: SecurityContext = Depends(check_api_key)
) -> Optional[VNCConnectionInfo]:
    """
    Get VNC connection information for a VM.
    
    Returns connection details if VNC server is running for the specified VM.
    """
    try:
        info = await vnc_manager.get_vnc_info(vm_name)
        if not info:
            return None
        
        return VNCConnectionInfo(
            vm_name=info["vm_name"],
            display=info["display"],
            port=info["port"],
            password=info["password"],
            status=info["status"],
            vnc_type=info.get("vnc_type", "guest"),  # Default to guest for backward compatibility
            os_type=info.get("os_type", "linux"),   # Default to linux for backward compatibility
            created_at=info["created_at"],
            connection_count=info["connection_count"],
            last_activity=info["last_activity"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get VNC info for VM '{vm_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_vnc_sessions(
    security_context: SecurityContext = Depends(check_api_key)
) -> Dict[str, Any]:
    """
    List all active VNC sessions.
    
    Returns information about all currently running VNC servers.
    """
    try:
        sessions = await vnc_manager.list_vnc_sessions()
        return {
            "sessions": sessions,
            "total_count": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"Failed to list VNC sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/screenshot")
async def take_screenshot(
    request: ScreenshotRequest,
    security_context: SecurityContext = Depends(check_api_key)
):
    """
    Take a screenshot of the VNC session.
    
    Captures the current desktop state and returns it as base64-encoded image data.
    """
    try:
        # Take screenshot
        image_data = await vnc_manager.take_screenshot(request.vm_name, request.format)
        if not image_data:
            raise HTTPException(status_code=404, detail=f"No VNC session found for VM '{request.vm_name}'")
        
        # Encode as base64
        encoded_image = base64.b64encode(image_data).decode('utf-8')
        
        # Determine MIME type
        mime_type = f"image/{request.format.lower()}"
        
        return {
            "vm_name": request.vm_name,
            "format": request.format,
            "image_data": encoded_image,
            "mime_type": mime_type,
            "size_bytes": len(image_data)
        }
        
    except Exception as e:
        logger.error(f"Failed to take screenshot for VM '{request.vm_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mouse/click")
async def mouse_click(
    request: MouseClickRequest,
    security_context: SecurityContext = Depends(check_api_key)
) -> Dict[str, str]:
    """
    Perform mouse click on VNC session.
    
    Simulates a mouse click at the specified coordinates.
    """
    try:
        await vnc_manager.mouse_click(request.vm_name, request.x, request.y, request.button)
        return {
            "status": "success",
            "message": f"Mouse click performed at ({request.x}, {request.y}) button {request.button}"
        }
        
    except Exception as e:
        logger.error(f"Failed to perform mouse click on VM '{request.vm_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/keyboard/keys")
async def send_key_combination(
    request: KeyCombinationRequest,
    security_context: SecurityContext = Depends(check_api_key)
) -> Dict[str, str]:
    """
    Send key combination to VNC session.
    
    Simulates keyboard key combinations for shortcuts and navigation.
    """
    try:
        await vnc_manager.send_key_combination(request.vm_name, request.keys)
        return {
            "status": "success",
            "message": f"Key combination '{request.keys}' sent to VM '{request.vm_name}'"
        }
        
    except Exception as e:
        logger.error(f"Failed to send keys to VM '{request.vm_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/keyboard/type")
async def type_text(
    request: TypeTextRequest,
    security_context: SecurityContext = Depends(check_api_key)
) -> Dict[str, str]:
    """
    Type text into VNC session.
    
    Simulates typing text character by character.
    """
    try:
        await vnc_manager.type_text(request.vm_name, request.text)
        return {
            "status": "success",
            "message": f"Text typed to VM '{request.vm_name}': {len(request.text)} characters"
        }
        
    except Exception as e:
        logger.error(f"Failed to type text to VM '{request.vm_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))