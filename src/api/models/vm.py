from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class VMState(str, Enum):
    CREATING = "creating"
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class OSType(str, Enum):
    LINUX = "linux"
    WINDOWS = "windows"


class VMCreateRequest(BaseModel):
    name: str = Field(..., description="VM name", min_length=1, max_length=64)
    template: str = Field(..., description="VM template name")
    vcpus: Optional[int] = Field(default=2, description="Number of vCPUs", ge=1, le=16)
    memory_mb: Optional[int] = Field(default=512, description="Memory in MB", ge=128, le=8192)
    os_type: OSType = Field(default=OSType.LINUX, description="Operating system type")
    guest_agent: Optional[bool] = Field(default=True, description="Enable guest agent")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="VM metadata")


class VMInfo(BaseModel):
    name: str
    state: VMState
    vcpus: int
    memory_mb: int
    os_type: OSType
    template: str
    guest_agent: bool
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]


class VMResponse(BaseModel):
    name: str
    state: VMState
    vcpus: int
    memory_mb: int
    os_type: OSType
    template: str
    guest_agent: bool
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]


class VMListResponse(BaseModel):
    vms: List[VMResponse]


class SnapshotCreateRequest(BaseModel):
    name: str = Field(..., description="Snapshot name", min_length=1, max_length=64)
    description: Optional[str] = Field(default="", description="Snapshot description")


class SnapshotInfo(BaseModel):
    name: str
    vm_name: str
    description: str
    created_at: datetime
    size_bytes: int


class SnapshotResponse(BaseModel):
    name: str
    vm_name: str
    description: str
    created_at: datetime
    size_bytes: int


# Guest Communication Models
class GuestCommandRequest(BaseModel):
    command: str = Field(..., description="Command to execute in guest")
    timeout: Optional[int] = Field(default=30, description="Command timeout in seconds", ge=1, le=3600)
    working_dir: Optional[str] = Field(default=None, description="Working directory for command")
    env: Optional[Dict[str, str]] = Field(default_factory=dict, description="Environment variables")


class GuestCommandResponse(BaseModel):
    success: bool
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime


class GuestFileUploadRequest(BaseModel):
    local_path: str = Field(..., description="Local file path on host")
    remote_path: str = Field(..., description="Remote file path in guest")
    create_dirs: Optional[bool] = Field(default=False, description="Create parent directories")
    mode: Optional[int] = Field(default=0o644, description="File permissions (Unix only)")


class GuestFileDownloadRequest(BaseModel):
    remote_path: str = Field(..., description="Remote file path in guest")
    local_path: str = Field(..., description="Local file path on host")
    max_size: Optional[int] = Field(default=10485760, description="Maximum file size in bytes")


class GuestFileTransferResponse(BaseModel):
    success: bool
    path: Optional[str] = None
    size: Optional[int] = None
    checksum: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime


class GuestSystemInfoResponse(BaseModel):
    success: bool
    system_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime


class GuestProcessListResponse(BaseModel):
    success: bool
    processes: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    timestamp: datetime


class GuestHealthCheckResponse(BaseModel):
    success: bool
    health: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime


class GuestServicesResponse(BaseModel):
    success: bool
    services: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    timestamp: datetime


class GuestEventLogsRequest(BaseModel):
    log_name: Optional[str] = Field(default="System", description="Event log name")
    max_events: Optional[int] = Field(default=100, description="Maximum number of events", ge=1, le=1000)


class GuestEventLogsResponse(BaseModel):
    success: bool
    events: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    timestamp: datetime


class GuestShutdownRequest(BaseModel):
    force: Optional[bool] = Field(default=False, description="Force shutdown")
    delay: Optional[int] = Field(default=0, description="Delay in seconds before shutdown")