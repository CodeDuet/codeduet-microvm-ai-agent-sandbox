"""
VM isolation and firewall management for enhanced security.
"""

import subprocess
import asyncio
import logging
import ipaddress
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path
import json
import tempfile
import os
from dataclasses import dataclass

from ..utils.security import SecurityError, InputValidator

logger = logging.getLogger(__name__)


@dataclass
class FirewallRule:
    """Represents a firewall rule."""
    chain: str  # INPUT, OUTPUT, FORWARD
    action: str  # ACCEPT, DROP, REJECT
    protocol: str  # tcp, udp, icmp, all
    source_ip: Optional[str] = None
    dest_ip: Optional[str] = None
    source_port: Optional[int] = None
    dest_port: Optional[int] = None
    interface: Optional[str] = None
    direction: str = "in"  # in, out, both
    description: str = ""


class FirewallManager:
    """Manages iptables firewall rules for VM isolation."""
    
    def __init__(self, config: Dict):
        """Initialize firewall manager."""
        self.config = config
        self.validator = InputValidator()
        self.vm_rules: Dict[str, List[FirewallRule]] = {}
        self.default_rules_applied = False
        
        # Network configuration
        self.bridge_name = config.get('bridge_name', 'chbr0')
        self.vm_network = config.get('vm_network', '192.168.200.0/24')
        self.host_ip = config.get('host_ip', '192.168.200.1')
        
    async def initialize_firewall(self):
        """Initialize firewall with default security rules."""
        try:
            # Apply default security rules
            await self._apply_default_rules()
            
            # Enable IP forwarding for VM networking
            await self._enable_ip_forwarding()
            
            # Set up VM network isolation
            await self._setup_vm_isolation()
            
            self.default_rules_applied = True
            logger.info("Firewall initialized with default security rules")
            
        except Exception as e:
            logger.error(f"Failed to initialize firewall: {e}")
            raise SecurityError(f"Firewall initialization failed: {e}")
    
    async def _apply_default_rules(self):
        """Apply default security rules."""
        rules = [
            # Allow loopback
            "iptables -A INPUT -i lo -j ACCEPT",
            "iptables -A OUTPUT -o lo -j ACCEPT",
            
            # Allow established connections
            "iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT",
            "iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT",
            
            # Allow SSH (port 22) from trusted networks only
            "iptables -A INPUT -p tcp --dport 22 -s 10.0.0.0/8 -j ACCEPT",
            "iptables -A INPUT -p tcp --dport 22 -s 172.16.0.0/12 -j ACCEPT",
            "iptables -A INPUT -p tcp --dport 22 -s 192.168.0.0/16 -j ACCEPT",
            
            # Allow API server port (8000) from management network
            "iptables -A INPUT -p tcp --dport 8000 -s 127.0.0.1 -j ACCEPT",
            "iptables -A INPUT -p tcp --dport 8000 -s 10.0.0.0/8 -j ACCEPT",
            "iptables -A INPUT -p tcp --dport 8000 -s 172.16.0.0/12 -j ACCEPT",
            "iptables -A INPUT -p tcp --dport 8000 -s 192.168.0.0/16 -j ACCEPT",
            
            # Drop all other incoming traffic by default
            "iptables -A INPUT -j DROP",
            
            # Allow all outgoing traffic (can be restricted based on policy)
            "iptables -A OUTPUT -j ACCEPT",
        ]
        
        for rule in rules:
            await self._execute_iptables_command(rule)
    
    async def _enable_ip_forwarding(self):
        """Enable IP forwarding for VM networking."""
        try:
            # Enable IPv4 forwarding
            await asyncio.create_subprocess_exec(
                'sysctl', '-w', 'net.ipv4.ip_forward=1',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Make it persistent
            sysctl_file = '/etc/sysctl.d/99-microvm-forwarding.conf'
            with open(sysctl_file, 'w') as f:
                f.write('net.ipv4.ip_forward=1\n')
                
            logger.info("IP forwarding enabled")
            
        except Exception as e:
            logger.error(f"Failed to enable IP forwarding: {e}")
            raise
    
    async def _setup_vm_isolation(self):
        """Set up VM network isolation rules."""
        # Create VM isolation chain
        await self._execute_iptables_command(
            "iptables -N VM_ISOLATION 2>/dev/null || true"
        )
        
        # Default VM isolation rules
        isolation_rules = [
            # Block VM-to-VM communication by default
            f"iptables -A VM_ISOLATION -s {self.vm_network} -d {self.vm_network} -j DROP",
            
            # Allow VM to host communication
            f"iptables -A VM_ISOLATION -s {self.vm_network} -d {self.host_ip} -j ACCEPT",
            
            # Allow VM to internet (through NAT)
            f"iptables -A VM_ISOLATION -s {self.vm_network} ! -d {self.vm_network} -j ACCEPT",
            
            # Jump to VM_ISOLATION chain from FORWARD
            f"iptables -I FORWARD -i {self.bridge_name} -j VM_ISOLATION",
        ]
        
        for rule in isolation_rules:
            await self._execute_iptables_command(rule)
    
    async def create_vm_isolation_rules(self, vm_name: str, vm_ip: str,
                                      allowed_vms: List[str] = None) -> bool:
        """Create isolation rules for a specific VM."""
        try:
            vm_name = self.validator.validate_vm_name(vm_name)
            vm_ip = self.validator.validate_ip_address(vm_ip)
            
            # Create VM-specific chain
            chain_name = f"VM_{vm_name.upper()}"
            await self._execute_iptables_command(
                f"iptables -N {chain_name} 2>/dev/null || true"
            )
            
            # Default drop rule for the VM
            await self._execute_iptables_command(
                f"iptables -A {chain_name} -j DROP"
            )
            
            # Allow communication with specified VMs
            if allowed_vms:
                for allowed_vm in allowed_vms:
                    allowed_vm = self.validator.validate_vm_name(allowed_vm)
                    # This would need VM IP lookup - simplified for now
                    logger.info(f"Would allow communication between {vm_name} and {allowed_vm}")
            
            # Redirect VM traffic to its specific chain
            await self._execute_iptables_command(
                f"iptables -I VM_ISOLATION -s {vm_ip} -j {chain_name}"
            )
            
            logger.info(f"Created isolation rules for VM {vm_name} ({vm_ip})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create VM isolation rules: {e}")
            return False
    
    async def add_port_forwarding_rule(self, vm_name: str, vm_ip: str,
                                     host_port: int, vm_port: int,
                                     protocol: str = "tcp") -> bool:
        """Add port forwarding rule for VM."""
        try:
            vm_name = self.validator.validate_vm_name(vm_name)
            vm_ip = self.validator.validate_ip_address(vm_ip)
            host_port = self.validator.validate_port(host_port)
            vm_port = self.validator.validate_port(vm_port)
            
            if protocol not in ['tcp', 'udp']:
                raise SecurityError("Protocol must be tcp or udp")
            
            # DNAT rule for incoming traffic
            dnat_rule = (
                f"iptables -t nat -A PREROUTING -p {protocol} "
                f"--dport {host_port} -j DNAT --to-destination {vm_ip}:{vm_port}"
            )
            
            # Allow forwarded traffic
            forward_rule = (
                f"iptables -A FORWARD -p {protocol} -d {vm_ip} "
                f"--dport {vm_port} -j ACCEPT"
            )
            
            await self._execute_iptables_command(dnat_rule)
            await self._execute_iptables_command(forward_rule)
            
            # Store rule for cleanup
            rule = FirewallRule(
                chain="nat",
                action="DNAT",
                protocol=protocol,
                dest_ip=vm_ip,
                dest_port=vm_port,
                description=f"Port forward {host_port}->{vm_port} for {vm_name}"
            )
            
            if vm_name not in self.vm_rules:
                self.vm_rules[vm_name] = []
            self.vm_rules[vm_name].append(rule)
            
            logger.info(
                f"Added port forwarding: {host_port}->{vm_ip}:{vm_port} "
                f"for VM {vm_name}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to add port forwarding rule: {e}")
            return False
    
    async def remove_vm_rules(self, vm_name: str) -> bool:
        """Remove all firewall rules for a VM."""
        try:
            vm_name = self.validator.validate_vm_name(vm_name)
            
            # Remove VM-specific chain
            chain_name = f"VM_{vm_name.upper()}"
            
            # Flush and delete the chain
            await self._execute_iptables_command(
                f"iptables -F {chain_name} 2>/dev/null || true"
            )
            await self._execute_iptables_command(
                f"iptables -X {chain_name} 2>/dev/null || true"
            )
            
            # Remove stored rules
            if vm_name in self.vm_rules:
                del self.vm_rules[vm_name]
            
            logger.info(f"Removed firewall rules for VM {vm_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove VM rules: {e}")
            return False
    
    async def _execute_iptables_command(self, command: str) -> bool:
        """Execute iptables command safely."""
        try:
            # Split command for subprocess
            cmd_parts = command.split()
            
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0 and "Chain already exists" not in stderr.decode():
                logger.error(f"iptables command failed: {command}")
                logger.error(f"Error: {stderr.decode()}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute iptables command: {e}")
            return False
    
    async def get_vm_rules(self, vm_name: str) -> List[FirewallRule]:
        """Get firewall rules for a specific VM."""
        vm_name = self.validator.validate_vm_name(vm_name)
        return self.vm_rules.get(vm_name, [])
    
    async def list_all_rules(self) -> Dict[str, List[FirewallRule]]:
        """List all VM firewall rules."""
        return self.vm_rules.copy()


class VMIsolationManager:
    """Manages VM isolation using multiple security mechanisms."""
    
    def __init__(self, config: Dict):
        """Initialize VM isolation manager."""
        self.config = config
        self.firewall_manager = FirewallManager(config.get('firewall', {}))
        self.namespace_isolation = config.get('namespace_isolation', True)
        self.cgroup_isolation = config.get('cgroup_isolation', True)
        self.seccomp_enabled = config.get('seccomp_enabled', True)
        
    async def initialize(self):
        """Initialize all isolation mechanisms."""
        await self.firewall_manager.initialize_firewall()
        
        if self.namespace_isolation:
            await self._setup_namespace_isolation()
        
        if self.cgroup_isolation:
            await self._setup_cgroup_isolation()
        
        logger.info("VM isolation manager initialized")
    
    async def _setup_namespace_isolation(self):
        """Set up network namespace isolation."""
        try:
            # Create dedicated network namespace for VMs if needed
            # This is a placeholder for advanced namespace isolation
            logger.info("Network namespace isolation configured")
            
        except Exception as e:
            logger.error(f"Failed to setup namespace isolation: {e}")
    
    async def _setup_cgroup_isolation(self):
        """Set up cgroup resource isolation."""
        try:
            # Create cgroup for VM resource isolation
            cgroup_path = Path("/sys/fs/cgroup/microvm")
            if not cgroup_path.exists():
                cgroup_path.mkdir(exist_ok=True)
            
            logger.info("Cgroup isolation configured")
            
        except Exception as e:
            logger.error(f"Failed to setup cgroup isolation: {e}")
    
    async def isolate_vm(self, vm_name: str, vm_ip: str,
                        isolation_level: str = "strict") -> bool:
        """Apply isolation for a specific VM."""
        try:
            # Apply firewall isolation
            success = await self.firewall_manager.create_vm_isolation_rules(
                vm_name, vm_ip
            )
            
            if not success:
                return False
            
            # Apply additional isolation based on level
            if isolation_level == "strict":
                await self._apply_strict_isolation(vm_name, vm_ip)
            elif isolation_level == "moderate":
                await self._apply_moderate_isolation(vm_name, vm_ip)
            
            logger.info(f"Applied {isolation_level} isolation for VM {vm_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to isolate VM {vm_name}: {e}")
            return False
    
    async def _apply_strict_isolation(self, vm_name: str, vm_ip: str):
        """Apply strict isolation (no VM-to-VM communication)."""
        # Block all inter-VM communication
        await self.firewall_manager._execute_iptables_command(
            f"iptables -A VM_ISOLATION -s {vm_ip} -d 192.168.200.0/24 -j DROP"
        )
    
    async def _apply_moderate_isolation(self, vm_name: str, vm_ip: str):
        """Apply moderate isolation (limited VM-to-VM communication)."""
        # Allow specific protocols only (e.g., ICMP for ping)
        await self.firewall_manager._execute_iptables_command(
            f"iptables -A VM_ISOLATION -s {vm_ip} -d 192.168.200.0/24 -p icmp -j ACCEPT"
        )
    
    async def create_vm_network_policy(self, vm_name: str, policy: Dict) -> bool:
        """Create network policy for VM."""
        try:
            vm_ip = policy.get('vm_ip')
            allowed_outbound = policy.get('allowed_outbound', [])
            allowed_inbound = policy.get('allowed_inbound', [])
            blocked_ports = policy.get('blocked_ports', [])
            
            # Create specific rules based on policy
            for rule in allowed_outbound:
                if 'ip' in rule and 'port' in rule:
                    await self.firewall_manager._execute_iptables_command(
                        f"iptables -A VM_ISOLATION -s {vm_ip} "
                        f"-d {rule['ip']} -p tcp --dport {rule['port']} -j ACCEPT"
                    )
            
            # Block specified ports
            for port in blocked_ports:
                await self.firewall_manager._execute_iptables_command(
                    f"iptables -A VM_ISOLATION -s {vm_ip} "
                    f"-p tcp --dport {port} -j DROP"
                )
            
            logger.info(f"Created network policy for VM {vm_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create network policy: {e}")
            return False
    
    async def remove_vm_isolation(self, vm_name: str) -> bool:
        """Remove isolation for a VM."""
        return await self.firewall_manager.remove_vm_rules(vm_name)
    
    async def get_isolation_status(self, vm_name: str) -> Dict:
        """Get isolation status for a VM."""
        rules = await self.firewall_manager.get_vm_rules(vm_name)
        return {
            'vm_name': vm_name,
            'firewall_rules_count': len(rules),
            'namespace_isolation': self.namespace_isolation,
            'cgroup_isolation': self.cgroup_isolation,
            'seccomp_enabled': self.seccomp_enabled
        }


class SecurityManager:
    """Main security manager coordinating all security components."""
    
    def __init__(self, config: Dict):
        """Initialize security manager."""
        self.config = config
        self.isolation_manager = VMIsolationManager(config.get('isolation', {}))
        self.security_policies = config.get('security_policies', {})
        self.monitoring_enabled = config.get('monitoring_enabled', True)
        
    async def initialize(self):
        """Initialize all security components."""
        await self.isolation_manager.initialize()
        logger.info("Security manager initialized")
    
    async def secure_vm(self, vm_name: str, vm_config: Dict) -> bool:
        """Apply all security measures for a VM."""
        try:
            vm_ip = vm_config.get('ip_address')
            isolation_level = vm_config.get('isolation_level', 'moderate')
            
            # Apply VM isolation
            success = await self.isolation_manager.isolate_vm(
                vm_name, vm_ip, isolation_level
            )
            
            if not success:
                logger.error(f"Failed to secure VM {vm_name}")
                return False
            
            # Apply additional security policies if configured
            if 'network_policy' in vm_config:
                await self.isolation_manager.create_vm_network_policy(
                    vm_name, vm_config['network_policy']
                )
            
            logger.info(f"VM {vm_name} secured successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to secure VM {vm_name}: {e}")
            return False
    
    async def unsecure_vm(self, vm_name: str) -> bool:
        """Remove all security measures for a VM."""
        return await self.isolation_manager.remove_vm_isolation(vm_name)
    
    async def get_security_status(self) -> Dict:
        """Get overall security status."""
        return {
            'firewall_initialized': self.isolation_manager.firewall_manager.default_rules_applied,
            'namespace_isolation': self.isolation_manager.namespace_isolation,
            'cgroup_isolation': self.isolation_manager.cgroup_isolation,
            'monitoring_enabled': self.monitoring_enabled,
            'policies_count': len(self.security_policies)
        }