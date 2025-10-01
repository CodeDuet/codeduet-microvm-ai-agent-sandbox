# MicroVM Sandbox

A production-ready MicroVM sandbox system using Cloud Hypervisor and Python, providing hardware-level isolation through MicroVMs while maintaining lightweight resource usage. Supports both Linux and Windows guest operating systems.

## 🚀 Features

- **Hardware-Level Isolation**: KVM-based MicroVMs for strong security boundaries
- **Multi-OS Support**: Linux (kernel boot) and Windows (UEFI boot) guest VMs
- **REST API**: FastAPI-based management interface with OpenAPI documentation
- **Guest Communication**: Bidirectional host-guest communication via HTTP agents
- **Snapshot & Restore**: Full VM state management for quick provisioning
- **Network Management**: Automated TAP devices, bridging, and port forwarding
- **Resource Management**: CPU, memory quotas and system resource monitoring
- **Production Ready**: Monitoring, scaling, security hardening, and deployment automation

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
git clone <repository-url>
cd microvm-sandbox

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

### API Reference
- **OpenAPI Docs**: Visit `http://localhost:8000/docs` when server is running
- **Redoc**: Visit `http://localhost:8000/redoc` for alternative documentation

### User Guides
- [VM Management](docs/user-guide/vm-management.md)
- [Network Configuration](docs/user-guide/networking.md)
- [Snapshot Operations](docs/user-guide/snapshots.md)
- [Troubleshooting](docs/user-guide/troubleshooting.md)

### Development
- [Development Setup](docs/development/setup.md)
- [Testing Guide](docs/development/testing.md)
- [Contributing Guidelines](docs/development/contributing.md)

### Deployment
- [Docker Deployment](docs/deployment/docker.md)
- [Kubernetes Deployment](docs/deployment/kubernetes.md)
- [Bare Metal Deployment](docs/deployment/bare-metal.md)

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
# Run all tests
make test

# Run specific test suites
pytest tests/unit/
pytest tests/integration/
pytest tests/performance/

# Run with coverage
pytest --cov=src tests/
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

## 📊 Monitoring

The system includes comprehensive monitoring capabilities:

- **Prometheus Metrics**: VM performance, resource usage, API metrics
- **Grafana Dashboards**: Pre-built dashboards for system visualization
- **Health Checks**: Built-in health endpoints for load balancers
- **Structured Logging**: JSON logs with correlation IDs

```bash
# Access monitoring
http://localhost:9090  # Prometheus
http://localhost:3000  # Grafana
http://localhost:8000/health  # Health check
```

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

## 🔒 Security

- **VM Isolation**: Hardware-level isolation via KVM
- **Network Isolation**: Separate network namespaces per VM
- **Input Validation**: Comprehensive request validation
- **Authentication**: API key-based authentication
- **Audit Logging**: Security events and access logs
- **Resource Limits**: Prevent resource exhaustion attacks

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

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-org/microvm-sandbox/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/microvm-sandbox/discussions)
- **Documentation**: [Project Wiki](https://github.com/your-org/microvm-sandbox/wiki)

---

Built with ❤️ for secure, lightweight virtualization.