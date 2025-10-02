# MicroVM Sandbox - Quick Start Guide

## Simplified Setup (5 minutes)

### 1. Prerequisites
```bash
# Ubuntu 20.04+ with KVM support
sudo apt update
sudo apt install -y python3.9 python3-pip
```

### 2. Fast Installation
```bash
# Install dependencies and Cloud Hypervisor
./scripts/setup/install-dependencies.sh
./scripts/setup/install-cloud-hypervisor.sh

# Setup networking
sudo ./scripts/setup/setup-networking.sh
```

### 3. Quick Start
```bash
# Use simplified config
cp config/config.simple.yaml config/config.yaml

# Start development server
make dev-server
```

### 4. Create Your First VM
```bash
# API will be available at http://localhost:8000
curl -X POST http://localhost:8000/api/v1/vms/linux \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "name": "my-vm",
    "memory": 1024,
    "vcpus": 2
  }'
```

## What's Different in This Simplified Approach?

- **Minimal Config**: Only 20 essential parameters vs 196 in full config
- **Sensible Defaults**: Production-ready security with minimal setup
- **Focus on Speed**: <3s Linux boot, <100ms API response targets maintained
- **Clear Separation**: Advanced features in separate config files

## Next Steps

- For production: Review `config/security.yaml` for hardening options
- For scaling: See `config/advanced.yaml` for cluster settings
- For monitoring: Check `docs/monitoring.md` for observability setup

## Security Notes

- Default JWT secret is secure but should be rotated in production
- CORS is restricted to localhost - update for production domains
- VM file operations restricted to `/tmp` for safety