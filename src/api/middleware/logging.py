import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from src.utils.logging import (
    set_correlation_id, set_request_id, set_user_id,
    get_structured_logger
)
from src.utils.metrics import metrics


class LoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced logging middleware with correlation IDs and metrics."""
    
    def __init__(self, app):
        super().__init__(app)
        self.structured_logger = get_structured_logger("api.middleware")
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extract or generate correlation and request IDs
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Extract user ID from authorization header if available
        user_id = None
        auth_header = request.headers.get("Authorization")
        if auth_header:
            # This would be extracted from JWT token in a real implementation
            # For now, we'll use a placeholder
            user_id = "authenticated_user"
        
        # Set context variables for this request
        set_correlation_id(correlation_id)
        set_request_id(request_id)
        if user_id:
            set_user_id(user_id)
        
        # Store IDs in request state for other middleware/handlers
        request.state.correlation_id = correlation_id
        request.state.request_id = request_id
        request.state.user_id = user_id
        
        # Log request start
        self.structured_logger.info(
            "API request started",
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            query_params=dict(request.query_params),
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("User-Agent"),
            content_length=request.headers.get("Content-Length"),
            content_type=request.headers.get("Content-Type")
        )
        
        try:
            response: Response = await call_next(request)
            process_time = time.time() - start_time
            
            # Log request completion
            self.structured_logger.info(
                "API request completed",
                method=request.method,
                url=str(request.url),
                path=request.url.path,
                status_code=response.status_code,
                process_time_seconds=process_time,
                response_size=response.headers.get("Content-Length")
            )
            
            # Record metrics
            metrics.record_api_request(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code,
                duration=process_time
            )
            
            # Add correlation headers to response
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            
            # Log request failure
            self.structured_logger.error(
                "API request failed",
                error=e,
                method=request.method,
                url=str(request.url),
                path=request.url.path,
                process_time_seconds=process_time,
                error_type=type(e).__name__,
                error_message=str(e)
            )
            
            # Record error metrics
            metrics.record_api_request(
                method=request.method,
                endpoint=request.url.path,
                status=500,
                duration=process_time
            )
            
            metrics.record_error("api", type(e).__name__)
            
            raise