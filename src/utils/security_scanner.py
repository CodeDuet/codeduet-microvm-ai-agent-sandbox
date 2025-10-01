"""
Security testing and vulnerability scanning utilities.
"""

import asyncio
import socket
import subprocess
import re
import json
import hashlib
import ssl
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
import logging

from .security import SecurityError, InputValidator

logger = logging.getLogger(__name__)


@dataclass
class SecurityVulnerability:
    """Represents a security vulnerability."""
    id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    title: str
    description: str
    affected_component: str
    cve_id: Optional[str] = None
    fix_recommendation: str = ""
    discovered_at: datetime = None
    
    def __post_init__(self):
        if self.discovered_at is None:
            self.discovered_at = datetime.utcnow()


@dataclass
class SecurityScanResult:
    """Security scan results."""
    scan_id: str
    scan_type: str
    target: str
    start_time: datetime
    end_time: datetime
    status: str  # COMPLETED, FAILED, IN_PROGRESS
    vulnerabilities: List[SecurityVulnerability]
    summary: Dict[str, Any]
    recommendations: List[str]


class NetworkScanner:
    """Network security scanner."""
    
    def __init__(self):
        """Initialize network scanner."""
        self.validator = InputValidator()
        self.common_ports = [
            22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 993, 995,
            1433, 1521, 3306, 3389, 5432, 5900, 8000, 8080, 8443
        ]
    
    async def scan_host(self, host: str, ports: List[int] = None) -> Dict[str, Any]:
        """Scan a host for open ports and services."""
        try:
            host = self.validator.validate_ip_address(host)
            ports_to_scan = ports or self.common_ports
            
            open_ports = []
            services = {}
            
            for port in ports_to_scan:
                if await self._is_port_open(host, port):
                    open_ports.append(port)
                    service = await self._identify_service(host, port)
                    if service:
                        services[port] = service
            
            return {
                'host': host,
                'open_ports': open_ports,
                'services': services,
                'scan_time': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Host scan failed for {host}: {e}")
            raise SecurityError(f"Host scan failed: {e}")
    
    async def _is_port_open(self, host: str, port: int, timeout: float = 1.0) -> bool:
        """Check if a port is open on a host."""
        try:
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return False
    
    async def _identify_service(self, host: str, port: int) -> Optional[str]:
        """Identify service running on a port."""
        try:
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=2.0)
            
            # Send a simple probe
            writer.write(b'GET / HTTP/1.0\r\n\r\n')
            await writer.drain()
            
            # Read response
            response = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            
            writer.close()
            await writer.wait_closed()
            
            # Analyze response
            response_str = response.decode('utf-8', errors='ignore')
            
            if 'HTTP/' in response_str:
                if 'Server:' in response_str:
                    server_match = re.search(r'Server:\s*([^\r\n]+)', response_str)
                    if server_match:
                        return f"HTTP - {server_match.group(1).strip()}"
                return "HTTP"
            elif 'SSH' in response_str:
                return "SSH"
            elif 'FTP' in response_str:
                return "FTP"
            
            return "Unknown"
            
        except Exception:
            return None
    
    async def scan_ssl_certificate(self, host: str, port: int = 443) -> Dict[str, Any]:
        """Scan SSL certificate for vulnerabilities."""
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with socket.create_connection((host, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
            
            # Analyze certificate
            issues = []
            
            # Check expiration
            not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            days_until_expiry = (not_after - datetime.utcnow()).days
            
            if days_until_expiry < 30:
                issues.append(f"Certificate expires in {days_until_expiry} days")
            
            # Check weak ciphers
            if cipher and cipher[1] < 128:
                issues.append(f"Weak cipher: {cipher[0]} ({cipher[1]} bits)")
            
            # Check SSL/TLS version
            if version in ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1']:
                issues.append(f"Outdated protocol: {version}")
            
            return {
                'host': host,
                'port': port,
                'certificate': {
                    'subject': dict(x[0] for x in cert['subject']),
                    'issuer': dict(x[0] for x in cert['issuer']),
                    'version': cert['version'],
                    'not_before': cert['notBefore'],
                    'not_after': cert['notAfter'],
                    'days_until_expiry': days_until_expiry
                },
                'cipher': cipher,
                'protocol_version': version,
                'issues': issues
            }
            
        except Exception as e:
            logger.error(f"SSL scan failed for {host}:{port}: {e}")
            return {'host': host, 'port': port, 'error': str(e)}


class VulnerabilityScanner:
    """Main vulnerability scanner."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize vulnerability scanner."""
        self.config = config
        self.network_scanner = NetworkScanner()
        self.scan_results: Dict[str, SecurityScanResult] = {}
        
    async def scan_system(self, scan_id: str) -> SecurityScanResult:
        """Perform comprehensive system security scan."""
        start_time = datetime.utcnow()
        vulnerabilities = []
        recommendations = []
        
        try:
            # 1. Check system configuration
            config_vulns = await self._scan_system_configuration()
            vulnerabilities.extend(config_vulns)
            
            # 2. Check network services
            network_vulns = await self._scan_network_services()
            vulnerabilities.extend(network_vulns)
            
            # 3. Check file permissions
            file_vulns = await self._scan_file_permissions()
            vulnerabilities.extend(file_vulns)
            
            # 4. Check for common vulnerabilities
            common_vulns = await self._scan_common_vulnerabilities()
            vulnerabilities.extend(common_vulns)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(vulnerabilities)
            
            # Create summary
            summary = self._create_scan_summary(vulnerabilities)
            
            result = SecurityScanResult(
                scan_id=scan_id,
                scan_type="SYSTEM_SCAN",
                target="localhost",
                start_time=start_time,
                end_time=datetime.utcnow(),
                status="COMPLETED",
                vulnerabilities=vulnerabilities,
                summary=summary,
                recommendations=recommendations
            )
            
            self.scan_results[scan_id] = result
            return result
            
        except Exception as e:
            logger.error(f"System scan failed: {e}")
            
            result = SecurityScanResult(
                scan_id=scan_id,
                scan_type="SYSTEM_SCAN",
                target="localhost",
                start_time=start_time,
                end_time=datetime.utcnow(),
                status="FAILED",
                vulnerabilities=[],
                summary={'error': str(e)},
                recommendations=[]
            )
            
            self.scan_results[scan_id] = result
            return result
    
    async def scan_vm(self, scan_id: str, vm_name: str, vm_ip: str) -> SecurityScanResult:
        """Perform security scan on a specific VM."""
        start_time = datetime.utcnow()
        vulnerabilities = []
        recommendations = []
        
        try:
            # Network scan
            network_result = await self.network_scanner.scan_host(vm_ip)
            
            # Check for vulnerable services
            for port, service in network_result.get('services', {}).items():
                if await self._is_vulnerable_service(service, port):
                    vuln = SecurityVulnerability(
                        id=f"VM_SERVICE_{vm_name}_{port}",
                        severity="MEDIUM",
                        title=f"Potentially vulnerable service on port {port}",
                        description=f"Service {service} on port {port} may have known vulnerabilities",
                        affected_component=f"VM {vm_name}",
                        fix_recommendation=f"Update service {service} or restrict access to port {port}"
                    )
                    vulnerabilities.append(vuln)
            
            # Check SSL certificates for HTTPS services
            if 443 in network_result.get('open_ports', []):
                ssl_result = await self.network_scanner.scan_ssl_certificate(vm_ip, 443)
                if ssl_result.get('issues'):
                    for issue in ssl_result['issues']:
                        vuln = SecurityVulnerability(
                            id=f"VM_SSL_{vm_name}",
                            severity="MEDIUM",
                            title=f"SSL/TLS issue on VM {vm_name}",
                            description=issue,
                            affected_component=f"VM {vm_name} HTTPS service",
                            fix_recommendation="Update SSL certificate and configuration"
                        )
                        vulnerabilities.append(vuln)
            
            # Generate recommendations
            recommendations = self._generate_vm_recommendations(vm_name, network_result)
            
            # Create summary
            summary = {
                'vm_name': vm_name,
                'vm_ip': vm_ip,
                'open_ports': network_result.get('open_ports', []),
                'services_count': len(network_result.get('services', {})),
                'vulnerabilities_by_severity': self._count_by_severity(vulnerabilities)
            }
            
            result = SecurityScanResult(
                scan_id=scan_id,
                scan_type="VM_SCAN",
                target=vm_name,
                start_time=start_time,
                end_time=datetime.utcnow(),
                status="COMPLETED",
                vulnerabilities=vulnerabilities,
                summary=summary,
                recommendations=recommendations
            )
            
            self.scan_results[scan_id] = result
            return result
            
        except Exception as e:
            logger.error(f"VM scan failed for {vm_name}: {e}")
            
            result = SecurityScanResult(
                scan_id=scan_id,
                scan_type="VM_SCAN",
                target=vm_name,
                start_time=start_time,
                end_time=datetime.utcnow(),
                status="FAILED",
                vulnerabilities=[],
                summary={'error': str(e)},
                recommendations=[]
            )
            
            self.scan_results[scan_id] = result
            return result
    
    async def _scan_system_configuration(self) -> List[SecurityVulnerability]:
        """Scan system configuration for security issues."""
        vulnerabilities = []
        
        try:
            # Check for default credentials
            if await self._check_default_credentials():
                vuln = SecurityVulnerability(
                    id="SYS_DEFAULT_CREDS",
                    severity="CRITICAL",
                    title="Default credentials detected",
                    description="System is using default or weak credentials",
                    affected_component="Authentication system",
                    fix_recommendation="Change all default passwords and use strong authentication"
                )
                vulnerabilities.append(vuln)
            
            # Check firewall status
            if not await self._check_firewall_enabled():
                vuln = SecurityVulnerability(
                    id="SYS_NO_FIREWALL",
                    severity="HIGH",
                    title="Firewall not enabled",
                    description="System firewall is not properly configured",
                    affected_component="Network security",
                    fix_recommendation="Enable and configure firewall rules"
                )
                vulnerabilities.append(vuln)
            
            # Check for unencrypted data
            if await self._check_unencrypted_data():
                vuln = SecurityVulnerability(
                    id="SYS_UNENCRYPTED_DATA",
                    severity="MEDIUM",
                    title="Unencrypted sensitive data found",
                    description="Sensitive data is stored without encryption",
                    affected_component="Data storage",
                    fix_recommendation="Implement encryption for sensitive data"
                )
                vulnerabilities.append(vuln)
            
        except Exception as e:
            logger.error(f"System configuration scan failed: {e}")
        
        return vulnerabilities
    
    async def _scan_network_services(self) -> List[SecurityVulnerability]:
        """Scan network services for vulnerabilities."""
        vulnerabilities = []
        
        try:
            # Scan localhost
            network_result = await self.network_scanner.scan_host('127.0.0.1')
            
            # Check for unnecessary services
            unnecessary_ports = [23, 135, 139, 445]  # Telnet, RPC, NetBIOS
            for port in network_result.get('open_ports', []):
                if port in unnecessary_ports:
                    vuln = SecurityVulnerability(
                        id=f"NET_UNNECESSARY_{port}",
                        severity="MEDIUM",
                        title=f"Unnecessary service on port {port}",
                        description=f"Potentially unnecessary service running on port {port}",
                        affected_component="Network services",
                        fix_recommendation=f"Disable service on port {port} if not needed"
                    )
                    vulnerabilities.append(vuln)
            
        except Exception as e:
            logger.error(f"Network services scan failed: {e}")
        
        return vulnerabilities
    
    async def _scan_file_permissions(self) -> List[SecurityVulnerability]:
        """Scan file system permissions."""
        vulnerabilities = []
        
        try:
            # Check for world-writable files in critical directories
            critical_dirs = ['/etc', '/bin', '/sbin', '/usr/bin', '/usr/sbin']
            
            for directory in critical_dirs:
                if Path(directory).exists():
                    result = await self._check_directory_permissions(directory)
                    if result:
                        vuln = SecurityVulnerability(
                            id=f"FILE_PERMS_{directory.replace('/', '_')}",
                            severity="HIGH",
                            title=f"Insecure permissions in {directory}",
                            description=result,
                            affected_component="File system",
                            fix_recommendation=f"Fix file permissions in {directory}"
                        )
                        vulnerabilities.append(vuln)
            
        except Exception as e:
            logger.error(f"File permissions scan failed: {e}")
        
        return vulnerabilities
    
    async def _scan_common_vulnerabilities(self) -> List[SecurityVulnerability]:
        """Scan for common vulnerabilities."""
        vulnerabilities = []
        
        # Check for known vulnerable software versions
        # This is a simplified check - in production, use CVE databases
        vulnerable_patterns = {
            'apache': ['2.2.0', '2.2.15'],
            'nginx': ['1.0.0', '1.2.0'],
            'openssh': ['6.0', '6.6']
        }
        
        for software, versions in vulnerable_patterns.items():
            if await self._check_software_version(software, versions):
                vuln = SecurityVulnerability(
                    id=f"CVE_{software.upper()}",
                    severity="HIGH",
                    title=f"Vulnerable {software} version detected",
                    description=f"Installed {software} version has known vulnerabilities",
                    affected_component=software,
                    fix_recommendation=f"Update {software} to the latest version"
                )
                vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    async def _is_vulnerable_service(self, service: str, port: int) -> bool:
        """Check if a service is potentially vulnerable."""
        # Simplified vulnerability check
        vulnerable_services = {
            'FTP': True,  # Often misconfigured
            'Telnet': True,  # Unencrypted
            'HTTP': port != 443,  # HTTP on non-HTTPS ports
        }
        
        for vuln_service, is_vuln in vulnerable_services.items():
            if vuln_service.lower() in service.lower():
                return is_vuln
        
        return False
    
    async def _check_default_credentials(self) -> bool:
        """Check for default credentials."""
        # Placeholder - would check against common default credential databases
        return False
    
    async def _check_firewall_enabled(self) -> bool:
        """Check if firewall is enabled."""
        try:
            result = await asyncio.create_subprocess_exec(
                'iptables', '-L',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            # If iptables runs and returns rules, firewall is likely configured
            return result.returncode == 0 and len(stdout) > 100
            
        except Exception:
            return False
    
    async def _check_unencrypted_data(self) -> bool:
        """Check for unencrypted sensitive data."""
        # Placeholder - would scan for unencrypted files containing sensitive data
        return False
    
    async def _check_directory_permissions(self, directory: str) -> Optional[str]:
        """Check directory permissions for security issues."""
        # Placeholder - would check file permissions
        return None
    
    async def _check_software_version(self, software: str, vulnerable_versions: List[str]) -> bool:
        """Check if installed software version is vulnerable."""
        # Placeholder - would check installed software versions
        return False
    
    def _generate_recommendations(self, vulnerabilities: List[SecurityVulnerability]) -> List[str]:
        """Generate security recommendations based on vulnerabilities."""
        recommendations = []
        
        severity_counts = self._count_by_severity(vulnerabilities)
        
        if severity_counts.get('CRITICAL', 0) > 0:
            recommendations.append("URGENT: Address all critical vulnerabilities immediately")
        
        if severity_counts.get('HIGH', 0) > 0:
            recommendations.append("Address high-severity vulnerabilities as soon as possible")
        
        # Generic recommendations
        recommendations.extend([
            "Implement regular security scanning",
            "Keep all software updated",
            "Enable comprehensive logging",
            "Implement network segmentation",
            "Use strong authentication mechanisms"
        ])
        
        return recommendations
    
    def _generate_vm_recommendations(self, vm_name: str, network_result: Dict) -> List[str]:
        """Generate VM-specific recommendations."""
        recommendations = []
        
        open_ports = network_result.get('open_ports', [])
        
        if len(open_ports) > 5:
            recommendations.append("Reduce number of exposed services")
        
        if 22 in open_ports:
            recommendations.append("Secure SSH configuration with key-based authentication")
        
        if 80 in open_ports and 443 not in open_ports:
            recommendations.append("Enable HTTPS for web services")
        
        recommendations.extend([
            f"Implement firewall rules for VM {vm_name}",
            "Enable VM-level logging",
            "Regular security updates"
        ])
        
        return recommendations
    
    def _count_by_severity(self, vulnerabilities: List[SecurityVulnerability]) -> Dict[str, int]:
        """Count vulnerabilities by severity."""
        counts = {}
        for vuln in vulnerabilities:
            counts[vuln.severity] = counts.get(vuln.severity, 0) + 1
        return counts
    
    def _create_scan_summary(self, vulnerabilities: List[SecurityVulnerability]) -> Dict[str, Any]:
        """Create scan summary."""
        severity_counts = self._count_by_severity(vulnerabilities)
        
        return {
            'total_vulnerabilities': len(vulnerabilities),
            'vulnerabilities_by_severity': severity_counts,
            'risk_score': self._calculate_risk_score(severity_counts),
            'scan_timestamp': datetime.utcnow().isoformat()
        }
    
    def _calculate_risk_score(self, severity_counts: Dict[str, int]) -> int:
        """Calculate overall risk score (0-100)."""
        weights = {'CRITICAL': 25, 'HIGH': 10, 'MEDIUM': 5, 'LOW': 1}
        
        score = 0
        for severity, count in severity_counts.items():
            score += weights.get(severity, 0) * count
        
        # Cap at 100
        return min(score, 100)
    
    def get_scan_result(self, scan_id: str) -> Optional[SecurityScanResult]:
        """Get scan result by ID."""
        return self.scan_results.get(scan_id)
    
    def list_scans(self) -> List[str]:
        """List all scan IDs."""
        return list(self.scan_results.keys())
    
    def cleanup_old_scans(self, max_age_days: int = 30):
        """Clean up old scan results."""
        cutoff_time = datetime.utcnow() - timedelta(days=max_age_days)
        
        to_remove = []
        for scan_id, result in self.scan_results.items():
            if result.end_time < cutoff_time:
                to_remove.append(scan_id)
        
        for scan_id in to_remove:
            del self.scan_results[scan_id]
        
        logger.info(f"Cleaned up {len(to_remove)} old scan results")