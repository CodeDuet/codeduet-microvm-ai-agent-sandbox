import pytest
import asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from pathlib import Path
import tempfile
import shutil

from src.api.server import app
from src.utils.config import Settings


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def temp_dir():
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def test_settings():
    return Settings(
        server={"host": "127.0.0.1", "port": 8000, "workers": 1},
        cloud_hypervisor={"binary_path": "/usr/local/bin/cloud-hypervisor", "api_socket_dir": "/tmp/test-ch-sockets"},
        networking={"bridge_name": "testbr0", "subnet": "192.168.100.0/24", "port_range_start": 20000, "port_range_end": 21000},
        resources={"max_vms": 10, "max_memory_per_vm": 2048, "max_vcpus_per_vm": 4},
        security={"enable_authentication": False, "api_key_required": False, "vm_isolation": True},
        monitoring={"prometheus_port": 9091, "metrics_enabled": True, "log_level": "DEBUG"}
    )


@pytest.fixture
def sample_vm_config():
    return {
        "name": "test-vm",
        "template": "linux-default",
        "vcpus": 2,
        "memory_mb": 512,
        "os_type": "linux",
        "guest_agent": True,
        "metadata": {"test": True}
    }


@pytest.fixture
def sample_linux_template():
    return {
        "vcpus": 2,
        "memory_mb": 512,
        "kernel": "images/linux/vmlinux.bin",
        "rootfs": "images/linux/rootfs.ext4",
        "boot_args": "console=ttyS0 reboot=k panic=1 pci=off",
        "guest_agent": {
            "enabled": True,
            "port": 8080
        },
        "network": {
            "enabled": True,
            "bridge": "chbr0"
        }
    }


@pytest.fixture
def sample_windows_template():
    return {
        "vcpus": 4,
        "memory_mb": 2048,
        "firmware": "images/windows/OVMF.fd",
        "disk": "images/windows/windows.qcow2",
        "cdrom": "images/windows/virtio-win.iso",
        "guest_agent": {
            "enabled": True,
            "port": 8080
        },
        "network": {
            "enabled": True,
            "bridge": "chbr0"
        }
    }