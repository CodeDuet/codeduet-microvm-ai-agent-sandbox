"""
Essential data models for py-microvm client.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class VMState(str, Enum):
    """VM state enumeration."""

    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"


class VMInfo(BaseModel):
    """VM information."""

    id: str
    name: str
    state: VMState
    template: str
    vcpus: int
    memory_mb: int
    ip_address: Optional[str] = None
    created_at: datetime


class CommandResult(BaseModel):
    """Command execution result."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time_ms: int


class FileTransferResult(BaseModel):
    """File transfer result."""

    success: bool
    size_bytes: int
    checksum: Optional[str] = None
