# VNC/GUI Access Guide

This guide covers how to use VNC for graphical desktop access to MicroVMs, enabling visual AI agents and desktop automation.

## Overview

The MicroVM Sandbox supports VNC (Virtual Network Computing) for remote desktop access to both Linux and Windows VMs with graphical environments. This enables:

- Visual AI agents that can interact with desktop applications
- Browser automation and web testing
- Desktop application testing and automation
- Remote development environments with IDEs
- Computer vision and OCR tasks

## VNC Templates

### Available Templates with GUI Support

#### Linux Templates (Guest VNC)
1. **ai-agent** - Development environment with VS Code, browsers, and Python
2. **computer-use** - Full desktop with GNOME, office suite, and development tools  
3. **web-automation** - Optimized for web browser automation and testing

#### Windows Templates (Hypervisor VNC)
1. **windows-desktop** - Full Windows desktop with development tools and browsers
2. **windows-default** - Basic Windows environment with VNC support

## VNC Implementation Types

### Linux VMs - Guest VNC
- VNC server runs inside the Linux VM
- Provides access to the full desktop environment (GNOME/XFCE)
- Uses x11vnc or similar VNC servers
- Supports desktop automation tools (xdotool, pyautogui)

### Windows VMs - Hypervisor VNC  
- VNC console provided by Cloud Hypervisor itself
- Direct access to Windows desktop through virtualization layer
- No additional software needed inside Windows
- Uses Cloud Hypervisor's built-in VNC console

## Starting a VM with VNC

### Using the API

#### Linux VM with Guest VNC
```bash
# Create Linux VM with VNC enabled
curl -X POST "http://localhost:8000/api/v1/vms" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "name": "linux-desktop-vm",
    "template": "computer-use",
    "vcpus": 4,
    "memory_mb": 8192
  }'

# Start VNC server (guest VNC)
curl -X POST "http://localhost:8000/api/v1/vnc/start" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "vm_name": "linux-desktop-vm",
    "resolution": "1920x1080",
    "color_depth": 24,
    "performance_mode": "quality"
  }'
```

#### Windows VM with Hypervisor VNC
```bash
# Create Windows VM with VNC enabled
curl -X POST "http://localhost:8000/api/v1/vms" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "name": "windows-desktop-vm",
    "template": "windows-desktop",
    "vcpus": 6,
    "memory_mb": 4096
  }'

# Start VNC server (hypervisor VNC)
curl -X POST "http://localhost:8000/api/v1/vnc/start" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "vm_name": "windows-desktop-vm",
    "port": 5901,
    "resolution": "1920x1080",
    "color_depth": 24,
    "performance_mode": "quality"
  }'
```

### Using the Python SDK

```python
from src.sdk import MicroVMManager, SecurityContext

# Initialize manager
security_context = SecurityContext(api_token="your_token")
manager = MicroVMManager(
    api_url="http://localhost:8000",
    security_context=security_context
)

# Create VM with VNC
vm_config = {
    "name": "desktop-vm",
    "template": "computer-use",
    "vcpus": 4,
    "memory_mb": 8192,
    "vnc_enabled": True
}

vm = await manager.create_vm(vm_config)
await manager.start_vm("desktop-vm")

# Start VNC server
vnc_info = await manager.start_vnc("desktop-vm", {
    "resolution": "1920x1080",
    "performance_mode": "quality"
})

print(f"VNC Server: {vnc_info['host']}:{vnc_info['port']}")
print(f"Password: {vnc_info['password']}")
```

## VNC Client Connection

### Using VNC Clients

1. **TigerVNC Viewer** (Recommended)
   ```bash
   # Install on Ubuntu/Debian
   sudo apt install tigervnc-viewer
   
   # Connect
   vncviewer localhost:5901
   ```

2. **RealVNC Viewer**
   - Download from RealVNC website
   - Connect to `localhost:5901`

3. **Built-in VNC (macOS)**
   ```bash
   # Connect via Finder > Go > Connect to Server
   vnc://localhost:5901
   ```

### Web-based VNC (noVNC)

Access desktop through web browser:
```
http://localhost:6080/vnc.html?host=localhost&port=5901
```

## Desktop Automation

### Taking Screenshots

