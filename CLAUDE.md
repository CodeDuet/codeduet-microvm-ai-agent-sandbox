# Claude.md - MicroVM Sandbox Project Context

## Overview
Cloud Hypervisor + Python MicroVM Sandbox with hardware-level isolation for Linux/Windows guests.

## Architecture
- **FastAPI Server**: VM management REST API
- **Cloud Hypervisor**: Rust VMM with KVM support
- **MicroVMs**: Linux (kernel boot) + Windows (UEFI boot)

## Structure
```
src/{api,core,utils,cli,guest_agents}/ config/ images/ scripts/ tests/ docs/ monitoring/
```

## Key Components
- **VM Management**: `vm_manager.py`, `ch_client.py`, `network_manager.py`, `snapshot_manager.py`
- **API**: `server.py`, routes, Pydantic models
- **Guests**: Linux/Windows agents + `guest_client.py`

## Commands
```bash
# Setup
./scripts/setup/{install-dependencies,install-cloud-hypervisor,setup-networking}.sh
make dev-server

# Test/Quality
pytest tests/{unit,integration,performance}/
flake8 src/ && black src/ && mypy src/
```

## Config
- **Main**: `config/config.yaml` (server, networking, resources, security)
- **Templates**: `config/vm-templates/{linux,windows}-default.yaml`

## Requirements
- **Host**: Ubuntu 20.04+, 4+ cores, 8GB+ RAM, KVM
- **Software**: Python >=3.9, Cloud Hypervisor >=34.0
- **Packages**: FastAPI, uvicorn, httpx, pydantic, prometheus-client

## Targets
- Boot: <3s Linux, <10s Windows
- API: <100ms response
- Scale: 50+ VMs/host, <5% overhead

## Change Management Rules
**MANDATORY**: When making ANY changes to the codebase:

1. **Always update CHANGES.md**:
   - Add entry with date, change type, and description
   - Include affected files/components
   - Note any breaking changes or migration steps

2. **Update documentation**:
   - Modify relevant docs/ files for new features
   - Update API documentation for endpoint changes
   - Update config examples for new parameters
   - Update README.md if setup/usage changes

3. **Change tracking format**:
   ```
   ## [YYYY-MM-DD] - Change Type
   ### Changed/Added/Fixed/Removed
   - Description of change (files: path/to/file.py)
   - Breaking change note if applicable
   ```