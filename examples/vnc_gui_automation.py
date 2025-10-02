#!/usr/bin/env python3
"""
VNC/GUI Automation Example

Demonstrates how to use VNC for desktop automation and visual AI agent workflows.
This example shows browser automation, screenshot analysis, and desktop interaction.
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


class VNCAutomationExample:
    """Example class demonstrating VNC automation capabilities."""
    
    def __init__(self, api_url: str = "http://localhost:8000", api_token: str = None):
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {api_token}"} if api_token else {}
        self.client = httpx.AsyncClient()
        self.vm_name = "desktop-automation-vm"
        
    async def setup_desktop_vm(self) -> Dict[str, Any]:
        """Create and configure a desktop VM for automation."""
        print("🖥️  Setting up desktop VM...")
        
        # Create VM with desktop template
        vm_config = {
            "name": self.vm_name,
            "template": "computer-use",  # Full desktop environment
            "vcpus": 6,
            "memory_mb": 8192,
            "guest_agent": True,
            "metadata": {
                "purpose": "vnc-automation-demo",
                "features": ["desktop", "vnc", "automation"]
            }
        }
        
        response = await self.client.post(
            f"{self.api_url}/api/v1/vms",
            headers=self.headers,
            json=vm_config
        )
        response.raise_for_status()
        vm_info = response.json()
        
        print(f"✅ Created VM: {vm_info['name']}")
        
        # Start the VM
        await self.client.post(
            f"{self.api_url}/api/v1/vms/{self.vm_name}/start",
            headers=self.headers
        )
        
        print("⏳ Waiting for VM to boot...")
        await asyncio.sleep(30)  # Wait for desktop environment to load
        
        return vm_info
    
    async def start_vnc_server(self) -> Dict[str, Any]:
        """Start VNC server for the desktop VM."""
        print("🖼️  Starting VNC server...")
        
        vnc_config = {
            "vm_name": self.vm_name,
            "resolution": "1920x1080",
            "color_depth": 24,
            "performance_mode": "balanced"
        }
        
        response = await self.client.post(
            f"{self.api_url}/api/v1/vnc/start",
            headers=self.headers,
            json=vnc_config
        )
        response.raise_for_status()
        vnc_info = response.json()
        
        print(f"✅ VNC Server running on port {vnc_info['port']}")
        print(f"🔐 VNC Password: {vnc_info['password']}")
        
        return vnc_info
    
    async def take_screenshot(self, format: str = "png") -> Image.Image:
        """Take a screenshot of the desktop."""
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
        """Click at specific coordinates."""
        await self.client.post(
            f"{self.api_url}/api/v1/vnc/mouse/click",
            headers=self.headers,
            json={
                "vm_name": self.vm_name,
                "x": x,
                "y": y,
                "button": button
            }
        )
    
    async def type_text(self, text: str) -> None:
        """Type text into the desktop."""
        await self.client.post(
            f"{self.api_url}/api/v1/vnc/keyboard/type",
            headers=self.headers,
            json={
                "vm_name": self.vm_name,
                "text": text
            }
        )
    
    async def send_keys(self, keys: str) -> None:
        """Send key combination."""
        await self.client.post(
            f"{self.api_url}/api/v1/vnc/keyboard/keys",
            headers=self.headers,
            json={
                "vm_name": self.vm_name,
                "keys": keys
            }
        )
    
    async def open_terminal(self) -> None:
        """Open a terminal window."""
        print("💻 Opening terminal...")
        await self.send_keys("ctrl+alt+t")
        await asyncio.sleep(2)  # Wait for terminal to open
    
    async def open_firefox(self) -> None:
        """Open Firefox browser."""
        print("🦊 Opening Firefox...")
        
        # Open application menu
        await self.send_keys("Super_L")  # Super/Windows key
        await asyncio.sleep(1)
        
        # Type to search for Firefox
        await self.type_text("firefox")
        await asyncio.sleep(1)
        
        # Press Enter to launch
        await self.send_keys("Return")
        await asyncio.sleep(5)  # Wait for Firefox to load
    
    async def navigate_to_website(self, url: str) -> None:
        """Navigate to a specific website."""
        print(f"🌐 Navigating to {url}...")
        
        # Focus address bar (Ctrl+L)
        await self.send_keys("ctrl+l")
        await asyncio.sleep(1)
        
        # Type URL
        await self.type_text(url)
        await asyncio.sleep(1)
        
        # Press Enter
        await self.send_keys("Return")
        await asyncio.sleep(3)  # Wait for page to load
    
    async def automated_web_browsing_demo(self) -> None:
        """Demonstrate automated web browsing."""
        print("🌐 Starting automated web browsing demo...")
        
        # Open Firefox
        await self.open_firefox()
        
        # Navigate to a test website
        await self.navigate_to_website("https://httpbin.org/")
        
        # Take screenshot of the website
        screenshot = await self.take_screenshot()
        screenshot.save("httpbin_homepage.png")
        print("📸 Saved screenshot: httpbin_homepage.png")
        
        # Navigate to JSON endpoint
        await self.navigate_to_website("https://httpbin.org/json")
        await asyncio.sleep(2)
        
        # Take another screenshot
        screenshot = await self.take_screenshot()
        screenshot.save("httpbin_json.png")
        print("📸 Saved screenshot: httpbin_json.png")
        
        # Select all text (Ctrl+A)
        await self.send_keys("ctrl+a")
        await asyncio.sleep(1)
        
        # Copy text (Ctrl+C)
        await self.send_keys("ctrl+c")
        await asyncio.sleep(1)
    
    async def text_editor_automation_demo(self) -> None:
        """Demonstrate text editor automation."""
        print("📝 Starting text editor automation demo...")
        
        # Open terminal
        await self.open_terminal()
        
        # Launch nano editor
        await self.type_text("nano demo_file.txt")
        await self.send_keys("Return")
        await asyncio.sleep(2)
        
        # Type some content
        demo_content = """# VNC Automation Demo
        
