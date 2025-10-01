import sys
import uuid
import json
import time
from typing import Dict, Any, Optional
from contextvars import ContextVar
from loguru import logger
from pathlib import Path
from src.utils.config import get_settings

# Context variables for correlation tracking
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
request_id: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
operation_id: ContextVar[Optional[str]] = ContextVar('operation_id', default=None)


class StructuredLogger:
    """Enhanced logger with correlation IDs and structured logging."""
    
    def __init__(self, component: str):
        self.component = component
        self.base_logger = logger.bind(component=component)
    
    def _get_context(self) -> Dict[str, Any]:
        """Get current logging context."""
        context = {
            "component": self.component,
            "timestamp": time.time(),
            "correlation_id": correlation_id.get(),
            "request_id": request_id.get(),
            "user_id": user_id.get(),
            "operation_id": operation_id.get(),
        }
        # Remove None values
        return {k: v for k, v in context.items() if v is not None}
    
    def _format_message(self, message: str, extra: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format structured log message."""
        log_data = {
            "message": message,
            **self._get_context()
        }
        
        if extra:
            log_data.update(extra)
        
        return log_data
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        log_data = self._format_message(message, kwargs)
        self.base_logger.debug(json.dumps(log_data))
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        log_data = self._format_message(message, kwargs)
        self.base_logger.info(json.dumps(log_data))
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        log_data = self._format_message(message, kwargs)
        self.base_logger.warning(json.dumps(log_data))
    
    def error(self, message: str, error: Exception = None, **kwargs):
        """Log error message with context and exception details."""
        log_data = self._format_message(message, kwargs)
        
        if error:
            log_data.update({
                "error_type": type(error).__name__,
                "error_message": str(error),
                "error_traceback": str(error.__traceback__) if error.__traceback__ else None
            })
        
        self.base_logger.error(json.dumps(log_data))
    
    def critical(self, message: str, error: Exception = None, **kwargs):
        """Log critical message with context."""
        log_data = self._format_message(message, kwargs)
        
        if error:
            log_data.update({
                "error_type": type(error).__name__,
                "error_message": str(error),
                "error_traceback": str(error.__traceback__) if error.__traceback__ else None
            })
        
        self.base_logger.critical(json.dumps(log_data))
    
    def operation_start(self, operation: str, **kwargs):
        """Log operation start with correlation tracking."""
        op_id = str(uuid.uuid4())
        operation_id.set(op_id)
        
        log_data = self._format_message(f"Operation started: {operation}", {
            "operation": operation,
            "operation_id": op_id,
            "status": "started",
            **kwargs
        })
        self.base_logger.info(json.dumps(log_data))
        return op_id
    
    def operation_end(self, operation: str, op_id: str, success: bool = True, duration: float = None, **kwargs):
        """Log operation completion."""
        operation_id.set(op_id)
        
        log_data = self._format_message(f"Operation completed: {operation}", {
            "operation": operation,
            "operation_id": op_id,
            "status": "completed" if success else "failed",
            "success": success,
            "duration_seconds": duration,
            **kwargs
        })
        
        if success:
            self.base_logger.info(json.dumps(log_data))
        else:
            self.base_logger.error(json.dumps(log_data))
    
    def audit_log(self, action: str, resource: str, **kwargs):
        """Log audit event."""
        log_data = self._format_message(f"Audit: {action} on {resource}", {
            "audit": True,
            "action": action,
            "resource": resource,
            "timestamp_iso": time.strftime('%Y-%m-%dT%H:%M:%S.%fZ', time.gmtime()),
            **kwargs
        })
        self.base_logger.info(json.dumps(log_data))
    
    def security_event(self, event_type: str, severity: str, description: str, **kwargs):
        """Log security event."""
        log_data = self._format_message(f"Security: {event_type}", {
            "security": True,
            "event_type": event_type,
            "severity": severity,
            "description": description,
            "timestamp_iso": time.strftime('%Y-%m-%dT%H:%M:%S.%fZ', time.gmtime()),
            **kwargs
        })
        self.base_logger.warning(json.dumps(log_data))
    
    def performance_metric(self, metric_name: str, value: float, unit: str = None, **kwargs):
        """Log performance metric."""
        log_data = self._format_message(f"Performance: {metric_name}", {
            "performance": True,
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            **kwargs
        })
        self.base_logger.info(json.dumps(log_data))


def set_correlation_id(corr_id: str = None) -> str:
    """Set correlation ID for request tracing."""
    if corr_id is None:
        corr_id = str(uuid.uuid4())
    correlation_id.set(corr_id)
    return corr_id


def set_request_id(req_id: str = None) -> str:
    """Set request ID for request tracing."""
    if req_id is None:
        req_id = str(uuid.uuid4())
    request_id.set(req_id)
    return req_id


def set_user_id(user: str):
    """Set user ID for request tracing."""
    user_id.set(user)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id.get()


def get_request_id() -> Optional[str]:
    """Get current request ID."""
    return request_id.get()


def get_user_id() -> Optional[str]:
    """Get current user ID."""
    return user_id.get()


def setup_logging():
    settings = get_settings()
    
    # Remove default handler
    logger.remove()
    
    # Console handler with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level=settings.monitoring.log_level,
        colorize=True,
    )
    
    # File handler for all logs
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        log_dir / "microvm-sandbox.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="100 MB",
        retention="30 days",
        compression="gz",
        serialize=False,
    )
    
    # Error file handler
    logger.add(
        log_dir / "microvm-sandbox-error.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="ERROR",
        rotation="50 MB",
        retention="90 days",
        compression="gz",
        serialize=False,
    )
    
    # JSON structured logging for production
    logger.add(
        log_dir / "microvm-sandbox.json",
        format="{message}",
        level="INFO",
        rotation="100 MB",
        retention="30 days",
        compression="gz",
        serialize=True,
    )
    
    logger.info("Logging system initialized")


def get_logger(name: str):
    """Get a basic logger instance."""
    return logger.bind(component=name)


def get_structured_logger(component: str) -> StructuredLogger:
    """Get a structured logger instance with correlation ID support."""
    return StructuredLogger(component)