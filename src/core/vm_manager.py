from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from src.api.models.vm import VMCreateRequest, VMInfo, VMState, OSType
from src.core.ch_client import CloudHypervisorClient
from src.utils.config import load_vm_template, get_settings
from src.utils.helpers import generate_vm_id, validate_vm_name, write_json_async, read_json_async
from src.utils.logging import get_logger

logger = get_logger(__name__)


class VMManager:
    def __init__(self):
        self.settings = get_settings()
        self.vms: Dict[str, VMInfo] = {}
        self.vm_data_dir = Path("data/vms")
        self.vm_data_dir.mkdir(parents=True, exist_ok=True)

    async def create_linux_vm(self, request: VMCreateRequest) -> VMInfo:
        """Create a Linux MicroVM with kernel boot."""
        request.os_type = OSType.LINUX
        return await self.create_vm(request)
    
    async def create_windows_vm(self, request: VMCreateRequest) -> VMInfo:
        """Create a Windows MicroVM with UEFI boot."""
        request.os_type = OSType.WINDOWS
        
        # Validate Windows-specific requirements
        if not request.template or not request.template.startswith("windows"):
            request.template = "windows-default"
        
        # Ensure adequate resources for Windows
        if request.memory_mb and request.memory_mb < 1024:
            raise ValueError("Windows VMs require at least 1024MB of memory")
        
        if request.vcpus and request.vcpus < 2:
            raise ValueError("Windows VMs require at least 2 vCPUs")
        
        return await self.create_vm(request)

    async def create_vm(self, request: VMCreateRequest) -> VMInfo:
        if not validate_vm_name(request.name):
            raise ValueError(f"Invalid VM name: {request.name}")
        
        if request.name in self.vms:
            raise ValueError(f"VM '{request.name}' already exists")
        
        logger.info(f"Creating VM '{request.name}' with template '{request.template}'")
        
        try:
            template = load_vm_template(request.template)
        except FileNotFoundError:
            raise ValueError(f"Template '{request.template}' not found")
        
        # Merge template with request overrides
        vm_config = template.copy()
        if request.vcpus:
            vm_config["vcpus"] = request.vcpus
        if request.memory_mb:
            vm_config["memory_mb"] = request.memory_mb
        
        vm_info = VMInfo(
            name=request.name,
            state=VMState.CREATING,
            vcpus=vm_config["vcpus"],
            memory_mb=vm_config["memory_mb"],
            os_type=request.os_type,
            template=request.template,
            guest_agent=request.guest_agent,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata=request.metadata or {}
        )
        
        # Store VM info
        self.vms[request.name] = vm_info
        await self._save_vm_data(request.name, vm_info)
        
        # Initialize Cloud Hypervisor client and create VM
        ch_client = CloudHypervisorClient(request.name)
        try:
            await ch_client.create_vm(vm_config)
            vm_info.state = VMState.STOPPED
        except Exception as e:
            vm_info.state = VMState.ERROR
            logger.error(f"Failed to create VM '{request.name}': {e}")
            raise
        finally:
            vm_info.updated_at = datetime.now()
            await self._save_vm_data(request.name, vm_info)
        
        logger.info(f"VM '{request.name}' created successfully")
        return vm_info

    async def list_vms(self) -> List[VMInfo]:
        await self._load_all_vm_data()
        return list(self.vms.values())

    async def get_vm(self, vm_name: str) -> Optional[VMInfo]:
        if vm_name not in self.vms:
            await self._load_vm_data(vm_name)
        return self.vms.get(vm_name)

    async def start_vm(self, vm_name: str) -> None:
        vm_info = await self.get_vm(vm_name)
        if not vm_info:
            raise ValueError(f"VM '{vm_name}' not found")
        
        if vm_info.state == VMState.RUNNING:
            raise ValueError(f"VM '{vm_name}' is already running")
        
        logger.info(f"Starting VM '{vm_name}'")
        
        # Load template configuration
        template = load_vm_template(vm_info.template)
        vm_config = template.copy()
        vm_config.update({
            "vcpus": vm_info.vcpus,
            "memory_mb": vm_info.memory_mb
        })
        
        # Apply OS-specific configurations
        if vm_info.os_type == OSType.WINDOWS:
            vm_config = self._apply_windows_config(vm_config, vm_name)
        elif vm_info.os_type == OSType.LINUX:
            vm_config = self._apply_linux_config(vm_config, vm_name)
        
        # Start VM via Cloud Hypervisor
        ch_client = CloudHypervisorClient(vm_name)
        try:
            await ch_client.start_hypervisor(vm_config)
            await ch_client.boot_vm()
            vm_info.state = VMState.RUNNING
        except Exception as e:
            vm_info.state = VMState.ERROR
            logger.error(f"Failed to start VM '{vm_name}': {e}")
            raise
        finally:
            vm_info.updated_at = datetime.now()
            await self._save_vm_data(vm_name, vm_info)
        
        logger.info(f"VM '{vm_name}' started successfully")

    async def stop_vm(self, vm_name: str) -> None:
        vm_info = await self.get_vm(vm_name)
        if not vm_info:
            raise ValueError(f"VM '{vm_name}' not found")
        
        if vm_info.state == VMState.STOPPED:
            raise ValueError(f"VM '{vm_name}' is already stopped")
        
        logger.info(f"Stopping VM '{vm_name}'")
        
        # Stop VM via Cloud Hypervisor
        ch_client = CloudHypervisorClient(vm_name)
        try:
            await ch_client.shutdown_vm()
            await ch_client.stop_hypervisor()
            vm_info.state = VMState.STOPPED
        except Exception as e:
            logger.error(f"Failed to stop VM '{vm_name}': {e}")
            vm_info.state = VMState.ERROR
            raise
        finally:
            vm_info.updated_at = datetime.now()
            await self._save_vm_data(vm_name, vm_info)
        
        logger.info(f"VM '{vm_name}' stopped successfully")

    async def delete_vm(self, vm_name: str) -> None:
        vm_info = await self.get_vm(vm_name)
        if not vm_info:
            raise ValueError(f"VM '{vm_name}' not found")
        
        if vm_info.state == VMState.RUNNING:
            await self.stop_vm(vm_name)
        
        logger.info(f"Deleting VM '{vm_name}'")
        
        # Clean up Cloud Hypervisor resources
        ch_client = CloudHypervisorClient(vm_name)
        try:
            await ch_client.stop_hypervisor()
        except Exception as e:
            logger.warning(f"Error stopping hypervisor during delete: {e}")
        
        # Remove from memory and disk
        del self.vms[vm_name]
        vm_data_file = self.vm_data_dir / f"{vm_name}.json"
        if vm_data_file.exists():
            vm_data_file.unlink()
        
        logger.info(f"VM '{vm_name}' deleted successfully")

    async def pause_vm(self, vm_name: str) -> None:
        vm_info = await self.get_vm(vm_name)
        if not vm_info:
            raise ValueError(f"VM '{vm_name}' not found")
        
        if vm_info.state != VMState.RUNNING:
            raise ValueError(f"VM '{vm_name}' must be running to pause")
        
        logger.info(f"Pausing VM '{vm_name}'")
        
        ch_client = CloudHypervisorClient(vm_name)
        try:
            await ch_client.pause_vm()
            vm_info.state = VMState.PAUSED
        except Exception as e:
            logger.error(f"Failed to pause VM '{vm_name}': {e}")
            raise
        finally:
            vm_info.updated_at = datetime.now()
            await self._save_vm_data(vm_name, vm_info)

    async def resume_vm(self, vm_name: str) -> None:
        vm_info = await self.get_vm(vm_name)
        if not vm_info:
            raise ValueError(f"VM '{vm_name}' not found")
        
        if vm_info.state != VMState.PAUSED:
            raise ValueError(f"VM '{vm_name}' must be paused to resume")
        
        logger.info(f"Resuming VM '{vm_name}'")
        
        ch_client = CloudHypervisorClient(vm_name)
        try:
            await ch_client.resume_vm()
            vm_info.state = VMState.RUNNING
        except Exception as e:
            logger.error(f"Failed to resume VM '{vm_name}': {e}")
            raise
        finally:
            vm_info.updated_at = datetime.now()
            await self._save_vm_data(vm_name, vm_info)

    async def get_vm_status(self, vm_name: str) -> Dict[str, Any]:
        vm_info = await self.get_vm(vm_name)
        if not vm_info:
            raise ValueError(f"VM '{vm_name}' not found")
        
        if vm_info.state == VMState.RUNNING:
            ch_client = CloudHypervisorClient(vm_name)
            try:
                ch_info = await ch_client.get_vm_info()
                counters = await ch_client.get_vm_counters()
                return {
                    "vm_info": vm_info.model_dump(),
                    "hypervisor_info": ch_info,
                    "counters": counters
                }
            except Exception as e:
                logger.warning(f"Failed to get hypervisor info for VM '{vm_name}': {e}")
        
        return {"vm_info": vm_info.model_dump()}

    async def _save_vm_data(self, vm_name: str, vm_info: VMInfo) -> None:
        vm_data_file = self.vm_data_dir / f"{vm_name}.json"
        await write_json_async(vm_data_file, vm_info.model_dump())

    async def _load_vm_data(self, vm_name: str) -> None:
        vm_data_file = self.vm_data_dir / f"{vm_name}.json"
        if vm_data_file.exists():
            data = await read_json_async(vm_data_file)
            self.vms[vm_name] = VMInfo(**data)

    async def _load_all_vm_data(self) -> None:
        if not self.vm_data_dir.exists():
            return
        
        for vm_file in self.vm_data_dir.glob("*.json"):
            vm_name = vm_file.stem
            if vm_name not in self.vms:
                await self._load_vm_data(vm_name)
    
    def _apply_windows_config(self, vm_config: Dict[str, Any], vm_name: str) -> Dict[str, Any]:
        """Apply Windows-specific VM configuration."""
        logger.debug(f"Applying Windows configuration for VM '{vm_name}'")
        
        # Ensure UEFI firmware is configured
        if "firmware" not in vm_config:
            vm_config["firmware"] = "images/windows/OVMF.fd"
        
        # Ensure VirtIO drivers are available
        if "cdrom" not in vm_config:
            vm_config["cdrom"] = "images/windows/virtio-win.iso"
        
        # Configure Windows-optimized performance settings
        if "performance" not in vm_config:
            vm_config["performance"] = {}
        
        vm_config["performance"].update({
            "cpu_topology": {
                "threads_per_core": 1,
                "cores_per_die": vm_config["vcpus"],
                "dies_per_socket": 1,
                "sockets": 1
            },
            "hugepages": False,
            "balloon": False
        })
        
        # Configure Windows-specific devices
        if "devices" not in vm_config:
            vm_config["devices"] = {}
        
        # Ensure VirtIO serial for guest agent
        vm_config["devices"]["serial"] = {
            "enabled": True,
            "mode": "pty"
        }
        
        # Add RNG device for Windows entropy
        vm_config["devices"]["rng"] = {
            "enabled": True,
            "source": "/dev/urandom"
        }
        
        # Configure network with static MAC for licensing
        if vm_config.get("network", {}).get("enabled", False):
            if "mac" not in vm_config["network"]:
                # Generate deterministic MAC based on VM name
                import hashlib
                mac_hash = hashlib.md5(vm_name.encode()).hexdigest()[:10]
                vm_config["network"]["mac"] = f"52:54:{mac_hash[:2]}:{mac_hash[2:4]}:{mac_hash[4:6]}:{mac_hash[6:8]}"
        
        return vm_config
    
    def _apply_linux_config(self, vm_config: Dict[str, Any], vm_name: str) -> Dict[str, Any]:
        """Apply Linux-specific VM configuration."""
        logger.debug(f"Applying Linux configuration for VM '{vm_name}'")
        
        # Ensure kernel and rootfs are configured
        if "kernel" not in vm_config:
            vm_config["kernel"] = "images/linux/vmlinux.bin"
        
        if "rootfs" not in vm_config:
            vm_config["rootfs"] = "images/linux/rootfs.ext4"
        
        # Configure optimized boot arguments for fast boot
        if "boot_args" not in vm_config:
            vm_config["boot_args"] = "console=ttyS0 reboot=k panic=1 pci=off nomodules 8250.nr_uarts=1"
        
        # Configure Linux-optimized performance settings
        if "performance" not in vm_config:
            vm_config["performance"] = {}
        
        vm_config["performance"].update({
            "hugepages": True,
            "balloon": True
        })
        
        # Configure security settings
        if "security" not in vm_config:
            vm_config["security"] = {}
        
        vm_config["security"].update({
            "seccomp": True,
            "iommu": True
        })
        
        return vm_config