This file was created through VNC automation!

Features demonstrated:
- Desktop interaction
- Keyboard input
- Mouse control
- Screenshot capture
- Application automation

Timestamp: """ + str(int(time.time()))
        
        await self.type_text(demo_content)
        await asyncio.sleep(1)
        
        # Save file (Ctrl+O)
        await self.send_keys("ctrl+o")
        await asyncio.sleep(1)
        await self.send_keys("Return")  # Confirm filename
        await asyncio.sleep(1)
        
        # Exit nano (Ctrl+X)
        await self.send_keys("ctrl+x")
        await asyncio.sleep(1)
        
        # Verify file was created
        await self.type_text("ls -la demo_file.txt")
        await self.send_keys("Return")
        await asyncio.sleep(1)
        
        # Take screenshot of terminal
        screenshot = await self.take_screenshot()
        screenshot.save("terminal_demo.png")
        print("📸 Saved screenshot: terminal_demo.png")
    
    async def desktop_application_demo(self) -> None:
        """Demonstrate desktop application interaction."""
        print("🖥️  Starting desktop application demo...")
        
        # Open file manager
        await self.send_keys("Super_L")
        await asyncio.sleep(1)
        await self.type_text("files")
        await asyncio.sleep(1)
        await self.send_keys("Return")
        await asyncio.sleep(3)
        
        # Navigate to home directory
        await self.send_keys("ctrl+h")
        await asyncio.sleep(2)
        
        # Take screenshot of file manager
        screenshot = await self.take_screenshot()
        screenshot.save("file_manager.png")
        print("📸 Saved screenshot: file_manager.png")
        
        # Create a new folder
        await self.send_keys("ctrl+shift+n")
        await asyncio.sleep(1)
        await self.type_text("VNC_Demo_Folder")
        await self.send_keys("Return")
        await asyncio.sleep(1)
        
        # Double-click to enter the folder
        await self.click_at(960, 400)  # Approximate center of screen
        await asyncio.sleep(1)
        await self.click_at(960, 400)  # Double-click
        await asyncio.sleep(2)
    
    async def visual_element_detection_demo(self) -> None:
        """Demonstrate basic visual element detection."""
        print("👁️  Starting visual element detection demo...")
        
        # Take a screenshot
        screenshot = await self.take_screenshot()
        
        # Simple color analysis (basic example)
        width, height = screenshot.size
        
        # Sample colors at different positions
        positions = [
            (100, 100),   # Top-left area
            (width//2, height//2),  # Center
            (width-100, height-100)  # Bottom-right area
        ]
        
        print("🎨 Color analysis at key positions:")
        for i, (x, y) in enumerate(positions):
            color = screenshot.getpixel((x, y))
            print(f"  Position {i+1} ({x}, {y}): RGB{color}")
        
        # Save analyzed screenshot
        screenshot.save("visual_analysis.png")
        print("📸 Saved screenshot with analysis: visual_analysis.png")
    
    async def run_complete_demo(self) -> None:
        """Run the complete VNC automation demonstration."""
        print("🚀 Starting Complete VNC Automation Demo")
        print("=" * 50)
        
        try:
            # Setup
            await self.setup_desktop_vm()
            await self.start_vnc_server()
            
            # Wait for desktop to fully load
            print("⏳ Waiting for desktop environment to initialize...")
            await asyncio.sleep(10)
            
            # Take initial screenshot
            initial_screenshot = await self.take_screenshot()
            initial_screenshot.save("desktop_initial.png")
            print("📸 Saved initial desktop screenshot")
            
            # Run demonstrations
            await self.automated_web_browsing_demo()
            await asyncio.sleep(3)
            
            await self.text_editor_automation_demo()
            await asyncio.sleep(3)
            
            await self.desktop_application_demo()
            await asyncio.sleep(3)
            
            await self.visual_element_detection_demo()
            
            # Final screenshot
            final_screenshot = await self.take_screenshot()
            final_screenshot.save("desktop_final.png")
            print("📸 Saved final desktop screenshot")
            
            print("\n✅ VNC Automation Demo completed successfully!")
            print("📁 Screenshots saved in current directory")
            
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
            
            # Stop and delete VM
            await self.client.post(
                f"{self.api_url}/api/v1/vms/{self.vm_name}/stop",
                headers=self.headers
            )
            
            await self.client.delete(
                f"{self.api_url}/api/v1/vms/{self.vm_name}",
                headers=self.headers
            )
            
            await self.client.aclose()
            print("✅ Cleanup completed")
            
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")


async def main():
    """Main function to run the VNC automation demo."""
    import os
    
    # Get API token from environment
    api_token = os.getenv("MICROVM_API_TOKEN")
    if not api_token:
        print("⚠️  Warning: No API token found. Set MICROVM_API_TOKEN environment variable.")
    
    # Create and run demo
    demo = VNCAutomationExample(api_token=api_token)
    await demo.run_complete_demo()


if __name__ == "__main__":
    asyncio.run(main())