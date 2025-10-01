"""
Guest communication API routes.
Provides endpoints for communicating with guest agents in VMs.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any
from datetime import datetime

from src.api.models.vm import (
    GuestCommandRequest, GuestCommandResponse,
    GuestFileUploadRequest, GuestFileDownloadRequest, GuestFileTransferResponse,
    GuestSystemInfoResponse, GuestProcessListResponse, GuestHealthCheckResponse,
    GuestServicesResponse, GuestEventLogsRequest, GuestEventLogsResponse,
    GuestShutdownRequest, OSType
)
from src.core.vm_manager import VMManager
from src.core.guest_client import guest_manager, GuestClientError
from src.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/vms/{vm_name}/guest", tags=["guest"])

# Dependency to get VM manager
def get_vm_manager() -> VMManager:
    return VMManager()


@router.post("/ping")
async def ping_guest(
    vm_name: str,
    vm_manager: VMManager = Depends(get_vm_manager)
) -> Dict[str, Any]:
    """Ping the guest agent to check connectivity."""
    try:
        # Get VM info to determine OS type
        vm_info = await vm_manager.get_vm(vm_name)
        if not vm_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' not found"
            )
        
        if not vm_info.guest_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Guest agent not enabled for VM '{vm_name}'"
            )
        
        # Get guest client and ping
        client = guest_manager.get_client(vm_name, vm_info.os_type)
        result = await client.ping()
        
        return result
        
    except GuestClientError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Guest communication failed: {e}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to ping guest for VM {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/execute", response_model=GuestCommandResponse)
async def execute_command(
    vm_name: str,
    request: GuestCommandRequest,
    vm_manager: VMManager = Depends(get_vm_manager)
) -> GuestCommandResponse:
    """Execute a command in the guest."""
    try:
        # Get VM info
        vm_info = await vm_manager.get_vm(vm_name)
        if not vm_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' not found"
            )
        
        if not vm_info.guest_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Guest agent not enabled for VM '{vm_name}'"
            )
        
        # Execute command
        client = guest_manager.get_client(vm_name, vm_info.os_type)
        result = await client.execute_command(
            command=request.command,
            timeout=request.timeout,
            working_dir=request.working_dir,
            env=request.env
        )
        
        return GuestCommandResponse(
            success=result.get("success", False),
            exit_code=result.get("exit_code"),
            stdout=result.get("stdout"),
            stderr=result.get("stderr"),
            error=result.get("error"),
            timestamp=datetime.now()
        )
        
    except GuestClientError as e:
        return GuestCommandResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute command in guest for VM {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/files/upload", response_model=GuestFileTransferResponse)
async def upload_file(
    vm_name: str,
    request: GuestFileUploadRequest,
    vm_manager: VMManager = Depends(get_vm_manager)
) -> GuestFileTransferResponse:
    """Upload a file from host to guest."""
    try:
        # Get VM info
        vm_info = await vm_manager.get_vm(vm_name)
        if not vm_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' not found"
            )
        
        if not vm_info.guest_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Guest agent not enabled for VM '{vm_name}'"
            )
        
        # Upload file
        client = guest_manager.get_client(vm_name, vm_info.os_type)
        result = await client.upload_file(
            local_path=request.local_path,
            remote_path=request.remote_path,
            create_dirs=request.create_dirs,
            mode=request.mode
        )
        
        return GuestFileTransferResponse(
            success=result.get("success", False),
            path=result.get("path"),
            size=result.get("size"),
            checksum=result.get("checksum"),
            error=result.get("error"),
            timestamp=datetime.now()
        )
        
    except GuestClientError as e:
        return GuestFileTransferResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload file to guest for VM {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/files/download", response_model=GuestFileTransferResponse)
async def download_file(
    vm_name: str,
    request: GuestFileDownloadRequest,
    vm_manager: VMManager = Depends(get_vm_manager)
) -> GuestFileTransferResponse:
    """Download a file from guest to host."""
    try:
        # Get VM info
        vm_info = await vm_manager.get_vm(vm_name)
        if not vm_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' not found"
            )
        
        if not vm_info.guest_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Guest agent not enabled for VM '{vm_name}'"
            )
        
        # Download file
        client = guest_manager.get_client(vm_name, vm_info.os_type)
        result = await client.download_file(
            remote_path=request.remote_path,
            local_path=request.local_path,
            max_size=request.max_size
        )
        
        return GuestFileTransferResponse(
            success=result.get("success", False),
            path=result.get("path"),
            size=result.get("size"),
            checksum=result.get("checksum"),
            error=result.get("error"),
            timestamp=datetime.now()
        )
        
    except GuestClientError as e:
        return GuestFileTransferResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download file from guest for VM {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/system-info", response_model=GuestSystemInfoResponse)
async def get_system_info(
    vm_name: str,
    vm_manager: VMManager = Depends(get_vm_manager)
) -> GuestSystemInfoResponse:
    """Get guest system information."""
    try:
        # Get VM info
        vm_info = await vm_manager.get_vm(vm_name)
        if not vm_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' not found"
            )
        
        if not vm_info.guest_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Guest agent not enabled for VM '{vm_name}'"
            )
        
        # Get system info
        client = guest_manager.get_client(vm_name, vm_info.os_type)
        result = await client.get_system_info()
        
        return GuestSystemInfoResponse(
            success=result.get("success", False),
            system_info=result.get("system_info"),
            error=result.get("error"),
            timestamp=datetime.now()
        )
        
    except GuestClientError as e:
        return GuestSystemInfoResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get system info from guest for VM {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/processes", response_model=GuestProcessListResponse)
async def get_process_list(
    vm_name: str,
    vm_manager: VMManager = Depends(get_vm_manager)
) -> GuestProcessListResponse:
    """Get list of running processes in guest."""
    try:
        # Get VM info
        vm_info = await vm_manager.get_vm(vm_name)
        if not vm_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' not found"
            )
        
        if not vm_info.guest_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Guest agent not enabled for VM '{vm_name}'"
            )
        
        # Get process list
        client = guest_manager.get_client(vm_name, vm_info.os_type)
        result = await client.get_process_list()
        
        return GuestProcessListResponse(
            success=result.get("success", False),
            processes=result.get("processes"),
            error=result.get("error"),
            timestamp=datetime.now()
        )
        
    except GuestClientError as e:
        return GuestProcessListResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get process list from guest for VM {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/health", response_model=GuestHealthCheckResponse)
async def health_check(
    vm_name: str,
    vm_manager: VMManager = Depends(get_vm_manager)
) -> GuestHealthCheckResponse:
    """Perform guest health check."""
    try:
        # Get VM info
        vm_info = await vm_manager.get_vm(vm_name)
        if not vm_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' not found"
            )
        
        if not vm_info.guest_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Guest agent not enabled for VM '{vm_name}'"
            )
        
        # Perform health check
        client = guest_manager.get_client(vm_name, vm_info.os_type)
        result = await client.health_check()
        
        return GuestHealthCheckResponse(
            success=result.get("success", False),
            health=result.get("health"),
            error=result.get("error"),
            timestamp=datetime.now()
        )
        
    except GuestClientError as e:
        return GuestHealthCheckResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to perform health check for guest in VM {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/shutdown")
async def shutdown_guest(
    vm_name: str,
    request: GuestShutdownRequest,
    vm_manager: VMManager = Depends(get_vm_manager)
) -> Dict[str, Any]:
    """Shutdown the guest system."""
    try:
        # Get VM info
        vm_info = await vm_manager.get_vm(vm_name)
        if not vm_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' not found"
            )
        
        if not vm_info.guest_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Guest agent not enabled for VM '{vm_name}'"
            )
        
        # Shutdown guest
        client = guest_manager.get_client(vm_name, vm_info.os_type)
        result = await client.shutdown(
            force=request.force,
            delay=request.delay
        )
        
        return result
        
    except GuestClientError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Guest communication failed: {e}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to shutdown guest for VM {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# Windows-specific endpoints
@router.get("/services", response_model=GuestServicesResponse)
async def get_services(
    vm_name: str,
    vm_manager: VMManager = Depends(get_vm_manager)
) -> GuestServicesResponse:
    """Get Windows services (Windows only)."""
    try:
        # Get VM info
        vm_info = await vm_manager.get_vm(vm_name)
        if not vm_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' not found"
            )
        
        if vm_info.os_type != OSType.WINDOWS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Services endpoint is only available for Windows guests"
            )
        
        if not vm_info.guest_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Guest agent not enabled for VM '{vm_name}'"
            )
        
        # Get services
        client = guest_manager.get_client(vm_name, vm_info.os_type)
        result = await client.get_services()
        
        return GuestServicesResponse(
            success=result.get("success", False),
            services=result.get("services"),
            error=result.get("error"),
            timestamp=datetime.now()
        )
        
    except GuestClientError as e:
        return GuestServicesResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get services from guest for VM {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/event-logs", response_model=GuestEventLogsResponse)
async def get_event_logs(
    vm_name: str,
    request: GuestEventLogsRequest,
    vm_manager: VMManager = Depends(get_vm_manager)
) -> GuestEventLogsResponse:
    """Get Windows event logs (Windows only)."""
    try:
        # Get VM info
        vm_info = await vm_manager.get_vm(vm_name)
        if not vm_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' not found"
            )
        
        if vm_info.os_type != OSType.WINDOWS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event logs endpoint is only available for Windows guests"
            )
        
        if not vm_info.guest_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Guest agent not enabled for VM '{vm_name}'"
            )
        
        # Get event logs
        client = guest_manager.get_client(vm_name, vm_info.os_type)
        result = await client.get_event_logs(
            log_name=request.log_name,
            max_events=request.max_events
        )
        
        return GuestEventLogsResponse(
            success=result.get("success", False),
            events=result.get("events"),
            error=result.get("error"),
            timestamp=datetime.now()
        )
        
    except GuestClientError as e:
        return GuestEventLogsResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get event logs from guest for VM {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )