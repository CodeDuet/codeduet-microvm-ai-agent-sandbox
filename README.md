# AI Agent MicroVM Sandbox
To quote Solomon Hykes:
> An AI agent is an LLM wrecking its environment in a loop.

## 🛡️ The AI Agent Security Crisis You Can't Ignore

**Your AI agents are one command away from disaster.** Here are three critical risks that traditional "YOLO mode" AI deployment exposes you to:

🚨 **Destructive Shell Commands** - Bad scripts deleting or corrupting critical files, databases, or entire systems  
🕵️ **Data Exfiltration Attacks** - Malicious actors stealing source code, secrets, or sensitive data from environment variables  
🎯 **Proxy Attacks** - Your infrastructure hijacked for DDoS attacks or to mask the origin of cyber attacks against other targets  

**Our MicroVM solution eliminates these risks with hardware-level isolation that traditional containers simply cannot provide.**

A production-ready AI agent microVM sandbox system using Cloud Hypervisor and Python, providing hardware-level isolation through MicroVMs while maintaining lightweight resource usage. Supports both Linux and Windows guest operating systems.

## 🚀 Features

- **Hardware-Level Isolation**: KVM-based MicroVMs for strong security boundaries
- **Multi-OS Support**: Linux (kernel boot) and Windows (UEFI boot) guest VMs
- **REST API**: FastAPI-based management interface with OpenAPI documentation
- **Guest Communication**: Bidirectional host-guest communication via HTTP agents
- **Snapshot & Restore**: Full VM state management for quick provisioning
- **Network Management**: Automated TAP devices, bridging, and port forwarding
- **Resource Management**: CPU, memory quotas and system resource monitoring
- **Production Ready**: Monitoring, scaling, security hardening, and deployment automation

## 📦 Python SDK

The MicroVM Sandbox includes a lightweight Python SDK for easy integration:

```bash
# Install from PyPI
pip install py-microvm
```

**Quick Usage:**
```python
from microvm_client import MicroVMClient

async with MicroVMClient("http://localhost:8000") as client:
    # Create and start a VM
    vm = await client.start_vm("my-vm", {"template": "linux-default"})
    
    # Execute commands
    result = await client.exec_command(vm.id, "python --version")
    print(result.output)
    
    # Upload files
    await client.upload_file(vm.id, "script.py", "/tmp/script.py")
    
    # Clean up
    await client.destroy_vm(vm.id)
```

**Package Information:**
- **PyPI**: https://pypi.org/project/py-microvm/
- **Version**: 1.0.1
- **License**: MIT
- **Dependencies**: httpx, pydantic

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐
│   Python SDK    │    │   Management CLI │
└─────────┬───────┘    └────────┬─────────┘
          │ REST API             │ REST API
          └─────────┬───────────────────┬────────────
                    │                   │
                    ▼                   ▼
          ┌─────────────────────────────────────────┐
          │       Python REST Server (FastAPI)     │
          │      (Cloud Hypervisor Manager)        │
          └─────────────────┬───────────────────────┘
                            │ HTTP API
                            ▼
          ┌─────────────────────────────────────────┐
          │        Cloud Hypervisor VMM             │
          │         (Multi-OS Support)              │
          └─────────────────┬───────────────────────┘
                            │ KVM/Hardware
          ┌─────────────────┼─────────────────┐
          │                 ▼                 │
          │        ┌─────────────────┐        │
          │        │    /dev/kvm     │        │
          │        └─────────────────┘        │
          │                                   │
    ┌─────┴─────────────┐           ┌─────────────────┴─────┐
    │   Linux MicroVM   │           │   Windows MicroVM     │
    │                   │           │                       │
    │ ┌───────────────┐ │           │ ┌───────────────────┐ │
    │ │ Guest Services│ │           │ │  Guest Services   │ │
    │ │ & Agent       │ │           │ │  & Agent          │ │
    │ └───────────────┘ │           │ └───────────────────┘ │
    │  Secure Sandbox   │           │   Secure Sandbox     │
    └───────────────────┘           └───────────────────────┘
