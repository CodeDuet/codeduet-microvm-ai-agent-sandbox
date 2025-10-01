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


class SecurityConfig(BaseSettings):
    enable_authentication: bool = Field(default=True, description="Enable authentication")
    api_key_required: bool = Field(default=True, description="Require API key")
    vm_isolation: bool = Field(default=True, description="Enable VM isolation")


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
    monitoring: MonitoringConfig = MonitoringConfig()

    model_config = {
        "env_file": ".env",
        "env_nested_delimiter": "__"
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