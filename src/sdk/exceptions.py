"""
Exception classes for py-microvm SDK.
"""

from typing import Optional, Dict, Any


class MicroVMSDKError(Exception):
    """Base exception for MicroVM SDK errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class SandboxNotFoundError(MicroVMSDKError):
    """Raised when a sandbox is not found."""
    
    def __init__(self, sandbox_name: str):
        super().__init__(f"Sandbox '{sandbox_name}' not found")
        self.sandbox_name = sandbox_name


class SandboxStateError(MicroVMSDKError):
    """Raised when sandbox is in invalid state for operation."""
    
    def __init__(self, sandbox_name: str, current_state: str, required_state: str):
        super().__init__(
            f"Sandbox '{sandbox_name}' is in state '{current_state}' but requires '{required_state}'"
        )
        self.sandbox_name = sandbox_name
        self.current_state = current_state
        self.required_state = required_state


class CommandExecutionError(MicroVMSDKError):
    """Raised when command execution fails."""
    
    def __init__(self, command: str, exit_code: int, stderr: Optional[str] = None):
        message = f"Command '{command}' failed with exit code {exit_code}"
        if stderr:
            message += f": {stderr}"
        super().__init__(message)
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr


class FileTransferError(MicroVMSDKError):
    """Raised when file transfer operations fail."""
    
    def __init__(self, operation: str, local_path: str, remote_path: str, reason: str):
        super().__init__(f"File {operation} failed: {local_path} <-> {remote_path}: {reason}")
        self.operation = operation
        self.local_path = local_path
        self.remote_path = remote_path
        self.reason = reason


class AuthenticationError(MicroVMSDKError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message)


class NetworkError(MicroVMSDKError):
    """Raised when network operations fail."""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class SnapshotError(MicroVMSDKError):
    """Raised when snapshot operations fail."""
    
    def __init__(self, operation: str, snapshot_name: str, reason: str):
        super().__init__(f"Snapshot {operation} failed for '{snapshot_name}': {reason}")
        self.operation = operation
        self.snapshot_name = snapshot_name
        self.reason = reason


class VNCError(MicroVMSDKError):
    """Raised when VNC operations fail."""
    
    def __init__(self, message: str):
        super().__init__(f"VNC error: {message}")


class ResourceError(MicroVMSDKError):
    """Raised when resource allocation fails."""
    
    def __init__(self, resource_type: str, requested: Any, available: Any):
        super().__init__(
            f"Insufficient {resource_type}: requested {requested}, available {available}"
        )
        self.resource_type = resource_type
        self.requested = requested
        self.available = available


class TimeoutError(MicroVMSDKError):
    """Raised when operations timeout."""
    
    def __init__(self, operation: str, timeout_seconds: int):
        super().__init__(f"Operation '{operation}' timed out after {timeout_seconds} seconds")
        self.operation = operation
        self.timeout_seconds = timeout_seconds