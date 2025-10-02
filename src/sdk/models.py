"""
Data models for py-microvm SDK.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class SandboxState(str, Enum):
    """Sandbox state enumeration."""
    CREATING = "creating"
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class OSType(str, Enum):
    """Operating system type enumeration."""
    LINUX = "linux"
    WINDOWS = "windows"


class SandboxConfig(BaseModel):
    """Configuration for creating a sandbox."""
    name: str = Field(..., description="Sandbox name")
    template: str = Field(default="ai-agent", description="VM template to use")
    vcpus: int = Field(default=4, description="Number of vCPUs", ge=1, le=16)
    memory_mb: int = Field(default=4096, description="Memory in MB", ge=512, le=16384)
    os_type: OSType = Field(default=OSType.LINUX, description="Operating system type")
    guest_agent: bool = Field(default=True, description="Enable guest agent")
    vnc_enabled: bool = Field(default=False, description="Enable VNC server")
    auto_start: bool = Field(default=True, description="Auto-start sandbox after creation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata")


class SecurityContext(BaseModel):
    """Security context for SDK operations."""
    api_token: Optional[str] = Field(None, description="API authentication token")
    user_id: Optional[str] = Field(None, description="User identifier")
    role: Optional[str] = Field(None, description="User role")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    audit_enabled: bool = Field(default=True, description="Enable audit logging")


class SandboxInfo(BaseModel):
    """Information about a sandbox."""
    name: str
    state: SandboxState
    vcpus: int
    memory_mb: int
    os_type: OSType
    template: str
    guest_agent: bool
    vnc_enabled: bool
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]
    
    # Extended info for AI agents
    ip_address: Optional[str] = None
    vnc_port: Optional[int] = None
    guest_agent_port: Optional[int] = None
    uptime_seconds: Optional[int] = None


class CommandResult(BaseModel):
    """Result of command execution in sandbox."""
    success: bool
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
    timestamp: datetime
    
    @property
    def output(self) -> str:
        """Get combined output (stdout preferred)."""
        return self.stdout or self.stderr or ""


class FileTransferResult(BaseModel):
    """Result of file transfer operation."""
    success: bool
    local_path: str
    remote_path: str
    size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    transfer_time_ms: Optional[int] = None
    error: Optional[str] = None
    timestamp: datetime


class SnapshotInfo(BaseModel):
    """Information about a VM snapshot."""
    id: str
    name: str
    sandbox_name: str
    description: str
    size_bytes: int
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Snapshot hierarchy for AI agent backtracking
    parent_snapshot_id: Optional[str] = None
    child_snapshot_ids: List[str] = Field(default_factory=list)


class VNCInfo(BaseModel):
    """VNC connection information."""
    enabled: bool
    host: str
    port: int
    password: Optional[str] = None
    web_url: Optional[str] = None
    resolution: Optional[str] = None
    color_depth: Optional[int] = None


class SystemInfo(BaseModel):
    """System information from guest."""
    os_name: str
    os_version: str
    hostname: str
    cpu_count: int
    memory_total_mb: int
    memory_available_mb: int
    disk_total_gb: int
    disk_available_gb: int
    uptime_seconds: int
    timestamp: datetime


class ProcessInfo(BaseModel):
    """Process information."""
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    status: str
    started_at: Optional[datetime] = None


class HealthStatus(BaseModel):
    """Health status of sandbox."""
    healthy: bool
    checks: Dict[str, bool]
    last_check: datetime
    uptime_seconds: int
    response_time_ms: int


class ResourceUsage(BaseModel):
    """Resource usage statistics."""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_rx_bytes: int
    network_tx_bytes: int
    timestamp: datetime


class SandboxMetrics(BaseModel):
    """Comprehensive sandbox metrics."""
    sandbox_info: SandboxInfo
    system_info: Optional[SystemInfo] = None
    resource_usage: Optional[ResourceUsage] = None
    health_status: Optional[HealthStatus] = None
    running_processes: List[ProcessInfo] = Field(default_factory=list)


# Computer Use Models for AI Agents
class ScreenshotResult(BaseModel):
    """Result of taking a screenshot."""
    success: bool
    image_data: Optional[bytes] = None
    image_format: str = "png"
    width: Optional[int] = None
    height: Optional[int] = None
    error: Optional[str] = None
    timestamp: datetime


class ClickAction(BaseModel):
    """Mouse click action."""
    x: int
    y: int
    button: str = Field(default="left", description="Mouse button: left, right, middle")
    double_click: bool = Field(default=False, description="Perform double click")


class KeyboardAction(BaseModel):
    """Keyboard input action."""
    text: Optional[str] = None
    key: Optional[str] = None
    modifiers: List[str] = Field(default_factory=list, description="Modifier keys: ctrl, alt, shift")


class ScrollAction(BaseModel):
    """Scroll action."""
    x: int
    y: int
    direction: str = Field(..., description="Scroll direction: up, down, left, right")
    amount: int = Field(default=3, description="Scroll amount")


class ComputerUseResult(BaseModel):
    """Result of computer use action."""
    success: bool
    action_type: str
    error: Optional[str] = None
    timestamp: datetime