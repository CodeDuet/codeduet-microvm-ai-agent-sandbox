#!/usr/bin/env python3
"""
Example usage of the py-microvm SDK for AI agent automation.

This script demonstrates how to use the MicroVM SDK for various AI agent tasks:
- Code execution in isolated sandboxes
- Web automation with browser control
- Computer use with visual interaction
- Snapshot and restore for backtracking
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for SDK import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.sdk import MicroVMManager, SecurityContext
from src.sdk.models import SandboxConfig, OSType


async def code_execution_example():
    """Example: Safe code execution in isolated sandbox."""
    print("🔬 Code Execution Example")
    print("=" * 50)
    
    # Initialize manager with security context
    security_context = SecurityContext(
        api_token="your-jwt-token",  # Replace with actual token
        user_id="ai-agent",
        audit_enabled=True
    )
    
    async with MicroVMManager("http://localhost:8000", security_context) as manager:
        # Start code interpreter sandbox
        async with manager.start_sandbox("code-interpreter") as sandbox:
            print(f"✅ Created sandbox: {sandbox.name}")
            
            # Execute Python code
            result = await sandbox.run_command("python3 -c 'print(\"Hello from MicroVM!\")'")
            print(f"📤 Output: {result.output}")
            
            # Upload a Python script
            script_content = """
import numpy as np
import pandas as pd

# Generate sample data
data = np.random.randn(100, 3)
df = pd.DataFrame(data, columns=['A', 'B', 'C'])

print("Data shape:", df.shape)
print("\\nSummary statistics:")
print(df.describe())

# Save to file
df.to_csv('/tmp/analysis.csv', index=False)
print("\\nData saved to /tmp/analysis.csv")
"""
            
            with open("/tmp/analysis_script.py", "w") as f:
                f.write(script_content)
            
            await sandbox.upload_file("/tmp/analysis_script.py", "/tmp/analysis_script.py")
            print("📁 Uploaded analysis script")
            
            # Execute the script
            result = await sandbox.run_command("python3 /tmp/analysis_script.py", timeout=60)
            print(f"📊 Analysis output:\n{result.output}")
            
            # Download the results
            await sandbox.download_file("/tmp/analysis.csv", "/tmp/results.csv")
            print("📥 Downloaded results to /tmp/results.csv")


async def web_automation_example():
    """Example: Web automation with browser control."""
    print("\n🌐 Web Automation Example")
    print("=" * 50)
    
    async with MicroVMManager("http://localhost:8000") as manager:
        # Create web automation sandbox
        config = SandboxConfig(
            name="web-scraper",
            template="web-automation",
            vcpus=4,
            memory_mb=6144,
            vnc_enabled=True
        )
        
        async with manager.start_sandbox(config=config) as sandbox:
            print(f"✅ Created web automation sandbox: {sandbox.name}")
            
            # Get VNC info for visual monitoring
            vnc_info = await sandbox.get_vnc_info()
            print(f"🖥️  VNC available at: {vnc_info.host}:{vnc_info.port}")
            
            # Install and run Selenium script
            selenium_script = """
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

# Configure Chrome for headless automation
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

# Create driver
driver = webdriver.Chrome(options=chrome_options)

try:
    # Navigate to example site
    driver.get('https://httpbin.org/html')
    print(f"Page title: {driver.title}")
    
    # Find and extract text
    h1_element = driver.find_element(By.TAG_NAME, 'h1')
    print(f"H1 text: {h1_element.text}")
    
    # Take screenshot
    driver.save_screenshot('/tmp/screenshot.png')
    print("Screenshot saved to /tmp/screenshot.png")
    
finally:
    driver.quit()
    
