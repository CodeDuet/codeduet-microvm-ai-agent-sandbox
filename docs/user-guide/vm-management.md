# VM Management Guide

This comprehensive guide covers all aspects of virtual machine management in the MicroVM Sandbox.

## VM Lifecycle Management

### Creating VMs

#### Basic VM Creation

```bash
# Create a minimal Linux VM
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Content-Type: application/json" \
  -d '{
    "name": "web-server",
    "os_type": "linux",
    "vcpus": 2,
    "memory_mb": 512,
    "template": "linux-default"
  }'
```

#### Advanced VM Configuration

```bash
# Create a VM with custom networking and storage
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Content-Type: application/json" \
  -d '{
    "name": "database-server",
    "os_type": "linux",
    "vcpus": 4,
    "memory_mb": 2048,
    "template": "linux-default",
    "network_config": {
      "bridge": "chbr0",
      "ip": "192.168.200.50"
    },
    "storage_config": {
      "disk_size_gb": 20,
      "disk_type": "ssd"
    },
    "cpu_limit_percent": 80,
    "memory_limit_percent": 90
  }'
```

#### Using VM Templates

VM templates provide predefined configurations for common use cases:

```yaml
# config/vm-templates/web-server.yaml
web_server:
  vcpus: 2
  memory_mb: 1024
  kernel: "images/linux/vmlinux.bin"
  rootfs: "images/linux/web-server-rootfs.ext4"
  boot_args: "console=ttyS0 reboot=k panic=1 root=/dev/vda rw"
  network_config:
    bridge: "chbr0"
  guest_agent:
    enabled: true
    port: 8080
  packages:
    - nginx
    - nodejs
    - npm
```

Use the template:

```bash
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-web-server",
    "template": "web-server"
  }'
```

### Starting and Stopping VMs

#### Starting VMs

```bash
# Start a VM
curl -X POST http://localhost:8000/api/v1/vms/web-server/start

# Check boot progress
curl http://localhost:8000/api/v1/vms/web-server | jq '.status'
```

#### Graceful Shutdown

```bash
# Graceful shutdown (gives VM 30 seconds to shut down)
curl -X POST http://localhost:8000/api/v1/vms/web-server/stop \
  -H "Content-Type: application/json" \
  -d '{
    "force": false,
    "timeout_seconds": 30
  }'
```

#### Force Shutdown

```bash
# Force immediate shutdown
curl -X POST http://localhost:8000/api/v1/vms/web-server/stop \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

#### Restarting VMs

```bash
# Restart a VM
curl -X POST http://localhost:8000/api/v1/vms/web-server/restart
```

### VM Status and Information

#### Getting VM Information

```bash
# Get detailed VM information
curl http://localhost:8000/api/v1/vms/web-server
```

Response includes:
- Current status (created, running, stopped)
- Resource allocation and usage
- Network configuration
- Uptime and performance metrics
- Guest agent status

#### Listing VMs

```bash
# List all VMs
curl http://localhost:8000/api/v1/vms

# Filter by status
curl "http://localhost:8000/api/v1/vms?status=running"

# Filter by OS type
curl "http://localhost:8000/api/v1/vms?os_type=linux"

# Pagination
curl "http://localhost:8000/api/v1/vms?limit=10&offset=20"
```

## Command Execution

### Running Commands

#### Basic Command Execution

```bash
# Execute a simple command
curl -X POST http://localhost:8000/api/v1/vms/web-server/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "uname -a"}'
```

#### Commands with Environment Variables

```bash
# Execute with custom environment
curl -X POST http://localhost:8000/api/v1/vms/web-server/execute \
  -H "Content-Type: application/json" \
  -d '{
    "command": "echo $MY_VAR",
    "environment": {
      "MY_VAR": "Hello from host",
      "PATH": "/usr/local/bin:/usr/bin:/bin"
    }
  }'
```

#### Long-Running Commands

```bash
# Execute with custom timeout
curl -X POST http://localhost:8000/api/v1/vms/web-server/execute \
  -H "Content-Type: application/json" \
  -d '{
    "command": "sleep 60 && echo done",
    "timeout_seconds": 120
  }'
```

#### Working Directory

```bash
# Execute in specific directory
curl -X POST http://localhost:8000/api/v1/vms/web-server/execute \
  -H "Content-Type: application/json" \
  -d '{
    "command": "ls -la",
    "working_directory": "/var/log"
  }'
