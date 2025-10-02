"""
MCP tools for MicroVM Sandbox operations.
"""

import asyncio
import base64
import json
import os
import tempfile
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

try:
    from mcp.types import Tool, ToolParameter
except ImportError:
    # Mock types for development without MCP
    class Tool:
        def __init__(self, name: str, description: str, inputSchema: Dict[str, Any]):
            self.name = name
            self.description = description
            self.inputSchema = inputSchema
    
    class ToolParameter:
        def __init__(self, type: str, description: str, required: bool = True):
            self.type = type
            self.description = description
            self.required = required

from src.sdk.models import SandboxConfig, OSType


class MCPTool(ABC):
    """Base class for MCP tools."""
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters
    
    def to_mcp_tool(self) -> Tool:
        """Convert to MCP Tool object."""
        return Tool(
            name=self.name,
            description=self.description,
            inputSchema={
                "type": "object",
                "properties": self.parameters,
                "required": [name for name, param in self.parameters.items() 
                           if param.get("required", True)]
            }
        )
    
    @abstractmethod
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Union[str, Dict[str, Any], bytes]:
        """Execute the tool."""
        pass


class CreateSandboxTool(MCPTool):
    """Tool to create a new MicroVM sandbox."""
    
    def __init__(self):
        super().__init__(
            name="create_sandbox",
            description="Create a new MicroVM sandbox for code execution and automation",
            parameters={
                "template": {
                    "type": "string",
                    "description": "Sandbox template (ai-agent, code-interpreter, web-automation, computer-use)",
                    "enum": ["ai-agent", "code-interpreter", "web-automation", "computer-use"],
                    "default": "ai-agent"
                },
                "name": {
                    "type": "string", 
                    "description": "Optional sandbox name (auto-generated if not provided)",
                    "required": False
                },
                "vcpus": {
                    "type": "integer",
                    "description": "Number of vCPUs (1-16)",
                    "minimum": 1,
                    "maximum": 16,
                    "required": False
                },
                "memory_mb": {
                    "type": "integer",
                    "description": "Memory in MB (512-16384)",
                    "minimum": 512,
                    "maximum": 16384,
                    "required": False
                },
                "vnc_enabled": {
                    "type": "boolean",
                    "description": "Enable VNC for desktop access",
                    "default": False,
                    "required": False
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        template = arguments.get("template", "ai-agent")
        name = arguments.get("name")
        
        # Create configuration
        config = SandboxConfig(
            name=name or f"{template}-sandbox",
            template=template,
            vcpus=arguments.get("vcpus", 4),
            memory_mb=arguments.get("memory_mb", 4096),
            vnc_enabled=arguments.get("vnc_enabled", False),
            auto_start=True
        )
        
        # Start sandbox
        sandbox = await manager.start_sandbox(config=config)
        active_sandboxes[sandbox.name] = sandbox
        
        return {
            "success": True,
            "sandbox_name": sandbox.name,
            "template": template,
            "state": sandbox.state,
            "vcpus": sandbox.info.vcpus,
            "memory_mb": sandbox.info.memory_mb,
            "vnc_enabled": sandbox.info.vnc_enabled,
            "message": f"Created {template} sandbox: {sandbox.name}"
        }


class ExecuteCodeTool(MCPTool):
    """Tool to execute code in a sandbox."""
    
    def __init__(self):
        super().__init__(
            name="execute_code",
            description="Execute code safely in a MicroVM sandbox",
            parameters={
                "sandbox_name": {
                    "type": "string",
                    "description": "Name of the sandbox to execute code in"
                },
                "code": {
                    "type": "string",
                    "description": "Code to execute"
                },
                "language": {
                    "type": "string",
                    "description": "Programming language (python, javascript, bash, etc.)",
                    "default": "python"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 300,
                    "required": False
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for execution",
                    "required": False
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_name = arguments["sandbox_name"]
        code = arguments["code"]
        language = arguments.get("language", "python")
        timeout = arguments.get("timeout", 30)
        working_dir = arguments.get("working_dir")
        
        # Get sandbox
        if sandbox_name not in active_sandboxes:
            sandbox = await manager.get_sandbox(sandbox_name)
            active_sandboxes[sandbox_name] = sandbox
        else:
            sandbox = active_sandboxes[sandbox_name]
        
        # Build command based on language
        if language == "python":
            command = f"python3 -c '{code.replace(chr(39), chr(34))}'"
        elif language == "javascript":
            command = f"node -e '{code.replace(chr(39), chr(34))}'"
        elif language == "bash":
            command = code
        else:
            # Generic execution
            command = f"{language} -c '{code.replace(chr(39), chr(34))}'"
        
        # Execute code
        result = await sandbox.run_command(
            command,
            timeout=timeout,
            working_dir=working_dir
        )
        
        return {
            "success": result.success,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time_ms": result.execution_time_ms,
            "language": language,
            "sandbox_name": sandbox_name
        }


class UploadFileTool(MCPTool):
    """Tool to upload files to a sandbox."""
    
    def __init__(self):
        super().__init__(
            name="upload_file",
            description="Upload a file to a MicroVM sandbox",
            parameters={
                "sandbox_name": {
                    "type": "string",
                    "description": "Name of the sandbox"
                },
                "content": {
                    "type": "string",
                    "description": "File content (text or base64 encoded binary)"
                },
                "remote_path": {
                    "type": "string",
                    "description": "Path where to save the file in the sandbox"
                },
                "encoding": {
                    "type": "string",
                    "description": "Content encoding (text or base64)",
                    "enum": ["text", "base64"],
                    "default": "text",
                    "required": False
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist",
                    "default": True,
                    "required": False
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_name = arguments["sandbox_name"]
        content = arguments["content"]
        remote_path = arguments["remote_path"]
        encoding = arguments.get("encoding", "text")
        create_dirs = arguments.get("create_dirs", True)
        
        # Get sandbox
        if sandbox_name not in active_sandboxes:
            sandbox = await manager.get_sandbox(sandbox_name)
            active_sandboxes[sandbox_name] = sandbox
        else:
            sandbox = active_sandboxes[sandbox_name]
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            if encoding == "base64":
                tmp_file.write(base64.b64decode(content))
            else:
                tmp_file.write(content.encode('utf-8'))
            tmp_path = tmp_file.name
        
        try:
            # Upload file
            result = await sandbox.upload_file(
                tmp_path,
                remote_path,
                create_dirs=create_dirs
            )
            
            return {
                "success": result.success,
                "remote_path": remote_path,
                "size_bytes": result.size_bytes,
                "checksum": result.checksum,
                "transfer_time_ms": result.transfer_time_ms,
                "sandbox_name": sandbox_name
            }
        
        finally:
            # Cleanup temporary file
            os.unlink(tmp_path)


class DownloadFileTool(MCPTool):
    """Tool to download files from a sandbox."""
    
    def __init__(self):
        super().__init__(
            name="download_file",
            description="Download a file from a MicroVM sandbox",
            parameters={
                "sandbox_name": {
                    "type": "string",
                    "description": "Name of the sandbox"
                },
                "remote_path": {
                    "type": "string",
                    "description": "Path of the file in the sandbox"
                },
                "encoding": {
                    "type": "string",
                    "description": "Return encoding (text or base64)",
                    "enum": ["text", "base64"],
                    "default": "text",
                    "required": False
                },
                "max_size": {
                    "type": "integer",
                    "description": "Maximum file size in bytes",
                    "default": 1048576,  # 1MB
                    "minimum": 1,
                    "maximum": 10485760,  # 10MB
                    "required": False
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_name = arguments["sandbox_name"]
        remote_path = arguments["remote_path"]
        encoding = arguments.get("encoding", "text")
        max_size = arguments.get("max_size", 1048576)
        
        # Get sandbox
        if sandbox_name not in active_sandboxes:
            sandbox = await manager.get_sandbox(sandbox_name)
            active_sandboxes[sandbox_name] = sandbox
        else:
            sandbox = active_sandboxes[sandbox_name]
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Download file
            result = await sandbox.download_file(
                remote_path,
                tmp_path,
                max_size=max_size
            )
            
            if result.success:
                # Read file content
                with open(tmp_path, 'rb') as f:
                    file_content = f.read()
                
                if encoding == "base64":
                    content = base64.b64encode(file_content).decode('utf-8')
                else:
                    content = file_content.decode('utf-8', errors='replace')
                
                return {
                    "success": True,
                    "content": content,
                    "encoding": encoding,
                    "size_bytes": result.size_bytes,
                    "remote_path": remote_path,
                    "transfer_time_ms": result.transfer_time_ms,
                    "sandbox_name": sandbox_name
                }
            else:
                return {
                    "success": False,
                    "error": result.error,
                    "remote_path": remote_path,
                    "sandbox_name": sandbox_name
                }
        
        finally:
            # Cleanup temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class SnapshotTool(MCPTool):
    """Tool to create a sandbox snapshot."""
    
    def __init__(self):
        super().__init__(
            name="create_snapshot",
            description="Create a snapshot of a MicroVM sandbox for backtracking",
            parameters={
                "sandbox_name": {
                    "type": "string",
                    "description": "Name of the sandbox"
                },
                "snapshot_name": {
                    "type": "string",
                    "description": "Name for the snapshot"
                },
                "description": {
                    "type": "string",
                    "description": "Optional description of the snapshot",
                    "default": "",
                    "required": False
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_name = arguments["sandbox_name"]
        snapshot_name = arguments["snapshot_name"]
        description = arguments.get("description", "")
        
        # Get sandbox
        if sandbox_name not in active_sandboxes:
            sandbox = await manager.get_sandbox(sandbox_name)
            active_sandboxes[sandbox_name] = sandbox
        else:
            sandbox = active_sandboxes[sandbox_name]
        
        # Create snapshot
        snapshot = await sandbox.snapshot(snapshot_name, description)
        
        return {
            "success": True,
            "snapshot_id": snapshot.id,
            "snapshot_name": snapshot.name,
            "description": snapshot.description,
            "size_bytes": snapshot.size_bytes,
            "created_at": snapshot.created_at.isoformat(),
            "sandbox_name": sandbox_name
        }


class RestoreTool(MCPTool):
    """Tool to restore a sandbox from snapshot."""
    
    def __init__(self):
        super().__init__(
            name="restore_snapshot",
            description="Restore a MicroVM sandbox from a snapshot",
            parameters={
                "sandbox_name": {
                    "type": "string",
                    "description": "Name of the sandbox"
                },
                "snapshot_id": {
                    "type": "string",
                    "description": "ID of the snapshot to restore"
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_name = arguments["sandbox_name"]
        snapshot_id = arguments["snapshot_id"]
        
        # Get sandbox
        if sandbox_name not in active_sandboxes:
            sandbox = await manager.get_sandbox(sandbox_name)
            active_sandboxes[sandbox_name] = sandbox
        else:
            sandbox = active_sandboxes[sandbox_name]
        
        # Restore snapshot
        await sandbox.restore(snapshot_id)
        
        return {
            "success": True,
            "snapshot_id": snapshot_id,
            "sandbox_name": sandbox_name,
            "message": f"Restored sandbox {sandbox_name} from snapshot {snapshot_id}"
        }


class TakeScreenshotTool(MCPTool):
    """Tool to take a screenshot of the sandbox desktop."""
    
    def __init__(self):
        super().__init__(
            name="take_screenshot",
            description="Take a screenshot of the MicroVM sandbox desktop",
            parameters={
                "sandbox_name": {
                    "type": "string",
                    "description": "Name of the sandbox"
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> bytes:
        sandbox_name = arguments["sandbox_name"]
        
        # Get sandbox
        if sandbox_name not in active_sandboxes:
            sandbox = await manager.get_sandbox(sandbox_name)
            active_sandboxes[sandbox_name] = sandbox
        else:
            sandbox = active_sandboxes[sandbox_name]
        
        # Take screenshot
        result = await sandbox.take_screenshot()
        
        if result.success:
            return result.image_data
        else:
            raise Exception(f"Screenshot failed: {result.error}")


class ClickTool(MCPTool):
    """Tool to perform mouse clicks."""
    
    def __init__(self):
        super().__init__(
            name="click",
            description="Perform a mouse click in the MicroVM sandbox desktop",
            parameters={
                "sandbox_name": {
                    "type": "string",
                    "description": "Name of the sandbox"
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate"
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate"
                },
                "button": {
                    "type": "string",
                    "description": "Mouse button",
                    "enum": ["left", "right", "middle"],
                    "default": "left",
                    "required": False
                },
                "double_click": {
                    "type": "boolean",
                    "description": "Perform double click",
                    "default": False,
                    "required": False
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_name = arguments["sandbox_name"]
        x = arguments["x"]
        y = arguments["y"]
        button = arguments.get("button", "left")
        double_click = arguments.get("double_click", False)
        
        # Get sandbox
        if sandbox_name not in active_sandboxes:
            sandbox = await manager.get_sandbox(sandbox_name)
            active_sandboxes[sandbox_name] = sandbox
        else:
            sandbox = active_sandboxes[sandbox_name]
        
        # Perform click
        result = await sandbox.click(x, y, button, double_click)
        
        return {
            "success": result.success,
            "action": "click",
            "x": x,
            "y": y,
            "button": button,
            "double_click": double_click,
            "error": result.error,
            "sandbox_name": sandbox_name
        }


class TypeTool(MCPTool):
    """Tool to type text."""
    
    def __init__(self):
        super().__init__(
            name="type_text",
            description="Type text in the MicroVM sandbox desktop",
            parameters={
                "sandbox_name": {
                    "type": "string",
                    "description": "Name of the sandbox"
                },
                "text": {
                    "type": "string",
                    "description": "Text to type"
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_name = arguments["sandbox_name"]
        text = arguments["text"]
        
        # Get sandbox
        if sandbox_name not in active_sandboxes:
            sandbox = await manager.get_sandbox(sandbox_name)
            active_sandboxes[sandbox_name] = sandbox
        else:
            sandbox = active_sandboxes[sandbox_name]
        
        # Type text
        result = await sandbox.type_text(text)
        
        return {
            "success": result.success,
            "action": "type",
            "text": text,
            "error": result.error,
            "sandbox_name": sandbox_name
        }


class ScrollTool(MCPTool):
    """Tool to perform scrolling."""
    
    def __init__(self):
        super().__init__(
            name="scroll",
            description="Perform scrolling in the MicroVM sandbox desktop",
            parameters={
                "sandbox_name": {
                    "type": "string",
                    "description": "Name of the sandbox"
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate"
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate"
                },
                "direction": {
                    "type": "string",
                    "description": "Scroll direction",
                    "enum": ["up", "down", "left", "right"]
                },
                "amount": {
                    "type": "integer",
                    "description": "Scroll amount",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 10,
                    "required": False
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_name = arguments["sandbox_name"]
        x = arguments["x"]
        y = arguments["y"]
        direction = arguments["direction"]
        amount = arguments.get("amount", 3)
        
        # Get sandbox
        if sandbox_name not in active_sandboxes:
            sandbox = await manager.get_sandbox(sandbox_name)
            active_sandboxes[sandbox_name] = sandbox
        else:
            sandbox = active_sandboxes[sandbox_name]
        
        # Perform scroll
        result = await sandbox.scroll(x, y, direction, amount)
        
        return {
            "success": result.success,
            "action": "scroll",
            "x": x,
            "y": y,
            "direction": direction,
            "amount": amount,
            "error": result.error,
            "sandbox_name": sandbox_name
        }


class GetVNCTool(MCPTool):
    """Tool to get VNC connection information."""
    
    def __init__(self):
        super().__init__(
            name="get_vnc_info",
            description="Get VNC connection information for visual access to the sandbox",
            parameters={
                "sandbox_name": {
                    "type": "string",
                    "description": "Name of the sandbox"
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_name = arguments["sandbox_name"]
        
        # Get sandbox
        if sandbox_name not in active_sandboxes:
            sandbox = await manager.get_sandbox(sandbox_name)
            active_sandboxes[sandbox_name] = sandbox
        else:
            sandbox = active_sandboxes[sandbox_name]
        
        # Get VNC info
        vnc_info = await sandbox.get_vnc_info()
        
        return {
            "enabled": vnc_info.enabled,
            "host": vnc_info.host,
            "port": vnc_info.port,
            "password": vnc_info.password,
            "web_url": vnc_info.web_url,
            "resolution": vnc_info.resolution,
            "color_depth": vnc_info.color_depth,
            "sandbox_name": sandbox_name
        }


class DestroySandboxTool(MCPTool):
    """Tool to destroy a sandbox."""
    
    def __init__(self):
        super().__init__(
            name="destroy_sandbox",
            description="Destroy a MicroVM sandbox and clean up resources",
            parameters={
                "sandbox_name": {
                    "type": "string",
                    "description": "Name of the sandbox to destroy"
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_name = arguments["sandbox_name"]
        
        # Remove from active sandboxes
        if sandbox_name in active_sandboxes:
            del active_sandboxes[sandbox_name]
        
        # Destroy sandbox
        await manager.delete_sandbox(sandbox_name)
        
        return {
            "success": True,
            "sandbox_name": sandbox_name,
            "message": f"Sandbox {sandbox_name} destroyed successfully"
        }


class ListSandboxesTool(MCPTool):
    """Tool to list all sandboxes."""
    
    def __init__(self):
        super().__init__(
            name="list_sandboxes",
            description="List all available MicroVM sandboxes",
            parameters={}
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        # List sandboxes
        sandboxes = await manager.list_sandboxes()
        
        return {
            "sandboxes": [
                {
                    "name": sb.name,
                    "state": sb.state,
                    "template": sb.template,
                    "vcpus": sb.vcpus,
                    "memory_mb": sb.memory_mb,
                    "os_type": sb.os_type,
                    "created_at": sb.created_at.isoformat(),
                    "vnc_enabled": sb.vnc_enabled
                }
                for sb in sandboxes
            ],
            "total": len(sandboxes)
        }


class GetSandboxInfoTool(MCPTool):
    """Tool to get detailed sandbox information."""
    
    def __init__(self):
        super().__init__(
            name="get_sandbox_info",
            description="Get detailed information about a specific MicroVM sandbox",
            parameters={
                "sandbox_name": {
                    "type": "string",
                    "description": "Name of the sandbox"
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_name = arguments["sandbox_name"]
        
        # Get sandbox
        if sandbox_name not in active_sandboxes:
            sandbox = await manager.get_sandbox(sandbox_name)
            active_sandboxes[sandbox_name] = sandbox
        else:
            sandbox = active_sandboxes[sandbox_name]
        
        # Get detailed metrics
        metrics = await sandbox.get_metrics()
        
        return {
            "sandbox_info": {
                "name": sandbox.info.name,
                "state": sandbox.info.state,
                "template": sandbox.info.template,
                "vcpus": sandbox.info.vcpus,
                "memory_mb": sandbox.info.memory_mb,
                "os_type": sandbox.info.os_type,
                "created_at": sandbox.info.created_at.isoformat(),
                "updated_at": sandbox.info.updated_at.isoformat(),
                "vnc_enabled": sandbox.info.vnc_enabled,
                "ip_address": sandbox.info.ip_address,
                "uptime_seconds": sandbox.info.uptime_seconds
            },
            "resource_usage": {
                "cpu_percent": metrics.resource_usage.cpu_percent if metrics.resource_usage else None,
                "memory_percent": metrics.resource_usage.memory_percent if metrics.resource_usage else None,
                "disk_percent": metrics.resource_usage.disk_percent if metrics.resource_usage else None
            } if metrics.resource_usage else None,
            "health_status": {
                "healthy": metrics.health_status.healthy if metrics.health_status else None,
                "checks": metrics.health_status.checks if metrics.health_status else None,
                "uptime_seconds": metrics.health_status.uptime_seconds if metrics.health_status else None
            } if metrics.health_status else None
        }


class CreateLangChainSessionTool(MCPTool):
    """Tool to create a LangChain AI framework session."""
    
    def __init__(self):
        super().__init__(
            name="create_langchain_session",
            description="Create a dedicated LangChain session for AI workflows",
            parameters={
                "session_name": {
                    "type": "string",
                    "description": "Optional session name (auto-generated if not provided)",
                    "required": False
                },
                "vcpus": {
                    "type": "integer",
                    "description": "Number of vCPUs (2-8)",
                    "minimum": 2,
                    "maximum": 8,
                    "default": 4,
                    "required": False
                },
                "memory_mb": {
                    "type": "integer",
                    "description": "Memory in MB (2048-8192)",
                    "minimum": 2048,
                    "maximum": 8192,
                    "default": 4096,
                    "required": False
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        # This would need to be implemented in the SDK to work with the AI framework manager
        # For now, return a placeholder response
        return {
            "success": True,
            "message": "LangChain session creation needs SDK integration with AI framework manager"
        }


class ExecuteLangChainTool(MCPTool):
    """Tool to execute LangChain operations."""
    
    def __init__(self):
        super().__init__(
            name="execute_langchain",
            description="Execute LangChain chains, agents, and workflows",
            parameters={
                "session_id": {
                    "type": "string",
                    "description": "LangChain session ID"
                },
                "operation": {
                    "type": "string",
                    "description": "Operation type",
                    "enum": ["execute_chain", "create_agent", "run_agent"]
                },
                "config": {
                    "type": "object",
                    "description": "Operation configuration",
                    "properties": {
                        "prompt_template": {"type": "string"},
                        "input_variables": {"type": "array"},
                        "inputs": {"type": "object"},
                        "llm_config": {"type": "object"},
                        "tools": {"type": "array"},
                        "agent_type": {"type": "string"}
                    }
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        # This would need to be implemented in the SDK to work with the AI framework manager
        return {
            "success": True,
            "message": "LangChain execution needs SDK integration with AI framework manager"
        }


class CreateAutoGenSessionTool(MCPTool):
    """Tool to create an AutoGen multi-agent session."""
    
    def __init__(self):
        super().__init__(
            name="create_autogen_session",
            description="Create a multi-agent AutoGen session for collaborative AI workflows",
            parameters={
                "session_name": {
                    "type": "string",
                    "description": "Optional session name (auto-generated if not provided)",
                    "required": False
                },
                "vcpus": {
                    "type": "integer",
                    "description": "Number of vCPUs (4-8)",
                    "minimum": 4,
                    "maximum": 8,
                    "default": 6,
                    "required": False
                },
                "memory_mb": {
                    "type": "integer",
                    "description": "Memory in MB (4096-16384)",
                    "minimum": 4096,
                    "maximum": 16384,
                    "default": 8192,
                    "required": False
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        # This would need to be implemented in the SDK to work with the AI framework manager
        return {
            "success": True,
            "message": "AutoGen session creation needs SDK integration with AI framework manager"
        }


class ExecuteAutoGenTool(MCPTool):
    """Tool to execute AutoGen multi-agent operations."""
    
    def __init__(self):
        super().__init__(
            name="execute_autogen",
            description="Execute AutoGen multi-agent conversations and workflows",
            parameters={
                "session_id": {
                    "type": "string",
                    "description": "AutoGen session ID"
                },
                "operation": {
                    "type": "string",
                    "description": "Operation type",
                    "enum": ["create_agents", "start_conversation", "continue_conversation"]
                },
                "config": {
                    "type": "object",
                    "description": "Operation configuration",
                    "properties": {
                        "agents": {"type": "array"},
                        "initial_message": {"type": "string"},
                        "max_rounds": {"type": "integer"},
                        "llm_config": {"type": "object"}
                    }
                }
            }
        )
    
    async def execute(self, manager, arguments: Dict[str, Any], active_sandboxes: Dict[str, Any]) -> Dict[str, Any]:
        # This would need to be implemented in the SDK to work with the AI framework manager
        return {
            "success": True,
            "message": "AutoGen execution needs SDK integration with AI framework manager"
        }


# Available tools for MCP server
AVAILABLE_TOOLS = [
    CreateSandboxTool(),
    ExecuteCodeTool(),
    UploadFileTool(),
    DownloadFileTool(),
    SnapshotTool(),
    RestoreTool(),
    TakeScreenshotTool(),
    ClickTool(),
    TypeTool(),
    ScrollTool(),
    GetVNCTool(),
    CreateLangChainSessionTool(),
    ExecuteLangChainTool(),
    CreateAutoGenSessionTool(),
    ExecuteAutoGenTool(),
    DestroySandboxTool(),
    ListSandboxesTool(),
    GetSandboxInfoTool()
]