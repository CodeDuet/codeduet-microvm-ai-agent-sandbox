# Quick Start Guide

This guide will help you get started with the MicroVM Sandbox in just a few minutes.

## Prerequisites

Before you begin, ensure you have:

- Ubuntu 20.04+ or RHEL 8+ (with KVM support)
- 4+ CPU cores with VT-x/AMD-V support
- 8GB+ RAM
- 50GB+ available disk space
- Python 3.9 or higher
- Docker (optional, for containerized deployment)

## Installation

### Option 1: Quick Setup Script

```bash
# Clone the repository
git clone https://github.com/your-org/microvm-sandbox.git
cd microvm-sandbox

# Run the automated setup
./scripts/setup/install-dependencies.sh
./scripts/setup/install-cloud-hypervisor.sh
./scripts/setup/setup-networking.sh
```

### Option 2: Manual Installation

1. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

2. **Install Cloud Hypervisor:**
```bash
wget https://github.com/cloud-hypervisor/cloud-hypervisor/releases/download/v34.0/cloud-hypervisor-static
sudo mv cloud-hypervisor-static /usr/local/bin/cloud-hypervisor
sudo chmod +x /usr/local/bin/cloud-hypervisor
```

3. **Setup networking:**
```bash
sudo ./scripts/setup/setup-networking.sh
```

## First Steps

### 1. Start the API Server

```bash
# Development mode
make dev-server

# Or manually
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### 2. Verify Installation

Check that everything is working:

```bash
curl http://localhost:8000/health
```

You should see:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-01T12:00:00Z",
  "components": {
    "api": "healthy",
    "cloud_hypervisor": "healthy",
    "network": "healthy"
  }
}
```

### 3. Create Your First VM

#### Using the CLI

```bash
# Create a Linux VM
python -m src.cli.main vm create my-first-vm --os linux --vcpus 2 --memory 512

# Start the VM
python -m src.cli.main vm start my-first-vm

# Check VM status
python -m src.cli.main vm info my-first-vm
```

#### Using the REST API

```bash
# Create a Linux VM
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-first-vm",
    "os_type": "linux",
    "vcpus": 2,
    "memory_mb": 512,
    "template": "linux-default"
  }'

# Start the VM
curl -X POST http://localhost:8000/api/v1/vms/my-first-vm/start

# Check VM status
curl http://localhost:8000/api/v1/vms/my-first-vm
```

#### Using Python SDK

```python
import asyncio
from src.core.vm_manager import VMManager
from src.api.models.vm import VMRequest
from src.utils.config import Config

async def create_first_vm():
    config = Config()
    vm_manager = VMManager(config)
    
    # Create VM
    vm_request = VMRequest(
        name="my-first-vm",
        os_type="linux",
        vcpus=2,
        memory_mb=512,
        template="linux-default"
    )
    
    vm_info = await vm_manager.create_vm(vm_request)
    print(f"Created VM: {vm_info.name}")
    
    # Start VM
    await vm_manager.start_vm("my-first-vm")
    print("VM started successfully")
    
    # Get VM info
    info = await vm_manager.get_vm_info("my-first-vm")
    print(f"VM Status: {info.status}")

# Run the example
asyncio.run(create_first_vm())
```

### 4. Execute Commands in Your VM

Once your VM is running, you can execute commands:

```bash
# Using CLI
python -m src.cli.main vm exec my-first-vm "echo 'Hello from VM'"

# Using API
curl -X POST http://localhost:8000/api/v1/vms/my-first-vm/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "echo '\''Hello from VM'\''"}'
```

### 5. Create a Windows VM

```bash
# Create a Windows VM (requires Windows image)
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-windows-vm",
    "os_type": "windows",
    "vcpus": 4,
    "memory_mb": 2048,
    "template": "windows-default"
  }'

# Start the Windows VM
curl -X POST http://localhost:8000/api/v1/vms/my-windows-vm/start
```

## Common Tasks

### Managing VM Lifecycle

