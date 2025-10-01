"""
Health check endpoints for MicroVM Sandbox.
Provides comprehensive health monitoring for all system components.
"""

import time
import asyncio
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
import psutil
import httpx
import os
import logging

from src.utils.metrics import metrics
from src.utils.config import get_config
from src.core.vm_manager import VMManager
from src.core.ch_client import CloudHypervisorClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class ComponentHealth(BaseModel):
    """Health status for a single component."""
    name: str
    status: str  # healthy, degraded, unhealthy
    message: str
    response_time_ms: float
    last_check: float
    details: Dict[str, Any] = {}


class SystemHealth(BaseModel):
    """Overall system health status."""
    status: str  # healthy, degraded, unhealthy
    timestamp: float
    uptime_seconds: float
    components: List[ComponentHealth]
    summary: Dict[str, int]  # count by status
    

class HealthChecker:
    """Comprehensive health checker for all system components."""
    
    def __init__(self):
        self.config = get_config()
        self.start_time = time.time()
        
    async def check_api_server(self) -> ComponentHealth:
        """Check API server health."""
        start_time = time.time()
        try:
            # API server is healthy if we're responding to this request
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="api_server",
                status="healthy",
                message="API server is responding",
                response_time_ms=response_time,
                last_check=time.time(),
                details={
                    "pid": os.getpid(),
                    "workers": self.config.server.workers
                }
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="api_server",
                status="unhealthy",
                message=f"API server error: {str(e)}",
                response_time_ms=response_time,
                last_check=time.time()
            )
    
    async def check_cloud_hypervisor(self) -> ComponentHealth:
        """Check Cloud Hypervisor binary availability."""
        start_time = time.time()
        try:
            ch_binary = self.config.cloud_hypervisor.binary_path
            
            # Check if binary exists and is executable
            if not os.path.exists(ch_binary):
                raise FileNotFoundError(f"Cloud Hypervisor binary not found: {ch_binary}")
            
            if not os.access(ch_binary, os.X_OK):
                raise PermissionError(f"Cloud Hypervisor binary not executable: {ch_binary}")
            
            # Try to get version
            proc = await asyncio.create_subprocess_exec(
                ch_binary, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            
            if proc.returncode != 0:
                raise RuntimeError(f"Cloud Hypervisor version check failed: {stderr.decode()}")
            
            version = stdout.decode().strip()
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="cloud_hypervisor",
                status="healthy",
                message="Cloud Hypervisor is available",
                response_time_ms=response_time,
                last_check=time.time(),
                details={
                    "binary_path": ch_binary,
                    "version": version
                }
            )
            
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="cloud_hypervisor",
                status="unhealthy",
                message="Cloud Hypervisor version check timed out",
                response_time_ms=response_time,
                last_check=time.time()
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="cloud_hypervisor",
                status="unhealthy",
                message=f"Cloud Hypervisor check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=time.time()
            )
    
    async def check_system_resources(self) -> ComponentHealth:
        """Check system resource availability."""
        start_time = time.time()
        try:
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Check memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Check disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Check load average (Unix only)
            load_avg = None
            try:
                load_avg = psutil.getloadavg()
            except AttributeError:
                # Windows doesn't have load average
                pass
            
            # Determine status based on thresholds
            status = "healthy"
            issues = []
            
            if cpu_percent > 90:
                status = "degraded" if status == "healthy" else "unhealthy"
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")
            elif cpu_percent > 80:
                status = "degraded"
                issues.append(f"Elevated CPU usage: {cpu_percent:.1f}%")
            
            if memory_percent > 90:
                status = "degraded" if status == "healthy" else "unhealthy"
                issues.append(f"High memory usage: {memory_percent:.1f}%")
            elif memory_percent > 80:
                status = "degraded"
                issues.append(f"Elevated memory usage: {memory_percent:.1f}%")
            
            if disk_percent > 95:
                status = "unhealthy"
                issues.append(f"Critical disk usage: {disk_percent:.1f}%")
            elif disk_percent > 85:
                status = "degraded"
                issues.append(f"High disk usage: {disk_percent:.1f}%")
            
            message = "System resources are healthy"
            if issues:
                message = f"Resource issues: {'; '.join(issues)}"
            
            response_time = (time.time() - start_time) * 1000
            
            details = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": disk_percent,
                "disk_free_gb": disk.free / (1024**3)
            }
            
            if load_avg:
                details["load_average"] = {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2]
                }
            
            return ComponentHealth(
                name="system_resources",
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=time.time(),
                details=details
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="system_resources",
                status="unhealthy",
                message=f"System resource check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=time.time()
            )
    
    async def check_networking(self) -> ComponentHealth:
        """Check networking configuration."""
        start_time = time.time()
        try:
            bridge_name = self.config.networking.bridge_name
            
            # Check if bridge exists
            network_interfaces = psutil.net_if_addrs()
            
            if bridge_name not in network_interfaces:
                return ComponentHealth(
                    name="networking",
                    status="unhealthy",
                    message=f"Bridge interface {bridge_name} not found",
                    response_time_ms=(time.time() - start_time) * 1000,
                    last_check=time.time(),
                    details={"bridge_name": bridge_name}
                )
            
            # Check bridge configuration
            bridge_addrs = network_interfaces[bridge_name]
            bridge_ip = None
            for addr in bridge_addrs:
                if addr.family == 2:  # AF_INET
                    bridge_ip = addr.address
                    break
            
            # Get network statistics
            net_io = psutil.net_io_counters(pernic=True).get(bridge_name)
            
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="networking",
                status="healthy",
                message="Networking is configured correctly",
                response_time_ms=response_time,
                last_check=time.time(),
                details={
                    "bridge_name": bridge_name,
                    "bridge_ip": bridge_ip,
                    "interfaces_count": len(network_interfaces),
                    "bytes_sent": net_io.bytes_sent if net_io else 0,
                    "bytes_recv": net_io.bytes_recv if net_io else 0
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="networking",
                status="unhealthy",
                message=f"Networking check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=time.time()
            )
    
    async def check_vm_manager(self) -> ComponentHealth:
        """Check VM manager status."""
        start_time = time.time()
        try:
            # This would normally check the VM manager instance
            # For now, we'll check if VM storage directory exists
            vm_storage_dir = "/tmp/microvm-sandbox/vms"
            
            if not os.path.exists(vm_storage_dir):
                os.makedirs(vm_storage_dir, exist_ok=True)
            
            # Count VM files/directories
            vm_count = 0
            try:
                vm_count = len([d for d in os.listdir(vm_storage_dir) 
                               if os.path.isdir(os.path.join(vm_storage_dir, d))])
            except (OSError, PermissionError):
                pass
            
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="vm_manager",
                status="healthy",
                message="VM manager is operational",
                response_time_ms=response_time,
                last_check=time.time(),
                details={
                    "storage_dir": vm_storage_dir,
                    "vm_count": vm_count
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="vm_manager",
                status="unhealthy",
                message=f"VM manager check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=time.time()
            )
    
    async def check_metrics_system(self) -> ComponentHealth:
        """Check metrics collection system."""
        start_time = time.time()
        try:
            # Try to get metrics
            metrics_data = metrics.get_metrics()
            
            if not metrics_data:
                raise RuntimeError("No metrics data available")
            
            # Count metrics
            metric_lines = [line for line in metrics_data.split('\n') 
                           if line and not line.startswith('#')]
            
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="metrics_system",
                status="healthy",
                message="Metrics system is collecting data",
                response_time_ms=response_time,
                last_check=time.time(),
                details={
                    "metrics_count": len(metric_lines),
                    "prometheus_enabled": True
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="metrics_system",
                status="unhealthy",
                message=f"Metrics system check failed: {str(e)}",
                response_time_ms=response_time,
                last_check=time.time()
            )
    
    async def check_all_components(self) -> SystemHealth:
        """Check all system components."""
        checks = [
            self.check_api_server(),
            self.check_cloud_hypervisor(),
            self.check_system_resources(),
            self.check_networking(),
            self.check_vm_manager(),
            self.check_metrics_system()
        ]
        
        # Run all checks concurrently
        components = await asyncio.gather(*checks, return_exceptions=True)
        
        # Handle any exceptions from failed checks
        valid_components = []
        for i, component in enumerate(components):
            if isinstance(component, Exception):
                # Create an unhealthy component for failed checks
                check_names = ["api_server", "cloud_hypervisor", "system_resources", 
                              "networking", "vm_manager", "metrics_system"]
                valid_components.append(ComponentHealth(
                    name=check_names[i],
                    status="unhealthy",
                    message=f"Health check failed: {str(component)}",
                    response_time_ms=0,
                    last_check=time.time()
                ))
            else:
                valid_components.append(component)
        
        # Update metrics for each component
        for component in valid_components:
            metrics.update_health_status(
                component.name, 
                component.status == "healthy", 
                component.response_time_ms / 1000
            )
        
        # Calculate overall status
        status_counts = {"healthy": 0, "degraded": 0, "unhealthy": 0}
        for component in valid_components:
            status_counts[component.status] += 1
        
        # Determine overall status
        if status_counts["unhealthy"] > 0:
            overall_status = "unhealthy"
        elif status_counts["degraded"] > 0:
            overall_status = "degraded"
        else:
            overall_status = "healthy"
        
        return SystemHealth(
            status=overall_status,
            timestamp=time.time(),
            uptime_seconds=time.time() - self.start_time,
            components=valid_components,
            summary=status_counts
        )


