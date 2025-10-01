"""
Unit tests for scaling and load balancing functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json

from src.utils.scaling import (
    ServiceInstance, LoadBalancingConfig, ServiceDiscovery,
    LoadBalancer, HorizontalScaler
)


class TestServiceInstance:
    """Test ServiceInstance dataclass."""
    
    def test_service_instance_creation(self):
        """Test creating a service instance."""
        instance = ServiceInstance(
            id="test-instance",
            host="192.168.1.100",
            port=8000,
            status="healthy",
            last_heartbeat=datetime.now(),
            load_score=0.5,
            capabilities=["vm_management", "api"],
            metadata={"pod_name": "microvm-api-1"}
        )
        
        assert instance.id == "test-instance"
        assert instance.host == "192.168.1.100"
        assert instance.port == 8000
        assert instance.status == "healthy"
        assert instance.load_score == 0.5
        assert "vm_management" in instance.capabilities
        assert instance.metadata["pod_name"] == "microvm-api-1"


class TestLoadBalancingConfig:
    """Test LoadBalancingConfig dataclass."""
    
    def test_default_config(self):
        """Test default load balancing configuration."""
        config = LoadBalancingConfig()
        
        assert config.algorithm == "weighted_round_robin"
        assert config.health_check_interval == 30
        assert config.max_retries == 3
        assert config.timeout_seconds == 10
        assert config.sticky_sessions == False
        assert config.session_affinity_timeout == 3600
    
    def test_custom_config(self):
        """Test custom load balancing configuration."""
        config = LoadBalancingConfig(
            algorithm="round_robin",
            health_check_interval=60,
            max_retries=5,
            timeout_seconds=15,
            sticky_sessions=True,
            session_affinity_timeout=7200
        )
        
        assert config.algorithm == "round_robin"
        assert config.health_check_interval == 60
        assert config.max_retries == 5
        assert config.timeout_seconds == 15
        assert config.sticky_sessions == True
        assert config.session_affinity_timeout == 7200


class TestServiceDiscovery:
    """Test ServiceDiscovery class."""
    
    @pytest.fixture
    def service_discovery(self):
        """Create a ServiceDiscovery instance for testing."""
        with patch('src.utils.scaling.config'):
            discovery = ServiceDiscovery("test-namespace")
            discovery.k8s_client = None  # Disable Kubernetes client for testing
            return discovery
    
    @pytest.mark.asyncio
    async def test_discover_static_instances(self, service_discovery):
        """Test discovering static instances."""
        with patch.dict('os.environ', {'MICROVM_CLUSTER_HOSTS': 'localhost:8000,localhost:8001'}):
            with patch.object(service_discovery, '_check_instance_health', return_value="healthy"):
                instances = await service_discovery.discover_instances()
                
                assert len(instances) == 2
                assert instances[0].host == "localhost"
                assert instances[0].port == 8000
                assert instances[1].host == "localhost"
                assert instances[1].port == 8001
                assert all(instance.status == "healthy" for instance in instances)
    
    @pytest.mark.asyncio
    async def test_check_instance_health_success(self, service_discovery):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "metrics": {"cpu_usage_percent": 50, "memory_usage_percent": 60}
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            status = await service_discovery._check_instance_health("localhost", 8000)
            assert status == "healthy"
    
    @pytest.mark.asyncio
    async def test_check_instance_health_failure(self, service_discovery):
        """Test failed health check."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=Exception("Connection failed"))
            
            status = await service_discovery._check_instance_health("localhost", 8000)
            assert status == "unhealthy"
    
    @pytest.mark.asyncio
    async def test_get_healthy_instances(self, service_discovery):
        """Test getting only healthy instances."""
        # Mock instances with mixed health status
        service_discovery.instances = {
            "host1:8000": ServiceInstance(
                id="host1:8000", host="host1", port=8000, status="healthy",
                last_heartbeat=datetime.now(), load_score=0.3, capabilities=[], metadata={}
            ),
            "host2:8000": ServiceInstance(
                id="host2:8000", host="host2", port=8000, status="unhealthy",
                last_heartbeat=datetime.now(), load_score=0.8, capabilities=[], metadata={}
            ),
            "host3:8000": ServiceInstance(
                id="host3:8000", host="host3", port=8000, status="healthy",
                last_heartbeat=datetime.now(), load_score=0.5, capabilities=[], metadata={}
            )
        }
        
        with patch.object(service_discovery, 'discover_instances', return_value=list(service_discovery.instances.values())):
            healthy_instances = await service_discovery.get_healthy_instances()
            
            assert len(healthy_instances) == 2
            assert all(instance.status == "healthy" for instance in healthy_instances)
            assert healthy_instances[0].host in ["host1", "host3"]
            assert healthy_instances[1].host in ["host1", "host3"]


