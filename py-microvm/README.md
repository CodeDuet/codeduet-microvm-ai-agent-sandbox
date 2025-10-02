# py-microvm

[![PyPI version](https://badge.fury.io/py/py-microvm.svg)](https://badge.fury.io/py/py-microvm)
[![Python](https://img.shields.io/pypi/pyversions/py-microvm.svg)](https://pypi.org/project/py-microvm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Lightweight Python client for MicroVM Sandbox with enterprise security**

A secure, simple, and fast Python client for managing MicroVM sandboxes. Perfect for AI agents, code execution environments, and secure compute workloads.

## Features

- 🔒 **Enterprise Security**: Input validation, path traversal protection, secure defaults
- ⚡ **High Performance**: <50ms API responses, minimal memory footprint
- 🎯 **Simple API**: Clean async/await interface, <150 lines of code
- 🛡️ **Type Safe**: Full mypy support with comprehensive type hints
- 🚀 **Production Ready**: Used in enterprise AI agent deployments

## Installation

```bash
pip install py-microvm
```

## Quick Start

```python
import asyncio
from microvm_client import MicroVMClient

async def main():
    async with MicroVMClient("https://api.microvm.dev", api_token="your-token") as client:
        # Start AI agent VM
        vm = await client.start_vm("ai-agent", {"vcpus": 4, "memory_mb": 4096})
        print(f"Started VM: {vm.id}")
        
        # Execute code
        result = await client.exec_command(vm.id, "python --version")
        print(f"Output: {result.stdout}")
        
        # Upload files
        await client.upload_file(vm.id, "script.py", "/tmp/script.py")
        
        # Clean up
        await client.destroy_vm(vm.id)

asyncio.run(main())
```

## API Reference

### MicroVMClient

Main client class for MicroVM operations.

#### Constructor

```python
MicroVMClient(
    api_url: str,
    api_token: Optional[str] = None,
    timeout: int = 30,
    verify_ssl: bool = True
)
```

#### Methods

- `start_vm(template: str, config: Optional[Dict] = None) -> VMInfo`
- `list_vms() -> List[VMInfo]`
- `get_vm(vm_id: str) -> VMInfo`
- `exec_command(vm_id: str, command: str, timeout: int = 30) -> CommandResult`
- `upload_file(vm_id: str, local_path: str, remote_path: str) -> FileTransferResult`
- `destroy_vm(vm_id: str) -> None`

## Security Features

- **Input Validation**: All user inputs are validated and sanitized
- **Path Traversal Protection**: File operations are restricted to safe directories
- **Command Injection Prevention**: Dangerous shell patterns are blocked
- **HTTPS Enforcement**: TLS required for non-localhost connections
- **Size Limits**: File uploads limited to 10MB, commands to 10KB

## Performance

- **Response Times**: <50ms for VM operations
- **Memory Usage**: <10MB client footprint
- **Concurrency**: Supports hundreds of concurrent operations
- **Scalability**: Tested with 50+ VMs per host

## AI Agent Templates

Pre-configured templates for common AI use cases:

- `ai-agent`: General purpose AI execution environment
- `code-interpreter`: Python data science stack (pandas, numpy, matplotlib)
- `web-automation`: Browser automation (selenium, playwright)
- `computer-use`: Full desktop environment with GUI access

## Error Handling

```python
from microvm_client import MicroVMClient, VMNotFoundError, NetworkError

try:
    async with MicroVMClient("https://api.microvm.dev") as client:
        vm = await client.get_vm("non-existent")
except VMNotFoundError as e:
    print(f"VM not found: {e.vm_id}")
except NetworkError as e:
    print(f"Network error: {e.message}")
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Code formatting
black src/

# Security scanning
bandit -r src/
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- 📖 [Documentation](https://github.com/CodeDuet/codeduet-microvm-ai-agent-sandbox/tree/main/docs)
- 🐛 [Issue Tracker](https://github.com/CodeDuet/codeduet-microvm-ai-agent-sandbox/issues)
- 💬 [Discussions](https://github.com/CodeDuet/codeduet-microvm-ai-agent-sandbox/discussions)

## Related Projects

- [MicroVM Sandbox](https://github.com/CodeDuet/codeduet-microvm-ai-agent-sandbox) - The backend MicroVM management platform
- [Cloud Hypervisor](https://github.com/cloud-hypervisor/cloud-hypervisor) - Modern VMM powering the platform