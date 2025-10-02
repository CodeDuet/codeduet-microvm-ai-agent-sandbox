"""
py-microvm: Enterprise Python SDK for MicroVM Sandbox
====================================================

A high-level Python SDK for managing MicroVM sandboxes with AI agent integration.
Provides async/await support, context managers, and enterprise security features.

Example Usage:
    Basic VM management:
        from microvm_sdk import MicroVMManager
        
        async with MicroVMManager("http://localhost:8000") as manager:
            async with manager.start_sandbox("ai-agent") as sandbox:
                result = await sandbox.run_command("python --version")
                print(result.output)
    
    AI agent execution:
        async with manager.start_sandbox("ai-agent") as sandbox:
            # Upload code
            await sandbox.upload_file("script.py", "/tmp/script.py")
            
            # Execute with timeout
            result = await sandbox.run_command("python /tmp/script.py", timeout=60)
            
            # Snapshot for backtracking
            snapshot = await sandbox.snapshot("before-modification")
            
            # Make changes and restore if needed
            await sandbox.restore(snapshot.id)
"""

from .microvm_sdk import MicroVMManager, Sandbox
from .models import (
    SandboxInfo,
    CommandResult,
    SnapshotInfo,
    VNCInfo,
    FileTransferResult,
    SandboxConfig,
    SecurityContext
)
from .exceptions import (
    MicroVMSDKError,
    SandboxNotFoundError,
    SandboxStateError,
    CommandExecutionError,
    FileTransferError,
    AuthenticationError
)

__version__ = "1.0.0"
__author__ = "MicroVM Sandbox Team"
__email__ = "support@microvm-sandbox.dev"

__all__ = [
    # Core classes
    "MicroVMManager",
    "Sandbox",
    
    # Data models
    "SandboxInfo",
    "CommandResult", 
    "SnapshotInfo",
    "VNCInfo",
    "FileTransferResult",
    "SandboxConfig",
    "SecurityContext",
    
    # Exceptions
    "MicroVMSDKError",
    "SandboxNotFoundError",
    "SandboxStateError",
    "CommandExecutionError",
    "FileTransferError",
    "AuthenticationError",
]