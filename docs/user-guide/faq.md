# Frequently Asked Questions (FAQ)

## General Questions

### What is MicroVM Sandbox?

MicroVM Sandbox is a production-ready virtualization platform that uses Cloud Hypervisor and Python to provide hardware-level isolation through MicroVMs. It supports both Linux and Windows guest operating systems with minimal resource overhead.

### How is this different from Docker or traditional VMs?

- **vs Docker**: Provides true hardware-level isolation (not just process isolation)
- **vs Traditional VMs**: Much lighter weight with faster boot times (<3s for Linux)
- **vs Other Hypervisors**: Modern Rust-based VMM optimized for cloud workloads

### What are the minimum system requirements?

- **CPU**: 4+ cores with VT-x/AMD-V virtualization support
- **Memory**: 8GB+ RAM (32GB recommended for production)
- **Storage**: 50GB+ SSD (200GB recommended)
- **OS**: Ubuntu 20.04+, RHEL 8+, or similar Linux distribution

## Installation and Setup

### Why can't I create VMs? (Permission denied)

This usually means your user isn't in the `kvm` group:

```bash
# Add user to kvm group
sudo usermod -a -G kvm $USER

# Log out and back in, then verify
groups | grep kvm
ls -la /dev/kvm
```

### The setup scripts fail with "command not found"

Make sure you've run the dependency installation first:

```bash
# Run setup scripts in order
sudo ./scripts/setup/install-dependencies.sh
sudo ./scripts/setup/install-cloud-hypervisor.sh
sudo ./scripts/setup/setup-networking.sh
```

### How do I verify my system supports virtualization?

```bash
# Check for virtualization flags
egrep -c '(vmx|svm)' /proc/cpuinfo

# Check KVM module
lsmod | grep kvm

# Verify KVM device
ls -la /dev/kvm
```

## VM Management

### Why do my VMs fail to start?

Common causes and solutions:

1. **No VM images**: Create or download images to `images/` directory
2. **Network issues**: Verify bridge network with `ip link show chbr0`
3. **Resource limits**: Check available memory and CPU
4. **Cloud Hypervisor issues**: Verify with `cloud-hypervisor --version`

### How do I connect to a running VM?

Use the guest agent for command execution:

```bash
# Execute command in VM
curl -X POST http://localhost:8000/api/v1/vms/my-vm/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "ps aux"}'

# Upload file to VM
curl -X POST http://localhost:8000/api/v1/vms/my-vm/files/upload \
  -F "file=@myfile.txt" \
  -F "path=/tmp/myfile.txt"
```

### Can I resize VM resources while running?

Yes, for certain resources:

```bash
# Resize memory (requires VM restart)
curl -X PUT http://localhost:8000/api/v1/vms/my-vm/resources \
  -H "Content-Type: application/json" \
  -d '{"memory_mb": 2048}'

# CPU changes require VM restart
```

### How do I backup my VMs?

Use the snapshot functionality:

```bash
# Create snapshot
curl -X POST http://localhost:8000/api/v1/vms/my-vm/snapshots \
  -H "Content-Type: application/json" \
  -d '{"name": "backup-2025-10-01", "description": "Daily backup"}'

# List snapshots
curl http://localhost:8000/api/v1/vms/my-vm/snapshots
```

## Networking

### My VMs can't access the internet

1. **Check IP forwarding**:
   ```bash
   cat /proc/sys/net/ipv4/ip_forward  # Should be 1
   ```

2. **Verify iptables rules**:
   ```bash
   sudo iptables -t nat -L
   sudo iptables -L FORWARD
   ```

3. **Re-run network setup**:
   ```bash
   sudo ./scripts/setup/setup-networking.sh
   ```

### How do I access services running in VMs?

Use port forwarding:

```bash
# Forward host port 8080 to VM port 80
curl -X POST http://localhost:8000/api/v1/vms/my-vm/network/port-forward \
  -H "Content-Type: application/json" \
  -d '{
    "host_port": 8080,
    "guest_port": 80,
    "protocol": "tcp"
  }'
```

### Can VMs communicate with each other?

By default, VMs can communicate within the bridge network. For isolation:

```yaml
# In config.yaml
security:
  vm_isolation: true
```

## Performance

### My VMs are slow to boot

- **Linux VMs** should boot in <3 seconds
- **Windows VMs** should boot in <10 seconds

If slower:
1. Check host resources (CPU, memory, disk I/O)
2. Verify SSD storage is being used
3. Ensure adequate CPU cores for host and VMs

### How many VMs can I run?

This depends on your hardware and VM resource allocation:

- **Default limit**: 50 VMs per host
- **Memory**: ~128-512MB per Linux VM, 1-2GB per Windows VM
- **CPU**: 1-2 vCPUs per VM typically

Monitor with:
```bash
curl http://localhost:8000/api/v1/system/metrics
```

### Can I optimize performance?

Yes, several options:

1. **CPU isolation** (bare metal):
   ```bash
   # Edit /etc/default/grub
   GRUB_CMDLINE_LINUX_DEFAULT="isolcpus=4,5,6,7"
   ```

2. **NUMA optimization**:
   ```bash
   numactl --cpunodebind=0 --membind=0 ./start-service.sh
   ```

