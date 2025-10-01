# Changelog

## [2025-10-01] - Phase 1 Week 2: Core VM Management Implementation
### Added
- **Complete Cloud Hypervisor Client Integration** (files: src/core/ch_client.py)
  - HTTP client for Cloud Hypervisor REST API communication via Unix domain sockets
  - VM lifecycle operations: create, boot, pause, resume, shutdown, resize
  - Snapshot and restore functionality with file-based storage
  - Enhanced VM configuration builder with topology, performance, and security options
  - Proper error handling and resource cleanup with timeout management
  - Support for VSOCK guest agent communication

- **Full-Featured VM Manager** (files: src/core/vm_manager.py)
  - Complete VM lifecycle management with state tracking (creating, stopped, running, paused, error)
  - Template-based VM configuration with override support
  - Persistent VM data storage with JSON serialization
  - Resource validation and limits enforcement
  - Real-time VM status monitoring with hypervisor metrics
  - Automatic cleanup and graceful error handling

- **Advanced Network Manager** (files: src/core/network_manager.py)
  - Bridge network setup and teardown with automatic configuration
  - TAP interface creation and management for VM networking
  - Dynamic IP address allocation from configurable subnet
  - Port forwarding with iptables NAT rules
  - Network statistics collection (rx/tx bytes)
  - Comprehensive cleanup and resource management

- **Enhanced Linux MicroVM Templates** (files: config/vm-templates/)
  - Optimized linux-default template with enhanced boot arguments and device configuration
  - New linux-microvm template optimized for fast boot times (<500ms target)
  - Advanced configuration options: CPU topology, rate limiting, security features
  - Support for hugepages, seccomp, and performance optimizations

- **Extended API Endpoints** (files: src/api/routes/)
  - Enhanced VM endpoints: pause/resume, status monitoring with hypervisor metrics
  - New network management endpoints for interface management and port forwarding
  - Bridge network setup/teardown endpoints
  - Comprehensive error handling with proper HTTP status codes

- **Comprehensive Unit Test Suite** (files: tests/unit/)
  - 84 passing unit tests with comprehensive coverage
  - VM Manager tests: lifecycle operations, error handling, state management
  - Cloud Hypervisor Client tests: API communication, configuration building
  - Network Manager tests: interface management, IP allocation, port forwarding
  - Async mock support with proper coroutine handling

### Enhanced
- **VM Configuration System** - Extended template support with advanced device, performance, and security options
- **API Error Handling** - Improved error responses with detailed messages and proper status codes
- **Resource Management** - Added proper cleanup and resource tracking across all components

### Technical Implementation Notes
- All core VM management functionality now fully integrated with Cloud Hypervisor
- Network isolation and security implemented through bridge networking and iptables
- Performance optimizations for sub-3-second Linux boot times
- Comprehensive state management and error recovery
- Full async/await pattern implementation throughout codebase

## [2025-10-01] - Phase 1 Week 1: Initial Setup
### Added
- MIT License for the project (files: LICENSE)
- Comprehensive README.md with features, architecture, setup instructions, and documentation (files: README.md)
- Detailed development plan with 12-week timeline, technical specifications, and implementation details (files: development-plan.md)
- Unit testing requirement added to project change management rules (files: CLAUDE.md)
- Complete project structure following development plan (files: src/, config/, tests/, scripts/, docs/, monitoring/)
- Python package configuration with dependencies and dev tools (files: requirements.txt, requirements-dev.txt, pyproject.toml, Makefile)
- FastAPI application skeleton with REST API endpoints for VMs, system info, and snapshots (files: src/api/)
- Pydantic models for VM management, requests, and responses (files: src/api/models/)
- Configuration management system with YAML support and environment variables (files: src/utils/config.py, config/)
- Logging system with structured logging, file rotation, and JSON output (files: src/utils/logging.py)
- Helper utilities for async file operations, validation, and subprocess management (files: src/utils/helpers.py)