class TestLoadBalancer:
    """Test LoadBalancer class."""
    
    @pytest.fixture
    def load_balancer(self):
        """Create a LoadBalancer instance for testing."""
        config = LoadBalancingConfig(algorithm="round_robin")
        lb = LoadBalancer(config)
        return lb
    
    @pytest.fixture
    def mock_instances(self):
        """Create mock service instances."""
        return [
            ServiceInstance(
                id="instance1", host="host1", port=8000, status="healthy",
                last_heartbeat=datetime.now(), load_score=0.3, capabilities=[], metadata={}
            ),
            ServiceInstance(
                id="instance2", host="host2", port=8000, status="healthy",
                last_heartbeat=datetime.now(), load_score=0.7, capabilities=[], metadata={}
            ),
            ServiceInstance(
                id="instance3", host="host3", port=8000, status="healthy",
                last_heartbeat=datetime.now(), load_score=0.5, capabilities=[], metadata={}
            )
        ]
    
    @pytest.mark.asyncio
    async def test_round_robin_selection(self, load_balancer, mock_instances):
        """Test round robin instance selection."""
        with patch.object(load_balancer.service_discovery, 'get_healthy_instances', return_value=mock_instances):
            # Test multiple selections to verify round robin behavior
            instance1 = await load_balancer.get_target_instance()
            instance2 = await load_balancer.get_target_instance()
            instance3 = await load_balancer.get_target_instance()
            instance4 = await load_balancer.get_target_instance()  # Should wrap around
            
            assert instance1.id == "instance1"
            assert instance2.id == "instance2"
            assert instance3.id == "instance3"
            assert instance4.id == "instance1"  # Wrapped around
    
    @pytest.mark.asyncio
    async def test_weighted_round_robin_selection(self, mock_instances):
        """Test weighted round robin instance selection."""
        config = LoadBalancingConfig(algorithm="weighted_round_robin")
        load_balancer = LoadBalancer(config)
        
        with patch.object(load_balancer.service_discovery, 'get_healthy_instances', return_value=mock_instances):
            # Test multiple selections - should favor instances with lower load scores
            selections = []
            for _ in range(100):
                instance = await load_balancer.get_target_instance()
                selections.append(instance.id)
            
            # instance1 (load_score=0.3) should be selected more often than instance2 (load_score=0.7)
            instance1_count = selections.count("instance1")
            instance2_count = selections.count("instance2")
            assert instance1_count > instance2_count
    
    @pytest.mark.asyncio
    async def test_least_connections_selection(self, mock_instances):
        """Test least connections instance selection."""
        config = LoadBalancingConfig(algorithm="least_connections")
        load_balancer = LoadBalancer(config)
        
        # Set up connection counts
        load_balancer.connection_counts = {
            "instance1": 5,
            "instance2": 2,
            "instance3": 8
        }
        
        with patch.object(load_balancer.service_discovery, 'get_healthy_instances', return_value=mock_instances):
            instance = await load_balancer.get_target_instance()
            
            # Should select instance2 with least connections (2)
            assert instance.id == "instance2"
    
    @pytest.mark.asyncio
    async def test_session_affinity(self, load_balancer, mock_instances):
        """Test session affinity functionality."""
        load_balancer.config.sticky_sessions = True
        
        with patch.object(load_balancer.service_discovery, 'get_healthy_instances', return_value=mock_instances):
            # First request with session ID
            instance1 = await load_balancer.get_target_instance(session_id="session123")
            
            # Second request with same session ID should return same instance
            instance2 = await load_balancer.get_target_instance(session_id="session123")
            
            assert instance1.id == instance2.id
            assert "session123" in load_balancer.session_affinity
            assert load_balancer.session_affinity["session123"] == instance1.id
    
    @pytest.mark.asyncio
    async def test_no_healthy_instances(self, load_balancer):
        """Test behavior when no healthy instances are available."""
        with patch.object(load_balancer.service_discovery, 'get_healthy_instances', return_value=[]):
            instance = await load_balancer.get_target_instance()
            assert instance is None
    
    @pytest.mark.asyncio
    async def test_proxy_request(self, load_balancer, mock_instances):
        """Test request proxying."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch.object(load_balancer.service_discovery, 'get_healthy_instances', return_value=mock_instances):
            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_response)
                
                response = await load_balancer.proxy_request("GET", "/api/v1/vms")
                
                assert response.status_code == 200
                mock_client.return_value.__aenter__.return_value.request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_cluster_status(self, load_balancer, mock_instances):
        """Test getting cluster status."""
        load_balancer.connection_counts = {"instance1": 3, "instance2": 1}
        
        with patch.object(load_balancer.service_discovery, 'discover_instances', return_value=mock_instances):
            status = await load_balancer.get_cluster_status()
            
            assert status["total_instances"] == 3
            assert status["healthy_instances"] == 3
            assert status["unhealthy_instances"] == 0
            assert len(status["instances"]) == 3
            assert status["connection_counts"] == {"instance1": 3, "instance2": 1}


class TestHorizontalScaler:
    """Test HorizontalScaler class."""
    
    @pytest.fixture
    def horizontal_scaler(self):
        """Create a HorizontalScaler instance for testing."""
        with patch.dict('os.environ', {
            'MICROVM_MIN_REPLICAS': '2',
            'MICROVM_MAX_REPLICAS': '10',
            'MICROVM_TARGET_CPU_PERCENT': '70',
            'MICROVM_TARGET_MEMORY_PERCENT': '80'
        }):
            scaler = HorizontalScaler("test-namespace")
            scaler.service_discovery.apps_client = None  # Disable Kubernetes for testing
            return scaler
    
    @pytest.mark.asyncio
    async def test_get_current_metrics(self, horizontal_scaler):
        """Test getting current cluster metrics."""
        mock_instances = [
            ServiceInstance(
                id="instance1", host="host1", port=8000, status="healthy",
                last_heartbeat=datetime.now(), load_score=0.3, capabilities=[], metadata={}
            ),
            ServiceInstance(
                id="instance2", host="host2", port=8000, status="healthy",
                last_heartbeat=datetime.now(), load_score=0.7, capabilities=[], metadata={}
            )
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "cpu_usage_percent": 60,
            "memory_usage_percent": 70,
            "requests_per_second": 50
        }
        
        with patch.object(horizontal_scaler.service_discovery, 'get_healthy_instances', return_value=mock_instances):
            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                
                metrics = await horizontal_scaler.get_current_metrics()
                
                assert metrics["cpu_usage"] == 60.0  # Average of both instances
                assert metrics["memory_usage"] == 70.0
                assert metrics["request_rate"] == 100.0  # Sum of both instances
    
    @pytest.mark.asyncio
    async def test_should_scale_up(self, horizontal_scaler):
        """Test scale up decision logic."""
        with patch.object(horizontal_scaler, 'get_current_metrics', return_value={
            "cpu_usage": 80.0,  # Above threshold (70 * 0.8 = 56)
            "memory_usage": 50.0,
            "request_rate": 100.0
        }):
            with patch.object(horizontal_scaler, 'get_current_replica_count', return_value=3):
                should_scale = await horizontal_scaler.should_scale_up()
                assert should_scale == True
    
    @pytest.mark.asyncio
    async def test_should_not_scale_up_at_max(self, horizontal_scaler):
        """Test scale up prevention when at maximum replicas."""
        with patch.object(horizontal_scaler, 'get_current_metrics', return_value={
            "cpu_usage": 80.0,
            "memory_usage": 90.0,
            "request_rate": 200.0
        }):
            with patch.object(horizontal_scaler, 'get_current_replica_count', return_value=10):  # At max
                should_scale = await horizontal_scaler.should_scale_up()
                assert should_scale == False
    
    @pytest.mark.asyncio
    async def test_should_scale_down(self, horizontal_scaler):
        """Test scale down decision logic."""
        with patch.object(horizontal_scaler, 'get_current_metrics', return_value={
            "cpu_usage": 20.0,  # Below threshold (70 * 0.5 = 35)
            "memory_usage": 25.0,  # Below threshold (80 * 0.5 = 40)
            "request_rate": 10.0
        }):
            with patch.object(horizontal_scaler, 'get_current_replica_count', return_value=5):
                should_scale = await horizontal_scaler.should_scale_down()
                assert should_scale == True
    
    @pytest.mark.asyncio
    async def test_should_not_scale_down_at_min(self, horizontal_scaler):
        """Test scale down prevention when at minimum replicas."""
        with patch.object(horizontal_scaler, 'get_current_metrics', return_value={
            "cpu_usage": 10.0,
            "memory_usage": 15.0,
            "request_rate": 5.0
        }):
            with patch.object(horizontal_scaler, 'get_current_replica_count', return_value=2):  # At min
                should_scale = await horizontal_scaler.should_scale_down()
                assert should_scale == False
    
    @pytest.mark.asyncio
    async def test_get_current_replica_count_no_k8s(self, horizontal_scaler):
        """Test getting replica count without Kubernetes client."""
        mock_instances = [MagicMock(), MagicMock(), MagicMock()]
        
        with patch.object(horizontal_scaler.service_discovery, 'get_healthy_instances', return_value=mock_instances):
            count = await horizontal_scaler.get_current_replica_count()
            assert count == 3
    
    @pytest.mark.asyncio
    async def test_scale_deployment_no_k8s(self, horizontal_scaler):
        """Test scaling deployment without Kubernetes client."""
        result = await horizontal_scaler.scale_deployment(5)
        assert result == False  # Should fail without Kubernetes client
    
    @pytest.mark.asyncio
    async def test_auto_scale_up(self, horizontal_scaler):
        """Test automatic scale up."""
        with patch.object(horizontal_scaler, 'should_scale_up', return_value=True):
            with patch.object(horizontal_scaler, 'should_scale_down', return_value=False):
                with patch.object(horizontal_scaler, 'get_current_replica_count', return_value=3):
                    with patch.object(horizontal_scaler, 'scale_deployment', return_value=True):
                        with patch.object(horizontal_scaler, 'get_current_metrics', return_value={
                            "cpu_usage": 80.0, "memory_usage": 85.0, "request_rate": 150.0
                        }):
                            result = await horizontal_scaler.auto_scale()
                            
                            assert result["action"] == "scale_up"
                            assert result["current_replicas"] == 3
                            assert result["new_replicas"] == 4
    
    @pytest.mark.asyncio
    async def test_auto_scale_down(self, horizontal_scaler):
        """Test automatic scale down."""
        with patch.object(horizontal_scaler, 'should_scale_up', return_value=False):
            with patch.object(horizontal_scaler, 'should_scale_down', return_value=True):
                with patch.object(horizontal_scaler, 'get_current_replica_count', return_value=5):
                    with patch.object(horizontal_scaler, 'scale_deployment', return_value=True):
                        with patch.object(horizontal_scaler, 'get_current_metrics', return_value={
                            "cpu_usage": 20.0, "memory_usage": 25.0, "request_rate": 10.0
                        }):
                            result = await horizontal_scaler.auto_scale()
                            
                            assert result["action"] == "scale_down"
                            assert result["current_replicas"] == 5
                            assert result["new_replicas"] == 4
    
    @pytest.mark.asyncio
    async def test_auto_scale_no_action(self, horizontal_scaler):
        """Test no auto-scaling action needed."""
        with patch.object(horizontal_scaler, 'should_scale_up', return_value=False):
            with patch.object(horizontal_scaler, 'should_scale_down', return_value=False):
                with patch.object(horizontal_scaler, 'get_current_replica_count', return_value=4):
                    with patch.object(horizontal_scaler, 'get_current_metrics', return_value={
                        "cpu_usage": 50.0, "memory_usage": 60.0, "request_rate": 75.0
                    }):
                        result = await horizontal_scaler.auto_scale()
                        
                        assert result["action"] == "none"
                        assert result["current_replicas"] == 4
                        assert result["new_replicas"] == 4