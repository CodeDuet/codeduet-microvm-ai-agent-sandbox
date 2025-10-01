#!/usr/bin/env python3
"""
Windows Guest Agent for MicroVM Sandbox
Handles host-to-guest communication, command execution, file transfers, and health monitoring.
"""

import json
import asyncio
import subprocess
import sys
import os
import hashlib
import base64
import signal
import logging
import platform
import psutil
import wmi
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WindowsGuestAgent:
    def __init__(self, pipe_name: str = r"\\.\pipe\guest-agent"):
        self.pipe_name = pipe_name
        self.server = None
        self.running = False
        self.wmi_conn = None
        self.handlers = {
            "ping": self._handle_ping,
            "execute": self._handle_execute,
            "upload_file": self._handle_upload_file,
            "download_file": self._handle_download_file,
            "get_system_info": self._handle_get_system_info,
            "get_process_list": self._handle_get_process_list,
            "health_check": self._handle_health_check,
            "shutdown": self._handle_shutdown,
            "get_services": self._handle_get_services,
            "get_event_logs": self._handle_get_event_logs
        }
        
        # Initialize WMI connection
        try:
            self.wmi_conn = wmi.WMI()
        except Exception as e:
            logger.warning(f"Failed to initialize WMI: {e}")
        
    async def start(self):
        """Start the guest agent server."""
        logger.info(f"Starting Windows guest agent on {self.pipe_name}")
        
        self.running = True
        
        # Start named pipe server
        await self._start_pipe_server()
        
    async def stop(self):
        """Stop the guest agent server."""
        logger.info("Stopping guest agent")
        self.running = False
        
        if self.server:
            self.server.close()
        
        logger.info("Guest agent stopped")
    
    async def _start_pipe_server(self):
        """Start the named pipe server."""
        import win32pipe
        import win32file
        import win32api
        import win32con
        
        while self.running:
            try:
                # Create named pipe
                pipe = win32pipe.CreateNamedPipe(
                    self.pipe_name,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                    1,  # max instances
                    65536,  # out buffer size
                    65536,  # in buffer size
                    0,  # default timeout
                    None  # security attributes
                )
                
                if pipe == win32file.INVALID_HANDLE_VALUE:
                    logger.error("Failed to create named pipe")
                    break
                
                logger.info("Waiting for client connection...")
                
                # Wait for client connection
                win32pipe.ConnectNamedPipe(pipe, None)
                logger.info("Client connected")
                
                # Handle client in separate task
                asyncio.create_task(self._handle_pipe_client(pipe))
                
            except Exception as e:
                logger.error(f"Pipe server error: {e}")
                await asyncio.sleep(1)
    
    async def _handle_pipe_client(self, pipe):
        """Handle a connected pipe client."""
        import win32file
        
        try:
            while self.running:
                # Read message
                try:
                    result, data = win32file.ReadFile(pipe, 65536)
                    if not data:
                        break
                    
                    message = json.loads(data.decode('utf-8'))
                    response = await self._process_message(message)
                    
                    # Send response
                    response_data = json.dumps(response).encode('utf-8')
                    win32file.WriteFile(pipe, response_data)
                    
                except Exception as e:
                    logger.error(f"Message processing error: {e}")
                    error_response = {
                        "success": False,
                        "error": f"Processing error: {e}",
                        "timestamp": datetime.now().isoformat()
                    }
                    response_data = json.dumps(error_response).encode('utf-8')
                    try:
                        win32file.WriteFile(pipe, response_data)
                    except:
                        break
                        
        except Exception as e:
            logger.error(f"Pipe client handler error: {e}")
        finally:
            try:
                win32file.CloseHandle(pipe)
            except:
                pass
            logger.info("Client disconnected")
    
    async def _process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming message and route to appropriate handler."""
        command = message.get("command")
        request_id = message.get("request_id", "unknown")
        
        if not command:
            return {
                "success": False,
                "error": "No command specified",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        
        handler = self.handlers.get(command)
        if not handler:
            return {
                "success": False,
                "error": f"Unknown command: {command}",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            result = await handler(message)
            result["request_id"] = request_id
            result["timestamp"] = datetime.now().isoformat()
            return result
        except Exception as e:
            logger.error(f"Handler error for command {command}: {e}")
            return {
                "success": False,
                "error": f"Handler error: {e}",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
    
    async def _handle_ping(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping command."""
        return {
            "success": True,
            "message": "pong",
            "agent_version": "1.0.0",
            "os": "windows",
            "os_version": platform.platform()
        }
    
    async def _handle_execute(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle command execution."""
        command = message.get("params", {}).get("command")
        timeout = message.get("params", {}).get("timeout", 30)
        working_dir = message.get("params", {}).get("working_dir")
        env = message.get("params", {}).get("env", {})
        shell = message.get("params", {}).get("shell", True)
        
        if not command:
            return {
                "success": False,
                "error": "No command specified"
            }
        
        try:
            # Prepare environment
            exec_env = os.environ.copy()
            exec_env.update(env)
            
            # Execute command
            if shell:
                # Use cmd.exe for shell commands
                full_command = f'cmd.exe /c "{command}"'
            else:
                full_command = command
            
            process = await asyncio.create_subprocess_shell(
                full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=exec_env
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "success": False,
                    "error": f"Command timed out after {timeout} seconds"
                }
            
            return {
                "success": True,
                "exit_code": process.returncode,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace')
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Execution error: {e}"
            }
    
    async def _handle_upload_file(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file upload from host to guest."""
        params = message.get("params", {})
        file_path = params.get("path")
        content_b64 = params.get("content")
        create_dirs = params.get("create_dirs", False)
        
        if not file_path or not content_b64:
            return {
                "success": False,
                "error": "Missing file path or content"
            }
        
        try:
            # Decode content
            content = base64.b64decode(content_b64)
            
            # Create parent directories if requested
            file_path_obj = Path(file_path)
            if create_dirs:
                file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(file_path, 'wb') as f:
                f.write(content)
            
            # Calculate checksum for verification
            checksum = hashlib.sha256(content).hexdigest()
            
            return {
                "success": True,
                "path": file_path,
                "size": len(content),
                "checksum": checksum
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Upload error: {e}"
            }
    
    async def _handle_download_file(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file download from guest to host."""
        params = message.get("params", {})
        file_path = params.get("path")
        max_size = params.get("max_size", 10 * 1024 * 1024)  # 10MB default
        
        if not file_path:
            return {
                "success": False,
                "error": "No file path specified"
            }
        
        try:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                return {
                    "success": False,
                    "error": "File not found"
                }
            
            if not file_path_obj.is_file():
                return {
                    "success": False,
                    "error": "Path is not a file"
                }
            
            file_size = file_path_obj.stat().st_size
            if file_size > max_size:
                return {
                    "success": False,
                    "error": f"File too large: {file_size} bytes (max: {max_size})"
                }
            
            # Read file
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Encode content
            content_b64 = base64.b64encode(content).decode('ascii')
            
            # Calculate checksum
            checksum = hashlib.sha256(content).hexdigest()
            
            return {
                "success": True,
                "path": file_path,
                "size": file_size,
                "content": content_b64,
                "checksum": checksum
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Download error: {e}"
            }
    
    async def _handle_get_system_info(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Get system information."""
        try:
            # Get Windows-specific system information
            info = {
                "hostname": platform.node(),
                "os": platform.system(),
                "os_version": platform.version(),
                "os_release": platform.release(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "uptime": await self._get_uptime(),
                "memory": await self._get_memory_info(),
                "disk": await self._get_disk_info(),
                "network": await self._get_network_info()
            }
            
            # Add WMI information if available
            if self.wmi_conn:
                try:
                    # Get computer system info
                    for computer in self.wmi_conn.Win32_ComputerSystem():
                        info["manufacturer"] = computer.Manufacturer
                        info["model"] = computer.Model
                        info["total_physical_memory"] = int(computer.TotalPhysicalMemory)
                        break
                    
                    # Get OS info
                    for os_info in self.wmi_conn.Win32_OperatingSystem():
                        info["os_name"] = os_info.Name.split('|')[0]
                        info["os_install_date"] = str(os_info.InstallDate)
                        info["last_boot_time"] = str(os_info.LastBootUpTime)
                        break
                except Exception as e:
                    logger.warning(f"WMI query error: {e}")
            
            return {
                "success": True,
                "system_info": info
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"System info error: {e}"
            }
    
    async def _handle_get_process_list(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Get running process list."""
        try:
            processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'create_time', 'cmdline']):
                try:
                    process_info = proc.info
                    process_info['create_time'] = datetime.fromtimestamp(process_info['create_time']).isoformat()
                    process_info['cmdline'] = ' '.join(process_info['cmdline']) if process_info['cmdline'] else ''
                    processes.append(process_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return {
                "success": True,
                "processes": processes
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Process list error: {e}"
            }
    
    async def _handle_get_services(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Get Windows services information."""
        try:
            services = []
            
            if self.wmi_conn:
                for service in self.wmi_conn.Win32_Service():
                    services.append({
                        "name": service.Name,
                        "display_name": service.DisplayName,
                        "state": service.State,
                        "start_mode": service.StartMode,
                        "path": service.PathName,
                        "description": service.Description
                    })
            
            return {
                "success": True,
                "services": services
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Services error: {e}"
            }
    
    async def _handle_get_event_logs(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Get Windows event logs."""
        params = message.get("params", {})
        log_name = params.get("log_name", "System")
        max_events = params.get("max_events", 100)
        
        try:
            events = []
            
            if self.wmi_conn:
                wql_query = f"SELECT * FROM Win32_NTLogEvent WHERE LogFile = '{log_name}'"
                for event in self.wmi_conn.query(wql_query)[:max_events]:
                    events.append({
                        "event_id": event.EventCode,
                        "source": event.SourceName,
                        "time_generated": str(event.TimeGenerated),
                        "type": event.Type,
                        "category": event.Category,
                        "message": event.Message
                    })
            
            return {
                "success": True,
                "events": events
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Event logs error: {e}"
            }
    
    async def _handle_health_check(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Perform health check."""
        try:
            health_data = {
                "agent_status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "uptime": await self._get_uptime(),
                "cpu_usage": psutil.cpu_percent(interval=1),
                "memory_usage": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('C:\\').percent
            }
            
            return {
                "success": True,
                "health": health_data
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Health check error: {e}"
            }
    
    async def _handle_shutdown(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle shutdown command."""
        force = message.get("params", {}).get("force", False)
        delay = message.get("params", {}).get("delay", 0)
        
        try:
            if delay > 0:
                await asyncio.sleep(delay)
            
            if force:
                command = "shutdown /s /f /t 0"
            else:
                command = "shutdown /s /t 60"
            
            subprocess.Popen(command, shell=True)
            
            return {
                "success": True,
                "message": "Shutdown initiated"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Shutdown error: {e}"
            }
    
    async def _get_uptime(self) -> float:
        """Get system uptime in seconds."""
        try:
            boot_time = psutil.boot_time()
            uptime = datetime.now().timestamp() - boot_time
            return uptime
        except:
            return 0.0
    
    async def _get_memory_info(self) -> Dict[str, int]:
        """Get memory information."""
        try:
            memory = psutil.virtual_memory()
            return {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "free": memory.free,
                "percent": memory.percent
            }
        except:
            return {}
    
    async def _get_disk_info(self) -> List[Dict[str, Any]]:
        """Get disk information."""
        try:
            disks = []
            
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disks.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent
                    })
                except PermissionError:
                    continue
            
            return disks
        except:
            return []
    
    async def _get_network_info(self) -> List[Dict[str, Any]]:
        """Get network interface information."""
        try:
            interfaces = []
            
            # Get network interfaces
            for interface, addrs in psutil.net_if_addrs().items():
                interface_info = {
                    "name": interface,
                    "addresses": []
                }
                
                for addr in addrs:
                    if addr.family == 2:  # IPv4
                        interface_info["addresses"].append({
                            "type": "IPv4",
                            "address": addr.address,
                            "netmask": addr.netmask
                        })
                    elif addr.family == 23:  # IPv6
                        interface_info["addresses"].append({
                            "type": "IPv6",
                            "address": addr.address,
                            "netmask": addr.netmask
                        })
                
                if interface_info["addresses"]:
                    interfaces.append(interface_info)
            
            return interfaces
        except:
            return []


def setup_signal_handlers(agent):
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(agent.stop())
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Windows Guest Agent")
    parser.add_argument("--pipe", default=r"\\.\pipe\guest-agent",
                        help="Named pipe path")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Log level")
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create and start agent
    agent = WindowsGuestAgent(pipe_name=args.pipe)
    setup_signal_handlers(agent)
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Agent error: {e}")
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())