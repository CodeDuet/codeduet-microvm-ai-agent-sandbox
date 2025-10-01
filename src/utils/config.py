from pydantic import Field
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


class ResourcesConfig(BaseSettings):
    max_vms: int = Field(default=50, description="Maximum number of VMs")
    max_memory_per_vm: int = Field(default=8192, description="Maximum memory per VM in MB")
    max_vcpus_per_vm: int = Field(default=8, description="Maximum vCPUs per VM")


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