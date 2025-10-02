"""
Core SDK implementation for MicroVM Sandbox.
"""

import asyncio
import httpx
import json
import time
from typing import Optional, List, Dict, Any, AsyncIterator, Union
from pathlib import Path
from datetime import datetime

from .models import (
    SandboxConfig, SandboxInfo, SandboxState, CommandResult, FileTransferResult,
    SnapshotInfo, VNCInfo, SandboxMetrics, SecurityContext, OSType,
    ScreenshotResult, ClickAction, KeyboardAction, ScrollAction, ComputerUseResult
)
from .exceptions import (
    MicroVMSDKError, SandboxNotFoundError, SandboxStateError, CommandExecutionError,
    FileTransferError, AuthenticationError, NetworkError, SnapshotError, VNCError,
    TimeoutError
)


class MicroVMManager:
    """
    High-level manager for MicroVM sandboxes with AI agent support.
    
    Features:
    - Async/await support for all operations
    - Context manager support for automatic cleanup
    - Enterprise security with JWT authentication
    - Comprehensive error handling and logging
    - AI-optimized VM templates and configurations
    """
    
    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        security_context: Optional[SecurityContext] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        self.api_url = api_url.rstrip("/")
        self.security_context = security_context or SecurityContext()
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self._sandboxes: Dict[str, "Sandbox"] = {}
    
    async def __aenter__(self) -> "MicroVMManager":
        """Async context manager entry."""
        await self._init_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with cleanup."""
        await self.cleanup()
    
    async def _init_client(self) -> None:
        """Initialize HTTP client with authentication."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "py-microvm-sdk/1.0.0"
        }
        
        if self.security_context.api_token:
            headers["Authorization"] = f"Bearer {self.security_context.api_token}"
        
        self._client = httpx.AsyncClient(
            base_url=self.api_url,
            headers=headers,
            timeout=self.timeout
        )
        
        # Verify connectivity and authentication
        try:
            response = await self._client.get("/health")
            if response.status_code == 401:
                raise AuthenticationError("Invalid API token")
            elif response.status_code != 200:
                raise NetworkError(f"Server health check failed: {response.status_code}")
        except httpx.RequestError as e:
            raise NetworkError(f"Failed to connect to MicroVM API: {e}")
    
    async def cleanup(self) -> None:
        """Clean up resources and close connections."""
        # Stop all managed sandboxes
        cleanup_tasks = []
        for sandbox in self._sandboxes.values():
            if sandbox.state == SandboxState.RUNNING:
                cleanup_tasks.append(sandbox.destroy())
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        # Close HTTP client
        if self._client:
            await self._client.aclose()
            self._client = None
        
        self._sandboxes.clear()
    
    async def start_sandbox(
        self,
        template: str = "ai-agent",
        name: Optional[str] = None,
        config: Optional[SandboxConfig] = None
    ) -> "Sandbox":
        """
        Start a new sandbox with AI agent capabilities.
        
        Args:
            template: VM template name (ai-agent, code-interpreter, web-automation, etc.)
            name: Optional sandbox name (auto-generated if not provided)
            config: Optional detailed configuration
        
        Returns:
            Sandbox instance ready for AI agent operations
        """
        if not self._client:
            await self._init_client()
        
        # Generate name if not provided
        if not name:
            timestamp = int(time.time())
            name = f"{template}-{timestamp}"
        
        # Create configuration
        if not config:
            config = SandboxConfig(name=name, template=template)
        else:
            config.name = name
            config.template = template
        
        # Create sandbox via API
        try:
            response = await self._client.post("/api/v1/vms", json=config.model_dump())
            if response.status_code != 201:
                raise NetworkError(f"Failed to create sandbox: {response.status_code}")
            
            vm_data = response.json()
            sandbox_info = SandboxInfo(**vm_data)
            
        except httpx.RequestError as e:
            raise NetworkError(f"Failed to create sandbox: {e}")
        except json.JSONDecodeError as e:
            raise MicroVMSDKError(f"Invalid response format: {e}")
        
        # Create and track sandbox instance
        sandbox = Sandbox(self, sandbox_info)
        self._sandboxes[name] = sandbox
        
        # Auto-start if configured
        if config.auto_start:
            await sandbox.start()
        
        return sandbox
    
    async def list_sandboxes(self) -> List[SandboxInfo]:
        """List all available sandboxes."""
        if not self._client:
            await self._init_client()
        
        try:
            response = await self._client.get("/api/v1/vms")
            if response.status_code != 200:
                raise NetworkError(f"Failed to list sandboxes: {response.status_code}")
            
            data = response.json()
            return [SandboxInfo(**vm) for vm in data.get("vms", [])]
            
        except httpx.RequestError as e:
            raise NetworkError(f"Failed to list sandboxes: {e}")
    
    async def get_sandbox(self, name: str) -> "Sandbox":
        """Get existing sandbox by name."""
        if name in self._sandboxes:
            return self._sandboxes[name]
        
        if not self._client:
            await self._init_client()
        
        try:
            response = await self._client.get(f"/api/v1/vms/{name}")
            if response.status_code == 404:
                raise SandboxNotFoundError(name)
            elif response.status_code != 200:
                raise NetworkError(f"Failed to get sandbox: {response.status_code}")
            
            vm_data = response.json()
            sandbox_info = SandboxInfo(**vm_data)
            
            sandbox = Sandbox(self, sandbox_info)
            self._sandboxes[name] = sandbox
            return sandbox
            
        except httpx.RequestError as e:
            raise NetworkError(f"Failed to get sandbox: {e}")
    
    async def delete_sandbox(self, name: str) -> None:
        """Delete a sandbox permanently."""
        if not self._client:
            await self._init_client()
        
        try:
            response = await self._client.delete(f"/api/v1/vms/{name}")
            if response.status_code == 404:
                raise SandboxNotFoundError(name)
            elif response.status_code != 204:
                raise NetworkError(f"Failed to delete sandbox: {response.status_code}")
            
            # Remove from tracking
            if name in self._sandboxes:
                del self._sandboxes[name]
                
        except httpx.RequestError as e:
            raise NetworkError(f"Failed to delete sandbox: {e}")


