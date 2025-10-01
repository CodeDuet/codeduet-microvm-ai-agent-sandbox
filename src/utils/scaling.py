"""
Horizontal scaling and load balancing utilities for MicroVM Sandbox.
Provides support for multi-instance deployments with load balancing.
"""

import asyncio
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import httpx

# Optional Kubernetes imports
try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    # Create dummy classes for type hints
    class ApiException(Exception):
        pass

logger = logging.getLogger(__name__)


@dataclass
class ServiceInstance:
    """Represents a service instance in the cluster."""
    id: str
    host: str
    port: int
    status: str  # healthy, unhealthy, starting, stopping
    last_heartbeat: datetime
    load_score: float  # 0.0 to 1.0, higher means more loaded
    capabilities: List[str]
    metadata: Dict[str, Any]


@dataclass
class LoadBalancingConfig:
    """Load balancing configuration."""
    algorithm: str = "weighted_round_robin"  # round_robin, weighted_round_robin, least_connections
    health_check_interval: int = 30
    max_retries: int = 3
    timeout_seconds: int = 10
    sticky_sessions: bool = False
    session_affinity_timeout: int = 3600


class ServiceDiscovery:
    """Service discovery for MicroVM Sandbox instances."""
    
    def __init__(self, namespace: str = "microvm-sandbox"):
        self.namespace = namespace
        self.instances: Dict[str, ServiceInstance] = {}
        self.last_discovery = datetime.min
        self.discovery_interval = 30  # seconds
        
        # Initialize Kubernetes client if in cluster
        self._init_kubernetes_client()
    
    def _init_kubernetes_client(self):
        """Initialize Kubernetes client."""
        if not KUBERNETES_AVAILABLE:
            logger.warning("Kubernetes client not available - install kubernetes package")
            self.k8s_client = None
            self.apps_client = None
            self.in_cluster = False
            return
            
        try:
            if os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount'):
                # Running in cluster
                config.load_incluster_config()
                self.k8s_client = client.CoreV1Api()
                self.apps_client = client.AppsV1Api()
                self.in_cluster = True
                logger.info("Initialized Kubernetes client for in-cluster operation")
            else:
                # Development environment
                config.load_kube_config()
                self.k8s_client = client.CoreV1Api()
                self.apps_client = client.AppsV1Api()
                self.in_cluster = False
                logger.info("Initialized Kubernetes client for out-of-cluster operation")
        except Exception as e:
            logger.warning(f"Failed to initialize Kubernetes client: {e}")
            self.k8s_client = None
            self.apps_client = None
            self.in_cluster = False
    
    async def discover_instances(self) -> List[ServiceInstance]:
        """Discover available service instances."""
        if datetime.now() - self.last_discovery < timedelta(seconds=self.discovery_interval):
            return list(self.instances.values())
        
        if self.k8s_client:
            await self._discover_kubernetes_instances()
        else:
            await self._discover_static_instances()
        
        self.last_discovery = datetime.now()
        return list(self.instances.values())
    
    async def _discover_kubernetes_instances(self):
        """Discover instances from Kubernetes."""
        try:
            # Get endpoints for microvm-api service
            endpoints = self.k8s_client.read_namespaced_endpoints(
                name="microvm-api-headless",
                namespace=self.namespace
            )
            
            discovered_instances = {}
            
            for subset in endpoints.subsets or []:
                for address in subset.addresses or []:
                    for port in subset.ports or []:
                        if port.name == "http":
                            instance_id = f"{address.ip}:{port.port}"
                            
                            # Check if instance is healthy
                            status = await self._check_instance_health(address.ip, port.port)
                            
                            instance = ServiceInstance(
                                id=instance_id,
                                host=address.ip,
                                port=port.port,
                                status=status,
                                last_heartbeat=datetime.now(),
                                load_score=0.0,  # Will be updated by health check
                                capabilities=["vm_management", "api"],
                                metadata={
                                    "pod_name": address.target_ref.name if address.target_ref else None,
                                    "namespace": self.namespace
                                }
                            )
                            discovered_instances[instance_id] = instance
            
            # Update instances
            self.instances = discovered_instances
            logger.info(f"Discovered {len(self.instances)} service instances")
            
        except ApiException as e:
            logger.error(f"Failed to discover Kubernetes instances: {e}")
        except Exception as e:
            logger.error(f"Error during Kubernetes service discovery: {e}")
    
    async def _discover_static_instances(self):
        """Discover instances from static configuration."""
        # For development/testing
        static_hosts = os.getenv("MICROVM_CLUSTER_HOSTS", "localhost:8000").split(",")
        
        discovered_instances = {}
        
        for host_port in static_hosts:
            try:
                host, port = host_port.strip().split(":")
                port = int(port)
                
                instance_id = f"{host}:{port}"
                status = await self._check_instance_health(host, port)
                
                instance = ServiceInstance(
                    id=instance_id,
                    host=host,
                    port=port,
                    status=status,
                    last_heartbeat=datetime.now(),
                    load_score=0.0,
                    capabilities=["vm_management", "api"],
                    metadata={"static": True}
                )
                discovered_instances[instance_id] = instance
                
            except Exception as e:
                logger.error(f"Failed to parse static host {host_port}: {e}")
        
        self.instances = discovered_instances
        logger.info(f"Discovered {len(self.instances)} static service instances")
    
    async def _check_instance_health(self, host: str, port: int) -> str:
        """Check health of a service instance."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"http://{host}:{port}/api/v1/health/ready")
                
                if response.status_code == 200:
                    health_data = response.json()
                    
                    # Extract load information if available
                    if "metrics" in health_data:
                        cpu_usage = health_data["metrics"].get("cpu_usage_percent", 0)
                        memory_usage = health_data["metrics"].get("memory_usage_percent", 0)
                        load_score = max(cpu_usage, memory_usage) / 100.0
                        
                        # Update load score for existing instance
                        instance_id = f"{host}:{port}"
                        if instance_id in self.instances:
                            self.instances[instance_id].load_score = load_score
                    
                    return "healthy"
                else:
                    return "unhealthy"
                    
        except Exception as e:
            logger.debug(f"Health check failed for {host}:{port}: {e}")
            return "unhealthy"
    
    async def get_healthy_instances(self) -> List[ServiceInstance]:
        """Get list of healthy instances."""
        await self.discover_instances()
        return [instance for instance in self.instances.values() if instance.status == "healthy"]


class LoadBalancer:
    """Load balancer for distributing requests across service instances."""
    
    def __init__(self, config: LoadBalancingConfig = None):
        self.config = config or LoadBalancingConfig()
        self.service_discovery = ServiceDiscovery()
        self.round_robin_index = 0
        self.connection_counts: Dict[str, int] = {}
        self.session_affinity: Dict[str, str] = {}  # session_id -> instance_id
        
    async def get_target_instance(self, session_id: Optional[str] = None) -> Optional[ServiceInstance]:
        """Get target instance for request routing."""
        healthy_instances = await self.service_discovery.get_healthy_instances()
        
        if not healthy_instances:
            logger.warning("No healthy instances available")
            return None
        
        # Check session affinity
        if session_id and self.config.sticky_sessions:
            if session_id in self.session_affinity:
                instance_id = self.session_affinity[session_id]
                instance = next((i for i in healthy_instances if i.id == instance_id), None)
                if instance:
                    return instance
                else:
                    # Instance no longer available, remove affinity
                    del self.session_affinity[session_id]
        
        # Select instance based on algorithm
        if self.config.algorithm == "round_robin":
            instance = self._round_robin_select(healthy_instances)
        elif self.config.algorithm == "weighted_round_robin":
            instance = self._weighted_round_robin_select(healthy_instances)
        elif self.config.algorithm == "least_connections":
            instance = self._least_connections_select(healthy_instances)
        else:
            # Default to round robin
            instance = self._round_robin_select(healthy_instances)
        
        # Update session affinity
        if session_id and self.config.sticky_sessions and instance:
            self.session_affinity[session_id] = instance.id
        
        return instance
    
    def _round_robin_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Round robin instance selection."""
        instance = instances[self.round_robin_index % len(instances)]
        self.round_robin_index += 1
        return instance
    
    def _weighted_round_robin_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Weighted round robin based on load scores."""
        # Calculate weights (inverse of load score)
        weights = [(1.0 - instance.load_score) for instance in instances]
        total_weight = sum(weights)
        
        if total_weight == 0:
            return self._round_robin_select(instances)
        
        # Weighted selection
        import random
        r = random.uniform(0, total_weight)
        
        cumulative_weight = 0
        for i, weight in enumerate(weights):
            cumulative_weight += weight
            if r <= cumulative_weight:
                return instances[i]
        
        return instances[-1]  # Fallback
    
    def _least_connections_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Select instance with least connections."""
        min_connections = float('inf')
        selected_instance = instances[0]
        
        for instance in instances:
            connections = self.connection_counts.get(instance.id, 0)
            if connections < min_connections:
                min_connections = connections
                selected_instance = instance
        
        return selected_instance
    
    async def proxy_request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Proxy request to appropriate instance."""
        session_id = kwargs.get('session_id')
        instance = await self.get_target_instance(session_id)
        
        if not instance:
            raise Exception("No healthy instances available")
        
        # Track connection
        self.connection_counts[instance.id] = self.connection_counts.get(instance.id, 0) + 1
        
        try:
            url = f"http://{instance.host}:{instance.port}{path}"
            
            # Remove session_id from kwargs as it's not part of httpx
            proxy_kwargs = {k: v for k, v in kwargs.items() if k != 'session_id'}
            
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.request(method, url, **proxy_kwargs)
                return response
                
        finally:
            # Release connection
            self.connection_counts[instance.id] = max(0, self.connection_counts.get(instance.id, 0) - 1)
    
    async def get_cluster_status(self) -> Dict[str, Any]:
        """Get cluster status information."""
        instances = await self.service_discovery.discover_instances()
        healthy_count = len([i for i in instances if i.status == "healthy"])
        
        return {
            "total_instances": len(instances),
            "healthy_instances": healthy_count,
            "unhealthy_instances": len(instances) - healthy_count,
            "instances": [asdict(instance) for instance in instances],
            "load_balancing_config": asdict(self.config),
            "connection_counts": self.connection_counts.copy()
        }


class HorizontalScaler:
    """Horizontal pod autoscaler for MicroVM Sandbox."""
    
    def __init__(self, namespace: str = "microvm-sandbox"):
        self.namespace = namespace
        self.service_discovery = ServiceDiscovery(namespace)
        
        # Scaling configuration
        self.min_replicas = int(os.getenv("MICROVM_MIN_REPLICAS", "3"))
        self.max_replicas = int(os.getenv("MICROVM_MAX_REPLICAS", "10"))
        self.target_cpu_percent = int(os.getenv("MICROVM_TARGET_CPU_PERCENT", "70"))
        self.target_memory_percent = int(os.getenv("MICROVM_TARGET_MEMORY_PERCENT", "80"))
        self.scale_up_threshold = 0.8  # Scale up when usage > 80% of target
        self.scale_down_threshold = 0.5  # Scale down when usage < 50% of target
        
    async def get_current_metrics(self) -> Dict[str, float]:
        """Get current cluster metrics."""
        instances = await self.service_discovery.get_healthy_instances()
        
        if not instances:
            return {"cpu_usage": 0.0, "memory_usage": 0.0, "request_rate": 0.0}
        
        total_cpu = 0.0
        total_memory = 0.0
        total_requests = 0.0
        
        for instance in instances:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"http://{instance.host}:{instance.port}/api/v1/health/metrics")
                    
                    if response.status_code == 200:
                        data = response.json()
                        total_cpu += data.get("cpu_usage_percent", 0)
                        total_memory += data.get("memory_usage_percent", 0)
                        total_requests += data.get("requests_per_second", 0)
            
            except Exception as e:
                logger.debug(f"Failed to get metrics from {instance.id}: {e}")
        
        count = len(instances)
        return {
            "cpu_usage": total_cpu / count if count > 0 else 0.0,
            "memory_usage": total_memory / count if count > 0 else 0.0,
            "request_rate": total_requests
        }
    
    async def should_scale_up(self) -> bool:
        """Check if scaling up is needed."""
        metrics = await self.get_current_metrics()
        
        cpu_threshold_exceeded = metrics["cpu_usage"] > (self.target_cpu_percent * self.scale_up_threshold)
        memory_threshold_exceeded = metrics["memory_usage"] > (self.target_memory_percent * self.scale_up_threshold)
        
        current_replicas = await self.get_current_replica_count()
        can_scale_up = current_replicas < self.max_replicas
        
        return (cpu_threshold_exceeded or memory_threshold_exceeded) and can_scale_up
    
    async def should_scale_down(self) -> bool:
        """Check if scaling down is needed."""
        metrics = await self.get_current_metrics()
        
        cpu_threshold_low = metrics["cpu_usage"] < (self.target_cpu_percent * self.scale_down_threshold)
        memory_threshold_low = metrics["memory_usage"] < (self.target_memory_percent * self.scale_down_threshold)
        
        current_replicas = await self.get_current_replica_count()
        can_scale_down = current_replicas > self.min_replicas
        
        return cpu_threshold_low and memory_threshold_low and can_scale_down
    
    async def get_current_replica_count(self) -> int:
        """Get current replica count."""
        if not self.service_discovery.apps_client:
            return len(await self.service_discovery.get_healthy_instances())
        
        try:
            deployment = self.service_discovery.apps_client.read_namespaced_deployment(
                name="microvm-api",
                namespace=self.namespace
            )
            return deployment.spec.replicas
        except ApiException as e:
            logger.error(f"Failed to get deployment replica count: {e}")
            return 0
    
    async def scale_deployment(self, target_replicas: int) -> bool:
        """Scale deployment to target replica count."""
        if not self.service_discovery.apps_client:
            logger.warning("Kubernetes client not available, cannot scale deployment")
            return False
        
        try:
            # Update deployment replica count
            body = {"spec": {"replicas": target_replicas}}
            
            self.service_discovery.apps_client.patch_namespaced_deployment_scale(
                name="microvm-api",
                namespace=self.namespace,
                body=body
            )
            
            logger.info(f"Scaled deployment to {target_replicas} replicas")
            return True
            
        except ApiException as e:
            logger.error(f"Failed to scale deployment: {e}")
            return False
    
    async def auto_scale(self) -> Dict[str, Any]:
        """Perform automatic scaling based on metrics."""
        metrics = await self.get_current_metrics()
        current_replicas = await self.get_current_replica_count()
        
        action_taken = "none"
        new_replicas = current_replicas
        
        if await self.should_scale_up():
            new_replicas = min(current_replicas + 1, self.max_replicas)
            if await self.scale_deployment(new_replicas):
                action_taken = "scale_up"
        
        elif await self.should_scale_down():
            new_replicas = max(current_replicas - 1, self.min_replicas)
            if await self.scale_deployment(new_replicas):
                action_taken = "scale_down"
        
        return {
            "action": action_taken,
            "current_replicas": current_replicas,
            "new_replicas": new_replicas,
            "metrics": metrics,
            "thresholds": {
                "cpu_target": self.target_cpu_percent,
                "memory_target": self.target_memory_percent,
                "scale_up_threshold": self.scale_up_threshold,
                "scale_down_threshold": self.scale_down_threshold
            }
        }


# Global instances
_load_balancer = None
_horizontal_scaler = None


def get_load_balancer() -> LoadBalancer:
    """Get global load balancer instance."""
    global _load_balancer
    if _load_balancer is None:
        _load_balancer = LoadBalancer()
    return _load_balancer


def get_horizontal_scaler() -> HorizontalScaler:
    """Get global horizontal scaler instance."""
    global _horizontal_scaler
    if _horizontal_scaler is None:
        _horizontal_scaler = HorizontalScaler()
    return _horizontal_scaler