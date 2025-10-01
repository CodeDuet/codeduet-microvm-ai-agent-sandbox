from pydantic import Field, BaseModel
from pydantic_settings import BaseSettings
from typing import Dict, Any, Optional
from pathlib import Path
import yaml
from functools import lru_cache


class ServerConfig(BaseSettings):
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=4, description="Number of workers")


class CloudHypervisorConfig(BaseSettings):
    binary_path: str = Field(default="/usr/local/bin/cloud-hypervisor", description="Cloud Hypervisor binary path")
    api_socket_dir: str = Field(default="/tmp/ch-sockets", description="API socket directory")


class NetworkingConfig(BaseSettings):
    bridge_name: str = Field(default="chbr0", description="Bridge name")
    subnet: str = Field(default="192.168.200.0/24", description="Subnet for VMs")
    port_range_start: int = Field(default=10000, description="Port range start")
    port_range_end: int = Field(default=20000, description="Port range end")


class OptimizationConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable optimization")
    cpu_underutilization_threshold: float = Field(default=10.0, description="CPU underutilization threshold")
    memory_underutilization_threshold: float = Field(default=20.0, description="Memory underutilization threshold")
    cpu_overutilization_threshold: float = Field(default=90.0, description="CPU overutilization threshold")
    memory_overutilization_threshold: float = Field(default=85.0, description="Memory overutilization threshold")
    resource_pressure_threshold: float = Field(default=80.0, description="Resource pressure threshold")
    recommendation_interval: int = Field(default=300, description="Recommendation interval in seconds")


class ScalingConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable scaling")
    auto_scale_critical: bool = Field(default=True, description="Auto-scale critical recommendations")
    auto_scale_high: bool = Field(default=False, description="Auto-scale high priority recommendations")
    scale_up_factor: float = Field(default=1.2, description="Scale up factor")
    scale_down_factor: float = Field(default=0.8, description="Scale down factor")
    min_vcpus: int = Field(default=1, description="Minimum vCPUs per VM")
    min_memory_mb: int = Field(default=512, description="Minimum memory per VM")


class ResourceMonitoringConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable monitoring")
    usage_history_size: int = Field(default=1000, description="Usage history size")
    update_interval: int = Field(default=60, description="Update interval in seconds")


class QuotaConfig(BaseModel):
    max_vcpus: int = Field(default=4, description="Maximum vCPUs")
    max_memory_mb: int = Field(default=2048, description="Maximum memory in MB")
    max_disk_gb: int = Field(default=20, description="Maximum disk in GB")
    max_vms: int = Field(default=5, description="Maximum VMs")
    priority: int = Field(default=1, description="Priority level")


class QuotasConfig(BaseModel):
    default: QuotaConfig = QuotaConfig()
    premium: QuotaConfig = QuotaConfig(
        max_vcpus=8,
        max_memory_mb=8192,
        max_disk_gb=100,
        max_vms=20,
        priority=5
    )


class ResourcesConfig(BaseSettings):
    max_vms: int = Field(default=50, description="Maximum number of VMs")
    max_memory_per_vm: int = Field(default=8192, description="Maximum memory per VM in MB")
    max_vcpus_per_vm: int = Field(default=8, description="Maximum vCPUs per VM")
    max_disk_per_vm: int = Field(default=100, description="Maximum disk per VM in GB")
    optimization: OptimizationConfig = OptimizationConfig()
    scaling: ScalingConfig = ScalingConfig()
    monitoring: ResourceMonitoringConfig = ResourceMonitoringConfig()
    quotas: QuotasConfig = QuotasConfig()


class AuthenticationConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable authentication")
    jwt_secret: str = Field(default="your-secret-key-change-in-production", description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    token_expire_minutes: int = Field(default=60, description="Token expiration in minutes")
    max_failed_attempts: int = Field(default=5, description="Max failed login attempts")
    lockout_duration_minutes: int = Field(default=30, description="Account lockout duration")
    require_strong_passwords: bool = Field(default=True, description="Require strong passwords")
    session_timeout_minutes: int = Field(default=60, description="Session timeout in minutes")
    enable_mfa: bool = Field(default=False, description="Enable multi-factor authentication")


class ApiSecurityConfig(BaseModel):
    require_api_key: bool = Field(default=True, description="Require API key")
    enable_rate_limiting: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests_per_minute: int = Field(default=100, description="Rate limit per minute")
    max_request_size_mb: int = Field(default=10, description="Max request size in MB")
    enable_cors: bool = Field(default=False, description="Enable CORS")
    allowed_origins: list = Field(default=[], description="Allowed CORS origins")
    require_https: bool = Field(default=False, description="Require HTTPS")


class FirewallConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable firewall")
    bridge_name: str = Field(default="chbr0", description="Bridge name")
    vm_network: str = Field(default="192.168.200.0/24", description="VM network")
    host_ip: str = Field(default="192.168.200.1", description="Host IP")
    default_drop_policy: bool = Field(default=True, description="Default drop policy")
    allow_ssh_from_management: bool = Field(default=True, description="Allow SSH from management")
    management_networks: list = Field(default=["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"], description="Management networks")


class IsolationConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable isolation")
    default_isolation_level: str = Field(default="moderate", description="Default isolation level")
    enable_vm_to_vm_communication: bool = Field(default=False, description="Enable VM-to-VM communication")
    enable_namespace_isolation: bool = Field(default=True, description="Enable namespace isolation")
    enable_cgroup_isolation: bool = Field(default=True, description="Enable cgroup isolation")
    seccomp_enabled: bool = Field(default=True, description="Enable seccomp")
    firewall: FirewallConfig = FirewallConfig()


class SecurityPoliciesConfig(BaseModel):
    max_concurrent_vms: int = Field(default=50, description="Max concurrent VMs")
    max_vm_memory_mb: int = Field(default=8192, description="Max VM memory MB")
    max_vm_vcpus: int = Field(default=8, description="Max VM vCPUs")
    require_authentication: bool = Field(default=True, description="Require authentication")
    session_timeout_minutes: int = Field(default=60, description="Session timeout minutes")
    enable_rate_limiting: bool = Field(default=True, description="Enable rate limiting")
    blocked_commands: list = Field(default=["rm -rf", "format", "del /q", "shutdown", "reboot", "halt", "mkfs", "fdisk", "dd if="], description="Blocked commands")
    allowed_networks: list = Field(default=["192.168.200.0/24", "10.0.0.0/8"], description="Allowed networks")


class ValidationConfig(BaseModel):
    enable_strict_validation: bool = Field(default=True, description="Enable strict validation")
    max_vm_name_length: int = Field(default=32, description="Max VM name length")
    max_snapshot_name_length: int = Field(default=64, description="Max snapshot name length")
    max_user_id_length: int = Field(default=256, description="Max user ID length")
    max_command_length: int = Field(default=1024, description="Max command length")
    allow_absolute_paths: bool = Field(default=False, description="Allow absolute paths")
    sanitize_commands: bool = Field(default=True, description="Sanitize commands")


class CredentialsConfig(BaseModel):
    encryption_enabled: bool = Field(default=True, description="Enable encryption")
    password_hash_rounds: int = Field(default=100000, description="Password hash rounds")
    api_key_length: int = Field(default=32, description="API key length")
    session_token_length: int = Field(default=32, description="Session token length")
    rotate_keys_days: int = Field(default=90, description="Key rotation days")


class ScanningConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable scanning")
    scan_interval_hours: int = Field(default=24, description="Scan interval hours")
    scan_on_vm_creation: bool = Field(default=True, description="Scan on VM creation")
    auto_remediate_critical: bool = Field(default=False, description="Auto remediate critical")
    scan_timeout_minutes: int = Field(default=30, description="Scan timeout minutes")
    vulnerability_db_update_hours: int = Field(default=6, description="Vulnerability DB update hours")


class SecurityConfig(BaseSettings):
    # Legacy fields for backward compatibility
    enable_authentication: bool = Field(default=True, description="Enable authentication")
    api_key_required: bool = Field(default=True, description="Require API key")
    vm_isolation: bool = Field(default=True, description="Enable VM isolation")
    
    # New security configuration
    authentication: AuthenticationConfig = Field(default_factory=AuthenticationConfig)
    api: ApiSecurityConfig = Field(default_factory=ApiSecurityConfig)
    isolation: IsolationConfig = Field(default_factory=IsolationConfig)
    policies: SecurityPoliciesConfig = Field(default_factory=SecurityPoliciesConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    credentials: CredentialsConfig = Field(default_factory=CredentialsConfig)
    scanning: ScanningConfig = Field(default_factory=ScanningConfig)
    
    model_config = {"extra": "allow"}


class EventsConfig(BaseModel):
    log_authentication: bool = Field(default=True, description="Log authentication")
    log_authorization: bool = Field(default=True, description="Log authorization")
    log_vm_operations: bool = Field(default=True, description="Log VM operations")
    log_resource_access: bool = Field(default=True, description="Log resource access")
    log_security_violations: bool = Field(default=True, description="Log security violations")
    log_configuration_changes: bool = Field(default=True, description="Log configuration changes")
    log_system_events: bool = Field(default=True, description="Log system events")
    log_command_execution: bool = Field(default=True, description="Log command execution")


class AlertingConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable alerting")
    security_violations_immediate: bool = Field(default=True, description="Immediate security violation alerts")
    failed_auth_threshold: int = Field(default=3, description="Failed auth threshold")
    suspicious_activity_patterns: bool = Field(default=True, description="Suspicious activity patterns")


class AuditConfig(BaseSettings):
    enabled: bool = Field(default=True, description="Enable audit")
    log_file: str = Field(default="/var/log/microvm/audit.log", description="Audit log file")
    retention_days: int = Field(default=2555, description="Retention days")
    enable_encryption: bool = Field(default=True, description="Enable encryption")
    buffer_size: int = Field(default=100, description="Buffer size")
    flush_interval_seconds: int = Field(default=30, description="Flush interval seconds")
    debug: bool = Field(default=False, description="Debug mode")
    compliance_frameworks: list = Field(default=["soc2", "iso27001"], description="Compliance frameworks")
    events: EventsConfig = Field(default_factory=EventsConfig)
    alerting: AlertingConfig = Field(default_factory=AlertingConfig)
    
    model_config = {"extra": "allow"}


class MonitoringConfig(BaseSettings):
    prometheus_port: int = Field(default=9090, description="Prometheus port")
    metrics_enabled: bool = Field(default=True, description="Enable metrics")
    log_level: str = Field(default="INFO", description="Log level")


class Settings(BaseSettings):
    server: ServerConfig = ServerConfig()
    cloud_hypervisor: CloudHypervisorConfig = CloudHypervisorConfig()
    networking: NetworkingConfig = NetworkingConfig()
    resources: ResourcesConfig = ResourcesConfig()
    security: SecurityConfig = SecurityConfig()
    audit: AuditConfig = AuditConfig()
    monitoring: MonitoringConfig = MonitoringConfig()

    model_config = {
        "env_file": ".env",
        "env_nested_delimiter": "__",
        "extra": "allow"  # Allow extra fields for flexible configuration
    }


@lru_cache()
def get_settings() -> Settings:
    config_path = Path("config/config.yaml")
    if config_path.exists():
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
        return Settings(**config_data)
    return Settings()


@lru_cache()
def get_config() -> Dict[str, Any]:
    """Get configuration as a dictionary for backward compatibility."""
    config_path = Path("config/config.yaml")
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return {
        "resources": {
            "max_vcpus_per_vm": 8,
            "max_memory_per_vm": 8192,
            "max_disk_per_vm": 100,
            "max_vms": 50
        }
    }


def load_vm_template(template_name: str) -> Dict[str, Any]:
    template_path = Path(f"config/vm-templates/{template_name}.yaml")
    if not template_path.exists():
        raise FileNotFoundError(f"VM template '{template_name}' not found")
    
    with open(template_path, "r") as f:
        template_data = yaml.safe_load(f)
    
    return template_data.get(template_name, {})


def load_network_config(network_name: str) -> Dict[str, Any]:
    network_path = Path(f"config/networks/{network_name}.yaml")
    if not network_path.exists():
        raise FileNotFoundError(f"Network config '{network_name}' not found")
    
    with open(network_path, "r") as f:
        network_data = yaml.safe_load(f)
    
    return network_data