```

### Interactive Sessions

For interactive workflows, use the WebSocket API:

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/vms/web-server/shell');

ws.onopen = function() {
    ws.send(JSON.stringify({
        type: 'command',
        data: 'bash'
    }));
};

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    console.log('Output:', message.data);
};

// Send commands
ws.send(JSON.stringify({
    type: 'input',
    data: 'ls -la\n'
}));
```

## File Transfer

### Uploading Files

#### Single File Upload

```bash
# Upload a configuration file
curl -X POST http://localhost:8000/api/v1/vms/web-server/files/upload \
  -F "file=@nginx.conf" \
  -F "path=/etc/nginx/nginx.conf" \
  -F "permissions=644"
```

#### Multiple Files

```bash
# Upload multiple files
for file in config/*.conf; do
  curl -X POST http://localhost:8000/api/v1/vms/web-server/files/upload \
    -F "file=@$file" \
    -F "path=/etc/app/$(basename $file)"
done
```

#### Large File Upload with Progress

```bash
# Upload with progress bar
curl -X POST http://localhost:8000/api/v1/vms/web-server/files/upload \
  -F "file=@large-dataset.tar.gz" \
  -F "path=/tmp/dataset.tar.gz" \
  --progress-bar -o upload-progress.txt
```

### Downloading Files

#### Single File Download

```bash
# Download a log file
curl "http://localhost:8000/api/v1/vms/web-server/files/download?path=/var/log/nginx/access.log" \
  -o access.log
```

#### Directory Listing

```bash
# List files in a directory
curl "http://localhost:8000/api/v1/vms/web-server/files?path=/var/log&recursive=true"
```

### Bulk Operations

#### Archive and Download

```bash
# Create and download archive of directory
curl -X POST http://localhost:8000/api/v1/vms/web-server/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "tar -czf /tmp/logs.tar.gz /var/log"}'

curl "http://localhost:8000/api/v1/vms/web-server/files/download?path=/tmp/logs.tar.gz" \
  -o logs.tar.gz
```

#### Upload and Extract

```bash
# Upload and extract archive
curl -X POST http://localhost:8000/api/v1/vms/web-server/files/upload \
  -F "file=@application.tar.gz" \
  -F "path=/tmp/app.tar.gz"

curl -X POST http://localhost:8000/api/v1/vms/web-server/execute \
  -H "Content-Type: application/json" \
  -d '{
    "command": "cd /opt && tar -xzf /tmp/app.tar.gz",
    "working_directory": "/opt"
  }'
```

## Resource Management

### Monitoring Resource Usage

#### Real-time Metrics

```bash
# Get current resource usage
curl http://localhost:8000/api/v1/vms/web-server/metrics
```

#### Historical Metrics

```bash
# Get metrics over time period
curl "http://localhost:8000/api/v1/vms/web-server/metrics/history?start=2025-10-01T00:00:00Z&end=2025-10-01T23:59:59Z"
```

### Resource Allocation

#### Updating Resources

```bash
# Scale up VM resources
curl -X PUT http://localhost:8000/api/v1/vms/web-server/resources \
  -H "Content-Type: application/json" \
  -d '{
    "vcpus": 4,
    "memory_mb": 2048,
    "cpu_limit_percent": 80,
    "memory_limit_percent": 90
  }'
```

#### Resource Limits

```bash
# Set resource limits
curl -X PUT http://localhost:8000/api/v1/vms/web-server/limits \
  -H "Content-Type: application/json" \
  -d '{
    "cpu_quota_percent": 75,
    "memory_limit_mb": 1024,
    "disk_limit_gb": 10,
    "network_bandwidth_mbps": 100
  }'
```

### Auto-scaling

#### Enable Auto-scaling

```bash
# Configure auto-scaling rules
curl -X POST http://localhost:8000/api/v1/vms/web-server/autoscale \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "cpu_threshold": 80,
    "memory_threshold": 85,
    "scale_up_action": {
      "vcpus_delta": 1,
      "memory_mb_delta": 512
    },
    "scale_down_action": {
      "vcpus_delta": -1,
      "memory_mb_delta": -512
    },
    "cooldown_seconds": 300
  }'
```

## Snapshot Management

### Creating Snapshots

#### Basic Snapshot

```bash
# Create a snapshot
curl -X POST http://localhost:8000/api/v1/vms/web-server/snapshots \
  -H "Content-Type: application/json" \
  -d '{
    "name": "before-update",
    "description": "Clean state before applying security updates"
  }'
```

