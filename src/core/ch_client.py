import asyncio
import json
import httpx
from pathlib import Path
from typing import Dict, Any, Optional
import subprocess

from src.utils.config import get_settings
from src.utils.helpers import run_subprocess
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CloudHypervisorClient:
    def __init__(self, vm_name: str):
        self.vm_name = vm_name
        self.settings = get_settings()
        self.api_socket_path = Path(self.settings.cloud_hypervisor.api_socket_dir) / f"{vm_name}.sock"
        self.api_socket_path.parent.mkdir(parents=True, exist_ok=True)
        self.process: Optional[subprocess.Popen] = None
        self.http_client: Optional[httpx.AsyncClient] = None

    async def start_hypervisor(self, vm_config: Dict[str, Any]) -> None:
        if self.process and self.process.poll() is None:
            logger.warning(f"Cloud Hypervisor already running for VM '{self.vm_name}'")
            return

        logger.info(f"Starting Cloud Hypervisor for VM '{self.vm_name}'")
        
        cmd = [
            self.settings.cloud_hypervisor.binary_path,
            "--api-socket", str(self.api_socket_path),
            "--memory", f"size={vm_config['memory_mb']}M",
            "--cpus", f"boot={vm_config['vcpus']}",
        ]
        
        # Add kernel and rootfs for Linux VMs
        if "kernel" in vm_config:
            cmd.extend(["--kernel", vm_config["kernel"]])
        if "rootfs" in vm_config:
            cmd.extend(["--disk", f"path={vm_config['rootfs']}"])
        if "boot_args" in vm_config:
            cmd.extend(["--cmdline", vm_config["boot_args"]])
        
        # Add firmware for Windows VMs (UEFI support)
        if "firmware" in vm_config:
            cmd.extend(["--firmware", vm_config["firmware"]])
        if "disk" in vm_config:
            disk_params = f"path={vm_config['disk']}"
            if vm_config.get("disk_format"):
                disk_params += f",format={vm_config['disk_format']}"
            cmd.extend(["--disk", disk_params])
        if "cdrom" in vm_config:
            cmd.extend(["--disk", f"path={vm_config['cdrom']},readonly=on"])

        logger.debug(f"Cloud Hypervisor command: {' '.join(cmd)}")
        
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait for API socket to be available
        await self._wait_for_api_socket()
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(uds=str(self.api_socket_path))
        )
        
        logger.info(f"Cloud Hypervisor started for VM '{self.vm_name}'")

    async def create_vm(self, vm_config: Dict[str, Any]) -> Dict[str, Any]:
        if not self.http_client:
            await self.start_hypervisor(vm_config)
        
        # Configure VM via REST API
        vm_api_config = self._build_vm_config(vm_config)
        
        response = await self.http_client.put("/api/v1/vm.create", json=vm_api_config)
        response.raise_for_status()
        
        logger.info(f"VM '{self.vm_name}' created via Cloud Hypervisor API")
        return response.json()

    async def boot_vm(self) -> Dict[str, Any]:
        if not self.http_client:
            raise RuntimeError("Cloud Hypervisor not started")
        
        response = await self.http_client.put("/api/v1/vm.boot")
        response.raise_for_status()
        
        logger.info(f"VM '{self.vm_name}' booted")
        return response.json()

    async def shutdown_vm(self) -> Dict[str, Any]:
        if not self.http_client:
            raise RuntimeError("Cloud Hypervisor not started")
        
        response = await self.http_client.put("/api/v1/vm.shutdown")
        response.raise_for_status()
        
        logger.info(f"VM '{self.vm_name}' shutdown")
        return response.json()

    async def snapshot_vm(self, snapshot_path: str) -> Dict[str, Any]:
        if not self.http_client:
            raise RuntimeError("Cloud Hypervisor not started")
        
        snapshot_config = {
            "destination_url": f"file://{snapshot_path}"
        }
        
        response = await self.http_client.put("/api/v1/vm.snapshot", json=snapshot_config)
        response.raise_for_status()
        
        logger.info(f"VM '{self.vm_name}' snapshot created at '{snapshot_path}'")
        return response.json()

    async def restore_vm(self, snapshot_path: str) -> Dict[str, Any]:
        if not self.http_client:
            raise RuntimeError("Cloud Hypervisor not started")
        
        restore_config = {
            "source_url": f"file://{snapshot_path}"
        }
        
        response = await self.http_client.put("/api/v1/vm.restore", json=restore_config)
        response.raise_for_status()
        
        logger.info(f"VM '{self.vm_name}' restored from '{snapshot_path}'")
        return response.json()

    async def get_vm_info(self) -> Dict[str, Any]:
        if not self.http_client:
            raise RuntimeError("Cloud Hypervisor not started")
        
        response = await self.http_client.get("/api/v1/vm.info")
        response.raise_for_status()
        
        return response.json()

    async def pause_vm(self) -> Dict[str, Any]:
        if not self.http_client:
            raise RuntimeError("Cloud Hypervisor not started")
        
        response = await self.http_client.put("/api/v1/vm.pause")
        response.raise_for_status()
        
        logger.info(f"VM '{self.vm_name}' paused")
        return response.json()

    async def resume_vm(self) -> Dict[str, Any]:
        if not self.http_client:
            raise RuntimeError("Cloud Hypervisor not started")
        
        response = await self.http_client.put("/api/v1/vm.resume")
        response.raise_for_status()
        
        logger.info(f"VM '{self.vm_name}' resumed")
        return response.json()

    async def resize_vm(self, new_vcpus: Optional[int] = None, new_memory_mb: Optional[int] = None) -> Dict[str, Any]:
        if not self.http_client:
            raise RuntimeError("Cloud Hypervisor not started")
        
        resize_config = {}
        if new_vcpus:
            resize_config["desired_vcpus"] = new_vcpus
        if new_memory_mb:
            resize_config["desired_ram"] = new_memory_mb * 1024 * 1024
        
        if not resize_config:
            raise ValueError("Must specify either new_vcpus or new_memory_mb")
        
        response = await self.http_client.put("/api/v1/vm.resize", json=resize_config)
        response.raise_for_status()
        
        logger.info(f"VM '{self.vm_name}' resized: {resize_config}")
        return response.json()

    async def get_vm_counters(self) -> Dict[str, Any]:
        if not self.http_client:
            raise RuntimeError("Cloud Hypervisor not started")
        
        response = await self.http_client.get("/api/v1/vm.counters")
        response.raise_for_status()
        
        return response.json()

    async def stop_hypervisor(self) -> None:
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
        
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=10)
            except asyncio.TimeoutError:
                logger.warning(f"Force killing Cloud Hypervisor for VM '{self.vm_name}'")
                self.process.kill()
                await self.process.wait()
        
        if self.api_socket_path.exists():
            self.api_socket_path.unlink()
        
        logger.info(f"Cloud Hypervisor stopped for VM '{self.vm_name}'")

    def _build_vm_config(self, vm_config: Dict[str, Any]) -> Dict[str, Any]:
        config = {
            "cpus": {
                "boot_vcpus": vm_config["vcpus"], 
                "max_vcpus": vm_config.get("resource_limits", {}).get("max_vcpus", vm_config["vcpus"])
            },
            "memory": {
                "size": vm_config["memory_mb"] * 1024 * 1024,
                "mergeable": False,
                "hotplug_method": "virtio-mem"
            },
        }
        
        # Add CPU topology if specified
        if "performance" in vm_config and "cpu_topology" in vm_config["performance"]:
            topology = vm_config["performance"]["cpu_topology"]
            config["cpus"]["topology"] = {
                "threads_per_core": topology.get("threads_per_core", 1),
                "cores_per_die": topology.get("cores_per_die", vm_config["vcpus"]),
                "dies_per_socket": topology.get("dies_per_socket", 1),
                "sockets": topology.get("sockets", 1)
            }
        
        # Add disks with enhanced configuration
        disks = []
        if "devices" in vm_config and "block" in vm_config["devices"]:
            for block_device in vm_config["devices"]["block"]:
                disk_config = {"path": block_device["path"]}
                if block_device.get("read_only", False):
                    disk_config["readonly"] = True
                if block_device.get("direct", False):
                    disk_config["direct"] = True
                if "rate_limiter" in block_device:
                    disk_config["rate_limiter"] = block_device["rate_limiter"]
                disks.append(disk_config)
        elif "rootfs" in vm_config:
            disks.append({"path": vm_config["rootfs"]})
        
        # Windows main disk (UEFI bootable)
        if "disk" in vm_config:
            disk_config = {"path": vm_config["disk"]}
            if vm_config.get("disk_format"):
                disk_config["format"] = vm_config["disk_format"]
            # Enable VirtIO for Windows with proper driver support
            if "firmware" in vm_config:  # Windows VM with UEFI
                disk_config["vhost_user"] = False
                disk_config["poll_queue"] = True
            disks.append(disk_config)
        
        # Windows VirtIO drivers CD-ROM
        if "cdrom" in vm_config:
            disks.append({
                "path": vm_config["cdrom"],
                "readonly": True
            })
        
        if disks:
            config["disks"] = disks
        
        # Add firmware configuration for Windows (UEFI)
        if "firmware" in vm_config:
            config["firmware"] = vm_config["firmware"]
        
        # Add boot configuration
        if "kernel" in vm_config:
            config["kernel"] = {"path": vm_config["kernel"]}
            if "boot_args" in vm_config:
                config["kernel"]["cmdline"] = vm_config["boot_args"]
        
        # Add network configuration
        if vm_config.get("network", {}).get("enabled", False):
            net_config = {"tap": f"tap-{self.vm_name}"}
            if "mac" in vm_config.get("network", {}):
                net_config["mac"] = vm_config["network"]["mac"]
            config["net"] = [net_config]
        
        # Add serial console
        if vm_config.get("devices", {}).get("serial", {}).get("enabled", False):
            serial_config = {"mode": "Pty"}
            if vm_config["devices"]["serial"].get("file"):
                serial_config = {"mode": "File", "file": vm_config["devices"]["serial"]["file"]}
            config["serial"] = serial_config
        
        # Add VSOCK for guest agent communication
        if vm_config.get("guest_agent", {}).get("enabled", False):
            config["vsock"] = {"cid": 3, "socket": f"/tmp/vsock-{self.vm_name}.sock"}
        
        # Add performance and security options
        if vm_config.get("performance", {}).get("hugepages", False):
            config["memory"]["hugepages"] = True
        
        if vm_config.get("security", {}).get("seccomp", False):
            config["seccomp"] = True
        
        return config

    async def _wait_for_api_socket(self, timeout: int = 30) -> None:
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if self.api_socket_path.exists():
                # Test socket connectivity
                try:
                    test_client = httpx.AsyncClient(
                        transport=httpx.AsyncHTTPTransport(uds=str(self.api_socket_path))
                    )
                    response = await test_client.get("/api/v1/vm.ping")
                    await test_client.aclose()
                    if response.status_code == 200:
                        return
                except:
                    pass
            await asyncio.sleep(0.1)
        
        raise TimeoutError(f"API socket not available after {timeout} seconds")