```python
# Take screenshot via API
response = requests.post(
    "http://localhost:8000/api/v1/vnc/screenshot",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={"vm_name": "desktop-vm", "format": "png"}
)

screenshot_data = response.json()["image_data"]
```

### Mouse Control

```python
# Click at coordinates
requests.post(
    "http://localhost:8000/api/v1/vnc/mouse/click",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "vm_name": "desktop-vm",
        "x": 100,
        "y": 200,
        "button": 1  # left click
    }
)
```

### Keyboard Input

```python
# Send key combination
requests.post(
    "http://localhost:8000/api/v1/vnc/keyboard/keys",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "vm_name": "desktop-vm",
        "keys": "ctrl+alt+t"  # Open terminal
    }
)

# Type text
requests.post(
    "http://localhost:8000/api/v1/vnc/keyboard/type",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "vm_name": "desktop-vm",
        "text": "echo 'Hello from VNC automation!'"
    }
)
```

## MCP Integration

### VNC Tools for AI Agents

The MCP server provides tools for AI agents to interact with VNC sessions:

- `take_screenshot` - Capture current desktop state
- `click` - Perform mouse clicks
- `type_text` - Type text into applications
- `scroll` - Scroll in applications
- `get_vnc_info` - Get connection details

### Example MCP Usage

```python
# In Claude Desktop or other MCP client
{
  "tool": "take_screenshot",
  "arguments": {
    "sandbox_name": "my-desktop-vm"
  }
}

{
  "tool": "click",
  "arguments": {
    "sandbox_name": "my-desktop-vm",
    "x": 100,
    "y": 200,
    "button": "left"
  }
}
```

## Performance Optimization

### VNC Performance Modes

1. **Speed Mode** - Lower quality, faster response
   ```json
   {"performance_mode": "speed"}
   ```

2. **Balanced Mode** - Default balanced performance
   ```json
   {"performance_mode": "balanced"}
   ```

3. **Quality Mode** - Higher quality, may be slower
   ```json
   {"performance_mode": "quality"}
   ```

### Resource Allocation

For optimal VNC performance:

- **Minimum:** 2 vCPUs, 2GB RAM
- **Recommended:** 4 vCPUs, 4GB RAM
- **High Performance:** 6+ vCPUs, 8GB+ RAM

### Network Optimization

- Use wired connection for best performance
- Consider VNC compression settings
- Use local networks when possible

## Troubleshooting

### Common Issues

1. **VNC Server Won't Start**
   ```bash
   # Check VM status
   curl -X GET "http://localhost:8000/api/v1/vms/my-vm" \
     -H "Authorization: Bearer YOUR_TOKEN"
   
   # Check VNC logs
   docker logs microvm-sandbox
   ```

2. **Poor Performance**
   - Reduce screen resolution
   - Use "speed" performance mode
   - Increase VM resources
   - Check network bandwidth

3. **Can't Connect to VNC**
   - Verify port forwarding
   - Check firewall settings
   - Ensure VNC server is running

### Debug Commands

```bash
# Check VNC sessions
curl -X GET "http://localhost:8000/api/v1/vnc/sessions" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get VNC info for specific VM
curl -X GET "http://localhost:8000/api/v1/vnc/info/my-vm" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Security Considerations

### VNC Security

- VNC passwords are auto-generated and secure
- Sessions are isolated per VM
- Use API authentication for access
- Consider VPN for remote access

### Best Practices

1. **Use Strong API Keys**
2. **Limit VNC Access** to trusted networks
3. **Regular Password Rotation**
4. **Monitor VNC Sessions** for unauthorized access
5. **Use HTTPS** for web-based VNC access

## Templates Configuration

### Customizing VNC Settings

VM templates can be customized with VNC-specific settings:

```yaml
# config/vm-templates/custom-desktop.yaml
custom_desktop:
  vcpus: 4
  memory_mb: 8192
  
  vnc_server:
    enabled: true
    port: 5901
    resolution: "1920x1080"
    color_depth: 24
    performance_mode: "balanced"
  
  preinstalled_packages:
    - ubuntu-desktop-minimal
    - firefox
    - code
    - git
```

This enables powerful visual AI agent capabilities and desktop automation workflows in isolated MicroVM environments.