```

## 📋 System Requirements

### Host System
- **OS**: Ubuntu 20.04+ or RHEL 8+
- **CPU**: 4+ cores with VT-x/AMD-V support
- **Memory**: 8GB+ RAM (32GB recommended)
- **Storage**: 50GB+ SSD (200GB NVMe recommended)
- **Network**: 1Gbps+ interface

### Software Dependencies
- Python >=3.9
- Cloud Hypervisor >=34.0
- KVM (kernel 5.4+)
- Docker (optional, for containerized deployment)

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/CodeDuet/codeduet-microvm-ai-agent-sandbox.git
cd codeduet-microvm-ai-agent-sandbox

# Install system dependencies
sudo ./scripts/setup/install-dependencies.sh

# Install Cloud Hypervisor
sudo ./scripts/setup/install-cloud-hypervisor.sh

# Setup networking
sudo ./scripts/setup/setup-networking.sh

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy default configuration
cp config/config.yaml.example config/config.yaml

# Edit configuration as needed
nano config/config.yaml
```

### 3. Start the Service

```bash
# Development mode
make dev-server

# Or manually
uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Create Your First VM

```bash
# Using the CLI
python -m src.cli vm create --name my-vm --template linux-default

# Using the REST API
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-vm",
    "template": "linux-default",
    "vcpus": 2,
    "memory_mb": 512
  }'
```

## 📚 Documentation

### 🚀 Getting Started
- **[Quick Start Guide](docs/user-guide/quickstart.md)** - Get up and running in minutes
- **[Installation & Setup](docs/user-guide/quickstart.md#installation)** - Complete installation instructions
- **[Your First VM](docs/user-guide/quickstart.md#create-your-first-vm)** - Create and manage your first VM

### 📖 User Guides
- **[VM Management Guide](docs/user-guide/vm-management.md)** - Complete VM lifecycle management
  - Creating, starting, stopping VMs
  - Command execution and file transfer
  - Resource allocation and monitoring
  - Windows and Linux VM operations
- **[Troubleshooting Guide](docs/user-guide/troubleshooting.md)** - Common issues and solutions
  - VM startup problems
  - Network connectivity issues
  - Performance optimization
  - Debug and recovery procedures

### 🔧 API Reference
- **[Complete API Documentation](docs/api/reference.md)** - Comprehensive REST API reference
  - All endpoints with examples
  - Authentication and authorization
  - Error codes and responses
  - WebSocket endpoints
- **Interactive API Docs**: Visit `http://localhost:8000/docs` when server is running
- **Alternative Docs**: Visit `http://localhost:8000/redoc` for ReDoc interface

### 🚀 Deployment Guides
- **[Docker Deployment](docs/deployment/docker.md)** - Containerized deployment
  - Single container setup
  - Multi-service docker-compose
  - Production configurations
  - Monitoring and security
- **[Kubernetes Deployment](docs/deployment/kubernetes.md)** - Cloud-native deployment
  - Complete manifests and Helm charts
  - High availability setup
  - Auto-scaling configuration
  - Monitoring integration
- **[Bare Metal Deployment](docs/deployment/bare-metal.md)** - Direct server installation
  - System optimization
  - Performance tuning
  - Security hardening
  - Maintenance procedures

### ⚡ How-To Guides

