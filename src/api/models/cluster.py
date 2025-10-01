"""
Pydantic models for cluster management API.
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, Any, List, Optional
from datetime import datetime


class ServiceInstanceResponse(BaseModel):
    """Service instance information."""
    id: str = Field(..., description="Unique instance identifier")
    host: str = Field(..., description="Instance host/IP address")
    port: int = Field(..., description="Instance port number")
    status: str = Field(..., description="Instance status (healthy, unhealthy, starting, stopping)")
    last_heartbeat: datetime = Field(..., description="Last heartbeat timestamp")
    load_score: float = Field(..., description="Current load score (0.0 to 1.0)")
    capabilities: List[str] = Field(default=[], description="Instance capabilities")
    metadata: Dict[str, Any] = Field(default={}, description="Additional instance metadata")


class LoadBalancingConfigResponse(BaseModel):
    """Load balancing configuration."""
    algorithm: str = Field(..., description="Load balancing algorithm")
    health_check_interval: int = Field(..., description="Health check interval in seconds")
    max_retries: int = Field(..., description="Maximum retry attempts")
    timeout_seconds: int = Field(..., description="Request timeout in seconds")
    sticky_sessions: bool = Field(..., description="Enable sticky sessions")
    session_affinity_timeout: int = Field(..., description="Session affinity timeout in seconds")


class ScalingConfigResponse(BaseModel):
    """Scaling configuration information."""
    current_replicas: int = Field(..., description="Current number of replicas")
    min_replicas: int = Field(..., description="Minimum number of replicas")
    max_replicas: int = Field(..., description="Maximum number of replicas")
    target_cpu_percent: int = Field(..., description="Target CPU utilization percentage")
    target_memory_percent: int = Field(..., description="Target memory utilization percentage")


class ClusterStatusResponse(BaseModel):
    """Comprehensive cluster status response."""
    total_instances: int = Field(..., description="Total number of instances")
    healthy_instances: int = Field(..., description="Number of healthy instances")
    unhealthy_instances: int = Field(..., description="Number of unhealthy instances")
    instances: List[ServiceInstanceResponse] = Field(default=[], description="List of all instances")
    load_balancing_config: Dict[str, Any] = Field(default={}, description="Load balancing configuration")
    connection_counts: Dict[str, int] = Field(default={}, description="Connection counts per instance")
    scaling_config: ScalingConfigResponse = Field(..., description="Scaling configuration")
    metrics: Dict[str, float] = Field(default={}, description="Current cluster metrics")


class ScalingRecommendation(BaseModel):
    """Scaling recommendation."""
    should_scale_up: bool = Field(..., description="Whether scaling up is recommended")
    should_scale_down: bool = Field(..., description="Whether scaling down is recommended")
    reason: str = Field(..., description="Reason for the recommendation")


class ScalingMetricsResponse(BaseModel):
    """Scaling metrics and recommendations."""
    cpu_usage: float = Field(..., description="Current CPU usage percentage")
    memory_usage: float = Field(..., description="Current memory usage percentage")
    request_rate: float = Field(..., description="Current request rate (requests/second)")
    current_replicas: int = Field(..., description="Current number of replicas")
    min_replicas: int = Field(..., description="Minimum allowed replicas")
    max_replicas: int = Field(..., description="Maximum allowed replicas")
    target_cpu_percent: int = Field(..., description="Target CPU utilization percentage")
    target_memory_percent: int = Field(..., description="Target memory utilization percentage")
    scaling_recommendation: ScalingRecommendation = Field(..., description="Scaling recommendation")


class ScalingActionRequest(BaseModel):
    """Request for manual scaling action."""
    action: str = Field(..., description="Scaling action (up, down, set)")
    replicas: int = Field(1, description="Number of replicas to scale (or target for 'set' action)")
    
    @validator('action')
    def validate_action(cls, v):
        if v not in ['up', 'down', 'set']:
            raise ValueError('Action must be one of: up, down, set')
        return v
    
    @validator('replicas')
    def validate_replicas(cls, v):
        if v < 1:
            raise ValueError('Replicas must be at least 1')
        return v


class LoadBalancingConfigRequest(BaseModel):
    """Request for updating load balancing configuration."""
    algorithm: str = Field("weighted_round_robin", description="Load balancing algorithm")
    health_check_interval: int = Field(30, description="Health check interval in seconds")
    max_retries: int = Field(3, description="Maximum retry attempts")
    timeout_seconds: int = Field(10, description="Request timeout in seconds")
    sticky_sessions: bool = Field(False, description="Enable sticky sessions")
    session_affinity_timeout: int = Field(3600, description="Session affinity timeout in seconds")
    
    @validator('algorithm')
    def validate_algorithm(cls, v):
        valid_algorithms = ['round_robin', 'weighted_round_robin', 'least_connections']
        if v not in valid_algorithms:
            raise ValueError(f'Algorithm must be one of: {valid_algorithms}')
        return v
    
    @validator('health_check_interval')
    def validate_health_check_interval(cls, v):
        if v < 5 or v > 300:
            raise ValueError('Health check interval must be between 5 and 300 seconds')
        return v
    
    @validator('max_retries')
    def validate_max_retries(cls, v):
        if v < 1 or v > 10:
            raise ValueError('Max retries must be between 1 and 10')
        return v
    
    @validator('timeout_seconds')
    def validate_timeout(cls, v):
        if v < 1 or v > 60:
            raise ValueError('Timeout must be between 1 and 60 seconds')
        return v
    
    @validator('session_affinity_timeout')
    def validate_session_affinity_timeout(cls, v):
        if v < 60 or v > 86400:  # 1 minute to 24 hours
            raise ValueError('Session affinity timeout must be between 60 and 86400 seconds')
        return v


class ClusterHealthResponse(BaseModel):
    """Cluster health check response."""
    status: str = Field(..., description="Overall cluster health status")
    healthy_instances: int = Field(..., description="Number of healthy instances")
    current_replicas: int = Field(..., description="Current replica count")
    timestamp: datetime = Field(..., description="Health check timestamp")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class ServiceDiscoveryRefreshResponse(BaseModel):
    """Service discovery refresh response."""
    message: str = Field(..., description="Success message")
    discovered_instances: int = Field(..., description="Number of discovered instances")
    healthy_instances: int = Field(..., description="Number of healthy instances")
    instances: List[Dict[str, Any]] = Field(default=[], description="Discovered instances summary")


class AutoScaleResponse(BaseModel):
    """Auto-scaling trigger response."""
    message: str = Field(..., description="Success message")
    action_taken: str = Field(..., description="Scaling action taken")
    current_replicas: int = Field(..., description="Current replica count before action")
    new_replicas: int = Field(..., description="New replica count after action")
    metrics: Dict[str, float] = Field(default={}, description="Current metrics that triggered action")
    thresholds: Dict[str, float] = Field(default={}, description="Scaling thresholds")


class ManualScaleResponse(BaseModel):
    """Manual scaling action response."""
    message: str = Field(..., description="Success message")
    target_replicas: int = Field(..., description="Target replica count")
    action: str = Field(..., description="Scaling action performed")
    user: str = Field(..., description="User who triggered the action")