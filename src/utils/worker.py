"""
Background worker service for MicroVM Sandbox.
Handles async tasks, scaling operations, and maintenance tasks.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json
import os

from .scaling import get_horizontal_scaler, get_load_balancer
from .config import get_config
from .logging import get_logger

logger = get_logger(__name__)


class BackgroundWorker:
    """Background worker for handling async tasks and maintenance."""
    
    def __init__(self):
        self.config = get_config()
        self.horizontal_scaler = get_horizontal_scaler()
        self.load_balancer = get_load_balancer()
        self.running = False
        self.tasks = {}
        
        # Task intervals (seconds)
        self.auto_scale_interval = int(os.getenv("MICROVM_AUTO_SCALE_INTERVAL", "60"))
        self.health_check_interval = int(os.getenv("MICROVM_HEALTH_CHECK_INTERVAL", "30"))
        self.cleanup_interval = int(os.getenv("MICROVM_CLEANUP_INTERVAL", "3600"))
        self.metrics_collection_interval = int(os.getenv("MICROVM_METRICS_INTERVAL", "15"))
        
        # Last execution times
        self.last_auto_scale = datetime.min
        self.last_health_check = datetime.min
        self.last_cleanup = datetime.min
        self.last_metrics_collection = datetime.min
        
        # Setup signal handlers
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    async def start(self):
        """Start the background worker."""
        logger.info("Starting MicroVM Sandbox background worker")
        self.running = True
        
        # Start main worker loop
        await self._worker_loop()
    
    async def shutdown(self):
        """Shutdown the background worker gracefully."""
        logger.info("Shutting down background worker...")
        self.running = False
        
        # Cancel all running tasks
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        logger.info("Background worker shutdown complete")
    
    async def _worker_loop(self):
        """Main worker loop."""
        logger.info("Background worker started successfully")
        
        while self.running:
            try:
                current_time = datetime.now()
                
                # Auto-scaling task
                if (current_time - self.last_auto_scale).total_seconds() >= self.auto_scale_interval:
                    if "auto_scale" not in self.tasks or self.tasks["auto_scale"].done():
                        self.tasks["auto_scale"] = asyncio.create_task(self._auto_scale_task())
                    self.last_auto_scale = current_time
                
                # Health check task
                if (current_time - self.last_health_check).total_seconds() >= self.health_check_interval:
                    if "health_check" not in self.tasks or self.tasks["health_check"].done():
                        self.tasks["health_check"] = asyncio.create_task(self._health_check_task())
                    self.last_health_check = current_time
                
                # Cleanup task
                if (current_time - self.last_cleanup).total_seconds() >= self.cleanup_interval:
                    if "cleanup" not in self.tasks or self.tasks["cleanup"].done():
                        self.tasks["cleanup"] = asyncio.create_task(self._cleanup_task())
                    self.last_cleanup = current_time
                
                # Metrics collection task
                if (current_time - self.last_metrics_collection).total_seconds() >= self.metrics_collection_interval:
                    if "metrics" not in self.tasks or self.tasks["metrics"].done():
                        self.tasks["metrics"] = asyncio.create_task(self._metrics_collection_task())
                    self.last_metrics_collection = current_time
                
                # Sleep for a short time before next iteration
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                await asyncio.sleep(10)  # Wait longer on error
    
    async def _auto_scale_task(self):
        """Auto-scaling task."""
        try:
            logger.debug("Running auto-scaling task")
            
            # Perform auto-scaling
            result = await self.horizontal_scaler.auto_scale()
            
            if result["action"] != "none":
                logger.info(f"Auto-scaling action taken: {result['action']}, "
                           f"replicas: {result['current_replicas']} -> {result['new_replicas']}")
            else:
                logger.debug(f"No auto-scaling action needed. Current metrics: {result['metrics']}")
            
            # Log scaling events for monitoring
            await self._log_scaling_event(result)
            
        except Exception as e:
            logger.error(f"Error in auto-scaling task: {e}", exc_info=True)
    
    async def _health_check_task(self):
        """Health check task."""
        try:
            logger.debug("Running health check task")
            
            # Get cluster status
            cluster_status = await self.load_balancer.get_cluster_status()
            
            healthy_instances = cluster_status["healthy_instances"]
            total_instances = cluster_status["total_instances"]
            
            if healthy_instances < total_instances:
                logger.warning(f"Some instances are unhealthy: {healthy_instances}/{total_instances} healthy")
            
            # Log health status
            await self._log_health_event(cluster_status)
            
        except Exception as e:
            logger.error(f"Error in health check task: {e}", exc_info=True)
    
    async def _cleanup_task(self):
        """Cleanup task for maintenance operations."""
        try:
            logger.debug("Running cleanup task")
            
            # Clean up old session affinity entries
            await self._cleanup_session_affinity()
            
            # Clean up old metrics (if needed)
            await self._cleanup_old_metrics()
            
            # Clean up temporary files
            await self._cleanup_temp_files()
            
            logger.debug("Cleanup task completed")
            
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}", exc_info=True)
    
    async def _metrics_collection_task(self):
        """Metrics collection task."""
        try:
            logger.debug("Running metrics collection task")
            
            # Collect cluster metrics
            cluster_metrics = await self._collect_cluster_metrics()
            
            # Store metrics (in production, this would go to a time-series database)
            await self._store_metrics(cluster_metrics)
            
        except Exception as e:
            logger.error(f"Error in metrics collection task: {e}", exc_info=True)
    
    async def _cleanup_session_affinity(self):
        """Clean up old session affinity entries."""
        try:
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(seconds=self.load_balancer.config.session_affinity_timeout)
            
            # In a production system, you would check session timestamps
            # For now, we'll just clear old entries periodically
            if len(self.load_balancer.session_affinity) > 1000:
                # Clear half of the entries when we have too many
                items = list(self.load_balancer.session_affinity.items())
                self.load_balancer.session_affinity = dict(items[:500])
                logger.info("Cleaned up old session affinity entries")
            
        except Exception as e:
            logger.error(f"Error cleaning up session affinity: {e}")
    
    async def _cleanup_old_metrics(self):
        """Clean up old metrics data."""
        try:
            # This would typically clean up old metrics from a database
            # For now, just a placeholder
            logger.debug("Metrics cleanup completed (placeholder)")
            
        except Exception as e:
            logger.error(f"Error cleaning up old metrics: {e}")
    
    async def _cleanup_temp_files(self):
        """Clean up temporary files."""
        try:
            import tempfile
            import os
            import glob
            
            temp_dir = tempfile.gettempdir()
            
            # Clean up old CH socket files
            ch_socket_pattern = os.path.join(temp_dir, "ch-*")
            for socket_file in glob.glob(ch_socket_pattern):
                try:
                    if os.path.isfile(socket_file):
                        # Check if file is older than 1 hour
                        file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(socket_file))
                        if file_age > timedelta(hours=1):
                            os.remove(socket_file)
                            logger.debug(f"Removed old socket file: {socket_file}")
                except Exception as e:
                    logger.debug(f"Failed to remove socket file {socket_file}: {e}")
            
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")
    
    async def _collect_cluster_metrics(self) -> Dict[str, Any]:
        """Collect cluster-wide metrics."""
        try:
            cluster_status = await self.load_balancer.get_cluster_status()
            scaling_metrics = await self.horizontal_scaler.get_current_metrics()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "cluster_status": cluster_status,
                "scaling_metrics": scaling_metrics,
                "worker_status": {
                    "running": self.running,
                    "tasks": {name: not task.done() for name, task in self.tasks.items()},
                    "last_auto_scale": self.last_auto_scale.isoformat(),
                    "last_health_check": self.last_health_check.isoformat(),
                    "last_cleanup": self.last_cleanup.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error collecting cluster metrics: {e}")
            return {}
    
    async def _store_metrics(self, metrics: Dict[str, Any]):
        """Store metrics data."""
        try:
            # In production, this would store to a time-series database
            # For now, we'll just log it
            logger.debug(f"Collected cluster metrics: healthy_instances={metrics.get('cluster_status', {}).get('healthy_instances', 0)}")
            
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
    
    async def _log_scaling_event(self, scaling_result: Dict[str, Any]):
        """Log scaling events for monitoring."""
        try:
            event = {
                "timestamp": datetime.now().isoformat(),
                "event_type": "scaling",
                "action": scaling_result["action"],
                "current_replicas": scaling_result["current_replicas"],
                "new_replicas": scaling_result["new_replicas"],
                "metrics": scaling_result["metrics"],
                "thresholds": scaling_result["thresholds"]
            }
            
            # In production, this would go to a proper logging/monitoring system
            logger.info(f"Scaling event: {json.dumps(event)}")
            
        except Exception as e:
            logger.error(f"Error logging scaling event: {e}")
    
    async def _log_health_event(self, cluster_status: Dict[str, Any]):
        """Log health events for monitoring."""
        try:
            event = {
                "timestamp": datetime.now().isoformat(),
                "event_type": "health_check",
                "total_instances": cluster_status["total_instances"],
                "healthy_instances": cluster_status["healthy_instances"],
                "unhealthy_instances": cluster_status["unhealthy_instances"]
            }
            
            # In production, this would go to a proper logging/monitoring system
            if cluster_status["unhealthy_instances"] > 0:
                logger.warning(f"Health event: {json.dumps(event)}")
            else:
                logger.debug(f"Health event: {json.dumps(event)}")
            
        except Exception as e:
            logger.error(f"Error logging health event: {e}")


async def main():
    """Main entry point for the background worker."""
    worker = BackgroundWorker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error in worker: {e}", exc_info=True)
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())