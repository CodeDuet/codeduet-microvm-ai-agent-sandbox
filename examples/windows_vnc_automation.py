#!/usr/bin/env python3
"""
Windows VNC Automation Example

Demonstrates how to use VNC with Windows VMs through Cloud Hypervisor's built-in
VNC console for desktop automation and visual AI agent workflows.
"""

import asyncio
import base64
import io
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
from PIL import Image


class WindowsVNCAutomationExample:
    """Example class demonstrating Windows VNC automation capabilities."""
    
    def __init__(self, api_url: str = "http://localhost:8000", api_token: str = None):
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {api_token}"} if api_token else {}
        self.client = httpx.AsyncClient()
        self.vm_name = "windows-desktop-vnc"
        
    async def setup_windows_vm(self) -> Dict[str, Any]:
        """Create and configure a Windows VM for VNC automation."""
        print("🖥️  Setting up Windows VM with VNC support...")
        
        # Create Windows VM with desktop template
        vm_config = {
            "name": self.vm_name,
            "template": "windows-desktop",  # Windows desktop environment
            "vcpus": 6,
            "memory_mb": 4096,
            "guest_agent": True,
            "metadata": {
                "purpose": "windows-vnc-automation-demo",
                "features": ["windows", "vnc", "desktop", "automation"]
            }
        }
        
        response = await self.client.post(
            f"{self.api_url}/api/v1/vms",
            headers=self.headers,
            json=vm_config
        )
        response.raise_for_status()
        vm_info = response.json()
        
        print(f"✅ Created Windows VM: {vm_info['name']}")
        
        # Start the VM
        await self.client.post(
            f"{self.api_url}/api/v1/vms/{self.vm_name}/start",
            headers=self.headers
        )
        
        print("⏳ Waiting for Windows to boot... (this may take 2-3 minutes)")
        await asyncio.sleep(120)  # Windows takes longer to boot than Linux
        
        return vm_info
    
    async def start_vnc_server(self) -> Dict[str, Any]:
        """Start hypervisor VNC server for the Windows VM."""
        print("🖼️  Starting hypervisor VNC server for Windows...")
        
        vnc_config = {
            "vm_name": self.vm_name,
            "port": 5901,  # Use a specific port for Windows VNC
            "resolution": "1920x1080",
            "color_depth": 24,
            "performance_mode": "quality"
        }
        
        response = await self.client.post(
            f"{self.api_url}/api/v1/vnc/start",
            headers=self.headers,
            json=vnc_config
        )
        response.raise_for_status()
        vnc_info = response.json()
        
        print(f"✅ Windows VNC Server running on port {vnc_info['port']}")
        print(f"🔐 VNC Password: {vnc_info['password']}")
        print(f"🖥️  VNC Type: {vnc_info['vnc_type']} ({vnc_info['os_type']})")
        
        # Provide connection instructions
        print("\n📋 Connection Instructions:")
        print(f"   VNC Client: localhost:{vnc_info['port']}")
        print(f"   Password: {vnc_info['password']}")
        print(f"   Resolution: {vnc_config['resolution']}")
        
        return vnc_info
    
    async def take_screenshot(self, format: str = "png") -> Image.Image:
        """Take a screenshot of the Windows desktop."""
        response = await self.client.post(
            f"{self.api_url}/api/v1/vnc/screenshot",
            headers=self.headers,
            json={"vm_name": self.vm_name, "format": format}
        )
        response.raise_for_status()
        
        screenshot_data = response.json()
        image_bytes = base64.b64decode(screenshot_data["image_data"])
        return Image.open(io.BytesIO(image_bytes))
    
    async def click_at(self, x: int, y: int, button: str = "left") -> None:
        """Click at specific coordinates on Windows desktop."""
        button_map = {"left": 1, "middle": 2, "right": 3}
        await self.client.post(
            f"{self.api_url}/api/v1/vnc/mouse/click",
            headers=self.headers,
            json={
                "vm_name": self.vm_name,
                "x": x,
                "y": y,
                "button": button_map.get(button, 1)
            }
        )
    
    async def type_text(self, text: str) -> None:
        """Type text into Windows."""
        await self.client.post(
            f"{self.api_url}/api/v1/vnc/keyboard/type",
            headers=self.headers,
            json={
                "vm_name": self.vm_name,
                "text": text
            }
        )
    
    async def send_keys(self, keys: str) -> None:
        """Send key combination to Windows."""
        await self.client.post(
            f"{self.api_url}/api/v1/vnc/keyboard/keys",
            headers=self.headers,
            json={
                "vm_name": self.vm_name,
                "keys": keys
            }
        )
    
    async def open_start_menu(self) -> None:
        """Open Windows Start menu."""
        print("🪟 Opening Windows Start menu...")
        await self.send_keys("Super_L")  # Windows key
        await asyncio.sleep(2)
    
    async def open_command_prompt(self) -> None:
        """Open Windows Command Prompt."""
        print("💻 Opening Command Prompt...")
        
        # Open Run dialog
        await self.send_keys("Super_L+r")
        await asyncio.sleep(1)
        
        # Type cmd and press Enter
        await self.type_text("cmd")
        await asyncio.sleep(1)
        await self.send_keys("Return")
        await asyncio.sleep(3)  # Wait for Command Prompt to open
    
    async def open_powershell(self) -> None:
        """Open Windows PowerShell."""
        print("⚡ Opening PowerShell...")
        
        # Open Run dialog
        await self.send_keys("Super_L+r")
        await asyncio.sleep(1)
        
        # Type powershell and press Enter
        await self.type_text("powershell")
        await asyncio.sleep(1)
        await self.send_keys("Return")
        await asyncio.sleep(3)  # Wait for PowerShell to open
    
    async def open_notepad(self) -> None:
        """Open Windows Notepad."""
        print("📝 Opening Notepad...")
        
        # Open Run dialog
        await self.send_keys("Super_L+r")
        await asyncio.sleep(1)
        
        # Type notepad and press Enter
        await self.type_text("notepad")
        await asyncio.sleep(1)
        await self.send_keys("Return")
        await asyncio.sleep(2)  # Wait for Notepad to open
    
    async def windows_automation_demo(self) -> None:
        """Demonstrate Windows-specific automation tasks."""
        print("🪟 Starting Windows automation demo...")
        
        # Take initial screenshot
        initial_screenshot = await self.take_screenshot()
        initial_screenshot.save("windows_desktop_initial.png")
        print("📸 Saved initial Windows desktop screenshot")
        
        # Open PowerShell and run some commands
        await self.open_powershell()
        
        # Wait for PowerShell to load, then type some commands
        await asyncio.sleep(3)
        
        # Get system information
        await self.type_text("Get-ComputerInfo | Select-Object WindowsProductName, TotalPhysicalMemory")
        await self.send_keys("Return")
        await asyncio.sleep(2)
        
        # Get running processes
        await self.type_text("Get-Process | Select-Object -First 10 Name, CPU, WorkingSet")
        await self.send_keys("Return")
        await asyncio.sleep(2)
        
        # Take screenshot of PowerShell
        powershell_screenshot = await self.take_screenshot()
        powershell_screenshot.save("windows_powershell_demo.png")
        print("📸 Saved PowerShell screenshot")
        
        # Minimize PowerShell (Alt+F9)
        await self.send_keys("alt+F9")
        await asyncio.sleep(1)
        
        # Open Notepad
        await self.open_notepad()
        
        # Type some content in Notepad
        demo_content = f"""Windows VNC Automation Demo
        
This content was typed through VNC automation!

System Information:
- VM Name: {self.vm_name}
- VNC Type: Hypervisor Console
- OS Type: Windows
- Automation: Via Cloud Hypervisor VNC

Features demonstrated:
✓ Windows desktop interaction
✓ Application launching (PowerShell, Notepad)
✓ Keyboard input automation
✓ Mouse control
✓ Screenshot capture
✓ Window management

Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        await self.type_text(demo_content)
        await asyncio.sleep(1)
        
        # Save the file (Ctrl+S)
        await self.send_keys("ctrl+s")
        await asyncio.sleep(1)
        
        # Type filename
        await self.type_text("VNC_Automation_Demo.txt")
        await self.send_keys("Return")
        await asyncio.sleep(1)
        
        # Take screenshot of Notepad
        notepad_screenshot = await self.take_screenshot()
        notepad_screenshot.save("windows_notepad_demo.png")
        print("📸 Saved Notepad screenshot")
    
    async def file_explorer_demo(self) -> None:
        """Demonstrate Windows File Explorer automation."""
        print("📁 Starting File Explorer demo...")
        
        # Open File Explorer (Windows + E)
        await self.send_keys("Super_L+e")
        await asyncio.sleep(3)
        
        # Navigate to Documents
        await self.send_keys("alt+d")  # Focus address bar
        await asyncio.sleep(1)
        await self.type_text("Documents")
        await self.send_keys("Return")
        await asyncio.sleep(2)
        
        # Take screenshot of File Explorer
        explorer_screenshot = await self.take_screenshot()
        explorer_screenshot.save("windows_explorer_demo.png")
        print("📸 Saved File Explorer screenshot")
        
        # Create a new folder (Ctrl+Shift+N)
        await self.send_keys("ctrl+shift+n")
        await asyncio.sleep(1)
        await self.type_text("VNC_Demo_Folder")
        await self.send_keys("Return")
        await asyncio.sleep(1)
    
    async def browser_automation_demo(self) -> None:
        """Demonstrate web browser automation on Windows."""
        print("🌐 Starting browser automation demo...")
        
        # Open Microsoft Edge (default Windows browser)
        await self.send_keys("Super_L+r")
        await asyncio.sleep(1)
        await self.type_text("msedge")
        await self.send_keys("Return")
        await asyncio.sleep(5)  # Wait for browser to load
        
        # Navigate to a test website
        await self.send_keys("ctrl+l")  # Focus address bar
        await asyncio.sleep(1)
        await self.type_text("https://httpbin.org/")
        await self.send_keys("Return")
        await asyncio.sleep(3)  # Wait for page to load
        
        # Take screenshot of browser
        browser_screenshot = await self.take_screenshot()
        browser_screenshot.save("windows_browser_demo.png")
        print("📸 Saved browser screenshot")
        
        # Test some navigation
        await self.send_keys("ctrl+l")
        await asyncio.sleep(1)
        await self.type_text("https://httpbin.org/json")
        await self.send_keys("Return")
        await asyncio.sleep(2)
        
        # Take another screenshot
        json_screenshot = await self.take_screenshot()
        json_screenshot.save("windows_browser_json.png")
        print("📸 Saved JSON page screenshot")
    
    async def desktop_interaction_demo(self) -> None:
        """Demonstrate desktop-level interactions."""
        print("🖱️  Starting desktop interaction demo...")
        
        # Right-click on desktop
        await self.click_at(500, 400, "right")
        await asyncio.sleep(1)
        
        # Take screenshot of context menu
        context_screenshot = await self.take_screenshot()
        context_screenshot.save("windows_context_menu.png")
        print("📸 Saved context menu screenshot")
        
        # Click elsewhere to dismiss menu
        await self.click_at(100, 100, "left")
        await asyncio.sleep(1)
        
        # Open Task Manager (Ctrl+Shift+Esc)
        await self.send_keys("ctrl+shift+Escape")
        await asyncio.sleep(3)
        
        # Take screenshot of Task Manager
        taskmanager_screenshot = await self.take_screenshot()
        taskmanager_screenshot.save("windows_task_manager.png")
        print("📸 Saved Task Manager screenshot")
        
        # Close Task Manager (Alt+F4)
        await self.send_keys("alt+F4")
        await asyncio.sleep(1)
    
    async def run_complete_demo(self) -> None:
        """Run the complete Windows VNC automation demonstration."""
        print("🚀 Starting Complete Windows VNC Automation Demo")
        print("=" * 60)
        
        try:
            # Setup
            await self.setup_windows_vm()
            vnc_info = await self.start_vnc_server()
            
            # Wait for Windows desktop to be ready
            print("⏳ Waiting for Windows desktop to be ready...")
            await asyncio.sleep(10)
            
            # Take initial screenshot to verify desktop is ready
            initial_screenshot = await self.take_screenshot()
            initial_screenshot.save("windows_initial.png")
            print("📸 Saved initial Windows desktop screenshot")
            
            # Run demonstration modules
            await self.windows_automation_demo()
            await asyncio.sleep(3)
            
            await self.file_explorer_demo()
            await asyncio.sleep(3)
            
            await self.browser_automation_demo()
            await asyncio.sleep(3)
            
            await self.desktop_interaction_demo()
            await asyncio.sleep(3)
            
            # Final screenshot
            final_screenshot = await self.take_screenshot()
            final_screenshot.save("windows_final.png")
            print("📸 Saved final Windows desktop screenshot")
            
            print("\n✅ Windows VNC Automation Demo completed successfully!")
            print("📁 Screenshots saved in current directory")
            print(f"🔗 VNC Connection: localhost:{vnc_info['port']}")
            print(f"🔐 VNC Password: {vnc_info['password']}")
            
            # Provide connection instructions
            print("\n📋 Manual VNC Connection Instructions:")
            print("   1. Install a VNC client (TigerVNC, RealVNC, etc.)")
            print(f"   2. Connect to: localhost:{vnc_info['port']}")
            print(f"   3. Use password: {vnc_info['password']}")
            print("   4. You should see the Windows desktop!")
            
        except Exception as e:
            print(f"❌ Demo failed: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        print("🧹 Cleaning up...")
        
        try:
            # Stop VNC server
            await self.client.post(
                f"{self.api_url}/api/v1/vnc/stop",
                headers=self.headers,
                params={"vm_name": self.vm_name}
            )
            
            # Note: Keep VM running for manual testing
            print("💡 Keeping Windows VM running for manual VNC testing")
            print(f"   To delete later: DELETE /api/v1/vms/{self.vm_name}")
            
            await self.client.aclose()
            print("✅ Cleanup completed")
            
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")


async def main():
    """Main function to run the Windows VNC automation demo."""
    import os
    
    # Get API token from environment
    api_token = os.getenv("MICROVM_API_TOKEN")
    if not api_token:
        print("⚠️  Warning: No API token found. Set MICROVM_API_TOKEN environment variable.")
    
    # Create and run demo
    demo = WindowsVNCAutomationExample(api_token=api_token)
    await demo.run_complete_demo()


if __name__ == "__main__":
    asyncio.run(main())