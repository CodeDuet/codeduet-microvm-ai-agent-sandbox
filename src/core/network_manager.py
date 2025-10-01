import subprocess
import ipaddress
from typing import Dict, List, Optional
from pathlib import Path

from src.utils.config import get_settings
from src.utils.helpers import run_subprocess
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NetworkManager:
    def __init__(self):
        self.settings = get_settings()
        self.bridge_name = self.settings.networking.bridge_name
        self.subnet = ipaddress.IPv4Network(self.settings.networking.subnet)
        self.allocated_ips: Dict[str, str] = {}
        self.allocated_ports: Dict[str, int] = {}
        self.port_counter = self.settings.networking.port_range_start

    async def setup_bridge_network(self) -> None:
        logger.info(f"Setting up bridge network '{self.bridge_name}'")
        
        # Check if bridge already exists
        result = await run_subprocess(["ip", "link", "show", self.bridge_name], check=False)
        if result.returncode == 0:
            logger.info(f"Bridge '{self.bridge_name}' already exists")
            return
        
        # Create bridge
        await run_subprocess(["ip", "link", "add", "name", self.bridge_name, "type", "bridge"])
        
        # Set bridge IP address (first IP in subnet)
        bridge_ip = str(list(self.subnet.hosts())[0])
        await run_subprocess(["ip", "addr", "add", f"{bridge_ip}/{self.subnet.prefixlen}", "dev", self.bridge_name])
        
        # Bring bridge up
        await run_subprocess(["ip", "link", "set", "dev", self.bridge_name, "up"])
        
        # Enable IP forwarding
        await run_subprocess(["sysctl", "-w", "net.ipv4.ip_forward=1"])
        
        # Setup iptables rules for NAT
        await self._setup_nat_rules()
        
        logger.info(f"Bridge network '{self.bridge_name}' setup complete")

    async def teardown_bridge_network(self) -> None:
        logger.info(f"Tearing down bridge network '{self.bridge_name}'")
        
        # Remove iptables rules
        await self._cleanup_nat_rules()
        
        # Remove bridge
        result = await run_subprocess(["ip", "link", "show", self.bridge_name], check=False)
        if result.returncode == 0:
            await run_subprocess(["ip", "link", "set", "dev", self.bridge_name, "down"])
            await run_subprocess(["ip", "link", "delete", self.bridge_name])
        
        logger.info(f"Bridge network '{self.bridge_name}' torn down")

    async def create_tap_interface(self, vm_name: str) -> Dict[str, str]:
        tap_name = f"tap-{vm_name}"
        
        # Create TAP interface
        await run_subprocess(["ip", "tuntap", "add", "dev", tap_name, "mode", "tap"])
        
        # Attach to bridge
        await run_subprocess(["ip", "link", "set", "dev", tap_name, "master", self.bridge_name])
        
        # Bring up interface
        await run_subprocess(["ip", "link", "set", "dev", tap_name, "up"])
        
        # Allocate IP address
        vm_ip = await self._allocate_ip_address(vm_name)
        
        logger.info(f"Created TAP interface '{tap_name}' for VM '{vm_name}' with IP {vm_ip}")
        
        return {
            "tap_name": tap_name,
            "vm_ip": vm_ip,
            "bridge_name": self.bridge_name,
            "subnet": str(self.subnet)
        }

    async def delete_tap_interface(self, vm_name: str) -> None:
        tap_name = f"tap-{vm_name}"
        
        # Check if interface exists
        result = await run_subprocess(["ip", "link", "show", tap_name], check=False)
        if result.returncode != 0:
            logger.warning(f"TAP interface '{tap_name}' does not exist")
            return
        
        # Remove interface
        await run_subprocess(["ip", "link", "delete", tap_name])
        
        # Release IP address
        if vm_name in self.allocated_ips:
            del self.allocated_ips[vm_name]
        
        # Release ports
        ports_to_remove = [key for key in self.allocated_ports.keys() if key.startswith(f"{vm_name}:")]
        for port_key in ports_to_remove:
            del self.allocated_ports[port_key]
        
        logger.info(f"Deleted TAP interface '{tap_name}' for VM '{vm_name}'")

    async def allocate_port_forward(self, vm_name: str, guest_port: int) -> int:
        host_port = self._get_next_available_port()
        
        if vm_name not in self.allocated_ips:
            raise ValueError(f"VM '{vm_name}' does not have an allocated IP address")
        
        vm_ip = self.allocated_ips[vm_name]
        
        # Add iptables DNAT rule for port forwarding
        await run_subprocess([
            "iptables", "-t", "nat", "-A", "PREROUTING",
            "-p", "tcp", "--dport", str(host_port),
            "-j", "DNAT", "--to-destination", f"{vm_ip}:{guest_port}"
        ])
        
        # Add iptables rule to allow forwarded traffic
        await run_subprocess([
            "iptables", "-A", "FORWARD",
            "-p", "tcp", "-d", vm_ip, "--dport", str(guest_port),
            "-j", "ACCEPT"
        ])
        
        self.allocated_ports[f"{vm_name}:{guest_port}"] = host_port
        
        logger.info(f"Port forward: host:{host_port} -> {vm_name}:{guest_port}")
        return host_port

    async def remove_port_forward(self, vm_name: str, guest_port: int) -> None:
        port_key = f"{vm_name}:{guest_port}"
        if port_key not in self.allocated_ports:
            logger.warning(f"No port forward found for {port_key}")
            return
        
        host_port = self.allocated_ports[port_key]
        vm_ip = self.allocated_ips[vm_name]
        
        # Remove iptables rules
        await run_subprocess([
            "iptables", "-t", "nat", "-D", "PREROUTING",
            "-p", "tcp", "--dport", str(host_port),
            "-j", "DNAT", "--to-destination", f"{vm_ip}:{guest_port}"
        ], check=False)
        
        await run_subprocess([
            "iptables", "-D", "FORWARD",
            "-p", "tcp", "-d", vm_ip, "--dport", str(guest_port),
            "-j", "ACCEPT"
        ], check=False)
        
        del self.allocated_ports[port_key]
        
        logger.info(f"Removed port forward: host:{host_port} -> {vm_name}:{guest_port}")

    async def get_vm_network_info(self, vm_name: str) -> Optional[Dict[str, str]]:
        if vm_name not in self.allocated_ips:
            return None
        
        tap_name = f"tap-{vm_name}"
        vm_ip = self.allocated_ips[vm_name]
        
        # Get interface stats
        result = await run_subprocess(["cat", f"/sys/class/net/{tap_name}/statistics/rx_bytes"], check=False)
        rx_bytes = int(result.stdout.strip()) if result.returncode == 0 else 0
        
        result = await run_subprocess(["cat", f"/sys/class/net/{tap_name}/statistics/tx_bytes"], check=False)
        tx_bytes = int(result.stdout.strip()) if result.returncode == 0 else 0
        
        return {
            "tap_name": tap_name,
            "vm_ip": vm_ip,
            "bridge_name": self.bridge_name,
            "rx_bytes": str(rx_bytes),
            "tx_bytes": str(tx_bytes)
        }

    async def list_network_interfaces(self) -> List[Dict[str, str]]:
        interfaces = []
        for vm_name, ip in self.allocated_ips.items():
            info = await self.get_vm_network_info(vm_name)
            if info:
                interfaces.append(info)
        return interfaces

    async def _allocate_ip_address(self, vm_name: str) -> str:
        for ip in self.subnet.hosts():
            ip_str = str(ip)
            if ip_str not in self.allocated_ips.values():
                self.allocated_ips[vm_name] = ip_str
                return ip_str
        
        raise RuntimeError("No available IP addresses in subnet")

    def _get_next_available_port(self) -> int:
        while self.port_counter <= self.settings.networking.port_range_end:
            if self.port_counter not in self.allocated_ports.values():
                port = self.port_counter
                self.port_counter += 1
                return port
            self.port_counter += 1
        
        raise RuntimeError("No available ports in range")

    async def _setup_nat_rules(self) -> None:
        bridge_ip = str(list(self.subnet.hosts())[0])
        
        # Enable masquerading for bridge subnet
        await run_subprocess([
            "iptables", "-t", "nat", "-A", "POSTROUTING",
            "-s", str(self.subnet), "!", "-d", str(self.subnet),
            "-j", "MASQUERADE"
        ], check=False)
        
        # Allow forwarding for bridge
        await run_subprocess([
            "iptables", "-A", "FORWARD",
            "-i", self.bridge_name, "-j", "ACCEPT"
        ], check=False)
        
        await run_subprocess([
            "iptables", "-A", "FORWARD",
            "-o", self.bridge_name, "-j", "ACCEPT"
        ], check=False)

    async def _cleanup_nat_rules(self) -> None:
        # Remove masquerading rule
        await run_subprocess([
            "iptables", "-t", "nat", "-D", "POSTROUTING",
            "-s", str(self.subnet), "!", "-d", str(self.subnet),
            "-j", "MASQUERADE"
        ], check=False)
        
        # Remove forwarding rules
        await run_subprocess([
            "iptables", "-D", "FORWARD",
            "-i", self.bridge_name, "-j", "ACCEPT"
        ], check=False)
        
        await run_subprocess([
            "iptables", "-D", "FORWARD",
            "-o", self.bridge_name, "-j", "ACCEPT"
        ], check=False)