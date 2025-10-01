"""
Guest Client for Host-to-Guest Communication
Provides interface to communicate with guest agents in Linux and Windows VMs.
"""

import asyncio
import json
import socket
import uuid
import logging
import base64
import hashlib
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from src.api.models.vm import OSType
from src.utils.logging import get_logger

logger = get_logger(__name__)


class GuestClientError(Exception):
    """Exception raised by guest client operations."""
    pass


class GuestClient:
    """Client for communicating with guest agents."""
    
    def __init__(self, vm_name: str, os_type: OSType):
        self.vm_name = vm_name
        self.os_type = os_type
        self.connection_timeout = 30
        self.command_timeout = 300
        
        # Connection details based on OS type
        if os_type == OSType.LINUX:
            self.socket_path = f"/tmp/vm-{vm_name}-guest.sock"
        else:  # Windows
            self.pipe_name = f"\\\\.\\pipe\\vm-{vm_name}-guest"
    
    async def ping(self) -> Dict[str, Any]:
        """Ping the guest agent to check connectivity."""
        return await self._send_command("ping", {})
    
    async def execute_command(
        self, 
        command: str, 
        timeout: int = 30,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Execute a command in the guest."""
        params = {
            "command": command,
            "timeout": timeout
        }
        
        if working_dir:
            params["working_dir"] = working_dir
        
        if env:
            params["env"] = env
        
        return await self._send_command("execute", params)
    
    async def upload_file(
        self, 
        local_path: str, 
        remote_path: str, 
        create_dirs: bool = False,
        mode: int = 0o644
    ) -> Dict[str, Any]:
        """Upload a file from host to guest."""
        try:
            # Read local file
            with open(local_path, 'rb') as f:
                content = f.read()
            
            # Encode content
            content_b64 = base64.b64encode(content).decode('ascii')
            
            params = {
                "path": remote_path,
                "content": content_b64,
                "create_dirs": create_dirs,
                "mode": mode
            }
            
            return await self._send_command("upload_file", params)
            
        except FileNotFoundError:
            raise GuestClientError(f"Local file not found: {local_path}")
        except Exception as e:
            raise GuestClientError(f"File upload failed: {e}")
    
    async def download_file(
        self, 
        remote_path: str, 
        local_path: str, 
        max_size: int = 10 * 1024 * 1024
    ) -> Dict[str, Any]:
        """Download a file from guest to host."""
        params = {
            "path": remote_path,
            "max_size": max_size
        }
        
        try:
            response = await self._send_command("download_file", params)
            
            if response.get("success"):
                content_b64 = response.get("content")
                if content_b64:
                    # Decode and save content
                    content = base64.b64decode(content_b64)
                    
                    # Create parent directories if needed
                    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(local_path, 'wb') as f:
                        f.write(content)
                    
                    # Verify checksum if provided
                    expected_checksum = response.get("checksum")
                    if expected_checksum:
                        actual_checksum = hashlib.sha256(content).hexdigest()
                        if actual_checksum != expected_checksum:
                            raise GuestClientError("File checksum mismatch")
            
            return response
            
        except Exception as e:
            raise GuestClientError(f"File download failed: {e}")
    
    async def get_system_info(self) -> Dict[str, Any]:
        """Get guest system information."""
        return await self._send_command("get_system_info", {})
    
    async def get_process_list(self) -> Dict[str, Any]:
        """Get list of running processes in guest."""
        return await self._send_command("get_process_list", {})
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform guest health check."""
        return await self._send_command("health_check", {})
    
    async def shutdown(self, force: bool = False, delay: int = 0) -> Dict[str, Any]:
        """Shutdown the guest system."""
        params = {
            "force": force,
            "delay": delay
        }
        return await self._send_command("shutdown", params)
    
    # Windows-specific methods
    async def get_services(self) -> Dict[str, Any]:
        """Get Windows services (Windows only)."""
        if self.os_type != OSType.WINDOWS:
            raise GuestClientError("get_services is only available on Windows guests")
        
        return await self._send_command("get_services", {})
    
    async def get_event_logs(
        self, 
        log_name: str = "System", 
        max_events: int = 100
    ) -> Dict[str, Any]:
        """Get Windows event logs (Windows only)."""
        if self.os_type != OSType.WINDOWS:
            raise GuestClientError("get_event_logs is only available on Windows guests")
        
        params = {
            "log_name": log_name,
            "max_events": max_events
        }
        return await self._send_command("get_event_logs", params)
    
    async def _send_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command to the guest agent."""
        request_id = str(uuid.uuid4())
        message = {
            "command": command,
            "params": params,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            if self.os_type == OSType.LINUX:
                return await self._send_unix_socket(message)
            else:  # Windows
                return await self._send_named_pipe(message)
        except Exception as e:
            logger.error(f"Failed to send command '{command}' to guest {self.vm_name}: {e}")
            raise GuestClientError(f"Communication failed: {e}")
    
    async def _send_unix_socket(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via Unix socket (Linux)."""
        try:
            # Connect to Unix socket
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.socket_path),
                timeout=self.connection_timeout
            )
            
            try:
                # Send message
                message_data = json.dumps(message).encode('utf-8')
                message_length = len(message_data).to_bytes(4, byteorder='big')
                
                writer.write(message_length + message_data)
                await writer.drain()
                
                # Read response
                length_data = await asyncio.wait_for(
                    reader.read(4), timeout=self.command_timeout
                )
                
                if not length_data:
                    raise GuestClientError("No response from guest")
                
                response_length = int.from_bytes(length_data, byteorder='big')
                response_data = await asyncio.wait_for(
                    reader.read(response_length), timeout=self.command_timeout
                )
                
                if not response_data:
                    raise GuestClientError("Incomplete response from guest")
                
                return json.loads(response_data.decode('utf-8'))
                
            finally:
                writer.close()
                await writer.wait_closed()
                
        except asyncio.TimeoutError:
            raise GuestClientError("Connection timeout")
        except FileNotFoundError:
            raise GuestClientError(f"Guest agent socket not found: {self.socket_path}")
        except json.JSONDecodeError:
            raise GuestClientError("Invalid response format from guest")
    
    async def _send_named_pipe(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via named pipe (Windows)."""
        try:
            import win32file
            import win32pipe
            
            # Connect to named pipe
            handle = win32file.CreateFile(
                self.pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            
            try:
                # Send message
                message_data = json.dumps(message).encode('utf-8')
                win32file.WriteFile(handle, message_data)
                
                # Read response
                result, response_data = win32file.ReadFile(handle, 65536)
                
                if not response_data:
                    raise GuestClientError("No response from guest")
                
                return json.loads(response_data.decode('utf-8'))
                
            finally:
                win32file.CloseHandle(handle)
                
        except ImportError:
            raise GuestClientError("pywin32 not available for Windows pipe communication")
        except Exception as e:
            if "The system cannot find the file specified" in str(e):
                raise GuestClientError(f"Guest agent pipe not found: {self.pipe_name}")
            raise GuestClientError(f"Pipe communication error: {e}")


class GuestManager:
    """Manager for guest client connections."""
    
    def __init__(self):
        self.clients: Dict[str, GuestClient] = {}
    
    def get_client(self, vm_name: str, os_type: OSType) -> GuestClient:
        """Get or create a guest client for a VM."""
        client_key = f"{vm_name}:{os_type.value}"
        
        if client_key not in self.clients:
            self.clients[client_key] = GuestClient(vm_name, os_type)
        
        return self.clients[client_key]
    
    def remove_client(self, vm_name: str, os_type: OSType) -> None:
        """Remove a guest client."""
        client_key = f"{vm_name}:{os_type.value}"
        self.clients.pop(client_key, None)
    
    async def ping_all(self) -> Dict[str, Dict[str, Any]]:
        """Ping all registered guest clients."""
        results = {}
        
        for client_key, client in self.clients.items():
            try:
                result = await client.ping()
                results[client_key] = result
            except Exception as e:
                results[client_key] = {
                    "success": False,
                    "error": str(e)
                }
        
        return results
    
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Perform health check on all registered guest clients."""
        results = {}
        
        for client_key, client in self.clients.items():
            try:
                result = await client.health_check()
                results[client_key] = result
            except Exception as e:
                results[client_key] = {
                    "success": False,
                    "error": str(e)
                }
        
        return results


# Global guest manager instance
guest_manager = GuestManager()