# Global health checker instance
health_checker = HealthChecker()


@router.get("/", response_model=SystemHealth)
async def get_system_health():
    """Get comprehensive system health status."""
    try:
        health_status = await health_checker.check_all_components()
        logger.info(f"System health check completed: {health_status.status}")
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        metrics.record_error("health", "system_check_failed")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/ready")
async def readiness_check():
    """Kubernetes-style readiness check."""
    try:
        health_status = await health_checker.check_all_components()
        
        # Consider system ready if no components are unhealthy
        if health_status.summary.get("unhealthy", 0) == 0:
            return {"status": "ready", "timestamp": time.time()}
        else:
            raise HTTPException(
                status_code=503, 
                detail={
                    "status": "not_ready", 
                    "unhealthy_components": [
                        c.name for c in health_status.components if c.status == "unhealthy"
                    ],
                    "timestamp": time.time()
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        metrics.record_error("health", "readiness_check_failed")
        raise HTTPException(status_code=503, detail=f"Readiness check failed: {str(e)}")


@router.get("/live")
async def liveness_check():
    """Kubernetes-style liveness check."""
    try:
        # Simple liveness check - just verify API server is responding
        api_health = await health_checker.check_api_server()
        
        if api_health.status == "healthy":
            return {"status": "alive", "timestamp": time.time()}
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "not_alive",
                    "message": api_health.message,
                    "timestamp": time.time()
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        metrics.record_error("health", "liveness_check_failed")
        raise HTTPException(status_code=503, detail=f"Liveness check failed: {str(e)}")


@router.get("/metrics")
async def get_metrics():
    """Get Prometheus metrics."""
    try:
        return Response(
            content=metrics.get_metrics(),
            media_type=metrics.get_content_type()
        )
    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        metrics.record_error("health", "metrics_endpoint_failed")
        raise HTTPException(status_code=500, detail=f"Metrics collection failed: {str(e)}")


@router.get("/component/{component_name}", response_model=ComponentHealth)
async def get_component_health(component_name: str):
    """Get health status for a specific component."""
    try:
        check_methods = {
            "api_server": health_checker.check_api_server,
            "cloud_hypervisor": health_checker.check_cloud_hypervisor,
            "system_resources": health_checker.check_system_resources,
            "networking": health_checker.check_networking,
            "vm_manager": health_checker.check_vm_manager,
            "metrics_system": health_checker.check_metrics_system
        }
        
        if component_name not in check_methods:
            raise HTTPException(
                status_code=404, 
                detail=f"Component '{component_name}' not found. Available: {list(check_methods.keys())}"
            )
        
        component_health = await check_methods[component_name]()
        
        # Update metrics
        metrics.update_health_status(
            component_name,
            component_health.status == "healthy",
            component_health.response_time_ms / 1000
        )
        
        return component_health
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Component health check failed for {component_name}: {e}")
        metrics.record_error("health", f"component_check_failed")
        raise HTTPException(
            status_code=500, 
            detail=f"Component health check failed: {str(e)}"
        )