```bash
# List all VMs
curl http://localhost:8000/api/v1/vms

# Stop a VM
curl -X POST http://localhost:8000/api/v1/vms/my-first-vm/stop

# Restart a VM
curl -X POST http://localhost:8000/api/v1/vms/my-first-vm/restart

# Delete a VM
curl -X DELETE http://localhost:8000/api/v1/vms/my-first-vm
```

### File Transfer

```bash
# Upload a file to VM
curl -X POST http://localhost:8000/api/v1/vms/my-first-vm/files/upload \
  -F "file=@/path/to/local/file.txt" \
  -F "path=/tmp/uploaded-file.txt"

# Download a file from VM
curl http://localhost:8000/api/v1/vms/my-first-vm/files/download?path=/tmp/uploaded-file.txt \
  -o downloaded-file.txt
```

### Creating Snapshots

```bash
# Create a snapshot
curl -X POST http://localhost:8000/api/v1/vms/my-first-vm/snapshots \
  -H "Content-Type: application/json" \
  -d '{
    "name": "before-updates",
    "description": "Clean state before applying updates"
  }'

# List snapshots
curl http://localhost:8000/api/v1/vms/my-first-vm/snapshots

# Restore from snapshot
curl -X POST http://localhost:8000/api/v1/vms/my-first-vm/snapshots/before-updates/restore
```

## Configuration

### Basic Configuration

Edit `config/config.yaml` to customize your setup:

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  workers: 4

cloud_hypervisor:
  binary_path: "/usr/local/bin/cloud-hypervisor"
  api_socket_dir: "/tmp/ch-sockets"

networking:
  bridge_name: "chbr0"
  subnet: "192.168.200.0/24"

resources:
  max_vms: 50
  max_memory_per_vm: 8192
  max_vcpus_per_vm: 8

security:
  enable_authentication: true
  vm_isolation: true
```

### VM Templates

Customize VM templates in `config/vm-templates/`:

```yaml
# config/vm-templates/my-custom-linux.yaml
my_custom_linux:
  vcpus: 4
  memory_mb: 1024
  kernel: "images/linux/vmlinux.bin"
  rootfs: "images/linux/rootfs.ext4"
  boot_args: "console=ttyS0 reboot=k panic=1 root=/dev/vda rw"
  guest_agent:
    enabled: true
    port: 8080
```

## Authentication

If authentication is enabled, you'll need to register and login:

```bash
# Register a new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "myuser",
    "password": "SecurePassword123!",
    "role": "user"
  }'

# Login and get token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "myuser",
    "password": "SecurePassword123!"
  }' | jq -r '.access_token')

# Use token in requests
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/vms
```

## Monitoring

### View System Metrics

```bash
# Host system metrics
curl http://localhost:8000/api/v1/system/metrics

# VM-specific metrics
curl http://localhost:8000/api/v1/vms/my-first-vm/metrics
```

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed status
curl http://localhost:8000/status
```

## Troubleshooting

### Common Issues

1. **VM fails to start**: Check that KVM is enabled and you have sufficient resources
2. **Network connectivity issues**: Verify bridge network setup
3. **Permission denied**: Ensure your user is in the `kvm` group

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

### Logs

Check logs for issues:

```bash
# API server logs
tail -f /var/log/microvm-sandbox/api.log

# VM-specific logs
tail -f /var/log/microvm-sandbox/vms/my-first-vm.log
```

## Next Steps

- Read the [VM Management Guide](vm-management.md) for advanced VM operations
- Check out the [API Reference](../api/reference.md) for complete API documentation
- Learn about [Deployment Options](../deployment/) for production setups
- Explore [Security Features](security.md) for enterprise environments

## Getting Help

- Check the [Troubleshooting Guide](troubleshooting.md)
- Review [GitHub Issues](https://github.com/your-org/microvm-sandbox/issues)
- Join our [Community Forum](https://community.microvm-sandbox.org)
- Read the [FAQ](faq.md)