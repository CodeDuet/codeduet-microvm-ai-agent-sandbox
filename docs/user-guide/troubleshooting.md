# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the MicroVM Sandbox.

## Quick Diagnostics

### Health Check

Start with a comprehensive health check:

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed system status
curl http://localhost:8000/status

# Component-specific checks
curl http://localhost:8000/api/v1/system/diagnostics
```

### Log Analysis

```bash
# API server logs
tail -f /var/log/microvm-sandbox/api.log

# Cloud Hypervisor logs
tail -f /var/log/microvm-sandbox/cloud-hypervisor.log

# VM-specific logs
tail -f /var/log/microvm-sandbox/vms/{vm-name}.log
```

## Common Issues

### 1. VM Creation Failures

#### Problem: VM creation fails immediately

**Symptoms:**
- HTTP 400/422 responses when creating VMs
- "Insufficient resources" errors
- "Invalid configuration" errors

**Diagnosis:**
```bash
# Check system resources
curl http://localhost:8000/api/v1/system/metrics

# Validate VM configuration
curl -X POST http://localhost:8000/api/v1/vms/validate \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-vm",
    "os_type": "linux",
    "vcpus": 2,
    "memory_mb": 512
  }'
```

**Solutions:**

1. **Insufficient memory:**
```bash
# Check available memory
free -h

# Reduce VM memory allocation or increase host memory
# Modify config/config.yaml:
resources:
  max_memory_per_vm: 2048  # Reduce if needed
```

2. **Invalid template:**
```bash
# List available templates
ls config/vm-templates/

# Use valid template name
curl -X POST http://localhost:8000/api/v1/vms \
  -d '{"name": "test", "template": "linux-default"}'
```

3. **Network configuration issues:**
```bash
# Check bridge network
ip link show chbr0

# Recreate bridge if needed
sudo ./scripts/setup/setup-networking.sh
```

### 2. VM Startup Issues

#### Problem: VM created but won't start

**Symptoms:**
- VM status remains "created" or becomes "failed"
- Timeout errors during startup
- Cloud Hypervisor process exits

**Diagnosis:**
```bash
# Check VM status and logs
curl http://localhost:8000/api/v1/vms/{vm-name}
curl http://localhost:8000/api/v1/vms/{vm-name}/logs

# Check Cloud Hypervisor process
ps aux | grep cloud-hypervisor
```

**Solutions:**

1. **KVM not available:**
```bash
# Check KVM support
lsmod | grep kvm
ls -la /dev/kvm

# Enable KVM if needed
sudo modprobe kvm
sudo modprobe kvm_intel  # or kvm_amd

# Add user to kvm group
sudo usermod -a -G kvm $USER
```

2. **Missing VM images:**
```bash
# Check image files exist
ls -la images/linux/
ls -la images/windows/

# Download/create missing images
./scripts/setup/download-images.sh
```

3. **Port conflicts:**
```bash
# Check for port conflicts
netstat -tlnp | grep :8000

# Use different port or kill conflicting process
sudo lsof -i :8000
```

### 3. Guest Agent Connection Issues

#### Problem: Cannot execute commands in VM

**Symptoms:**
- "Guest agent not responding" errors
- Command execution timeouts
- File transfer failures

**Diagnosis:**
```bash
# Check guest agent status
curl http://localhost:8000/api/v1/vms/{vm-name}/agent/status

# Test basic connectivity
curl -X POST http://localhost:8000/api/v1/vms/{vm-name}/execute \
  -d '{"command": "echo test"}'
```

**Solutions:**

1. **Guest agent not running:**
```bash
# Check if VM is fully booted
curl http://localhost:8000/api/v1/vms/{vm-name}/metrics

# Wait for boot to complete (Linux ~10s, Windows ~60s)
sleep 30

# For Linux VMs, check agent service
curl -X POST http://localhost:8000/api/v1/vms/{vm-name}/execute \
  -d '{"command": "systemctl status guest-agent"}'
