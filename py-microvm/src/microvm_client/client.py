"""
Secure, lightweight MicroVM client implementation.
"""

import os.path
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import httpx

from .exceptions import (
    AuthenticationError,
    NetworkError,
    ValidationError,
    VMNotFoundError,
)
from .models import CommandResult, FileTransferResult, VMInfo


class SecurityValidator:
    """Input validation and security checks."""

    @staticmethod
    def validate_command(command: str) -> str:
        """Validate command for security."""
        if not command or len(command.strip()) == 0:
            raise ValidationError("Command cannot be empty")

        if len(command) > 10000:
            raise ValidationError("Command too long")

        # Block dangerous patterns
        dangerous_patterns = [
            r"[;&|`$()]",  # Shell metacharacters
            r"sudo|su\s+",  # Privilege escalation
            r"rm\s+-rf",  # Destructive commands
            r"dd\s+if=",  # Disk operations
            r"mkfs\.",  # Filesystem operations
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                raise ValidationError(f"Command contains forbidden pattern: {pattern}")

        return command.strip()

    @staticmethod
    def validate_path(path: str) -> str:
        """Validate file path for security."""
        if not path:
            raise ValidationError("Path cannot be empty")

        # Normalize path
        normalized = os.path.normpath(path)

        # Block path traversal
        if (
            ".." in normalized
            or normalized.startswith("/etc")
            or normalized.startswith("/usr")
        ):
            raise ValidationError("Path traversal or system directory access denied")

        return normalized

    @staticmethod
    def validate_vm_name(name: str) -> str:
        """Validate VM name."""
        if not name or not re.match(r"^[a-zA-Z0-9_-]+$", name):
            raise ValidationError(
                "VM name must contain only alphanumeric, underscore, "
                "and hyphen characters"
            )

        if len(name) > 64:
            raise ValidationError("VM name too long")

        return name


class MicroVMClient:
    """Lightweight, secure MicroVM client."""

    def __init__(
        self,
        api_url: str,
        api_token: Optional[str] = None,
        timeout: int = 30,
        verify_ssl: bool = True,
    ):
        # Enforce HTTPS for non-localhost
        parsed = urlparse(api_url)
        if parsed.scheme == "http" and parsed.hostname not in (
            "localhost",
            "127.0.0.1",
        ):
            raise ValidationError("HTTPS required for non-localhost connections")

        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        # Setup headers
        headers = {"Content-Type": "application/json"}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        # HTTP client with security settings
        self._client = httpx.AsyncClient(
            base_url=self.api_url,
            headers=headers,
            timeout=self.timeout,
            verify=self.verify_ssl,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    async def __aenter__(self) -> "MicroVMClient":
        """Async context manager entry."""
        # Verify connectivity and auth
        try:
            response = await self._client.get("/health")
            if response.status_code == 401:
                raise AuthenticationError("Invalid API token")
            elif response.status_code != 200:
                raise NetworkError(f"Health check failed: {response.status_code}")
        except httpx.RequestError as e:
            raise NetworkError(f"Connection failed: {e}") from e

        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[object],
    ) -> None:
        """Async context manager exit."""
        await self._client.aclose()

    async def start_vm(
        self, template: str, config: Optional[Dict[str, Any]] = None
    ) -> VMInfo:
        """Start a new VM."""
        # Validate template name
        if not re.match(r"^[a-zA-Z0-9_-]+$", template):
            raise ValidationError("Invalid template name")

        payload = {"template": template}
        if config:
            payload.update(config)

        try:
            response = await self._client.post("/api/v1/vms", json=payload)
            if response.status_code == 401:
                raise AuthenticationError("Authentication required")
            elif response.status_code != 201:
                raise NetworkError(f"VM creation failed: {response.status_code}")

            data = response.json()
            return VMInfo(**data)

        except httpx.RequestError as e:
            raise NetworkError(f"Request failed: {e}") from e

    async def list_vms(self) -> List[VMInfo]:
        """List all VMs."""
        try:
            response = await self._client.get("/api/v1/vms")
            if response.status_code != 200:
                raise NetworkError(f"List VMs failed: {response.status_code}")

            data = response.json()
            return [VMInfo(**vm) for vm in data.get("vms", [])]

        except httpx.RequestError as e:
            raise NetworkError(f"Request failed: {e}") from e

    async def get_vm(self, vm_id: str) -> VMInfo:
        """Get VM information."""
        vm_id = SecurityValidator.validate_vm_name(vm_id)

        try:
            response = await self._client.get(f"/api/v1/vms/{vm_id}")
            if response.status_code == 404:
                raise VMNotFoundError(vm_id)
            elif response.status_code != 200:
                raise NetworkError(f"Get VM failed: {response.status_code}")

            data = response.json()
            return VMInfo(**data)

        except httpx.RequestError as e:
            raise NetworkError(f"Request failed: {e}") from e

    async def exec_command(
        self, vm_id: str, command: str, timeout: int = 30
    ) -> CommandResult:
        """Execute command in VM."""
        vm_id = SecurityValidator.validate_vm_name(vm_id)
        command = SecurityValidator.validate_command(command)

        if not 1 <= timeout <= 300:
            raise ValidationError("Timeout must be between 1-300 seconds")

        payload = {"command": command, "timeout": timeout}

        try:
            response = await self._client.post(
                f"/api/v1/vms/{vm_id}/guest/command", json=payload
            )
            if response.status_code == 404:
                raise VMNotFoundError(vm_id)
            elif response.status_code != 200:
                raise NetworkError(f"Command execution failed: {response.status_code}")

            data = response.json()
            return CommandResult(**data)

        except httpx.RequestError as e:
            raise NetworkError(f"Request failed: {e}") from e

    async def upload_file(
        self, vm_id: str, local_path: Union[str, Path], remote_path: str
    ) -> FileTransferResult:
        """Upload file to VM."""
        vm_id = SecurityValidator.validate_vm_name(vm_id)
        remote_path = SecurityValidator.validate_path(remote_path)

        local_path = Path(local_path)
        if not local_path.exists():
            raise ValidationError(f"Local file not found: {local_path}")

        # 10MB size limit
        if local_path.stat().st_size > 10 * 1024 * 1024:
            raise ValidationError("File too large (max 10MB)")

        try:
            with open(local_path, "rb") as f:
                files = {"file": (local_path.name, f, "application/octet-stream")}
                data = {"remote_path": remote_path}

                response = await self._client.post(
                    f"/api/v1/vms/{vm_id}/guest/upload", files=files, data=data
                )

            if response.status_code == 404:
                raise VMNotFoundError(vm_id)
            elif response.status_code != 200:
                raise NetworkError(f"File upload failed: {response.status_code}")

            data = response.json()
            return FileTransferResult(**data)

        except httpx.RequestError as e:
            raise NetworkError(f"Request failed: {e}") from e

    async def destroy_vm(self, vm_id: str) -> None:
        """Destroy VM."""
        vm_id = SecurityValidator.validate_vm_name(vm_id)

        try:
            response = await self._client.delete(f"/api/v1/vms/{vm_id}")
            if response.status_code == 404:
                raise VMNotFoundError(vm_id)
            elif response.status_code != 204:
                raise NetworkError(f"VM destruction failed: {response.status_code}")

        except httpx.RequestError as e:
            raise NetworkError(f"Request failed: {e}") from e