#### Memory-inclusive Snapshot

```bash
# Include VM memory state in snapshot
curl -X POST http://localhost:8000/api/v1/vms/web-server/snapshots \
  -H "Content-Type: application/json" \
  -d '{
    "name": "running-state",
    "description": "Snapshot with running state",
    "include_memory": true
  }'
```

### Managing Snapshots

#### Listing Snapshots

```bash
# List all snapshots for a VM
curl http://localhost:8000/api/v1/vms/web-server/snapshots
```

#### Snapshot Information

```bash
# Get detailed snapshot info
curl http://localhost:8000/api/v1/vms/web-server/snapshots/before-update
```

### Restoring from Snapshots

#### Basic Restore

```bash
# Stop VM first
curl -X POST http://localhost:8000/api/v1/vms/web-server/stop

# Restore from snapshot
curl -X POST http://localhost:8000/api/v1/vms/web-server/snapshots/before-update/restore

# Start VM
curl -X POST http://localhost:8000/api/v1/vms/web-server/start
```

#### Clone from Snapshot

```bash
# Create new VM from snapshot
curl -X POST http://localhost:8000/api/v1/vms/web-server/snapshots/before-update/clone \
  -H "Content-Type: application/json" \
  -d '{
    "new_vm_name": "web-server-clone",
    "vcpus": 2,
    "memory_mb": 1024
  }'
```

## Network Configuration

### Basic Networking

#### View Network Configuration

```bash
# Get VM network info
curl http://localhost:8000/api/v1/vms/web-server/network
```

#### Update Network Settings

```bash
# Change VM IP address
curl -X PUT http://localhost:8000/api/v1/vms/web-server/network \
  -H "Content-Type: application/json" \
  -d '{
    "ip_address": "192.168.200.100",
    "netmask": "255.255.255.0",
    "gateway": "192.168.200.1"
  }'
```

### Port Forwarding

#### Configure Port Forwarding

```bash
# Forward host port 8080 to VM port 80
curl -X POST http://localhost:8000/api/v1/vms/web-server/network/port-forward \
  -H "Content-Type: application/json" \
  -d '{
    "host_port": 8080,
    "guest_port": 80,
    "protocol": "tcp",
    "description": "Web server access"
  }'
```

#### List Port Forwards

```bash
# List active port forwards
curl http://localhost:8000/api/v1/vms/web-server/network/port-forwards
```

#### Remove Port Forward

```bash
# Remove port forward
curl -X DELETE http://localhost:8000/api/v1/vms/web-server/network/port-forward/8080
```

### Network Isolation

#### Create Isolated Network

```bash
# Create private network for VM group
curl -X POST http://localhost:8000/api/v1/networks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "private-net",
    "subnet": "10.0.1.0/24",
    "isolated": true,
    "dhcp_enabled": true
  }'
```

#### Assign VM to Network

```bash
# Move VM to private network
curl -X PUT http://localhost:8000/api/v1/vms/web-server/network \
  -H "Content-Type: application/json" \
  -d '{
    "network": "private-net",
    "ip_address": "10.0.1.10"
  }'
```

## Windows VM Management

### Windows-Specific Operations

#### Creating Windows VMs

```bash
# Create Windows VM with UEFI boot
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Content-Type: application/json" \
  -d '{
    "name": "windows-server",
    "os_type": "windows",
    "vcpus": 4,
    "memory_mb": 4096,
    "template": "windows-server-2022",
    "boot_type": "uefi"
  }'
```

#### PowerShell Commands

```bash
# Execute PowerShell command
curl -X POST http://localhost:8000/api/v1/vms/windows-server/execute \
  -H "Content-Type: application/json" \
  -d '{
    "command": "Get-Process | Where-Object CPU -gt 10",
    "shell": "powershell"
  }'
```

#### Windows Features

```bash
# Install Windows feature
curl -X POST http://localhost:8000/api/v1/vms/windows-server/execute \
  -H "Content-Type: application/json" \
  -d '{
    "command": "Install-WindowsFeature -Name IIS-WebServerRole -IncludeManagementTools",
    "shell": "powershell"
  }'
```

## Automation and Scripting

### VM Provisioning Scripts

#### Cloud-Init for Linux