print("Web automation completed successfully!")
"""
            
            with open("/tmp/selenium_script.py", "w") as f:
                f.write(selenium_script)
            
            await sandbox.upload_file("/tmp/selenium_script.py", "/tmp/selenium_script.py")
            
            # Run the web automation
            result = await sandbox.run_command("python3 /tmp/selenium_script.py", timeout=120)
            print(f"🤖 Automation output:\n{result.output}")
            
            # Download screenshot
            await sandbox.download_file("/tmp/screenshot.png", "/tmp/web_screenshot.png")
            print("📸 Downloaded screenshot")


async def computer_use_example():
    """Example: Computer use with visual interaction."""
    print("\n🖱️  Computer Use Example")
    print("=" * 50)
    
    async with MicroVMManager("http://localhost:8000") as manager:
        # Start computer use sandbox with full desktop
        config = SandboxConfig(
            name="desktop-agent",
            template="computer-use",
            vcpus=6,
            memory_mb=8192,
            vnc_enabled=True
        )
        
        async with manager.start_sandbox(config=config) as sandbox:
            print(f"✅ Created desktop sandbox: {sandbox.name}")
            
            # Take initial screenshot
            screenshot = await sandbox.take_screenshot()
            if screenshot.success:
                with open("/tmp/initial_desktop.png", "wb") as f:
                    f.write(screenshot.image_data)
                print("📸 Captured initial desktop screenshot")
            
            # Wait for desktop to load
            await asyncio.sleep(10)
            
            # Click to open application menu (GNOME)
            click_result = await sandbox.click(50, 50)  # Top-left corner
            print(f"🖱️  Clicked application menu: {click_result.success}")
            
            await asyncio.sleep(2)
            
            # Type to search for terminal
            type_result = await sandbox.type_text("terminal")
            print(f"⌨️  Typed 'terminal': {type_result.success}")
            
            await asyncio.sleep(1)
            
            # Press Enter to open terminal
            await sandbox.run_command("xdotool key Return", timeout=10)
            
            await asyncio.sleep(3)
            
            # Take screenshot after opening terminal
            screenshot = await sandbox.take_screenshot()
            if screenshot.success:
                with open("/tmp/terminal_opened.png", "wb") as f:
                    f.write(screenshot.image_data)
                print("📸 Captured terminal screenshot")
            
            # Type command in terminal using guest agent
            terminal_command = """
echo "Hello from AI agent!"
python3 -c "print('Computer use automation working!')"
ls -la
"""
            
            # Since we opened terminal, we can now type directly
            for line in terminal_command.strip().split('\n'):
                await sandbox.type_text(line)
                await sandbox.run_command("xdotool key Return", timeout=5)
                await asyncio.sleep(1)
            
            # Final screenshot
            screenshot = await sandbox.take_screenshot()
            if screenshot.success:
                with open("/tmp/final_desktop.png", "wb") as f:
                    f.write(screenshot.image_data)
                print("📸 Captured final desktop screenshot")


async def snapshot_restore_example():
    """Example: Snapshot and restore for AI agent backtracking."""
    print("\n💾 Snapshot & Restore Example")
    print("=" * 50)
    
    async with MicroVMManager("http://localhost:8000") as manager:
        async with manager.start_sandbox("ai-agent") as sandbox:
            print(f"✅ Created sandbox: {sandbox.name}")
            
            # Initial state
            await sandbox.run_command("echo 'Initial state' > /tmp/state.txt")
            
            # Create checkpoint snapshot
            checkpoint = await sandbox.snapshot("checkpoint", "Before making changes")
            print(f"💾 Created checkpoint: {checkpoint.id}")
            
            # Make some changes
            await sandbox.run_command("echo 'Modified state' > /tmp/state.txt")
            await sandbox.run_command("mkdir -p /tmp/new_directory")
            await sandbox.run_command("touch /tmp/new_directory/file.txt")
            
            # Verify changes
            result = await sandbox.run_command("cat /tmp/state.txt")
            print(f"📝 Current state: {result.output.strip()}")
            
            # Create another snapshot
            modified = await sandbox.snapshot("modified", "After modifications")
            print(f"💾 Created modified snapshot: {modified.id}")
            
            # Restore to checkpoint
            await sandbox.restore(checkpoint.id)
            print("🔄 Restored to checkpoint")
            
            # Verify restoration
            result = await sandbox.run_command("cat /tmp/state.txt")
            print(f"📝 Restored state: {result.output.strip()}")
            
            # Check that new directory is gone
            result = await sandbox.run_command("ls /tmp/new_directory", timeout=5)
            if result.exit_code != 0:
                print("✅ Directory correctly removed after restore")
            
            # Restore to modified state
            await sandbox.restore(modified.id)
            result = await sandbox.run_command("cat /tmp/state.txt")
            print(f"📝 Re-modified state: {result.output.strip()}")


async def ai_agent_workflow_example():
    """Example: Complete AI agent workflow with error handling."""
    print("\n🤖 AI Agent Workflow Example")
    print("=" * 50)
    
    async with MicroVMManager("http://localhost:8000") as manager:
        async with manager.start_sandbox("ai-agent") as sandbox:
            print(f"✅ Created AI agent sandbox: {sandbox.name}")
            
            # Step 1: Setup working environment
            setup_commands = [
                "mkdir -p /tmp/ai_workspace",
                "cd /tmp/ai_workspace",
                "python3 -m venv ai_env",
                "source ai_env/bin/activate && pip install requests beautifulsoup4 pandas"
            ]
            
            for cmd in setup_commands:
                result = await sandbox.run_command(cmd, timeout=60)
                if not result.success:
                    print(f"❌ Setup failed: {cmd}")
                    return
            
            print("🔧 Environment setup complete")
            
            # Step 2: Create a web scraping script
            scraper_code = """
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json

