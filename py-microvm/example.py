"""
Example usage of py-microvm client.
"""

import asyncio
from microvm_client import MicroVMClient


async def main():
    """Demonstrate basic SDK usage."""
    
    # Initialize client with secure defaults
    async with MicroVMClient(
        "https://api.microvm.dev",  # Replace with your API URL
        api_token="your-secure-token",  # Replace with your API token
        timeout=30,
        verify_ssl=True
    ) as client:
        
        print("🚀 Starting AI agent VM...")
        
        # Start VM with AI agent template
        vm = await client.start_vm("ai-agent", {
            "vcpus": 4,
            "memory_mb": 4096,
        })
        print(f"✅ VM started: {vm.id} ({vm.state})")
        
        # Execute secure command
        print("🐍 Checking Python version...")
        result = await client.exec_command(vm.id, "python --version")
        print(f"📋 Output: {result.stdout}")
        
        # Upload a script file (with size validation)
        print("📤 Would upload script.py (demo only)")
        # await client.upload_file(vm.id, "script.py", "/tmp/script.py")
        
        # List all VMs
        print("📝 Listing all VMs...")
        vms = await client.list_vms()
        for v in vms:
            print(f"  - {v.id}: {v.state} ({v.template})")
        
        # Clean up
        print("🧹 Destroying VM...")
        await client.destroy_vm(vm.id)
        print("✅ VM destroyed successfully!")


if __name__ == "__main__":
    asyncio.run(main())