```yaml
# cloud-init.yaml
#cloud-config
users:
  - name: admin
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - ssh-rsa AAAAB3...

packages:
  - nginx
  - docker.io
  - git

runcmd:
  - systemctl enable nginx
  - systemctl start nginx
  - usermod -aG docker admin
```

```bash
# Create VM with cloud-init
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Content-Type: application/json" \
  -d '{
    "name": "auto-provisioned",
    "os_type": "linux",
    "vcpus": 2,
    "memory_mb": 1024,
    "template": "linux-default",
    "cloud_init": "'$(cat cloud-init.yaml | base64 -w 0)'"
  }'
```

### Batch Operations

#### Multiple VM Creation

```bash
#!/bin/bash
# create-vm-cluster.sh

VMS=("web-1" "web-2" "web-3" "db-1")

for vm in "${VMS[@]}"; do
  curl -X POST http://localhost:8000/api/v1/vms \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"$vm\",
      \"os_type\": \"linux\",
      \"vcpus\": 2,
      \"memory_mb\": 1024,
      \"template\": \"web-server\"
    }"
  
  curl -X POST http://localhost:8000/api/v1/vms/$vm/start
done
```

#### Parallel Operations

```bash
#!/bin/bash
# parallel-updates.sh

VMS=("web-1" "web-2" "web-3")

# Update all VMs in parallel
for vm in "${VMS[@]}"; do
  {
    curl -X POST http://localhost:8000/api/v1/vms/$vm/execute \
      -H "Content-Type: application/json" \
      -d '{"command": "apt update && apt upgrade -y"}'
  } &
done

wait  # Wait for all background jobs to complete
echo "All VMs updated"
```

## Monitoring and Alerting

### Performance Monitoring

#### Set up Monitoring

```bash
# Enable detailed monitoring
curl -X PUT http://localhost:8000/api/v1/vms/web-server/monitoring \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "interval_seconds": 10,
    "metrics": [
      "cpu_usage",
      "memory_usage",
      "disk_io",
      "network_io",
      "process_count"
    ]
  }'
```

#### Custom Alerts

```bash
# Configure alerts
curl -X POST http://localhost:8000/api/v1/vms/web-server/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "high-cpu-usage",
    "condition": "cpu_usage_percent > 80",
    "duration_seconds": 300,
    "action": "email",
    "recipients": ["admin@example.com"]
  }'
```

## Best Practices

### Resource Planning

1. **Right-sizing VMs**: Start with minimal resources and scale up based on monitoring
2. **Memory allocation**: Leave 20% buffer for host system
3. **CPU allocation**: Don't over-allocate vCPUs beyond physical cores
4. **Storage**: Use SSD storage for database VMs

### Security

1. **Network isolation**: Use separate networks for different VM groups
2. **Regular snapshots**: Create snapshots before major changes
3. **Access control**: Use authentication and RBAC
4. **Updates**: Keep VM images and host system updated

### Performance

1. **Batch operations**: Use parallel operations for multiple VMs
2. **Resource monitoring**: Set up alerts for resource exhaustion
3. **Snapshot management**: Clean up old snapshots regularly
4. **Network optimization**: Use appropriate network configurations

### Backup and Recovery

1. **Snapshot strategy**: Regular automated snapshots
2. **External backups**: Export important snapshots
3. **Recovery testing**: Regularly test snapshot restoration
4. **Documentation**: Document recovery procedures

## Troubleshooting

### Common Issues

#### VM Won't Start

```bash
# Check VM configuration
curl http://localhost:8000/api/v1/vms/web-server

# Check host resources
curl http://localhost:8000/api/v1/system/metrics

# Check logs
curl http://localhost:8000/api/v1/vms/web-server/logs
```

#### Guest Agent Issues

```bash
# Check guest agent status
curl http://localhost:8000/api/v1/vms/web-server/agent/status

# Restart guest agent
curl -X POST http://localhost:8000/api/v1/vms/web-server/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "systemctl restart guest-agent"}'
```

#### Network Connectivity

```bash
# Test network connectivity
curl -X POST http://localhost:8000/api/v1/vms/web-server/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "ping -c 4 8.8.8.8"}'

# Check network configuration
curl http://localhost:8000/api/v1/vms/web-server/network
```

### Debug Information

```bash
# Get comprehensive debug info
curl http://localhost:8000/api/v1/vms/web-server/debug

# Export VM configuration
curl http://localhost:8000/api/v1/vms/web-server/export > vm-config.json
```