```

2. **Network connectivity issues:**
```bash
# Test VM network connectivity
curl -X POST http://localhost:8000/api/v1/vms/{vm-name}/execute \
  -d '{"command": "ping -c 1 192.168.200.1"}'

# Check firewall rules
curl -X POST http://localhost:8000/api/v1/vms/{vm-name}/execute \
  -d '{"command": "iptables -L"}'
```

3. **Guest agent configuration:**
```bash
# Check agent configuration in VM
curl -X POST http://localhost:8000/api/v1/vms/{vm-name}/execute \
  -d '{"command": "cat /etc/guest-agent/config.yaml"}'

# Restart guest agent
curl -X POST http://localhost:8000/api/v1/vms/{vm-name}/execute \
  -d '{"command": "systemctl restart guest-agent"}'
```

### 4. Network Connectivity Problems

#### Problem: VM has no network access

**Symptoms:**
- VM cannot reach external hosts
- Port forwarding not working
- DNS resolution failures

**Diagnosis:**
```bash
# Check VM network configuration
curl http://localhost:8000/api/v1/vms/{vm-name}/network

# Test connectivity from VM
curl -X POST http://localhost:8000/api/v1/vms/{vm-name}/execute \
  -d '{"command": "ip addr show"}'

curl -X POST http://localhost:8000/api/v1/vms/{vm-name}/execute \
  -d '{"command": "ping -c 1 8.8.8.8"}'
```

**Solutions:**

1. **Bridge network issues:**
```bash
# Check bridge status
ip link show chbr0
brctl show chbr0

# Recreate bridge network
sudo ip link delete chbr0
sudo ./scripts/setup/setup-networking.sh
```

2. **IP forwarding disabled:**
```bash
# Check IP forwarding
cat /proc/sys/net/ipv4/ip_forward

# Enable IP forwarding
echo 1 | sudo tee /proc/sys/net/ipv4/ip_forward

# Make permanent
echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf
```

3. **Firewall blocking traffic:**
```bash
# Check iptables rules
sudo iptables -L
sudo iptables -t nat -L

# Allow VM traffic
sudo iptables -A FORWARD -i chbr0 -j ACCEPT
sudo iptables -A FORWARD -o chbr0 -j ACCEPT
sudo iptables -t nat -A POSTROUTING -s 192.168.200.0/24 -j MASQUERADE
```

### 5. Performance Issues

#### Problem: Poor VM performance

**Symptoms:**
- Slow VM response times
- High host CPU/memory usage
- API timeouts

**Diagnosis:**
```bash
# Check system resources
curl http://localhost:8000/api/v1/system/metrics

# Check VM-specific metrics
curl http://localhost:8000/api/v1/vms/{vm-name}/metrics

# Monitor host performance
top
iostat 1
```

**Solutions:**

1. **Resource overallocation:**
```bash
# Check total allocated resources
curl http://localhost:8000/api/v1/system/resources/summary

# Reduce VM allocations
curl -X PUT http://localhost:8000/api/v1/vms/{vm-name}/resources \
  -d '{"vcpus": 1, "memory_mb": 256}'
```

2. **Disk I/O bottlenecks:**
```bash
# Check disk usage
df -h
iostat -x 1

# Use faster storage or reduce disk I/O
mount -o remount,noatime /
```

3. **Memory pressure:**
```bash
# Check memory usage
free -h
cat /proc/meminfo

# Enable swap if needed
sudo swapon -a

# Reduce number of running VMs
curl -X POST http://localhost:8000/api/v1/vms/{vm-name}/stop
```

### 6. Snapshot and Restore Issues

#### Problem: Snapshot creation/restoration fails

**Symptoms:**
- Snapshot operations hang or fail
- Restored VMs don't boot
- Snapshot file corruption

**Diagnosis:**
```bash
# Check snapshot status
curl http://localhost:8000/api/v1/vms/{vm-name}/snapshots

