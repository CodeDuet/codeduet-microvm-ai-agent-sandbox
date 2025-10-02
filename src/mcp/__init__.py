"""
Model Context Protocol (MCP) Server for MicroVM Sandbox
======================================================

Provides seamless integration with AI clients like Claude Desktop, Cursor, and Windsurf
through the Model Context Protocol. Enables AI agents to:

- Create and manage MicroVM sandboxes
- Execute code safely in isolated environments  
- Upload and download files
- Take screenshots and interact with desktops
- Create snapshots for backtracking
- Generate and execute code with LLM integration

Example Usage:
    Start MCP server:
        python -m src.mcp.server
    
    Configure in Claude Desktop (~/.config/claude-desktop/config.json):
        {
          "mcpServers": {
            "microvm-sandbox": {
              "command": "python",
              "args": ["-m", "src.mcp.server"],
              "env": {
                "MICROVM_API_URL": "http://localhost:8000",
                "MICROVM_API_TOKEN": "your-jwt-token"
              }
            }
          }
        }
"""

from .server import MicroVMMCPServer
from .tools import (
    CreateSandboxTool,
    ExecuteCodeTool,
    UploadFileTool,
    DownloadFileTool,
    SnapshotTool,
    RestoreTool,
    TakeScreenshotTool,
    ClickTool,
    TypeTool,
    ScrollTool,
    GetVNCTool,
    DestroySandboxTool,
    ListSandboxesTool,
    GetSandboxInfoTool
)
from .codex_integration import CodexMicroVMIntegration

__version__ = "1.0.0"
__author__ = "MicroVM Sandbox Team"

__all__ = [
    "MicroVMMCPServer",
    "CreateSandboxTool",
    "ExecuteCodeTool", 
    "UploadFileTool",
    "DownloadFileTool",
    "SnapshotTool",
    "RestoreTool",
    "TakeScreenshotTool",
    "ClickTool",
    "TypeTool",
    "ScrollTool",
    "GetVNCTool",
    "DestroySandboxTool",
    "ListSandboxesTool",
    "GetSandboxInfoTool",
    "CodexMicroVMIntegration"
]