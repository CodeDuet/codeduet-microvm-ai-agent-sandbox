"""
Cluster management API routes for load balancing, scaling, and service discovery.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, List, Optional
import logging

from ...utils.scaling import get_load_balancer, get_horizontal_scaler, LoadBalancingConfig
from ..middleware.auth import get_current_user
from ..models.cluster import (
    ClusterStatusResponse,
    ScalingMetricsResponse,
    ScalingActionRequest,
    LoadBalancingConfigRequest,
    ServiceInstanceResponse
)

router = APIRouter(prefix="/cluster", tags=["cluster"])
logger = logging.getLogger(__name__)


@router.get("/status", response_model=ClusterStatusResponse)
async def get_cluster_status(current_user: dict = Depends(get_current_user)):
    """Get comprehensive cluster status including instances and load balancing."""
    try:
        load_balancer = get_load_balancer()
        horizontal_scaler = get_horizontal_scaler()
        
        # Get cluster status from load balancer
        cluster_status = await load_balancer.get_cluster_status()
        
        # Get scaling metrics
        scaling_metrics = await horizontal_scaler.get_current_metrics()
        current_replicas = await horizontal_scaler.get_current_replica_count()
        
        return ClusterStatusResponse(
            total_instances=cluster_status["total_instances"],
            healthy_instances=cluster_status["healthy_instances"],
            unhealthy_instances=cluster_status["unhealthy_instances"],
            instances=[
                ServiceInstanceResponse(
                    id=instance["id"],
                    host=instance["host"],
                    port=instance["port"],
                    status=instance["status"],
                    last_heartbeat=instance["last_heartbeat"],
                    load_score=instance["load_score"],
                    capabilities=instance["capabilities"],
                    metadata=instance["metadata"]
                )
                for instance in cluster_status["instances"]
            ],
            load_balancing_config=cluster_status["load_balancing_config"],
            connection_counts=cluster_status["connection_counts"],
            scaling_config={
                "current_replicas": current_replicas,
                "min_replicas": horizontal_scaler.min_replicas,
                "max_replicas": horizontal_scaler.max_replicas,
                "target_cpu_percent": horizontal_scaler.target_cpu_percent,
                "target_memory_percent": horizontal_scaler.target_memory_percent
            },
            metrics=scaling_metrics
        )
        
    except Exception as e:
        logger.error(f"Failed to get cluster status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cluster status: {str(e)}")


@router.get("/instances", response_model=List[ServiceInstanceResponse])
async def list_service_instances(current_user: dict = Depends(get_current_user)):
    """List all service instances in the cluster."""
    try:
        load_balancer = get_load_balancer()
        instances = await load_balancer.service_discovery.discover_instances()
        
        return [
            ServiceInstanceResponse(
                id=instance.id,
                host=instance.host,
                port=instance.port,
                status=instance.status,
                last_heartbeat=instance.last_heartbeat,
                load_score=instance.load_score,
                capabilities=instance.capabilities,
                metadata=instance.metadata
            )
            for instance in instances
        ]
        
    except Exception as e:
        logger.error(f"Failed to list service instances: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list service instances: {str(e)}")


@router.get("/instances/healthy", response_model=List[ServiceInstanceResponse])
async def list_healthy_instances(current_user: dict = Depends(get_current_user)):
    """List only healthy service instances."""
    try:
        load_balancer = get_load_balancer()
        instances = await load_balancer.service_discovery.get_healthy_instances()
        
        return [
            ServiceInstanceResponse(
                id=instance.id,
                host=instance.host,
                port=instance.port,
                status=instance.status,
                last_heartbeat=instance.last_heartbeat,
                load_score=instance.load_score,
                capabilities=instance.capabilities,
                metadata=instance.metadata
            )
            for instance in instances
        ]
        
    except Exception as e:
        logger.error(f"Failed to list healthy instances: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list healthy instances: {str(e)}")


@router.get("/metrics", response_model=ScalingMetricsResponse)
async def get_scaling_metrics(current_user: dict = Depends(get_current_user)):
    """Get current scaling metrics for the cluster."""
    try:
        horizontal_scaler = get_horizontal_scaler()
        metrics = await horizontal_scaler.get_current_metrics()
        current_replicas = await horizontal_scaler.get_current_replica_count()
        
        # Check scaling recommendations
        should_scale_up = await horizontal_scaler.should_scale_up()
        should_scale_down = await horizontal_scaler.should_scale_down()
        
        return ScalingMetricsResponse(
            cpu_usage=metrics["cpu_usage"],
            memory_usage=metrics["memory_usage"],
            request_rate=metrics["request_rate"],
            current_replicas=current_replicas,
            min_replicas=horizontal_scaler.min_replicas,
            max_replicas=horizontal_scaler.max_replicas,
            target_cpu_percent=horizontal_scaler.target_cpu_percent,
            target_memory_percent=horizontal_scaler.target_memory_percent,
            scaling_recommendation={
                "should_scale_up": should_scale_up,
                "should_scale_down": should_scale_down,
                "reason": (
                    "Scale up recommended due to high resource usage" if should_scale_up
                    else "Scale down recommended due to low resource usage" if should_scale_down
                    else "No scaling action recommended"
                )
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get scaling metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scaling metrics: {str(e)}")


@router.post("/scale")
async def manual_scale(
    request: ScalingActionRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Manually trigger scaling action."""
    try:
        horizontal_scaler = get_horizontal_scaler()
        
        if request.action == "up":
            current_replicas = await horizontal_scaler.get_current_replica_count()
            target_replicas = min(current_replicas + request.replicas, horizontal_scaler.max_replicas)
            
            if target_replicas == current_replicas:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot scale up: already at maximum replicas ({horizontal_scaler.max_replicas})"
                )
            
            success = await horizontal_scaler.scale_deployment(target_replicas)
            
        elif request.action == "down":
            current_replicas = await horizontal_scaler.get_current_replica_count()
            target_replicas = max(current_replicas - request.replicas, horizontal_scaler.min_replicas)
            
            if target_replicas == current_replicas:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot scale down: already at minimum replicas ({horizontal_scaler.min_replicas})"
                )
            
            success = await horizontal_scaler.scale_deployment(target_replicas)
            
        elif request.action == "set":
            if request.replicas < horizontal_scaler.min_replicas or request.replicas > horizontal_scaler.max_replicas:
                raise HTTPException(
                    status_code=400,
                    detail=f"Target replicas must be between {horizontal_scaler.min_replicas} and {horizontal_scaler.max_replicas}"
                )
            
            success = await horizontal_scaler.scale_deployment(request.replicas)
            target_replicas = request.replicas
            
        else:
            raise HTTPException(status_code=400, detail="Invalid scaling action. Use 'up', 'down', or 'set'")
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to execute scaling action")
        
        return {
            "message": f"Scaling action '{request.action}' executed successfully",
            "target_replicas": target_replicas,
            "action": request.action,
            "user": current_user.get("username", "unknown")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute scaling action: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute scaling action: {str(e)}")


@router.post("/auto-scale")
async def trigger_auto_scale(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Manually trigger auto-scaling evaluation."""
    try:
        horizontal_scaler = get_horizontal_scaler()
        result = await horizontal_scaler.auto_scale()
        
        return {
            "message": "Auto-scaling evaluation completed",
            "action_taken": result["action"],
            "current_replicas": result["current_replicas"],
            "new_replicas": result["new_replicas"],
            "metrics": result["metrics"],
            "thresholds": result["thresholds"]
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger auto-scaling: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger auto-scaling: {str(e)}")


@router.get("/load-balancing/config")
async def get_load_balancing_config(current_user: dict = Depends(get_current_user)):
    """Get current load balancing configuration."""
    try:
        load_balancer = get_load_balancer()
        config = load_balancer.config
        
        return {
            "algorithm": config.algorithm,
            "health_check_interval": config.health_check_interval,
            "max_retries": config.max_retries,
            "timeout_seconds": config.timeout_seconds,
            "sticky_sessions": config.sticky_sessions,
            "session_affinity_timeout": config.session_affinity_timeout
        }
        
    except Exception as e:
        logger.error(f"Failed to get load balancing config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get load balancing config: {str(e)}")


@router.put("/load-balancing/config")
async def update_load_balancing_config(
    request: LoadBalancingConfigRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update load balancing configuration."""
    try:
        load_balancer = get_load_balancer()
        
        # Validate algorithm
        valid_algorithms = ["round_robin", "weighted_round_robin", "least_connections"]
        if request.algorithm not in valid_algorithms:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid algorithm. Must be one of: {valid_algorithms}"
            )
        
        # Update configuration
        load_balancer.config = LoadBalancingConfig(
            algorithm=request.algorithm,
            health_check_interval=request.health_check_interval,
            max_retries=request.max_retries,
            timeout_seconds=request.timeout_seconds,
            sticky_sessions=request.sticky_sessions,
            session_affinity_timeout=request.session_affinity_timeout
        )
        
        return {
            "message": "Load balancing configuration updated successfully",
            "config": {
                "algorithm": load_balancer.config.algorithm,
                "health_check_interval": load_balancer.config.health_check_interval,
                "max_retries": load_balancer.config.max_retries,
                "timeout_seconds": load_balancer.config.timeout_seconds,
                "sticky_sessions": load_balancer.config.sticky_sessions,
                "session_affinity_timeout": load_balancer.config.session_affinity_timeout
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update load balancing config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update load balancing config: {str(e)}")


@router.post("/service-discovery/refresh")
async def refresh_service_discovery(current_user: dict = Depends(get_current_user)):
    """Manually refresh service discovery."""
    try:
        load_balancer = get_load_balancer()
        
        # Reset last discovery time to force refresh
        load_balancer.service_discovery.last_discovery = load_balancer.service_discovery.last_discovery.min
        
        instances = await load_balancer.service_discovery.discover_instances()
        
        return {
            "message": "Service discovery refreshed successfully",
            "discovered_instances": len(instances),
            "healthy_instances": len([i for i in instances if i.status == "healthy"]),
            "instances": [
                {
                    "id": instance.id,
                    "host": instance.host,
                    "port": instance.port,
                    "status": instance.status,
                    "load_score": instance.load_score
                }
                for instance in instances
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to refresh service discovery: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh service discovery: {str(e)}")


@router.get("/health")
async def cluster_health_check():
    """Simple health check for the cluster management system."""
    try:
        load_balancer = get_load_balancer()
        horizontal_scaler = get_horizontal_scaler()
        
        # Quick health checks
        instances = await load_balancer.service_discovery.get_healthy_instances()
        current_replicas = await horizontal_scaler.get_current_replica_count()
        
        status = "healthy" if len(instances) > 0 else "unhealthy"
        
        return {
            "status": status,
            "healthy_instances": len(instances),
            "current_replicas": current_replicas,
            "timestamp": "2025-10-01T00:00:00Z"  # Would use actual timestamp
        }
        
    except Exception as e:
        logger.error(f"Cluster health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2025-10-01T00:00:00Z"  # Would use actual timestamp
        }