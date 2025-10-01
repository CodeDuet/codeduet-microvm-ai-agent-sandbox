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


# Resource Management Models
class ResourceQuotaRequest(BaseModel):
    max_vcpus: int = Field(..., description="Maximum vCPUs allowed", ge=1, le=32)
    max_memory_mb: int = Field(..., description="Maximum memory in MB", ge=512, le=32768)
    max_disk_gb: int = Field(..., description="Maximum disk space in GB", ge=1, le=1000)
    max_vms: int = Field(..., description="Maximum number of VMs", ge=1, le=100)
    priority: int = Field(default=1, description="Priority level (1-10)", ge=1, le=10)


class ResourceQuotaResponse(BaseModel):
    max_vcpus: int
    max_memory_mb: int
    max_disk_gb: int
    max_vms: int
    priority: int


class ResourceAllocationRequest(BaseModel):
    vcpus: int = Field(..., description="Number of vCPUs to allocate", ge=1, le=32)
    memory_mb: int = Field(..., description="Memory to allocate in MB", ge=512, le=32768)
    disk_gb: int = Field(default=10, description="Disk space to allocate in GB", ge=1, le=1000)
    priority: int = Field(default=1, description="Priority level (1-10)", ge=1, le=10)


class ResourceAllocationResponse(BaseModel):
    vm_name: str
    vcpus: int
    memory_mb: int
    disk_gb: int
    priority: int
    cpu_usage_percent: float
    memory_usage_percent: float
    allocated_at: datetime
    last_updated: datetime


class ResourceUsageUpdateRequest(BaseModel):
    cpu_usage_percent: float = Field(..., description="CPU usage percentage", ge=0, le=100)
    memory_usage_percent: float = Field(..., description="Memory usage percentage", ge=0, le=100)


class SystemResourceUsageResponse(BaseModel):
    total_vcpus: int
    available_vcpus: int
    used_vcpus: int
    total_memory_mb: int
    available_memory_mb: int
    used_memory_mb: int
    total_disk_gb: int
    available_disk_gb: int
    used_disk_gb: int
    active_vms: int
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    load_average: List[float]
    timestamp: datetime


class ResourceRecommendationResponse(BaseModel):
    vm_name: str
    recommended_vcpus: int
    recommended_memory_mb: int
    current_vcpus: int
    current_memory_mb: int
    reason: str
    urgency: str
    estimated_savings_percent: float


class ResourceRecommendationsResponse(BaseModel):
    recommendations: List[ResourceRecommendationResponse]
    generated_at: datetime


class ResourceResizeRequest(BaseModel):
    new_vcpus: Optional[int] = Field(default=None, description="New number of vCPUs", ge=1, le=32)
    new_memory_mb: Optional[int] = Field(default=None, description="New memory in MB", ge=512, le=32768)


class ResourceMetricsResponse(BaseModel):
    system_usage: SystemResourceUsageResponse
    allocations: List[ResourceAllocationResponse]
    quotas: Dict[str, ResourceQuotaResponse]
    optimization_enabled: bool
    scaling_enabled: bool
    monitoring_enabled: bool


class AutoScaleResponse(BaseModel):
    scaled_vms: List[str]
    total_scaled: int
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Error details")
    code: Optional[str] = Field(None, description="Error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")