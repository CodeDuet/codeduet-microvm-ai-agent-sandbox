"""
Prometheus metrics collection for MicroVM Sandbox.
Provides comprehensive metrics for monitoring VM performance, resource usage, and system health.
"""

import time
from typing import Dict, Any, Optional
from prometheus_client import (
    Counter, Gauge, Histogram, Summary,
    CollectorRegistry, generate_latest,
    CONTENT_TYPE_LATEST, REGISTRY
)
import psutil
import asyncio
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class MicroVMMetrics:
    """Prometheus metrics collector for MicroVM Sandbox."""
    
    def __init__(self, registry: CollectorRegistry = REGISTRY):
        self.registry = registry
        self._setup_metrics()
        self._last_network_stats = {}
        self._last_disk_stats = {}
        
    def _setup_metrics(self):
        """Initialize all Prometheus metrics."""
        
        # VM Lifecycle Metrics
        self.vm_total = Counter(
            'microvm_vm_total',
            'Total number of VMs created',
            ['os_type', 'template'],
            registry=self.registry
        )
        
        self.vm_current = Gauge(
            'microvm_vm_current',
            'Current number of VMs by state',
            ['state', 'os_type'],
            registry=self.registry
        )
        
        self.vm_operations_total = Counter(
            'microvm_vm_operations_total',
            'Total VM operations performed',
            ['operation', 'status', 'os_type'],
            registry=self.registry
        )
        
        self.vm_operation_duration = Histogram(
            'microvm_vm_operation_duration_seconds',
            'Time spent on VM operations',
            ['operation', 'os_type'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry
        )
        
        # VM Boot Time Metrics
        self.vm_boot_time = Histogram(
            'microvm_vm_boot_time_seconds',
            'VM boot time from start to ready',
            ['os_type', 'template'],
            buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 30.0],
            registry=self.registry
        )
        
        # Resource Usage Metrics
        self.vm_cpu_usage = Gauge(
            'microvm_vm_cpu_usage_percent',
            'VM CPU usage percentage',
            ['vm_name', 'vm_id'],
            registry=self.registry
        )
        
        self.vm_memory_usage = Gauge(
            'microvm_vm_memory_usage_bytes',
            'VM memory usage in bytes',
            ['vm_name', 'vm_id', 'type'],
            registry=self.registry
        )
        
        self.vm_disk_usage = Gauge(
            'microvm_vm_disk_usage_bytes',
            'VM disk usage in bytes',
            ['vm_name', 'vm_id', 'type'],
            registry=self.registry
        )
        
        self.vm_network_bytes = Counter(
            'microvm_vm_network_bytes_total',
            'VM network bytes transferred',
            ['vm_name', 'vm_id', 'direction'],
            registry=self.registry
        )
        
        self.vm_network_packets = Counter(
            'microvm_vm_network_packets_total',
            'VM network packets transferred',
            ['vm_name', 'vm_id', 'direction'],
            registry=self.registry
        )
        
        # System Resource Metrics
        self.host_cpu_usage = Gauge(
            'microvm_host_cpu_usage_percent',
            'Host system CPU usage percentage',
            ['core'],
            registry=self.registry
        )
        
        self.host_memory_usage = Gauge(
            'microvm_host_memory_usage_bytes',
            'Host system memory usage',
            ['type'],
            registry=self.registry
        )
        
        self.host_disk_usage = Gauge(
            'microvm_host_disk_usage_bytes',
            'Host system disk usage',
            ['device', 'type'],
            registry=self.registry
        )
        
        self.host_network_bytes = Counter(
            'microvm_host_network_bytes_total',
            'Host network bytes transferred',
            ['interface', 'direction'],
            registry=self.registry
        )
        
        # API Metrics
        self.api_requests_total = Counter(
            'microvm_api_requests_total',
            'Total API requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )
        
        self.api_request_duration = Histogram(
            'microvm_api_request_duration_seconds',
            'API request duration',
            ['method', 'endpoint'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.registry
        )
        
        # Snapshot Metrics
        self.snapshot_operations_total = Counter(
            'microvm_snapshot_operations_total',
            'Total snapshot operations',
            ['operation', 'status'],
            registry=self.registry
        )
        
        self.snapshot_size_bytes = Gauge(
            'microvm_snapshot_size_bytes',
            'Snapshot size in bytes',
            ['vm_name', 'snapshot_name'],
            registry=self.registry
        )
        
        self.snapshot_duration = Histogram(
            'microvm_snapshot_duration_seconds',
            'Snapshot operation duration',
            ['operation'],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry
        )
        
        # Guest Agent Metrics
        self.guest_operations_total = Counter(
            'microvm_guest_operations_total',
            'Total guest operations',
            ['vm_name', 'operation', 'status'],
            registry=self.registry
        )
        
        self.guest_operation_duration = Histogram(
            'microvm_guest_operation_duration_seconds',
            'Guest operation duration',
            ['vm_name', 'operation'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            registry=self.registry
        )
        
        # Security Metrics
        self.security_events_total = Counter(
            'microvm_security_events_total',
            'Total security events',
            ['event_type', 'severity'],
            registry=self.registry
        )
        
        self.authentication_attempts_total = Counter(
            'microvm_authentication_attempts_total',
            'Total authentication attempts',
            ['status', 'method'],
            registry=self.registry
        )
        
        # Resource Allocation Metrics
        self.resource_allocations = Gauge(
            'microvm_resource_allocations',
            'Current resource allocations',
            ['resource_type', 'status'],
            registry=self.registry
        )
        
        self.resource_quota_usage = Gauge(
            'microvm_resource_quota_usage_percent',
            'Resource quota usage percentage',
            ['user_id', 'resource_type'],
            registry=self.registry
        )
        
        # Error Metrics
        self.errors_total = Counter(
            'microvm_errors_total',
            'Total errors by component',
            ['component', 'error_type'],
            registry=self.registry
        )
        
        # Health Check Metrics
        self.health_check_status = Gauge(
            'microvm_health_check_status',
            'Health check status (1=healthy, 0=unhealthy)',
            ['component'],
            registry=self.registry
        )
        
        self.health_check_duration = Histogram(
            'microvm_health_check_duration_seconds',
            'Health check duration',
            ['component'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )
    
    def record_vm_created(self, os_type: str, template: str):
        """Record VM creation."""
        self.vm_total.labels(os_type=os_type, template=template).inc()
        logger.debug(f"Recorded VM creation: {os_type}/{template}")
    
    def update_vm_count(self, state: str, os_type: str, count: int):
        """Update current VM count by state."""
        self.vm_current.labels(state=state, os_type=os_type).set(count)
    
    def record_vm_operation(self, operation: str, status: str, os_type: str, duration: float):
        """Record VM operation with duration."""
        self.vm_operations_total.labels(
            operation=operation, status=status, os_type=os_type
        ).inc()
        self.vm_operation_duration.labels(
            operation=operation, os_type=os_type
        ).observe(duration)
        logger.debug(f"Recorded VM operation: {operation}/{status} in {duration:.2f}s")
    
    def record_vm_boot_time(self, os_type: str, template: str, boot_time: float):
        """Record VM boot time."""
        self.vm_boot_time.labels(os_type=os_type, template=template).observe(boot_time)
        logger.debug(f"Recorded VM boot time: {os_type}/{template} in {boot_time:.2f}s")
    
    def update_vm_resources(self, vm_name: str, vm_id: str, cpu_percent: float, 
                           memory_used: int, memory_total: int):
        """Update VM resource usage metrics."""
        self.vm_cpu_usage.labels(vm_name=vm_name, vm_id=vm_id).set(cpu_percent)
        self.vm_memory_usage.labels(
            vm_name=vm_name, vm_id=vm_id, type="used"
        ).set(memory_used)
        self.vm_memory_usage.labels(
            vm_name=vm_name, vm_id=vm_id, type="total"
        ).set(memory_total)
    
    def update_vm_disk_usage(self, vm_name: str, vm_id: str, disk_used: int, disk_total: int):
        """Update VM disk usage metrics."""
        self.vm_disk_usage.labels(
            vm_name=vm_name, vm_id=vm_id, type="used"
        ).set(disk_used)
        self.vm_disk_usage.labels(
            vm_name=vm_name, vm_id=vm_id, type="total"
        ).set(disk_total)
    
    def update_vm_network_stats(self, vm_name: str, vm_id: str, 
                               bytes_sent: int, bytes_recv: int,
                               packets_sent: int, packets_recv: int):
        """Update VM network statistics."""
        # Calculate deltas for counter metrics
        key = f"{vm_name}:{vm_id}"
        if key in self._last_network_stats:
            last_stats = self._last_network_stats[key]
            bytes_sent_delta = max(0, bytes_sent - last_stats['bytes_sent'])
            bytes_recv_delta = max(0, bytes_recv - last_stats['bytes_recv'])
            packets_sent_delta = max(0, packets_sent - last_stats['packets_sent'])
            packets_recv_delta = max(0, packets_recv - last_stats['packets_recv'])
            
            self.vm_network_bytes.labels(
                vm_name=vm_name, vm_id=vm_id, direction="tx"
            ).inc(bytes_sent_delta)
            self.vm_network_bytes.labels(
                vm_name=vm_name, vm_id=vm_id, direction="rx"
            ).inc(bytes_recv_delta)
            self.vm_network_packets.labels(
                vm_name=vm_name, vm_id=vm_id, direction="tx"
            ).inc(packets_sent_delta)
            self.vm_network_packets.labels(
                vm_name=vm_name, vm_id=vm_id, direction="rx"
            ).inc(packets_recv_delta)
        
        self._last_network_stats[key] = {
            'bytes_sent': bytes_sent,
            'bytes_recv': bytes_recv,
            'packets_sent': packets_sent,
            'packets_recv': packets_recv
        }
    
    def update_host_metrics(self):
        """Update host system metrics."""
        try:
            # CPU usage
            cpu_percentages = psutil.cpu_percent(percpu=True)
            for i, cpu_percent in enumerate(cpu_percentages):
                self.host_cpu_usage.labels(core=str(i)).set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.host_memory_usage.labels(type="total").set(memory.total)
            self.host_memory_usage.labels(type="used").set(memory.used)
            self.host_memory_usage.labels(type="available").set(memory.available)
            
            # Disk usage
            for disk in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(disk.mountpoint)
                    device = disk.device.replace('/', '_')
                    self.host_disk_usage.labels(device=device, type="total").set(usage.total)
                    self.host_disk_usage.labels(device=device, type="used").set(usage.used)
                    self.host_disk_usage.labels(device=device, type="free").set(usage.free)
                except (PermissionError, OSError):
                    continue
            
            # Network interface stats
            net_io = psutil.net_io_counters(pernic=True)
            for interface, stats in net_io.items():
                if interface in self._last_network_stats:
                    last_stats = self._last_network_stats[interface]
                    bytes_sent_delta = max(0, stats.bytes_sent - last_stats['bytes_sent'])
                    bytes_recv_delta = max(0, stats.bytes_recv - last_stats['bytes_recv'])
                    
                    self.host_network_bytes.labels(
                        interface=interface, direction="tx"
                    ).inc(bytes_sent_delta)
                    self.host_network_bytes.labels(
                        interface=interface, direction="rx"
                    ).inc(bytes_recv_delta)
                
                self._last_network_stats[interface] = {
                    'bytes_sent': stats.bytes_sent,
                    'bytes_recv': stats.bytes_recv
                }
                
        except Exception as e:
            logger.error(f"Error updating host metrics: {e}")
            self.errors_total.labels(component="metrics", error_type="host_update").inc()
    
    def record_api_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record API request metrics."""
        self.api_requests_total.labels(
            method=method, endpoint=endpoint, status=str(status)
        ).inc()
        self.api_request_duration.labels(
            method=method, endpoint=endpoint
        ).observe(duration)
    
    def record_snapshot_operation(self, operation: str, status: str, duration: float, 
                                 vm_name: str = None, snapshot_name: str = None, 
                                 size_bytes: int = None):
        """Record snapshot operation metrics."""
        self.snapshot_operations_total.labels(
            operation=operation, status=status
        ).inc()
        self.snapshot_duration.labels(operation=operation).observe(duration)
        
        if vm_name and snapshot_name and size_bytes:
            self.snapshot_size_bytes.labels(
                vm_name=vm_name, snapshot_name=snapshot_name
            ).set(size_bytes)
    
    def record_guest_operation(self, vm_name: str, operation: str, status: str, duration: float):
        """Record guest operation metrics."""
        self.guest_operations_total.labels(
            vm_name=vm_name, operation=operation, status=status
        ).inc()
        self.guest_operation_duration.labels(
            vm_name=vm_name, operation=operation
        ).observe(duration)
    
    def record_security_event(self, event_type: str, severity: str):
        """Record security event."""
        self.security_events_total.labels(
            event_type=event_type, severity=severity
        ).inc()
        logger.info(f"Security event recorded: {event_type}/{severity}")
    
    def record_authentication_attempt(self, status: str, method: str):
        """Record authentication attempt."""
        self.authentication_attempts_total.labels(
            status=status, method=method
        ).inc()
    
    def update_resource_allocation(self, resource_type: str, status: str, count: int):
        """Update resource allocation metrics."""
        self.resource_allocations.labels(
            resource_type=resource_type, status=status
        ).set(count)
    
    def update_quota_usage(self, user_id: str, resource_type: str, usage_percent: float):
        """Update resource quota usage."""
        self.resource_quota_usage.labels(
            user_id=user_id, resource_type=resource_type
        ).set(usage_percent)
    
    def record_error(self, component: str, error_type: str):
        """Record error by component."""
        self.errors_total.labels(component=component, error_type=error_type).inc()
        logger.warning(f"Error recorded: {component}/{error_type}")
    
    def update_health_status(self, component: str, is_healthy: bool, check_duration: float):
        """Update health check status."""
        self.health_check_status.labels(component=component).set(1 if is_healthy else 0)
        self.health_check_duration.labels(component=component).observe(check_duration)
    
    def get_metrics(self) -> str:
        """Get current metrics in Prometheus format."""
        return generate_latest(self.registry)
    
    def get_content_type(self) -> str:
        """Get Prometheus metrics content type."""
        return CONTENT_TYPE_LATEST


# Global metrics instance
metrics = MicroVMMetrics()


def time_operation(operation: str, os_type: str = "unknown"):
    """Decorator to time operations and record metrics."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                metrics.record_error("operation", type(e).__name__)
                raise
            finally:
                duration = time.time() - start_time
                metrics.record_vm_operation(operation, status, os_type, duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                metrics.record_error("operation", type(e).__name__)
                raise
            finally:
                duration = time.time() - start_time
                metrics.record_vm_operation(operation, status, os_type, duration)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def time_api_request(func):
    """Decorator to time API requests and record metrics."""
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        start_time = time.time()
        method = request.method
        endpoint = request.url.path
        status = 200
        
        try:
            response = await func(request, *args, **kwargs)
            if hasattr(response, 'status_code'):
                status = response.status_code
            return response
        except Exception as e:
            status = 500
            metrics.record_error("api", type(e).__name__)
            raise
        finally:
            duration = time.time() - start_time
            metrics.record_api_request(method, endpoint, status, duration)
    
    return wrapper


class MetricsCollector:
    """Background metrics collector for periodic system updates."""
    
    def __init__(self, metrics_instance: MicroVMMetrics, interval: int = 30):
        self.metrics = metrics_instance
        self.interval = interval
        self._running = False
        self._task = None
    
    async def start(self):
        """Start metrics collection."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._collect_loop())
        logger.info(f"Started metrics collection with {self.interval}s interval")
    
    async def stop(self):
        """Stop metrics collection."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped metrics collection")
    
    async def _collect_loop(self):
        """Main collection loop."""
        while self._running:
            try:
                self.metrics.update_host_metrics()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
                self.metrics.record_error("metrics", "collection_error")
                await asyncio.sleep(self.interval)