# Verify snapshot files
ls -la /var/lib/microvm-sandbox/snapshots/

# Check file integrity
sha256sum /var/lib/microvm-sandbox/snapshots/{snapshot-file}
```

**Solutions:**

1. **Insufficient disk space:**
```bash
# Check available space
df -h /var/lib/microvm-sandbox/

# Clean up old snapshots
curl -X DELETE http://localhost:8000/api/v1/vms/{vm-name}/snapshots/{old-snapshot}

# Configure snapshot retention
# In config/config.yaml:
snapshots:
  max_per_vm: 5
  cleanup_interval_hours: 24
```

2. **VM running during snapshot:**
```bash
# Stop VM before snapshot
curl -X POST http://localhost:8000/api/v1/vms/{vm-name}/stop

# Create snapshot
curl -X POST http://localhost:8000/api/v1/vms/{vm-name}/snapshots \
  -d '{"name": "stopped-state"}'
```

3. **Corrupted snapshot files:**
```bash
# Verify snapshot integrity
curl http://localhost:8000/api/v1/vms/{vm-name}/snapshots/{snapshot}/verify

# Remove corrupted snapshots
curl -X DELETE http://localhost:8000/api/v1/vms/{vm-name}/snapshots/{corrupted-snapshot}
```

### 7. Authentication and Authorization Issues

#### Problem: API authentication failures

**Symptoms:**
- 401 Unauthorized responses
- 403 Forbidden errors
- Token validation failures

**Diagnosis:**
```bash
# Check authentication configuration
grep -A 5 "security:" config/config.yaml

# Test authentication endpoint
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d '{"username": "test", "password": "test"}'

# Validate token
curl -H "Authorization: Bearer {token}" \
  http://localhost:8000/api/v1/auth/validate
```

**Solutions:**

1. **Invalid credentials:**
```bash
# Reset user password
curl -X PUT http://localhost:8000/api/v1/auth/users/{username}/password \
  -d '{"new_password": "NewSecurePass123!"}'

# Create new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -d '{"username": "newuser", "password": "SecurePass123!", "role": "user"}'
```

2. **Expired tokens:**
```bash
# Get new token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -d '{"username": "user", "password": "pass"}' | jq -r '.access_token')

# Use fresh token
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/vms
```

3. **Insufficient permissions:**
```bash
# Check user role
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/auth/user

# Update user role (admin only)
curl -X PUT http://localhost:8000/api/v1/auth/users/{username}/role \
  -d '{"role": "admin"}'
```

## Advanced Diagnostics

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Set debug environment
export LOG_LEVEL=DEBUG
export DEBUG_MODE=true

# Restart API server
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload
```

### System Information Collection

```bash
#!/bin/bash
# collect-debug-info.sh

echo "=== System Information ===" > debug-info.txt
uname -a >> debug-info.txt
lsb_release -a >> debug-info.txt

echo -e "\n=== KVM Support ===" >> debug-info.txt
lsmod | grep kvm >> debug-info.txt
ls -la /dev/kvm >> debug-info.txt

echo -e "\n=== Memory Info ===" >> debug-info.txt
free -h >> debug-info.txt

echo -e "\n=== Disk Usage ===" >> debug-info.txt
df -h >> debug-info.txt

echo -e "\n=== Network Configuration ===" >> debug-info.txt
ip addr show >> debug-info.txt
brctl show >> debug-info.txt

echo -e "\n=== Running Processes ===" >> debug-info.txt
ps aux | grep -E "(cloud-hypervisor|microvm)" >> debug-info.txt

echo -e "\n=== API Status ===" >> debug-info.txt
curl -s http://localhost:8000/health >> debug-info.txt

echo -e "\n=== VM List ===" >> debug-info.txt
curl -s http://localhost:8000/api/v1/vms >> debug-info.txt

echo "Debug information collected in debug-info.txt"
```

### Log Analysis Tools

