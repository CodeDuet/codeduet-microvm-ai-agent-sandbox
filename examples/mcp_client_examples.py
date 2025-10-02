#!/usr/bin/env python3
"""
Example MCP client interactions with MicroVM Sandbox.

This script demonstrates how different AI clients can interact with the
MicroVM Sandbox through the Model Context Protocol.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.mcp.server import MicroVMMCPServer
from src.mcp.tools import AVAILABLE_TOOLS


async def example_create_and_execute():
    """Example: Create sandbox and execute Python code."""
    print("🚀 MCP Example: Create Sandbox and Execute Code")
    print("=" * 60)
    
    # Initialize MCP server (normally done by MCP client)
    server = MicroVMMCPServer()
    await server._init_manager()
    
    try:
        # Create sandbox
        create_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "create_sandbox")
        result = await create_tool.execute(
            server.manager,
            {
                "template": "ai-agent",
                "vcpus": 2,
                "memory_mb": 2048,
                "vnc_enabled": False
            },
            server.active_sandboxes
        )
        
        print(f"✅ Sandbox created: {json.dumps(result, indent=2)}")
        sandbox_name = result["sandbox_name"]
        
        # Execute Python code
        execute_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "execute_code")
        code_result = await execute_tool.execute(
            server.manager,
            {
                "sandbox_name": sandbox_name,
                "code": """
import numpy as np
import pandas as pd
from datetime import datetime

# Generate sample data
np.random.seed(42)
data = {
    'timestamp': pd.date_range(start='2024-01-01', periods=100, freq='D'),
    'value': np.random.randn(100).cumsum(),
    'category': np.random.choice(['A', 'B', 'C'], 100)
}

df = pd.DataFrame(data)
print("Dataset created:")
print(df.head())
print(f"\\nDataset shape: {df.shape}")
print(f"\\nSummary statistics:")
print(df['value'].describe())

# Save to file
df.to_csv('/tmp/sample_data.csv', index=False)
print(f"\\nData saved to /tmp/sample_data.csv")
""",
                "language": "python",
                "timeout": 60
            },
            server.active_sandboxes
        )
        
        print(f"📊 Code execution result:")
        print(f"Success: {code_result['success']}")
        print(f"Output:\n{code_result['stdout']}")
        
        # Download the generated file
        download_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "download_file")
        download_result = await download_tool.execute(
            server.manager,
            {
                "sandbox_name": sandbox_name,
                "remote_path": "/tmp/sample_data.csv",
                "encoding": "text"
            },
            server.active_sandboxes
        )
        
        if download_result["success"]:
            print(f"📥 Downloaded file content (first 200 chars):")
            print(download_result["content"][:200] + "...")
        
        # Create snapshot
        snapshot_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "create_snapshot")
        snapshot_result = await snapshot_tool.execute(
            server.manager,
            {
                "sandbox_name": sandbox_name,
                "snapshot_name": "data-analysis-complete",
                "description": "After generating and saving sample data"
            },
            server.active_sandboxes
        )
        
        print(f"💾 Snapshot created: {snapshot_result['snapshot_id']}")
        
    finally:
        # Cleanup
        await server.cleanup()


async def example_web_automation():
    """Example: Web automation with browser control."""
    print("\n🌐 MCP Example: Web Automation")
    print("=" * 60)
    
    server = MicroVMMCPServer()
    await server._init_manager()
    
    try:
        # Create web automation sandbox
        create_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "create_sandbox")
        result = await create_tool.execute(
            server.manager,
            {
                "template": "web-automation",
                "vcpus": 4,
                "memory_mb": 6144,
                "vnc_enabled": True
            },
            server.active_sandboxes
        )
        
        sandbox_name = result["sandbox_name"]
        print(f"✅ Web automation sandbox created: {sandbox_name}")
        
        # Get VNC info
        vnc_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "get_vnc_info")
        vnc_info = await vnc_tool.execute(
            server.manager,
            {"sandbox_name": sandbox_name},
            server.active_sandboxes
        )
        
        print(f"🖥️  VNC Access: {vnc_info['host']}:{vnc_info['port']}")
        
        # Execute web scraping script
        execute_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "execute_code")
        web_script = """
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import json
import time

# Configure Chrome for headless mode
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

# Create driver
driver = webdriver.Chrome(options=chrome_options)

try:
    # Navigate to example site
    driver.get('https://httpbin.org/json')
    time.sleep(2)
    
    # Get page content
    page_source = driver.page_source
    print(f"Page title: {driver.title}")
    print(f"Current URL: {driver.current_url}")
    
    # Try to extract JSON data
    try:
        body_element = driver.find_element(By.TAG_NAME, 'body')
        json_text = body_element.text
        data = json.loads(json_text)
        print("JSON data extracted:")
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"JSON extraction error: {e}")
    
    # Take screenshot
    driver.save_screenshot('/tmp/web_screenshot.png')
    print("Screenshot saved to /tmp/web_screenshot.png")
    
finally:
    driver.quit()
    print("Browser closed successfully")
