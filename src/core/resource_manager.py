"""
Resource Management and Allocation System for MicroVM Sandbox.

This module provides comprehensive resource management including:
- CPU and memory resource allocation
- Resource limits and quotas enforcement
- System resource monitoring
- Resource optimization algorithms
- Automatic resource scaling
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import psutil
import json

from src.utils.config import get_config


logger = logging.getLogger(__name__)


@dataclass
class ResourceQuota:
    """Resource quota configuration for VMs."""
    max_vcpus: int
    max_memory_mb: int
    max_disk_gb: int
    max_vms: int
    priority: int = 1  # 1-10, higher is more priority


@dataclass
class ResourceAllocation:
    """Current resource allocation for a VM."""
    vm_name: str
    vcpus: int
    memory_mb: int
    disk_gb: int
    allocated_at: datetime
    last_updated: datetime
    priority: int = 1
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0


@dataclass
class SystemResourceUsage:
    """Current system resource usage."""
    total_vcpus: int
    available_vcpus: int
    used_vcpus: int
    total_memory_mb: int
    available_memory_mb: int
    used_memory_mb: int
    total_disk_gb: int
    available_disk_gb: int
    used_disk_gb: int
    active_vms: int
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    load_average: List[float]
    timestamp: datetime


@dataclass
class ResourceRecommendation:
    """Resource allocation recommendation."""
    vm_name: str
    recommended_vcpus: int
    recommended_memory_mb: int
    current_vcpus: int
    current_memory_mb: int
    reason: str
    urgency: str  # low, medium, high, critical
    estimated_savings_percent: float = 0.0


class ResourceManager:
    """Comprehensive resource management system."""
    
    def __init__(self, config_manager=None):
        """Initialize resource manager."""
        self.config = config_manager or get_config()
        self.allocations: Dict[str, ResourceAllocation] = {}
        self.quotas: Dict[str, ResourceQuota] = {}
        self.monitoring_enabled = True
        self.optimization_enabled = True
        self.scaling_enabled = True
        
        # Resource limits from configuration
        self.system_limits = ResourceQuota(
            max_vcpus=self.config.get("resources", {}).get("max_vcpus_per_vm", 8),
            max_memory_mb=self.config.get("resources", {}).get("max_memory_per_vm", 8192),
            max_disk_gb=self.config.get("resources", {}).get("max_disk_per_vm", 100),
            max_vms=self.config.get("resources", {}).get("max_vms", 50)
        )
        
        # Default quotas
        self.default_quota = ResourceQuota(
            max_vcpus=4,
            max_memory_mb=2048,
            max_disk_gb=20,
            max_vms=5,
            priority=1
        )
        
        # Resource monitoring history
        self.usage_history: List[SystemResourceUsage] = []
        self.max_history_size = 1000
        
        # Optimization thresholds
        self.optimization_thresholds = {
            "cpu_underutilization": 10.0,  # % CPU usage
            "memory_underutilization": 20.0,  # % Memory usage
            "cpu_overutilization": 90.0,
            "memory_overutilization": 85.0,
            "resource_pressure": 80.0  # % of total system resources
        }
        
        logger.info("ResourceManager initialized with system limits: %s", self.system_limits)
    
    async def get_system_resources(self) -> SystemResourceUsage:
        """Get current system resource usage."""
        try:
            # CPU information
            cpu_count = psutil.cpu_count(logical=True)
            cpu_usage = psutil.cpu_percent(interval=1)
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0.0, 0.0, 0.0]
            
            # Memory information
            memory = psutil.virtual_memory()
            total_memory_mb = memory.total // (1024 * 1024)
            available_memory_mb = memory.available // (1024 * 1024)
            used_memory_mb = total_memory_mb - available_memory_mb
            
            # Disk information
            disk = psutil.disk_usage('/')
            total_disk_gb = disk.total // (1024 * 1024 * 1024)
            available_disk_gb = disk.free // (1024 * 1024 * 1024)
            used_disk_gb = total_disk_gb - available_disk_gb
            
            # Calculate allocated resources
            allocated_vcpus = sum(alloc.vcpus for alloc in self.allocations.values())
            allocated_memory_mb = sum(alloc.memory_mb for alloc in self.allocations.values())
            allocated_disk_gb = sum(alloc.disk_gb for alloc in self.allocations.values())
            
            usage = SystemResourceUsage(
                total_vcpus=cpu_count,
                available_vcpus=max(0, cpu_count - allocated_vcpus),
                used_vcpus=allocated_vcpus,
                total_memory_mb=total_memory_mb,
                available_memory_mb=max(0, available_memory_mb - allocated_memory_mb),
                used_memory_mb=used_memory_mb + allocated_memory_mb,
                total_disk_gb=total_disk_gb,
                available_disk_gb=max(0, available_disk_gb - allocated_disk_gb),
                used_disk_gb=used_disk_gb + allocated_disk_gb,
                active_vms=len(self.allocations),
                cpu_usage_percent=cpu_usage,
                memory_usage_percent=(used_memory_mb / total_memory_mb) * 100,
                disk_usage_percent=(used_disk_gb / total_disk_gb) * 100,
                load_average=list(load_avg),
                timestamp=datetime.now()
            )
            
            # Store in history
            if self.monitoring_enabled:
                self.usage_history.append(usage)
                if len(self.usage_history) > self.max_history_size:
                    self.usage_history.pop(0)
            
            return usage
        except Exception as e:
            logger.error("Failed to get system resources: %s", e)
            raise
    
    async def allocate_resources(self, vm_name: str, vcpus: int, memory_mb: int, 
                               disk_gb: int = 10, priority: int = 1, 
                               user_quota: Optional[ResourceQuota] = None) -> bool:
        """Allocate resources for a VM with quota enforcement."""
        try:
            # Get current system usage
            system_usage = await self.get_system_resources()
            
            # Check if VM already has allocation
            if vm_name in self.allocations:
                logger.warning("VM %s already has resource allocation", vm_name)
                return False
            
            # Determine effective quota
            effective_quota = user_quota or self.default_quota
            
            # Validate against quota limits
            if not self._validate_against_quota(vcpus, memory_mb, disk_gb, effective_quota):
                logger.error("Resource request exceeds quota limits for VM %s", vm_name)
                return False
            
            # Validate against system limits
            if not self._validate_against_system_limits(vcpus, memory_mb, disk_gb):
                logger.error("Resource request exceeds system limits for VM %s", vm_name)
                return False
            
            # Check resource availability
            if not self._check_resource_availability(system_usage, vcpus, memory_mb, disk_gb):
                logger.error("Insufficient system resources for VM %s", vm_name)
                return False
            
            # Check VM count limits
            if len(self.allocations) >= self.system_limits.max_vms:
                logger.error("Maximum VM limit reached: %d", self.system_limits.max_vms)
                return False
            
            # Create allocation
            allocation = ResourceAllocation(
                vm_name=vm_name,
                vcpus=vcpus,
                memory_mb=memory_mb,
                disk_gb=disk_gb,
                allocated_at=datetime.now(),
                last_updated=datetime.now(),
                priority=priority
            )
            
            self.allocations[vm_name] = allocation
            logger.info("Allocated resources for VM %s: %d vCPUs, %d MB RAM, %d GB disk", 
                       vm_name, vcpus, memory_mb, disk_gb)
            
            return True
            
        except Exception as e:
            logger.error("Failed to allocate resources for VM %s: %s", vm_name, e)
            return False
    
    async def deallocate_resources(self, vm_name: str) -> bool:
        """Deallocate resources for a VM."""
        try:
            if vm_name not in self.allocations:
                logger.warning("No resource allocation found for VM %s", vm_name)
                return False
            
            allocation = self.allocations.pop(vm_name)
            logger.info("Deallocated resources for VM %s: %d vCPUs, %d MB RAM, %d GB disk",
                       vm_name, allocation.vcpus, allocation.memory_mb, allocation.disk_gb)
            
            return True
            
        except Exception as e:
            logger.error("Failed to deallocate resources for VM %s: %s", vm_name, e)
            return False
    
    async def update_vm_usage(self, vm_name: str, cpu_usage_percent: float, 
                            memory_usage_percent: float) -> bool:
        """Update VM resource usage statistics."""
        try:
            if vm_name not in self.allocations:
                logger.warning("No allocation found for VM %s", vm_name)
                return False
            
            allocation = self.allocations[vm_name]
            allocation.cpu_usage_percent = cpu_usage_percent
            allocation.memory_usage_percent = memory_usage_percent
            allocation.last_updated = datetime.now()
            
            return True
            
        except Exception as e:
            logger.error("Failed to update usage for VM %s: %s", vm_name, e)
            return False
    
    async def resize_vm_resources(self, vm_name: str, new_vcpus: Optional[int] = None,
                                new_memory_mb: Optional[int] = None) -> bool:
        """Resize VM resources if possible."""
        try:
            if vm_name not in self.allocations:
                logger.error("No allocation found for VM %s", vm_name)
                return False
            
            allocation = self.allocations[vm_name]
            current_vcpus = allocation.vcpus
            current_memory = allocation.memory_mb
            
            # Calculate new resource requirements
            target_vcpus = new_vcpus if new_vcpus is not None else current_vcpus
            target_memory = new_memory_mb if new_memory_mb is not None else current_memory
            
            # Validate new requirements
            if not self._validate_against_system_limits(target_vcpus, target_memory, allocation.disk_gb):
                logger.error("New resource requirements exceed system limits for VM %s", vm_name)
                return False
            
            # Check if we're increasing resources - need to check availability
            if target_vcpus > current_vcpus or target_memory > current_memory:
                # Temporarily remove current allocation to check availability
                temp_allocation = self.allocations.pop(vm_name)
                system_usage = await self.get_system_resources()
                
                if not self._check_resource_availability(system_usage, target_vcpus, target_memory, allocation.disk_gb):
                    # Restore allocation and fail
                    self.allocations[vm_name] = temp_allocation
                    logger.error("Insufficient resources for VM %s resize", vm_name)
                    return False
                
                # Restore allocation with new values
                self.allocations[vm_name] = temp_allocation
            
            # Update allocation
            allocation.vcpus = target_vcpus
            allocation.memory_mb = target_memory
            allocation.last_updated = datetime.now()
            
            logger.info("Resized VM %s resources: %d vCPUs, %d MB RAM", 
                       vm_name, target_vcpus, target_memory)
            
            return True
            
        except Exception as e:
            logger.error("Failed to resize resources for VM %s: %s", vm_name, e)
            return False
    
    async def get_resource_recommendations(self) -> List[ResourceRecommendation]:
        """Generate resource optimization recommendations."""
        recommendations = []
        
        try:
            if not self.optimization_enabled:
                return recommendations
            
            system_usage = await self.get_system_resources()
            
            for vm_name, allocation in self.allocations.items():
                recommendation = await self._analyze_vm_optimization(allocation, system_usage)
                if recommendation:
                    recommendations.append(recommendation)
            
            # Sort by urgency and potential savings
            urgency_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            recommendations.sort(
                key=lambda r: (urgency_order.get(r.urgency, 0), r.estimated_savings_percent),
                reverse=True
            )
            
            return recommendations
            
        except Exception as e:
            logger.error("Failed to generate resource recommendations: %s", e)
            return []
    
    async def auto_scale_resources(self) -> List[str]:
        """Automatically scale VM resources based on usage patterns."""
        scaled_vms = []
        
        try:
            if not self.scaling_enabled:
                return scaled_vms
            
            recommendations = await self.get_resource_recommendations()
            
            for rec in recommendations:
                if rec.urgency in ["critical", "high"]:
                    # Apply automatic scaling for critical/high priority recommendations
                    success = await self.resize_vm_resources(
                        rec.vm_name, 
                        rec.recommended_vcpus, 
                        rec.recommended_memory_mb
                    )
                    
                    if success:
                        scaled_vms.append(rec.vm_name)
                        logger.info("Auto-scaled VM %s: %s", rec.vm_name, rec.reason)
            
            return scaled_vms
            
        except Exception as e:
            logger.error("Failed to auto-scale resources: %s", e)
            return []
    
    async def get_allocation(self, vm_name: str) -> Optional[ResourceAllocation]:
        """Get resource allocation for a VM."""
        return self.allocations.get(vm_name)
    
    async def list_allocations(self) -> List[ResourceAllocation]:
        """List all current resource allocations."""
        return list(self.allocations.values())
    
    async def set_quota(self, user_id: str, quota: ResourceQuota) -> bool:
        """Set resource quota for a user."""
        try:
            self.quotas[user_id] = quota
            logger.info("Set quota for user %s: %s", user_id, quota)
            return True
        except Exception as e:
            logger.error("Failed to set quota for user %s: %s", user_id, e)
            return False
    
    async def get_quota(self, user_id: str) -> ResourceQuota:
        """Get resource quota for a user."""
        return self.quotas.get(user_id, self.default_quota)
    
    def _validate_against_quota(self, vcpus: int, memory_mb: int, disk_gb: int, 
                              quota: ResourceQuota) -> bool:
        """Validate resource request against quota."""
        return (vcpus <= quota.max_vcpus and 
                memory_mb <= quota.max_memory_mb and 
                disk_gb <= quota.max_disk_gb)
    
    def _validate_against_system_limits(self, vcpus: int, memory_mb: int, disk_gb: int) -> bool:
        """Validate resource request against system limits."""
        return (vcpus <= self.system_limits.max_vcpus and 
                memory_mb <= self.system_limits.max_memory_mb and 
                disk_gb <= self.system_limits.max_disk_gb)
    
    def _check_resource_availability(self, system_usage: SystemResourceUsage, 
                                   vcpus: int, memory_mb: int, disk_gb: int) -> bool:
        """Check if requested resources are available."""
        return (vcpus <= system_usage.available_vcpus and 
                memory_mb <= system_usage.available_memory_mb and 
                disk_gb <= system_usage.available_disk_gb)
    
    async def _analyze_vm_optimization(self, allocation: ResourceAllocation, 
                                     system_usage: SystemResourceUsage) -> Optional[ResourceRecommendation]:
        """Analyze VM for optimization opportunities."""
        try:
            current_cpu_usage = allocation.cpu_usage_percent
            current_memory_usage = allocation.memory_usage_percent
            
            # Determine if VM is under or over-utilized
            cpu_underutilized = current_cpu_usage < self.optimization_thresholds["cpu_underutilization"]
            memory_underutilized = current_memory_usage < self.optimization_thresholds["memory_underutilization"]
            cpu_overutilized = current_cpu_usage > self.optimization_thresholds["cpu_overutilization"]
            memory_overutilized = current_memory_usage > self.optimization_thresholds["memory_overutilization"]
            
            # Check system pressure
            system_pressure = (
                (system_usage.used_vcpus / system_usage.total_vcpus * 100) > 
                self.optimization_thresholds["resource_pressure"]
            )
            
            recommendation = None
            
            # Generate recommendations based on usage patterns
            if cpu_underutilized and memory_underutilized and system_pressure:
                # Scale down
                new_vcpus = max(1, allocation.vcpus - 1)
                new_memory = max(512, int(allocation.memory_mb * 0.8))
                urgency = "high" if system_pressure else "medium"
                reason = f"VM underutilized (CPU: {current_cpu_usage:.1f}%, RAM: {current_memory_usage:.1f}%) during system pressure"
                
                recommendation = ResourceRecommendation(
                    vm_name=allocation.vm_name,
                    recommended_vcpus=new_vcpus,
                    recommended_memory_mb=new_memory,
                    current_vcpus=allocation.vcpus,
                    current_memory_mb=allocation.memory_mb,
                    reason=reason,
                    urgency=urgency,
                    estimated_savings_percent=((allocation.vcpus - new_vcpus) / allocation.vcpus * 100)
                )
                
            elif cpu_overutilized or memory_overutilized:
                # Scale up
                new_vcpus = min(self.system_limits.max_vcpus, allocation.vcpus + 1) if cpu_overutilized else allocation.vcpus
                new_memory = min(self.system_limits.max_memory_mb, int(allocation.memory_mb * 1.2)) if memory_overutilized else allocation.memory_mb
                urgency = "critical" if (cpu_overutilized and memory_overutilized) else "high"
                reason = f"VM overutilized (CPU: {current_cpu_usage:.1f}%, RAM: {current_memory_usage:.1f}%)"
                
                recommendation = ResourceRecommendation(
                    vm_name=allocation.vm_name,
                    recommended_vcpus=new_vcpus,
                    recommended_memory_mb=new_memory,
                    current_vcpus=allocation.vcpus,
                    current_memory_mb=allocation.memory_mb,
                    reason=reason,
                    urgency=urgency,
                    estimated_savings_percent=0.0  # This is a scale-up
                )
            
            return recommendation
            
        except Exception as e:
            logger.error("Failed to analyze VM optimization for %s: %s", allocation.vm_name, e)
            return None
    
    async def export_metrics(self) -> Dict[str, Any]:
        """Export resource management metrics."""
        try:
            system_usage = await self.get_system_resources()
            
            return {
                "system_usage": {
                    "total_vcpus": system_usage.total_vcpus,
                    "used_vcpus": system_usage.used_vcpus,
                    "total_memory_mb": system_usage.total_memory_mb,
                    "used_memory_mb": system_usage.used_memory_mb,
                    "total_disk_gb": system_usage.total_disk_gb,
                    "used_disk_gb": system_usage.used_disk_gb,
                    "active_vms": system_usage.active_vms,
                    "cpu_usage_percent": system_usage.cpu_usage_percent,
                    "memory_usage_percent": system_usage.memory_usage_percent,
                    "disk_usage_percent": system_usage.disk_usage_percent,
                    "load_average": system_usage.load_average
                },
                "allocations": [
                    {
                        "vm_name": alloc.vm_name,
                        "vcpus": alloc.vcpus,
                        "memory_mb": alloc.memory_mb,
                        "disk_gb": alloc.disk_gb,
                        "priority": alloc.priority,
                        "cpu_usage_percent": alloc.cpu_usage_percent,
                        "memory_usage_percent": alloc.memory_usage_percent,
                        "allocated_at": alloc.allocated_at.isoformat(),
                        "last_updated": alloc.last_updated.isoformat()
                    }
                    for alloc in self.allocations.values()
                ],
                "quotas": {
                    user_id: {
                        "max_vcpus": quota.max_vcpus,
                        "max_memory_mb": quota.max_memory_mb,
                        "max_disk_gb": quota.max_disk_gb,
                        "max_vms": quota.max_vms,
                        "priority": quota.priority
                    }
                    for user_id, quota in self.quotas.items()
                },
                "optimization_enabled": self.optimization_enabled,
                "scaling_enabled": self.scaling_enabled,
                "monitoring_enabled": self.monitoring_enabled
            }
            
        except Exception as e:
            logger.error("Failed to export resource metrics: %s", e)
            return {}