3. **Storage optimization**: Use NVMe SSDs and tune filesystem

## Security

### How do I enable authentication?

Edit `config/config.yaml`:

```yaml
security:
  enable_authentication: true
  jwt_secret_key: "your-secret-key-here"
```

Then create users:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "SecurePassword123!",
    "role": "admin"
  }'
```

### Are VMs isolated from each other?

Yes, through multiple layers:
- **Hardware isolation**: Separate VM memory spaces
- **Network isolation**: Optional separate network namespaces
- **Filesystem isolation**: Separate disk images
- **Process isolation**: Separate kernel instances

### How do I monitor security events?

Enable audit logging:

```yaml
security:
  audit_logging:
    enabled: true
    retention_days: 365
```

View logs:
```bash
curl http://localhost:8000/api/v1/security/audit-logs
```

## Deployment

### Can I run this in production?

Yes! The system includes:
- **High availability** configurations
- **Monitoring** with Prometheus/Grafana
- **Security hardening** options
- **Compliance** features (SOC 2, HIPAA, etc.)

### What deployment options are available?

1. **Docker**: Single container or multi-service with docker-compose
2. **Kubernetes**: Full manifests with auto-scaling
3. **Bare metal**: Direct installation with systemd services

See [deployment guides](../deployment/) for details.

### How do I scale horizontally?

For Kubernetes:
```bash
kubectl scale deployment microvm-sandbox --replicas=5
```

For Docker Swarm:
```bash
docker service scale microvm-sandbox=5
```

### Can I use external databases?

Yes, configure PostgreSQL:

```yaml
database:
  url: "postgresql://user:pass@localhost:5432/microvm_sandbox"
```

## Troubleshooting

### Where are the log files?

- **API logs**: `/var/log/microvm-sandbox/api.log`
- **Cloud Hypervisor logs**: `/var/log/microvm-sandbox/cloud-hypervisor.log`
- **VM logs**: `/var/log/microvm-sandbox/vms/{vm-name}.log`

### How do I debug VM issues?

1. **Check VM status**:
   ```bash
   curl http://localhost:8000/api/v1/vms/my-vm
   ```

2. **View VM logs**:
   ```bash
   curl http://localhost:8000/api/v1/vms/my-vm/logs
   ```

3. **Check host resources**:
   ```bash
   curl http://localhost:8000/api/v1/system/metrics
   ```

### The API is not responding

1. **Check service status**:
   ```bash
   sudo systemctl status microvm-sandbox
   ```

2. **View service logs**:
   ```bash
   sudo journalctl -u microvm-sandbox -f
   ```

3. **Verify configuration**:
   ```bash
   python -m src.utils.config validate
   ```

### How do I recover from failures?

1. **Service recovery**:
   ```bash
   sudo systemctl restart microvm-sandbox
   ```

2. **Database recovery**:
   ```bash
   # Backup current state
   cp /var/lib/microvm-sandbox/db.sqlite backup.db
   
   # Reset if needed
   python -m src.utils.database init
   ```

3. **Network recovery**:
   ```bash
   sudo ./scripts/setup/setup-networking.sh
   ```

## Advanced Topics

### Can I use custom VM images?

Yes, place your images in:
- **Linux**: `images/linux/vmlinux.bin` and `images/linux/rootfs.ext4`
- **Windows**: `images/windows/OVMF.fd`, `images/windows/windows.qcow2`

### How do I create custom templates?

Create YAML files in `config/vm-templates/`:

```yaml
my_custom_template:
  vcpus: 4
  memory_mb: 2048
  kernel: "images/linux/vmlinux.bin"
  rootfs: "images/linux/my-rootfs.ext4"
  boot_args: "console=ttyS0 reboot=k panic=1"
```

### Can I integrate with CI/CD?

Yes, use the REST API or Python SDK:

```python
import asyncio
from microvm_client import MicroVMClient

async def test_workflow():
    client = MicroVMClient("http://localhost:8000")
    
    # Create test VM
    vm = await client.create_vm("test-vm", template="linux-default")
    await client.start_vm("test-vm")
    
    # Run tests
    result = await client.execute_command("test-vm", "pytest /app/tests")
    
    # Cleanup
    await client.delete_vm("test-vm")
    
    return result.exit_code == 0
```

### How do I monitor performance?

Access monitoring endpoints:
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000`
- **Health check**: `http://localhost:8000/health`
- **Metrics API**: `http://localhost:8000/api/v1/system/metrics`

## Getting More Help

### Documentation
- **[Quick Start Guide](quickstart.md)** - Basic setup and usage
- **[VM Management](vm-management.md)** - Detailed VM operations
- **[API Reference](../api/reference.md)** - Complete API documentation
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions

### Community
- **GitHub Issues**: Report bugs and request features
- **GitHub Discussions**: Ask questions and share experiences
- **Documentation**: Complete guides and references

### Support
When asking for help, please provide:
1. **System information**: OS, hardware, versions
2. **Configuration**: Relevant config files (redact secrets)
3. **Logs**: Error messages and debug output
4. **Steps to reproduce**: Clear reproduction steps
5. **Expected vs actual behavior**: What should happen vs what does happen