"""
        
        web_result = await execute_tool.execute(
            server.manager,
            {
                "sandbox_name": sandbox_name,
                "code": web_script,
                "language": "python",
                "timeout": 120
            },
            server.active_sandboxes
        )
        
        print(f"🤖 Web automation result:")
        print(f"Success: {web_result['success']}")
        if web_result['success']:
            print(f"Output:\n{web_result['stdout']}")
        else:
            print(f"Error: {web_result['stderr']}")
        
    finally:
        await server.cleanup()


async def example_computer_use():
    """Example: Computer use with desktop interaction."""
    print("\n🖱️  MCP Example: Computer Use")
    print("=" * 60)
    
    server = MicroVMMCPServer()
    await server._init_manager()
    
    try:
        # Create computer use sandbox
        create_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "create_sandbox")
        result = await create_tool.execute(
            server.manager,
            {
                "template": "computer-use",
                "vcpus": 4,
                "memory_mb": 8192,
                "vnc_enabled": True
            },
            server.active_sandboxes
        )
        
        sandbox_name = result["sandbox_name"]
        print(f"✅ Computer use sandbox created: {sandbox_name}")
        
        # Wait for desktop to load
        print("⏳ Waiting for desktop to initialize...")
        await asyncio.sleep(15)
        
        # Take initial screenshot
        screenshot_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "take_screenshot")
        initial_screenshot = await screenshot_tool.execute(
            server.manager,
            {"sandbox_name": sandbox_name},
            server.active_sandboxes
        )
        
        if isinstance(initial_screenshot, bytes):
            print(f"📸 Initial screenshot captured ({len(initial_screenshot)} bytes)")
            
            # Save screenshot to file
            with open("/tmp/initial_desktop.png", "wb") as f:
                f.write(initial_screenshot)
            print("💾 Screenshot saved to /tmp/initial_desktop.png")
        
        # Perform some desktop interactions
        click_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "click")
        type_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "type_text")
        
        # Click on desktop (to focus)
        click_result = await click_tool.execute(
            server.manager,
            {
                "sandbox_name": sandbox_name,
                "x": 500,
                "y": 400,
                "button": "left"
            },
            server.active_sandboxes
        )
        print(f"🖱️  Desktop click: {click_result['success']}")
        
        # Open terminal using keyboard shortcut
        execute_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "execute_code")
        terminal_result = await execute_tool.execute(
            server.manager,
            {
                "sandbox_name": sandbox_name,
                "code": "xdotool key ctrl+alt+t",
                "language": "bash",
                "timeout": 10
            },
            server.active_sandboxes
        )
        
        await asyncio.sleep(3)
        
        # Type in terminal
        type_result = await type_tool.execute(
            server.manager,
            {
                "sandbox_name": sandbox_name,
                "text": "echo 'Hello from MCP Computer Use!' && date && uname -a"
            },
            server.active_sandboxes
        )
        print(f"⌨️  Text typed: {type_result['success']}")
        
        # Press Enter
        await execute_tool.execute(
            server.manager,
            {
                "sandbox_name": sandbox_name,
                "code": "xdotool key Return",
                "language": "bash",
                "timeout": 5
            },
            server.active_sandboxes
        )
        
        await asyncio.sleep(2)
        
        # Take final screenshot
        final_screenshot = await screenshot_tool.execute(
            server.manager,
            {"sandbox_name": sandbox_name},
            server.active_sandboxes
        )
        
        if isinstance(final_screenshot, bytes):
            with open("/tmp/final_desktop.png", "wb") as f:
                f.write(final_screenshot)
            print("📸 Final screenshot saved to /tmp/final_desktop.png")
        
        # Get sandbox info
        info_tool = next(tool for tool in AVAILABLE_TOOLS if tool.name == "get_sandbox_info")
        info_result = await info_tool.execute(
            server.manager,
            {"sandbox_name": sandbox_name},
            server.active_sandboxes
        )
        
        print(f"📊 Sandbox info:")
        print(f"  State: {info_result['sandbox_info']['state']}")
        print(f"  Template: {info_result['sandbox_info']['template']}")
        print(f"  Uptime: {info_result['sandbox_info']['uptime_seconds']} seconds")
        if info_result.get('resource_usage'):
            print(f"  CPU: {info_result['resource_usage']['cpu_percent']}%")
            print(f"  Memory: {info_result['resource_usage']['memory_percent']}%")
        
    finally:
        await server.cleanup()


async def example_codex_integration():
    """Example: OpenAI Codex integration."""
    print("\n🧠 MCP Example: Codex Integration")
    print("=" * 60)
    
    # Check if OpenAI API key is available
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY not set - skipping Codex example")
        return
    
    server = MicroVMMCPServer()
    await server._init_manager()
    
    try:
        # Test Codex integration if available
        if server.codex_integration:
            print("🤖 Testing Codex integration...")
            
            # Generate and execute code
            result = await server.codex_integration.codex_execute_with_context(
                prompt="Create a function to calculate fibonacci numbers and test it with the first 10 numbers",
                language="python",
                include_tests=True
            )
            
            print(f"✅ Codex execution:")
            print(f"Success: {result['success']}")
            print(f"\nGenerated code:")
            print(result['generated_code'])
            print(f"\nExecution output:")
            print(result['execution_result']['output'])
            
            if result.get('test_code'):
                print(f"\nGenerated tests:")
                print(result['test_code'])
        else:
            print("⚠️  Codex integration not available")
    
    finally:
        await server.cleanup()


async def main():
    """Run all MCP examples."""
    print("🚀 MicroVM Sandbox MCP Examples")
    print("=" * 70)
    
    examples = [
        example_create_and_execute,
        example_web_automation,
        example_computer_use,
        example_codex_integration
    ]
    
    for example in examples:
        try:
            await example()
        except Exception as e:
            print(f"❌ Example {example.__name__} failed: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "="*70 + "\n")
    
    print("✅ All MCP examples completed!")


if __name__ == "__main__":
    asyncio.run(main())