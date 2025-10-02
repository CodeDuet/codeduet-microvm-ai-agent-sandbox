"""
VNC Manager for MicroVM GUI access and control.

Provides VNC server management, session control, and screenshot capabilities
for visual AI agents and desktop automation.
"""

import asyncio
import json
import subprocess
import signal
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import base64
import socket
import tempfile

from src.utils.config import get_settings
from src.utils.logging import get_logger
from src.utils.helpers import run_subprocess, generate_password

logger = get_logger(__name__)


class VNCSession:
    """Represents an active VNC session."""
    
    def __init__(self, vm_name: str, display: int, port: int, password: Optional[str] = None, 
                 vnc_type: str = "guest", os_type: str = "linux"):
        self.vm_name = vm_name
        self.display = display
        self.port = port
        self.password = password
        self.vnc_type = vnc_type  # "guest" for Linux, "hypervisor" for Windows
        self.os_type = os_type    # "linux" or "windows"
        self.created_at = datetime.now()
        self.process: Optional[subprocess.Popen] = None
        self.connection_count = 0
        self.last_activity = datetime.now()


class VNCManager:
    """
    Manages VNC servers for MicroVM desktop access.
    
    Handles VNC server lifecycle, authentication, and provides tools for
    visual AI agents to interact with desktop environments.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.sessions: Dict[str, VNCSession] = {}
        self.vnc_data_dir = Path("data/vnc")
        self.vnc_data_dir.mkdir(parents=True, exist_ok=True)
        
        # VNC configuration
        self.vnc_base_port = getattr(self.settings, 'vnc_base_port', 5900)
        self.vnc_display_base = getattr(self.settings, 'vnc_display_base', 10)
        self.max_sessions = getattr(self.settings, 'max_vnc_sessions', 50)
        
        logger.info("VNC Manager initialized")
    
    async def start_vnc_server(self, vm_name: str, config: Dict[str, Any], vm_config: Optional[Dict[str, Any]] = None) -> VNCSession:
        """
        Start VNC server for a MicroVM.
        
        Args:
            vm_name: Name of the VM
            config: VNC configuration from VM template
            vm_config: Full VM configuration to determine OS type
            
        Returns:
            VNCSession object
        """
        if vm_name in self.sessions:
            logger.warning(f"VNC session already exists for VM '{vm_name}'")
            return self.sessions[vm_name]
        
        # Determine OS type and VNC approach
        is_windows = vm_config and "firmware" in vm_config
        os_type = "windows" if is_windows else "linux"
        vnc_type = "hypervisor" if is_windows else "guest"
        
        # For Windows VMs, use the port configured in Cloud Hypervisor
        if is_windows:
            port = config.get('port', 5900)
            display = port - self.vnc_base_port
        else:
            # Allocate display and port for Linux VMs
            display = await self._allocate_display()
            port = self.vnc_base_port + display
        
        # Generate password if not provided
        password = config.get('password')
        if not password:
            password = generate_password(12)
        
        logger.info(f"Starting {vnc_type} VNC server for {os_type} VM '{vm_name}' on port {port}")
        
        # Create VNC session
        session = VNCSession(vm_name, display, port, password, vnc_type, os_type)
        
        try:
            # Configure VNC server based on VM type
            if is_windows:
                await self._configure_windows_vnc(vm_name, session, config)
            else:
                await self._configure_vnc_for_vm(vm_name, session, config)
                # Start VNC server process for Linux VMs
                await self._start_vnc_process(session, config)
            
            # Store session
            self.sessions[vm_name] = session
            await self._save_session_data(session)
            
            logger.info(f"{vnc_type.title()} VNC server started for VM '{vm_name}' - Port: {port}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to start VNC server for VM '{vm_name}': {e}")
            if session.process:
                await self._stop_vnc_process(session)
            raise
    
    async def stop_vnc_server(self, vm_name: str) -> None:
        """Stop VNC server for a VM."""
        if vm_name not in self.sessions:
            logger.warning(f"No VNC session found for VM '{vm_name}'")
            return
        
        session = self.sessions[vm_name]
        logger.info(f"Stopping VNC server for VM '{vm_name}' (display :{session.display})")
        
        try:
            await self._stop_vnc_process(session)
            
            # Cleanup session data
            del self.sessions[vm_name]
            session_file = self.vnc_data_dir / f"{vm_name}.json"
            if session_file.exists():
                session_file.unlink()
                
            logger.info(f"VNC server stopped for VM '{vm_name}'")
            
        except Exception as e:
            logger.error(f"Error stopping VNC server for VM '{vm_name}': {e}")
            raise
    
    async def get_vnc_info(self, vm_name: str) -> Optional[Dict[str, Any]]:
        """Get VNC connection information for a VM."""
        if vm_name not in self.sessions:
            return None
        
        session = self.sessions[vm_name]
        
        # Check if process is still running
        if session.process and session.process.poll() is not None:
            logger.warning(f"VNC process for VM '{vm_name}' has terminated")
            await self.stop_vnc_server(vm_name)
            return None
        
        return {
            "vm_name": vm_name,
            "display": session.display,
            "port": session.port,
            "password": session.password,
            "vnc_type": session.vnc_type,
            "os_type": session.os_type,
            "created_at": session.created_at.isoformat(),
            "connection_count": session.connection_count,
            "last_activity": session.last_activity.isoformat(),
            "status": "running" if session.process or session.vnc_type == "hypervisor" else "stopped"
        }
    
    async def list_vnc_sessions(self) -> List[Dict[str, Any]]:
        """List all active VNC sessions."""
        sessions = []
        for vm_name in list(self.sessions.keys()):
            info = await self.get_vnc_info(vm_name)
            if info:
                sessions.append(info)
        return sessions
    
    async def take_screenshot(self, vm_name: str, format: str = "png") -> Optional[bytes]:
        """
        Take a screenshot of the VNC session.
        
        Args:
            vm_name: Name of the VM
            format: Image format (png, jpeg)
            
        Returns:
            Screenshot image data
        """
        if vm_name not in self.sessions:
            raise ValueError(f"No VNC session found for VM '{vm_name}'")
        
        session = self.sessions[vm_name]
        
        try:
            # Use xwd to capture the display
            cmd = [
                "xwd",
                "-display", f":{session.display}",
                "-root",
                "-silent"
            ]
            
            logger.debug(f"Taking screenshot of VM '{vm_name}' display :{session.display}")
            
            # Capture screenshot
            result = await run_subprocess(cmd, capture_output=True)
            if result.returncode != 0:
                raise RuntimeError(f"Screenshot capture failed: {result.stderr}")
            
            # Convert to desired format if needed
            if format.lower() == "png":
                # Convert XWD to PNG using ImageMagick
                convert_cmd = ["convert", "xwd:-", "png:-"]
                convert_result = await run_subprocess(
                    convert_cmd, 
                    input=result.stdout,
                    capture_output=True
                )
                if convert_result.returncode != 0:
                    raise RuntimeError(f"Screenshot conversion failed: {convert_result.stderr}")
                
                session.last_activity = datetime.now()
                return convert_result.stdout
            
            # Return raw XWD data
            session.last_activity = datetime.now()
            return result.stdout
            
        except Exception as e:
            logger.error(f"Failed to take screenshot for VM '{vm_name}': {e}")
            raise
    
    async def send_key_combination(self, vm_name: str, keys: str) -> None:
        """
        Send key combination to VNC session.
        
        Args:
            vm_name: Name of the VM
            keys: Key combination (e.g., "ctrl+alt+t", "alt+F4")
        """
        if vm_name not in self.sessions:
            raise ValueError(f"No VNC session found for VM '{vm_name}'")
        
        session = self.sessions[vm_name]
        
        try:
            if session.vnc_type == "hypervisor":
                # For Windows VMs using hypervisor VNC, use VNC protocol
                await self._send_vnc_keys(session, keys)
            else:
                # For Linux VMs using guest VNC, use xdotool
                cmd = [
                    "xdotool",
                    "key",
                    "--display", f":{session.display}",
                    keys
                ]
                
                logger.debug(f"Sending keys '{keys}' to VM '{vm_name}' display :{session.display}")
                
                result = await run_subprocess(cmd)
                if result.returncode != 0:
                    raise RuntimeError(f"Failed to send keys: {result.stderr}")
            
            session.last_activity = datetime.now()
            
        except Exception as e:
            logger.error(f"Failed to send keys to VM '{vm_name}': {e}")
            raise
    
    async def mouse_click(self, vm_name: str, x: int, y: int, button: int = 1) -> None:
        """
        Perform mouse click on VNC session.
        
        Args:
            vm_name: Name of the VM
            x, y: Click coordinates
            button: Mouse button (1=left, 2=middle, 3=right)
        """
        if vm_name not in self.sessions:
            raise ValueError(f"No VNC session found for VM '{vm_name}'")
        
        session = self.sessions[vm_name]
        
        try:
            if session.vnc_type == "hypervisor":
                # For Windows VMs using hypervisor VNC, use VNC protocol
                await self._send_vnc_mouse_click(session, x, y, button)
            else:
                # For Linux VMs using guest VNC, use xdotool
                cmd = [
                    "xdotool",
                    "--display", f":{session.display}",
                    "mousemove", str(x), str(y),
                    "click", str(button)
                ]
                
                logger.debug(f"Mouse click at ({x}, {y}) button {button} on VM '{vm_name}'")
                
                result = await run_subprocess(cmd)
                if result.returncode != 0:
                    raise RuntimeError(f"Mouse click failed: {result.stderr}")
            
            session.last_activity = datetime.now()
            
        except Exception as e:
            logger.error(f"Failed to perform mouse click on VM '{vm_name}': {e}")
            raise
    
    async def type_text(self, vm_name: str, text: str) -> None:
        """
        Type text into VNC session.
        
        Args:
            vm_name: Name of the VM
            text: Text to type
        """
        if vm_name not in self.sessions:
            raise ValueError(f"No VNC session found for VM '{vm_name}'")
        
        session = self.sessions[vm_name]
        
        try:
            # Use xdotool to type text
            cmd = [
                "xdotool",
                "--display", f":{session.display}",
                "type", text
            ]
            
            logger.debug(f"Typing text to VM '{vm_name}': {text[:50]}{'...' if len(text) > 50 else ''}")
            
            result = await run_subprocess(cmd)
            if result.returncode != 0:
                raise RuntimeError(f"Text typing failed: {result.stderr}")
            
            session.last_activity = datetime.now()
            
        except Exception as e:
            logger.error(f"Failed to type text to VM '{vm_name}': {e}")
            raise
    
    async def cleanup_all_sessions(self) -> None:
        """Cleanup all VNC sessions."""
        logger.info("Cleaning up all VNC sessions")
        
        for vm_name in list(self.sessions.keys()):
            try:
                await self.stop_vnc_server(vm_name)
            except Exception as e:
                logger.warning(f"Error cleaning up VNC session for '{vm_name}': {e}")
        
        logger.info("VNC cleanup complete")
    
    async def _allocate_display(self) -> int:
        """Allocate an available display number."""
        used_displays = {session.display for session in self.sessions.values()}
        
        for display in range(self.vnc_display_base, self.vnc_display_base + self.max_sessions):
            if display not in used_displays:
                # Check if port is actually available
                port = self.vnc_base_port + display
                if await self._is_port_available(port):
                    return display
        
        raise RuntimeError("No available VNC displays")
    
    async def _is_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('localhost', port))
                return True
        except OSError:
            return False
    
    async def _configure_vnc_for_vm(self, vm_name: str, session: VNCSession, config: Dict[str, Any]) -> None:
        """Configure VNC server for specific VM requirements."""
        # Create VNC password file
        passwd_file = self.vnc_data_dir / f"{vm_name}.passwd"
        
        # Use vncpasswd to create password file
        vncpasswd_cmd = ["vncpasswd", "-f"]
        result = await run_subprocess(
            vncpasswd_cmd,
            input=f"{session.password}\n{session.password}\n".encode(),
            capture_output=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create VNC password file: {result.stderr}")
        
        # Write password file
        passwd_file.write_bytes(result.stdout)
        passwd_file.chmod(0o600)
        
        logger.debug(f"VNC password file created for VM '{vm_name}'")
    
    async def _configure_windows_vnc(self, vm_name: str, session: VNCSession, config: Dict[str, Any]) -> None:
        """Configure Windows VNC access via hypervisor console."""
        # For Windows VMs, VNC is handled by Cloud Hypervisor's built-in console
        # No additional configuration needed since it's managed by the hypervisor
        logger.debug(f"Windows VNC configured for VM '{vm_name}' via hypervisor console")
        
        # Note: Windows VNC access is provided directly by Cloud Hypervisor
        # The VNC server is automatically started when the VM boots with --console vnc=port
        # No separate process management needed for Windows VNC
    
    async def _start_vnc_process(self, session: VNCSession, config: Dict[str, Any]) -> None:
        """Start the VNC server process."""
        passwd_file = self.vnc_data_dir / f"{session.vm_name}.passwd"
        
        # Configure VNC server command
        resolution = config.get('resolution', '1920x1080')
        color_depth = config.get('color_depth', 24)
        
        cmd = [
            "x11vnc",
            "-display", f":{session.display}",
            "-rfbport", str(session.port),
            "-passwd", str(passwd_file),
            "-forever",
            "-shared",
            "-noxdamage",
            "-noxfixes",
            "-noxrandr",
            "-wait", "5",
            "-defer", "5",
            "-gone", "chvt 12",
            "-logfile", str(self.vnc_data_dir / f"{session.vm_name}.log")
        ]
        
        # Performance optimizations
        performance_mode = config.get('performance_mode', 'balanced')
        if performance_mode == 'speed':
            cmd.extend(["-nolookup", "-nosel", "-nocursor"])
        elif performance_mode == 'quality':
            cmd.extend(["-cursor", "arrow", "-cursorpos"])
        
        logger.debug(f"Starting VNC server: {' '.join(cmd)}")
        
        # Start VNC server process
        session.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait a moment for server to start
        await asyncio.sleep(2)
        
        # Check if process started successfully
        if session.process.poll() is not None:
            stdout, stderr = await session.process.communicate()
            raise RuntimeError(f"VNC server failed to start: {stderr.decode()}")
        
        logger.debug(f"VNC server process started (PID: {session.process.pid})")
    
    async def _stop_vnc_process(self, session: VNCSession) -> None:
        """Stop the VNC server process."""
        if not session.process:
            return
        
        try:
            # Send SIGTERM
            session.process.terminate()
            
            # Wait for graceful shutdown
            try:
                await asyncio.wait_for(session.process.wait(), timeout=5)
                logger.debug(f"VNC process terminated gracefully (PID: {session.process.pid})")
            except asyncio.TimeoutError:
                # Force kill if needed
                session.process.kill()
                await session.process.wait()
                logger.debug(f"VNC process force killed (PID: {session.process.pid})")
                
        except Exception as e:
            logger.warning(f"Error stopping VNC process: {e}")
        
        session.process = None
    
    async def _save_session_data(self, session: VNCSession) -> None:
        """Save session data to disk."""
        session_file = self.vnc_data_dir / f"{session.vm_name}.json"
        
        session_data = {
            "vm_name": session.vm_name,
            "display": session.display,
            "port": session.port,
            "vnc_type": session.vnc_type,
            "os_type": session.os_type,
            "created_at": session.created_at.isoformat(),
            "connection_count": session.connection_count,
            "last_activity": session.last_activity.isoformat()
        }
        
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
    
    async def _send_vnc_keys(self, session: VNCSession, keys: str) -> None:
        """Send keyboard input via VNC protocol for Windows VMs."""
        try:
            # Use vncdo tool for VNC automation if available
            cmd = [
                "vncdo",
                "-s", f"localhost:{session.port}",
                "key", keys
            ]
            
            logger.debug(f"Sending VNC keys '{keys}' to Windows VM '{session.vm_name}'")
            
            result = await run_subprocess(cmd)
            if result.returncode != 0:
                logger.warning(f"vncdo not available, using alternative method")
                # Fall back to manual VNC protocol implementation if needed
                await self._send_vnc_keys_manual(session, keys)
                
        except Exception as e:
            logger.warning(f"VNC key sending failed, trying alternative: {e}")
            await self._send_vnc_keys_manual(session, keys)
    
    async def _send_vnc_mouse_click(self, session: VNCSession, x: int, y: int, button: int) -> None:
        """Send mouse click via VNC protocol for Windows VMs."""
        try:
            # Use vncdo tool for VNC automation if available
            button_map = {1: "left", 2: "middle", 3: "right"}
            button_name = button_map.get(button, "left")
            
            # Move mouse and click
            cmd = [
                "vncdo",
                "-s", f"localhost:{session.port}",
                "move", str(x), str(y),
                "click", button_name
            ]
            
            logger.debug(f"Sending VNC mouse click at ({x}, {y}) button {button} to Windows VM '{session.vm_name}'")
            
            result = await run_subprocess(cmd)
            if result.returncode != 0:
                logger.warning(f"vncdo not available, using alternative method")
                # Fall back to manual VNC protocol implementation if needed
                await self._send_vnc_mouse_click_manual(session, x, y, button)
                
        except Exception as e:
            logger.warning(f"VNC mouse click failed, trying alternative: {e}")
            await self._send_vnc_mouse_click_manual(session, x, y, button)
    
    async def _send_vnc_keys_manual(self, session: VNCSession, keys: str) -> None:
        """Manual VNC key sending implementation."""
        # This would implement the VNC protocol directly
        # For now, log that the operation was attempted
        logger.info(f"Manual VNC key sending for '{keys}' to Windows VM '{session.vm_name}' (not yet implemented)")
        
        # TODO: Implement manual VNC protocol key sending
        # This would involve connecting to the VNC socket and sending RFB protocol messages
    
    async def _send_vnc_mouse_click_manual(self, session: VNCSession, x: int, y: int, button: int) -> None:
        """Manual VNC mouse click implementation."""
        # This would implement the VNC protocol directly
        # For now, log that the operation was attempted
        logger.info(f"Manual VNC mouse click at ({x}, {y}) button {button} to Windows VM '{session.vm_name}' (not yet implemented)")
        
        # TODO: Implement manual VNC protocol mouse interaction
        # This would involve connecting to the VNC socket and sending RFB protocol messages