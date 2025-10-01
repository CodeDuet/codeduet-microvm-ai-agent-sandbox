import pytest
import ipaddress
from unittest.mock import Mock, AsyncMock, patch

from src.core.network_manager import NetworkManager


@pytest.fixture
def network_manager():
    with patch("src.core.network_manager.get_settings") as mock_settings:
        mock_settings.return_value.networking.bridge_name = "test-br0"
        mock_settings.return_value.networking.subnet = "192.168.100.0/24"
        mock_settings.return_value.networking.port_range_start = 10000
        mock_settings.return_value.networking.port_range_end = 20000
        return NetworkManager()


@pytest.mark.asyncio
async def test_setup_bridge_network_new_bridge(network_manager):
    with patch("src.core.network_manager.run_subprocess", new_callable=AsyncMock) as mock_run, \
         patch.object(network_manager, "_setup_nat_rules", new_callable=AsyncMock) as mock_nat:
        
        # First call (check if bridge exists) returns non-zero (doesn't exist)
        # Subsequent calls succeed
        mock_run.side_effect = [
            Mock(returncode=1),  # Bridge doesn't exist
            Mock(returncode=0),  # Create bridge
            Mock(returncode=0),  # Set IP
            Mock(returncode=0),  # Bring up
            Mock(returncode=0),  # Enable forwarding
        ]
        
        await network_manager.setup_bridge_network()
        
        assert mock_run.call_count == 5
        mock_nat.assert_called_once()


@pytest.mark.asyncio
async def test_setup_bridge_network_existing_bridge(network_manager):
    with patch("src.core.network_manager.run_subprocess", new_callable=AsyncMock) as mock_run:
        
        mock_run.return_value = Mock(returncode=0)  # Bridge exists
        
        await network_manager.setup_bridge_network()
        
        # Only one call to check if bridge exists
        assert mock_run.call_count == 1


@pytest.mark.asyncio
async def test_teardown_bridge_network(network_manager):
    with patch("src.core.network_manager.run_subprocess", new_callable=AsyncMock) as mock_run, \
         patch.object(network_manager, "_cleanup_nat_rules", new_callable=AsyncMock) as mock_cleanup:
        
        mock_run.side_effect = [
            Mock(returncode=0),  # Bridge exists
            Mock(returncode=0),  # Bring down
            Mock(returncode=0),  # Delete
        ]
        
        await network_manager.teardown_bridge_network()
        
        mock_cleanup.assert_called_once()
        assert mock_run.call_count == 3


@pytest.mark.asyncio
async def test_create_tap_interface(network_manager):
    with patch("src.core.network_manager.run_subprocess", new_callable=AsyncMock) as mock_run, \
         patch.object(network_manager, "_allocate_ip_address", return_value="192.168.100.10") as mock_alloc:
        
        mock_run.return_value = Mock(returncode=0)
        
        result = await network_manager.create_tap_interface("test-vm")
        
        assert result["tap_name"] == "tap-test-vm"
        assert result["vm_ip"] == "192.168.100.10"
        assert result["bridge_name"] == "test-br0"
        assert result["subnet"] == "192.168.100.0/24"
        
        mock_alloc.assert_called_once_with("test-vm")
        assert mock_run.call_count == 3  # create, attach, bring up


@pytest.mark.asyncio
async def test_delete_tap_interface_exists(network_manager):
    network_manager.allocated_ips["test-vm"] = "192.168.100.10"
    network_manager.allocated_ports["test-vm:22"] = 10001
    
    with patch("src.core.network_manager.run_subprocess", new_callable=AsyncMock) as mock_run:
        
        mock_run.side_effect = [
            Mock(returncode=0),  # Interface exists
            Mock(returncode=0),  # Delete interface
        ]
        
        await network_manager.delete_tap_interface("test-vm")
        
        assert "test-vm" not in network_manager.allocated_ips
        assert "test-vm:22" not in network_manager.allocated_ports
        assert mock_run.call_count == 2


@pytest.mark.asyncio
async def test_delete_tap_interface_not_exists(network_manager):
    with patch("src.core.network_manager.run_subprocess", new_callable=AsyncMock) as mock_run:
        
        mock_run.return_value = Mock(returncode=1)  # Interface doesn't exist
        
        await network_manager.delete_tap_interface("test-vm")
        
        # Only one call to check if interface exists
        assert mock_run.call_count == 1


@pytest.mark.asyncio
async def test_allocate_port_forward(network_manager):
    network_manager.allocated_ips["test-vm"] = "192.168.100.10"
    network_manager.port_counter = 10000
    
    with patch("src.core.network_manager.run_subprocess", new_callable=AsyncMock) as mock_run:
        
        mock_run.return_value = Mock(returncode=0)
        
        host_port = await network_manager.allocate_port_forward("test-vm", 22)
        
        assert host_port == 10000
        assert network_manager.allocated_ports["test-vm:22"] == 10000
        assert network_manager.port_counter == 10001
        assert mock_run.call_count == 2  # DNAT rule + FORWARD rule


@pytest.mark.asyncio
async def test_allocate_port_forward_no_vm_ip(network_manager):
    with pytest.raises(ValueError, match="VM 'test-vm' does not have an allocated IP address"):
        await network_manager.allocate_port_forward("test-vm", 22)


