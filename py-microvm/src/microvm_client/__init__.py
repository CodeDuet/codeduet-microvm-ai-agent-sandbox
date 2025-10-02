"""
py-microvm: Lightweight Python client for MicroVM Sandbox

A secure, simple client for managing MicroVM sandboxes with enterprise security.

Example:
    async with MicroVMClient("https://api.microvm.dev", api_token="token") as client:
        vm = await client.start_vm("ai-agent", {"vcpus": 4})
        result = await client.exec_command(vm.id, "python --version")
        await client.destroy_vm(vm.id)
"""

from .client import MicroVMClient, SecurityValidator
from .exceptions import (
    AuthenticationError,
    MicroVMError,
    NetworkError,
    ValidationError,
    VMNotFoundError,
)
from .models import CommandResult, FileTransferResult, VMInfo, VMState

__version__ = "1.0.0"
__author__ = "CodeDuet MicroVM Sandbox Team"

__all__ = [
    "MicroVMClient",
    "SecurityValidator",
    "VMInfo",
    "VMState",
    "CommandResult",
    "FileTransferResult",
    "MicroVMError",
    "ValidationError",
    "AuthenticationError",
    "NetworkError",
    "VMNotFoundError",
]
