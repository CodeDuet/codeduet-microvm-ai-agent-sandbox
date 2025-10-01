import pytest
import tempfile
import yaml
from pathlib import Path

from src.utils.config import Settings, get_settings, load_vm_template, load_network_config


class TestSettings:
    def test_default_settings(self):
        settings = Settings()
        assert settings.server.host == "0.0.0.0"
        assert settings.server.port == 8000
        assert settings.cloud_hypervisor.binary_path == "/usr/local/bin/cloud-hypervisor"
        assert settings.networking.bridge_name == "chbr0"
        assert settings.resources.max_vms == 50
        assert settings.security.enable_authentication is True
        assert settings.monitoring.metrics_enabled is True

    def test_custom_settings(self):
        custom_config = {
            "server": {"host": "127.0.0.1", "port": 9000},
            "resources": {"max_vms": 100}
        }
        settings = Settings(**custom_config)
        assert settings.server.host == "127.0.0.1"
        assert settings.server.port == 9000
        assert settings.resources.max_vms == 100
        # Defaults should still be applied
        assert settings.networking.bridge_name == "chbr0"


class TestVMTemplateLoading:
    def test_load_existing_template(self, sample_linux_template, temp_dir):
        template_dir = temp_dir / "config" / "vm-templates"
        template_dir.mkdir(parents=True)
        
        template_file = template_dir / "test-template.yaml"
        with open(template_file, 'w') as f:
            yaml.dump({"test-template": sample_linux_template}, f)
        
        # Temporarily change working directory
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            template = load_vm_template("test-template")
            assert template["vcpus"] == 2
            assert template["memory_mb"] == 512
            assert template["kernel"] == "images/linux/vmlinux.bin"
        finally:
            os.chdir(original_cwd)

    def test_load_nonexistent_template(self):
        with pytest.raises(FileNotFoundError, match="VM template 'nonexistent' not found"):
            load_vm_template("nonexistent")


class TestNetworkConfigLoading:
    def test_load_existing_network_config(self, temp_dir):
        network_dir = temp_dir / "config" / "networks"
        network_dir.mkdir(parents=True)
        
        network_config = {
            "networking": {
                "bridge_name": "testbr0",
                "subnet": "10.0.0.0/24",
                "gateway": "10.0.0.1"
            }
        }
        
        network_file = network_dir / "test-network.yaml"
        with open(network_file, 'w') as f:
            yaml.dump(network_config, f)
        
        # Temporarily change working directory
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            config = load_network_config("test-network")
            assert config["networking"]["bridge_name"] == "testbr0"
            assert config["networking"]["subnet"] == "10.0.0.0/24"
        finally:
            os.chdir(original_cwd)

    def test_load_nonexistent_network_config(self):
        with pytest.raises(FileNotFoundError, match="Network config 'nonexistent' not found"):
            load_network_config("nonexistent")