#### VM Operations
- **Creating VMs**: See [VM Management - Creating VMs](docs/user-guide/vm-management.md#creating-vms)
- **Managing Snapshots**: See [VM Management - Snapshot Management](docs/user-guide/vm-management.md#snapshot-management)
- **File Transfer**: See [VM Management - File Transfer](docs/user-guide/vm-management.md#file-transfer)
- **Command Execution**: See [VM Management - Command Execution](docs/user-guide/vm-management.md#command-execution)

#### Network Configuration
- **Basic Networking**: See [VM Management - Network Configuration](docs/user-guide/vm-management.md#network-configuration)
- **Port Forwarding**: See [VM Management - Port Forwarding](docs/user-guide/vm-management.md#port-forwarding)
- **Network Isolation**: See [VM Management - Network Isolation](docs/user-guide/vm-management.md#network-isolation)

#### Performance & Monitoring
- **Resource Monitoring**: See [VM Management - Resource Management](docs/user-guide/vm-management.md#resource-management)
- **Performance Tuning**: See [Bare Metal Deployment - Performance Optimization](docs/deployment/bare-metal.md#performance-optimization)
- **Load Testing**: See [Load Testing Script](scripts/testing/load-test.py)

#### Security & Compliance
- **Authentication Setup**: See [API Reference - Authentication](docs/api/reference.md#authentication)
- **Security Hardening**: See [Bare Metal Deployment - Security Hardening](docs/deployment/bare-metal.md#security-hardening)
- **Audit Logging**: See [API Reference - Security Management](docs/api/reference.md#security-management)

#### Troubleshooting
- **VM Won't Start**: See [Troubleshooting - VM Creation Failures](docs/user-guide/troubleshooting.md#vm-creation-failures)
- **Network Issues**: See [Troubleshooting - Network Connectivity](docs/user-guide/troubleshooting.md#network-connectivity-problems)
- **Performance Issues**: See [Troubleshooting - Performance Issues](docs/user-guide/troubleshooting.md#performance-issues)
- **Debug Mode**: See [Troubleshooting - Advanced Diagnostics](docs/user-guide/troubleshooting.md#advanced-diagnostics)

### 🧪 Testing Documentation
- **[Integration Tests](tests/integration/)** - VM lifecycle and security integration tests
- **[Performance Tests](tests/performance/)** - Boot time, resource usage, and load testing
- **[Load Testing Guide](scripts/testing/load-test.py)** - API load testing framework
- **[Test Validation](scripts/testing/validate-tests.py)** - Test syntax and import validation

### 🔍 Advanced Topics
- **High Availability**: See [Kubernetes Deployment - High Availability](docs/deployment/kubernetes.md#high-availability-setup)
- **Auto-scaling**: See [Kubernetes Deployment - Scaling and Autoscaling](docs/deployment/kubernetes.md#scaling-and-autoscaling)
- **Monitoring Setup**: See [Docker Deployment - Monitoring](docs/deployment/docker.md#monitoring-and-logging)
- **Backup & Recovery**: See [Bare Metal Deployment - Backup and Recovery](docs/deployment/bare-metal.md#backup-and-recovery)

## 🛠️ Development

### Environment Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Setup pre-commit hooks
pre-commit install

# Run in development mode
make dev-server
```

### Testing

```bash
# Run core functionality tests (most reliable)
python scripts/testing/run-core-tests.py

# Run all unit tests
pytest tests/unit/ -v

# Run integration tests (requires VM infrastructure)
pytest tests/integration/ -v

# Run performance tests
pytest tests/performance/ -v

# Validate test syntax and imports
python scripts/testing/validate-tests.py

# Run load testing against API
python scripts/testing/load-test.py --users 10 --operations 5

# Run with coverage
pytest --cov=src tests/unit/
```

### Code Quality

```bash
# Format code
black src/

# Lint code
flake8 src/

# Type checking
mypy src/
```

## 🐳 Deployment

### Docker

```bash
# Build image
docker build -t microvm-sandbox:latest .

# Run with docker-compose
docker-compose up -d
```

### Kubernetes

```bash
# Deploy to Kubernetes
kubectl apply -f scripts/deployment/kubernetes/
```

### Production

```bash
# Install as system service
sudo ./scripts/deployment/install-systemd-service.sh
sudo systemctl enable microvm-sandbox
sudo systemctl start microvm-sandbox
```

## 📊 Monitoring & Observability

The system includes enterprise-grade monitoring and observability:

- **[Prometheus Metrics](docs/api/reference.md#system-metrics)**: VM performance, resource usage, API metrics
- **[Grafana Dashboards](docs/deployment/docker.md#monitoring-and-logging)**: Pre-built dashboards for system visualization
- **[Health Checks](docs/api/reference.md#health-and-status)**: Built-in health endpoints for load balancers
- **[Structured Logging](docs/deployment/bare-metal.md#monitoring-setup)**: JSON logs with correlation IDs
- **[Performance Testing](docs/user-guide/troubleshooting.md#performance-issues)**: Load testing and benchmarking tools

```bash
# Access monitoring endpoints
http://localhost:9090  # Prometheus metrics
http://localhost:3000  # Grafana dashboards  
http://localhost:8000/health  # Health check
http://localhost:8000/status  # Detailed status
http://localhost:8000/api/v1/system/metrics  # System metrics API

# Performance testing
python scripts/testing/load-test.py --users 50 --operations 10
```

For complete monitoring setup guides, see:
- **[Docker Monitoring Setup](docs/deployment/docker.md#monitoring-and-logging)**
- **[Kubernetes Monitoring](docs/deployment/kubernetes.md#monitoring-and-observability)**
- **[Bare Metal Monitoring](docs/deployment/bare-metal.md#monitoring-setup)**

## 🔧 Configuration

### VM Templates

Create custom VM templates in `config/vm-templates/`:

```yaml
# config/vm-templates/my-template.yaml
my_template:
  vcpus: 4
  memory_mb: 2048
  kernel: "images/linux/vmlinux.bin"
  rootfs: "images/linux/rootfs.ext4"
  boot_args: "console=ttyS0 reboot=k panic=1"
  guest_agent:
    enabled: true
    port: 8080
```

### Network Configuration

```yaml
# config/networks/custom-network.yaml
networking:
  bridge_name: "mybr0"
  subnet: "10.0.0.0/24"
  port_range:
    start: 20000
    end: 30000
```

## 🔒 Security & Compliance

Enterprise-grade security with comprehensive compliance support:

- **[VM Isolation](docs/user-guide/vm-management.md#network-isolation)**: Hardware-level isolation via KVM
- **[Network Security](docs/api/reference.md#network-management)**: Separate network namespaces per VM
- **[Input Validation](docs/api/reference.md#error-responses)**: Comprehensive request validation and sanitization
- **[Authentication & RBAC](docs/api/reference.md#authentication)**: JWT-based authentication with role-based access control
- **[Audit Logging](docs/api/reference.md#security-management)**: Security events and compliance logging
- **[Security Scanning](docs/api/reference.md#security-management)**: Vulnerability scanning and risk assessment
- **[Compliance Frameworks](docs/user-guide/troubleshooting.md#compliance-logging)**: SOC 2, ISO 27001, HIPAA, PCI DSS, GDPR support

Security setup guides:
- **[Security Hardening](docs/deployment/bare-metal.md#security-hardening)**
- **[Network Security](docs/deployment/kubernetes.md#security-configuration)**
- **[Docker Security](docs/deployment/docker.md#security-hardening)**

## 🚀 Performance

Target performance metrics:

- **VM Boot Time**: <3s for Linux, <10s for Windows
- **API Response**: <100ms for management operations
- **Concurrent VMs**: 50+ VMs per host
- **Resource Overhead**: <5% host CPU and memory usage

## 📝 Use Cases

- **Secure Code Execution**: Isolate untrusted code execution
- **Multi-Tenant Environments**: Provide isolated environments for multiple users
- **CI/CD Pipelines**: Isolate build and test environments
- **Security Testing**: Safe environment for malware analysis
- **Development Environments**: Quickly provision development sandboxes
- **Cross-Platform Testing**: Test applications on multiple OS environments

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](docs/development/contributing.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- [Cloud Hypervisor](https://github.com/cloud-hypervisor/cloud-hypervisor)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [KVM Documentation](https://www.linux-kvm.org/)

## 📞 Support & Help

### 📖 Documentation & Guides
- **[Quick Start Guide](docs/user-guide/quickstart.md)** - Get started in minutes
- **[Troubleshooting Guide](docs/user-guide/troubleshooting.md)** - Common issues and solutions
- **[Complete API Reference](docs/api/reference.md)** - Full API documentation
- **[Deployment Guides](docs/deployment/)** - Docker, Kubernetes, and bare metal

### 🔧 Self-Help Resources
- **[FAQ & Common Issues](docs/user-guide/troubleshooting.md#common-issues)**
- **[Performance Tuning](docs/user-guide/troubleshooting.md#performance-issues)**
- **[Debug Procedures](docs/user-guide/troubleshooting.md#advanced-diagnostics)**
- **[Recovery Procedures](docs/user-guide/troubleshooting.md#recovery-procedures)**

### 💬 Community Support
- **Issues**: [GitHub Issues](https://github.com/CodeDuet/codeduet-microvm-ai-agent-sandbox/issues)
- **Discussions**: [GitHub Discussions](https://github.com/CodeDuet/codeduet-microvm-ai-agent-sandbox/discussions)
- **Documentation**: [Complete Documentation](docs/)

### 🚨 Getting Help
When reporting issues, please include:
1. **System Information**: OS, hardware specs, Cloud Hypervisor version
2. **Configuration**: Relevant config files (redact sensitive data)
3. **Logs**: Error logs and debug output
4. **Steps to Reproduce**: Clear reproduction steps
5. **Expected vs Actual**: What you expected vs what happened

See our **[Bug Reporting Guide](docs/user-guide/troubleshooting.md#getting-help)** for detailed instructions.

---

Built with ❤️ for secure, lightweight virtualization.