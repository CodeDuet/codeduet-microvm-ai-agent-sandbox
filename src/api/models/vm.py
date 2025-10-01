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