class Sandbox:
    """
    Individual sandbox instance with AI agent capabilities.
    
    Supports:
    - Command execution with timeout and environment
    - File upload/download with integrity checking
    - Snapshot creation and restoration for backtracking
    - VNC access for visual AI agents
    - Computer use actions (click, type, scroll)
    - Resource monitoring and health checks
    """
    
    def __init__(self, manager: MicroVMManager, info: SandboxInfo):
        self.manager = manager
        self.info = info
        self.name = info.name
        self.state = info.state
    
    async def __aenter__(self) -> "Sandbox":
        """Async context manager entry."""
        if self.state != SandboxState.RUNNING:
            await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.destroy()
    
    async def start(self) -> None:
        """Start the sandbox."""
        if self.state == SandboxState.RUNNING:
            return
        
        try:
            response = await self.manager._client.post(f"/api/v1/vms/{self.name}/start")
            if response.status_code != 200:
                raise NetworkError(f"Failed to start sandbox: {response.status_code}")
            
            self.state = SandboxState.RUNNING
            await self._update_info()
            
        except httpx.RequestError as e:
            raise NetworkError(f"Failed to start sandbox: {e}")
    
    async def stop(self) -> None:
        """Stop the sandbox."""
        if self.state == SandboxState.STOPPED:
            return
        
        try:
            response = await self.manager._client.post(f"/api/v1/vms/{self.name}/stop")
            if response.status_code != 200:
                raise NetworkError(f"Failed to stop sandbox: {response.status_code}")
            
            self.state = SandboxState.STOPPED
            await self._update_info()
            
        except httpx.RequestError as e:
            raise NetworkError(f"Failed to stop sandbox: {e}")
    
    async def destroy(self) -> None:
        """Destroy the sandbox."""
        await self.manager.delete_sandbox(self.name)
    
    async def run_command(
        self,
        command: str,
        timeout: int = 30,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ) -> CommandResult:
        """
        Execute command in sandbox with AI agent optimizations.
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds
            working_dir: Working directory
            env: Environment variables
        
        Returns:
            CommandResult with output and execution details
        """
        if self.state != SandboxState.RUNNING:
            raise SandboxStateError(self.name, self.state, SandboxState.RUNNING)
        
        payload = {
            "command": command,
            "timeout": timeout,
            "working_dir": working_dir,
            "env": env or {}
        }
        
        try:
            start_time = time.time()
            response = await self.manager._client.post(
                f"/api/v1/vms/{self.name}/guest/command",
                json=payload
            )
            execution_time = int((time.time() - start_time) * 1000)
            
            if response.status_code != 200:
                raise CommandExecutionError(command, -1, f"HTTP {response.status_code}")
            
            data = response.json()
            result = CommandResult(
                success=data.get("success", False),
                exit_code=data.get("exit_code"),
                stdout=data.get("stdout"),
                stderr=data.get("stderr"),
                error=data.get("error"),
                execution_time_ms=execution_time,
                timestamp=datetime.now()
            )
            
            if not result.success and result.exit_code != 0:
                raise CommandExecutionError(command, result.exit_code, result.stderr)
            
            return result
            
        except httpx.RequestError as e:
            raise NetworkError(f"Failed to execute command: {e}")
    
    async def upload_file(
        self,
        local_path: Union[str, Path],
        remote_path: str,
        create_dirs: bool = True
    ) -> FileTransferResult:
        """Upload file to sandbox."""
        local_path = Path(local_path)
        if not local_path.exists():
            raise FileTransferError("upload", str(local_path), remote_path, "Local file not found")
        
        try:
            start_time = time.time()
            
            with open(local_path, "rb") as f:
                files = {"file": (local_path.name, f, "application/octet-stream")}
                data = {
                    "remote_path": remote_path,
                    "create_dirs": str(create_dirs).lower()
                }
                
                response = await self.manager._client.post(
                    f"/api/v1/vms/{self.name}/guest/upload",
                    files=files,
                    data=data
                )
            
            transfer_time = int((time.time() - start_time) * 1000)
            
            if response.status_code != 200:
                raise FileTransferError("upload", str(local_path), remote_path, f"HTTP {response.status_code}")
            
            data = response.json()
            return FileTransferResult(
                success=data.get("success", False),
                local_path=str(local_path),
                remote_path=remote_path,
                size_bytes=data.get("size"),
                checksum=data.get("checksum"),
                transfer_time_ms=transfer_time,
                error=data.get("error"),
                timestamp=datetime.now()
            )
            
        except httpx.RequestError as e:
            raise FileTransferError("upload", str(local_path), remote_path, str(e))
    
    async def download_file(
        self,
        remote_path: str,
        local_path: Union[str, Path],
        max_size: int = 10485760  # 10MB default
    ) -> FileTransferResult:
        """Download file from sandbox."""
        local_path = Path(local_path)
        
        try:
            start_time = time.time()
            
            response = await self.manager._client.post(
                f"/api/v1/vms/{self.name}/guest/download",
                json={"remote_path": remote_path, "max_size": max_size}
            )
            
            transfer_time = int((time.time() - start_time) * 1000)
            
            if response.status_code != 200:
                raise FileTransferError("download", str(local_path), remote_path, f"HTTP {response.status_code}")
            
            # Write file content
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(response.content)
            
            return FileTransferResult(
                success=True,
                local_path=str(local_path),
                remote_path=remote_path,
                size_bytes=len(response.content),
                transfer_time_ms=transfer_time,
                timestamp=datetime.now()
            )
            
        except httpx.RequestError as e:
            raise FileTransferError("download", str(local_path), remote_path, str(e))
    
    async def snapshot(self, name: str, description: str = "") -> SnapshotInfo:
        """Create a snapshot for backtracking."""
        payload = {"name": name, "description": description}
        
        try:
            response = await self.manager._client.post(
                f"/api/v1/vms/{self.name}/snapshots",
                json=payload
            )
            
            if response.status_code != 201:
                raise SnapshotError("create", name, f"HTTP {response.status_code}")
            
            data = response.json()
            return SnapshotInfo(**data)
            
        except httpx.RequestError as e:
            raise SnapshotError("create", name, str(e))
    
    async def restore(self, snapshot_id: str) -> None:
        """Restore from snapshot."""
        try:
            response = await self.manager._client.post(
                f"/api/v1/vms/{self.name}/snapshots/{snapshot_id}/restore"
            )
            
            if response.status_code != 200:
                raise SnapshotError("restore", snapshot_id, f"HTTP {response.status_code}")
            
            await self._update_info()
            
        except httpx.RequestError as e:
            raise SnapshotError("restore", snapshot_id, str(e))
    
    async def get_vnc_info(self) -> VNCInfo:
        """Get VNC connection information."""
        try:
            response = await self.manager._client.get(f"/api/v1/vms/{self.name}/vnc")
            
            if response.status_code != 200:
                raise VNCError(f"Failed to get VNC info: {response.status_code}")
            
            data = response.json()
            return VNCInfo(**data)
            
        except httpx.RequestError as e:
            raise VNCError(f"Failed to get VNC info: {e}")
    
    # Computer Use Methods for AI Agents
    async def take_screenshot(self) -> ScreenshotResult:
        """Take screenshot for visual AI agents."""
        try:
            response = await self.manager._client.get(f"/api/v1/vms/{self.name}/screenshot")
            
            if response.status_code != 200:
                return ScreenshotResult(
                    success=False,
                    error=f"HTTP {response.status_code}",
                    timestamp=datetime.now()
                )
            
            return ScreenshotResult(
                success=True,
                image_data=response.content,
                image_format="png",
                timestamp=datetime.now()
            )
            
        except httpx.RequestError as e:
            return ScreenshotResult(
                success=False,
                error=str(e),
                timestamp=datetime.now()
            )
    
    async def click(self, x: int, y: int, button: str = "left", double_click: bool = False) -> ComputerUseResult:
        """Perform mouse click action."""
        action = ClickAction(x=x, y=y, button=button, double_click=double_click)
        
        try:
            response = await self.manager._client.post(
                f"/api/v1/vms/{self.name}/computer-use/click",
                json=action.model_dump()
            )
            
            success = response.status_code == 200
            error = None if success else f"HTTP {response.status_code}"
            
            return ComputerUseResult(
                success=success,
                action_type="click",
                error=error,
                timestamp=datetime.now()
            )
            
        except httpx.RequestError as e:
            return ComputerUseResult(
                success=False,
                action_type="click",
                error=str(e),
                timestamp=datetime.now()
            )
    
    async def type_text(self, text: str) -> ComputerUseResult:
        """Type text into the active window."""
        action = KeyboardAction(text=text)
        
        try:
            response = await self.manager._client.post(
                f"/api/v1/vms/{self.name}/computer-use/type",
                json=action.model_dump()
            )
            
            success = response.status_code == 200
            error = None if success else f"HTTP {response.status_code}"
            
            return ComputerUseResult(
                success=success,
                action_type="type",
                error=error,
                timestamp=datetime.now()
            )
            
        except httpx.RequestError as e:
            return ComputerUseResult(
                success=False,
                action_type="type",
                error=str(e),
                timestamp=datetime.now()
            )
    
    async def scroll(self, x: int, y: int, direction: str, amount: int = 3) -> ComputerUseResult:
        """Perform scroll action."""
        action = ScrollAction(x=x, y=y, direction=direction, amount=amount)
        
        try:
            response = await self.manager._client.post(
                f"/api/v1/vms/{self.name}/computer-use/scroll",
                json=action.model_dump()
            )
            
            success = response.status_code == 200
            error = None if success else f"HTTP {response.status_code}"
            
            return ComputerUseResult(
                success=success,
                action_type="scroll",
                error=error,
                timestamp=datetime.now()
            )
            
        except httpx.RequestError as e:
            return ComputerUseResult(
                success=False,
                action_type="scroll",
                error=str(e),
                timestamp=datetime.now()
            )
    
    async def get_metrics(self) -> SandboxMetrics:
        """Get comprehensive sandbox metrics."""
        try:
            response = await self.manager._client.get(f"/api/v1/vms/{self.name}/metrics")
            
            if response.status_code != 200:
                raise NetworkError(f"Failed to get metrics: {response.status_code}")
            
            data = response.json()
            return SandboxMetrics(**data)
            
        except httpx.RequestError as e:
            raise NetworkError(f"Failed to get metrics: {e}")
    
    async def _update_info(self) -> None:
        """Update sandbox info from server."""
        try:
            response = await self.manager._client.get(f"/api/v1/vms/{self.name}")
            if response.status_code == 200:
                data = response.json()
                self.info = SandboxInfo(**data)
                self.state = self.info.state
        except httpx.RequestError:
            pass  # Ignore update errors