@pytest.mark.asyncio
async def test_remove_port_forward(network_manager):
    network_manager.allocated_ips["test-vm"] = "192.168.100.10"
    network_manager.allocated_ports["test-vm:22"] = 10000
    
    with patch("src.core.network_manager.run_subprocess", new_callable=AsyncMock) as mock_run:
        
        mock_run.return_value = Mock(returncode=0)
        
        await network_manager.remove_port_forward("test-vm", 22)
        
        assert "test-vm:22" not in network_manager.allocated_ports
        assert mock_run.call_count == 2  # Remove DNAT + FORWARD rules


@pytest.mark.asyncio
async def test_remove_port_forward_not_found(network_manager):
    await network_manager.remove_port_forward("test-vm", 22)
    # Should not raise exception, just log warning


@pytest.mark.asyncio
async def test_get_vm_network_info_exists(network_manager):
    network_manager.allocated_ips["test-vm"] = "192.168.100.10"
    
    with patch("src.core.network_manager.run_subprocess", new_callable=AsyncMock) as mock_run:
        
        mock_run.side_effect = [
            Mock(returncode=0, stdout="1024\n"),  # rx_bytes
            Mock(returncode=0, stdout="2048\n"),  # tx_bytes
        ]
        
        result = await network_manager.get_vm_network_info("test-vm")
        
        assert result["tap_name"] == "tap-test-vm"
        assert result["vm_ip"] == "192.168.100.10"
        assert result["bridge_name"] == "test-br0"
        assert result["rx_bytes"] == "1024"
        assert result["tx_bytes"] == "2048"


@pytest.mark.asyncio
async def test_get_vm_network_info_not_exists(network_manager):
    result = await network_manager.get_vm_network_info("test-vm")
    assert result is None


@pytest.mark.asyncio
async def test_get_vm_network_info_stats_error(network_manager):
    network_manager.allocated_ips["test-vm"] = "192.168.100.10"
    
    with patch("src.core.network_manager.run_subprocess", new_callable=AsyncMock) as mock_run:
        
        mock_run.return_value = Mock(returncode=1)  # Error reading stats
        
        result = await network_manager.get_vm_network_info("test-vm")
        
        assert result["rx_bytes"] == "0"
        assert result["tx_bytes"] == "0"


@pytest.mark.asyncio
async def test_list_network_interfaces(network_manager):
    network_manager.allocated_ips = {
        "vm1": "192.168.100.10",
        "vm2": "192.168.100.11"
    }
    
    with patch.object(network_manager, "get_vm_network_info") as mock_get_info:
        
        mock_get_info.side_effect = [
            {"tap_name": "tap-vm1", "vm_ip": "192.168.100.10"},
            {"tap_name": "tap-vm2", "vm_ip": "192.168.100.11"}
        ]
        
        interfaces = await network_manager.list_network_interfaces()
        
        assert len(interfaces) == 2
        assert interfaces[0]["tap_name"] == "tap-vm1"
        assert interfaces[1]["tap_name"] == "tap-vm2"


@pytest.mark.asyncio
async def test_allocate_ip_address(network_manager):
    # Test first available IP
    ip = await network_manager._allocate_ip_address("test-vm")
    
    # First host IP in 192.168.100.0/24 should be 192.168.100.1
    assert ip == "192.168.100.1"
    assert network_manager.allocated_ips["test-vm"] == "192.168.100.1"


@pytest.mark.asyncio
async def test_allocate_ip_address_second_vm(network_manager):
    # Allocate first IP
    network_manager.allocated_ips["vm1"] = "192.168.100.1"
    
    # Test second available IP
    ip = await network_manager._allocate_ip_address("test-vm")
    
    assert ip == "192.168.100.2"
    assert network_manager.allocated_ips["test-vm"] == "192.168.100.2"


@pytest.mark.asyncio
async def test_allocate_ip_address_subnet_full(network_manager):
    # Fill all available IPs (this is a test scenario, real subnet has 254 hosts)
    subnet = ipaddress.IPv4Network("192.168.100.0/30")  # Only 2 host IPs
    network_manager.subnet = subnet
    
    # Allocate all available IPs
    for i, ip in enumerate(subnet.hosts()):
        network_manager.allocated_ips[f"vm{i}"] = str(ip)
    
    with pytest.raises(RuntimeError, match="No available IP addresses in subnet"):
        await network_manager._allocate_ip_address("test-vm")


def test_get_next_available_port(network_manager):
    port = network_manager._get_next_available_port()
    
    assert port == 10000
    assert network_manager.port_counter == 10001


def test_get_next_available_port_skip_allocated(network_manager):
    network_manager.allocated_ports["test:80"] = 10000
    
    port = network_manager._get_next_available_port()
    
    assert port == 10001
    assert network_manager.port_counter == 10002


def test_get_next_available_port_range_exhausted(network_manager):
    network_manager.port_counter = 20001  # Beyond range
    
    with pytest.raises(RuntimeError, match="No available ports in range"):
        network_manager._get_next_available_port()


@pytest.mark.asyncio
async def test_setup_nat_rules(network_manager):
    with patch("src.core.network_manager.run_subprocess", new_callable=AsyncMock) as mock_run:
        
        mock_run.return_value = Mock(returncode=0)
        
        await network_manager._setup_nat_rules()
        
        assert mock_run.call_count == 3  # MASQUERADE + 2 FORWARD rules


@pytest.mark.asyncio
async def test_cleanup_nat_rules(network_manager):
    with patch("src.core.network_manager.run_subprocess", new_callable=AsyncMock) as mock_run:
        
        mock_run.return_value = Mock(returncode=0)
        
        await network_manager._cleanup_nat_rules()
        
        assert mock_run.call_count == 3  # Remove MASQUERADE + 2 FORWARD rules