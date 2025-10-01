"""
Unit tests for cluster management API routes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from src.api.server import app
from src.utils.scaling import ServiceInstance, LoadBalancingConfig


class TestClusterRoutes:
    """Test cluster management API routes."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_auth(self):
        """Mock authentication."""
        with patch('src.api.routes.cluster.get_current_user') as mock:
            mock.return_value = {"username": "testuser", "permissions": ["cluster:read", "cluster:write"]}
            yield mock
    
    @pytest.fixture
    def mock_load_balancer(self):
        """Mock load balancer."""
        with patch('src.api.routes.cluster.get_load_balancer') as mock:
            lb = MagicMock()
            lb.get_cluster_status = AsyncMock()
            lb.service_discovery.discover_instances = AsyncMock()
            lb.service_discovery.get_healthy_instances = AsyncMock()
            lb.config = LoadBalancingConfig()
            mock.return_value = lb
            yield lb
    
    @pytest.fixture
    def mock_horizontal_scaler(self):
        """Mock horizontal scaler."""
        with patch('src.api.routes.cluster.get_horizontal_scaler') as mock:
            scaler = MagicMock()
            scaler.get_current_metrics = AsyncMock()
            scaler.get_current_replica_count = AsyncMock()
            scaler.should_scale_up = AsyncMock()
            scaler.should_scale_down = AsyncMock()
            scaler.scale_deployment = AsyncMock()
            scaler.auto_scale = AsyncMock()
            scaler.min_replicas = 3
            scaler.max_replicas = 10
            scaler.target_cpu_percent = 70
            scaler.target_memory_percent = 80
            mock.return_value = scaler
            yield scaler
    
    @pytest.fixture
    def sample_instances(self):
        """Create sample service instances."""
        return [
            ServiceInstance(
                id="instance1",
                host="host1",
                port=8000,
                status="healthy",
                last_heartbeat=datetime.now(),
                load_score=0.3,
                capabilities=["vm_management", "api"],
                metadata={"pod_name": "microvm-api-1"}
            ),
            ServiceInstance(
                id="instance2",
                host="host2",
                port=8000,
                status="healthy",
                last_heartbeat=datetime.now(),
                load_score=0.7,
                capabilities=["vm_management", "api"],
                metadata={"pod_name": "microvm-api-2"}
            ),
            ServiceInstance(
                id="instance3",
                host="host3",
                port=8000,
                status="unhealthy",
                last_heartbeat=datetime.now(),
                load_score=0.9,
                capabilities=["vm_management", "api"],
                metadata={"pod_name": "microvm-api-3"}
            )
        ]
    
    def test_get_cluster_status(self, client, mock_auth, mock_load_balancer, mock_horizontal_scaler, sample_instances):
        """Test getting cluster status."""
        # Set up mock responses
        mock_load_balancer.get_cluster_status.return_value = {
            "total_instances": 3,
            "healthy_instances": 2,
            "unhealthy_instances": 1,
            "instances": [
                {
                    "id": instance.id,
                    "host": instance.host,
                    "port": instance.port,
                    "status": instance.status,
                    "last_heartbeat": instance.last_heartbeat.isoformat(),
                    "load_score": instance.load_score,
                    "capabilities": instance.capabilities,
                    "metadata": instance.metadata
                }
                for instance in sample_instances
            ],
            "load_balancing_config": {
                "algorithm": "weighted_round_robin",
                "health_check_interval": 30
            },
            "connection_counts": {"instance1": 5, "instance2": 3}
        }
        
        mock_horizontal_scaler.get_current_metrics.return_value = {
            "cpu_usage": 45.0,
            "memory_usage": 60.0,
            "request_rate": 120.0
        }
        mock_horizontal_scaler.get_current_replica_count.return_value = 3
        
        response = client.get("/api/v1/cluster/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_instances"] == 3
        assert data["healthy_instances"] == 2
        assert data["unhealthy_instances"] == 1
        assert len(data["instances"]) == 3
        assert data["scaling_config"]["current_replicas"] == 3
        assert data["metrics"]["cpu_usage"] == 45.0
    
    def test_list_service_instances(self, client, mock_auth, mock_load_balancer, sample_instances):
        """Test listing service instances."""
        mock_load_balancer.service_discovery.discover_instances.return_value = sample_instances
        
        response = client.get("/api/v1/cluster/instances")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 3
        assert data[0]["id"] == "instance1"
        assert data[1]["id"] == "instance2"
        assert data[2]["id"] == "instance3"
        assert data[0]["status"] == "healthy"
        assert data[2]["status"] == "unhealthy"
    
    def test_list_healthy_instances(self, client, mock_auth, mock_load_balancer, sample_instances):
        """Test listing only healthy instances."""
        healthy_instances = [inst for inst in sample_instances if inst.status == "healthy"]
        mock_load_balancer.service_discovery.get_healthy_instances.return_value = healthy_instances
        
        response = client.get("/api/v1/cluster/instances/healthy")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 2
        assert all(instance["status"] == "healthy" for instance in data)
        assert data[0]["id"] == "instance1"
        assert data[1]["id"] == "instance2"
    
    def test_get_scaling_metrics(self, client, mock_auth, mock_horizontal_scaler):
        """Test getting scaling metrics."""
        mock_horizontal_scaler.get_current_metrics.return_value = {
            "cpu_usage": 75.0,
            "memory_usage": 85.0,
            "request_rate": 200.0
        }
        mock_horizontal_scaler.get_current_replica_count.return_value = 5
        mock_horizontal_scaler.should_scale_up.return_value = True
        mock_horizontal_scaler.should_scale_down.return_value = False
        
        response = client.get("/api/v1/cluster/metrics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["cpu_usage"] == 75.0
        assert data["memory_usage"] == 85.0
        assert data["request_rate"] == 200.0
        assert data["current_replicas"] == 5
        assert data["min_replicas"] == 3
        assert data["max_replicas"] == 10
        assert data["scaling_recommendation"]["should_scale_up"] == True
        assert data["scaling_recommendation"]["should_scale_down"] == False
        assert "high resource usage" in data["scaling_recommendation"]["reason"].lower()
    
    def test_manual_scale_up(self, client, mock_auth, mock_horizontal_scaler):
        """Test manual scale up."""
        mock_horizontal_scaler.get_current_replica_count.return_value = 5
        mock_horizontal_scaler.scale_deployment.return_value = True
        
        response = client.post("/api/v1/cluster/scale", json={
            "action": "up",
            "replicas": 2
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["action"] == "up"
        assert data["target_replicas"] == 7  # 5 + 2
        assert "successfully" in data["message"]
        mock_horizontal_scaler.scale_deployment.assert_called_once_with(7)
    
    def test_manual_scale_down(self, client, mock_auth, mock_horizontal_scaler):
        """Test manual scale down."""
        mock_horizontal_scaler.get_current_replica_count.return_value = 8
        mock_horizontal_scaler.scale_deployment.return_value = True
        
        response = client.post("/api/v1/cluster/scale", json={
            "action": "down",
            "replicas": 3
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["action"] == "down"
        assert data["target_replicas"] == 5  # 8 - 3
        mock_horizontal_scaler.scale_deployment.assert_called_once_with(5)
    
    def test_manual_scale_set(self, client, mock_auth, mock_horizontal_scaler):
        """Test manual scale set to specific number."""
        mock_horizontal_scaler.scale_deployment.return_value = True
        
        response = client.post("/api/v1/cluster/scale", json={
            "action": "set",
            "replicas": 6
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["action"] == "set"
        assert data["target_replicas"] == 6
        mock_horizontal_scaler.scale_deployment.assert_called_once_with(6)
    
    def test_manual_scale_invalid_action(self, client, mock_auth):
        """Test manual scale with invalid action."""
        response = client.post("/api/v1/cluster/scale", json={
            "action": "invalid",
            "replicas": 1
        })
        
        assert response.status_code == 400
        assert "Invalid scaling action" in response.json()["detail"]
    
    def test_manual_scale_at_max_limit(self, client, mock_auth, mock_horizontal_scaler):
        """Test manual scale up when already at maximum."""
        mock_horizontal_scaler.get_current_replica_count.return_value = 10  # At max
        
        response = client.post("/api/v1/cluster/scale", json={
            "action": "up",
            "replicas": 1
        })
        
        assert response.status_code == 400
        assert "already at maximum" in response.json()["detail"]
    
    def test_manual_scale_at_min_limit(self, client, mock_auth, mock_horizontal_scaler):
        """Test manual scale down when already at minimum."""
        mock_horizontal_scaler.get_current_replica_count.return_value = 3  # At min
        
        response = client.post("/api/v1/cluster/scale", json={
            "action": "down",
            "replicas": 1
        })
        
        assert response.status_code == 400
        assert "already at minimum" in response.json()["detail"]
    
    def test_trigger_auto_scale(self, client, mock_auth, mock_horizontal_scaler):
        """Test triggering auto-scale."""
        mock_horizontal_scaler.auto_scale.return_value = {
            "action": "scale_up",
            "current_replicas": 3,
            "new_replicas": 4,
            "metrics": {"cpu_usage": 80.0, "memory_usage": 85.0},
            "thresholds": {"cpu_target": 70, "memory_target": 80}
        }
        
        response = client.post("/api/v1/cluster/auto-scale")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["action_taken"] == "scale_up"
        assert data["current_replicas"] == 3
        assert data["new_replicas"] == 4
        assert data["metrics"]["cpu_usage"] == 80.0
    
    def test_get_load_balancing_config(self, client, mock_auth, mock_load_balancer):
        """Test getting load balancing configuration."""
        response = client.get("/api/v1/cluster/load-balancing/config")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["algorithm"] == "weighted_round_robin"
        assert data["health_check_interval"] == 30
        assert data["max_retries"] == 3
        assert data["timeout_seconds"] == 10
        assert data["sticky_sessions"] == False
    
    def test_update_load_balancing_config(self, client, mock_auth, mock_load_balancer):
        """Test updating load balancing configuration."""
        response = client.put("/api/v1/cluster/load-balancing/config", json={
            "algorithm": "round_robin",
            "health_check_interval": 60,
            "max_retries": 5,
            "timeout_seconds": 15,
            "sticky_sessions": True,
            "session_affinity_timeout": 7200
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "updated successfully" in data["message"]
        assert data["config"]["algorithm"] == "round_robin"
        assert data["config"]["health_check_interval"] == 60
        assert data["config"]["sticky_sessions"] == True
    
    def test_update_load_balancing_config_invalid_algorithm(self, client, mock_auth):
        """Test updating load balancing config with invalid algorithm."""
        response = client.put("/api/v1/cluster/load-balancing/config", json={
            "algorithm": "invalid_algorithm"
        })
        
        assert response.status_code == 400
        assert "Invalid algorithm" in response.json()["detail"]
    
    def test_refresh_service_discovery(self, client, mock_auth, mock_load_balancer, sample_instances):
        """Test refreshing service discovery."""
        mock_load_balancer.service_discovery.discover_instances.return_value = sample_instances
        
        response = client.post("/api/v1/cluster/service-discovery/refresh")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "refreshed successfully" in data["message"]
        assert data["discovered_instances"] == 3
        assert data["healthy_instances"] == 2
        assert len(data["instances"]) == 3
    
    def test_cluster_health_check(self, client, mock_load_balancer, mock_horizontal_scaler, sample_instances):
        """Test cluster health check."""
        healthy_instances = [inst for inst in sample_instances if inst.status == "healthy"]
        mock_load_balancer.service_discovery.get_healthy_instances.return_value = healthy_instances
        mock_horizontal_scaler.get_current_replica_count.return_value = 3
        
        response = client.get("/api/v1/cluster/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["healthy_instances"] == 2
        assert data["current_replicas"] == 3
        assert "timestamp" in data
    
    def test_cluster_health_check_unhealthy(self, client, mock_load_balancer, mock_horizontal_scaler):
        """Test cluster health check when unhealthy."""
        mock_load_balancer.service_discovery.get_healthy_instances.return_value = []
        mock_horizontal_scaler.get_current_replica_count.return_value = 0
        
        response = client.get("/api/v1/cluster/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["healthy_instances"] == 0
        assert data["current_replicas"] == 0
    
    def test_unauthorized_access(self, client):
        """Test unauthorized access to cluster endpoints."""
        # Without mocking auth, should get authentication error
        with patch('src.api.routes.cluster.get_current_user', side_effect=Exception("Authentication required")):
            response = client.get("/api/v1/cluster/status")
            assert response.status_code == 500  # FastAPI converts unhandled exceptions to 500
    
    def test_scaling_failure(self, client, mock_auth, mock_horizontal_scaler):
        """Test scaling failure scenario."""
        mock_horizontal_scaler.get_current_replica_count.return_value = 5
        mock_horizontal_scaler.scale_deployment.return_value = False  # Scaling fails
        
        response = client.post("/api/v1/cluster/scale", json={
            "action": "up",
            "replicas": 1
        })
        
        assert response.status_code == 500
        assert "Failed to execute scaling action" in response.json()["detail"]
    
    def test_auto_scale_failure(self, client, mock_auth, mock_horizontal_scaler):
        """Test auto-scale failure scenario."""
        mock_horizontal_scaler.auto_scale.side_effect = Exception("Auto-scaling failed")
        
        response = client.post("/api/v1/cluster/auto-scale")
        
        assert response.status_code == 500
        assert "Failed to trigger auto-scaling" in response.json()["detail"]
    
    def test_service_discovery_failure(self, client, mock_auth, mock_load_balancer):
        """Test service discovery failure scenario."""
        mock_load_balancer.service_discovery.discover_instances.side_effect = Exception("Discovery failed")
        
        response = client.post("/api/v1/cluster/service-discovery/refresh")
        
        assert response.status_code == 500
        assert "Failed to refresh service discovery" in response.json()["detail"]