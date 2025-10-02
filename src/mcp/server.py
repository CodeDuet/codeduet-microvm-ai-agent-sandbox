"""
MCP Server implementation for MicroVM Sandbox.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Sequence
from datetime import datetime

# MCP imports
try:
    from mcp import ClientSession, StdioServerTransport
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.types import (
        CallToolRequest, 
        CallToolResult,
        ListToolsRequest,
        ListToolsResult,
        Tool,
        TextContent,
        ImageContent,
        EmbeddedResource
    )
except ImportError:
    print("MCP not available. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Local imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.sdk import MicroVMManager, SecurityContext
from .tools import AVAILABLE_TOOLS
from .codex_integration import CodexMicroVMIntegration

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MicroVMMCPServer:
    """
    Model Context Protocol server for MicroVM Sandbox.
    
    Provides AI clients with tools to manage MicroVM sandboxes through MCP.
    Supports code execution, file operations, desktop interaction, and more.
    """
    
    def __init__(self, api_url: Optional[str] = None, api_token: Optional[str] = None):
        """Initialize MCP server."""
        # Configuration from environment
        self.api_url = api_url or os.getenv("MICROVM_API_URL", "http://localhost:8000")
        self.api_token = api_token or os.getenv("MICROVM_API_TOKEN")
        
        # Initialize components
        self.server = Server("microvm-sandbox")
        self.manager: Optional[MicroVMManager] = None
        self.codex_integration: Optional[CodexMicroVMIntegration] = None
        
        # Active sandboxes (for cleanup)
        self.active_sandboxes: Dict[str, Any] = {}
        
        # Setup tool handlers
        self._setup_tool_handlers()
        
        logger.info(f"MicroVM MCP Server initialized (API URL: {self.api_url})")
    
    def _setup_tool_handlers(self):
        """Setup MCP tool handlers."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available MCP tools."""
            return [tool.to_mcp_tool() for tool in AVAILABLE_TOOLS]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent | ImageContent | EmbeddedResource]:
            """Handle tool execution."""
            logger.info(f"Executing tool: {name} with args: {arguments}")
            
            # Ensure manager is initialized
            if not self.manager:
                await self._init_manager()
            
            # Find and execute tool
            for tool in AVAILABLE_TOOLS:
                if tool.name == name:
                    try:
                        result = await tool.execute(self.manager, arguments, self.active_sandboxes)
                        
                        # Handle different result types
                        if isinstance(result, dict):
                            return [TextContent(type="text", text=json.dumps(result, indent=2))]
                        elif isinstance(result, str):
                            return [TextContent(type="text", text=result)]
                        elif isinstance(result, bytes):
                            # Image data
                            return [ImageContent(type="image", data=result, mimeType="image/png")]
                        else:
                            return [TextContent(type="text", text=str(result))]
                            
                    except Exception as e:
                        logger.error(f"Tool {name} failed: {e}")
                        error_msg = f"Tool execution failed: {str(e)}"
                        return [TextContent(type="text", text=error_msg)]
            
            # Tool not found
            error_msg = f"Unknown tool: {name}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
    
    async def _init_manager(self):
        """Initialize MicroVM manager."""
        security_context = SecurityContext(
            api_token=self.api_token,
            user_id="mcp-client",
            role="mcp-user",
            audit_enabled=True
        )
        
        self.manager = MicroVMManager(
            api_url=self.api_url,
            security_context=security_context
        )
        
        # Initialize the manager connection
        await self.manager._init_client()
        
        # Initialize Codex integration if OpenAI API key is available
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            self.codex_integration = CodexMicroVMIntegration(
                api_key=openai_api_key,
                sandbox_manager=self.manager
            )
            logger.info("Codex integration enabled")
        else:
            logger.info("Codex integration disabled (no OPENAI_API_KEY)")
    
    async def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up MCP server...")
        
        # Cleanup active sandboxes
        if self.active_sandboxes:
            logger.info(f"Cleaning up {len(self.active_sandboxes)} active sandboxes")
            for sandbox_name in list(self.active_sandboxes.keys()):
                try:
                    await self.manager.delete_sandbox(sandbox_name)
                    logger.info(f"Cleaned up sandbox: {sandbox_name}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup sandbox {sandbox_name}: {e}")
        
        # Cleanup manager
        if self.manager:
            await self.manager.cleanup()
        
        logger.info("MCP server cleanup complete")
    
    async def run_stdio(self):
        """Run MCP server with stdio transport."""
        logger.info("Starting MicroVM MCP Server with stdio transport")
        
        async with StdioServerTransport() as (read_stream, write_stream):
            try:
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="microvm-sandbox",
                        server_version="1.0.0",
                        capabilities={
                            "tools": {},
                            "logging": {}
                        }
                    )
                )
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
            except Exception as e:
                logger.error(f"Server error: {e}")
            finally:
                await self.cleanup()


# Global MCP server instance
mcp_server: Optional[MicroVMMCPServer] = None


async def main():
    """Main entry point for MCP server."""
    global mcp_server
    
    try:
        # Create and run MCP server
        mcp_server = MicroVMMCPServer()
        await mcp_server.run_stdio()
        
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the MCP server
    asyncio.run(main())