```bash
# Search for errors in logs
grep -i error /var/log/microvm-sandbox/*.log

# Find timeout issues
grep -i timeout /var/log/microvm-sandbox/*.log

# Check for memory issues
grep -i "out of memory\|oom" /var/log/microvm-sandbox/*.log

# Monitor real-time logs
tail -f /var/log/microvm-sandbox/*.log | grep -i error
```

### Performance Profiling

```bash
# CPU profiling
perf top -p $(pgrep cloud-hypervisor)

# Memory profiling
valgrind --tool=massif cloud-hypervisor ...

# I/O profiling
iotop -p $(pgrep cloud-hypervisor)

# Network profiling
ss -tuln | grep :8000
netstat -i
```

## Recovery Procedures

### Emergency VM Stop

```bash
# Force stop all VMs
curl -X POST http://localhost:8000/api/v1/system/emergency-stop

# Or manually kill processes
sudo pkill -f cloud-hypervisor
```

### Service Recovery

```bash
# Restart API service
sudo systemctl restart microvm-sandbox

# Clear temporary files
sudo rm -rf /tmp/ch-sockets/*
sudo rm -rf /tmp/microvm-*

# Reset networking
sudo ./scripts/setup/setup-networking.sh
```

### Database Recovery

```bash
# Backup current state
cp /var/lib/microvm-sandbox/db.sqlite /var/lib/microvm-sandbox/db.sqlite.backup

# Reset database (loses VM metadata)
rm /var/lib/microvm-sandbox/db.sqlite
python -m src.utils.database init

# Restore from backup
cp /var/lib/microvm-sandbox/db.sqlite.backup /var/lib/microvm-sandbox/db.sqlite
```

## Prevention Strategies

### Monitoring Setup

```bash
# Install monitoring tools
pip install prometheus-client psutil

# Configure alerts
curl -X POST http://localhost:8000/api/v1/system/alerts \
  -d '{
    "name": "high-memory-usage",
    "condition": "memory_usage_percent > 90",
    "action": "email",
    "recipients": ["admin@example.com"]
  }'
```

### Regular Maintenance

```bash
#!/bin/bash
# maintenance.sh - Run weekly

# Clean up old logs
find /var/log/microvm-sandbox/ -name "*.log" -mtime +7 -delete

# Clean up old snapshots
curl -X POST http://localhost:8000/api/v1/system/cleanup/snapshots

# Update system
apt update && apt upgrade -y

# Restart services
systemctl restart microvm-sandbox
```

### Configuration Validation

```bash
# Validate configuration before deployment
python -m src.utils.config validate

# Test API endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/vms

# Verify templates
python -m src.utils.templates validate
```

## Getting Help

### Community Resources

- **Documentation**: [https://docs.microvm-sandbox.org](https://docs.microvm-sandbox.org)
- **GitHub Issues**: [https://github.com/your-org/microvm-sandbox/issues](https://github.com/your-org/microvm-sandbox/issues)
- **Community Forum**: [https://community.microvm-sandbox.org](https://community.microvm-sandbox.org)
- **Discord**: [https://discord.gg/microvm-sandbox](https://discord.gg/microvm-sandbox)

### Support Levels

1. **Community Support**: Free support through GitHub issues and forums
2. **Professional Support**: Paid support with SLA guarantees
3. **Enterprise Support**: 24/7 support with dedicated engineer

### Bug Reports

When reporting bugs, include:

1. **System information**: OS, version, hardware specs
2. **Configuration**: Relevant config files (redact sensitive data)
3. **Logs**: Relevant log excerpts
4. **Steps to reproduce**: Detailed reproduction steps
5. **Expected vs actual behavior**: Clear description of the issue

### Feature Requests

Submit feature requests with:

1. **Use case**: Why you need the feature
2. **Proposed solution**: How you think it should work
3. **Alternatives**: Other approaches you've considered
4. **Impact**: How it would benefit other users