def scrape_quotes():
    url = "http://quotes.toscrape.com/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    quotes = []
    for quote in soup.find_all('div', class_='quote'):
        text = quote.find('span', class_='text').text
        author = quote.find('small', class_='author').text
        tags = [tag.text for tag in quote.find_all('a', class_='tag')]
        
        quotes.append({
            'text': text,
            'author': author,
            'tags': tags
        })
    
    return quotes

# Scrape quotes
quotes_data = scrape_quotes()
print(f"Scraped {len(quotes_data)} quotes")

# Save as JSON
with open('/tmp/quotes.json', 'w') as f:
    json.dump(quotes_data, f, indent=2)

# Create pandas DataFrame and save as CSV
df = pd.DataFrame(quotes_data)
df['tags'] = df['tags'].apply(lambda x: ', '.join(x))
df.to_csv('/tmp/quotes.csv', index=False)

print("Data saved to /tmp/quotes.json and /tmp/quotes.csv")

# Display first few quotes
for i, quote in enumerate(quotes_data[:3]):
    print(f"\\nQuote {i+1}:")
    print(f"Text: {quote['text']}")
    print(f"Author: {quote['author']}")
    print(f"Tags: {', '.join(quote['tags'])}")
"""
            
            with open("/tmp/scraper.py", "w") as f:
                f.write(scraper_code)
            
            await sandbox.upload_file("/tmp/scraper.py", "/tmp/ai_workspace/scraper.py")
            
            # Step 3: Create checkpoint before execution
            checkpoint = await sandbox.snapshot("before-scraping", "Before running web scraper")
            
            # Step 4: Execute the scraper
            result = await sandbox.run_command(
                "cd /tmp/ai_workspace && source ai_env/bin/activate && python scraper.py",
                timeout=120
            )
            
            if result.success:
                print(f"🕷️  Scraping completed:\n{result.output}")
                
                # Download results
                await sandbox.download_file("/tmp/quotes.json", "/tmp/scraped_quotes.json")
                await sandbox.download_file("/tmp/quotes.csv", "/tmp/scraped_quotes.csv")
                print("📥 Downloaded scraping results")
                
            else:
                print(f"❌ Scraping failed: {result.error}")
                # Restore to checkpoint and try alternative approach
                await sandbox.restore(checkpoint.id)
                print("🔄 Restored to checkpoint for retry")
            
            # Step 5: Get sandbox metrics
            metrics = await sandbox.get_metrics()
            print(f"📊 Sandbox metrics:")
            print(f"   CPU usage: {metrics.resource_usage.cpu_percent if metrics.resource_usage else 'N/A'}%")
            print(f"   Memory usage: {metrics.resource_usage.memory_percent if metrics.resource_usage else 'N/A'}%")
            print(f"   Uptime: {metrics.sandbox_info.uptime_seconds} seconds")


async def main():
    """Run all examples."""
    print("🚀 MicroVM SDK Examples")
    print("=" * 60)
    
    try:
        await code_execution_example()
        await web_automation_example()
        await computer_use_example()
        await snapshot_restore_example()
        await ai_agent_workflow_example()
        
        print("\n✅ All examples completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())