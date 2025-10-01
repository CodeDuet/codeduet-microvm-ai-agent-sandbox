"""
Resource Management API routes.

This module provides REST API endpoints for:
- Resource allocation and deallocation
- Resource quotas management
- System resource monitoring
- Resource optimization recommendations
- Automatic resource scaling
"""

import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Path, Query
from fastapi.responses import JSONResponse

from src.api.models.vm import (
    ResourceQuotaRequest,
    ResourceQuotaResponse,
    ResourceAllocationRequest,
    ResourceAllocationResponse,
    ResourceUsageUpdateRequest,
    SystemResourceUsageResponse,
    ResourceRecommendationResponse,
    ResourceRecommendationsResponse,
    ResourceResizeRequest,
    ResourceMetricsResponse,
    AutoScaleResponse
)
from src.core.resource_manager import ResourceManager, ResourceQuota
from src.utils.config import get_config


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/resources", tags=["resources"])


async def get_resource_manager() -> ResourceManager:
    """Dependency to get resource manager instance."""
    config = get_config()
    return ResourceManager(config)


@router.get("/system/usage", response_model=SystemResourceUsageResponse)
async def get_system_usage(
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Get current system resource usage."""
    try:
        usage = await resource_manager.get_system_resources()
        
        return SystemResourceUsageResponse(
            total_vcpus=usage.total_vcpus,
            available_vcpus=usage.available_vcpus,
            used_vcpus=usage.used_vcpus,
            total_memory_mb=usage.total_memory_mb,
            available_memory_mb=usage.available_memory_mb,
            used_memory_mb=usage.used_memory_mb,
            total_disk_gb=usage.total_disk_gb,
            available_disk_gb=usage.available_disk_gb,
            used_disk_gb=usage.used_disk_gb,
            active_vms=usage.active_vms,
            cpu_usage_percent=usage.cpu_usage_percent,
            memory_usage_percent=usage.memory_usage_percent,
            disk_usage_percent=usage.disk_usage_percent,
            load_average=usage.load_average,
            timestamp=usage.timestamp
        )
        
    except Exception as e:
        logger.error("Failed to get system usage: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to get system usage: {str(e)}")


@router.post("/allocate/{vm_name}", response_model=ResourceAllocationResponse)
async def allocate_resources(
    vm_name: str = Path(..., description="VM name"),
    request: ResourceAllocationRequest = ...,
    user_id: str = Query(default="default", description="User ID for quota enforcement"),
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Allocate resources for a VM."""
    try:
        # Get user quota
        user_quota = await resource_manager.get_quota(user_id)
        
        # Attempt allocation
        success = await resource_manager.allocate_resources(
            vm_name=vm_name,
            vcpus=request.vcpus,
            memory_mb=request.memory_mb,
            disk_gb=request.disk_gb,
            priority=request.priority,
            user_quota=user_quota
        )
        
        if not success:
            raise HTTPException(
                status_code=400, 
                detail="Failed to allocate resources - insufficient resources or quota exceeded"
            )
        
        # Get the allocation
        allocation = await resource_manager.get_allocation(vm_name)
        if not allocation:
            raise HTTPException(status_code=500, detail="Allocation failed unexpectedly")
        
        return ResourceAllocationResponse(
            vm_name=allocation.vm_name,
            vcpus=allocation.vcpus,
            memory_mb=allocation.memory_mb,
            disk_gb=allocation.disk_gb,
            priority=allocation.priority,
            cpu_usage_percent=allocation.cpu_usage_percent,
            memory_usage_percent=allocation.memory_usage_percent,
            allocated_at=allocation.allocated_at,
            last_updated=allocation.last_updated
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to allocate resources for VM %s: %s", vm_name, e)
        raise HTTPException(status_code=500, detail=f"Failed to allocate resources: {str(e)}")


@router.delete("/deallocate/{vm_name}")
async def deallocate_resources(
    vm_name: str = Path(..., description="VM name"),
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Deallocate resources for a VM."""
    try:
        success = await resource_manager.deallocate_resources(vm_name)
        
        if not success:
            raise HTTPException(
                status_code=404, 
                detail=f"No resource allocation found for VM {vm_name}"
            )
        
        return {"message": f"Resources deallocated for VM {vm_name}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to deallocate resources for VM %s: %s", vm_name, e)
        raise HTTPException(status_code=500, detail=f"Failed to deallocate resources: {str(e)}")


@router.get("/allocations", response_model=List[ResourceAllocationResponse])
async def list_allocations(
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """List all current resource allocations."""
    try:
        allocations = await resource_manager.list_allocations()
        
        return [
            ResourceAllocationResponse(
                vm_name=allocation.vm_name,
                vcpus=allocation.vcpus,
                memory_mb=allocation.memory_mb,
                disk_gb=allocation.disk_gb,
                priority=allocation.priority,
                cpu_usage_percent=allocation.cpu_usage_percent,
                memory_usage_percent=allocation.memory_usage_percent,
                allocated_at=allocation.allocated_at,
                last_updated=allocation.last_updated
            )
            for allocation in allocations
        ]
        
    except Exception as e:
        logger.error("Failed to list allocations: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to list allocations: {str(e)}")


@router.get("/allocations/{vm_name}", response_model=ResourceAllocationResponse)
async def get_allocation(
    vm_name: str = Path(..., description="VM name"),
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Get resource allocation for a specific VM."""
    try:
        allocation = await resource_manager.get_allocation(vm_name)
        
        if not allocation:
            raise HTTPException(
                status_code=404, 
                detail=f"No resource allocation found for VM {vm_name}"
            )
        
        return ResourceAllocationResponse(
            vm_name=allocation.vm_name,
            vcpus=allocation.vcpus,
            memory_mb=allocation.memory_mb,
            disk_gb=allocation.disk_gb,
            priority=allocation.priority,
            cpu_usage_percent=allocation.cpu_usage_percent,
            memory_usage_percent=allocation.memory_usage_percent,
            allocated_at=allocation.allocated_at,
            last_updated=allocation.last_updated
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get allocation for VM %s: %s", vm_name, e)
        raise HTTPException(status_code=500, detail=f"Failed to get allocation: {str(e)}")


@router.put("/allocations/{vm_name}/usage")
async def update_vm_usage(
    vm_name: str = Path(..., description="VM name"),
    request: ResourceUsageUpdateRequest = ...,
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Update VM resource usage statistics."""
    try:
        success = await resource_manager.update_vm_usage(
            vm_name=vm_name,
            cpu_usage_percent=request.cpu_usage_percent,
            memory_usage_percent=request.memory_usage_percent
        )
        
        if not success:
            raise HTTPException(
                status_code=404, 
                detail=f"No resource allocation found for VM {vm_name}"
            )
        
        return {"message": f"Usage updated for VM {vm_name}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update usage for VM %s: %s", vm_name, e)
        raise HTTPException(status_code=500, detail=f"Failed to update usage: {str(e)}")


@router.put("/allocations/{vm_name}/resize", response_model=ResourceAllocationResponse)
async def resize_vm_resources(
    vm_name: str = Path(..., description="VM name"),
    request: ResourceResizeRequest = ...,
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Resize VM resources."""
    try:
        success = await resource_manager.resize_vm_resources(
            vm_name=vm_name,
            new_vcpus=request.new_vcpus,
            new_memory_mb=request.new_memory_mb
        )
        
        if not success:
            raise HTTPException(
                status_code=400, 
                detail="Failed to resize VM resources - insufficient resources or VM not found"
            )
        
        # Get updated allocation
        allocation = await resource_manager.get_allocation(vm_name)
        if not allocation:
            raise HTTPException(status_code=500, detail="Resize failed unexpectedly")
        
        return ResourceAllocationResponse(
            vm_name=allocation.vm_name,
            vcpus=allocation.vcpus,
            memory_mb=allocation.memory_mb,
            disk_gb=allocation.disk_gb,
            priority=allocation.priority,
            cpu_usage_percent=allocation.cpu_usage_percent,
            memory_usage_percent=allocation.memory_usage_percent,
            allocated_at=allocation.allocated_at,
            last_updated=allocation.last_updated
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to resize resources for VM %s: %s", vm_name, e)
        raise HTTPException(status_code=500, detail=f"Failed to resize resources: {str(e)}")


@router.post("/quotas/{user_id}", response_model=ResourceQuotaResponse)
async def set_user_quota(
    user_id: str = Path(..., description="User ID"),
    request: ResourceQuotaRequest = ...,
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Set resource quota for a user."""
    try:
        quota = ResourceQuota(
            max_vcpus=request.max_vcpus,
            max_memory_mb=request.max_memory_mb,
            max_disk_gb=request.max_disk_gb,
            max_vms=request.max_vms,
            priority=request.priority
        )
        
        success = await resource_manager.set_quota(user_id, quota)
        
        if not success:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to set quota for user {user_id}"
            )
        
        return ResourceQuotaResponse(
            max_vcpus=quota.max_vcpus,
            max_memory_mb=quota.max_memory_mb,
            max_disk_gb=quota.max_disk_gb,
            max_vms=quota.max_vms,
            priority=quota.priority
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to set quota for user %s: %s", user_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to set quota: {str(e)}")


@router.get("/quotas/{user_id}", response_model=ResourceQuotaResponse)
async def get_user_quota(
    user_id: str = Path(..., description="User ID"),
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Get resource quota for a user."""
    try:
        quota = await resource_manager.get_quota(user_id)
        
        return ResourceQuotaResponse(
            max_vcpus=quota.max_vcpus,
            max_memory_mb=quota.max_memory_mb,
            max_disk_gb=quota.max_disk_gb,
            max_vms=quota.max_vms,
            priority=quota.priority
        )
        
    except Exception as e:
        logger.error("Failed to get quota for user %s: %s", user_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to get quota: {str(e)}")


@router.get("/recommendations", response_model=ResourceRecommendationsResponse)
async def get_resource_recommendations(
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Get resource optimization recommendations."""
    try:
        recommendations = await resource_manager.get_resource_recommendations()
        
        recommendation_responses = [
            ResourceRecommendationResponse(
                vm_name=rec.vm_name,
                recommended_vcpus=rec.recommended_vcpus,
                recommended_memory_mb=rec.recommended_memory_mb,
                current_vcpus=rec.current_vcpus,
                current_memory_mb=rec.current_memory_mb,
                reason=rec.reason,
                urgency=rec.urgency,
                estimated_savings_percent=rec.estimated_savings_percent
            )
            for rec in recommendations
        ]
        
        return ResourceRecommendationsResponse(
            recommendations=recommendation_responses,
            generated_at=datetime.now()
        )
        
    except Exception as e:
        logger.error("Failed to get resource recommendations: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.post("/auto-scale", response_model=AutoScaleResponse)
async def auto_scale_resources(
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Automatically scale VM resources based on usage patterns."""
    try:
        scaled_vms = await resource_manager.auto_scale_resources()
        
        return AutoScaleResponse(
            scaled_vms=scaled_vms,
            total_scaled=len(scaled_vms),
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error("Failed to auto-scale resources: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to auto-scale: {str(e)}")


@router.get("/metrics", response_model=ResourceMetricsResponse)
async def get_resource_metrics(
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Get comprehensive resource management metrics."""
    try:
        metrics = await resource_manager.export_metrics()
        
        # Convert system usage
        system_usage_data = metrics["system_usage"]
        system_usage = SystemResourceUsageResponse(
            total_vcpus=system_usage_data["total_vcpus"],
            available_vcpus=system_usage_data["total_vcpus"] - system_usage_data["used_vcpus"],
            used_vcpus=system_usage_data["used_vcpus"],
            total_memory_mb=system_usage_data["total_memory_mb"],
            available_memory_mb=system_usage_data["total_memory_mb"] - system_usage_data["used_memory_mb"],
            used_memory_mb=system_usage_data["used_memory_mb"],
            total_disk_gb=system_usage_data["total_disk_gb"],
            available_disk_gb=system_usage_data["total_disk_gb"] - system_usage_data["used_disk_gb"],
            used_disk_gb=system_usage_data["used_disk_gb"],
            active_vms=system_usage_data["active_vms"],
            cpu_usage_percent=system_usage_data["cpu_usage_percent"],
            memory_usage_percent=system_usage_data["memory_usage_percent"],
            disk_usage_percent=system_usage_data["disk_usage_percent"],
            load_average=system_usage_data["load_average"],
            timestamp=datetime.now()
        )
        
        # Convert allocations
        allocations = [
            ResourceAllocationResponse(
                vm_name=alloc["vm_name"],
                vcpus=alloc["vcpus"],
                memory_mb=alloc["memory_mb"],
                disk_gb=alloc["disk_gb"],
                priority=alloc["priority"],
                cpu_usage_percent=alloc["cpu_usage_percent"],
                memory_usage_percent=alloc["memory_usage_percent"],
                allocated_at=datetime.fromisoformat(alloc["allocated_at"]),
                last_updated=datetime.fromisoformat(alloc["last_updated"])
            )
            for alloc in metrics["allocations"]
        ]
        
        # Convert quotas
        quotas = {
            user_id: ResourceQuotaResponse(
                max_vcpus=quota["max_vcpus"],
                max_memory_mb=quota["max_memory_mb"],
                max_disk_gb=quota["max_disk_gb"],
                max_vms=quota["max_vms"],
                priority=quota["priority"]
            )
            for user_id, quota in metrics["quotas"].items()
        }
        
        return ResourceMetricsResponse(
            system_usage=system_usage,
            allocations=allocations,
            quotas=quotas,
            optimization_enabled=metrics["optimization_enabled"],
            scaling_enabled=metrics["scaling_enabled"],
            monitoring_enabled=metrics["monitoring_enabled"]
        )
        
    except Exception as e:
        logger.error("Failed to get resource metrics: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.post("/optimization/enable")
async def enable_optimization(
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Enable resource optimization."""
    try:
        resource_manager.optimization_enabled = True
        return {"message": "Resource optimization enabled"}
        
    except Exception as e:
        logger.error("Failed to enable optimization: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to enable optimization: {str(e)}")


@router.post("/optimization/disable")
async def disable_optimization(
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Disable resource optimization."""
    try:
        resource_manager.optimization_enabled = False
        return {"message": "Resource optimization disabled"}
        
    except Exception as e:
        logger.error("Failed to disable optimization: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to disable optimization: {str(e)}")


@router.post("/scaling/enable")
async def enable_scaling(
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Enable automatic resource scaling."""
    try:
        resource_manager.scaling_enabled = True
        return {"message": "Automatic resource scaling enabled"}
        
    except Exception as e:
        logger.error("Failed to enable scaling: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to enable scaling: {str(e)}")


@router.post("/scaling/disable")
async def disable_scaling(
    resource_manager: ResourceManager = Depends(get_resource_manager)
):
    """Disable automatic resource scaling."""
    try:
        resource_manager.scaling_enabled = False
        return {"message": "Automatic resource scaling disabled"}
        
    except Exception as e:
        logger.error("Failed to disable scaling: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to disable scaling: {str(e)}")