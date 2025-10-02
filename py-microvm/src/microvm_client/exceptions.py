"""
Secure exception classes for py-microvm client.
"""

from typing import Optional


class MicroVMError(Exception):
    """Base exception for MicroVM client errors."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(MicroVMError):
    """Input validation failed."""

    pass


class AuthenticationError(MicroVMError):
    """Authentication failed."""

    pass


class NetworkError(MicroVMError):
    """Network operation failed."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class VMNotFoundError(MicroVMError):
    """VM not found."""

    def __init__(self, vm_id: str):
        super().__init__(f"VM '{vm_id}' not found")
        self.vm_id = vm_id
