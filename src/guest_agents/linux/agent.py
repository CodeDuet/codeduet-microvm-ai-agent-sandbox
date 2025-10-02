#!/usr/bin/env python3
"""
Linux Guest Agent for MicroVM Sandbox
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
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LinuxGuestAgent:
    def __init__(self, socket_path: str = "/tmp/guest-agent.sock"):
        self.socket_path = socket_path
        self.server = None
        self.running = False
        self.handlers = {
            "ping": self._handle_ping,
            "execute": self._handle_execute,
            "upload_file": self._handle_upload_file,
            "download_file": self._handle_download_file,
            "get_system_info": self._handle_get_system_info,
            "get_process_list": self._handle_get_process_list,
            "health_check": self._handle_health_check,
            "shutdown": self._handle_shutdown
        }
        
    async def start(self):
        """Start the guest agent server."""
        logger.info(f"Starting Linux guest agent on {self.socket_path}")
        
        # Remove existing socket
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        self.server = await asyncio.start_unix_server(
            self._handle_client, self.socket_path
        )
        
        # Set socket permissions
        os.chmod(self.socket_path, 0o600)
        
        self.running = True
        logger.info("Guest agent started successfully")
        
        async with self.server:
            await self.server.serve_forever()
    
    async def stop(self):
        """Stop the guest agent server."""
        logger.info("Stopping guest agent")
        self.running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        logger.info("Guest agent stopped")
    
    async def _handle_client(self, reader, writer):
        """Handle incoming client connections."""
        client_addr = writer.get_extra_info('peername')
        logger.debug(f"Client connected: {client_addr}")
        
        try:
            while True:
                # Read message length
                length_data = await reader.read(4)
                if not length_data:
                    break
                
                message_length = int.from_bytes(length_data, byteorder='big')
                
                # Read message data
                message_data = await reader.read(message_length)
                if not message_data:
                    break
                
                try:
                    message = json.loads(message_data.decode('utf-8'))
                    response = await self._process_message(message)
                except json.JSONDecodeError as e:
                    response = {
                        "success": False,
                        "error": f"Invalid JSON: {e}",
                        "timestamp": datetime.now().isoformat()
                    }
                except Exception as e:
                    response = {
                        "success": False,
                        "error": f"Processing error: {e}",
                        "timestamp": datetime.now().isoformat()
                    }
                
                # Send response
                response_data = json.dumps(response).encode('utf-8')
                response_length = len(response_data).to_bytes(4, byteorder='big')
                
                writer.write(response_length + response_data)
                await writer.drain()
                
        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.debug(f"Client disconnected: {client_addr}")
    
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
            "os": "linux"
        }
    
    async def _handle_execute(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle command execution."""
        command = message.get("params", {}).get("command")
        timeout = message.get("params", {}).get("timeout", 30)
        working_dir = message.get("params", {}).get("working_dir")
        env = message.get("params", {}).get("env", {})
        
        if not command:
            return {
                "success": False,
                "error": "No command specified"
            }
        
        try:
            # Prepare environment
            exec_env = os.environ.copy()
            exec_env.update(env)
            
            # Execute command safely with argument list instead of shell
            import shlex
            try:
                cmd_args = shlex.split(command)
            except ValueError:
                return {
                    "success": False,
                    "error": "Invalid command syntax",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": 1
                }
            
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
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
        mode = params.get("mode", 0o644)
        create_dirs = params.get("create_dirs", False)
        
        if not file_path or not content_b64:
            return {
                "success": False,
                "error": "Missing file path or content"
            }
        
        try:
            # Validate file path to prevent directory traversal
            file_path_obj = Path(file_path).resolve()
            allowed_base = Path("/tmp").resolve()
            
            if not str(file_path_obj).startswith(str(allowed_base)):
                return {
                    "success": False,
                    "error": "File path not allowed - must be under /tmp"
                }
            
            # Decode content
            content = base64.b64decode(content_b64)
            
            # Create parent directories if requested
            if create_dirs:
                file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(file_path_obj, 'wb') as f:
                f.write(content)
            
            # Set permissions
            os.chmod(file_path_obj, mode)
            
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
            # Get various system information
            info = {
                "hostname": os.uname().nodename,
                "kernel": f"{os.uname().sysname} {os.uname().release}",
                "architecture": os.uname().machine,
                "uptime": await self._get_uptime(),
                "memory": await self._get_memory_info(),
                "disk": await self._get_disk_info(),
                "network": await self._get_network_info(),
                "load_average": os.getloadavg()
            }
            
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
            process = await asyncio.create_subprocess_shell(
                "ps aux --no-headers",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                return {
                    "success": False,
                    "error": f"ps command failed: {stderr.decode()}"
                }
            
            processes = []
            for line in stdout.decode().strip().split('\n'):
                if line:
                    parts = line.split(None, 10)
                    if len(parts) >= 11:
                        processes.append({
                            "user": parts[0],
                            "pid": int(parts[1]),
                            "cpu_percent": float(parts[2]),
                            "memory_percent": float(parts[3]),
                            "vsz": int(parts[4]),
                            "rss": int(parts[5]),
                            "tty": parts[6],
                            "stat": parts[7],
                            "start": parts[8],
                            "time": parts[9],
                            "command": parts[10]
                        })
            
            return {
                "success": True,
                "processes": processes
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Process list error: {e}"
            }
    
    async def _handle_health_check(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Perform health check."""
        try:
            health_data = {
                "agent_status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "uptime": await self._get_uptime(),
                "load_average": os.getloadavg(),
                "memory_usage": await self._get_memory_usage(),
                "disk_usage": await self._get_root_disk_usage()
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
                command = "shutdown -h now"
            else:
                command = "shutdown -h +1"
            
            await asyncio.create_subprocess_shell(command)
            
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
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
            return uptime_seconds
        except:
            return 0.0
    
    async def _get_memory_info(self) -> Dict[str, int]:
        """Get memory information from /proc/meminfo."""
        try:
            memory_info = {}
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        # Extract numeric value (remove 'kB' suffix if present)
                        value = value.strip().split()[0]
                        memory_info[key] = int(value) * 1024  # Convert kB to bytes
            return memory_info
        except:
            return {}
    
    async def _get_memory_usage(self) -> float:
        """Get memory usage percentage."""
        try:
            info = await self._get_memory_info()
            total = info.get('MemTotal', 0)
            free = info.get('MemFree', 0)
            buffers = info.get('Buffers', 0)
            cached = info.get('Cached', 0)
            
            if total > 0:
                used = total - free - buffers - cached
                return (used / total) * 100
        except:
            pass
        return 0.0
    
    async def _get_disk_info(self) -> List[Dict[str, Any]]:
        """Get disk information."""
        try:
            process = await asyncio.create_subprocess_shell(
                "df -h",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await process.communicate()
            
            disks = []
            for line in stdout.decode().strip().split('\n')[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 6:
                    disks.append({
                        "filesystem": parts[0],
                        "size": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "use_percent": parts[4],
                        "mount_point": parts[5]
                    })
            
            return disks
        except:
            return []
    
    async def _get_root_disk_usage(self) -> float:
        """Get root filesystem usage percentage."""
        try:
            import shutil
            total, used, free = shutil.disk_usage('/')
            return (used / total) * 100
        except:
            return 0.0
    
    async def _get_network_info(self) -> List[Dict[str, Any]]:
        """Get network interface information."""
        try:
            process = await asyncio.create_subprocess_shell(
                "ip addr show",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await process.communicate()
            
            interfaces = []
            current_interface = None
            
            for line in stdout.decode().strip().split('\n'):
                if line and not line.startswith(' '):
                    # New interface
                    parts = line.split(':')
                    if len(parts) >= 2:
                        current_interface = {
                            "name": parts[1].strip(),
                            "addresses": []
                        }
                        interfaces.append(current_interface)
                elif current_interface and 'inet' in line:
                    # IP address
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        current_interface["addresses"].append(parts[1])
            
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
    
    parser = argparse.ArgumentParser(description="Linux Guest Agent")
    parser.add_argument("--socket", default="/tmp/guest-agent.sock",
                        help="Unix socket path")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Log level")
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create and start agent
    agent = LinuxGuestAgent(socket_path=args.socket)
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