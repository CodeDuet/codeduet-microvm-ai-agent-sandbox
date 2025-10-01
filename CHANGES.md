# Changelog

## [2025-10-01] - Phase 2 Week 5: Guest Communication Implementation
### Added
- **Complete Guest Agent System** (files: src/guest_agents/)
  - Linux guest agent with Unix socket communication using asyncio server
  - Windows guest agent with named pipe communication and WMI integration
  - Full command execution with timeout, environment variables, and working directory support
  - Bidirectional file transfer with base64 encoding and checksum verification
  - Comprehensive system monitoring: processes, memory, disk, network interfaces
  - Health monitoring with CPU usage, memory usage, and disk usage metrics
  - Installation scripts for both Linux (systemd service) and Windows (Windows service)

- **Host-to-Guest Communication Client** (files: src/core/guest_client.py)
  - Unified client interface for both Linux and Windows guest communication
  - OS-specific protocol handling: Unix sockets for Linux, named pipes for Windows
  - Command execution with comprehensive parameter support and error handling
  - File upload/download with integrity verification and size limits
  - System information retrieval and process monitoring
  - Windows-specific features: services management and event log access
  - Guest manager for client lifecycle management and health monitoring

- **Guest Communication API Endpoints** (files: src/api/routes/guest.py)
  - RESTful endpoints for all guest communication operations
  - `/vms/{vm_name}/guest/ping` - Guest agent connectivity testing
  - `/vms/{vm_name}/guest/execute` - Command execution with full parameter support
  - `/vms/{vm_name}/guest/files/upload` and `/vms/{vm_name}/guest/files/download` - File transfer operations
  - `/vms/{vm_name}/guest/system-info` - Comprehensive system information
  - `/vms/{vm_name}/guest/processes` - Running process enumeration
  - `/vms/{vm_name}/guest/health` - Guest health monitoring
  - `/vms/{vm_name}/guest/shutdown` - Graceful guest shutdown
  - Windows-specific endpoints: `/vms/{vm_name}/guest/services` and `/vms/{vm_name}/guest/event-logs`

- **Enhanced API Models** (files: src/api/models/vm.py)
  - Guest communication request/response models with comprehensive validation
  - Command execution models with timeout, environment, and working directory support
  - File transfer models with path validation and size limits
  - System information and health check response models
  - Windows-specific models for services and event logs

- **Comprehensive Guest Communication Tests** (files: tests/unit/)
  - Complete unit test coverage for guest client with async mocking
  - API endpoint tests with FastAPI TestClient and dependency injection mocking
  - Error handling tests for communication failures and edge cases
  - OS-specific functionality tests for Linux and Windows features
  - Mock-based testing for Unix sockets and named pipes

### Enhanced
- **VM Manager Integration** - Guest agent enablement and OS-specific configuration
- **API Server** - New guest communication routes integrated into main application
- **Error Handling** - Comprehensive error handling for guest communication failures
- **Security** - Guest agent runs with restricted permissions and proper isolation

### Technical Implementation Notes
- Guest agents use secure communication protocols with proper authentication
- File transfers include integrity verification with SHA256 checksums
- Command execution includes proper timeout handling and resource limits
- Windows agent leverages WMI for enhanced system information collection
- All guest communication is asynchronous with proper error handling
- Guest agents install as system services for automatic startup and management

### Phase 2 Status: ✅ COMPLETED
- **Foundation (Weeks 1-3)**: ✅ Complete Linux MicroVM support with REST API
- **Windows Support (Week 4)**: ✅ Full UEFI Windows MicroVM implementation
- **Guest Communication (Week 5)**: ✅ Bidirectional host-guest communication system
- **Networking (Week 6)**: ✅ Advanced networking with bridge, TAP, and port forwarding
- **Test Coverage**: 122 unit tests passing with comprehensive coverage

## [2025-10-01] - Phase 2 Week 4: Windows MicroVM Support Implementation
### Added
- **Complete Windows MicroVM Support with UEFI** (files: src/core/ch_client.py, src/core/vm_manager.py)
  - Enhanced Cloud Hypervisor client with Windows UEFI boot support
  - VirtIO devices configuration for Windows: block storage, network, serial, RNG
  - Windows-specific VM configuration methods with resource validation
  - OS-specific boot configuration management for both Linux and Windows
  - Deterministic MAC address generation for Windows licensing compatibility

- **Enhanced Windows VM Template** (files: config/vm-templates/windows-default.yaml)
  - Comprehensive Windows template with UEFI firmware and VirtIO drivers
  - Performance optimizations: CPU topology, memory configuration, device settings
  - Security settings appropriate for Windows guests (disabled seccomp, optimized IOMMU)
  - VirtIO drivers ISO integration for automated driver installation
  - Enhanced device configuration with VirtIO-optimized settings

- **Windows Guest Image Preparation System** (files: scripts/setup/prepare-windows-image.sh)
  - Automated Windows guest image preparation script with OVMF UEFI firmware download
  - VirtIO drivers ISO download and integration
  - Windows automation files: autounattend.xml for unattended installation
  - PowerShell guest agent setup script with VirtIO driver installation
  - Automated disk image creation with proper formatting and structure

- **Advanced Image Management System** (files: src/core/image_manager.py)
  - Comprehensive VM image registry with metadata and integrity checking
  - Support for both Windows (qcow2) and Linux (kernel/rootfs) image formats
  - Image validation with format detection and size verification
  - Automated checksum calculation and integrity verification
  - Image creation utilities for Windows disks and Linux rootfs

- **Enhanced API Endpoints** (files: src/api/routes/vms.py)
  - OS-specific VM creation endpoints: `/vms/linux` and `/vms/windows`
  - Enhanced VM creation with OS-specific validation and configuration
  - Improved error handling with detailed Windows-specific requirements

### Enhanced
- **Cloud Hypervisor Integration** - Added Windows UEFI support with proper firmware and VirtIO device configuration
- **VM Configuration System** - OS-specific configuration application with Windows and Linux optimizations
- **Resource Management** - Windows minimum resource requirements enforcement (2+ vCPUs, 1024+ MB RAM)

### Technical Implementation Notes
- Windows VMs now support UEFI boot with OVMF firmware
- VirtIO drivers automatically integrated for optimal Windows performance
- Automated Windows installation process with guest agent deployment
- Comprehensive image management with format validation and integrity checking
- All 84 unit tests passing with new Windows functionality

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